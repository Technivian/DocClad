
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
from contracts.services.approval_workflow import (
    ApprovalAccessDenied,
    get_approval_workflow_service,
)
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
@require_http_methods(['GET'])
def admin_settings_api(request):
    org = get_user_organization(request.user)
    svc = get_admin_console_service()
    settings = svc.get_settings(org)
    return JsonResponse({
        'org_id': settings.org_id,
        'name': settings.name,
        'slug': settings.slug,
        'member_count': settings.member_count,
        'token_count': settings.token_count,
        'policy': settings.policy,
    })


@login_required
@require_http_methods(['GET', 'PATCH'])
def admin_policy_api(request):
    org = get_user_organization(request.user)
    svc = get_admin_console_service()
    if request.method == 'PATCH':
        data = json.loads(request.body or '{}')
        policy = svc.update_policy(org, request.user, **data)
        from contracts.services.admin_console import _policy_to_dict
        return JsonResponse({'ok': True, 'policy': _policy_to_dict(policy)})
    settings = svc.get_settings(org)
    return JsonResponse({'policy': settings.policy})


@login_required
@require_http_methods(['GET'])
def admin_integrations_api(request):
    org = get_user_organization(request.user)
    svc = get_admin_console_service()
    integrations = svc.list_integrations(org)
    return JsonResponse({
        'integrations': [
            {'name': i.name, 'enabled': i.enabled, 'details': i.details}
            for i in integrations
        ]
    })


@login_required
@require_http_methods(['GET'])
def admin_audit_api(request):
    org = get_user_organization(request.user)
    svc = get_admin_console_service()
    limit = min(int(request.GET.get('limit', 50)), 200)
    logs = svc.get_audit_summary(org, limit=limit)
    return JsonResponse({'logs': logs})


@login_required
@require_http_methods(['GET'])
def permissions_matrix_api(request):
    org = get_user_organization(request.user)
    svc = get_permission_service()
    matrix = svc.get_org_permission_matrix(org)
    return JsonResponse({
        'org_id': matrix.org_id,
        'org_name': matrix.org_name,
        'users': [
            {
                'user_id': u.user_id,
                'username': u.username,
                'role': u.role,
                'capabilities': u.capabilities,
                'is_active': u.is_active,
            }
            for u in matrix.users
        ],
    })


@login_required
@require_http_methods(['GET'])
def contract_access_api(request, contract_id):
    org = get_user_organization(request.user)
    svc = get_permission_service()
    entry = svc.get_record_access(contract_id, org)
    return JsonResponse({
        'contract_id': entry.contract_id,
        'contract_title': entry.contract_title,
        'users_with_access': [
            {
                'user_id': u.user_id,
                'username': u.username,
                'role': u.role,
                'capabilities': u.capabilities,
                'is_active': u.is_active,
            }
            for u in entry.users_with_access
        ],
    })


@login_required
@require_http_methods(['GET'])
def user_permissions_api(request, user_id):
    org = get_user_organization(request.user)
    svc = get_permission_service()
    access = svc.get_user_permissions(user_id, org)
    if access is None:
        return JsonResponse({'error': 'User not found in organisation'}, status=404)
    return JsonResponse({
        'user_id': access.user_id,
        'username': access.username,
        'role': access.role,
        'capabilities': access.capabilities,
        'is_active': access.is_active,
    })


@login_required
@require_http_methods(['GET'])
def onboarding_status_api(request):
    org = get_user_organization(request.user)
    svc = get_onboarding_service()
    state = svc.get_progress(org)
    return JsonResponse({
        'org_id': state.org_id,
        'current_step': state.current_step,
        'steps_completed': state.steps_completed,
        'progress_pct': state.progress_pct,
        'completed': state.completed,
        'completed_at': state.completed_at,
        'remaining_steps': state.remaining_steps,
        'next_step': state.next_step,
    })


@login_required
@require_http_methods(['POST'])
def onboarding_advance_api(request):
    org = get_user_organization(request.user)
    data = json.loads(request.body or '{}')
    step = data.get('step')
    if not step:
        return JsonResponse({'error': 'step is required'}, status=400)
    svc = get_onboarding_service()
    try:
        state = svc.advance_step(org, step)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({
        'ok': True,
        'org_id': state.org_id,
        'current_step': state.current_step,
        'steps_completed': state.steps_completed,
        'progress_pct': state.progress_pct,
        'completed': state.completed,
        'next_step': state.next_step,
    })


