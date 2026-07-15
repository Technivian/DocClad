
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


def _obligation_to_dict(obl) -> dict:
    return {
        'id': obl.id,
        'title': obl.title,
        'description': obl.description,
        'due_date': obl.due_date,
        'contract_id': obl.contract_id,
        'assigned_to': obl.assigned_to,
        'priority': obl.priority,
        'status': obl.status,
        'reminder_days': obl.reminder_days,
        'created_at': obl.created_at,
        'deadline_type': obl.deadline_type,
        'auto_generated': obl.auto_generated,
        'days_remaining': obl.days_remaining,
    }


@login_required
@require_http_methods(['GET', 'POST'])
def contract_obligations_api(request, contract_id):
    """List or create obligations for a contract.

    GET  — returns all deadlines attached to the contract.
    POST — creates a new obligation. Body (JSON):
        title, description, due_date (YYYY-MM-DD), priority (optional),
        deadline_type (optional), reminder_days (optional), assigned_to (optional).
    """

    organization = get_user_organization(request.user)
    contract = Contract.objects.filter(id=contract_id, organization=organization).first()
    if contract is None:
        return _error_response(request, 'Contract not found or access denied.', 404)

    svc = get_obligation_service(organization)

    if request.method == 'GET':
        status_filter = request.GET.get('status')
        type_filter = request.GET.get('deadline_type')
        obligations = svc.list_obligations(
            contract_id=str(contract_id),
            status=status_filter,
            deadline_type=type_filter,
        )
        return JsonResponse({
            'contract_id': contract_id,
            'count': len(obligations),
            'obligations': [_obligation_to_dict(o) for o in obligations],
        })

    # POST — create
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, Exception):
        return _error_response(request, 'Invalid JSON body.', 400)

    title = (body.get('title') or '').strip()
    due_date = (body.get('due_date') or '').strip()
    if not title:
        return _error_response(request, 'title is required.', 400)
    if not due_date:
        return _error_response(request, 'due_date is required (YYYY-MM-DD).', 400)

    try:
        obligation = svc.create_obligation(
            title=title,
            description=body.get('description', ''),
            due_date=due_date,
            contract_id=str(contract_id),
            assigned_to=body.get('assigned_to', ''),
            priority=body.get('priority', 'medium'),
            deadline_type=body.get('deadline_type', 'CONTRACT'),
            reminder_days=int(body.get('reminder_days', 7)),
        )
    except Exception as exc:
        return _error_response(request, str(exc), 400)

    return JsonResponse({'ok': True, 'obligation': _obligation_to_dict(obligation)}, status=201)


@login_required
@require_http_methods(['GET', 'PATCH', 'DELETE'])
def obligation_detail_api(request, obligation_id):
    """Retrieve, update, or delete a single obligation.

    PATCH body (JSON, all fields optional):
        title, description, due_date, priority, status, reminder_days, assigned_to.
    """

    organization = get_user_organization(request.user)
    svc = get_obligation_service(organization)

    if request.method == 'GET':
        obligations = svc.list_obligations()
        match = next((o for o in obligations if o.id == str(obligation_id)), None)
        if match is None:
            return _error_response(request, 'Obligation not found.', 404)
        return JsonResponse({'obligation': _obligation_to_dict(match)})

    if request.method == 'PATCH':
        try:
            body = json.loads(request.body)
        except Exception:
            return _error_response(request, 'Invalid JSON body.', 400)
        updated = svc.update_obligation(str(obligation_id), **body)
        if updated is None:
            return _error_response(request, 'Obligation not found.', 404)
        return JsonResponse({'ok': True, 'obligation': _obligation_to_dict(updated)})

    # DELETE
    deleted = svc.delete_obligation(str(obligation_id))
    if not deleted:
        return _error_response(request, 'Obligation not found.', 404)
    return JsonResponse({'ok': True, 'deleted_id': obligation_id})


@login_required
@require_http_methods(['GET'])
def obligation_reminders_api(request):
    """Return all obligations currently within their reminder window."""

    organization = get_user_organization(request.user)
    svc = get_obligation_service(organization)
    reminders = svc.get_reminders_due()
    return JsonResponse({
        'count': len(reminders),
        'reminders': [_obligation_to_dict(o) for o in reminders],
    })


