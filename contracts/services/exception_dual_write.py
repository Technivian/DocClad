"""PAR-EXC-001 — priority-path dual-write adapters (legacy authoritative).

Creates canonical ExceptionRequest / ExceptionDecision mirrors for six
authorized source paths. Canonical rows are non-authoritative until a later
read-path cutover. Flags default OFF.
"""

from __future__ import annotations

import logging
import uuid
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from contracts.services.exception_canonical import (
    EVENT_CROSS_TENANT_DENIED,
    EVENT_DECISION_RECORDED,
    EVENT_REQUEST_CREATED,
    EVENT_REQUEST_SUBMITTED,
    ExceptionCanonicalError,
    KNOWN_PRIVILEGE_TOKENS,
    _normalize_privileges,
    _validate_window,
    exception_is_applicable,
)

logger = logging.getLogger(__name__)

EVENT_ACTIVATED = 'exception.activated'
EVENT_EXPIRED = 'exception.expired'
EVENT_REVOKED = 'exception.revoked'
EVENT_RENEWED = 'exception.renewed'
EVENT_CLOSED = 'exception.closed'
EVENT_DUAL_WRITE_FAILED = 'exception.dual_write_failed'
EVENT_SECURITY_GATE_BLOCKED = 'exception.security_gate_blocked'

SOURCE_KEEP_EXCEPTION = 'KEEP_EXCEPTION'
SOURCE_ACCEPTED_RISK = 'ACCEPTED_RISK'
SOURCE_AI_EXCEPTION = 'AI_EXCEPTION'
SOURCE_CONFLICT_CHECK_WAIVER = 'CONFLICT_CHECK_WAIVER'
SOURCE_DEADLINE_DEFER = 'DEADLINE_DEFER'
SOURCE_DPA_APPROVE_WITH_BLOCKERS = 'DPA_APPROVE_WITH_BLOCKERS'

AUTHORIZED_SOURCES = frozenset({
    SOURCE_KEEP_EXCEPTION,
    SOURCE_ACCEPTED_RISK,
    SOURCE_AI_EXCEPTION,
    SOURCE_CONFLICT_CHECK_WAIVER,
    SOURCE_DEADLINE_DEFER,
    SOURCE_DPA_APPROVE_WITH_BLOCKERS,
})

# Outcome tokens for mirrored decisions (truthful mapping only).
OUTCOME_APPROVED = 'APPROVED'
OUTCOME_REJECTED = 'REJECTED'
OUTCOME_REVOKED = 'REVOKED'
OUTCOME_NONE = 'NONE'  # request only (e.g. AI exception requested)
OUTCOME_LEGACY_UNKNOWN = 'LEGACY_UNKNOWN'


class ExceptionDualWriteError(ExceptionCanonicalError):
    """Fail-closed dual-write errors (tenant / Critical / privilege)."""


class ExceptionDualWriteSkip(Exception):
    """Non-fatal: dual-write not enabled or not applicable."""


def dual_write_enabled_for_org(organization) -> bool:
    if not getattr(settings, 'EXCEPTION_DUAL_WRITE_ENABLED', False):
        return False
    raw = getattr(settings, 'EXCEPTION_DUAL_WRITE_ORG_ALLOWLIST', '') or ''
    allow = {s.strip() for s in raw.split(',') if s.strip()}
    if not allow:
        return False
    slug = getattr(organization, 'slug', None) or ''
    return slug in allow


def build_correlation_id(*, source: str, object_model: str, object_id: int | str, suffix: str = '') -> str:
    base = f'{source}:{object_model}:{object_id}'
    if suffix:
        return f'{base}:{suffix}'
    return base