@login_required
@require_http_methods(['POST'])
def onboarding_complete_api(request):
    org = get_user_organization(request.user)
    svc = get_onboarding_service()
    state = svc.mark_complete(org)
    return JsonResponse({'ok': True, 'completed': state.completed, 'progress_pct': state.progress_pct})


@login_required
@require_http_methods(['GET'])
def billing_usage_api(request):
    org = get_user_organization(request.user)
    svc = get_billing_service()
    usage = svc.get_current_usage(org)
    return JsonResponse({
        'org_id': usage.org_id,
        'plan_name': usage.plan_name,
        'period_start': usage.period_start,
        'period_end': usage.period_end,
        'user_count': usage.user_count,
        'contract_count': usage.contract_count,
        'api_call_count': usage.api_call_count,
        'max_users': usage.max_users,
        'max_contracts': usage.max_contracts,
        'max_api_calls_per_month': usage.max_api_calls_per_month,
        'overage_users': usage.overage_users,
        'overage_contracts': usage.overage_contracts,
        'overage_api_calls': usage.overage_api_calls,
        'any_overage': usage.any_overage,
    })


@login_required
@require_http_methods(['GET'])
def billing_plan_api(request):
    org = get_user_organization(request.user)
    svc = get_billing_service()
    plan = svc.get_plan(org)
    return JsonResponse({
        'name': plan.name,
        'max_users': plan.max_users,
        'max_contracts': plan.max_contracts,
        'max_api_calls_per_month': plan.max_api_calls_per_month,
        'price_monthly': str(plan.price_monthly),
    })


@login_required
@require_http_methods(['GET'])
def compliance_trust_report_api(request):
    org = get_user_organization(request.user)
    svc = get_compliance_portal_service()
    report = svc.generate_trust_report(org)
    return JsonResponse({
        'org_id': report.org_id,
        'org_name': report.org_name,
        'generated_at': report.generated_at,
        'policy_summary': report.policy_summary,
        'dsar_stats': report.dsar_stats,
        'retention_config': report.retention_config,
        'ai_governance': report.ai_governance,
        'audit_counts': report.audit_counts,
        'contract_stats': report.contract_stats,
    })


@login_required
@require_http_methods(['GET'])
def compliance_export_api(request):
    org = get_user_organization(request.user)
    svc = get_compliance_portal_service()
    bundle = svc.export_compliance_bundle(org)
    return JsonResponse(bundle)


@login_required
@require_http_methods(['POST'])
def approval_initiate_api(request, contract_id):
    contract = get_object_or_404(
        scope_queryset_for_organization(Contract.objects.all(), get_user_organization(request.user)),
        pk=contract_id,
    )
    svc = get_approval_workflow_service()
    try:
        requests_created = svc.initiate_approval_workflow(contract, actor=request.user)
    except ApprovalAccessDenied as exc:
        return JsonResponse({'error': str(exc)}, status=exc.status_code)
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    return JsonResponse({
        'ok': True,
        'created': len(requests_created),
        'requests': [_approval_dto_to_dict(r) for r in requests_created],
    })


@login_required
@require_http_methods(['GET'])
def approval_contract_list_api(request, contract_id):
    contract = get_object_or_404(
        scope_queryset_for_organization(Contract.objects.all(), get_user_organization(request.user)),
        pk=contract_id,
    )
    svc = get_approval_workflow_service()
    summary = svc.get_contract_approvals(contract)
    return JsonResponse({
        'contract_id': summary.contract_id,
        'all_approved': summary.all_approved,
        'any_rejected': summary.any_rejected,
        'any_pending': summary.any_pending,
        'requests': [_approval_dto_to_dict(r) for r in summary.requests],
    })


def _stamp_work_surface(request, data=None):
    """Attach surface attribution onto the actor for downstream audit/instrumentation."""
    from contracts.services.work_instrumentation import resolve_surface
    surface = resolve_surface(request, explicit=(data or {}).get('surface') or (data or {}).get('from') or '')
    request.user._work_surface = surface
    return surface


@login_required
@require_http_methods(['POST'])
def approval_approve_api(request, approval_id):
    data = json.loads(request.body or '{}')
    _stamp_work_surface(request, data)
    svc = get_approval_workflow_service()
    try:
        dto = svc.approve(approval_id, request.user, comments=data.get('comments', ''))
    except ApprovalRequest.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    except ApprovalAccessDenied as e:
        return JsonResponse({'error': str(e)}, status=e.status_code)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'ok': True, 'request': _approval_dto_to_dict(dto)})


