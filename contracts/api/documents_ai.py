
"""
API views for CLM One repository functionality.
"""
import hashlib
import json
import logging
import secrets
from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from contracts.services.repository import BulkUpdateValidationError, get_repository_service
from contracts.services.salesforce import (
    CANONICAL_CONTRACT_FIELDS,
    build_salesforce_authorize_url,
    create_salesforce_sync_run,
    decrypt_salesforce_token,
    default_field_map_records,
    encrypt_salesforce_token,
    exchange_salesforce_code_for_tokens,
    get_effective_field_map_records,
    ingest_salesforce_records,
    SalesforceSyncError,
    refresh_salesforce_access_token,
    salesforce_oauth_is_configured,
    sync_salesforce_connection,
)
from contracts.services.webhooks import queue_webhook_event
from contracts.services.esign import ESignReconciliationError, apply_esign_event
from contracts.services.executive_analytics import build_executive_analytics_snapshot
from contracts.services.obligations import get_obligation_service
from contracts.services.netsuite import (
    NetSuiteSyncError,
    fetch_netsuite_records,
    ingest_netsuite_records,
    map_netsuite_record,
    netsuite_is_configured,
)
from contracts.domain.contracts import ListParams
from contracts.middleware import log_action
from contracts.permissions import ContractAction, can_access_contract_action, can_manage_organization
from contracts.tenancy import get_user_organization
from contracts.tenancy import scope_queryset_for_organization
from contracts.models import (
    Contract,
    Document,
    OrganizationAPIToken,
    OrganizationContractFieldMap,
    Organization,
    OrganizationMembership,
    SalesforceOrganizationConnection,
    OrganizationSCIMGroup,
    OrganizationSCIMGroupMembership,
    ExecutiveDashboardPreset,
    WebhookDelivery,
    WebhookEndpoint,
    SalesforceSyncRun,
    UserProfile,
    AuditLog,
    SignatureRequest,
    BackgroundJob,
    OnboardingProgress,
    BillingPlan,
    OrgBillingSubscription,
    UsageRecord,
    ApprovalRequest,
    ClauseTemplate,
    ClausePlaybook,
    ClauseVariant,
    ClauseUsageEvent,
    DocumentReviewRun,
    Matter,
    ContractReviewFinding,
)

logger = logging.getLogger(__name__)
User = get_user_model()



# --- domain-specific imports (originally declared mid-module) ---
from contracts.services.dsar import get_dsar_service
from contracts.services.contract_versions import get_version_service
from contracts.models import ContractVersion
from contracts.services.ai_drafting import get_ai_drafting_service
from contracts.models import ClauseRecommendation
from contracts.services.admin_console import get_admin_console_service
from contracts.models import OrgPolicy
from contracts.services.permissions import get_permission_service
from contracts.services.onboarding import get_onboarding_service
from contracts.services.billing import get_billing_service
from contracts.services.compliance_portal import get_compliance_portal_service
from contracts.services.approval_workflow import get_approval_workflow_service
from contracts.services.clause_analytics import get_clause_analytics_service
from contracts.services.mandatory_clauses import get_mandatory_enforcement_service
from contracts.services.playbook import get_playbook_service
from contracts.services.search_api import (
    get_contract_search_service,
    get_clause_search_service,
)
from contracts.models import SearchTelemetryEvent
from contracts.services.subprocessor_alerts import get_subprocessor_alert_service
from contracts.services.retention_jobs import get_retention_service
from contracts.services.webhook_management import get_webhook_management_service
from contracts.services.inbound_import import get_inbound_import_service
from contracts.services.crm_sync import get_crm_sync_service
from contracts.services.postgres_health import get_postgres_health_service
from contracts.services.cve_gate import get_cve_gate_service
from contracts.services.restore_drill import get_restore_drill_service
from contracts.models import RestoreDrill as _RestoreDrillModel


from contracts.api._helpers import (
    _error_response,
    _scim_response,
    _api_version_response,
    _scim_paginated_list,
    _api_paginated_contracts,
    _resolve_scim_organization,
    _resolve_api_organization,
    _require_org_member_context,
)


# ── Document upload ingestion ─────────────────────────────────────────────────

_ALLOWED_UPLOAD_EXTENSIONS = {
    '.pdf', '.docx', '.txt', '.md', '.csv', '.html', '.xml', '.json',
}
_MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


_REVIEW_STEP_LABELS = ('Uploaded', 'Extracting', 'Classifying', 'Matching playbook', 'AI reviewing', 'Review ready')


def _apply_document_review_contract_state(contract, *, status, lifecycle_stage=None, actor=None, request=None, reason=''):
    from contracts.services.contract_lifecycle import apply_contract_operational_position
    if not contract:
        return
    apply_contract_operational_position(
        contract,
        status=status,
        lifecycle_stage=lifecycle_stage,
        actor=actor,
        system=True,
        reason=reason,
        request=request,
    )


def _review_steps(current_step, *, blocked=False):
    """Return a dependency-aware processing timeline without implying success."""
    current_index = _REVIEW_STEP_LABELS.index(current_step) if current_step in _REVIEW_STEP_LABELS else 0
    steps = []
    for index, label in enumerate(_REVIEW_STEP_LABELS):
        state = 'complete' if index < current_index else ('active' if index == current_index else 'pending')
        if blocked and index == current_index:
            state = 'blocked'
        steps.append({'key': label.lower().replace(' ', '-'), 'label': label, 'status': state})
    return steps


def _payment_terms_are_confirmed(metadata):
    """Payment terms only block when the agreement produced a term to confirm."""
    metadata = metadata or {}
    hint = (metadata.get('payment_terms') or '').strip()
    if not hint:
        return True
    return bool(metadata.get('payment_terms_confirmed'))


