"""PAR-ID-001 — feature-flagged resolver parity (comparison only).

Evaluates canonical ProcessRoleAssignment resolution beside selected legacy
resolvers. Always returns the legacy result unchanged. Never repairs, blocks,
or alters production behaviour.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from django.conf import settings
from django.utils import timezone

from contracts.services.process_role_assignment import resolve_legacy_process_role_code

logger = logging.getLogger(__name__)

EVENT_RESOLVER_PARITY = 'role.resolver.parity_compared'
EVENT_RESOLVER_CROSS_TENANT = 'role.resolver.cross_tenant_anomaly'
EVENT_RESOLVER_ERROR = 'role.resolver.parity_resolution_error'

CLASS_MATCH = 'MATCH'
CLASS_LEGACY_ONLY = 'LEGACY_ONLY'
CLASS_CANONICAL_ONLY = 'CANONICAL_ONLY'
CLASS_DIFFERENT_USER = 'DIFFERENT_USER'
CLASS_DIFFERENT_ROLE = 'DIFFERENT_ROLE'
CLASS_AMBIGUOUS = 'AMBIGUOUS'
CLASS_INACTIVE = 'INACTIVE_ASSIGNMENT'
CLASS_CROSS_TENANT = 'CROSS_TENANT_ANOMALY'
CLASS_ERROR = 'RESOLUTION_ERROR'

CRITICAL_CLASSES = frozenset({
    CLASS_DIFFERENT_USER,
    CLASS_CROSS_TENANT,
    CLASS_ERROR,
})

WORKSPACE_ROLE_VALUES = frozenset({'OWNER', 'ADMIN', 'MEMBER'})

# In-process staging counters (deterministic for tests / management command snapshot).
_STAGING_COUNTERS: dict[str, int] = {
    'total_comparisons': 0,
    CLASS_MATCH: 0,
    CLASS_LEGACY_ONLY: 0,
    CLASS_CANONICAL_ONLY: 0,
    CLASS_DIFFERENT_USER: 0,
    CLASS_DIFFERENT_ROLE: 0,
    CLASS_AMBIGUOUS: 0,
    CLASS_INACTIVE: 0,
    CLASS_CROSS_TENANT: 0,
    CLASS_ERROR: 0,
    'critical_drift': 0,
}


def resolver_parity_enabled() -> bool:
    return bool(getattr(settings, 'PROCESS_ROLE_RESOLVER_PARITY_ENABLED', False))


def reset_staging_counters() -> None:
    for key in list(_STAGING_COUNTERS.keys()):
        _STAGING_COUNTERS[key] = 0


def get_staging_counters() -> dict[str, int]:
    return dict(_STAGING_COUNTERS)


def _bump(classification: str) -> None:
    _STAGING_COUNTERS['total_comparisons'] += 1
    if classification in _STAGING_COUNTERS:
        _STAGING_COUNTERS[classification] += 1
    if classification in CRITICAL_CLASSES:
        _STAGING_COUNTERS['critical_drift'] += 1


def _permission_safe_evidence(
    *,
    organization_id,
    resolver_type: str,
    classification: str,
    correlation_id,
    legacy_present: bool,
    canonical_present: bool,
    criticality: str,
) -> dict[str, Any]:
    return {
        'organization_id': organization_id,
        'resolver_type': resolver_type,
        'classification': classification,
        'correlation_id': str(correlation_id),
        'legacy_result_present': bool(legacy_present),
        'canonical_result_present': bool(canonical_present),
        'criticality': criticality,
        'timestamp': timezone.now().isoformat(),
        'authoritative_for_runtime': False,
    }


def _emit_evidence(organization, evidence: dict[str, Any], *, event_type: str) -> None:
    try:
        from contracts.middleware import log_action
        from contracts.models import AuditLog

        log_action(
            None,
            AuditLog.Action.UPDATE,
            'ProcessRoleResolverParity',
            object_id=None,
            object_repr=f"resolver_parity {evidence.get('resolver_type')} {evidence.get('classification')}",
            organization=organization,
            event_type=event_type,
            changes=evidence,
        )
    except Exception:
        logger.exception('resolver parity audit failed')


def _canonical_users_for_role(*, organization, role_label: str) -> tuple[set[int], str, str, bool]:
    """Return (user_ids, mapped_code, confidence, inactive_match_exists).

    Never maps workspace membership roles as process targets.
    """
    from contracts.models import ProcessRoleAssignment, RoleDefinition

    label = (role_label or '').strip().upper()
    if not label:
        return set(), '', 'UNKNOWN', False
    if label in WORKSPACE_ROLE_VALUES and label != 'ADMIN':
        # OWNER/MEMBER are workspace-only; ADMIN is process AMBIGUOUS via profile_role map.
        # Membership OWNER/MEMBER must never become process targets.
        return set(), '', 'UNKNOWN', False

    code, confidence = resolve_legacy_process_role_code('profile_role', label)
    if code.startswith('workspace_'):
        return set(), code, confidence, False

    role_def = RoleDefinition.objects.filter(organization=organization, code=code).first()
    if role_def is None:
        return set(), code, confidence, False

    active = ProcessRoleAssignment.objects.filter(
        organization=organization,
        role_definition=role_def,
        is_active=True,
    ).values_list('user_id', flat=True)
    inactive_exists = ProcessRoleAssignment.objects.filter(
        organization=organization,
        role_definition=role_def,
        is_active=False,
    ).exists()
    return set(active), code, confidence, inactive_exists


def _classify(
    *,
    legacy_user,
    canonical_user_ids: set[int],
    confidence: str,
    inactive_exists: bool,
    cross_tenant: bool,
) -> str:
    if cross_tenant:
        return CLASS_CROSS_TENANT
    legacy_id = getattr(legacy_user, 'pk', None)
    legacy_present = legacy_id is not None
    canonical_present = bool(canonical_user_ids)

    if confidence == 'AMBIGUOUS' and (legacy_present or canonical_present):
        # Still compute mismatch classes first for stronger signals.
        if legacy_present and canonical_present and legacy_id not in canonical_user_ids:
            return CLASS_DIFFERENT_USER
        return CLASS_AMBIGUOUS

    if legacy_present and canonical_present:
        if legacy_id in canonical_user_ids:
            return CLASS_MATCH
        return CLASS_DIFFERENT_USER
    if legacy_present and not canonical_present:
        if inactive_exists:
            return CLASS_INACTIVE
        return CLASS_LEGACY_ONLY
    if not legacy_present and canonical_present:
        return CLASS_CANONICAL_ONLY
    # Neither present — treat as MATCH (both unresolved)
    if inactive_exists:
        return CLASS_INACTIVE
    return CLASS_MATCH


def compare_assignee_resolution(
    *,
    legacy_user,
    organization,
    role_label: str,
    resolver_type: str,
    source_organization=None,
) -> Any:
    """Compare then return legacy_user unchanged. Never raises to caller."""
    if not resolver_parity_enabled():
        return legacy_user

    correlation_id = uuid.uuid4()
    org = organization
    try:
        if org is None:
            _bump(CLASS_ERROR)
            return legacy_user

        # Fail closed diagnostically if rule/template org mismatches contract org.
        cross_tenant = False
        if (
            source_organization is not None
            and getattr(source_organization, 'pk', None) is not None
            and getattr(source_organization, 'pk', None) != getattr(org, 'pk', None)
        ):
            cross_tenant = True

        canonical_ids, mapped_code, confidence, inactive_exists = _canonical_users_for_role(
            organization=org, role_label=role_label,
        )

        # DIFFERENT_ROLE: legacy profile role maps to code A, but active assignments
        # for this user exist only under a different process code.
        classification = _classify(
            legacy_user=legacy_user,
            canonical_user_ids=canonical_ids,
            confidence=confidence,
            inactive_exists=inactive_exists,
            cross_tenant=cross_tenant,
        )
        if (
            classification in (CLASS_MATCH, CLASS_LEGACY_ONLY, CLASS_INACTIVE)
            and legacy_user is not None
            and mapped_code
            and confidence != 'AMBIGUOUS'
        ):
            from contracts.models import ProcessRoleAssignment

            other = ProcessRoleAssignment.objects.filter(
                organization=org,
                user=legacy_user,
                is_active=True,
            ).exclude(role_definition__code=mapped_code).exists()
            expected_present = legacy_user.pk in canonical_ids
            if other and not expected_present:
                classification = CLASS_DIFFERENT_ROLE

        criticality = 'critical' if classification in CRITICAL_CLASSES else 'info'
        evidence = _permission_safe_evidence(
            organization_id=getattr(org, 'pk', None),
            resolver_type=resolver_type,
            classification=classification,
            correlation_id=correlation_id,
            legacy_present=legacy_user is not None,
            canonical_present=bool(canonical_ids),
            criticality=criticality,
        )
        _bump(classification)

        event = EVENT_RESOLVER_PARITY
        if classification == CLASS_CROSS_TENANT:
            event = EVENT_RESOLVER_CROSS_TENANT
        elif classification == CLASS_ERROR:
            event = EVENT_RESOLVER_ERROR
        _emit_evidence(org, evidence, event_type=event)
    except Exception:
        logger.exception('resolver parity comparison failed')
        try:
            _bump(CLASS_ERROR)
            evidence = _permission_safe_evidence(
                organization_id=getattr(org, 'pk', None) if org is not None else None,
                resolver_type=resolver_type,
                classification=CLASS_ERROR,
                correlation_id=correlation_id,
                legacy_present=legacy_user is not None,
                canonical_present=False,
                criticality='critical',
            )
            if org is not None:
                _emit_evidence(org, evidence, event_type=EVENT_RESOLVER_ERROR)
        except Exception:
            logger.exception('resolver parity error audit failed')
    return legacy_user


def after_resolve_assignee(*, legacy_user, step, contract):
    organization = getattr(contract, 'organization', None)
    role_label = (getattr(step, 'assignee_role', None) or '').strip()
    template = getattr(step, 'template', None)
    source_org = getattr(template, 'organization', None) if template is not None else None
    return compare_assignee_resolution(
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
    return compare_assignee_resolution(
        legacy_user=legacy_user,
        organization=organization,
        role_label=role_label,
        resolver_type='resolve_rule_assignee',
        source_organization=source_org,
    )