@login_required
@require_http_methods(['POST'])
def approval_reject_api(request, approval_id):
    data = json.loads(request.body or '{}')
    _stamp_work_surface(request, data)
    svc = get_approval_workflow_service()
    try:
        dto = svc.reject(approval_id, request.user, comments=data.get('comments', ''))
    except ApprovalRequest.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    except ApprovalAccessDenied as e:
        return JsonResponse({'error': str(e)}, status=e.status_code)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'ok': True, 'request': _approval_dto_to_dict(dto)})


@login_required
@require_http_methods(['POST'])
def approval_request_changes_api(request, approval_id):
    data = json.loads(request.body or '{}')
    _stamp_work_surface(request, data)
    svc = get_approval_workflow_service()
    try:
        dto = svc.request_changes(approval_id, request.user, comments=data.get('comments', ''))
    except ApprovalRequest.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    except ApprovalAccessDenied as e:
        return JsonResponse({'error': str(e)}, status=e.status_code)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'ok': True, 'request': _approval_dto_to_dict(dto)})


@login_required
@require_http_methods(['POST'])
def approval_delegate_api(request, approval_id):
    data = json.loads(request.body or '{}')
    to_user_id = data.get('to_user_id')
    if not to_user_id:
        return JsonResponse({'error': 'to_user_id is required'}, status=400)
    User = get_user_model()
    try:
        to_user = User.objects.get(pk=to_user_id)
    except User.DoesNotExist:
        return JsonResponse({'error': 'Delegate user not found'}, status=404)
    ends_at = None
    ends_at_raw = data.get('ends_at')
    if ends_at_raw:
        from django.utils.dateparse import parse_datetime
        ends_at = parse_datetime(str(ends_at_raw))
    svc = get_approval_workflow_service()
    try:
        dto = svc.delegate(
            approval_id,
            to_user,
            request.user,
            reason=data.get('reason') or '',
            ends_at=ends_at,
        )
    except ApprovalRequest.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    except ApprovalAccessDenied as e:
        return JsonResponse({'error': str(e)}, status=e.status_code)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'ok': True, 'request': _approval_dto_to_dict(dto)})


@login_required
@require_http_methods(['POST'])
def approval_reassign_api(request, approval_id):
    data = json.loads(request.body or '{}')
    to_user_id = data.get('to_user_id')
    reason = (data.get('reason') or '').strip()
    if not to_user_id:
        return JsonResponse({'error': 'to_user_id is required'}, status=400)
    if not reason:
        return JsonResponse({'error': 'A reassignment reason is required'}, status=400)
    User = get_user_model()
    try:
        to_user = User.objects.get(pk=to_user_id)
    except User.DoesNotExist:
        return JsonResponse({'error': 'Assignee not found'}, status=404)
    svc = get_approval_workflow_service()
    try:
        dto = svc.reassign(approval_id, to_user, request.user, reason=reason)
    except ApprovalRequest.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    except ApprovalAccessDenied as e:
        return JsonResponse({'error': str(e)}, status=e.status_code)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'ok': True, 'request': _approval_dto_to_dict(dto)})


@login_required
@require_http_methods(['POST'])
def approval_suggest_decision_api(request, approval_id):
    """Suggest a reject/return comment — never auto-submits the decision."""
    from contracts.services.ai_decision_assist import suggest_approval_decision_comment
    from contracts.services.approval_workflow import actor_can_decide
    from contracts.tenancy import scope_queryset_for_organization

    data = json.loads(request.body or '{}')
    decision = (data.get('decision') or 'return').strip().lower()
    org = get_user_organization(request.user)
    approval = scope_queryset_for_organization(
        ApprovalRequest.objects.select_related('contract', 'organization'),
        org,
    ).filter(pk=approval_id).first()
    if approval is None:
        return JsonResponse({'error': 'Not found'}, status=404)
    if not actor_can_decide(approval, request.user, 'approve'):
        return JsonResponse({'error': 'Not permitted'}, status=403)
    try:
        result = suggest_approval_decision_comment(approval, decision, allow_ai=True)
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    from contracts.services.work_instrumentation import record_adoption_event
    record_adoption_event(
        organization=org,
        user=request.user,
        evidence_key='suggest_requested',
        surface='my_work',
        metadata={'kind': result.get('decision') or decision, 'source': result.get('source')},
    )
    return JsonResponse({'ok': True, **result})