def _emit_failure(
    *,
    actor,
    organization=None,
    organization_id=None,
    source: str,
    correlation_id: str,
    classification: str,
    detail: str,
    request=None,
    fail_closed: bool = False,
):
    from contracts.middleware import log_action
    from contracts.models import AuditLog

    log_action(
        actor,
        AuditLog.Action.UPDATE,
        'ExceptionRequest',
        changes={
            'event': EVENT_DUAL_WRITE_FAILED,
            'source': source,
            'correlation_id': correlation_id,
            'failure_classification': classification,
            # Intentionally omit restricted contract/identity content.
            'detail': (detail or '')[:240],
        },
        request=request,
        organization=organization,
        organization_id=organization_id,
        event_type=EVENT_DUAL_WRITE_FAILED,
        outcome=AuditLog.Outcome.FAILURE if not fail_closed else AuditLog.Outcome.BLOCKED,
    )


def _category_for_source(source: str) -> str:
    from contracts.models import ExceptionRequest

    return {
        SOURCE_KEEP_EXCEPTION: ExceptionRequest.ExceptionCategory.POLICY,
        SOURCE_ACCEPTED_RISK: ExceptionRequest.ExceptionCategory.RISK_ACCEPTANCE,
        SOURCE_AI_EXCEPTION: ExceptionRequest.ExceptionCategory.POLICY,
        SOURCE_CONFLICT_CHECK_WAIVER: ExceptionRequest.ExceptionCategory.POLICY,
        SOURCE_DEADLINE_DEFER: ExceptionRequest.ExceptionCategory.DEADLINE,
        SOURCE_DPA_APPROVE_WITH_BLOCKERS: ExceptionRequest.ExceptionCategory.APPROVAL,
    }.get(source, ExceptionRequest.ExceptionCategory.OTHER)


def _scope_for_source(source: str) -> str:
    from contracts.models import ExceptionRequest

    return {
        SOURCE_KEEP_EXCEPTION: ExceptionRequest.ScopeType.RISK_SIGNAL,
        SOURCE_ACCEPTED_RISK: ExceptionRequest.ScopeType.DPA_RISK_ITEM,
        SOURCE_AI_EXCEPTION: ExceptionRequest.ScopeType.REVIEW_FINDING,
        SOURCE_CONFLICT_CHECK_WAIVER: ExceptionRequest.ScopeType.CONFLICT_CHECK,
        SOURCE_DEADLINE_DEFER: ExceptionRequest.ScopeType.DEADLINE,
        SOURCE_DPA_APPROVE_WITH_BLOCKERS: ExceptionRequest.ScopeType.CONTRACT,
    }.get(source, ExceptionRequest.ScopeType.OTHER)


def _default_expiry(*, source: str, starts_at, explicit_expires_at=None):
    if explicit_expires_at is not None:
        return explicit_expires_at
    days = {
        SOURCE_KEEP_EXCEPTION: 90,
        SOURCE_ACCEPTED_RISK: 90,
        SOURCE_AI_EXCEPTION: 30,
        SOURCE_CONFLICT_CHECK_WAIVER: 180,
        SOURCE_DEADLINE_DEFER: 7,
        SOURCE_DPA_APPROVE_WITH_BLOCKERS: 30,
    }.get(source, 30)
    return starts_at + timedelta(days=days)