def _dsar_dto_to_dict(dto) -> dict:
    return {
        'id': dto.id,
        'reference_number': dto.reference_number,
        'request_type': dto.request_type,
        'status': dto.status,
        'sla_label': dto.sla_label,
        'days_remaining': dto.days_remaining,
        'is_overdue': dto.is_overdue,
        'is_extended': dto.is_extended,
        'received_date': dto.received_date,
        'due_date': dto.due_date,
        'completed_date': dto.completed_date,
        'requester_name': dto.requester_name,
        'requester_email': dto.requester_email,
        'assigned_to': dto.assigned_to,
    }


@login_required
@require_http_methods(['GET', 'POST'])
def dsar_list_api(request):
    """GET /api/dsar/ — list | POST — create."""
    organization = get_user_organization(request.user)
    svc = get_dsar_service()

    if request.method == 'GET':
        status_filter = request.GET.get('status')
        overdue_only = request.GET.get('overdue_only') in ('1', 'true', 'True')
        result = svc.list_requests(organization, status_filter=status_filter, overdue_only=overdue_only)
        return JsonResponse({
            'total': result.total,
            'overdue_count': result.overdue_count,
            'at_risk_count': result.at_risk_count,
            'requests': [_dsar_dto_to_dict(r) for r in result.requests],
        })

    # POST — create
    import json as _json
    try:
        body = _json.loads(request.body or '{}')
    except ValueError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    required = ('request_type', 'requester_name', 'requester_email', 'description')
    missing = [f for f in required if not body.get(f)]
    if missing:
        return JsonResponse({'error': f'Missing fields: {missing}'}, status=400)

    dto = svc.create_request(
        organization=organization,
        request_type=body['request_type'],
        requester_name=body['requester_name'],
        requester_email=body['requester_email'],
        description=body['description'],
        created_by=request.user,
    )
    return JsonResponse({'ok': True, 'dsar': _dsar_dto_to_dict(dto)}, status=201)


@login_required
@require_http_methods(['GET', 'PATCH'])
def dsar_detail_api(request, dsar_id: int):
    """GET /api/dsar/<id>/ | PATCH — update."""
    organization = get_user_organization(request.user)
    svc = get_dsar_service()

    if request.method == 'GET':
        dto = svc.get_request(dsar_id, organization)
        if dto is None:
            return JsonResponse({'error': 'Not found'}, status=404)
        return JsonResponse({'dsar': _dsar_dto_to_dict(dto)})

    # PATCH
    import json as _json
    try:
        body = _json.loads(request.body or '{}')
    except ValueError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    dto = svc.update_request(dsar_id, organization, **body)
    if dto is None:
        return JsonResponse({'error': 'Not found'}, status=404)
    return JsonResponse({'ok': True, 'dsar': _dsar_dto_to_dict(dto)})


@login_required
@require_http_methods(['GET'])
def dsar_evidence_api(request, dsar_id: int):
    """GET /api/dsar/<id>/evidence/ — export evidence bundle as JSON."""
    organization = get_user_organization(request.user)
    svc = get_dsar_service()
    bundle = svc.generate_evidence_bundle(dsar_id, organization)
    if bundle is None:
        return JsonResponse({'error': 'Not found'}, status=404)
    return JsonResponse(bundle)


def _job_to_dict(job) -> dict:
    return {
        'id': job.id,
        'job_type': job.job_type,
        'status': job.status,
        'attempt_count': job.attempt_count,
        'max_attempts': job.max_attempts,
        'error_message': job.error_message or '',
        'result': job.result or {},
        'payload': job.payload or {},
        'scheduled_at': job.scheduled_at.isoformat() if job.scheduled_at else None,
        'started_at': job.started_at.isoformat() if job.started_at else None,
        'completed_at': job.completed_at.isoformat() if job.completed_at else None,
        'dead_lettered_at': job.dead_lettered_at.isoformat() if job.dead_lettered_at else None,
        'created_at': job.created_at.isoformat() if job.created_at else None,
        'organization_id': job.organization_id,
    }