def _classification_pending_labels(contract, metadata):
    """Human-readable classification fields still needing confirmation."""
    metadata = metadata or {}
    pending = []
    if not (contract.counterparty or '').strip():
        pending.append('Counterparty')
    if contract.contract_type == Contract.ContractType.OTHER:
        pending.append('Contract type')
    if not ((contract.governing_law or '').strip() and metadata.get('governing_law_confirmed')):
        pending.append('Governing law')
    if not (contract.value is not None and metadata.get('value_confirmed')):
        pending.append('Contract value')
    if not _payment_terms_are_confirmed(metadata):
        pending.append('Payment terms')
    return pending


def _seed_upload_confirmation_metadata(contract, document):
    """Treat Upload & Review form values as the first confirmation pass."""
    metadata = {}
    try:
        text = document.ocr_review.extracted_text or ''
    except Exception:
        text = ''
    if (text or '').strip():
        metadata.update(_metadata_from_text(text))
    if (contract.governing_law or '').strip():
        metadata['governing_law_confirmed'] = True
    if contract.value is not None:
        metadata['value_confirmed'] = True
    # Payment terms are not collected on the upload form. Keep any extracted
    # hint for the review workspace, but do not block AI on a second pass.
    metadata['payment_terms_confirmed'] = True
    return metadata


def _metadata_from_text(text):
    """Conservative extraction hints: surfaced for confirmation, never silently approved."""
    from contracts.services.agreement_metadata_extract import metadata_hints_from_text

    hints = metadata_hints_from_text(text)
    import re
    payment_match = re.search(r'(?:payment|invoice)[^.\n]{0,100}', text or '', re.I)
    hints['payment_terms'] = payment_match.group(0).strip() if payment_match else ''
    return hints


@login_required
@require_http_methods(['POST'])
def document_extract_preview_api(request):
    """Dry-run metadata extraction for Upload & Review after file selection.

    Does not create a Document or Contract — returns confirmation-ready field
    hints with confidence labels for the client to populate the form.
    """
    from contracts.services.agreement_metadata_extract import (
        extract_agreement_metadata,
        extract_text_from_upload,
    )

    organization = get_user_organization(request.user)
    if organization is None:
        return _error_response(request, 'No organization found for this user.', 400)

    uploaded_file = request.FILES.get('file')
    if uploaded_file is None:
        return _error_response(request, 'No file provided.', 400)

    if uploaded_file.size > _MAX_UPLOAD_BYTES:
        return _error_response(request, f'File exceeds maximum size of {_MAX_UPLOAD_BYTES // (1024*1024)} MB.', 413)

    import os
    filename = uploaded_file.name or ''
    ext = os.path.splitext(filename)[1].lower()
    if ext not in _ALLOWED_UPLOAD_EXTENSIONS:
        return _error_response(
            request,
            f'File type {ext!r} is not supported. Allowed: {", ".join(sorted(_ALLOWED_UPLOAD_EXTENSIONS))}',
            415,
        )

    text, source = extract_text_from_upload(uploaded_file, filename)
    result = extract_agreement_metadata(text, filename=filename, extraction_source=source)
    return JsonResponse({'ok': True, 'extraction': result.to_dict()})


