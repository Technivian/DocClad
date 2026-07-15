
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




def _error_response(request, message, status):
    return JsonResponse(
        {
            'error': message,
            'request_id': getattr(request, 'request_id', None),
        },
        status=status,
    )


def _scim_response(payload, status=200):
    response = JsonResponse(payload, status=status)
    response['Content-Type'] = 'application/scim+json'
    return response


def _api_version_response(payload, status=200, version='1'):
    response = JsonResponse(payload, status=status)
    response['X-API-Version'] = str(version)
    return response


def _scim_paginated_list(queryset, request):
    total_results = queryset.count()
    try:
        start_index = max(int(request.GET.get('startIndex', 1)), 1)
    except (TypeError, ValueError):
        start_index = 1
    try:
        count = int(request.GET.get('count', total_results or 0))
    except (TypeError, ValueError):
        count = total_results or 0
    count = max(count, 0)
    zero_based_start = start_index - 1
    resources = list(queryset[zero_based_start:zero_based_start + count]) if count else []
    return total_results, start_index, count, resources


def _api_paginated_contracts(queryset, request):
    try:
        limit = int(request.GET.get('limit', 25))
    except (TypeError, ValueError):
        limit = 25
    try:
        offset = int(request.GET.get('offset', 0))
    except (TypeError, ValueError):
        offset = 0
    limit = max(0, min(limit, 100))
    offset = max(0, offset)
    total_count = queryset.count()
    resources = list(queryset[offset:offset + limit]) if limit else []
    return {
        'total_count': total_count,
        'limit': limit,
        'offset': offset,
        'next_offset': offset + limit if offset + limit < total_count else None,
        'previous_offset': max(0, offset - limit) if offset > 0 and limit else None,
        'resources': resources,
    }


def _resolve_scim_organization(request):
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    if not auth_header.startswith('Bearer '):
        return None, None
    token = auth_header.split(' ', 1)[1].strip()
    if not token:
        return None, None
    token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
    organization = (
        Organization.objects
        .filter(scim_enabled=True, scim_token_hash=token_hash)
        .only('id', 'scim_token_hash', 'scim_token_last4', 'name', 'slug')
        .first()
    )
    if organization:
        return organization, token
    return None, token


def _resolve_api_organization(request, required_scope='contracts:read'):
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    if not auth_header.startswith('Bearer '):
        return None, None, None
    token = auth_header.split(' ', 1)[1].strip()
    if not token:
        return None, None, None
    api_token = (
        OrganizationAPIToken.objects
        .select_related('organization')
        .filter(
            token_hash=OrganizationAPIToken._hash_token(token),
            is_active=True,
            organization__is_active=True,
        )
        .first()
    )
    if api_token:
        if api_token.is_expired:
            return None, token, api_token
        if not api_token.has_scope(required_scope):
            return None, token, api_token
        api_token.last_used_at = timezone.now()
        api_token.save(update_fields=['last_used_at', 'updated_at'])
        return api_token.organization, token, api_token
    return None, token, None


def _require_org_member_context(request):
    if not getattr(request.user, 'is_authenticated', False):
        return None, _error_response(request, 'Authentication required.', 401)
    organization = get_user_organization(request.user)
    if organization is None:
        return None, _error_response(request, 'No active organization context.', 403)
    membership = OrganizationMembership.objects.filter(
        organization=organization,
        user=request.user,
        is_active=True,
    ).first()
    if membership is None:
        return None, _error_response(request, 'No active organization membership.', 403)
    return organization, None