@login_required
@require_http_methods(['GET'])
def assignee_options_api(request):
    """Live searchable assignee list with open-work workload (admin/owner)."""
    from contracts.permissions import can_manage_organization
    from contracts.view_support import reassign_member_options

    org = get_user_organization(request.user)
    if org is None:
        return JsonResponse({'error': 'No organization'}, status=400)
    if not can_manage_organization(request.user, org):
        return JsonResponse({'error': 'Forbidden'}, status=403)
    q = (request.GET.get('q') or '').strip()
    try:
        limit = int(request.GET.get('limit') or 40)
    except (TypeError, ValueError):
        limit = 40
    exclude_raw = request.GET.get('exclude') or ''
    exclude_ids = []
    for part in exclude_raw.split(','):
        part = part.strip()
        if part.isdigit():
            exclude_ids.append(int(part))
    members = reassign_member_options(
        org, q=q, limit=limit, exclude_ids=exclude_ids, include_workload=True,
    )
    from contracts.services.work_instrumentation import record_adoption_event
    record_adoption_event(
        organization=org,
        user=request.user,
        evidence_key='assignee_search',
        surface='my_work',
        metadata={'q_len': len(q), 'result_count': len(members)},
    )
    return JsonResponse({'ok': True, 'members': members, 'q': q})


@login_required
@require_http_methods(['POST'])
def work_suggest_comment_api(request):
    """Suggest a decision-changing comment for reassign / conflict / escalate."""
    from contracts.models import Deadline, DPARiskItem
    from contracts.permissions import can_manage_organization
    from contracts.services.ai_decision_assist import suggest_work_action_comment
    from contracts.services.approval_workflow import actor_can_decide
    from contracts.tenancy import scope_queryset_for_organization
    from contracts.views_domains.dpa_review import _can_review_pack

    data = json.loads(request.body or '{}')
    kind = (data.get('kind') or data.get('decision') or '').strip().lower()
    org = get_user_organization(request.user)
    if org is None:
        return JsonResponse({'error': 'No organization'}, status=400)

    approval = None
    risk_item = None
    deadline = None

    if data.get('approval_id'):
        approval = scope_queryset_for_organization(
            ApprovalRequest.objects.select_related('contract', 'organization'),
            org,
        ).filter(pk=data.get('approval_id')).first()
        if approval is None:
            return JsonResponse({'error': 'Approval not found'}, status=404)
        if kind == 'reassign':
            if not can_manage_organization(request.user, org):
                return JsonResponse({'error': 'Not permitted'}, status=403)
        elif kind in ('reject', 'return'):
            if not actor_can_decide(approval, request.user, 'approve'):
                return JsonResponse({'error': 'Not permitted'}, status=403)
        else:
            return JsonResponse({'error': 'Unsupported kind for approval'}, status=400)

    if data.get('risk_item_id'):
        risk_item = (
            DPARiskItem.objects
            .filter(pk=data.get('risk_item_id'), review_pack__organization=org)
            .select_related('review_pack', 'review_pack__contract', 'review_pack__organization')
            .first()
        )
        if risk_item is None:
            return JsonResponse({'error': 'Risk item not found'}, status=404)
        if not _can_review_pack(request.user, risk_item.review_pack):
            return JsonResponse({'error': 'Not permitted'}, status=403)
        if kind not in ('conflict_resolved', 'conflict_false_positive'):
            return JsonResponse({'error': 'Unsupported kind for risk item'}, status=400)

    if data.get('deadline_id'):
        deadline = Deadline.objects.for_organization(org).select_related('contract').filter(
            pk=data.get('deadline_id'),
        ).first()
        if deadline is None:
            return JsonResponse({'error': 'Obligation not found'}, status=404)
        if kind != 'escalate':
            return JsonResponse({'error': 'Unsupported kind for obligation'}, status=400)

    if approval is None and risk_item is None and deadline is None:
        return JsonResponse({'error': 'approval_id, risk_item_id, or deadline_id is required'}, status=400)

    try:
        result = suggest_work_action_comment(
            kind,
            organization=org,
            approval=approval,
            risk_item=risk_item,
            deadline=deadline,
            allow_ai=True,
        )
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    from contracts.services.work_instrumentation import record_adoption_event
    record_adoption_event(
        organization=org,
        user=request.user,
        evidence_key='suggest_requested',
        surface='my_work',
        metadata={'kind': result.get('decision') or kind, 'source': result.get('source')},
    )
    return JsonResponse({'ok': True, **result})


