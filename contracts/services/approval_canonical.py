"""PAR-APR-001 — canonical Approval Requirement / Approval Decision service."""

from __future__ import annotations

from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

EVENT_REQUIREMENT_CREATED = 'approval.requirement.created'
EVENT_REQUIREMENT_INVALIDATED = 'approval.requirement.invalidated'
EVENT_DECISION_RECORDED = 'approval.decision.recorded'

IMMUTABLE_DECISION_FIELDS = frozenset({
    'requirement_id',
    'organization_id',
    'outcome',
    'decided_by_id',
    'authority_holder_id',
    'acting_under_delegation',
    'delegation_holder_id',
    'comments',
    'contract_status',
    'contract_lifecycle_stage',
    'document_version_id',
    'document_version_missing',
    'decided_at',
})


class ApprovalCanonicalError(ValidationError):
    """Raised when approval canonical rules are violated."""


def _assert_tenant_access(*, actor, organization_id: int | None) -> None:
    if actor is None or not getattr(actor, 'is_authenticated', False):
        return
    from contracts.tenancy import get_user_organization

    actor_org = get_user_organization(actor)
    actor_org_id = getattr(actor_org, 'pk', None)
    if organization_id and actor_org_id and organization_id != actor_org_id:
        raise PermissionDenied('Cross-tenant approval operations are forbidden.')


def resolve_contract_document_version(contract) -> tuple[object | None, bool]:
    """Return the primary DocumentVersion under evaluation for a contract, if any."""
    from contracts.models import Document, DocumentVersion
    from contracts.services.document_version_service import resolve_canonical_version

    if contract is None:
        return None, True
    doc = (
        contract.documents.filter(
            status__in=[Document.Status.FINAL, Document.Status.EXECUTED, Document.Status.DRAFT],
        )
        .order_by('-version', '-created_at')
        .first()
    )
    if doc is None:
        return None, True
    version = resolve_canonical_version(doc)
    if version is None:
        version = DocumentVersion.objects.filter(document_row_id=doc.pk).first()
    return version, version is None


def contract_state_snapshot(contract) -> dict[str, str]:
    return {
        'contract_status': getattr(contract, 'status', '') or '',
        'contract_lifecycle_stage': getattr(contract, 'lifecycle_stage', '') or '',
    }


@transaction.atomic
def create_approval_requirement(
    *,
    organization,
    contract,
    approval_step: str,
    assigned_to=None,
    rule=None,
    sort_order: int = 0,
    authority_basis: str = 'manual',
    authority_reference: dict | None = None,
    due_date=None,
    actor=None,
    legacy_request=None,
    request=None,
) -> object:
    """Create a canonical ApprovalRequirement and optionally link a legacy ApprovalRequest."""
    from contracts.models import ApprovalRequirement, AuditLog
    from contracts.middleware import log_action

    org_id = getattr(organization, 'pk', None) or getattr(contract, 'organization_id', None)
    _assert_tenant_access(actor=actor, organization_id=org_id)

    if legacy_request is not None and legacy_request.pk:
        existing = ApprovalRequirement.objects.filter(legacy_request_id=legacy_request.pk).first()
        if existing is not None:
            updates = []
            if existing.authority_basis == ApprovalRequirement.AuthorityBasis.LEGACY_UNKNOWN and authority_basis != 'legacy_unknown':
                existing.authority_basis = authority_basis
                updates.append('authority_basis')
            if authority_reference and existing.authority_reference != authority_reference:
                existing.authority_reference = authority_reference
                updates.append('authority_reference')
            if updates:
                existing.save(update_fields=[*updates, 'updated_at'])
            return existing

    document_version, document_version_missing = resolve_contract_document_version(contract)
    snap = contract_state_snapshot(contract)

    requirement = ApprovalRequirement.objects.create(
        organization_id=org_id,
        contract=contract,
        legacy_request=legacy_request,
        rule=rule,
        approval_step=approval_step,
        sort_order=sort_order,
        authority_basis=authority_basis,
        authority_reference=authority_reference or {},
        contract_status_at_open=snap['contract_status'],
        contract_lifecycle_stage_at_open=snap['contract_lifecycle_stage'],
        document_version=document_version,
        document_version_missing=document_version_missing,
        assigned_to=assigned_to,
        status=ApprovalRequirement.Status.OPEN,
        due_date=due_date,
        opened_by=actor,
    )

    log_action(
        actor,
        AuditLog.Action.CREATE,
        'ApprovalRequirement',
        requirement.pk,
        str(requirement)[:300],
        organization=organization,
        request=request,
        event_type=EVENT_REQUIREMENT_CREATED,
        changes={
            'event': EVENT_REQUIREMENT_CREATED,
            'contract_id': contract.pk,
            'approval_step': approval_step,
            'authority_basis': authority_basis,
            'document_version_id': getattr(document_version, 'pk', None),
            'document_version_missing': document_version_missing,
            'legacy_request_id': getattr(legacy_request, 'pk', None),
            **snap,
        },
    )
    return requirement