@login_required
@require_http_methods(['POST'])
def document_upload_api(request):
    """Ingest a contract document file: upload → hash → OCR queue → AI extraction.

    Multipart POST:
      file        — required, the document file
      contract_id — optional, associate with an existing contract
      document_type — optional, one of Document.DocType choices (default OTHER)
      title       — optional, defaults to the original filename
    """
    organization = get_user_organization(request.user)
    if organization is None:
        return _error_response(request, 'No organization found for this user.', 400)

    uploaded_file = request.FILES.get('file')
    if uploaded_file is None:
        return _error_response(request, 'No file provided.', 400)

    if uploaded_file.size > _MAX_UPLOAD_BYTES:
        return _error_response(request, f'File exceeds maximum size of {_MAX_UPLOAD_BYTES // (1024*1024)} MB.', 413)

    import os
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext not in _ALLOWED_UPLOAD_EXTENSIONS:
        return _error_response(
            request,
            f'File type {ext!r} is not supported. Allowed: {", ".join(sorted(_ALLOWED_UPLOAD_EXTENSIONS))}',
            415,
        )

    contract_id = request.POST.get('contract_id')
    contract = None
    if contract_id:
        contract = Contract.objects.filter(
            id=contract_id,
            organization=organization,
        ).first()
        if contract is None:
            return _error_response(request, 'Contract not found or access denied.', 404)

    create_contract = request.POST.get('create_contract') in {'1', 'true', 'True', 'on'}
    contract_payload = None
    if create_contract and contract is None:
        contract_type = request.POST.get('contract_type') or Contract.ContractType.OTHER
        if contract_type not in {value for value, _ in Contract.ContractType.choices}:
            return _error_response(request, 'Invalid contract type.', 400)
        start_date = parse_date(request.POST.get('start_date', '')) if request.POST.get('start_date') else None
        end_date = parse_date(request.POST.get('end_date', '')) if request.POST.get('end_date') else None
        if end_date and start_date and end_date < start_date:
            return _error_response(request, 'Expiry date must be on or after the effective date.', 400)
        owner_id = request.POST.get('owner_id') or request.user.pk
        owner = User.objects.filter(
            pk=owner_id,
            organization_memberships__organization=organization,
            organization_memberships__is_active=True,
        ).distinct().first()
        if owner is None:
            return _error_response(request, 'Owner must be an active workspace member.', 400)
        value = None
        if (request.POST.get('value') or '').strip():
            try:
                value = Decimal(request.POST['value'])
            except (InvalidOperation, ValueError):
                return _error_response(request, 'Contract value must be a valid number.', 400)
            if value < 0:
                return _error_response(request, 'Contract value cannot be negative.', 400)
        matter = None
        if request.POST.get('matter_id'):
            matter = Matter.objects.filter(pk=request.POST['matter_id'], organization=organization).first()
            if matter is None:
                return _error_response(request, 'Related matter not found or access denied.', 404)
        contract_payload = {
            'organization': organization,
            'title': (request.POST.get('title') or '').strip() or os.path.splitext(uploaded_file.name)[0],
            'contract_type': contract_type,
            'counterparty': (request.POST.get('counterparty') or '').strip(),
            'business_unit': (request.POST.get('business_unit') or '').strip(),
            'matter': matter,
            'owner': owner,
            'created_by': request.user,
            'value': value,
            'currency': request.POST.get('currency') or Contract.Currency.USD,
            'start_date': start_date,
            'end_date': end_date,
            'governing_law': (request.POST.get('governing_law') or '').strip(),
            'dpa_attached': request.POST.get('dpa_attached') in {'1', 'true', 'True', 'on'},
            'status': Contract.Status.IN_PROGRESS,
            'lifecycle_stage': Contract.LifecycleStage.INTAKE,
        }

    doc_type = request.POST.get('document_type', Document.DocType.OTHER)
    if doc_type not in {c[0] for c in Document.DocType.choices}:
        doc_type = Document.DocType.OTHER

    title = (request.POST.get('title') or '').strip() or uploaded_file.name

    document = None
    try:
        with transaction.atomic():
            if contract_payload is not None:
                from contracts.services.contract_provenance import (
                    EVENT_PROVENANCE_ASSIGNED,
                    OriginKind,
                    apply_provenance_fields,
                    provenance_snapshot,
                )
                contract = Contract(**contract_payload)
                apply_provenance_fields(
                    contract,
                    origin_kind=OriginKind.UPLOAD,
                    origin_channel='documents_ai_upload',
                    actor=request.user,
                    lock=True,
                    validate=True,
                )
                contract.save()
                get_version_service().create_version(
                    contract, changed_by=request.user, change_summary='Initial source document uploaded.'
                )
                snap = provenance_snapshot(contract)
                log_action(
                    request.user, AuditLog.Action.CREATE, 'Contract', contract.pk, str(contract),
                    organization=organization, request=request,
                    event_type='contract.uploaded',
                    changes={
                        'event': 'contract.uploaded',
                        'equivalent_event': 'contract.record.created',
                        'status': contract.status,
                        'contract_type': contract.contract_type,
                        'provenance': snap,
                    },
                )
                log_action(
                    request.user, AuditLog.Action.CREATE, 'Contract', contract.pk, str(contract),
                    organization=organization, request=request,
                    event_type=EVENT_PROVENANCE_ASSIGNED,
                    changes={'event': EVENT_PROVENANCE_ASSIGNED, 'provenance': snap},
                )
            prior_document = None
            if contract is not None:
                prior_document = contract.documents.order_by('-version', '-created_at').first()
            from contracts.services.document_version_service import create_document_version

            document, _version = create_document_version(
                organization=organization,
                title=title,
                document_type=doc_type,
                status=Document.Status.DRAFT,
                contract=contract,
                uploaded_by=request.user,
                actor=request.user,
                source='ai_upload',
                derived_from_document=prior_document,
                parent_document=(prior_document.parent_document or prior_document) if prior_document else None,
                file=uploaded_file,
                request=request,
                supersede_prior=True,
            )
            if contract and prior_document:
                get_version_service().create_version(
                    contract, changed_by=request.user,
                    change_summary=f'Revised source document uploaded as version {document.version}.',
                )
            review_run = None
            if contract:
                review_run = DocumentReviewRun.objects.create(
                    organization=organization,
                    contract=contract,
                    document=document,
                    status=DocumentReviewRun.Status.UPLOADED,
                    current_step='Uploaded',
                    progress_steps=_review_steps('Uploaded'),
                    review_objective=(request.POST.get('review_objective') or '').strip(),
                    extracted_metadata=_seed_upload_confirmation_metadata(contract, document),
                    primary_next_action='Extract document text and prepare the review for human confirmation.',
                )
            log_action(
                request.user, AuditLog.Action.CREATE, 'Document', document.pk, str(document),
                organization=organization, request=request,
                event_type='document.uploaded',
                changes={
                    'event': 'document.uploaded',
                    'contract_id': contract.pk if contract else None,
                    'file_hash': document.file_hash,
                    'file_size': document.file_size,
                },
            )
            if contract and contract.dpa_attached:
                from contracts.services.dpa_activation import ensure_dpa_review_pack
                ensure_dpa_review_pack(contract, request.user, request=request)
    except Exception:
        logger.exception(
            'document_upload_failed title=%r org=%s',
            title, organization.id if organization else None,
        )
        # Best-effort: if the file was committed to object storage before the
        # DB INSERT failed, delete the orphaned object so storage and the DB
        # remain consistent.  Cleanup failure is logged but never re-raised so
        # the original error is preserved and the caller receives a clean 503.
        _cleanup_orphaned_upload(document)
        return _error_response(request, 'File could not be stored. Please try again later.', 503)

    ocr_status = 'unknown'
    confidence = None
    ocr_source = None
    try:
        ocr_review = document.ocr_review
        ocr_status = ocr_review.status
        confidence = float(ocr_review.confidence_score) if ocr_review.confidence_score is not None else None
        ocr_source = ocr_review.source
    except Exception:
        pass

    review_requested = request.POST.get('run_ai_review') in {'1', 'true', 'True', 'on'}
    ai_review = {'requested': False, 'status': 'not-requested', 'finding_count': 0}
    if review_requested and contract is not None:
        ai_review = _run_uploaded_contract_review(
            request=request,
            organization=organization,
            document=document,
            review_run=review_run,
        )

    return JsonResponse(
        {
            'ok': True,
            'document_id': document.id,
            'title': document.title,
            'file_hash': document.file_hash,
            'file_size': document.file_size,
            'mime_type': document.mime_type,
            'document_type': document.document_type,
            'contract_id': contract.pk if contract else None,
            'contract_url': reverse('contracts:contract_detail', kwargs={'pk': contract.pk}) if contract else None,
            'contract_review_url': (
                reverse('contracts:contract_review_workspace', kwargs={'pk': contract.pk})
                if contract else None
            ),
            'review_run_id': review_run.pk if review_run else None,
            'ocr': {
                'status': ocr_status,
                'confidence': confidence,
                'source': ocr_source,
            },
            'ai_review': ai_review,
        },
        status=201,
    )