@login_required
@require_http_methods(['GET'])
def approval_overdue_api(request):
    org = get_user_organization(request.user)
    svc = get_approval_workflow_service()
    overdue = svc.get_overdue_approvals(org)
    return JsonResponse({'overdue': [_approval_dto_to_dict(r) for r in overdue]})


@login_required
@require_http_methods(['POST'])
def approval_escalate_overdue_api(request):
    org = get_user_organization(request.user)
    svc = get_approval_workflow_service()
    count = svc.escalate_overdue_for_org(org)
    return JsonResponse({'ok': True, 'escalated': count})


@login_required
@require_http_methods(['GET'])
def approval_list_api(request):
    org = get_user_organization(request.user)
    status_filter = request.GET.get('status')
    svc = get_approval_workflow_service()
    requests_list = svc.list_approvals(org, status=status_filter)
    return JsonResponse({'requests': [_approval_dto_to_dict(r) for r in requests_list]})


def _approval_dto_to_dict(dto) -> dict:
    return {
        'id': dto.id,
        'contract_id': dto.contract_id,
        'contract_title': dto.contract_title,
        'approval_step': dto.approval_step,
        'status': dto.status,
        'assigned_to_id': dto.assigned_to_id,
        'assigned_to_username': dto.assigned_to_username,
        'delegated_to_id': dto.delegated_to_id,
        'due_date': dto.due_date,
        'sla_hours': dto.sla_hours,
        'is_overdue': dto.is_overdue,
        'comments': dto.comments,
        'created_at': dto.created_at,
    }


@login_required
@require_http_methods(['GET'])
def api_db_health(request):
    svc = get_postgres_health_service()
    return JsonResponse(svc.check_connection())


@login_required
@require_http_methods(['GET'])
def api_migration_status(request):
    svc = get_postgres_health_service()
    return JsonResponse(svc.get_migration_status())


@login_required
@require_http_methods(['GET'])
def api_cve_gate_status(request):
    svc = get_cve_gate_service()
    return JsonResponse(svc.get_gate_status())


@login_required
@require_http_methods(['GET'])
def api_cve_scan_requirements(request):
    svc = get_cve_gate_service()
    result = svc.scan_requirements()
    svc.record_scan_result(
        packages_checked=len(result.packages),
        issues_found=0,
        performed_by=request.user,
    )
    return JsonResponse({
        'packages': result.packages,
        'scan_timestamp': result.scan_timestamp,
        'note': result.note,
    })


@login_required
@require_http_methods(['GET'])
def api_restore_drill_list(request):
    org = get_user_organization(request.user)
    svc = get_restore_drill_service()
    return JsonResponse({'drills': svc.list_drills(org)})


@login_required
@require_http_methods(['POST'])
def api_restore_drill_schedule(request):
    org = get_user_organization(request.user)
    svc = get_restore_drill_service()
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, Exception):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    try:
        from datetime import date
        drill_date = date.fromisoformat(data.get('drill_date', ''))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'drill_date must be YYYY-MM-DD'}, status=400)
    drill = svc.schedule_drill(
        org=org,
        drill_date=drill_date,
        rto_hours=float(data.get('rto_hours', 4.0)),
        rpo_hours=float(data.get('rpo_hours', 1.0)),
        performed_by=request.user,
    )
    return JsonResponse({'id': drill.id, 'drill_date': drill.drill_date.isoformat()}, status=201)


@login_required
@require_http_methods(['POST'])
def api_restore_drill_record(request, drill_id):
    svc = get_restore_drill_service()
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, Exception):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    try:
        drill = svc.record_result(
            drill_id=drill_id,
            actual_rto_minutes=int(data.get('actual_rto_minutes', 0)),
            actual_rpo_minutes=int(data.get('actual_rpo_minutes', 0)),
            passed=bool(data.get('passed', False)),
            notes=data.get('notes', ''),
            performed_by=request.user,
        )
        return JsonResponse({'id': drill.id, 'passed': drill.passed})
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=404)


@login_required
@require_http_methods(['GET'])
def api_restore_drill_summary(request):
    org = get_user_organization(request.user)
    svc = get_restore_drill_service()
    return JsonResponse(svc.get_drill_summary(org))