def _map_action_to_outcome(action: str) -> str:
    from contracts.models import ApprovalDecision

    mapping = {
        'approve': ApprovalDecision.Outcome.APPROVED,
        'reject': ApprovalDecision.Outcome.REJECTED,
        'request_changes': ApprovalDecision.Outcome.RETURNED,
    }
    if action not in mapping:
        raise ApprovalCanonicalError(f'Unsupported approval action: {action}')
    return mapping[action]


def _requirement_status_for_outcome(outcome: str) -> str:
    from contracts.models import ApprovalRequirement, ApprovalDecision

    if outcome == ApprovalDecision.Outcome.APPROVED:
        return ApprovalRequirement.Status.SATISFIED
    if outcome == ApprovalDecision.Outcome.REJECTED:
        return ApprovalRequirement.Status.REJECTED
    if outcome == ApprovalDecision.Outcome.RETURNED:
        return ApprovalRequirement.Status.RETURNED
    if outcome == ApprovalDecision.Outcome.REVOKED:
        return ApprovalRequirement.Status.INVALIDATED
    return ApprovalRequirement.Status.OPEN


@transaction.atomic
def record_approval_decision(
    requirement,
    *,
    action: str,
    actor,
    comments: str = '',
    request=None,
) -> object:
    """Append an immutable ApprovalDecision against a requirement."""
    from contracts.models import ApprovalDecision, ApprovalRequirement, AuditLog
    from contracts.middleware import log_action

    if requirement.status != ApprovalRequirement.Status.OPEN:
        raise ApprovalCanonicalError(
            f'Cannot record a decision on requirement in status {requirement.status}.'
        )

    outcome = _map_action_to_outcome(action)
    document_version, document_version_missing = resolve_contract_document_version(requirement.contract)
    snap = contract_state_snapshot(requirement.contract)

    acting_under_delegation = bool(
        requirement.delegated_to_id
        and actor
        and requirement.delegated_to_id == getattr(actor, 'pk', None)
        and requirement.assigned_to_id != getattr(actor, 'pk', None)
    )

    decision = ApprovalDecision.objects.create(
        organization_id=requirement.organization_id,
        requirement=requirement,
        outcome=outcome,
        decided_by=actor,
        authority_holder_id=requirement.assigned_to_id,
        acting_under_delegation=acting_under_delegation,
        delegation_holder_id=requirement.delegated_to_id if acting_under_delegation else None,
        comments=(comments or '').strip(),
        contract_status=snap['contract_status'],
        contract_lifecycle_stage=snap['contract_lifecycle_stage'],
        document_version=document_version,
        document_version_missing=document_version_missing,
        decided_at=timezone.now(),
    )

    requirement.status = _requirement_status_for_outcome(outcome)
    requirement.closed_at = timezone.now()
    requirement.save(update_fields=['status', 'closed_at', 'updated_at'])

    log_action(
        actor,
        AuditLog.Action.APPROVE if outcome == ApprovalDecision.Outcome.APPROVED else AuditLog.Action.UPDATE,
        'ApprovalDecision',
        decision.pk,
        str(decision)[:300],
        organization_id=requirement.organization_id,
        request=request,
        event_type=EVENT_DECISION_RECORDED,
        changes={
            'event': EVENT_DECISION_RECORDED,
            'requirement_id': requirement.pk,
            'contract_id': requirement.contract_id,
            'outcome': outcome,
            'document_version_id': getattr(document_version, 'pk', None),
            'document_version_missing': document_version_missing,
            'acting_under_delegation': acting_under_delegation,
            **snap,
        },
    )
    return decision