def _cleanup_orphaned_upload(document):
    """Delete an object that was written to storage but never committed to the DB.

    Called when Document.save() raises after the storage write succeeded.
    On cleanup failure the error is logged — the original failure is NOT masked.
    The orphan-detection command will surface any objects that slip through.
    """
    if document is None:
        return
    try:
        name = getattr(document.file, 'name', None)
        if name:
            document.file.storage.delete(name)
            logger.info('orphan_cleanup_ok key_suffix=%r', name.split('/')[-1])
    except Exception:
        logger.exception(
            'orphan_cleanup_failed key_suffix=%r',
            getattr(document.file, 'name', '?').split('/')[-1],
        )


def _run_uploaded_contract_review(*, request, organization, document, review_run=None):
    """Run an optional AI review after the agreement has been safely stored."""
    review = {
        'requested': True,
        'status': 'unavailable',
        'finding_count': 0,
        'message': 'AI review is not available for this workspace.',
    }

    def record_outcome():
        log_action(
            request.user,
            AuditLog.Action.CREATE,
            'Document',
            document.pk,
            str(document),
            organization=organization,
            request=request,
            event_type='ai.uploaded_contract_review',
            outcome=AuditLog.Outcome.SUCCESS if review['status'] == 'completed' else AuditLog.Outcome.FAILURE,
            changes={
                'event': 'ai.uploaded_contract_review',
                'review_status': review['status'],
                'finding_count': review['finding_count'],
                'citation_count': review.get('citation_count', 0),
                'review_message': review.get('message', ''),
                'document_id': document.pk,
            },
        )

    def update_run(status, step, *, message='', model='', metadata=None, playbook_matched=None, analysis_completed=False, citation_count=None):
        review['current_step'] = step
        if review_run is None:
            return
        review_run.status = status
        review_run.current_step = step
        review_run.progress_steps = _review_steps(
            step,
            blocked=status in {
                DocumentReviewRun.Status.CLASSIFICATION_REQUIRED,
                DocumentReviewRun.Status.PLAYBOOK_REQUIRED,
                DocumentReviewRun.Status.AI_REVIEW_INCOMPLETE,
            },
        )
        review_run.primary_next_action = message
        if model:
            review_run.review_model = model
        if metadata is not None:
            review_run.extracted_metadata = metadata
        if playbook_matched is not None:
            review_run.governance_sources = {
                **(review_run.governance_sources or {}),
                'governance_charter': 'Current CLM One Governance Charter',
                'approved_playbook_matched': playbook_matched,
            }
        if analysis_completed:
            review_run.governance_sources = {
                **(review_run.governance_sources or {}),
                'ai_analysis_completed': True,
            }
        if citation_count is not None:
            review_run.governance_sources = {
                **(review_run.governance_sources or {}),
                'citation_count': citation_count,
            }
        if status != DocumentReviewRun.Status.AI_REVIEW_IN_PROGRESS:
            review_run.completed_at = timezone.now()
        review_run.save()

    policy, _ = OrgPolicy.objects.get_or_create(organization=organization)
    if not policy.ai_features_enabled:
        review['message'] = 'AI-assisted features are disabled for this workspace.'
        update_run(DocumentReviewRun.Status.AI_REVIEW_INCOMPLETE, 'AI reviewing', message=review['message'])
        record_outcome()
        return review

    try:
        text = document.ocr_review.extracted_text or ''
    except Exception:
        text = ''
    if not text.strip():
        review.update({
            'status': 'needs-readable-text',
            'message': 'The agreement was uploaded, but no readable text was found for AI review.',
        })
        if document.contract_id:
            _apply_document_review_contract_state(
                document.contract,
                status=Contract.Status.IN_PROGRESS,
                lifecycle_stage='INTERNAL_REVIEW',
                actor=request.user,
                request=request,
                reason='document_review_missing_text',
            )
        update_run(DocumentReviewRun.Status.AI_REVIEW_INCOMPLETE, 'Extracting', message=review['message'])
        record_outcome()
        return review

    review_metadata = review_run.extracted_metadata or {} if review_run else {}
    review_governance = review_run.governance_sources or {} if review_run else {}
    pending_confirmations = _classification_pending_labels(document.contract, review_metadata) if document.contract_id else [
        'Counterparty', 'Contract type', 'Governing law', 'Contract value',
    ]
    classification_confirmed = not pending_confirmations
    if not classification_confirmed:
        review.update({
            'status': 'needs-input',
            'message': 'Contract classification and required metadata must be confirmed before AI review can begin.',
            'pending_confirmations': pending_confirmations,
        })
        if document.contract_id:
            _apply_document_review_contract_state(
                document.contract,
                status=Contract.Status.IN_PROGRESS,
                lifecycle_stage='INTERNAL_REVIEW',
                actor=request.user,
                request=request,
                reason='document_review_missing_text',
            )
        update_run(DocumentReviewRun.Status.CLASSIFICATION_REQUIRED, 'Classifying', message=review['message'])
        record_outcome()
        return review
    if not (review_governance.get('approved_playbook_matched') or review_governance.get('selected_playbook_id')):
        review.update({
            'status': 'playbook-required',
            'message': 'Select an approved contract playbook before AI review can begin.',
            'pending_confirmations': ['Review playbook'],
        })
        if document.contract_id:
            _apply_document_review_contract_state(
                document.contract,
                status=Contract.Status.IN_PROGRESS,
                lifecycle_stage='INTERNAL_REVIEW',
                actor=request.user,
                request=request,
                reason='document_review_missing_text',
            )
        update_run(DocumentReviewRun.Status.PLAYBOOK_REQUIRED, 'Matching playbook', message=review['message'])
        record_outcome()
        return review

    from contracts.services.ai_contract_review import (
        AIContractReviewUnavailable,
        review_uploaded_contract,
    )
    from contracts.services.ai_extraction import AIExtractionError

    try:
        if document.contract_id:
            _apply_document_review_contract_state(
                document.contract,
                status=Contract.Status.IN_PROGRESS,
                lifecycle_stage='INTERNAL_REVIEW',
                actor=request.user,
                request=request,
                reason='document_review_started',
            )
        update_run(DocumentReviewRun.Status.AI_REVIEW_IN_PROGRESS, 'AI reviewing')
        result = review_uploaded_contract(
            document=document,
            organization=organization,
            text=text,
            user=request.user,
            review_run=review_run,
        )
    except AIContractReviewUnavailable as exc:
        review['message'] = str(exc)
    except AIExtractionError:
        logger.exception('uploaded_contract_ai_review_invalid_response document=%s', document.pk)
        review.update({
            'status': 'failed',
            'message': 'AI review could not validate a provider response. The agreement is safely stored.',
        })
    except Exception:
        logger.exception('uploaded_contract_ai_review_failed document=%s', document.pk)
        review.update({
            'status': 'failed',
            'message': 'AI review could not be completed. The agreement is safely stored.',
        })
    else:
        review.update({
            'status': 'completed',
            'finding_count': result.flags_created,
            'citation_count': result.spans_reviewed,
            'model': result.model,
            'message': (
                f'{result.flags_created} potential issue(s) were added to the risk register for human review.'
                if result.flags_created else
                'No potential issues were found in the clauses reviewed. Human review is still required.'
            ),
        })

        if document.contract_id:
            _apply_document_review_contract_state(
                document.contract,
                status=Contract.Status.IN_PROGRESS,
                lifecycle_stage='INTERNAL_REVIEW',
                actor=request.user,
                request=request,
                reason='document_review_completed',
            )
        update_run(
            DocumentReviewRun.Status.READY,
            'Review ready',
            message=(
                'Resolve or route the cited findings before negotiation, approval, or signature.'
                if result.flags_created else
                'Confirm the clear review outcome before routing the targeted internal approval.'
            ),
            model=result.model,
            metadata={
                **_metadata_from_text(text),
                **{
                    key: value for key, value in (review_run.extracted_metadata or {}).items()
                    if key.endswith('_confirmed')
                },
            },
            playbook_matched=(
                result.playbook_matched
                or bool((review_run.governance_sources or {}).get('selected_playbook_id'))
            ),
            analysis_completed=True,
            citation_count=result.spans_reviewed,
        )

    if review['status'] != 'completed':
        if document.contract_id:
            _apply_document_review_contract_state(
                document.contract,
                status=Contract.Status.IN_PROGRESS,
                lifecycle_stage='INTERNAL_REVIEW',
                actor=request.user,
                request=request,
                reason='document_review_missing_text',
            )
        update_run(DocumentReviewRun.Status.AI_REVIEW_INCOMPLETE, 'AI reviewing', message=review['message'])

    record_outcome()
    return review


