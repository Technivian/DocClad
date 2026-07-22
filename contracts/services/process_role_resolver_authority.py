"""PAR-ID-001 — feature-flagged canonical resolver authority (default off).

When PROCESS_ROLE_CANONICAL_RESOLVER_ENABLED is on for an allowlisted
organization, eligible CERTAIN non-ADMIN process roles on approved resolver
paths may return canonical ProcessRoleAssignment users. Legacy remains the
fallback for exclusions, missing/inactive assignments, ambiguous mappings,
and canonical failures. Cross-tenant anomalies fail closed (no cross-tenant
fallback). Activation is separately governed; this module defaults off.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from django.conf import settings
from django.utils import timezone

from contracts.services.process_role_assignment import resolve_legacy_process_role_code

logger = logging.getLogger(__name__)

EVENT_CANONICAL_USED = 'role.resolver.canonical_used'
EVENT_LEGACY_FALLBACK = 'role.resolver.legacy_fallback'
EVENT_CUTOVER_EXCLUDED = 'role.resolver.cutover_excluded'
EVENT_CANONICAL_FAILURE = 'role.resolver.canonical_failure'
EVENT_CROSS_TENANT = 'role.resolver.cross_tenant_anomaly'

REASON_FLAG_OFF = 'authority_flag_off'
REASON_ORG_NOT_ALLOWLISTED = 'organization_not_allowlisted'
REASON_EXCLUDED_PROFILE_ADMIN = 'excluded_profile_admin'
REASON_EXCLUDED_WORKSPACE_ROLE = 'excluded_workspace_role'
REASON_EXCLUDED_AMBIGUOUS = 'excluded_ambiguous_mapping'
REASON_EXCLUDED_LEGACY_UNKNOWN = 'excluded_legacy_unknown'
REASON_MISSING_ASSIGNMENT = 'missing_assignment'
REASON_INACTIVE_ASSIGNMENT = 'inactive_assignment'
REASON_CANONICAL_ERROR = 'canonical_resolution_error'
REASON_ORG_MISSING = 'organization_missing'
REASON_ORG_MISMATCH = 'organization_mismatch'
REASON_CROSS_TENANT = 'cross_tenant_anomaly'
REASON_EMPTY_ROLE = 'empty_role_label'
REASON_CANONICAL_USED = 'canonical_assignment_active'

WORKSPACE_ROLE_VALUES = frozenset({'OWNER', 'ADMIN', 'MEMBER'})
PROHIBITED_CODES = frozenset({
    'legacy_process_admin',
    'legacy_unknown',
    'workspace_owner',
    'workspace_admin',
    'workspace_member',
})


def canonical_resolver_enabled() -> bool:
    return bool(getattr(settings, 'PROCESS_ROLE_CANONICAL_RESOLVER_ENABLED', False))


def canonical_resolver_org_allowlist() -> set[str]:
    raw = getattr(settings, 'PROCESS_ROLE_CANONICAL_RESOLVER_ORG_ALLOWLIST', '') or ''
    return {part.strip() for part in str(raw).split(',') if part.strip()}


def organization_authority_allowed(organization) -> bool:
    if organization is None:
        return False
    allowlist = canonical_resolver_org_allowlist()
    if not allowlist:
        # Empty allowlist: no org receives canonical authority (fail-safe).
        return False
    slug = getattr(organization, 'slug', '') or ''
    return slug in allowlist


def _permission_safe_evidence(
    *,
    organization_id,
    resolver_type: str,
    path: str,
    reason: str,
    correlation_id,
    criticality: str,
) -> dict[str, Any]:
    return {
        'organization_id': organization_id,
        'resolver_type': resolver_type,
        'path': path,
        'reason': reason,
        'correlation_id': str(correlation_id),
        'criticality': criticality,
        'timestamp': timezone.now().isoformat(),
        'authoritative_for_runtime': path == 'canonical',
    }


def _emit(*, organization, event_type: str, evidence: dict[str, Any]) -> None:
    try:
        from contracts.middleware import log_action
        from contracts.models import AuditLog

        log_action(
            None,
            AuditLog.Action.UPDATE,
            'ProcessRoleResolverAuthority',
            object_id=None,
            object_repr=(
                f"resolver_authority {evidence.get('resolver_type')} "
                f"{evidence.get('path')} {evidence.get('reason')}"
            ),
            organization=organization,
            event_type=event_type,
            changes=evidence,
        )
    except Exception:
        logger.exception('resolver authority audit failed')


def _select_canonical_user(user_ids: set[int], legacy_user):
    from django.contrib.auth import get_user_model

    if not user_ids:
        return None
    legacy_id = getattr(legacy_user, 'pk', None)
    if legacy_id is not None and legacy_id in user_ids:
        return legacy_user
    User = get_user_model()
    return User.objects.filter(pk__in=sorted(user_ids)).order_by('pk').first()


def apply_canonical_authority(
    *,
    legacy_user,
    organization,
    role_label: str,
    resolver_type: str,
    source_organization=None,
):
    """Return canonical user when authorized; otherwise legacy (or None on cross-tenant).

    Never raises to callers. Does not enable diagnostic flags.
    """
    correlation_id = uuid.uuid4()

    if not canonical_resolver_enabled():
        return legacy_user

    org = organization
    try:
        if org is None:
            evidence = _permission_safe_evidence(
                organization_id=None,
                resolver_type=resolver_type,
                path='legacy',
                reason=REASON_ORG_MISSING,
                correlation_id=correlation_id,
                criticality='info',
            )
            # No org to attach audit; still fall back to legacy.
            return legacy_user

        if not organization_authority_allowed(org):
            evidence = _permission_safe_evidence(
                organization_id=getattr(org, 'pk', None),
                resolver_type=resolver_type,
                path='legacy',
                reason=REASON_ORG_NOT_ALLOWLISTED,
                correlation_id=correlation_id,
                criticality='info',
            )
            _emit(organization=org, event_type=EVENT_LEGACY_FALLBACK, evidence=evidence)
            return legacy_user

        # Cross-tenant: fail closed — never return a user across tenants.
        if (
            source_organization is not None
            and getattr(source_organization, 'pk', None) is not None
            and getattr(source_organization, 'pk', None) != getattr(org, 'pk', None)
        ):
            evidence = _permission_safe_evidence(
                organization_id=getattr(org, 'pk', None),
                resolver_type=resolver_type,
                path='blocked',
                reason=REASON_CROSS_TENANT,
                correlation_id=correlation_id,
                criticality='critical',
            )
            _emit(organization=org, event_type=EVENT_CROSS_TENANT, evidence=evidence)
            return None

        label = (role_label or '').strip().upper()
        if not label:
            evidence = _permission_safe_evidence(
                organization_id=getattr(org, 'pk', None),
                resolver_type=resolver_type,
                path='legacy',
                reason=REASON_EMPTY_ROLE,
                correlation_id=correlation_id,
                criticality='info',
            )
            _emit(organization=org, event_type=EVENT_LEGACY_FALLBACK, evidence=evidence)
            return legacy_user

        # Workspace roles and profile ADMIN are never canonical authority targets.
        if label in WORKSPACE_ROLE_VALUES:
            reason = (
                REASON_EXCLUDED_PROFILE_ADMIN
                if label == 'ADMIN'
                else REASON_EXCLUDED_WORKSPACE_ROLE
            )
            evidence = _permission_safe_evidence(
                organization_id=getattr(org, 'pk', None),
                resolver_type=resolver_type,
                path='legacy',
                reason=reason,
                correlation_id=correlation_id,
                criticality='info',
            )
            _emit(organization=org, event_type=EVENT_CUTOVER_EXCLUDED, evidence=evidence)
            return legacy_user

        code, confidence = resolve_legacy_process_role_code('profile_role', label)
        if confidence != 'CERTAIN' or code in PROHIBITED_CODES or code.startswith('workspace_'):
            if confidence == 'AMBIGUOUS' or code == 'legacy_process_admin':
                reason = REASON_EXCLUDED_AMBIGUOUS
            elif code in PROHIBITED_CODES or code.startswith('workspace_'):
                reason = REASON_EXCLUDED_LEGACY_UNKNOWN
            else:
                reason = REASON_EXCLUDED_AMBIGUOUS
            evidence = _permission_safe_evidence(
                organization_id=getattr(org, 'pk', None),
                resolver_type=resolver_type,
                path='legacy',
                reason=reason,
                correlation_id=correlation_id,
                criticality='info',
            )
            _emit(organization=org, event_type=EVENT_CUTOVER_EXCLUDED, evidence=evidence)
            return legacy_user

        from contracts.models import ProcessRoleAssignment, RoleDefinition

        role_def = RoleDefinition.objects.filter(
            organization=org, code=code, is_active=True,
        ).first()
        if role_def is None:
            evidence = _permission_safe_evidence(
                organization_id=getattr(org, 'pk', None),
                resolver_type=resolver_type,
                path='legacy',
                reason=REASON_MISSING_ASSIGNMENT,
                correlation_id=correlation_id,
                criticality='info',
            )
            _emit(organization=org, event_type=EVENT_LEGACY_FALLBACK, evidence=evidence)
            return legacy_user

        active_ids = set(
            ProcessRoleAssignment.objects.filter(
                organization=org,
                role_definition=role_def,
                is_active=True,
            ).values_list('user_id', flat=True)
        )
        if not active_ids:
            inactive_exists = ProcessRoleAssignment.objects.filter(
                organization=org,
                role_definition=role_def,
                is_active=False,
            ).exists()
            reason = REASON_INACTIVE_ASSIGNMENT if inactive_exists else REASON_MISSING_ASSIGNMENT
            evidence = _permission_safe_evidence(
                organization_id=getattr(org, 'pk', None),
                resolver_type=resolver_type,
                path='legacy',
                reason=reason,
                correlation_id=correlation_id,
                criticality='info',
            )
            _emit(organization=org, event_type=EVENT_LEGACY_FALLBACK, evidence=evidence)
            return legacy_user

        canonical_user = _select_canonical_user(active_ids, legacy_user)
        if canonical_user is None:
            evidence = _permission_safe_evidence(
                organization_id=getattr(org, 'pk', None),
                resolver_type=resolver_type,
                path='legacy',
                reason=REASON_MISSING_ASSIGNMENT,
                correlation_id=correlation_id,
                criticality='info',
            )
            _emit(organization=org, event_type=EVENT_LEGACY_FALLBACK, evidence=evidence)
            return legacy_user

        evidence = _permission_safe_evidence(
            organization_id=getattr(org, 'pk', None),
            resolver_type=resolver_type,
            path='canonical',
            reason=REASON_CANONICAL_USED,
            correlation_id=correlation_id,
            criticality='info',
        )
        _emit(organization=org, event_type=EVENT_CANONICAL_USED, evidence=evidence)
        return canonical_user
    except Exception:
        logger.exception('canonical resolver authority failed')
        try:
            evidence = _permission_safe_evidence(
                organization_id=getattr(org, 'pk', None) if org is not None else None,
                resolver_type=resolver_type,
                path='legacy',
                reason=REASON_CANONICAL_ERROR,
                correlation_id=correlation_id,
                criticality='critical',
            )
            if org is not None:
                _emit(organization=org, event_type=EVENT_CANONICAL_FAILURE, evidence=evidence)
        except Exception:
            logger.exception('canonical failure audit failed')
        return legacy_user


def after_resolve_assignee(*, legacy_user, step, contract):
    organization = getattr(contract, 'organization', None)
    role_label = (getattr(step, 'assignee_role', None) or '').strip()
    template = getattr(step, 'template', None)
    source_org = getattr(template, 'organization', None) if template is not None else None
    # specific_assignee path: no role-based cutover; keep legacy
    if getattr(step, 'specific_assignee_id', None):
        return legacy_user
    return apply_canonical_authority(
        legacy_user=legacy_user,
        organization=organization,
        role_label=role_label,
        resolver_type='resolve_assignee',
        source_organization=source_org,
    )


def after_resolve_rule_assignee(*, legacy_user, rule, contract):
    organization = getattr(contract, 'organization', None) if contract is not None else None
    role_label = (getattr(rule, 'approver_role', None) or '').strip()
    source_org = getattr(rule, 'organization', None)
    if getattr(rule, 'specific_approver_id', None):
        return legacy_user
    return apply_canonical_authority(
        legacy_user=legacy_user,
        organization=organization,
        role_label=role_label,
        resolver_type='resolve_rule_assignee',
        source_organization=source_org,
    )
