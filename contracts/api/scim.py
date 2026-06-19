
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