@transaction.atomic
def mirror_legacy_exception(
    *,
    source: str,
    organization,
    actor,
    owner,
    title: str,
    reason: str,
    scope_object_model: str,
    scope_object_id: int,
    correlation_id: str,
    outcome: str,
    contract=None,
    scope_reference: dict | None = None,
    authority_basis: str = 'policy_owner',
    compensating_controls: str = '',
    granted_privileges: list | None = None,
    risk_classification: str = 'MEDIUM',
    bypasses_critical_security_control: bool = False,
    security_approval: bool = False,
    starts_at=None,
    expires_at=None,
    request=None,
) -> tuple[object | None, object | None]:
    """Mirror a legacy exception action into canonical rows.

    Returns (ExceptionRequest|None, ExceptionDecision|None).
    Legacy remains authoritative. Raises ExceptionDualWriteError for fail-closed
    cases; ordinary failures are audited and return (None, None).
    """
    from contracts.models import ExceptionDecision, ExceptionRequest
    from contracts.middleware import log_action
    from contracts.tenancy import get_user_organization

    if source not in AUTHORIZED_SOURCES:
        raise ExceptionDualWriteError(f'Unauthorized dual-write source: {source}')

    if organization is None:
        raise ExceptionDualWriteError('organization is required for dual-write')

    if not dual_write_enabled_for_org(organization):
        raise ExceptionDualWriteSkip('dual-write disabled for organization')

    # Tenant isolation — fail closed.
    if actor is not None and getattr(actor, 'is_authenticated', False):
        actor_org = get_user_organization(actor)
        if actor_org is not None and actor_org.pk != organization.pk:
            _emit_failure(
                actor=actor,
                organization=actor_org,
                source=source,
                correlation_id=correlation_id,
                classification='cross_tenant',
                detail='actor organization mismatch',
                request=request,
                fail_closed=True,
            )
            log_action(
                actor,
                'VIEW',
                'ExceptionRequest',
                changes={
                    'event': EVENT_CROSS_TENANT_DENIED,
                    'source': source,
                    'correlation_id': correlation_id,
                },
                organization=actor_org,
                event_type=EVENT_CROSS_TENANT_DENIED,
                outcome='blocked',
                request=request,
            )
            raise ExceptionDualWriteError('Cross-tenant exception dual-write is prohibited.')

    if contract is not None and getattr(contract, 'organization_id', None) not in {None, organization.pk}:
        _emit_failure(
            actor=actor,
            organization=organization,
            source=source,
            correlation_id=correlation_id,
            classification='cross_tenant',
            detail='contract organization mismatch',
            request=request,
            fail_closed=True,
        )
        raise ExceptionDualWriteError('Cross-tenant exception scope is prohibited.')

    if owner is None:
        _emit_failure(
            actor=actor,
            organization=organization,
            source=source,
            correlation_id=correlation_id,
            classification='missing_owner',
            detail='owner required',
            request=request,
            fail_closed=True,
        )
        raise ExceptionDualWriteError('Every mirrored exception requires an owner.')

    if not (reason or '').strip():
        _emit_failure(
            actor=actor,
            organization=organization,
            source=source,
            correlation_id=correlation_id,
            classification='missing_reason',
            detail='reason required',
            request=request,
            fail_closed=True,
        )
        raise ExceptionDualWriteError('Every mirrored exception requires a reason.')

    try:
        privileges = _normalize_privileges(granted_privileges)
    except ExceptionCanonicalError as exc:
        _emit_failure(
            actor=actor,
            organization=organization,
            source=source,
            correlation_id=correlation_id,
            classification='malformed_privilege',
            detail=str(exc),
            request=request,
            fail_closed=True,
        )
        raise ExceptionDualWriteError(str(exc)) from exc

    if bypasses_critical_security_control and not security_approval:
        log_action(
            actor,
            'UPDATE',
            'ExceptionRequest',
            changes={
                'event': EVENT_SECURITY_GATE_BLOCKED,
                'source': source,
                'correlation_id': correlation_id,
            },
            organization=organization,
            event_type=EVENT_SECURITY_GATE_BLOCKED,
            outcome='blocked',
            request=request,
        )
        _emit_failure(
            actor=actor,
            organization=organization,
            source=source,
            correlation_id=correlation_id,
            classification='critical_without_security',
            detail='Critical bypass requires security_approval',
            request=request,
            fail_closed=True,
        )
        raise ExceptionDualWriteError(
            'Critical security-control bypass requires explicit Security approval.'
        )

    # Idempotency: same correlation_id + source → return existing.
    existing = ExceptionRequest.objects.filter(
        organization=organization,
        legacy_source=source,
        correlation_id=correlation_id,
    ).order_by('pk').first()
    if existing is not None:
        decision = existing.decisions.order_by('pk').first()
        return existing, decision

    start = starts_at or timezone.now()
    expiry = _default_expiry(source=source, starts_at=start, explicit_expires_at=expires_at)
    try:
        _validate_window(starts_at=start, expires_at=expiry, is_permanent=False)
    except ExceptionCanonicalError as exc:
        _emit_failure(
            actor=actor,
            organization=organization,
            source=source,
            correlation_id=correlation_id,
            classification='invalid_window',
            detail=str(exc),
            request=request,
        )
        return None, None

    risk = risk_classification
    if bypasses_critical_security_control:
        risk = ExceptionRequest.RiskClassification.CRITICAL

    try:
        exception = ExceptionRequest.objects.create(
            organization=organization,
            category=_category_for_source(source),
            title=(title or source)[:255],
            reason=reason.strip(),
            scope_type=_scope_for_source(source),
            scope_object_model=scope_object_model,
            scope_object_id=int(scope_object_id),
            scope_reference=scope_reference or {},
            contract=contract,
            requester=actor,
            owner=owner,
            authority_basis=authority_basis,
            authority_reference={'dual_write': True, 'source': source},
            designated_approver=actor,
            risk_classification=risk,
            bypasses_critical_security_control=bypasses_critical_security_control,
            compensating_controls=(compensating_controls or '').strip()
            or 'Legacy path remains authoritative; review at expiry.',
            granted_privileges=privileges,
            is_permanent=False,
            starts_at=start,
            expires_at=expiry,
            status=ExceptionRequest.Status.SUBMITTED,
            legacy_source=source,
            correlation_id=correlation_id,
            legacy_reference={
                'correlation_id': correlation_id,
                'dual_write': True,
                'outcome': outcome,
            },
        )
    except Exception as exc:  # noqa: BLE001 — preserve legacy; audit failure
        logger.exception('exception dual-write create failed source=%s', source)
        _emit_failure(
            actor=actor,
            organization=organization,
            source=source,
            correlation_id=correlation_id,
            classification='create_failed',
            detail=exc.__class__.__name__,
            request=request,
        )
        return None, None

    log_action(
        actor,
        'CREATE',
        'ExceptionRequest',
        object_id=exception.pk,
        object_repr=exception.title,
        changes={
            'event': EVENT_REQUEST_SUBMITTED,
            'source': source,
            'correlation_id': correlation_id,
            'legacy_authoritative': True,
        },
        request=request,
        organization=organization,
        event_type=EVENT_REQUEST_SUBMITTED,
    )

    decision = None
    if outcome == OUTCOME_APPROVED:
        try:
            decision = ExceptionDecision.objects.create(
                organization_id=organization.pk,
                exception_request=exception,
                outcome=ExceptionDecision.Outcome.APPROVED,
                decided_by=actor,
                authority_basis=authority_basis,
                authority_holder_id=getattr(actor, 'pk', None),
                security_approval=bool(security_approval),
                comments='Mirrored from legacy authoritative path (dual-write).',
                compensating_controls_at_decision=exception.compensating_controls,
                granted_privileges_at_decision=list(privileges),
                starts_at=start,
                expires_at=expiry,
                is_permanent_approved=False,
                decided_at=timezone.now(),
            )
            exception.status = ExceptionRequest.Status.ACTIVE
            exception.save(update_fields=['status', 'updated_at'])
            log_action(
                actor,
                'APPROVE',
                'ExceptionDecision',
                object_id=decision.pk,
                object_repr=f'APPROVED:{exception.pk}',
                changes={
                    'event': EVENT_DECISION_RECORDED,
                    'source': source,
                    'correlation_id': correlation_id,
                    'outcome': OUTCOME_APPROVED,
                },
                request=request,
                organization=organization,
                event_type=EVENT_DECISION_RECORDED,
            )
            log_action(
                actor,
                'UPDATE',
                'ExceptionRequest',
                object_id=exception.pk,
                object_repr=exception.title,
                changes={
                    'event': EVENT_ACTIVATED,
                    'source': source,
                    'correlation_id': correlation_id,
                    'expires_at': expiry.isoformat() if expiry else None,
                },
                request=request,
                organization=organization,
                event_type=EVENT_ACTIVATED,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception('exception dual-write decision failed source=%s', source)
            _emit_failure(
                actor=actor,
                organization=organization,
                source=source,
                correlation_id=correlation_id,
                classification='decision_failed',
                detail=exc.__class__.__name__,
                request=request,
            )
            return exception, None
    elif outcome == OUTCOME_REJECTED:
        decision = ExceptionDecision.objects.create(
            organization_id=organization.pk,
            exception_request=exception,
            outcome=ExceptionDecision.Outcome.REJECTED,
            decided_by=actor,
            authority_basis=authority_basis,
            authority_holder_id=getattr(actor, 'pk', None),
            security_approval=False,
            comments='Mirrored rejection from legacy path.',
            decided_at=timezone.now(),
        )
        exception.status = ExceptionRequest.Status.REJECTED
        exception.closed_at = timezone.now()
        exception.save(update_fields=['status', 'closed_at', 'updated_at'])
        log_action(
            actor,
            'UPDATE',
            'ExceptionDecision',
            object_id=decision.pk,
            object_repr=f'REJECTED:{exception.pk}',
            changes={
                'event': EVENT_DECISION_RECORDED,
                'source': source,
                'correlation_id': correlation_id,
                'outcome': OUTCOME_REJECTED,
            },
            request=request,
            organization=organization,
            event_type=EVENT_DECISION_RECORDED,
        )
    elif outcome == OUTCOME_REVOKED:
        decision = ExceptionDecision.objects.create(
            organization_id=organization.pk,
            exception_request=exception,
            outcome=ExceptionDecision.Outcome.REVOKED,
            decided_by=actor,
            authority_basis=authority_basis,
            authority_holder_id=getattr(actor, 'pk', None),
            decided_at=timezone.now(),
        )
        exception.status = ExceptionRequest.Status.REVOKED
        exception.closed_at = timezone.now()
        exception.save(update_fields=['status', 'closed_at', 'updated_at'])
        log_action(
            actor,
            'UPDATE',
            'ExceptionDecision',
            object_id=decision.pk,
            object_repr=f'REVOKED:{exception.pk}',
            changes={
                'event': EVENT_REVOKED,
                'source': source,
                'correlation_id': correlation_id,
            },
            request=request,
            organization=organization,
            event_type=EVENT_REVOKED,
        )
    elif outcome in {OUTCOME_NONE, OUTCOME_LEGACY_UNKNOWN}:
        # Request recorded; no approval decision invented.
        log_action(
            actor,
            'CREATE',
            'ExceptionRequest',
            object_id=exception.pk,
            object_repr=exception.title,
            changes={
                'event': EVENT_REQUEST_CREATED,
                'source': source,
                'correlation_id': correlation_id,
                'outcome': outcome,
            },
            request=request,
            organization=organization,
            event_type=EVENT_REQUEST_CREATED,
        )

    return exception, decision


def safe_mirror_legacy_exception(**kwargs) -> tuple[object | None, object | None]:
    """Call mirror_legacy_exception; swallow ordinary failures; re-raise fail-closed."""
    try:
        return mirror_legacy_exception(**kwargs)
    except ExceptionDualWriteSkip:
        return None, None
    except ExceptionDualWriteError:
        raise
    except Exception:  # noqa: BLE001
        logger.exception('unexpected exception dual-write failure')
        org = kwargs.get('organization')
        _emit_failure(
            actor=kwargs.get('actor'),
            organization=org,
            source=kwargs.get('source', ''),
            correlation_id=kwargs.get('correlation_id', ''),
            classification='unexpected',
            detail='unexpected',
            request=kwargs.get('request'),
        )
        return None, None


def parity_legacy_applies_after_canonical_expiry(exception_request) -> bool:
    """True when canonical is expired/inapplicable but legacy path may still apply.

    Used for pilot evidence only — legacy remains authoritative in this slice.
    """
    return not exception_is_applicable(exception_request)
