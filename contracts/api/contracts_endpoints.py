
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
def contracts_api(request):
    """
    API endpoint for listing contracts with filtering and pagination.
    Used by the CLM One repository UI.
    """
    try:
        # Parse filters from request
        expiring_within_days = request.GET.get('expiring_within_days')
        params = ListParams(
            q=request.GET.get('q', ''),
            status=[s for s in request.GET.getlist('status') if s],
            lifecycle_stage=[s for s in request.GET.getlist('lifecycle_stage') if s],
            contract_type=[t for t in request.GET.getlist('contract_type') if t],
            owner=[owner for owner in request.GET.getlist('owner') if owner],
            counterparty=[party for party in request.GET.getlist('counterparty') if party],
            risk_level=[level for level in request.GET.getlist('risk_level') if level],
            approval_state=[state for state in request.GET.getlist('approval_state') if state],
            sort=request.GET.get('sort', 'updated_desc'),
            page=int(request.GET.get('page', 1)),
            page_size=int(request.GET.get('page_size', 25)),
            expiring_within_days=int(expiring_within_days) if expiring_within_days else None,
        )

        service = get_repository_service(request.user)
        result = service.list(params)
        return JsonResponse(result.to_dict())
    except Exception:
        logger.exception('contracts_api_failed')
        return _error_response(request, 'An unexpected error occurred.', 500)


@csrf_exempt
@require_http_methods(["GET"])
def contracts_api_v1(request):
    organization, token, api_token = _resolve_api_organization(request, required_scope='contracts:read')
    if organization is None:
        return _error_response(request, 'Missing or invalid API bearer token.', 401)

    try:
        service = get_repository_service(request.user)
        service.organization = organization
        try:
            page_size = int(request.GET.get('limit', request.GET.get('page_size', 25)) or 25)
        except (TypeError, ValueError):
            page_size = 25
        try:
            page = int(request.GET.get('page', 1) or 1)
        except (TypeError, ValueError):
            page = 1
        params = ListParams(
            q=request.GET.get('q', ''),
            status=[s for s in request.GET.getlist('status') if s],
            lifecycle_stage=[s for s in request.GET.getlist('lifecycle_stage') if s],
            contract_type=[t for t in request.GET.getlist('contract_type') if t],
            owner=[owner for owner in request.GET.getlist('owner') if owner],
            counterparty=[party for party in request.GET.getlist('counterparty') if party],
            risk_level=[level for level in request.GET.getlist('risk_level') if level],
            approval_state=[state for state in request.GET.getlist('approval_state') if state],
            sort=request.GET.get('sort', 'updated_desc'),
            page=max(1, page),
            page_size=max(1, min(page_size, 100)),
        )
        result = service.list(params)
        response = _api_version_response({
            'meta': {
                'version': '1',
                'organization': organization.slug,
                'token_label': api_token.label if api_token else '',
                'token_scopes': api_token.scopes if api_token else [],
                'limit': params.page_size,
                'offset': max(0, int(request.GET.get('offset', 0) or 0)),
                'total_count': result.total_count,
            },
            'data': result.to_dict(),
        })
        return response
    except Exception:
        logger.exception('contracts_api_v1_failed')
        return _error_response(request, 'An unexpected error occurred.', 500)


@login_required
@require_http_methods(["GET"])
def case_detail_api(request, contract_id=None, case_id=None):
    """Get single case details."""
    try:
        record_id = case_id or contract_id
        organization = get_user_organization(request.user)
        queryset = scope_queryset_for_organization(CareCase.objects.all(), organization)

        try:
            case = queryset.get(id=record_id)
        except CareCase.DoesNotExist:
            case = None
        
        if not case:
            return JsonResponse({'error': 'Casus niet gevonden'}, status=404)
            
        return JsonResponse(_build_case_data(case).to_dict())
        
    except Exception:
        logger.exception('contract_detail_api_failed')
        return _error_response(request, 'An unexpected error occurred.', 500)


@csrf_exempt
@require_http_methods(["GET"])
def contract_detail_api_v1(request, contract_id):
    organization, token, api_token = _resolve_api_organization(request, required_scope='contracts:read')
    if organization is None:
        return _error_response(request, 'Missing or invalid API bearer token.', 401)

    try:
        service = get_repository_service(request.user)
        service.organization = organization
        contract = service.get_by_id(contract_id)
        if not contract:
            return _error_response(request, 'Contract not found', 404)
        response = _api_version_response({
            'meta': {
                'version': '1',
                'organization': organization.slug,
                'token_label': api_token.label if api_token else '',
                'token_scopes': api_token.scopes if api_token else [],
            },
            'data': contract.to_dict(),
        })
        return response
    except Exception:
        logger.exception('contract_detail_api_v1_failed')
        return _error_response(request, 'An unexpected error occurred.', 500)


