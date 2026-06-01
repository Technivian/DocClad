
"""
API views for CMS Aegis repository functionality.
"""
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


def _scim_user_payload(membership):
    profile, _ = UserProfile.objects.get_or_create(user=membership.user)
    return {
        'schemas': ['urn:ietf:params:scim:schemas:core:2.0:User'],
        'id': str(membership.id),
        'userName': membership.user.email or membership.user.username,
        'name': {
            'givenName': membership.user.first_name or '',
            'familyName': membership.user.last_name or '',
        },
        'displayName': membership.user.get_full_name() or membership.user.username,
        'active': membership.is_active,
        'emails': [
            {
                'value': membership.user.email or '',
                'primary': True,
            }
        ],
        'externalId': membership.scim_external_id or str(membership.user.id),
        'meta': {
            'resourceType': 'User',
        },
        'urn:ietf:params:scim:schemas:extension:enterprise:2.0:User': {
            'role': membership.role,
            'mfaEnabled': profile.mfa_enabled,
            'sessionRevocationCounter': profile.session_revocation_counter,
        },
    }


def _scim_error(message, status, scim_type=None):
    payload = {'detail': message, 'status': str(status)}
    if scim_type:
        payload['scimType'] = scim_type
    return _scim_response(payload, status=status)


def _scim_value_to_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {'true', '1', 'yes', 'on'}


def _scim_first_non_empty_value(value):
    if isinstance(value, list):
        for entry in value:
            if isinstance(entry, dict):
                candidate = entry.get('value')
            else:
                candidate = entry
            if candidate not in {None, ''}:
                return candidate
        return ''
    if isinstance(value, dict):
        candidate = value.get('value')
        return candidate if candidate not in {None, ''} else ''
    return value if value not in {None, ''} else ''


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
    for organization in Organization.objects.filter(scim_enabled=True).only('id', 'scim_token_hash', 'scim_token_last4', 'name', 'slug'):
        if organization.matches_scim_token(token):
            return organization, token
    return None, token


def _resolve_api_organization(request, required_scope='contracts:read'):
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    if not auth_header.startswith('Bearer '):
        return None, None, None
    token = auth_header.split(' ', 1)[1].strip()
    if not token:
        return None, None, None
    for api_token in OrganizationAPIToken.objects.select_related('organization').filter(is_active=True, organization__is_active=True):
        if api_token.matches_token(token):
            if not api_token.has_scope(required_scope):
                return None, token, api_token
            api_token.last_used_at = timezone.now()
            api_token.save(update_fields=['last_used_at', 'updated_at'])
            return api_token.organization, token, api_token
    return None, token, None


def _scim_member_queryset(organization):
    return (
        OrganizationMembership.objects
        .filter(organization=organization)
        .select_related('user')
        .order_by('user__username')
    )


def _scim_group_queryset(organization):
    return (
        OrganizationSCIMGroup.objects
        .filter(organization=organization)
        .prefetch_related('members__user', 'nested_groups')
        .order_by('display_name')
    )


def _scim_role_priority(role):
    priorities = {
        OrganizationMembership.Role.MEMBER: 0,
        OrganizationMembership.Role.ADMIN: 1,
        OrganizationMembership.Role.OWNER: 2,
    }
    return priorities.get(role, 0)


def _scim_normalize_role(role):
    if not role:
        return OrganizationMembership.Role.MEMBER
    role_value = str(role).strip().upper()
    if role_value == OrganizationMembership.Role.OWNER:
        return OrganizationMembership.Role.OWNER
    if role_value == OrganizationMembership.Role.ADMIN:
        return OrganizationMembership.Role.ADMIN
    return OrganizationMembership.Role.MEMBER


def _scim_parse_filter(filter_value):
    if not filter_value:
        return None, None
    parts = str(filter_value).strip().split(' ', 2)
    if len(parts) != 3:
        return None, None
    field, operator, raw_value = parts
    if operator.lower() != 'eq':
        return None, None
    value = raw_value.strip().strip('"').strip("'")
    return field, value


def _scim_filter_memberships(organization, filter_value):
    field, value = _scim_parse_filter(filter_value)
    queryset = _scim_member_queryset(organization)
    if field is None:
        return queryset
    field_lower = field.lower()
    if field_lower in {'username', 'usernamevalue', 'username.value', 'usernamevalue.value'}:
        return queryset.filter(Q(user__email__iexact=value) | Q(user__username__iexact=value))
    if field_lower == 'externalid':
        return queryset.filter(scim_external_id__iexact=value)
    if field_lower in {'emails.value', 'email'}:
        return queryset.filter(user__email__iexact=value)
    if field_lower in {'name.givenname', 'givenname'}:
        return queryset.filter(user__first_name__icontains=value)
    if field_lower in {'name.familyname', 'familyname'}:
        return queryset.filter(user__last_name__icontains=value)
    if field_lower == 'displayname':
        return queryset.filter(
            Q(user__first_name__icontains=value)
            | Q(user__last_name__icontains=value)
            | Q(user__username__icontains=value)
            | Q(user__email__iexact=value)
        ).distinct()
    if field_lower == 'active':
        return queryset.filter(is_active=str(value).lower() in {'true', '1'})
    return queryset


def _scim_filter_groups(organization, filter_value):
    field, value = _scim_parse_filter(filter_value)
    queryset = _scim_group_queryset(organization)
    if field is None:
        return queryset
    field_lower = field.lower()
    if field_lower == 'displayname':
        return queryset.filter(display_name__icontains=value)
    if field_lower == 'externalid':
        return queryset.filter(external_id__iexact=value)
    if field_lower == 'active':
        return queryset.filter(is_active=str(value).lower() in {'true', '1'})
    return queryset


