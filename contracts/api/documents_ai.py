
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
        required = {
            'title': 'Title',
            'contract_type': 'Contract type',
            'counterparty': 'Counterparty',
            'start_date': 'Effective date',
            'end_date': 'Expiry date',
            'governing_law': 'Governing law',
        }
        missing = [label for key, label in required.items() if not (request.POST.get(key) or '').strip()]
        if missing:
            return _error_response(request, f'Missing required metadata: {", ".join(missing)}.', 400)
        contract_type = request.POST.get('contract_type')
        if contract_type not in {value for value, _ in Contract.ContractType.choices}:
            return _error_response(request, 'Invalid contract type.', 400)
        start_date = parse_date(request.POST.get('start_date', ''))
        end_date = parse_date(request.POST.get('end_date', ''))
        if not start_date or not end_date:
            return _error_response(request, 'Effective and expiry dates must be valid dates.', 400)
        if end_date < start_date:
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
        contract_payload = {
            'organization': organization,
            'title': request.POST['title'].strip(),
            'contract_type': contract_type,
            'counterparty': request.POST['counterparty'].strip(),
            'owner': owner,
            'created_by': request.user,
            'value': value,
            'currency': request.POST.get('currency') or Contract.Currency.USD,
            'start_date': start_date,
            'end_date': end_date,
            'governing_law': request.POST['governing_law'].strip(),
            'dpa_attached': request.POST.get('dpa_attached') in {'1', 'true', 'True', 'on'},
            'status': Contract.Status.DRAFT,
        }

    doc_type = request.POST.get('document_type', Document.DocType.OTHER)
    if doc_type not in {c[0] for c in Document.DocType.choices}:
        doc_type = Document.DocType.OTHER

    title = (request.POST.get('title') or '').strip() or uploaded_file.name

    document = None
    try:
        with transaction.atomic():
            if contract_payload is not None:
                contract = Contract.objects.create(**contract_payload)
                log_action(
                    request.user, AuditLog.Action.CREATE, 'Contract', contract.pk, str(contract),
                    organization=organization, request=request,
                    event_type='contract.uploaded',
                    changes={
                        'event': 'contract.uploaded',
                        'status': contract.status,
                        'contract_type': contract.contract_type,
                    },
                )
            document = Document(
                organization=organization,
                title=title,
                document_type=doc_type,
                status=Document.Status.DRAFT,
                contract=contract,
                uploaded_by=request.user,
            )
            document.file = uploaded_file
            document.save()  # triggers SHA256 hash + OCR queue in Document.save()
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
            'ocr': {
                'status': ocr_status,
                'confidence': confidence,
                'source': ocr_source,
            },
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