def _resolve_ai_contract(request, contract_id, *, action=ContractAction.AI, require_provider=False):
    organization = get_user_organization(request.user)
    if organization is None:
        return None, None, _error_response(request, 'No workspace found for this user.', 400)
    contract = Contract.objects.filter(id=contract_id, organization=organization).first()
    if contract is None:
        return organization, None, _error_response(
            request, 'Contract not found or access denied.', 404,
        )
    if not can_access_contract_action(request.user, contract, action):
        return organization, contract, _error_response(
            request, 'You do not have permission to perform this action.', 403,
        )
    policy, _ = OrgPolicy.objects.get_or_create(organization=organization)
    if not policy.ai_features_enabled:
        return organization, contract, _error_response(
            request, 'AI-assisted features are disabled for this workspace.', 403,
        )
    if require_provider and (
        not getattr(settings, 'GEMINI_AI_ENABLED', False)
        or not getattr(settings, 'GEMINI_API_KEY', '')
    ):
        return organization, contract, _error_response(
            request,
            'Clause extraction is not configured. Ask a workspace administrator to configure the AI provider.',
            503,
        )
    return organization, contract, None


@login_required
@require_http_methods(['GET', 'POST'])
def contract_ai_extract_api(request, contract_id):
    """Read cached citations or explicitly extract them from contract documents.

    GET is read-only. POST calls the configured provider and replaces citations
    only after a valid structured response has been received.
    """
    from contracts.services.ai_extraction import (
        AIExtractionError,
        extract_clause_spans,
        get_extraction_model,
        get_spans_summary,
    )
    from contracts.models import DocumentOCRReview

    organization, contract, error = _resolve_ai_contract(
        request,
        contract_id,
        require_provider=request.method == 'POST',
    )
    if error:
        return error

    selected_document_id = None
    if request.method == 'POST':
        try:
            payload = json.loads(request.body or '{}')
        except (TypeError, ValueError):
            return _error_response(request, 'Request body must be valid JSON.', 400)
        selected_document_id = payload.get('document_id')

    results = []
    documents = contract.documents.select_related('organization', 'contract').order_by('created_at')
    if selected_document_id is not None:
        documents = documents.filter(pk=selected_document_id)
        if not documents.exists():
            return _error_response(request, 'Document not found for this contract.', 404)

    failed = 0
    extracted_count = 0
    for document in documents:
        try:
            ocr_review = document.ocr_review
        except DocumentOCRReview.DoesNotExist:
            results.append({
                'document_id': document.id,
                'title': document.title,
                'status': 'no-ocr-review',
                'spans': None,
            })
            continue

        extracted_text = ocr_review.extracted_text or ''
        if request.method == 'POST':
            if not extracted_text.strip():
                results.append({
                    'document_id': document.id,
                    'title': document.title,
                    'ocr_status': ocr_review.status,
                    'status': 'no-readable-text',
                    'spans': get_spans_summary(document),
                })
                continue
            try:
                created = extract_clause_spans(
                    extracted_text,
                    organization,
                    document,
                    replace_existing=True,
                )
                extracted_count += len(created)
            except AIExtractionError as exc:
                failed += 1
                results.append({
                    'document_id': document.id,
                    'title': document.title,
                    'status': 'provider-error',
                    'error': str(exc),
                    'spans': get_spans_summary(document),
                })
                continue
            except Exception:
                logger.exception('ai_clause_extraction_failed contract=%s document=%s', contract.pk, document.pk)
                failed += 1
                results.append({
                    'document_id': document.id,
                    'title': document.title,
                    'status': 'provider-error',
                    'error': 'The AI provider could not complete clause extraction.',
                    'spans': get_spans_summary(document),
                })
                continue

        results.append({
            'document_id': document.id,
            'title': document.title,
            'ocr_status': ocr_review.status,
            'ocr_confidence': float(ocr_review.confidence_score) if ocr_review.confidence_score else None,
            'status': 'ok',
            'spans': get_spans_summary(document),
        })

    response_payload = {
        'contract_id': contract_id,
        'document_count': len(results),
        'provider_configured': bool(
            getattr(settings, 'GEMINI_AI_ENABLED', False)
            and getattr(settings, 'GEMINI_API_KEY', '')
        ),
        'extraction_model': get_extraction_model(),
        'results': results,
    }
    if request.method == 'POST':
        outcome = AuditLog.Outcome.FAILURE if failed and not extracted_count else AuditLog.Outcome.SUCCESS
        log_action(
            request.user,
            AuditLog.Action.CREATE,
            'Contract',
            contract.pk,
            str(contract),
            organization=organization,
            request=request,
            event_type='ai.clauses_extracted',
            outcome=outcome,
            changes={
                'event': 'ai.clauses_extracted',
                'document_id': selected_document_id,
                'span_count': extracted_count,
                'failed_document_count': failed,
                'model': get_extraction_model(),
            },
        )
        response_payload['created'] = extracted_count
        if failed and not extracted_count:
            return JsonResponse(response_payload, status=502)
        return JsonResponse(response_payload, status=201)
    return JsonResponse(response_payload)