def _upsert_scim_member(organization, user_name, first_name='', last_name='', active=True, role=None, external_id=''):
    email = (user_name or '').strip().lower()
    if not email:
        raise ValueError('userName is required')
    external_id = (external_id or '').strip()
    membership = None
    if external_id:
        membership = (
            OrganizationMembership.objects
            .select_related('user')
            .filter(organization=organization, scim_external_id__iexact=external_id)
            .first()
        )
    user = membership.user if membership else User.objects.filter(email__iexact=email).first()
    if user is None:
        user = User.objects.create_user(
            username=email.split('@', 1)[0] or email,
            email=email,
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            is_active=active,
        )
    else:
        updates = []
        if user.username != (email.split('@', 1)[0] or email):
            user.username = email.split('@', 1)[0] or email
            updates.append('username')
        if first_name.strip() and user.first_name != first_name.strip():
            user.first_name = first_name.strip()
            updates.append('first_name')
        if last_name.strip() and user.last_name != last_name.strip():
            user.last_name = last_name.strip()
            updates.append('last_name')
        if user.is_active != active:
            user.is_active = active
            updates.append('is_active')
        if updates:
            user.save(update_fields=updates)

    if membership is None:
        membership, _ = OrganizationMembership.objects.get_or_create(
            organization=organization,
            user=user,
            defaults={
                'role': role or OrganizationMembership.Role.MEMBER,
                'is_active': active,
                'scim_external_id': external_id,
            },
        )
    updates = []
    if membership.user_id != user.id:
        membership.user = user
        updates.append('user')
    if external_id and membership.scim_external_id != external_id:
        membership.scim_external_id = external_id
        updates.append('scim_external_id')
    if role and membership.role != role:
        membership.role = role
        updates.append('role')
    if membership.is_active != active:
        membership.is_active = active
        updates.append('is_active')
    if updates:
        membership.save(update_fields=updates)
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return membership, profile


def _apply_scim_user_updates(membership, data):
    user = membership.user
    name = data.get('name') or {}
    enterprise = data.get('urn:ietf:params:scim:schemas:extension:enterprise:2.0:User') or {}
    active = data.get('active')
    updates = []
    membership_updates = []

    user_name = (data.get('userName') or '').strip().lower()
    if user_name and user.email != user_name:
        user.email = user_name
        user.username = user_name.split('@', 1)[0] or user_name
        updates.extend(['email', 'username'])
    if name.get('givenName') is not None and user.first_name != (name.get('givenName') or '').strip():
        user.first_name = (name.get('givenName') or '').strip()
        updates.append('first_name')
    if name.get('familyName') is not None and user.last_name != (name.get('familyName') or '').strip():
        user.last_name = (name.get('familyName') or '').strip()
        updates.append('last_name')
    if active is not None and user.is_active != _scim_value_to_bool(active):
        user.is_active = _scim_value_to_bool(active)
        updates.append('is_active')
    external_id = data.get('externalId')
    if external_id is not None:
        external_id = str(external_id).strip()
        if membership.scim_external_id != external_id:
            membership.scim_external_id = external_id
            membership_updates.append('scim_external_id')
    if updates:
        user.save(update_fields=list(dict.fromkeys(updates)))

    if active is not None and membership.is_active != _scim_value_to_bool(active):
        membership.is_active = _scim_value_to_bool(active)
        membership_updates.append('is_active')
    role = enterprise.get('role')
    if role and membership.role != role:
        membership.role = role
        membership_updates.append('role')
    if membership_updates:
        membership.save(update_fields=membership_updates)

    profile, _ = UserProfile.objects.get_or_create(user=user)
    if enterprise.get('mfaEnabled') is not None or profile.mfa_enabled != _scim_value_to_bool(enterprise.get('mfaEnabled', profile.mfa_enabled), profile.mfa_enabled):
        profile.mfa_enabled = _scim_value_to_bool(enterprise.get('mfaEnabled', profile.mfa_enabled), profile.mfa_enabled)
        if profile.mfa_enabled:
            profile.mfa_verified_at = timezone.now()
        profile.save(update_fields=['mfa_enabled', 'mfa_verified_at', 'updated_at'])

    return membership


def _scim_group_payload(group):
    members = []
    for membership in group.members.select_related('user').order_by('user__username'):
        members.append({
            'value': str(membership.id),
            'type': 'User',
            'display': membership.user.get_full_name() or membership.user.username,
        })
    for nested_group in group.nested_groups.order_by('display_name'):
        members.append({
            'value': str(nested_group.id),
            'type': 'Group',
            'display': nested_group.display_name,
        })

    return {
        'schemas': ['urn:ietf:params:scim:schemas:core:2.0:Group'],
        'id': str(group.id),
        'displayName': group.display_name,
        'externalId': group.external_id or '',
        'active': group.is_active,
        'members': members,
        'meta': {
            'resourceType': 'Group',
        },
        'urn:ietf:params:scim:schemas:extension:enterprise:2.0:Group': {
            'role': group.role,
        },
    }


def _scim_group_membership_contains(group, membership_id, seen=None):
    seen = seen or set()
    if group.id in seen:
        return False
    seen.add(group.id)
    if group.members.filter(id=membership_id).exists():
        return True
    for nested_group in group.nested_groups.filter(is_active=True):
        if _scim_group_membership_contains(nested_group, membership_id, seen):
            return True
    return False


def _reconcile_scim_group_membership_role(organization, membership):
    target_role = OrganizationMembership.Role.MEMBER
    for group in _scim_group_queryset(organization).filter(is_active=True):
        if _scim_group_membership_contains(group, membership.id):
            group_role = _scim_normalize_role(group.role)
            if _scim_role_priority(group_role) > _scim_role_priority(target_role):
                target_role = group_role
    if membership.role != target_role:
        membership.role = target_role
        membership.save(update_fields=['role'])


def _reconcile_all_scim_group_memberships(organization):
    for membership in _scim_member_queryset(organization):
        _reconcile_scim_group_membership_role(organization, membership)


def _resolve_scim_group_reference(organization, value):
    if not value:
        return None
    value = str(value).strip()
    if not value:
        return None
    if value.isdigit():
        return OrganizationSCIMGroup.objects.filter(organization=organization, id=int(value)).first()
    return OrganizationSCIMGroup.objects.filter(
        organization=organization,
        display_name__iexact=value,
    ).first() or OrganizationSCIMGroup.objects.filter(
        organization=organization,
        external_id__iexact=value,
    ).first()


