"""Canonical contract lifecycle transitions for record status and workflow stage.

Record status, workflow stage, and document state are three separate dimensions.
Pairing rules live in ``lifecycle_dimensions``; this module owns transition
graphs, activation, and audited writers.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from contracts.services.lifecycle_dimensions import (
    RECORD_STATUS_ACTIVE,
    RECORD_STATUS_ARCHIVED,
    RECORD_STATUS_CANCELLED,
    RECORD_STATUS_EXPIRED,
    RECORD_STATUS_IN_PROGRESS,
    RECORD_STATUS_TERMINATED,
    RECORD_TERMINAL_STATUSES,
    STAGE_APPROVAL,
    STAGE_DRAFTING,
    STAGE_EXECUTED,
    STAGE_INTAKE,
    STAGE_INTERNAL_REVIEW,
    STAGE_NEGOTIATION,
    STAGE_OBLIGATION_TRACKING,
    STAGE_RENEWAL,
    STAGE_SIGNATURE,
    DOC_STATE_EXECUTED,
    is_valid_status_stage_pair,
    validate_status_stage_pair,
)

logger = logging.getLogger(__name__)


CONTRACT_LIFECYCLE_TRANSITIONS = {
    STAGE_INTAKE: {STAGE_DRAFTING},
    STAGE_DRAFTING: {STAGE_INTERNAL_REVIEW},
    STAGE_INTERNAL_REVIEW: {STAGE_NEGOTIATION},
    STAGE_NEGOTIATION: {STAGE_APPROVAL},
    STAGE_APPROVAL: {STAGE_SIGNATURE},
    STAGE_SIGNATURE: {STAGE_EXECUTED, STAGE_OBLIGATION_TRACKING},
    STAGE_EXECUTED: {STAGE_OBLIGATION_TRACKING, STAGE_RENEWAL},
    STAGE_OBLIGATION_TRACKING: {STAGE_RENEWAL},
    STAGE_RENEWAL: {STAGE_DRAFTING},
}

TRACKED_CONTRACT_FIELDS = (
    'title',
    'content',
    'status',
    'lifecycle_stage',
    'contract_type',
    'counterparty',
    'paper_source',
    'value',
    'currency',
    'governing_law',
    'jurisdiction',
    'risk_level',
    'data_transfer_flag',
    'dpa_attached',
    'scc_attached',
    'start_date',
    'end_date',
    'renewal_date',
    'auto_renew',
    'notice_period_days',
    'termination_notice_date',
    'client_id',
    'matter_id',
    'owner_id',
)


def get_allowed_lifecycle_stages(current_stage):
    return CONTRACT_LIFECYCLE_TRANSITIONS.get(current_stage, set())


def can_transition_lifecycle_stage(contract, new_stage):
    if contract is None or not new_stage:
        return False

    current_stage = getattr(contract, 'lifecycle_stage', None)
    if new_stage == current_stage:
        return True
    if not get_allowed_lifecycle_stages(current_stage):
        return False
    if new_stage not in get_allowed_lifecycle_stages(current_stage):
        return False
    # Stage advances must remain compatible with current record status.
    status = getattr(contract, 'status', None)
    return is_valid_status_stage_pair(status, new_stage)


def _normalize_audit_value(value):
    if isinstance(value, (date,)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, 'pk'):
        return value.pk
    return value


def build_contract_audit_changes(before_contract, after_contract, tracked_fields=TRACKED_CONTRACT_FIELDS):
    if before_contract is None or after_contract is None:
        return {}

    changes = {}
    for field_name in tracked_fields:
        if field_name == 'content':
            before_content = getattr(before_contract, field_name, '') or ''
            after_content = getattr(after_contract, field_name, '') or ''
            if before_content != after_content:
                changes[field_name] = {
                    'before': {
                        'sha256': hashlib.sha256(before_content.encode('utf-8')).hexdigest(),
                        'length': len(before_content),
                    },
                    'after': {
                        'sha256': hashlib.sha256(after_content.encode('utf-8')).hexdigest(),
                        'length': len(after_content),
                    },
                }
            continue
        before_value = _normalize_audit_value(getattr(before_contract, field_name, None))
        after_value = _normalize_audit_value(getattr(after_contract, field_name, None))
        if before_value != after_value:
            changes[field_name] = {
                'before': before_value,
                'after': after_value,
            }
    return changes


def build_contract_lifecycle_guidance(contract, today=None):
    today = today or timezone.localdate()

    stage_guidance = {
        STAGE_INTAKE: ('Intake', 'Capture required fields and open drafting.', STAGE_DRAFTING),
        STAGE_DRAFTING: ('Drafting', 'Submit for review when the record is ready.', STAGE_INTERNAL_REVIEW),
        STAGE_INTERNAL_REVIEW: ('Internal review', 'Resolve reviewer feedback and move into negotiation.', STAGE_NEGOTIATION),
        STAGE_NEGOTIATION: ('Negotiation', 'Resolve open commercial and legal positions before approval.', STAGE_APPROVAL),
        STAGE_APPROVAL: ('Approval', 'Collect the required approvals before signature routing.', STAGE_SIGNATURE),
        STAGE_SIGNATURE: ('Signature', 'Track signatures and activate when the packet is complete.', STAGE_OBLIGATION_TRACKING),
        STAGE_EXECUTED: ('Executed', 'Confirm obligations and renewal dates for ongoing management.', STAGE_OBLIGATION_TRACKING),
        STAGE_OBLIGATION_TRACKING: ('Obligation tracking', 'Monitor obligations and prepare the next renewal decision.', STAGE_RENEWAL),
        STAGE_RENEWAL: ('Renewal', 'Decide whether to renew, amend, terminate, or archive the agreement.', STAGE_DRAFTING),
    }
    state, action, next_stage = stage_guidance.get(
        getattr(contract, 'lifecycle_stage', None),
        ('Lifecycle review', 'Confirm the next accountable workflow step.', getattr(contract, 'lifecycle_stage', None)),
    )
    guidance = {
        'state': state,
        'severity': 'low',
        'action': action,
        'next_stage': next_stage,
        'detail': '',
        'signals': [],
    }

    if contract is None:
        return guidance

    if contract.status == RECORD_STATUS_ARCHIVED:
        guidance.update({
            'state': 'Archived',
            'severity': 'low',
            'action': 'No operational action required.',
            'next_stage': contract.lifecycle_stage,
            'detail': 'Archived contracts are retained for evidence and reference only.',
        })
        return guidance

    # Renewal, expiry and termination signals become operational only after a
    # contract is active or past execution stage.
    operational_lifecycle = (
        contract.status == RECORD_STATUS_ACTIVE
        or contract.lifecycle_stage in {STAGE_EXECUTED, STAGE_OBLIGATION_TRACKING, STAGE_RENEWAL}
    )

    if operational_lifecycle and contract.end_date:
        days_until_end = (contract.end_date - today).days
        guidance['signals'].append(
            f'End date is in {days_until_end} day(s) on {contract.end_date.isoformat()}.'
        )
        if days_until_end < 0:
            guidance.update({
                'state': 'Expired',
                'severity': 'high',
                'action': 'Review immediately for renewal, termination, or archive eligibility.',
                'next_stage': STAGE_RENEWAL,
            })
        elif days_until_end <= 30:
            guidance.update({
                'state': 'Renewal Window',
                'severity': 'medium',
                'action': 'Prepare renewal or termination decision now.',
                'next_stage': STAGE_RENEWAL,
            })

    if operational_lifecycle and contract.renewal_date:
        days_until_renewal = (contract.renewal_date - today).days
        guidance['signals'].append(
            f'Renewal date is in {days_until_renewal} day(s) on {contract.renewal_date.isoformat()}.'
        )
        if days_until_renewal <= 14 and guidance['severity'] != 'high':
            guidance.update({
                'state': 'Renewal Due',
                'severity': 'medium',
                'action': 'Finalize renewal language and stakeholder approvals.',
                'next_stage': STAGE_RENEWAL,
            })

    if operational_lifecycle and contract.auto_renew:
        guidance['signals'].append('Auto-renew is enabled.')
        if guidance['severity'] == 'low':
            guidance.update({
                'state': 'Auto-Renew Enabled',
                'severity': 'medium',
                'action': 'Set a cancellation checkpoint before the notice deadline.',
                'next_stage': STAGE_RENEWAL,
            })
        else:
            guidance['action'] = f"{guidance['action']} Auto-renew is enabled."

    if operational_lifecycle and contract.termination_notice_date:
        days_until_notice = (contract.termination_notice_date - today).days
        guidance['signals'].append(
            f'Termination notice date is in {days_until_notice} day(s) on {contract.termination_notice_date.isoformat()}.'
        )
        if days_until_notice <= 0:
            guidance.update({
                'state': 'Termination Notice Due',
                'severity': 'high',
                'action': 'Send termination notice or move to archive review immediately.',
                'next_stage': STAGE_RENEWAL,
            })

    if guidance['severity'] == 'low' and contract.lifecycle_stage == STAGE_EXECUTED and not contract.end_date:
        guidance.update({
            'state': 'Execution Complete',
            'action': 'Capture renewal date and notice period to prepare for lifecycle management.',
            'next_stage': STAGE_OBLIGATION_TRACKING,
        })

    return guidance


def get_signature_routing_blockers(contract):
    """Return truthful prerequisites for creating a new signature request.

    This helper is deliberately used by both the detail-page action model and
    the form endpoint so a hidden or stale UI cannot bypass the workflow.
    """
    from contracts.models import ApprovalRequest, RiskLog

    blockers = []
    # Signature routing is a workflow-stage concern; record status stays IN_PROGRESS
    # until activation. Approvals must be complete and stage at/after APPROVAL.
    stage = getattr(contract, 'lifecycle_stage', None)
    if stage not in {STAGE_APPROVAL, STAGE_SIGNATURE, STAGE_EXECUTED}:
        blockers.append('Move the contract to Approval or Signature stage before routing signatures.')

    from contracts.models import ApprovalRequirement

    open_requirements = ApprovalRequirement.objects.filter(
        contract=contract,
        status=ApprovalRequirement.Status.OPEN,
    )
    if open_requirements.exists():
        blockers.append('All open approval requirements must be satisfied before signature routing.')

    approvals = ApprovalRequest.objects.filter(contract=contract)
    if not approvals.exists():
        blockers.append('At least one approval is required before signature routing.')
    elif approvals.exclude(status=ApprovalRequest.Status.APPROVED).exists():
        blockers.append('All requested approvals must be completed before signature routing.')

    if RiskLog.objects.filter(
        contract=contract,
        status__in=[RiskLog.Status.OPEN, RiskLog.Status.IN_PROGRESS],
        risk_level__in=[RiskLog.RiskLevel.HIGH, RiskLog.RiskLevel.CRITICAL],
    ).exists():
        blockers.append('Resolve high or critical open risk findings before signature routing.')
    return blockers


def record_contract_grounded_check(contract, actor, *, request=None, trigger='manual'):
    """Persist evidence that deterministic contract fields were checked.

    A check is an audit event, not an AI claim.  The detail view compares this
    timestamp with ``contract.updated_at`` to mark it stale after data changes.
    """
    from contracts.middleware import log_action
    from contracts.models import AuditLog, RiskLog

    open_risk_count = RiskLog.objects.filter(
        contract=contract,
        status__in=[RiskLog.Status.OPEN, RiskLog.Status.IN_PROGRESS],
    ).count()
    log_action(
        actor,
        AuditLog.Action.UPDATE,
        'Contract',
        object_id=contract.pk,
        object_repr=str(contract)[:300],
        organization=contract.organization,
        request=request,
        event_type='contract.grounded_check_completed',
        changes={
            'event': 'contract.grounded_check_completed',
            'trigger': trigger,
            'status': contract.status,
            'lifecycle_stage': contract.lifecycle_stage,
            'risk_level': contract.risk_level,
            'open_risk_count': open_risk_count,
        },
    )


# Allowed record-status transitions. Terminal states have no outgoing edges;
# returning from a terminal state requires system repair (system=True).
CONTRACT_STATUS_TRANSITIONS = {
    RECORD_STATUS_IN_PROGRESS: {
        RECORD_STATUS_ACTIVE,
        RECORD_STATUS_CANCELLED,
        RECORD_STATUS_ARCHIVED,
    },
    RECORD_STATUS_ACTIVE: {
        RECORD_STATUS_EXPIRED,
        RECORD_STATUS_TERMINATED,
        RECORD_STATUS_CANCELLED,
        RECORD_STATUS_ARCHIVED,
    },
    RECORD_STATUS_EXPIRED: {RECORD_STATUS_ARCHIVED},
    RECORD_STATUS_TERMINATED: {RECORD_STATUS_ARCHIVED},
    RECORD_STATUS_CANCELLED: {RECORD_STATUS_ARCHIVED},
    RECORD_STATUS_ARCHIVED: set(),
}
CONTRACT_TERMINAL_STATUSES = RECORD_TERMINAL_STATUSES


class ContractTransitionError(Exception):
    """Base for contract status transition failures (carries an HTTP status_code)."""
    status_code = 400

    def __init__(self, message, status_code=None):
        super().__init__(message)
        if status_code is not None:
            self.status_code = status_code


class InvalidContractTransition(ContractTransitionError):
    status_code = 400


class ContractTransitionForbidden(ContractTransitionError):
    status_code = 403


class ContractTransitionPreconditionFailed(ContractTransitionError):
    status_code = 409


def get_allowed_contract_statuses(current_status):
    return CONTRACT_STATUS_TRANSITIONS.get(current_status, set())


def can_transition_contract_status(current_status, new_status):
    if not new_status:
        return False
    if new_status == current_status:
        return True
    return new_status in get_allowed_contract_statuses(current_status)


def _primary_contract_document(contract):
    docs = list(contract.documents.filter(is_deleted=False).order_by('-version', '-id'))
    if not docs:
        return None
    # Prefer non-superseded, then highest version.
    for doc in docs:
        if doc.status != 'SUPERSEDED':
            return doc
    return docs[0]


class ContractLifecycleService:
    """Single authority for Contract.status and lifecycle_stage transitions."""

    def transition(self, contract, new_status, actor=None, *, system=False,
                   reason='', request=None, actor_type=None, job_run_id=None):
        """Transition a contract to ``new_status`` atomically.

        - Locks the contract row (concurrent transitions serialize).
        - Verifies tenant ownership + actor permission (unless ``system=True``).
        - Validates the transition graph and prerequisites.
        - Writes a Phase 3 chained audit event.
        Returns the updated Contract; raises a ContractTransitionError subclass.
        Same-status requests are idempotent no-ops (no audit, no error).
        """
        from contracts.models import ApprovalRequest, AuditLog, Contract, SignatureRequest
        from contracts.middleware import log_action
        from contracts.permissions import ContractAction, can_access_contract_action

        contract_id = contract.pk if hasattr(contract, 'pk') else contract
        with transaction.atomic():
            contract = (
                Contract.objects.select_for_update(of=('self',)).select_related('organization')
                .get(pk=contract_id)
            )
            old_status = contract.status

            if not system:
                if actor is None or not getattr(actor, 'is_authenticated', False):
                    raise ContractTransitionForbidden('Authentication required.', status_code=403)
                if not can_access_contract_action(actor, contract, ContractAction.EDIT):
                    raise ContractTransitionForbidden(
                        'You do not have permission to change this contract.', status_code=403)

            if new_status == old_status:
                return contract

            if new_status not in get_allowed_contract_statuses(old_status) and not system:
                raise InvalidContractTransition(
                    f'Cannot move a contract from {old_status} to {new_status}.')

            # Keep stage compatible when status changes (e.g. ACTIVE requires post-activation stage).
            target_stage = contract.lifecycle_stage
            if new_status == RECORD_STATUS_ACTIVE and target_stage not in {
                STAGE_EXECUTED, STAGE_OBLIGATION_TRACKING, STAGE_RENEWAL,
            }:
                target_stage = STAGE_OBLIGATION_TRACKING
            if not system:
                validate_status_stage_pair(new_status, target_stage)

            self._check_preconditions(contract, new_status, ApprovalRequest, SignatureRequest)

            update_fields = ['status', 'updated_at']
            contract.status = new_status
            if target_stage != contract.lifecycle_stage:
                contract.lifecycle_stage = target_stage
                update_fields.append('lifecycle_stage')
            contract.save(update_fields=update_fields)

            resolved_actor_type = actor_type or (
                AuditLog.ActorType.SCHEDULED_JOB if system and actor is None
                else (AuditLog.ActorType.HUMAN if actor is not None else AuditLog.ActorType.SYSTEM)
            )
            log_action(
                actor, AuditLog.Action.UPDATE, 'Contract',
                object_id=contract.pk, object_repr=str(contract)[:300],
                organization=contract.organization, request=request,
                event_type='contract.status_changed', actor_type=resolved_actor_type,
                job_run_id=job_run_id,
                changes={
                    'event': 'contract.status_changed',
                    'from': old_status, 'to': new_status,
                    'reason': (reason or '')[:300],
                },
            )
        return contract

    def _check_preconditions(self, contract, new_status, ApprovalRequest, SignatureRequest):
        if new_status == RECORD_STATUS_ACTIVE:
            has_approval = ApprovalRequest.objects.filter(
                contract=contract, status=ApprovalRequest.Status.APPROVED,
            ).exists()
            if not has_approval:
                raise ContractTransitionPreconditionFailed(
                    'A contract cannot be activated without an approved approval request.')
            S = SignatureRequest.Status
            withdrawn = {S.CANCELLED, S.EXPIRED}
            latest_by_signer = {}
            for req in (
                SignatureRequest.objects.filter(contract=contract)
                .order_by('signer_email', '-created_at', '-id')
            ):
                latest_by_signer.setdefault(req.signer_email, req)
            blocking = [
                r for r in latest_by_signer.values()
                if r.status != S.SIGNED and r.status not in withdrawn
            ]
            if blocking:
                raise ContractTransitionPreconditionFailed(
                    'A contract cannot be activated while its current signature '
                    'workflow has unsigned, in-flight or declined requests.')

    def transition_lifecycle_stage(
        self,
        contract,
        new_stage,
        actor=None,
        *,
        system=False,
        reason='',
        request=None,
        actor_type=None,
    ):
        """Move ``lifecycle_stage`` through the canonical service with audit."""
        from contracts.middleware import log_action
        from contracts.models import AuditLog, Contract
        from contracts.permissions import ContractAction, can_access_contract_action

        contract_id = contract.pk if hasattr(contract, 'pk') else contract
        with transaction.atomic():
            contract = (
                Contract.objects.select_for_update(of=('self',)).select_related('organization')
                .get(pk=contract_id)
            )
            old_stage = contract.lifecycle_stage
            if new_stage == old_stage:
                return contract

            if not system:
                if actor is None or not getattr(actor, 'is_authenticated', False):
                    raise ContractTransitionForbidden('Authentication required.', status_code=403)
                if not can_access_contract_action(actor, contract, ContractAction.EDIT):
                    raise ContractTransitionForbidden(
                        'You do not have permission to change this contract.', status_code=403)

                if contract.status in RECORD_TERMINAL_STATUSES:
                    raise InvalidContractTransition(
                        'Cannot advance workflow stage on a terminal contract record.')

                if not can_transition_lifecycle_stage(contract, new_stage):
                    raise InvalidContractTransition(
                        f'Cannot move a contract from lifecycle stage {old_stage} to {new_stage}.')
                validate_status_stage_pair(contract.status, new_stage)

            contract.lifecycle_stage = new_stage
            contract.save(update_fields=['lifecycle_stage', 'updated_at'])
            resolved_actor_type = actor_type or (
                AuditLog.ActorType.SYSTEM if system and actor is None else AuditLog.ActorType.HUMAN
            )
            log_action(
                actor, AuditLog.Action.UPDATE, 'Contract',
                object_id=contract.pk, object_repr=str(contract)[:300],
                organization=contract.organization, request=request,
                event_type='contract.lifecycle_stage_changed', actor_type=resolved_actor_type,
                changes={
                    'event': 'contract.lifecycle_stage_changed',
                    'from': old_stage,
                    'to': new_stage,
                    'reason': (reason or '')[:300],
                },
            )
        return contract

    def apply_operational_position(
        self,
        contract,
        *,
        status=None,
        lifecycle_stage=None,
        actor=None,
        system=False,
        reason='',
        request=None,
        actor_type=None,
    ):
        """Apply status and/or lifecycle stage atomically with chained audit."""
        from contracts.middleware import log_action
        from contracts.models import AuditLog, Contract
        from contracts.permissions import ContractAction, can_access_contract_action

        contract_id = contract.pk if hasattr(contract, 'pk') else contract
        with transaction.atomic():
            contract = (
                Contract.objects.select_for_update(of=('self',)).select_related('organization')
                .get(pk=contract_id)
            )
            old_status = contract.status
            old_stage = contract.lifecycle_stage
            update_fields = ['updated_at']
            next_status = status if status is not None else old_status
            next_stage = lifecycle_stage if lifecycle_stage is not None else old_stage

            if not system:
                if actor is None or not getattr(actor, 'is_authenticated', False):
                    raise ContractTransitionForbidden('Authentication required.', status_code=403)
                if not can_access_contract_action(actor, contract, ContractAction.EDIT):
                    raise ContractTransitionForbidden(
                        'You do not have permission to change this contract.', status_code=403)
                if status is not None and status != old_status:
                    if status not in get_allowed_contract_statuses(old_status):
                        raise InvalidContractTransition(
                            f'Cannot move a contract from {old_status} to {status}.')
                if lifecycle_stage is not None and lifecycle_stage != old_stage:
                    if not can_transition_lifecycle_stage(
                        type('C', (), {'status': next_status, 'lifecycle_stage': old_stage})(),
                        lifecycle_stage,
                    ):
                        # Re-check with provisional status for joint updates.
                        provisional = type('C', (), {
                            'status': old_status,
                            'lifecycle_stage': old_stage,
                        })()
                        if not can_transition_lifecycle_stage(provisional, lifecycle_stage) and status is None:
                            raise InvalidContractTransition(
                                f'Cannot move a contract from lifecycle stage {old_stage} to {lifecycle_stage}.')
                validate_status_stage_pair(next_status, next_stage)

            if status is not None and status != old_status:
                if status == RECORD_STATUS_ACTIVE and not system:
                    from contracts.models import ApprovalRequest, SignatureRequest
                    self._check_preconditions(contract, status, ApprovalRequest, SignatureRequest)
                contract.status = status
                update_fields.append('status')

            if lifecycle_stage is not None and lifecycle_stage != old_stage:
                contract.lifecycle_stage = lifecycle_stage
                update_fields.append('lifecycle_stage')

            if len(update_fields) == 1:
                return contract

            if system or status is not None or lifecycle_stage is not None:
                validate_status_stage_pair(contract.status, contract.lifecycle_stage)

            contract.save(update_fields=update_fields)
            resolved_actor_type = actor_type or (
                AuditLog.ActorType.SYSTEM if system and actor is None else AuditLog.ActorType.HUMAN
            )
            log_action(
                actor, AuditLog.Action.UPDATE, 'Contract',
                object_id=contract.pk, object_repr=str(contract)[:300],
                organization=contract.organization, request=request,
                event_type='contract.operational_position_changed', actor_type=resolved_actor_type,
                changes={
                    'event': 'contract.operational_position_changed',
                    'status': {'before': old_status, 'after': contract.status},
                    'lifecycle_stage': {'before': old_stage, 'after': contract.lifecycle_stage},
                    'reason': (reason or '')[:300],
                },
            )
        return contract

    def activate_contract(
        self,
        contract,
        actor=None,
        *,
        system=False,
        reason='Contract activated after signature completion',
        request=None,
        actor_type=None,
    ):
        """Happy-path activation triad: ACTIVE + OBLIGATION_TRACKING + primary doc EXECUTED."""
        from contracts.middleware import log_action
        from contracts.models import AuditLog, Contract, Document

        contract_id = contract.pk if hasattr(contract, 'pk') else contract
        with transaction.atomic():
            contract = (
                Contract.objects.select_for_update(of=('self',)).select_related('organization')
                .get(pk=contract_id)
            )
            if not system:
                from contracts.models import ApprovalRequest, SignatureRequest
                self._check_preconditions(
                    contract, RECORD_STATUS_ACTIVE, ApprovalRequest, SignatureRequest,
                )

            old_status = contract.status
            old_stage = contract.lifecycle_stage
            contract.status = RECORD_STATUS_ACTIVE
            contract.lifecycle_stage = STAGE_OBLIGATION_TRACKING
            contract.save(update_fields=['status', 'lifecycle_stage', 'updated_at'])

            primary = _primary_contract_document(contract)
            if primary and primary.status != DOC_STATE_EXECUTED:
                old_doc_status = primary.status
                primary.status = Document.Status.EXECUTED
                primary.save(update_fields=['status', 'updated_at'])
                log_action(
                    actor, AuditLog.Action.UPDATE, 'Document',
                    object_id=primary.pk, object_repr=str(primary)[:300],
                    organization=contract.organization, request=request,
                    event_type='document.status_changed',
                    actor_type=actor_type or (
                        AuditLog.ActorType.SYSTEM if system and actor is None else AuditLog.ActorType.HUMAN
                    ),
                    changes={
                        'event': 'document.status_changed',
                        'from': old_doc_status,
                        'to': DOC_STATE_EXECUTED,
                        'reason': (reason or '')[:300],
                    },
                )

            resolved_actor_type = actor_type or (
                AuditLog.ActorType.SYSTEM if system and actor is None else AuditLog.ActorType.HUMAN
            )
            log_action(
                actor, AuditLog.Action.UPDATE, 'Contract',
                object_id=contract.pk, object_repr=str(contract)[:300],
                organization=contract.organization, request=request,
                event_type='contract.activated',
                actor_type=resolved_actor_type,
                changes={
                    'event': 'contract.activated',
                    'status': {'before': old_status, 'after': contract.status},
                    'lifecycle_stage': {'before': old_stage, 'after': contract.lifecycle_stage},
                    'reason': (reason or '')[:300],
                },
            )
        return contract


def apply_contract_operational_position(contract, **kwargs):
    return get_contract_lifecycle_service().apply_operational_position(contract, **kwargs)


def activate_contract(contract, **kwargs):
    return get_contract_lifecycle_service().activate_contract(contract, **kwargs)


def get_contract_lifecycle_service():
    return ContractLifecycleService()