@login_required
@require_http_methods(['POST'])
def ai_extraction_span_review_api(request, contract_id, span_id):
    """Record the human disposition of one tenant-scoped extracted citation."""
    from contracts.models import AIExtractionSpan

    organization, contract, error = _resolve_ai_contract(request, contract_id)
    if error:
        return error
    span = AIExtractionSpan.objects.filter(
        pk=span_id,
        organization=organization,
        document__contract=contract,
    ).first()
    if span is None:
        return _error_response(request, 'Clause citation not found or access denied.', 404)
    try:
        payload = json.loads(request.body or '{}')
    except (TypeError, ValueError):
        return _error_response(request, 'Request body must be valid JSON.', 400)
    status = str(payload.get('status') or '').upper()
    allowed = {AIExtractionSpan.ReviewStatus.CONFIRMED, AIExtractionSpan.ReviewStatus.DISMISSED}
    if status not in allowed:
        return _error_response(request, 'Status must be CONFIRMED or DISMISSED.', 400)
    previous = span.review_status
    span.review_status = status
    span.reviewed_by = request.user
    span.reviewed_at = timezone.now()
    span.save(update_fields=['review_status', 'reviewed_by', 'reviewed_at'])
    log_action(
        request.user,
        AuditLog.Action.UPDATE,
        'Contract',
        contract.pk,
        str(contract),
        organization=organization,
        request=request,
        event_type='ai.clause_reviewed',
        changes={
            'event': 'ai.clause_reviewed',
            'span_id': span.pk,
            'document_id': span.document_id,
            'label': span.label,
            'previous_status': previous,
            'new_status': status,
        },
    )
    return JsonResponse({
        'ok': True,
        'span_id': span.pk,
        'review_status': span.review_status,
        'reviewed_by': request.user.get_full_name() or request.user.username,
        'reviewed_at': span.reviewed_at.isoformat(),
    })