def _sync_scim_group_relations(group, member_entries):
    desired_memberships = set()
    desired_nested_groups = set()
    for entry in member_entries or []:
        if not isinstance(entry, dict):
            continue
        member_type = str(entry.get('type') or 'User').strip().lower()
        member_value = entry.get('value')
        if member_type == 'group':
            nested_group = _resolve_scim_group_reference(group.organization, member_value)
            if nested_group and nested_group.id != group.id:
                desired_nested_groups.add(nested_group.id)
            continue
        if member_value is not None:
            desired_memberships.add(str(member_value))

    current_memberships = set(str(member.id) for member in group.members.all())
    current_nested_groups = set(str(nested_group.id) for nested_group in group.nested_groups.all())

    for membership_id in current_memberships - desired_memberships:
        membership = OrganizationMembership.objects.filter(id=membership_id, organization=group.organization).first()
        if membership:
            group.members.remove(membership)
            _reconcile_scim_group_membership_role(group.organization, membership)

    for membership_id in desired_memberships - current_memberships:
        membership = OrganizationMembership.objects.filter(id=membership_id, organization=group.organization).first()
        if membership:
            group.members.add(membership)

    for nested_group_id in current_nested_groups - desired_nested_groups:
        nested_group = OrganizationSCIMGroup.objects.filter(id=nested_group_id, organization=group.organization).first()
        if nested_group:
            group.nested_groups.remove(nested_group)

    for nested_group_id in desired_nested_groups - current_nested_groups:
        nested_group = OrganizationSCIMGroup.objects.filter(id=nested_group_id, organization=group.organization).first()
        if nested_group:
            group.nested_groups.add(nested_group)

    for membership_id in desired_memberships | current_memberships:
        membership = OrganizationMembership.objects.filter(id=membership_id, organization=group.organization).first()
        if membership:
            _reconcile_scim_group_membership_role(group.organization, membership)
    _reconcile_all_scim_group_memberships(group.organization)


def _upsert_scim_group(organization, display_name, external_id='', role=None, active=True, member_entries=None):
    display_name = (display_name or '').strip()
    if not display_name:
        raise ValueError('displayName is required')

    group = None
    external_id = (external_id or '').strip()
    if external_id:
        group = OrganizationSCIMGroup.objects.filter(organization=organization, external_id=external_id).first()
    if group is None:
        group = OrganizationSCIMGroup.objects.filter(organization=organization, display_name__iexact=display_name).first()
    if group is None:
        group = OrganizationSCIMGroup.objects.create(
            organization=organization,
            external_id=external_id,
            display_name=display_name,
            role=_scim_normalize_role(role),
            is_active=active,
        )
    else:
        updates = []
        if group.display_name != display_name:
            group.display_name = display_name
            updates.append('display_name')
        if external_id and group.external_id != external_id:
            group.external_id = external_id
            updates.append('external_id')
        normalized_role = _scim_normalize_role(role or group.role)
        if group.role != normalized_role:
            group.role = normalized_role
            updates.append('role')
        if group.is_active != active:
            group.is_active = active
            updates.append('is_active')
        if updates:
            group.save(update_fields=updates)

    if member_entries is not None:
        _sync_scim_group_relations(group, member_entries)
    return group