@transaction.atomic
def invalidate_open_requirements_for_contract(
    contract,
    *,
    reason: str,
    actor=None,
    document_version=None,
    request=None,
) -> int:
    """Invalidate open requirements when evaluated contract/document state changes materially."""
    from contracts.models import ApprovalDecision, ApprovalRequirement, AuditLog
    from contracts.middleware import log_action

    reason_text = (reason or '').strip()
    if not reason_text:
        raise ApprovalCanonicalError('An invalidation reason is required.')

    qs = ApprovalRequirement.objects.filter(
        contract=contract,
        status=ApprovalRequirement.Status.OPEN,
    )
    count = 0
    for requirement in qs.select_for_update():
        requirement.status = ApprovalRequirement.Status.INVALIDATED
        requirement.invalidation_reason = reason_text
        requirement.invalidated_at = timezone.now()
        requirement.closed_at = timezone.now()
        requirement.save(update_fields=[
            'status', 'invalidation_reason', 'invalidated_at', 'closed_at', 'updated_at',
        ])
        ApprovalDecision.objects.create(
            organization_id=requirement.organization_id,
            requirement=requirement,
            outcome=ApprovalDecision.Outcome.REVOKED,
            decided_by=actor,
            authority_holder_id=requirement.assigned_to_id,
            acting_under_delegation=False,
            comments=reason_text,
            contract_status=requirement.contract_status_at_open,
            contract_lifecycle_stage=requirement.contract_lifecycle_stage_at_open,
            document_version=document_version or requirement.document_version,
            document_version_missing=requirement.document_version_missing,
            decided_at=timezone.now(),
        )
        if requirement.legacy_request_id:
            from contracts.models import ApprovalRequest

            ApprovalRequest.objects.filter(pk=requirement.legacy_request_id).update(
                status=ApprovalRequest.Status.CHANGES_REQUESTED,
                comments=reason_text,
                decided_at=timezone.now(),
                decided_by_id=getattr(actor, 'pk', None),
            )
        log_action(
            actor,
            AuditLog.Action.UPDATE,
            'ApprovalRequirement',
            requirement.pk,
            str(requirement)[:300],
            organization_id=requirement.organization_id,
            request=request,
            event_type=EVENT_REQUIREMENT_INVALIDATED,
            changes={
                'event': EVENT_REQUIREMENT_INVALIDATED,
                'contract_id': contract.pk,
                'reason': reason_text,
                'document_version_id': getattr(document_version, 'pk', None),
            },
        )
        count += 1
    return count


def ensure_requirement_for_legacy_request(approval_request, *, actor=None) -> object | None:
    """Idempotently create a canonical requirement for an existing ApprovalRequest."""
    from contracts.models import ApprovalRequirement

    if not approval_request.pk:
        return None
    if hasattr(approval_request, 'canonical_requirement'):
        try:
            existing = approval_request.canonical_requirement
            if existing is not None:
                return existing
        except ApprovalRequirement.DoesNotExist:
            pass

    basis = 'rule' if approval_request.rule_id else 'legacy_unknown'
    status_map = {
        'PENDING': ApprovalRequirement.Status.OPEN,
        'ESCALATED': ApprovalRequirement.Status.OPEN,
        'APPROVED': ApprovalRequirement.Status.SATISFIED,
        'REJECTED': ApprovalRequirement.Status.REJECTED,
        'CHANGES_REQUESTED': ApprovalRequirement.Status.RETURNED,
    }
    from contracts.models import ApprovalRequirement as AR

    document_version, document_version_missing = resolve_contract_document_version(approval_request.contract)
    snap = contract_state_snapshot(approval_request.contract)

    requirement = AR.objects.create(
        organization_id=approval_request.organization_id or approval_request.contract.organization_id,
        contract=approval_request.contract,
        legacy_request=approval_request,
        rule=approval_request.rule,
        approval_step=approval_request.approval_step,
        sort_order=approval_request.sort_order,
        authority_basis=basis,
        authority_reference={'legacy_backfill': True},
        contract_status_at_open=snap['contract_status'],
        contract_lifecycle_stage_at_open=snap['contract_lifecycle_stage'],
        document_version=document_version,
        document_version_missing=document_version_missing,
        assigned_to=approval_request.assigned_to,
        delegated_to=approval_request.delegated_to,
        delegated_at=approval_request.delegated_at,
        delegation_reason=approval_request.delegation_reason or '',
        delegation_ends_at=approval_request.delegation_ends_at,
        status=status_map.get(approval_request.status, AR.Status.OPEN),
        due_date=approval_request.due_date,
        opened_at=approval_request.created_at,
        opened_by=approval_request.decided_by,
        closed_at=approval_request.decided_at,
    )
    return requirement


def decision_snapshot(decision) -> dict[str, Any]:
    return {
        'id': decision.pk,
        'requirement_id': decision.requirement_id,
        'outcome': decision.outcome,
        'document_version_id': decision.document_version_id,
        'document_version_missing': decision.document_version_missing,
        'decided_at': decision.decided_at.isoformat() if decision.decided_at else None,
    }