@login_required
@require_http_methods(['POST'])
def contract_review_finding_action_api(request, contract_id, finding_id):
    """Apply a human-owned decision to a governed AI finding.

    The endpoint deliberately records only a review disposition or a routing
    request. It never changes a playbook, approves a deviation, or sends a
    redline externally.
    """
    organization, contract, error = _resolve_ai_contract(request, contract_id, action=ContractAction.EDIT)
    if error:
        return error
    finding = ContractReviewFinding.objects.filter(
        pk=finding_id, contract=contract, document__organization=organization,
    ).select_related('risk_log').first()
    if finding is None:
        return _error_response(request, 'Review finding not found or access denied.', 404)
    try:
        payload = json.loads(request.body or '{}')
    except (TypeError, ValueError):
        return _error_response(request, 'Request body must be valid JSON.', 400)

    action = str(payload.get('action') or '').strip().lower()
    allowed = {
        'accept', 'dismiss', 'edit_assessment', 'accept_redline', 'edit_redline',
        'assign', 'comment', 'escalate', 'request_information', 'create_exception', 'resolve',
    }
    if action not in allowed:
        return _error_response(request, 'Unsupported finding action.', 400)

    updates = []
    previous_status = finding.status
    if action == 'accept':
        finding.status = ContractReviewFinding.Status.IN_PROGRESS
        updates.append('status')
    elif action == 'dismiss':
        reason = str(payload.get('dismissal_reason') or '').upper()
        if finding.severity in {ContractReviewFinding.Severity.CRITICAL, ContractReviewFinding.Severity.HIGH} and not reason:
            return _error_response(request, 'A dismissal reason is required for Critical and High findings.', 400)
        if reason and reason not in ContractReviewFinding.DismissalReason.values:
            return _error_response(request, 'Invalid dismissal reason.', 400)
        finding.status = ContractReviewFinding.Status.DISMISSED
        finding.dismissal_reason = reason
        updates.extend(['status', 'dismissal_reason'])
    elif action == 'edit_assessment':
        finding.assessment = str(payload.get('assessment') or '').strip()
        updates.append('assessment')
    elif action == 'accept_redline':
        finding.status = ContractReviewFinding.Status.IN_PROGRESS
        finding.redline_draft = str(payload.get('redline') or finding.suggested_redline or '').strip()
        _apply_document_review_contract_state(
            contract,
            status=Contract.Status.IN_PROGRESS,
            lifecycle_stage='NEGOTIATION',
            actor=request.user,
            request=request,
            reason='review_finding_accept_redline',
        )
        updates.extend(['status', 'redline_draft'])
    elif action == 'edit_redline':
        finding.redline_draft = str(payload.get('redline') or '').strip()
        updates.append('redline_draft')
    elif action == 'assign':
        reviewer_id = payload.get('reviewer_id')
        reviewer = User.objects.filter(
            pk=reviewer_id,
            organization_memberships__organization=organization,
            organization_memberships__is_active=True,
        ).distinct().first()
        if reviewer is None:
            return _error_response(request, 'Reviewer must be an active workspace member.', 400)
        finding.assigned_reviewer = reviewer
        updates.append('assigned_reviewer')
    elif action == 'comment':
        finding.comment = str(payload.get('comment') or '').strip()
        updates.append('comment')
    elif action == 'escalate':
        finding.status = ContractReviewFinding.Status.ESCALATED
        updates.append('status')
    elif action == 'request_information':
        finding.status = ContractReviewFinding.Status.INFORMATION_REQUESTED
        _apply_document_review_contract_state(
            contract,
            status=Contract.Status.IN_PROGRESS,
            lifecycle_stage='INTERNAL_REVIEW',
            actor=request.user,
            request=request,
            reason='review_finding_request_information',
        )
        updates.append('status')
    elif action == 'create_exception':
        finding.status = ContractReviewFinding.Status.EXCEPTION_REQUESTED
        ApprovalRequest.objects.get_or_create(
            contract=contract,
            approval_step=f'Exception decision: {finding.title[:100]}',
            defaults={
                'organization': organization,
                'assigned_to': contract.owner,
                'comments': 'Decide the specific policy deviation recorded in this AI review finding. This is not an approval of the full contract.',
            },
        )
        _apply_document_review_contract_state(
            contract,
            status=Contract.Status.IN_PROGRESS,
            lifecycle_stage='APPROVAL',
            actor=request.user,
            request=request,
            reason='review_finding_exception_requested',
        )
        updates.append('status')
    elif action == 'resolve':
        finding.status = ContractReviewFinding.Status.RESOLVED
        finding.resolved_by = request.user
        finding.resolved_at = timezone.now()
        updates.extend(['status', 'resolved_by', 'resolved_at'])
        if finding.risk_log_id:
            finding.risk_log.status = finding.risk_log.Status.RESOLVED
            finding.risk_log.save(update_fields=['status', 'updated_at'])

    if updates:
        finding.save(update_fields=[*updates, 'updated_at'])
    log_action(
        request.user,
        AuditLog.Action.UPDATE,
        'ContractReviewFinding',
        finding.pk,
        str(finding),
        organization=organization,
        request=request,
        event_type='ai.review_finding_updated',
        changes={
            'event': 'ai.review_finding_updated',
            'finding_id': finding.pk,
            'action': action,
            'previous_status': previous_status,
            'new_status': finding.status,
            'document_id': finding.document_id,
        },
    )
    return JsonResponse({
        'ok': True,
        'finding_id': finding.pk,
        'status': finding.status,
        'status_label': finding.get_status_display(),
        'assigned_reviewer': (
            finding.assigned_reviewer.get_full_name() or finding.assigned_reviewer.username
            if finding.assigned_reviewer else None
        ),
    })


