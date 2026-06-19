
"""
API views for CMS Aegis repository functionality.
"""
import hashlib
import json
import logging
import secrets

from django.contrib.auth import get_user_model
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.utils import timezone
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
from contracts.permissions import can_manage_organization
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

    doc_type = request.POST.get('document_type', Document.DocType.OTHER)
    if doc_type not in {c[0] for c in Document.DocType.choices}:
        doc_type = Document.DocType.OTHER

    title = (request.POST.get('title') or '').strip() or uploaded_file.name

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
            'ocr': {
                'status': ocr_status,
                'confidence': confidence,
                'source': ocr_source,
            },
        },
        status=201,
    )


@login_required
@require_http_methods(['GET'])
def contract_ai_extract_api(request, contract_id):
    """Return AI text-span citations for all documents attached to a contract.

    For each document that has an OCR review with extracted text the rules
    engine is run (or cached results are returned). The response includes
    labelled spans with character offsets, excerpt text, and confidence score.
    """
    from contracts.services.ai_extraction import extract_clause_spans, get_spans_summary
    from contracts.models import DocumentOCRReview

    organization = get_user_organization(request.user)
    contract = Contract.objects.filter(
        id=contract_id,
        organization=organization,
    ).first()
    if contract is None:
        return _error_response(request, 'Contract not found or access denied.', 404)

    force_reextract = request.GET.get('reextract') == '1'

    results = []
    for document in contract.documents.select_related('organization').order_by('created_at'):
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

        if force_reextract and extracted_text:
            extract_clause_spans(extracted_text, organization, document, replace_existing=True)
        elif extracted_text and not document.ai_extraction_spans.exists():
            extract_clause_spans(extracted_text, organization, document, replace_existing=False)

        results.append({
            'document_id': document.id,
            'title': document.title,
            'ocr_status': ocr_review.status,
            'ocr_confidence': float(ocr_review.confidence_score) if ocr_review.confidence_score else None,
            'status': 'ok',
            'spans': get_spans_summary(document),
        })

    return JsonResponse({
        'contract_id': contract_id,
        'document_count': len(results),
        'results': results,
    })


@login_required
@require_http_methods(['POST'])
def ai_suggest_clauses_api(request, contract_id):
    org = get_user_organization(request.user)
    svc = get_ai_drafting_service()
    try:
        recs = svc.suggest_clauses(contract_id, org)
    except Contract.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    return JsonResponse({'created': len(recs), 'recommendations': [_rec_to_dict(r) for r in recs]}, status=201)


@login_required
@require_http_methods(['GET'])
def ai_clause_recommendations_api(request, contract_id):
    org = get_user_organization(request.user)
    svc = get_ai_drafting_service()
    accepted_only = request.GET.get('accepted') == 'true'
    recs = svc.list_recommendations(contract_id, org, accepted_only=accepted_only)
    return JsonResponse({'recommendations': [_rec_to_dict(r) for r in recs]})


@login_required
@require_http_methods(['POST'])
def ai_accept_clause_api(request, contract_id, recommendation_id):
    org = get_user_organization(request.user)
    svc = get_ai_drafting_service()
    try:
        rec = svc.accept_clause(contract_id, recommendation_id, request.user, org)
    except ClauseRecommendation.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    return JsonResponse({'ok': True, 'recommendation': _rec_to_dict(rec)})


@login_required
@require_http_methods(['POST'])
def ai_draft_section_api(request, contract_id):
    org = get_user_organization(request.user)
    svc = get_ai_drafting_service()
    data = json.loads(request.body or '{}')
    section = data.get('section', 'recitals')
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