@login_required
@require_http_methods(["GET"])
def contracts_api(request):
    """
    API endpoint for listing contracts with filtering and pagination.
    Used by the CMS Aegis repository UI.
    """
    try:
        # Parse filters from request
        params = ListParams(
            q=request.GET.get('q', ''),
            status=[s for s in request.GET.getlist('status') if s],
            contract_type=[t for t in request.GET.getlist('contract_type') if t],
            sort=request.GET.get('sort', 'updated_desc'),
            page=int(request.GET.get('page', 1)),
            page_size=int(request.GET.get('page_size', 25))
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
            contract_type=[t for t in request.GET.getlist('contract_type') if t],
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


@csrf_exempt
@require_http_methods(["GET", "POST"])
def scim_users_api(request):
    organization, token = _resolve_scim_organization(request)
    if organization is None:
        return _scim_error('Missing or invalid SCIM bearer token.', 401)

    if request.method == 'GET':
        queryset = _scim_filter_memberships(organization, request.GET.get('filter', ''))
        total_results, start_index, items_per_page, memberships = _scim_paginated_list(queryset, request)
        resources = [_scim_user_payload(membership) for membership in memberships]
        return _scim_response({
            'schemas': ['urn:ietf:params:scim:api:messages:2.0:ListResponse'],
            'totalResults': total_results,
            'itemsPerPage': items_per_page,
            'startIndex': start_index,
            'Resources': resources,
        })

    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return _scim_error('Invalid JSON body.', 400, scim_type='invalidSyntax')

    if data.get('Operations'):
        return _scim_error(
            'SCIM POST create does not accept Operations; use PATCH on /Users/{id}.',
            400,
            scim_type='invalidSyntax',
        )

    user_name = data.get('userName') or ''
    name = data.get('name') or {}
    enterprise = data.get('urn:ietf:params:scim:schemas:extension:enterprise:2.0:User') or {}
    active = _scim_value_to_bool(data.get('active', True), True)
    role = enterprise.get('role') or OrganizationMembership.Role.MEMBER
    membership, profile = _upsert_scim_member(
        organization,
        user_name=user_name,
        first_name=name.get('givenName', ''),
        last_name=name.get('familyName', ''),
        active=active,
        role=role,
        external_id=data.get('externalId', ''),
    )
    profile.mfa_enabled = _scim_value_to_bool(enterprise.get('mfaEnabled', profile.mfa_enabled), profile.mfa_enabled)
    if profile.mfa_enabled:
        profile.mfa_verified_at = timezone.now()
    profile.save(update_fields=['mfa_enabled', 'mfa_verified_at', 'updated_at'])
    _apply_scim_user_updates(membership, data)
    log_action(
        None,
        AuditLog.Action.CREATE,
        'OrganizationMembership',
        object_id=membership.id,
        object_repr=str(membership),
        changes={
            'organization_id': organization.id,
            'event': 'scim_user_provisioned',
            'user_name': user_name,
            'active': active,
        },
    )
    return _scim_response(_scim_user_payload(membership), status=201)


@csrf_exempt
@require_http_methods(["GET", "PATCH", "DELETE"])
def scim_user_api(request, scim_id):
    organization, token = _resolve_scim_organization(request)
    if organization is None:
        return _scim_error('Missing or invalid SCIM bearer token.', 401)

    membership = get_object_or_404(OrganizationMembership, id=scim_id, organization=organization)

    if request.method == 'GET':
        return _scim_response(_scim_user_payload(membership))

    if request.method == 'DELETE':
        membership.is_active = False
        membership.save(update_fields=['is_active'])
        _reconcile_all_scim_group_memberships(organization)
        log_action(
            None,
            AuditLog.Action.DELETE,
            'OrganizationMembership',
            object_id=membership.id,
            object_repr=str(membership),
            changes={'organization_id': organization.id, 'event': 'scim_user_deprovisioned'},
        )
        return HttpResponse(status=204)

    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return _scim_error('Invalid JSON body.', 400, scim_type='invalidSyntax')

    operations = data.get('Operations') or []
    if operations:
        for operation in operations:
            op = (operation.get('op') or operation.get('operation') or '').lower()
            path = (operation.get('path') or '').lower()
            value = operation.get('value')
            if op not in {'add', 'replace'}:
                continue
            if path == 'active' and value is not None:
                membership.is_active = _scim_value_to_bool(value)
                membership.save(update_fields=['is_active'])
            elif path == 'externalid' and value is not None:
                membership.scim_external_id = str(value).strip()
                membership.save(update_fields=['scim_external_id'])
            elif path in {'username', 'usernamevalue'} and value:
                _apply_scim_user_updates(membership, {'userName': value})
            elif path in {'name', 'displayname'} and isinstance(value, dict):
                _apply_scim_user_updates(membership, {'name': value})
            elif path in {'name.givenname', 'givenname'}:
                _apply_scim_user_updates(membership, {'name': {'givenName': value}})
            elif path in {'name.familyname', 'familyname'}:
                _apply_scim_user_updates(membership, {'name': {'familyName': value}})
            elif path.startswith('emails') and isinstance(value, (list, dict, str)):
                first_email = _scim_first_non_empty_value(value)
                if first_email:
                    _apply_scim_user_updates(membership, {'userName': first_email})
            elif path == 'urn:ietf:params:scim:schemas:extension:enterprise:2.0:user' and isinstance(value, dict):
                _apply_scim_user_updates(membership, {'urn:ietf:params:scim:schemas:extension:enterprise:2.0:User': value})
        _apply_scim_user_updates(membership, data)
        _reconcile_scim_group_membership_role(organization, membership)
    else:
        active = data.get('active')
        updates = []
        if active is not None:
            new_active = _scim_value_to_bool(active)
            if membership.is_active != new_active:
                membership.is_active = new_active
                updates.append('is_active')
        enterprise = data.get('urn:ietf:params:scim:schemas:extension:enterprise:2.0:User') or {}
        if data.get('externalId') is not None:
            external_id = str(data.get('externalId')).strip()
            if membership.scim_external_id != external_id:
                membership.scim_external_id = external_id
                updates.append('scim_external_id')
        if enterprise.get('role') and enterprise['role'] != membership.role:
            membership.role = enterprise['role']
            updates.append('role')
        if updates:
            membership.save(update_fields=updates)
            _reconcile_scim_group_membership_role(organization, membership)
    return _scim_response(_scim_user_payload(membership))


@csrf_exempt
@require_http_methods(["GET", "POST"])
def scim_groups_api(request):
    organization, token = _resolve_scim_organization(request)
    if organization is None:
        return _scim_error('Missing or invalid SCIM bearer token.', 401)

    if request.method == 'GET':
        queryset = _scim_filter_groups(organization, request.GET.get('filter', ''))
        total_results, start_index, items_per_page, groups = _scim_paginated_list(queryset, request)
        resources = [_scim_group_payload(group) for group in groups]
        return _scim_response({
            'schemas': ['urn:ietf:params:scim:api:messages:2.0:ListResponse'],
            'totalResults': total_results,
            'itemsPerPage': items_per_page,
            'startIndex': start_index,
            'Resources': resources,
        })

    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return _scim_error('Invalid JSON body.', 400, scim_type='invalidSyntax')

    enterprise = data.get('urn:ietf:params:scim:schemas:extension:enterprise:2.0:Group') or {}
    member_entries = [member for member in data.get('members', []) if isinstance(member, dict)]
    active = _scim_value_to_bool(data.get('active', True), True)
    group = _upsert_scim_group(
        organization,
        display_name=data.get('displayName', ''),
        external_id=data.get('externalId', ''),
        role=enterprise.get('role'),
        active=active,
        member_entries=member_entries,
    )
    log_action(
        None,
        AuditLog.Action.CREATE,
        'OrganizationSCIMGroup',
        object_id=group.id,
        object_repr=str(group),
        changes={
            'organization_id': organization.id,
            'event': 'scim_group_provisioned',
            'display_name': group.display_name,
        },
    )
    return _scim_response(_scim_group_payload(group), status=201)


@csrf_exempt
@require_http_methods(["GET", "PATCH", "DELETE"])
def scim_group_api(request, scim_id):
    organization, token = _resolve_scim_organization(request)
    if organization is None:
        return _scim_error('Missing or invalid SCIM bearer token.', 401)

    group = get_object_or_404(OrganizationSCIMGroup, id=scim_id, organization=organization)

    if request.method == 'GET':
        return _scim_response(_scim_group_payload(group))

    if request.method == 'DELETE':
        group.is_active = False
        group.save(update_fields=['is_active'])
        for membership in list(group.members.all()):
            group.members.remove(membership)
        for nested_group in list(group.nested_groups.all()):
            group.nested_groups.remove(nested_group)
        _reconcile_all_scim_group_memberships(organization)
        log_action(
            None,
            AuditLog.Action.DELETE,
            'OrganizationSCIMGroup',
            object_id=group.id,
            object_repr=str(group),
            changes={'organization_id': organization.id, 'event': 'scim_group_deprovisioned'},
        )
        return HttpResponse(status=204)

    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return _scim_error('Invalid JSON body.', 400, scim_type='invalidSyntax')

    operations = data.get('Operations') or []
    changed = False
    if operations:
        for operation in operations:
            op = (operation.get('op') or operation.get('operation') or '').lower()
            path = (operation.get('path') or '').lower()
            value = operation.get('value')
            if path in {'displayname', 'externalid', 'active'} or not path:
                if 'displayName' in operation and group.display_name != operation['displayName']:
                    group.display_name = operation['displayName']
                    changed = True
                if 'externalId' in operation and group.external_id != operation['externalId']:
                    group.external_id = operation['externalId']
                    changed = True
                if 'active' in operation:
                    new_active = _scim_value_to_bool(operation['active'])
                    if group.is_active != new_active:
                        group.is_active = new_active
                        changed = True
            if path == 'members' or (op in {'add', 'replace'} and isinstance(value, dict) and 'members' in value):
                member_values = value if isinstance(value, list) else value.get('members', [])
                _sync_scim_group_relations(group, member_values)
                changed = True
    else:
        if 'displayName' in data and group.display_name != data['displayName']:
            group.display_name = data['displayName']
            changed = True
        if 'externalId' in data and group.external_id != data['externalId']:
            group.external_id = data['externalId']
            changed = True
        if 'active' in data:
            new_active = _scim_value_to_bool(data['active'])
            if group.is_active != new_active:
                group.is_active = new_active
                changed = True
        enterprise = data.get('urn:ietf:params:scim:schemas:extension:enterprise:2.0:Group') or {}
        if enterprise.get('role'):
            normalized_role = _scim_normalize_role(enterprise['role'])
            if group.role != normalized_role:
                group.role = normalized_role
                changed = True
        if 'members' in data:
            _sync_scim_group_relations(group, data.get('members', []))
            changed = True

    if changed:
        group.save()
    return _scim_response(_scim_group_payload(group))


def _require_org_admin_for_salesforce(request):
    if not getattr(request.user, 'is_authenticated', False):
        return None, _error_response(request, 'Authentication required.', 401)
    organization = get_user_organization(request.user)
    if organization is None:
        return None, _error_response(request, 'No active organization context.', 403)
    if not can_manage_organization(request.user, organization):
        return None, _error_response(request, 'Only organization admins/owners can manage integrations.', 403)
    return organization, None


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


@login_required
@require_http_methods(["GET"])
def salesforce_connection_status_api(request):
    organization, error = _require_org_admin_for_salesforce(request)
    if error:
        return error

    connection = SalesforceOrganizationConnection.objects.filter(organization=organization).first()
    if connection and connection.refresh_token and connection.token_expired:
        try:
            refreshed = refresh_salesforce_access_token(decrypt_salesforce_token(connection.refresh_token))
            connection.access_token = encrypt_salesforce_token(refreshed.access_token)
            connection.instance_url = refreshed.instance_url or connection.instance_url
            connection.scope = refreshed.scope or connection.scope
            connection.token_expires_at = refreshed.token_expires_at
            if refreshed.refresh_token:
                connection.refresh_token = encrypt_salesforce_token(refreshed.refresh_token)
            connection.save(update_fields=['access_token', 'instance_url', 'scope', 'token_expires_at', 'updated_at'])
        except Exception:
            logger.exception('Salesforce token refresh failed for org_id=%s', organization.id)

    persisted_maps = get_effective_field_map_records(organization)
    return JsonResponse(
        {
            'configured': salesforce_oauth_is_configured(),
            'connected': bool(connection and connection.is_active and connection.access_token),
            'connection': (
                {
                    'instance_url': connection.instance_url,
                    'external_org_id': connection.external_org_id,
                    'scope': connection.scope,
                    'token_expires_at': connection.token_expires_at.isoformat() if connection.token_expires_at else None,
                    'updated_at': connection.updated_at.isoformat() if connection.updated_at else None,
                }
                if connection and connection.is_active
                else None
            ),
            'mapping_count': len(persisted_maps),
        }
    )


@login_required
@require_http_methods(["POST"])
def salesforce_oauth_start_api(request):
    organization, error = _require_org_admin_for_salesforce(request)
    if error:
        return error
    if not salesforce_oauth_is_configured():
        return _error_response(request, 'Salesforce OAuth is not configured.', 400)

    state = secrets.token_urlsafe(24)
    request.session['salesforce_oauth_state'] = state
    request.session['salesforce_oauth_org_id'] = organization.id
    authorize_url = build_salesforce_authorize_url(state)
    return JsonResponse({'authorize_url': authorize_url, 'state': state})


@login_required
@require_http_methods(["GET"])
def salesforce_oauth_callback_api(request):
    organization, error = _require_org_admin_for_salesforce(request)
    if error:
        return error
    if not salesforce_oauth_is_configured():
        return _error_response(request, 'Salesforce OAuth is not configured.', 400)

    state = request.GET.get('state', '').strip()
    code = request.GET.get('code', '').strip()
    expected_state = request.session.get('salesforce_oauth_state')
    expected_org_id = request.session.get('salesforce_oauth_org_id')
    if not state or state != expected_state or expected_org_id != organization.id:
        return _error_response(request, 'Invalid OAuth state.', 400)
    if not code:
        return _error_response(request, 'Missing Salesforce authorization code.', 400)

    try:
        token_data = exchange_salesforce_code_for_tokens(code)
    except Exception:
        logger.exception('Salesforce OAuth callback failed for org_id=%s', organization.id)
        return _error_response(request, 'Salesforce OAuth exchange failed.', 502)

    connection, _ = SalesforceOrganizationConnection.objects.get_or_create(
        organization=organization,
        defaults={'connected_by': request.user},
    )
    connection.connected_by = request.user
    connection.external_org_id = token_data.external_org_id
    connection.instance_url = token_data.instance_url
    connection.access_token = encrypt_salesforce_token(token_data.access_token)
    connection.refresh_token = (
        encrypt_salesforce_token(token_data.refresh_token) if token_data.refresh_token else connection.refresh_token
    )
    connection.scope = token_data.scope
    connection.token_expires_at = token_data.token_expires_at
    connection.is_active = True
    connection.save()

    request.session.pop('salesforce_oauth_state', None)
    request.session.pop('salesforce_oauth_org_id', None)
    return JsonResponse({'connected': True, 'instance_url': connection.instance_url, 'external_org_id': connection.external_org_id})


@login_required
@require_http_methods(["POST"])
def salesforce_disconnect_api(request):
    organization, error = _require_org_admin_for_salesforce(request)
    if error:
        return error
    connection = SalesforceOrganizationConnection.objects.filter(organization=organization).first()
    if not connection:
        return JsonResponse({'disconnected': True, 'message': 'No active Salesforce connection.'})

    connection.is_active = False
    connection.access_token = ''
    connection.refresh_token = ''
    connection.scope = ''
    connection.token_expires_at = None
    connection.save(update_fields=['is_active', 'access_token', 'refresh_token', 'scope', 'token_expires_at', 'updated_at'])
    return JsonResponse({'disconnected': True})


@login_required
@require_http_methods(["GET", "PUT"])
def salesforce_field_map_api(request):
    organization, error = _require_org_admin_for_salesforce(request)
    if error:
        return error

    if request.method == 'GET':
        persisted = list(
            OrganizationContractFieldMap.objects.filter(organization=organization, is_active=True)
            .values('canonical_field', 'salesforce_object', 'salesforce_field', 'is_required', 'transform_rule')
            .order_by('canonical_field')
        )
        mappings = persisted or default_field_map_records()
        return JsonResponse({'mappings': mappings, 'source': 'database' if persisted else 'default'})

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return _error_response(request, 'Invalid JSON body.', 400)
    mappings = payload.get('mappings')
    if not isinstance(mappings, list) or not mappings:
        return _error_response(request, 'mappings must be a non-empty list.', 400)

    seen_fields = set()
    allowed_fields = set(CANONICAL_CONTRACT_FIELDS)
    normalized = []
    for item in mappings:
        if not isinstance(item, dict):
            return _error_response(request, 'Each mapping must be an object.', 400)
        canonical_field = str(item.get('canonical_field', '')).strip()
        salesforce_field = str(item.get('salesforce_field', '')).strip()
        salesforce_object = str(item.get('salesforce_object', '')).strip() or 'Opportunity'
        transform_rule = str(item.get('transform_rule', '')).strip()
        is_required = bool(item.get('is_required', False))
        if not canonical_field or not salesforce_field:
            return _error_response(request, 'canonical_field and salesforce_field are required.', 400)
        if canonical_field not in allowed_fields:
            return _error_response(request, f'Unsupported canonical_field: {canonical_field}', 400)
        if canonical_field in seen_fields:
            return _error_response(request, f'Duplicate canonical_field: {canonical_field}', 400)
        seen_fields.add(canonical_field)
        normalized.append(
            {
                'canonical_field': canonical_field,
                'salesforce_field': salesforce_field,
                'salesforce_object': salesforce_object,
                'transform_rule': transform_rule,
                'is_required': is_required,
            }
        )

    active_fields = [item['canonical_field'] for item in normalized]
    OrganizationContractFieldMap.objects.filter(organization=organization).exclude(canonical_field__in=active_fields).update(
        is_active=False,
        updated_by=request.user,
    )
    for item in normalized:
        mapping, _ = OrganizationContractFieldMap.objects.get_or_create(
            organization=organization,
            canonical_field=item['canonical_field'],
            defaults={'created_by': request.user},
        )
        mapping.salesforce_field = item['salesforce_field']
        mapping.salesforce_object = item['salesforce_object']
        mapping.transform_rule = item['transform_rule']
        mapping.is_required = item['is_required']
        mapping.is_active = True
        mapping.updated_by = request.user
        mapping.save()

    return JsonResponse({'updated': len(normalized)})


@login_required
@require_http_methods(["POST"])
def salesforce_ingest_preview_api(request):
    organization, error = _require_org_admin_for_salesforce(request)
    if error:
        return error

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return _error_response(request, 'Invalid JSON body.', 400)

    records = payload.get('records')
    dry_run = bool(payload.get('dry_run', True))
    if not isinstance(records, list):
        return _error_response(request, 'records must be a list.', 400)

    summary = ingest_salesforce_records(organization, records, dry_run=dry_run)
    return JsonResponse({'summary': summary, 'dry_run': dry_run})


@login_required
@require_http_methods(["POST"])
def salesforce_sync_api(request):
    organization, error = _require_org_admin_for_salesforce(request)
    if error:
        return error

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return _error_response(request, 'Invalid JSON body.', 400)

    connection = SalesforceOrganizationConnection.objects.filter(organization=organization, is_active=True).first()
    if connection is None:
        return _error_response(request, 'No active Salesforce connection.', 400)

    dry_run = bool(payload.get('dry_run', False))
    limit = payload.get('limit', getattr(settings, 'SALESFORCE_SYNC_DEFAULT_LIMIT', 200))
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        return _error_response(request, 'limit must be an integer.', 400)
    if limit <= 0 or limit > 2000:
        return _error_response(request, 'limit must be between 1 and 2000.', 400)

    try:
        run = create_salesforce_sync_run(
            organization=organization,
            connection=connection,
            trigger_source=SalesforceSyncRun.TriggerSource.API,
            dry_run=dry_run,
            limit=limit,
            triggered_by=request.user,
        )
    except SalesforceSyncError as exc:
        return _error_response(request, str(exc), 409)

    try:
        summary = sync_salesforce_connection(connection, dry_run=dry_run, limit=limit)
    except Exception:
        logger.exception('Salesforce sync failed for org_id=%s', organization.id)
        run.status = SalesforceSyncRun.Status.FAILED
        run.error_message = 'Salesforce sync failed.'
        run.completed_at = timezone.now()
        run.save(update_fields=['status', 'error_message', 'completed_at'])
        queue_webhook_event(
            organization=organization,
            event_type='salesforce.sync.failed',
            payload={
                'run_id': run.id,
                'status': run.status,
                'error_message': run.error_message,
                'dry_run': dry_run,
                'limit': limit,
            },
        )
        return _error_response(request, 'Salesforce sync failed.', 502)

    run.status = SalesforceSyncRun.Status.SUCCESS
    run.source_object = str(summary.get('source_object', '') or '')
    run.fetched_records = int(summary.get('fetched_records', 0) or 0)
    run.created_count = int(summary.get('created', 0) or 0)
    run.updated_count = int(summary.get('updated', 0) or 0)
    run.skipped_count = int(summary.get('skipped', 0) or 0)
    run.error_count = len(summary.get('errors') or [])
    run.summary = summary
    run.completed_at = timezone.now()
    run.save(
        update_fields=[
            'status',
            'source_object',
            'fetched_records',
            'created_count',
            'updated_count',
            'skipped_count',
            'error_count',
            'summary',
            'completed_at',
        ]
    )
    queue_webhook_event(
        organization=organization,
        event_type='salesforce.sync.completed',
        payload={
            'run_id': run.id,
            'status': run.status,
            'dry_run': dry_run,
            'summary': summary,
        },
    )
    return JsonResponse({'summary': summary, 'dry_run': dry_run})


@login_required
@require_http_methods(["GET"])
def salesforce_sync_runs_api(request):
    organization, error = _require_org_admin_for_salesforce(request)
    if error:
        return error

    limit = request.GET.get('limit', 20)
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        return _error_response(request, 'limit must be an integer.', 400)
    limit = max(1, min(limit, 100))

    runs = (
        SalesforceSyncRun.objects.filter(organization=organization)
        .select_related('triggered_by')
        .order_by('-started_at')[:limit]
    )
    payload = []
    for run in runs:
        payload.append(
            {
                'id': run.id,
                'status': run.status,
                'trigger_source': run.trigger_source,
                'dry_run': run.dry_run,
                'limit_applied': run.limit_applied,
                'source_object': run.source_object,
                'fetched_records': run.fetched_records,
                'created_count': run.created_count,
                'updated_count': run.updated_count,
                'skipped_count': run.skipped_count,
                'error_count': run.error_count,
                'error_message': run.error_message,
                'started_at': run.started_at.isoformat() if run.started_at else None,
                'completed_at': run.completed_at.isoformat() if run.completed_at else None,
                'triggered_by': run.triggered_by.username if run.triggered_by else None,
            }
        )
    return JsonResponse({'runs': payload})


@login_required
@require_http_methods(["POST"])
def netsuite_sync_api(request):
    organization, error = _require_org_admin_for_salesforce(request)
    if error:
        return error

    if not netsuite_is_configured():
        return _error_response(request, 'NetSuite integration is not configured.', 400)

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return _error_response(request, 'Invalid JSON body.', 400)

    dry_run = bool(payload.get('dry_run', False))
    limit = payload.get('limit', 200)
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        return _error_response(request, 'limit must be an integer.', 400)
    if limit <= 0 or limit > 2000:
        return _error_response(request, 'limit must be between 1 and 2000.', 400)

    try:
        records = fetch_netsuite_records(limit=limit)
    except NetSuiteSyncError as exc:
        return _error_response(request, str(exc), 502)

    if dry_run:
        summary = {'total_records': len(records), 'created': 0, 'updated': 0, 'skipped': 0, 'errors': []}
        for index, record in enumerate(records):
            try:
                mapped = map_netsuite_record(record)
                source_id = str(mapped.get('source_system_id', '') or '').strip()
                title = str(mapped.get('contract_title', '') or '').strip()
                if not source_id or not title:
                    summary['skipped'] += 1
                    continue
                exists = Contract.objects.filter(
                    organization=organization,
                    source_system='netsuite',
                    source_system_id=source_id,
                ).exists()
                if exists:
                    summary['updated'] += 1
                else:
                    summary['created'] += 1
            except Exception as exc:
                summary['errors'].append({'index': index, 'error': str(exc)})
    else:
        summary = ingest_netsuite_records(organization, records)

    summary['fetched_records'] = len(records)
    summary['dry_run'] = dry_run
    summary['source'] = 'netsuite_api'
    return JsonResponse({'summary': summary, 'dry_run': dry_run})


@login_required
@require_http_methods(["GET"])
def webhook_deliveries_api(request):
    organization, error = _require_org_admin_for_salesforce(request)
    if error:
        return error

    limit = request.GET.get('limit', 50)
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        return _error_response(request, 'limit must be an integer.', 400)
    limit = max(1, min(limit, 200))

    deliveries = (
        WebhookDelivery.objects.filter(organization=organization)
        .select_related('endpoint')
        .order_by('-created_at')[:limit]
    )
    payload = []
    for item in deliveries:
        payload.append(
            {
                'id': item.id,
                'endpoint_id': item.endpoint_id,
                'endpoint_name': item.endpoint.name if item.endpoint else '',
                'event_type': item.event_type,
                'status': item.status,
                'attempt_count': item.attempt_count,
                'max_attempts': item.max_attempts,
                'response_status': item.response_status,
                'error_message': item.error_message,
                'next_attempt_at': item.next_attempt_at.isoformat() if item.next_attempt_at else None,
                'dead_lettered_at': item.dead_lettered_at.isoformat() if item.dead_lettered_at else None,
                'created_at': item.created_at.isoformat() if item.created_at else None,
            }
        )
    return JsonResponse({'deliveries': payload})


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


@csrf_exempt
@require_http_methods(["POST"])
def esign_webhook_api(request):
    secret = str(getattr(settings, 'ESIGN_WEBHOOK_SECRET', '') or '').strip()
    if not secret:
        return _error_response(request, 'E-sign webhook secret is not configured.', 503)
    provided_secret = str(request.headers.get('X-Esign-Webhook-Secret', '') or '').strip()
    if not provided_secret or not secrets.compare_digest(secret, provided_secret):
        return _error_response(request, 'Invalid webhook secret.', 403)

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return _error_response(request, 'Invalid JSON body.', 400)
    events = payload if isinstance(payload, list) else [payload]
    if not all(isinstance(event, dict) for event in events):
        return _error_response(request, 'Events payload must be an object or list of objects.', 400)

    summary = {
        'total_events': len(events),
        'applied': 0,
        'duplicate': 0,
        'stale': 0,
        'errors': [],
    }
    for index, event in enumerate(events):
        signature_request = None
        signature_request_id = event.get('signature_request_id')
        external_id = str(event.get('external_id') or '').strip()
        if signature_request_id:
            signature_request = SignatureRequest.objects.filter(id=signature_request_id).first()
        if signature_request is None and external_id:
            signature_request = SignatureRequest.objects.filter(external_id=external_id).order_by('-id').first()
        if signature_request is None:
            summary['errors'].append({'index': index, 'error': 'Signature request not found.'})
            continue

        try:
            result = apply_esign_event(signature_request, event, dry_run=False)
        except ESignReconciliationError as exc:
            summary['errors'].append({'index': index, 'error': str(exc)})
            continue

        result_key = str(result.get('result') or '')
        if result_key in summary:
            summary[result_key] += 1
        else:
            summary['errors'].append({'index': index, 'error': f'Unknown reconciliation result: {result_key}'})

    return JsonResponse({'summary': summary})


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


# ── AI clause-span extraction ─────────────────────────────────────────────────

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



# ── Obligation (Deadline) CRUD API ────────────────────────────────────────────

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


# ---------------------------------------------------------------------------
# DSAR SLA API
# ---------------------------------------------------------------------------
from contracts.services.dsar import get_dsar_service


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


# ---------------------------------------------------------------------------
# Background Job Status API
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Feature 1: Document Versioning + Immutable History
# ---------------------------------------------------------------------------

from contracts.services.contract_versions import get_version_service
from contracts.models import ContractVersion


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


# ---------------------------------------------------------------------------
# Feature 2: AI-Assisted Drafting + Clause Recommendations
# ---------------------------------------------------------------------------

from contracts.services.ai_drafting import get_ai_drafting_service
from contracts.models import ClauseRecommendation


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


# ---------------------------------------------------------------------------
# Feature 3: Enterprise Admin Console
# ---------------------------------------------------------------------------

from contracts.services.admin_console import get_admin_console_service
from contracts.models import OrgPolicy


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


# ---------------------------------------------------------------------------
# Feature 4: Permission Transparency
# ---------------------------------------------------------------------------

from contracts.services.permissions import get_permission_service


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


# ---------------------------------------------------------------------------
# Feature 5: Self-Serve Onboarding
# ---------------------------------------------------------------------------

from contracts.services.onboarding import get_onboarding_service


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


# ---------------------------------------------------------------------------
# Feature 6: Billing + Subscription Controls
# ---------------------------------------------------------------------------

from contracts.services.billing import get_billing_service


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


# ---------------------------------------------------------------------------
# Feature 7: Compliance Portal
# ---------------------------------------------------------------------------

from contracts.services.compliance_portal import get_compliance_portal_service


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


# ---------------------------------------------------------------------------
# Feature 8: Approval Workflow API
# ---------------------------------------------------------------------------

from contracts.services.approval_workflow import get_approval_workflow_service


@login_required
@require_http_methods(['POST'])
def approval_initiate_api(request, contract_id):
    contract = get_object_or_404(Contract, pk=contract_id)
    svc = get_approval_workflow_service()
    requests_created = svc.initiate_approval_workflow(contract)
    return JsonResponse({
        'ok': True,
        'created': len(requests_created),
        'requests': [_approval_dto_to_dict(r) for r in requests_created],
    })


@login_required
@require_http_methods(['GET'])
def approval_contract_list_api(request, contract_id):
    contract = get_object_or_404(Contract, pk=contract_id)
    svc = get_approval_workflow_service()
    summary = svc.get_contract_approvals(contract)
    return JsonResponse({
        'contract_id': summary.contract_id,
        'all_approved': summary.all_approved,
        'any_rejected': summary.any_rejected,
        'any_pending': summary.any_pending,
        'requests': [_approval_dto_to_dict(r) for r in summary.requests],
    })


@login_required
@require_http_methods(['POST'])
def approval_approve_api(request, approval_id):
    data = json.loads(request.body or '{}')
    svc = get_approval_workflow_service()
    try:
        dto = svc.approve(approval_id, request.user, comments=data.get('comments', ''))
    except ApprovalRequest.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'ok': True, 'request': _approval_dto_to_dict(dto)})


