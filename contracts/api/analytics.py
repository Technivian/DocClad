
"""
API views for CLM One repository functionality.
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


@login_required
@require_http_methods(["GET"])
def executive_analytics_api(request):
    organization, error = _require_org_member_context(request)
    if error:
        return error
    return JsonResponse(build_executive_analytics_snapshot(organization))


@login_required
@require_http_methods(["GET", "POST"])
def executive_dashboard_presets_api(request):
    organization, error = _require_org_member_context(request)
    if error:
        return error

    if request.method == 'GET':
        presets = (
            ExecutiveDashboardPreset.objects.filter(organization=organization, is_shared=True)
            .select_related('created_by')
            .order_by('name')
        )
        payload = [
            {
                'id': preset.id,
                'name': preset.name,
                'filters': preset.filters,
                'layout': preset.layout,
                'created_by': preset.created_by.username if preset.created_by else None,
                'created_at': preset.created_at.isoformat() if preset.created_at else None,
                'updated_at': preset.updated_at.isoformat() if preset.updated_at else None,
            }
            for preset in presets
        ]
        return JsonResponse({'presets': payload})

    if not can_manage_organization(request.user, organization):
        return _error_response(request, 'Only organization admins/owners can manage shared dashboards.', 403)

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return _error_response(request, 'Invalid JSON body.', 400)
    name = str(payload.get('name') or '').strip()
    if not name:
        return _error_response(request, 'name is required.', 400)
    filters = payload.get('filters') if isinstance(payload.get('filters'), dict) else {}
    layout = payload.get('layout') if isinstance(payload.get('layout'), dict) else {}

    preset, _ = ExecutiveDashboardPreset.objects.update_or_create(
        organization=organization,
        name=name,
        defaults={
            'filters': filters,
            'layout': layout,
            'is_shared': True,
            'created_by': request.user,
        },
    )
    return JsonResponse(
        {
            'preset': {
                'id': preset.id,
                'name': preset.name,
                'filters': preset.filters,
                'layout': preset.layout,
            }
        }
    )


@login_required
@require_http_methods(["DELETE"])
def executive_dashboard_preset_delete_api(request, preset_id):
    organization, error = _require_org_member_context(request)
    if error:
        return error
    if not can_manage_organization(request.user, organization):
        return _error_response(request, 'Only organization admins/owners can manage shared dashboards.', 403)

    preset = ExecutiveDashboardPreset.objects.filter(organization=organization, id=preset_id).first()
    if preset is None:
        return _error_response(request, 'Preset not found.', 404)
    preset.delete()
    return JsonResponse({'deleted': True, 'preset_id': preset_id})


@login_required
@require_http_methods(['GET'])
def clause_analytics_stats(request):
    org = get_user_organization(request.user)
    svc = get_clause_analytics_service()
    stats = svc.get_clause_usage_stats(org)
    return JsonResponse({'stats': stats})


@login_required
@require_http_methods(['GET'])
def clause_analytics_top_clauses(request):
    org = get_user_organization(request.user)
    limit = int(request.GET.get('limit', 20))
    svc = get_clause_analytics_service()
    results = svc.get_most_used_clauses(org, limit=limit)
    return JsonResponse({'clauses': [
        {
            'clause_id': r.clause_id,
            'clause_title': r.clause_title,
            'category': r.category,
            'jurisdiction_scope': r.jurisdiction_scope,
            'total_uses': r.total_uses,
            'accepted_count': r.accepted_count,
            'rejected_count': r.rejected_count,
            'modified_count': r.modified_count,
            'acceptance_rate_pct': r.acceptance_rate_pct,
        }
        for r in results
    ]})


@login_required
@require_http_methods(['GET'])
def clause_dependency_graph(request):
    org = get_user_organization(request.user)
    svc = get_clause_analytics_service()
    nodes = svc.get_dependency_graph(org)
    return JsonResponse({'nodes': [
        {
            'clause_id': n.clause_id,
            'clause_title': n.clause_title,
            'co_occurring_clauses': n.co_occurring_clauses,
        }
        for n in nodes
    ]})


@csrf_exempt
@login_required
@require_http_methods(['POST'])
def clause_record_usage(request):
    org = get_user_organization(request.user)
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    clause_id = body.get('clause_id')
    action = body.get('action', ClauseUsageEvent.Action.ADDED)
    contract_id = body.get('contract_id')
    note = body.get('note', '')
    if not clause_id:
        return JsonResponse({'error': 'clause_id required'}, status=400)
    clause = get_object_or_404(ClauseTemplate, pk=clause_id, organization=org)
    contract = None
    if contract_id:
        contract = get_object_or_404(Contract, pk=contract_id, organization=org)
    svc = get_clause_analytics_service()
    ev = svc.record_usage(org, clause, contract, action, performed_by=request.user, note=note)
    return JsonResponse({'event_id': ev.pk, 'action': ev.action}, status=201)


@login_required
@require_http_methods(['GET'])
def mandatory_clause_compliance_contract(request, contract_id):
    org = get_user_organization(request.user)
    contract = get_object_or_404(Contract, pk=contract_id, organization=org)
    svc = get_mandatory_enforcement_service()
    report = svc.check_contract_compliance(contract)
    return JsonResponse({
        'contract_id': report.contract_id,
        'contract_title': report.contract_title,
        'contract_type': report.contract_type,
        'is_compliant': report.is_compliant,
        'missing_mandatory_clauses': [
            {
                'clause_id': m.clause_id,
                'clause_title': m.clause_title,
                'jurisdiction_scope': m.jurisdiction_scope,
                'applicable_contract_types': m.applicable_contract_types,
                'fallback_available': m.fallback_available,
            }
            for m in report.missing_mandatory_clauses
        ],
        'present_mandatory_clauses': report.present_mandatory_clauses,
    })


@login_required
@require_http_methods(['GET'])
def mandatory_clause_org_summary(request):
    org = get_user_organization(request.user)
    svc = get_mandatory_enforcement_service()
    summary = svc.get_org_compliance_summary(org)
    return JsonResponse({
        'org_id': summary.org_id,
        'total_contracts_checked': summary.total_contracts_checked,
        'compliant_contracts': summary.compliant_contracts,
        'non_compliant_contracts': summary.non_compliant_contracts,
        'compliance_rate_pct': summary.compliance_rate_pct,
        'most_missing_clauses': summary.most_missing_clauses,
    })


@login_required
@require_http_methods(['GET'])
def playbook_list(request):
    org = get_user_organization(request.user)
    jurisdiction = request.GET.get('jurisdiction')
    risk_level = request.GET.get('risk_level')
    svc = get_playbook_service()
    playbooks = svc.list_playbooks(org, jurisdiction=jurisdiction, risk_level=risk_level)
    return JsonResponse({'playbooks': [
        {
            'playbook_id': p.playbook_id,
            'name': p.name,
            'description': p.description,
            'jurisdiction_scope': p.jurisdiction_scope,
            'risk_level': p.risk_level,
            'fallback_position': p.fallback_position,
        }
        for p in playbooks
    ]})


@login_required
@require_http_methods(['GET'])
def playbook_detail(request, playbook_id):
    org = get_user_organization(request.user)
    svc = get_playbook_service()
    try:
        pb = svc.get_playbook(playbook_id, org)
    except ClausePlaybook.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    return JsonResponse({
        'playbook_id': pb.playbook_id,
        'name': pb.name,
        'description': pb.description,
        'jurisdiction_scope': pb.jurisdiction_scope,
        'risk_level': pb.risk_level,
        'fallback_position': pb.fallback_position,
        'clauses': [
            {
                'clause_id': c.clause_id,
                'clause_title': c.clause_title,
                'standard_text': c.standard_text,
                'variant_content': c.variant_content,
                'fallback_content': c.fallback_content,
                'playbook_notes': c.playbook_notes,
                'jurisdiction_scope': c.jurisdiction_scope,
            }
            for c in pb.clauses
        ],
    })


@login_required
@require_http_methods(['GET'])
def playbook_for_contract(request, contract_id):
    org = get_user_organization(request.user)
    contract = get_object_or_404(Contract, pk=contract_id, organization=org)
    svc = get_playbook_service()
    playbooks = svc.get_playbooks_for_contract(contract)
    return JsonResponse({'playbooks': [
        {
            'playbook_id': p.playbook_id,
            'name': p.name,
            'jurisdiction_scope': p.jurisdiction_scope,
            'risk_level': p.risk_level,
            'fallback_position': p.fallback_position,
        }
        for p in playbooks
    ]})


@login_required
@require_http_methods(['GET'])
def api_contract_search(request):
    org = get_user_organization(request.user)
    svc = get_contract_search_service()
    q = request.GET.get('q', '')
    filters = {
        'status': request.GET.get('status', ''),
        'contract_type': request.GET.get('contract_type', ''),
        'jurisdiction': request.GET.get('jurisdiction', ''),
        'date_from': request.GET.get('date_from', ''),
        'date_to': request.GET.get('date_to', ''),
    }
    filters = {k: v for k, v in filters.items() if v}
    try:
        page = max(1, int(request.GET.get('page', 1)))
    except (ValueError, TypeError):
        page = 1
    result = svc.search_contracts(org, q=q, filters=filters, page=page)
    svc.record_search_event(org, q, result.total, request.user)
    return JsonResponse({
        'results': result.results,
        'total': result.total,
        'page': result.page,
        'page_size': result.page_size,
        'total_pages': result.total_pages,
    })


@login_required
@require_http_methods(['GET'])
def api_clause_search(request):
    org = get_user_organization(request.user)
    svc = get_clause_search_service()
    q = request.GET.get('q', '')
    filters = {
        'category_id': request.GET.get('category_id'),
        'jurisdiction': request.GET.get('jurisdiction', ''),
        'is_mandatory': request.GET.get('is_mandatory'),
    }
    filters = {k: v for k, v in filters.items() if v is not None and v != ''}
    if 'is_mandatory' in filters:
        filters['is_mandatory'] = filters['is_mandatory'].lower() in ('true', '1', 'yes')
    try:
        page = max(1, int(request.GET.get('page', 1)))
    except (ValueError, TypeError):
        page = 1
    result = svc.search_clauses(org, q=q, filters=filters, page=page)
    svc.record_search_event(org, q, result.total, request.user)
    return JsonResponse({
        'results': result.results,
        'total': result.total,
        'page': result.page,
        'page_size': result.page_size,
        'total_pages': result.total_pages,
    })


@login_required
@require_http_methods(['GET'])
def api_search_facets(request):
    org = get_user_organization(request.user)
    svc = get_contract_search_service()
    facets = svc.get_contract_facets(org)
    return JsonResponse(facets)


@login_required
@require_http_methods(['GET'])
def api_search_telemetry(request):
    org = get_user_organization(request.user)
    events = SearchTelemetryEvent.objects.filter(organization=org)[:50]
    return JsonResponse({'events': [
        {
            'id': e.id,
            'query': e.query,
            'result_count': e.result_count,
            'search_type': e.search_type,
            'created_at': e.created_at.isoformat(),
        }
        for e in events
    ]})


@login_required
@require_http_methods(['POST'])
def work_interaction_api(request):
    """Beacon for My Work open / primary-action discovery events."""
    from contracts.services.work_instrumentation import VALID_SURFACES, record_work_event, resolve_surface

    org = get_user_organization(request.user)
    if org is None:
        return JsonResponse({'error': 'No organization'}, status=400)
    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    event = (data.get('event') or '').strip()
    work_item_id = (data.get('work_item_id') or '').strip()
    evidence_key = (data.get('evidence') or data.get('evidence_key') or '').strip()
    if evidence_key:
        from contracts.services.work_instrumentation import record_adoption_event
        record_adoption_event(
            organization=org,
            user=request.user,
            evidence_key=evidence_key,
            surface=resolve_surface(request, explicit=data.get('surface') or ''),
            metadata=data.get('metadata') if isinstance(data.get('metadata'), dict) else {'via': 'beacon'},
        )
        return JsonResponse({'ok': True})
    if event not in {'opened', 'primary_action', 'surfaced'}:
        return JsonResponse({'error': 'Unsupported event'}, status=400)
    if not work_item_id:
        return JsonResponse({'error': 'work_item_id is required'}, status=400)

    surface = resolve_surface(request, explicit=data.get('surface') or '')
    if surface not in VALID_SURFACES:
        surface = 'my_work'

    record_work_event(
        organization=org,
        user=request.user,
        event=event,
        work_item_id=work_item_id,
        work_kind=data.get('work_kind') or '',
        surface=surface,
        contract_id=data.get('contract_id'),
        contract_type=data.get('contract_type') or '',
        is_restricted=bool(data.get('is_restricted')),
        is_blocked=bool(data.get('is_blocked')),
        is_overdue=bool(data.get('is_overdue')),
        metadata={'via': 'beacon'},
        dedupe_days=1 if event == 'opened' else None,
    )
    return JsonResponse({'ok': True})


@login_required
@require_http_methods(['GET'])
def work_operating_metrics_api(request):
    """Phase 5 operating metrics — hub proof, not a decorative dashboard."""
    from contracts.permissions import can_manage_organization
    from contracts.services.work_instrumentation import build_operating_metrics, build_operating_trends

    org = get_user_organization(request.user)
    if org is None:
        return JsonResponse({'error': 'No organization'}, status=400)
    if not can_manage_organization(request.user, org):
        return JsonResponse({'error': 'Forbidden'}, status=403)
    try:
        days = int(request.GET.get('days') or 30)
    except (TypeError, ValueError):
        days = 30
    days = max(1, min(days, 180))
    payload = build_operating_metrics(org, days=days)
    if request.GET.get('trends') in ('1', 'true', 'yes'):
        payload['trends'] = build_operating_trends(org, days=days).get('trends') or {}
    if request.GET.get('adoption') in ('1', 'true', 'yes'):
        from contracts.services.work_instrumentation import build_adoption_evidence
        payload['adoption'] = build_adoption_evidence(org, days=days)
    return JsonResponse(payload)