@login_required
@require_http_methods(['POST'])
def contract_review_confirm_api(request, contract_id):
    """Turn a completed clear review into a specific human-confirmation task."""
    organization, contract, error = _resolve_ai_contract(request, contract_id, action=ContractAction.EDIT)
    if error:
        return error
    review_run = contract.document_review_runs.order_by('-started_at').first()
    review_metadata = (review_run.extracted_metadata if review_run else {}) or {}
    review_governance = (review_run.governance_sources if review_run else {}) or {}
    review_is_ready = bool(
        review_run
        and review_run.status == DocumentReviewRun.Status.READY
        and review_governance.get('ai_analysis_completed')
        and (review_governance.get('approved_playbook_matched') or review_governance.get('selected_playbook_id'))
        and (contract.counterparty or '').strip()
        and contract.contract_type != Contract.ContractType.OTHER
        and (contract.governing_law or '').strip()
        and contract.value is not None
        and review_metadata.get('governing_law_confirmed')
        and review_metadata.get('value_confirmed')
        and _payment_terms_are_confirmed(review_metadata)
    )
    if not review_is_ready:
        return _error_response(request, 'Resolve the review blockers and complete AI analysis before starting human review.', 409)
    unresolved = ContractReviewFinding.objects.filter(
        contract=contract,
        status__in=[
            ContractReviewFinding.Status.OPEN,
            ContractReviewFinding.Status.IN_PROGRESS,
            ContractReviewFinding.Status.ESCALATED,
            ContractReviewFinding.Status.INFORMATION_REQUESTED,
            ContractReviewFinding.Status.EXCEPTION_REQUESTED,
        ],
    ).exists()
    if unresolved:
        return _error_response(request, 'Resolve, dismiss, or route all open findings before confirming the review outcome.', 409)
    approval, created = ApprovalRequest.objects.get_or_create(
        contract=contract,
        approval_step='Human confirmation: AI review outcome',
        defaults={
            'organization': organization,
            'assigned_to': contract.owner,
            'comments': 'Confirm that the completed AI review outcome has been assessed. This is a specific human confirmation, not an automatic contract approval.',
        },
    )
    _apply_document_review_contract_state(
        contract,
        status=Contract.Status.IN_PROGRESS,
        lifecycle_stage='APPROVAL',
        actor=request.user,
        request=request,
        reason='ai_review_human_confirmation_requested',
    )
    log_action(
        request.user,
        AuditLog.Action.CREATE if created else AuditLog.Action.UPDATE,
        'ApprovalRequest',
        approval.pk,
        str(approval),
        organization=organization,
        request=request,
        event_type='ai.review_human_confirmation_requested',
        changes={
            'event': 'ai.review_human_confirmation_requested',
            'contract_id': contract.pk,
            'approval_id': approval.pk,
            'created': created,
        },
    )
    return JsonResponse({'ok': True, 'approval_id': approval.pk, 'created': created})


@login_required
@require_http_methods(['POST'])
def ai_suggest_clauses_api(request, contract_id):
    org, contract, error = _resolve_ai_contract(request, contract_id, require_provider=True)
    if error:
        return error
    svc = get_ai_drafting_service()
    try:
        recs = svc.suggest_clauses(contract_id, org)
    except Contract.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    return JsonResponse({'created': len(recs), 'recommendations': [_rec_to_dict(r) for r in recs]}, status=201)


@login_required
@require_http_methods(['GET'])
def ai_clause_recommendations_api(request, contract_id):
    org, contract, error = _resolve_ai_contract(request, contract_id, action=ContractAction.VIEW)
    if error:
        return error
    svc = get_ai_drafting_service()
    accepted_only = request.GET.get('accepted') == 'true'
    recs = svc.list_recommendations(contract_id, org, accepted_only=accepted_only)
    return JsonResponse({'recommendations': [_rec_to_dict(r) for r in recs]})


@login_required
@require_http_methods(['POST'])
def ai_accept_clause_api(request, contract_id, recommendation_id):
    org, contract, error = _resolve_ai_contract(request, contract_id, action=ContractAction.EDIT)
    if error:
        return error
    svc = get_ai_drafting_service()
    try:
        rec = svc.accept_clause(contract_id, recommendation_id, request.user, org)
    except ClauseRecommendation.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    return JsonResponse({'ok': True, 'recommendation': _rec_to_dict(rec)})


@login_required
@require_http_methods(['POST'])
def ai_draft_section_api(request, contract_id):
    org, contract, error = _resolve_ai_contract(request, contract_id, require_provider=True)
    if error:
        return error
    svc = get_ai_drafting_service()
    try:
        data = json.loads(request.body or '{}')
    except (TypeError, ValueError):
        return _error_response(request, 'Request body must be valid JSON.', 400)
    section = str(data.get('section', 'recitals')).strip()[:100]
    if not section:
        return _error_response(request, 'Section is required.', 400)
    try:
        result = svc.generate_draft_section(contract_id, section, org)
    except Contract.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    return JsonResponse(result)


def _rec_to_dict(rec: ClauseRecommendation) -> dict:
    return {
        'id': rec.pk,
        'clause_type': rec.clause_type,
        'recommendation_text': rec.recommendation_text,
        'confidence': rec.confidence,
        'rationale': rec.rationale,
        'accepted': rec.accepted,
        'accepted_by': rec.accepted_by.username if rec.accepted_by else None,
        'accepted_at': rec.accepted_at.isoformat() if rec.accepted_at else None,
        'created_at': rec.created_at.isoformat() if rec.created_at else None,
    }