@login_required
@require_http_methods(['POST'])
def approval_reject_api(request, approval_id):
    data = json.loads(request.body or '{}')
    svc = get_approval_workflow_service()
    try:
        dto = svc.reject(approval_id, request.user, comments=data.get('comments', ''))
    except ApprovalRequest.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
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
    svc = get_approval_workflow_service()
    try:
        dto = svc.delegate(approval_id, to_user, request.user)
    except ApprovalRequest.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'ok': True, 'request': _approval_dto_to_dict(dto)})


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


# ---------------------------------------------------------------------------
# Clause Analytics
# ---------------------------------------------------------------------------

from contracts.services.clause_analytics import get_clause_analytics_service
from contracts.services.mandatory_clauses import get_mandatory_enforcement_service
from contracts.services.playbook import get_playbook_service


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


# ---------------------------------------------------------------------------
# Mandatory Clause Enforcement
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Playbooks
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Area 1: Search & Analytics API
# ---------------------------------------------------------------------------
from contracts.services.search_api import (
    get_contract_search_service,
    get_clause_search_service,
)
from contracts.models import SearchTelemetryEvent


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


# ---------------------------------------------------------------------------
# Area 2: Privacy Ops
# ---------------------------------------------------------------------------
from contracts.services.subprocessor_alerts import get_subprocessor_alert_service
from contracts.services.retention_jobs import get_retention_service


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