@login_required
@require_http_methods(['GET'])
def job_list_api(request):
    """GET /api/jobs/ — list recent background jobs for the user's org."""
    organization = get_user_organization(request.user)
    status_filter = request.GET.get('status')
    job_type_filter = request.GET.get('job_type')
    limit = min(int(request.GET.get('limit', 50)), 200)

    qs = BackgroundJob.objects.filter(organization=organization).order_by('-created_at')
    if status_filter:
        qs = qs.filter(status=status_filter)
    if job_type_filter:
        qs = qs.filter(job_type=job_type_filter)

    jobs = list(qs[:limit])
    counts = {s: 0 for s in ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')}
    for j in jobs:
        if j.status in counts:
            counts[j.status] += 1

    return JsonResponse({
        'total': len(jobs),
        'status_counts': counts,
        'jobs': [_job_to_dict(j) for j in jobs],
    })


@login_required
@require_http_methods(['GET'])
def job_detail_api(request, job_id: int):
    """GET /api/jobs/<id>/ — single job detail."""
    organization = get_user_organization(request.user)
    try:
        job = BackgroundJob.objects.get(id=job_id, organization=organization)
    except BackgroundJob.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    return JsonResponse({'job': _job_to_dict(job)})


@login_required
@require_http_methods(['POST'])
def job_retry_api(request, job_id: int):
    """POST /api/jobs/<id>/retry/ — re-queue a failed job."""
    from django.utils import timezone as _tz
    organization = get_user_organization(request.user)
    try:
        job = BackgroundJob.objects.get(id=job_id, organization=organization)
    except BackgroundJob.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)

    if job.status != BackgroundJob.Status.FAILED:
        return JsonResponse({'error': f'Job is {job.status}, not FAILED'}, status=400)

    job.status = BackgroundJob.Status.PENDING
    job.attempt_count = 0
    job.error_message = ''
    job.dead_lettered_at = None
    job.scheduled_at = _tz.now()
    job.save(update_fields=[
        'status', 'attempt_count', 'error_message', 'dead_lettered_at', 'scheduled_at',
    ])
    return JsonResponse({'ok': True, 'job': _job_to_dict(job)})


@login_required
@require_http_methods(['GET'])
def api_subprocessor_alerts(request):
    org = get_user_organization(request.user)
    svc = get_subprocessor_alert_service()
    alerts = svc.get_alerts(org)
    return JsonResponse({'alerts': [
        {
            'subprocessor_id': a.subprocessor_id,
            'subprocessor_name': a.subprocessor_name,
            'country': a.country,
            'alert_type': a.alert_type,
            'severity': a.severity,
            'description': a.description,
        }
        for a in alerts
    ]})


@login_required
@require_http_methods(['GET'])
def api_transfer_risk_flags(request):
    org = get_user_organization(request.user)
    svc = get_subprocessor_alert_service()
    flags = svc.get_transfer_risk_flags(org)
    return JsonResponse({'flags': [
        {
            'transfer_id': f.transfer_id,
            'title': f.title,
            'flag_type': f.flag_type,
            'description': f.description,
        }
        for f in flags
    ]})


@login_required
@require_http_methods(['GET'])
def api_retention_overdue(request):
    org = get_user_organization(request.user)
    svc = get_retention_service()
    items = svc.get_overdue_contracts(org)
    return JsonResponse({'items': [
        {
            'contract_id': item.contract_id,
            'contract_title': item.contract_title,
            'created_at': item.created_at.isoformat(),
            'days_overdue': item.days_overdue,
            'policy_id': item.policy_id,
            'policy_title': item.policy_title,
            'auto_delete': item.auto_delete,
        }
        for item in items
    ]})


@login_required
@require_http_methods(['POST'])
def api_retention_log_action(request):
    org = get_user_organization(request.user)
    svc = get_retention_service()
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, Exception):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    contract_id = data.get('contract_id')
    action = data.get('action', '')
    notes = data.get('notes', '')
    if not contract_id or not action:
        return JsonResponse({'error': 'contract_id and action required'}, status=400)
    log = svc.log_retention_action(org, contract_id, action, request.user, notes=notes)
    return JsonResponse({'id': log.id, 'action': log.action, 'created_at': log.created_at.isoformat()})


@login_required
@require_http_methods(['GET'])
def api_retention_log(request):
    org = get_user_organization(request.user)
    svc = get_retention_service()
    logs = svc.get_retention_log(org)
    return JsonResponse({'logs': logs})


