"""PAR-ID-001 — additive Role Definition catalogue (ADR-0014 Accepted; migration 0112).

This service manages catalogue rows only. It does **not** change:
- OrganizationMembership authority
- UserProfile.role runtime behaviour
- approval / workflow / signer resolution
- navigation visibility
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

EVENT_CREATED = 'role.definition.created'
EVENT_UPDATED = 'role.definition.updated'
EVENT_DEACTIVATED = 'role.definition.deactivated'
EVENT_REPAIRED = 'role.definition.repaired'

IMMUTABLE_ROLE_DEFINITION_FIELDS = frozenset({
    'code',
    'organization_id',
})

# Truthful legacy → RoleDefinition.code mappings.
# Ambiguous values map to LEGACY_UNKNOWN codes; never merge ADMIN meanings.
LEGACY_LABEL_MAP: dict[tuple[str, str], str] = {
    # Workspace membership
    ('membership_role', 'OWNER'): 'workspace_owner',
    ('membership_role', 'ADMIN'): 'workspace_admin',
    ('membership_role', 'MEMBER'): 'workspace_member',
    # UserProfile.Role — process labels (ADMIN is ambiguous → legacy_process_admin)
    ('profile_role', 'PARTNER'): 'partner_reviewer',
    ('profile_role', 'SENIOR_ASSOCIATE'): 'senior_reviewer',
    ('profile_role', 'ASSOCIATE'): 'legal_reviewer',
    ('profile_role', 'PARALEGAL'): 'paralegal_reviewer',
    ('profile_role', 'LEGAL_ASSISTANT'): 'legal_assistant',
    ('profile_role', 'CLIENT'): 'external_participant',
    ('profile_role', 'ADMIN'): 'legacy_process_admin',
    # Approval steps
    ('approval_step', 'LEGAL'): 'legal_reviewer',
    ('approval_step', 'FINANCE'): 'finance_approver',
    ('approval_step', 'PRIVACY'): 'privacy_reviewer',
    ('approval_step', 'EXECUTIVE'): 'executive_approver',
    ('approval_step', 'COMPLIANCE'): 'compliance_reviewer',
    # Signer display (auth remains email-based; catalogue label only)
    ('signer_role_label', 'SIGNER'): 'signer',
}

CANONICAL_SEEDS: tuple[dict[str, Any], ...] = (
    {'code': 'workspace_owner', 'name': 'Workspace Owner', 'category': 'WORKSPACE',
     'description': 'Organization owner — workspace administration.'},
    {'code': 'workspace_admin', 'name': 'Workspace Admin', 'category': 'WORKSPACE',
     'description': 'Organization admin — configuration and elevated operations.'},
    {'code': 'workspace_member', 'name': 'Workspace Member', 'category': 'WORKSPACE',
     'description': 'Organization member — base workspace access.'},
    {'code': 'requester', 'name': 'Requester', 'category': 'WORKFLOW',
     'description': 'Process requester for a contract or workflow instance.'},
    {'code': 'contract_owner', 'name': 'Contract Owner', 'category': 'WORKFLOW',
     'description': 'Accountable contract owner.'},
    {'code': 'legal_reviewer', 'name': 'Legal Reviewer', 'category': 'APPROVAL',
     'description': 'Legal review / approval process role.'},
    {'code': 'senior_reviewer', 'name': 'Senior Reviewer', 'category': 'APPROVAL',
     'description': 'Senior legal review process role.'},
    {'code': 'partner_reviewer', 'name': 'Partner Reviewer', 'category': 'APPROVAL',
     'description': 'Partner-level review process role.'},
    {'code': 'paralegal_reviewer', 'name': 'Paralegal Reviewer', 'category': 'WORKFLOW',
     'description': 'Paralegal process role.'},
    {'code': 'legal_assistant', 'name': 'Legal Assistant', 'category': 'WORKFLOW',
     'description': 'Legal assistant process role.'},
    {'code': 'finance_approver', 'name': 'Finance Approver', 'category': 'APPROVAL',
     'description': 'Finance approval process role.'},
    {'code': 'privacy_reviewer', 'name': 'Privacy Reviewer', 'category': 'APPROVAL',
     'description': 'Privacy review process role.'},
    {'code': 'executive_approver', 'name': 'Executive Approver', 'category': 'APPROVAL',
     'description': 'Executive approval process role.'},
    {'code': 'compliance_reviewer', 'name': 'Compliance Reviewer', 'category': 'APPROVAL',
     'description': 'Compliance review process role.'},
    {'code': 'signer', 'name': 'Signer', 'category': 'SIGNATURE',
     'description': 'Signature process role (display catalogue; auth remains email-based).'},
    {'code': 'archiver', 'name': 'Archiver', 'category': 'WORKFLOW',
     'description': 'Archival process role.'},
    {'code': 'external_participant', 'name': 'External Participant', 'category': 'WORKFLOW',
     'description': 'External / client participant process role.'},
    {'code': 'system_actor', 'name': 'System Actor', 'category': 'SYSTEM',
     'description': 'Explicit system principal for background jobs and migrations.'},
    {'code': 'legacy_process_admin', 'name': 'Legacy Process Admin (ambiguous)', 'category': 'LEGACY_UNKNOWN',
     'description': 'Maps UserProfile.Role.ADMIN — NOT workspace ADMIN. Semantics uncertain.'},
    {'code': 'legacy_unknown', 'name': 'Legacy Unknown', 'category': 'LEGACY_UNKNOWN',
     'description': 'Catch-all for unmapped historical role labels.'},
)


class RoleDefinitionError(ValidationError):
    """Raised when Role Definition catalogue rules are violated."""


def assert_role_definition_immutable(instance, *, previous: dict) -> None:
    if previous.get('code') != getattr(instance, 'code', None):
        raise RoleDefinitionError('RoleDefinition.code is immutable after creation.')
    if previous.get('organization_id') != getattr(instance, 'organization_id', None):
        raise RoleDefinitionError('RoleDefinition.organization is immutable after creation.')
    if previous.get('is_system_managed') and previous.get('category') != getattr(instance, 'category', None):
        raise RoleDefinitionError(
            'System-managed RoleDefinition.category cannot be changed without governed repair.'
        )


def _assert_catalogue_manager(*, actor, organization) -> None:
    from contracts.permissions import can_manage_organization

    if actor is None or not getattr(actor, 'is_authenticated', False):
        raise PermissionDenied('Authentication required for Role Definition catalogue management.')
    if organization is None:
        raise PermissionDenied('Organization is required.')
    if not can_manage_organization(actor, organization):
        raise PermissionDenied('Only organization OWNER or ADMIN may manage Role Definitions.')


def _assert_tenant(*, actor, organization) -> None:
    if actor is None or not getattr(actor, 'is_authenticated', False):
        return
    from contracts.tenancy import get_user_organization

    actor_org = get_user_organization(actor)
    if actor_org is None or organization is None or actor_org.pk != organization.pk:
        raise PermissionDenied('Cross-tenant Role Definition operations are forbidden.')


def _audit(*, actor, organization, event_type, role_definition, changes: dict | None = None) -> None:
    from contracts.middleware import log_action
    from contracts.models import AuditLog

    log_action(
        actor if getattr(actor, 'is_authenticated', False) else None,
        AuditLog.Action.UPDATE,
        'RoleDefinition',
        object_id=getattr(role_definition, 'pk', None),
        object_repr=f'RoleDefinition {getattr(role_definition, "code", "")}',
        organization=organization,
        event_type=event_type,
        changes=changes or {},
    )


@transaction.atomic
def create_role_definition(
    *,
    organization,
    code: str,
    name: str,
    category: str,
    description: str = '',
    is_system_managed: bool = False,
    actor=None,
    skip_authz: bool = False,
):
    from contracts.models import RoleDefinition

    if not skip_authz:
        _assert_tenant(actor=actor, organization=organization)
        _assert_catalogue_manager(actor=actor, organization=organization)
    code = (code or '').strip()
    name = (name or '').strip()
    if not code or not name:
        raise RoleDefinitionError('code and name are required.')
    if category not in RoleDefinition.Category.values:
        raise RoleDefinitionError(f'Invalid category: {category}')
    if RoleDefinition.objects.filter(organization=organization, code=code).exists():
        raise RoleDefinitionError(f'RoleDefinition code "{code}" already exists for this organization.')

    role = RoleDefinition(
        organization=organization,
        code=code,
        name=name,
        description=description or '',
        category=category,
        is_active=True,
        is_system_managed=is_system_managed,
        created_by=actor if getattr(actor, 'is_authenticated', False) else None,
        updated_by=actor if getattr(actor, 'is_authenticated', False) else None,
    )
    role.save(skip_role_definition_immutability=True)
    _audit(
        actor=actor,
        organization=organization,
        event_type=EVENT_CREATED,
        role_definition=role,
        changes={'code': code, 'category': category, 'system_managed': is_system_managed},
    )
    return role


@transaction.atomic
def update_role_definition(
    role_definition,
    *,
    actor,
    name: str | None = None,
    description: str | None = None,
    skip_authz: bool = False,
):
    if not skip_authz:
        _assert_tenant(actor=actor, organization=role_definition.organization)
        _assert_catalogue_manager(actor=actor, organization=role_definition.organization)

    changes: dict[str, Any] = {}
    if name is not None:
        name = name.strip()
        if not name:
            raise RoleDefinitionError('name cannot be empty.')
        if role_definition.is_system_managed and name != role_definition.name:
            # Allow display rename of system-managed rows for UX, but record as update.
            pass
        changes['name'] = {'from': role_definition.name, 'to': name}
        role_definition.name = name
    if description is not None:
        changes['description'] = {'from': role_definition.description, 'to': description}
        role_definition.description = description
    if not changes:
        return role_definition
    role_definition.updated_by = actor if getattr(actor, 'is_authenticated', False) else None
    role_definition.save()
    _audit(
        actor=actor,
        organization=role_definition.organization,
        event_type=EVENT_UPDATED,
        role_definition=role_definition,
        changes=changes,
    )
    return role_definition


@transaction.atomic
def deactivate_role_definition(role_definition, *, actor, skip_authz: bool = False):
    if not skip_authz:
        _assert_tenant(actor=actor, organization=role_definition.organization)
        _assert_catalogue_manager(actor=actor, organization=role_definition.organization)
    if role_definition.is_system_managed:
        raise RoleDefinitionError(
            'System-managed Role Definitions cannot be deactivated without governed repair.'
        )
    if not role_definition.is_active:
        return role_definition
    role_definition.is_active = False
    role_definition.updated_by = actor if getattr(actor, 'is_authenticated', False) else None
    role_definition.save()
    _audit(
        actor=actor,
        organization=role_definition.organization,
        event_type=EVENT_DEACTIVATED,
        role_definition=role_definition,
        changes={'is_active': False},
    )
    return role_definition


@transaction.atomic
def repair_role_definition(
    role_definition,
    *,
    actor,
    is_active: bool | None = None,
    name: str | None = None,
    description: str | None = None,
    skip_authz: bool = False,
):
    """Governed repair for system-managed rows (OWNER/ADMIN only)."""
    if not skip_authz:
        _assert_tenant(actor=actor, organization=role_definition.organization)
        _assert_catalogue_manager(actor=actor, organization=role_definition.organization)
    changes: dict[str, Any] = {}
    if is_active is not None and is_active != role_definition.is_active:
        changes['is_active'] = {'from': role_definition.is_active, 'to': is_active}
        role_definition.is_active = is_active
    if name is not None:
        name = name.strip()
        if name and name != role_definition.name:
            changes['name'] = {'from': role_definition.name, 'to': name}
            role_definition.name = name
    if description is not None and description != role_definition.description:
        changes['description'] = {'from': role_definition.description, 'to': description}
        role_definition.description = description
    if not changes:
        return role_definition
    role_definition.updated_by = actor if getattr(actor, 'is_authenticated', False) else None
    role_definition.save()
    _audit(
        actor=actor,
        organization=role_definition.organization,
        event_type=EVENT_REPAIRED,
        role_definition=role_definition,
        changes=changes,
    )
    return role_definition


def lookup_role_definition(organization, *, source_system: str, source_value: str, active_only: bool = True):
    """Compatibility lookup: map legacy label → RoleDefinition without privilege dual-write.

    Does not alter UserProfile.role, membership, or any resolver.
    """
    from contracts.models import RoleDefinition

    if organization is None:
        return None
    key = ((source_system or '').strip(), (source_value or '').strip().upper())
    # Normalize: source_value for profile/membership stored uppercase
    code = LEGACY_LABEL_MAP.get(key)
    if code is None:
        # Try original case for source_system keys that aren't uppercased values
        key_raw = ((source_system or '').strip(), (source_value or '').strip())
        code = LEGACY_LABEL_MAP.get(key_raw)
    if code is None:
        code = 'legacy_unknown'
    qs = RoleDefinition.objects.filter(organization=organization, code=code)
    if active_only:
        qs = qs.filter(is_active=True)
    return qs.first()


def ensure_canonical_role_definitions(organization, *, actor=None) -> list:
    """Idempotently seed canonical Role Definitions for an organization."""
    from contracts.models import RoleDefinition

    created = []
    for seed in CANONICAL_SEEDS:
        existing = RoleDefinition.objects.filter(organization=organization, code=seed['code']).first()
        if existing:
            continue
        role = create_role_definition(
            organization=organization,
            code=seed['code'],
            name=seed['name'],
            category=seed['category'],
            description=seed['description'],
            is_system_managed=True,
            actor=actor,
            skip_authz=True,
        )
        created.append(role)
    return created