@login_required
@require_http_methods(["GET"])
def contract_detail_api(request, contract_id):
    """Legacy authenticated contract detail endpoint."""
    try:
        service = get_repository_service(request.user)
        result = service.get_by_id(contract_id)
        if not result:
            return _error_response(request, 'Contract not found', 404)
        return JsonResponse(result.to_dict())
    except Exception:
        logger.exception('contract_detail_api_failed')
        return _error_response(request, 'An unexpected error occurred.', 500)


@login_required
@require_http_methods(["POST"])
def cases_bulk_update_api(request):
    """Bulk update cases."""
    try:
        data = json.loads(request.body)
        case_ids = data.get('case_ids', data.get('contract_ids', []))
        updates = data.get('updates', {})

        if not isinstance(case_ids, list) or not case_ids:
            return _error_response(request, 'contract_ids must be a non-empty list', 400)

        try:
            normalized_contract_ids = [str(int(case_id)) for case_id in case_ids]
        except (TypeError, ValueError):
            return _error_response(request, 'contract_ids must contain numeric IDs only', 400)

        service = get_repository_service(request.user)
        result = service.bulk_update(normalized_contract_ids, updates)
        log_action(
            request.user,
            AuditLog.Action.UPDATE,
            'Contract',
            changes={
                'event': 'bulk_contract_update',
                'contract_ids': normalized_contract_ids,
                'updates': updates,
                'updated_count': result,
            },
            request=request,
        )

        return JsonResponse({'success': True, 'updated_count': result})
    except json.JSONDecodeError:
        return _error_response(request, 'Invalid JSON body', 400)
    except BulkUpdateValidationError as exc:
        return _error_response(request, str(exc), 400)
    except Exception:
        logger.exception('contracts_bulk_update_api_failed')
        return _error_response(request, 'An unexpected error occurred.', 500)


# Backwards-compatible alias used by legacy URL patterns.
contracts_bulk_update_api = cases_bulk_update_api

@login_required
@require_http_methods(['GET', 'POST'])
def contract_versions_api(request, contract_id):
    org = get_user_organization(request.user)
    svc = get_version_service()
    if request.method == 'POST':
        data = json.loads(request.body or '{}')
        try:
            contract = Contract.objects.get(pk=contract_id, organization=org)
        except Contract.DoesNotExist:
            return JsonResponse({'error': 'Not found'}, status=404)
        ver = svc.create_version(contract, changed_by=request.user, change_summary=data.get('change_summary', ''))
        return JsonResponse({'ok': True, 'version': _version_to_dict(ver)}, status=201)
    try:
        versions = svc.list_versions(contract_id, org)
    except Exception:
        return JsonResponse({'error': 'Not found'}, status=404)
    return JsonResponse({'versions': [_version_to_dict(v) for v in versions]})


@login_required
@require_http_methods(['GET'])
def contract_version_detail_api(request, contract_id, version_number):
    org = get_user_organization(request.user)
    svc = get_version_service()
    try:
        ver = svc.get_version(contract_id, version_number, org)
    except ContractVersion.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    return JsonResponse({'version': _version_to_dict(ver)})


@login_required
@require_http_methods(['GET'])
def contract_version_diff_api(request, contract_id):
    org = get_user_organization(request.user)
    svc = get_version_service()
    try:
        v1 = int(request.GET.get('v1', 0))
        v2 = int(request.GET.get('v2', 0))
        if not v1 or not v2:
            return JsonResponse({'error': 'v1 and v2 query params required'}, status=400)
        diff = svc.diff_versions(contract_id, v1, v2, org)
    except ContractVersion.DoesNotExist:
        return JsonResponse({'error': 'Version not found'}, status=404)
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    return JsonResponse({
        'contract_id': diff.contract_id,
        'v1': diff.v1,
        'v2': diff.v2,
        'added_lines': diff.added_lines,
        'removed_lines': diff.removed_lines,
        'unified_diff': diff.unified_diff,
    })


def _version_to_dict(ver: ContractVersion) -> dict:
    return {
        'id': ver.pk,
        'version_number': ver.version_number,
        'title_snapshot': ver.title_snapshot,
        'status_snapshot': ver.status_snapshot,
        'content_hash': ver.content_hash,
        'change_summary': ver.change_summary,
        'changed_by': ver.changed_by.username if ver.changed_by else None,
        'created_at': ver.created_at.isoformat() if ver.created_at else None,
    }