# ---------------------------------------------------------------------------
# Area 3: Integrations
# ---------------------------------------------------------------------------
from contracts.services.webhook_management import get_webhook_management_service
from contracts.services.inbound_import import get_inbound_import_service
from contracts.services.crm_sync import get_crm_sync_service


@login_required
@require_http_methods(['GET'])
def api_webhook_failed(request):
    org = get_user_organization(request.user)
    svc = get_webhook_management_service()
    return JsonResponse({'deliveries': svc.get_failed_deliveries(org)})


@login_required
@require_http_methods(['POST'])
def api_webhook_retry(request, delivery_id):
    org = get_user_organization(request.user)
    svc = get_webhook_management_service()
    try:
        result = svc.retry_delivery(delivery_id, org)
        return JsonResponse(result)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=404)


@login_required
@require_http_methods(['GET'])
def api_webhook_dlq(request):
    org = get_user_organization(request.user)
    svc = get_webhook_management_service()
    return JsonResponse({'deliveries': svc.get_dead_letter_queue(org)})


@login_required
@require_http_methods(['GET'])
def api_webhook_diagnostics(request):
    org = get_user_organization(request.user)
    svc = get_webhook_management_service()
    return JsonResponse(svc.get_diagnostics(org))


@login_required
@require_http_methods(['POST'])
def api_webhook_requeue(request, delivery_id):
    org = get_user_organization(request.user)
    svc = get_webhook_management_service()
    try:
        result = svc.requeue_dead_letter(delivery_id, org)
        return JsonResponse(result)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=404)


