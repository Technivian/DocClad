"""PAR-EXC-001 — canonical ExceptionRequest / ExceptionDecision service.

Governed write path for temporary exceptions, waivers, overrides, and risk
acceptances. Production legacy paths are not cut over here; callers must use
this service for new governed writes.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

EVENT_REQUEST_CREATED = 'exception.request.created'
EVENT_REQUEST_SUBMITTED = 'exception.request.submitted'
EVENT_DECISION_RECORDED = 'exception.decision.recorded'
EVENT_REQUEST_EXPIRED = 'exception.request.expired'
EVENT_REQUEST_RENEWED = 'exception.request.renewed'
EVENT_CROSS_TENANT_DENIED = 'exception.cross_tenant.denied'

IMMUTABLE_DECISION_FIELDS = frozenset({
    'exception_request_id',
    'organization_id',
    'outcome',
    'decided_by_id',
    'authority_basis',
    'authority_holder_id',
    'security_approval',
    'comments',
    'compensating_controls_at_decision',
    'granted_privileges_at_decision',
    'starts_at',
    'expires_at',
    'is_permanent_approved',
    'decided_at',
})

# Privilege tokens that may be granted only when listed on the ExceptionRequest
# at create/submit time. An APPROVED decision cannot invent new privileges.
KNOWN_PRIVILEGE_TOKENS = frozenset({
    'policy.deviation',
    'approval.defer_blocker',
    'workflow.bypass_step',
    'deadline.extend',
    'signature.alternate_path',
    'risk.accept',
    'audit.defer_finding',
    'repair.provenance',
    'feature.pilot_allow',
})


class ExceptionCanonicalError(ValidationError):
    """Raised when exception canonical rules are violated."""


def _assert_tenant_access(*, actor, organization_id: int | None) -> None:
    if actor is None or not getattr(actor, 'is_authenticated', False):
        return
    from contracts.tenancy import get_user_organization

    actor_org = get_user_organization(actor)
    actor_org_id = getattr(actor_org, 'pk', None)
    if organization_id and actor_org_id and organization_id != actor_org_id:
        from contracts.middleware import log_action

        log_action(
            actor,
            'VIEW',
            'ExceptionRequest',
            changes={
                'event': EVENT_CROSS_TENANT_DENIED,
                'attempted_organization_id': organization_id,
                'actor_organization_id': actor_org_id,
            },
            organization_id=actor_org_id,
            event_type=EVENT_CROSS_TENANT_DENIED,
            outcome='blocked',
        )
        raise PermissionDenied('Cross-tenant exception operations are prohibited.')


def _normalize_privileges(raw: list | tuple | None) -> list[str]:
    if not raw:
        return []
    privileges: list[str] = []
    for item in raw:
        token = str(item).strip()
        if not token:
            continue
        if token not in KNOWN_PRIVILEGE_TOKENS:
            raise ExceptionCanonicalError(
                f'Unknown privilege token "{token}". Exceptions cannot grant arbitrary privileges.'
            )
        if token not in privileges:
            privileges.append(token)
    return privileges


def _validate_window(*, starts_at, expires_at, is_permanent: bool) -> None:
    if starts_at is None:
        raise ExceptionCanonicalError('Every exception requires starts_at.')
    if is_permanent:
        return
    if expires_at is None:
        raise ExceptionCanonicalError(
            'Temporary exceptions require expires_at (exceptions are temporary unless '
            'explicitly approved as permanent).'
        )
    if expires_at <= starts_at:
        raise ExceptionCanonicalError('expires_at must be after starts_at.')


def exception_is_applicable(exception_request, *, at=None) -> bool:
    """Server-side applicability — UI visibility is not authorization."""
    return exception_request.is_temporally_applicable(at=at)


@transaction.atomic
def create_exception_request(
    *,
    organization,
    category: str,
    title: str,
    reason: str,
    scope_type: str,
    owner,
    actor=None,
    requester=None,
    scope_object_model: str = '',
    scope_object_id: int | None = None,
    scope_reference: dict | None = None,
    contract=None,
    authority_basis: str = 'legacy_unknown',
    authority_reference: dict | None = None,
    designated_approver=None,
    risk_classification: str = 'MEDIUM',
    bypasses_critical_security_control: bool = False,
    compensating_controls: str = '',
    granted_privileges: list | None = None,
    is_permanent: bool = False,
    starts_at=None,
    expires_at=None,
    legacy_source: str = '',
    legacy_reference: dict | None = None,
    submit: bool = False,
    request=None,
) -> object:
    """Create an ExceptionRequest. Does not grant effect until APPROVED/ACTIVE."""
    from contracts.models import ExceptionRequest
    from contracts.middleware import log_action

    org_id = getattr(organization, 'pk', None)
    _assert_tenant_access(actor=actor, organization_id=org_id)

    if owner is None:
        raise ExceptionCanonicalError('Every exception requires an owner.')
    if not (reason or '').strip():
        raise ExceptionCanonicalError('Every exception requires a reason.')
    if not (title or '').strip():
        raise ExceptionCanonicalError('Every exception requires a title.')

    if contract is not None and getattr(contract, 'organization_id', None) != org_id:
        raise PermissionDenied('Cross-tenant exception scope is prohibited.')

    start = starts_at or timezone.now()
    privileges = _normalize_privileges(granted_privileges)
    _validate_window(starts_at=start, expires_at=expires_at, is_permanent=is_permanent)

    if bypasses_critical_security_control and risk_classification != ExceptionRequest.RiskClassification.CRITICAL:
        risk_classification = ExceptionRequest.RiskClassification.CRITICAL

    status = ExceptionRequest.Status.SUBMITTED if submit else ExceptionRequest.Status.DRAFT
    exception = ExceptionRequest.objects.create(
        organization_id=org_id,
        category=category,
        title=title.strip(),
        reason=reason.strip(),
        scope_type=scope_type,
        scope_object_model=(scope_object_model or '').strip(),
        scope_object_id=scope_object_id,
        scope_reference=scope_reference or {},
        contract=contract,
        requester=requester or actor,
        owner=owner,
        authority_basis=authority_basis,
        authority_reference=authority_reference or {},
        designated_approver=designated_approver,
        risk_classification=risk_classification,
        bypasses_critical_security_control=bypasses_critical_security_control,
        compensating_controls=(compensating_controls or '').strip(),
        granted_privileges=privileges,
        is_permanent=is_permanent,
        starts_at=start,
        expires_at=expires_at,
        status=status,
        legacy_source=legacy_source or '',
        legacy_reference=legacy_reference or {},
    )

    event = EVENT_REQUEST_SUBMITTED if submit else EVENT_REQUEST_CREATED
    log_action(
        actor,
        'CREATE',
        'ExceptionRequest',
        object_id=exception.pk,
        object_repr=exception.title,
        changes={
            'event': event,
            'category': exception.category,
            'scope_type': exception.scope_type,
            'scope_object_id': exception.scope_object_id,
            'owner_id': exception.owner_id,
            'authority_basis': exception.authority_basis,
            'risk_classification': exception.risk_classification,
            'bypasses_critical_security_control': exception.bypasses_critical_security_control,
            'granted_privileges': exception.granted_privileges,
            'starts_at': exception.starts_at.isoformat() if exception.starts_at else None,
            'expires_at': exception.expires_at.isoformat() if exception.expires_at else None,
            'is_permanent': exception.is_permanent,
            'status': exception.status,
        },
        request=request,
        organization=organization,
        event_type=event,
    )
    return exception


def _actor_may_decide(*, exception, actor, security_approval: bool) -> None:
    """Server-side decision authorization (UI visibility is not authorization)."""
    if actor is None or not getattr(actor, 'is_authenticated', False):
        raise PermissionDenied('Authenticated actor required to decide an exception.')

    from contracts.models import OrganizationMembership
    from contracts.tenancy import get_user_organization

    actor_org = get_user_organization(actor)
    if actor_org is None or actor_org.pk != exception.organization_id:
        raise PermissionDenied('Cross-tenant exception decisions are prohibited.')

    membership = OrganizationMembership.objects.filter(
        organization_id=exception.organization_id,
        user=actor,
        is_active=True,
    ).first()
    if membership is None:
        raise PermissionDenied('Actor is not an active member of the exception workspace.')

    if exception.bypasses_critical_security_control and not security_approval:
        raise ExceptionCanonicalError(
            'Critical security-control bypass requires explicit Security approval '
            '(security_approval=True on the decision).'
        )

    if exception.designated_approver_id and actor.pk != exception.designated_approver_id:
        # Designated approver is required when set; Security flag alone is insufficient
        # unless the designated approver is the security actor.
        if not (
            exception.bypasses_critical_security_control
            and security_approval
            and membership.role in {
                OrganizationMembership.Role.OWNER,
                OrganizationMembership.Role.ADMIN,
            }
        ):
            raise PermissionDenied('Only the designated approver may decide this exception.')

    # Owner/requester cannot silently self-approve their own exception.
    if actor.pk in {exception.owner_id, exception.requester_id}:
        if exception.bypasses_critical_security_control:
            raise PermissionDenied(
                'Critical security-control bypass cannot be self-approved by owner/requester.'
            )
        if exception.designated_approver_id != actor.pk:
            raise PermissionDenied(
                'Exception owner/requester cannot approve their own exception '
                'unless explicitly designated as approver.'
            )


@transaction.atomic
def record_exception_decision(
    exception_request,
    *,
    outcome: str,
    actor,
    comments: str = '',
    security_approval: bool = False,
    authority_basis: str | None = None,
    starts_at=None,
    expires_at=None,
    is_permanent_approved: bool = False,
    request=None,
) -> object:
    """Append an immutable ExceptionDecision and update request status."""
    from contracts.models import ExceptionDecision, ExceptionRequest
    from contracts.middleware import log_action

    exception = (
        ExceptionRequest.objects.select_for_update()
        .select_related('organization', 'owner', 'requester', 'designated_approver')
        .get(pk=exception_request.pk)
    )
    _assert_tenant_access(actor=actor, organization_id=exception.organization_id)
    _actor_may_decide(exception=exception, actor=actor, security_approval=security_approval)

    outcome = (outcome or '').upper().strip()
    valid = {c.value for c in ExceptionDecision.Outcome}
    if outcome not in valid:
        raise ExceptionCanonicalError(f'Invalid exception decision outcome: {outcome}')

    now = timezone.now()
    decision_starts = starts_at or exception.starts_at or now
    decision_expires = expires_at if expires_at is not None else exception.expires_at
    permanent = bool(is_permanent_approved or (exception.is_permanent and outcome == ExceptionDecision.Outcome.APPROVED))

    if outcome == ExceptionDecision.Outcome.APPROVED:
        _validate_window(starts_at=decision_starts, expires_at=decision_expires, is_permanent=permanent)
        if permanent and not is_permanent_approved:
            raise ExceptionCanonicalError(
                'Permanent exceptions require explicit is_permanent_approved=True on the decision.'
            )

    # Decisions cannot invent privileges beyond those declared on the request.
    privileges_snapshot = list(exception.granted_privileges or [])

    decision = ExceptionDecision.objects.create(
        organization_id=exception.organization_id,
        exception_request=exception,
        outcome=outcome,
        decided_by=actor,
        authority_basis=authority_basis or exception.authority_basis,
        authority_holder_id=getattr(actor, 'pk', None),
        security_approval=bool(security_approval),
        comments=(comments or '').strip(),
        compensating_controls_at_decision=exception.compensating_controls or '',
        granted_privileges_at_decision=privileges_snapshot,
        starts_at=decision_starts if outcome == ExceptionDecision.Outcome.APPROVED else None,
        expires_at=decision_expires if outcome == ExceptionDecision.Outcome.APPROVED else None,
        is_permanent_approved=permanent if outcome == ExceptionDecision.Outcome.APPROVED else False,
        decided_at=now,
    )

    updates: list[str] = ['status', 'updated_at']
    if outcome == ExceptionDecision.Outcome.APPROVED:
        exception.status = ExceptionRequest.Status.ACTIVE
        exception.starts_at = decision_starts
        exception.expires_at = None if permanent else decision_expires
        exception.is_permanent = permanent
        updates.extend(['starts_at', 'expires_at', 'is_permanent'])
    elif outcome == ExceptionDecision.Outcome.REJECTED:
        exception.status = ExceptionRequest.Status.REJECTED
        exception.closed_at = now
        updates.append('closed_at')
    elif outcome == ExceptionDecision.Outcome.REVOKED:
        exception.status = ExceptionRequest.Status.REVOKED
        exception.closed_at = now
        updates.append('closed_at')
    elif outcome == ExceptionDecision.Outcome.CLOSED:
        exception.status = ExceptionRequest.Status.CLOSED
        exception.closed_at = now
        exception.closure_notes = (comments or '').strip()
        updates.extend(['closed_at', 'closure_notes'])
    elif outcome == ExceptionDecision.Outcome.EXPIRED_RECORDED:
        exception.status = ExceptionRequest.Status.EXPIRED
        exception.closed_at = now
        updates.append('closed_at')
    elif outcome == ExceptionDecision.Outcome.RENEWED:
        exception.status = ExceptionRequest.Status.SUPERSEDED
        exception.closed_at = now
        updates.append('closed_at')

    exception.save(update_fields=updates)

    log_action(
        actor,
        'APPROVE' if outcome == ExceptionDecision.Outcome.APPROVED else 'UPDATE',
        'ExceptionDecision',
        object_id=decision.pk,
        object_repr=f'{outcome}:{exception.pk}',
        changes={
            'event': EVENT_DECISION_RECORDED,
            'exception_request_id': exception.pk,
            'outcome': outcome,
            'authority_basis': decision.authority_basis,
            'security_approval': decision.security_approval,
            'granted_privileges': privileges_snapshot,
            'starts_at': decision.starts_at.isoformat() if decision.starts_at else None,
            'expires_at': decision.expires_at.isoformat() if decision.expires_at else None,
            'is_permanent_approved': decision.is_permanent_approved,
            'request_status': exception.status,
        },
        request=request,
        organization_id=exception.organization_id,
        event_type=EVENT_DECISION_RECORDED,
    )
    return decision


@transaction.atomic
def renew_exception(
    prior_exception,
    *,
    actor,
    owner=None,
    reason: str = '',
    starts_at=None,
    expires_at=None,
    compensating_controls: str | None = None,
    designated_approver=None,
    request=None,
) -> object:
    """Renewal creates a new ExceptionRequest; prior is superseded only after approval.

    Returns the new SUBMITTED ExceptionRequest. Call record_exception_decision on both
    the new approval and prior RENEWED/SUPERSEDED as authorized.
    """
    from contracts.models import ExceptionRequest

    prior = ExceptionRequest.objects.select_for_update().get(pk=prior_exception.pk)
    _assert_tenant_access(actor=actor, organization_id=prior.organization_id)

    if prior.status not in {
        ExceptionRequest.Status.ACTIVE,
        ExceptionRequest.Status.APPROVED,
        ExceptionRequest.Status.EXPIRED,
    }:
        raise ExceptionCanonicalError('Only active, approved, or expired exceptions may be renewed.')

    start = starts_at or timezone.now()
    new_expiry = expires_at
    if new_expiry is None and not prior.is_permanent:
        # Default renewal window: prior duration, or 30 days.
        if prior.expires_at and prior.starts_at:
            delta = prior.expires_at - prior.starts_at
            new_expiry = start + delta
        else:
            from datetime import timedelta

            new_expiry = start + timedelta(days=30)

    renewed = create_exception_request(
        organization=prior.organization,
        category=prior.category,
        title=prior.title,
        reason=(reason or prior.reason).strip(),
        scope_type=prior.scope_type,
        owner=owner or prior.owner,
        actor=actor,
        requester=actor,
        scope_object_model=prior.scope_object_model,
        scope_object_id=prior.scope_object_id,
        scope_reference=dict(prior.scope_reference or {}),
        contract=prior.contract,
        authority_basis=prior.authority_basis,
        authority_reference=dict(prior.authority_reference or {}),
        designated_approver=designated_approver or prior.designated_approver,
        risk_classification=prior.risk_classification,
        bypasses_critical_security_control=prior.bypasses_critical_security_control,
        compensating_controls=(
            compensating_controls
            if compensating_controls is not None
            else prior.compensating_controls
        ),
        granted_privileges=list(prior.granted_privileges or []),
        is_permanent=False,
        starts_at=start,
        expires_at=new_expiry,
        legacy_source=prior.legacy_source,
        legacy_reference={
            **(prior.legacy_reference or {}),
            'renewed_from_id': prior.pk,
        },
        submit=True,
        request=request,
    )
    renewed.renewed_from = prior
    renewed.save(update_fields=['renewed_from', 'updated_at'])

    from contracts.middleware import log_action

    log_action(
        actor,
        'CREATE',
        'ExceptionRequest',
        object_id=renewed.pk,
        object_repr=renewed.title,
        changes={
            'event': EVENT_REQUEST_RENEWED,
            'renewed_from_id': prior.pk,
            'new_exception_id': renewed.pk,
        },
        request=request,
        organization_id=prior.organization_id,
        event_type=EVENT_REQUEST_RENEWED,
    )
    return renewed


@transaction.atomic
def mark_exception_expired_if_due(exception_request, *, actor=None, request=None) -> object | None:
    """Record expiry when the window has passed. Expired exceptions stop applying.

    Does not require designated-approver authority — expiry is a temporal fact.
    """
    from contracts.models import ExceptionDecision, ExceptionRequest
    from contracts.middleware import log_action

    exception = ExceptionRequest.objects.select_for_update().get(pk=exception_request.pk)
    if exception.status not in {ExceptionRequest.Status.ACTIVE, ExceptionRequest.Status.APPROVED}:
        return None
    if exception.is_permanent:
        return None
    now = timezone.now()
    if exception.expires_at is None or exception.expires_at > now:
        return None

    # Temporal applicability already false; persist EXPIRED + immutable decision.
    decision = ExceptionDecision.objects.create(
        organization_id=exception.organization_id,
        exception_request=exception,
        outcome=ExceptionDecision.Outcome.EXPIRED_RECORDED,
        decided_by=actor,
        authority_basis='temporal_expiry',
        authority_holder_id=getattr(actor, 'pk', None),
        security_approval=False,
        comments='Automatic expiry — exception no longer applicable.',
        compensating_controls_at_decision=exception.compensating_controls or '',
        granted_privileges_at_decision=list(exception.granted_privileges or []),
        decided_at=now,
    )
    exception.status = ExceptionRequest.Status.EXPIRED
    exception.closed_at = now
    exception.save(update_fields=['status', 'closed_at', 'updated_at'])
    log_action(
        actor,
        'UPDATE',
        'ExceptionDecision',
        object_id=decision.pk,
        object_repr=f'EXPIRED_RECORDED:{exception.pk}',
        changes={
            'event': EVENT_REQUEST_EXPIRED,
            'exception_request_id': exception.pk,
            'expires_at': exception.expires_at.isoformat() if exception.expires_at else None,
        },
        request=request,
        organization_id=exception.organization_id,
        event_type=EVENT_REQUEST_EXPIRED,
    )
    return decision


def privilege_granted(exception_request, privilege_token: str, *, at=None) -> bool:
    """Return True only when the exception is applicable and lists the privilege."""
    if privilege_token not in KNOWN_PRIVILEGE_TOKENS:
        return False
    if not exception_is_applicable(exception_request, at=at):
        return False
    return privilege_token in (exception_request.granted_privileges or [])