@login_required
@require_http_methods(['POST'])
def api_import_contracts_csv(request):
    org = get_user_organization(request.user)
    svc = get_inbound_import_service()
    csv_text = request.body.decode('utf-8', errors='replace')
    dry_run = request.GET.get('dry_run', '').lower() in ('true', '1', 'yes')
    result = svc.import_contracts_from_csv(org, csv_text, request.user, dry_run=dry_run)
    return JsonResponse({
        'imported_count': result.imported_count,
        'skipped_count': result.skipped_count,
        'errors': result.errors,
        'dry_run': result.dry_run,
    })


@login_required
@require_http_methods(['POST'])
def api_import_contracts_json(request):
    org = get_user_organization(request.user)
    svc = get_inbound_import_service()
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, Exception):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    if not isinstance(data, list):
        return JsonResponse({'error': 'Expected a JSON array'}, status=400)
    dry_run = request.GET.get('dry_run', '').lower() in ('true', '1', 'yes')
    result = svc.import_contracts_from_json(org, data, request.user, dry_run=dry_run)
    return JsonResponse({
        'imported_count': result.imported_count,
        'skipped_count': result.skipped_count,
        'errors': result.errors,
        'dry_run': result.dry_run,
    })


@login_required
@require_http_methods(['GET'])
def api_crm_sync_status(request):
    org = get_user_organization(request.user)
    svc = get_crm_sync_service()
    return JsonResponse(svc.get_sync_status(org))


@login_required
@require_http_methods(['GET'])
def api_crm_list_integrations(request):
    org = get_user_organization(request.user)
    svc = get_crm_sync_service()
    return JsonResponse({'integrations': svc.list_available_integrations(org)})


@login_required
@require_http_methods(['POST'])
def api_crm_trigger_sync(request):
    org = get_user_organization(request.user)
    svc = get_crm_sync_service()
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, Exception):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    provider = data.get('provider', 'salesforce')
    try:
        result = svc.trigger_sync(org, provider, request.user)
        return JsonResponse(result)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)


# ---------------------------------------------------------------------------
# Area 4: Ops Hardening
# ---------------------------------------------------------------------------
from contracts.services.postgres_health import get_postgres_health_service
from contracts.services.cve_gate import get_cve_gate_service
from contracts.services.restore_drill import get_restore_drill_service
from contracts.models import RestoreDrill as _RestoreDrillModel


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
