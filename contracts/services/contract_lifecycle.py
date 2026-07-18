import logging
import hashlib
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


CONTRACT_LIFECYCLE_TRANSITIONS = {
    'DRAFTING': {'INTERNAL_REVIEW', 'ARCHIVED'},
    'INTERNAL_REVIEW': {'NEGOTIATION', 'ARCHIVED'},
    'NEGOTIATION': {'APPROVAL', 'ARCHIVED'},
    'APPROVAL': {'SIGNATURE', 'ARCHIVED'},
    'SIGNATURE': {'EXECUTED', 'ARCHIVED'},
    'EXECUTED': {'OBLIGATION_TRACKING', 'RENEWAL', 'ARCHIVED'},
    'OBLIGATION_TRACKING': {'RENEWAL', 'ARCHIVED'},
    'RENEWAL': {'DRAFTING', 'ARCHIVED'},
    'ARCHIVED': set(),
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
    return new_stage in get_allowed_lifecycle_stages(current_stage)


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
        'DRAFTING': ('Drafting', 'Submit for review when the record is ready.', 'INTERNAL_REVIEW'),
        'INTERNAL_REVIEW': ('Internal review', 'Resolve reviewer feedback and move into negotiation.', 'NEGOTIATION'),
        'NEGOTIATION': ('Negotiation', 'Resolve open commercial and legal positions before approval.', 'APPROVAL'),
        'APPROVAL': ('Approval', 'Collect the required approvals before signature routing.', 'SIGNATURE'),
        'SIGNATURE': ('Signature', 'Track signatures and activate only when the packet is complete.', 'EXECUTED'),
        'EXECUTED': ('Executed', 'Confirm obligations and renewal dates for ongoing management.', 'OBLIGATION_TRACKING'),
        'OBLIGATION_TRACKING': ('Obligation tracking', 'Monitor obligations and prepare the next renewal decision.', 'RENEWAL'),
        'RENEWAL': ('Renewal', 'Decide whether to renew, amend, terminate, or archive the agreement.', 'DRAFTING'),
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

    if contract.lifecycle_stage == 'ARCHIVED':
        guidance.update({
            'state': 'Archived',
            'severity': 'low',
            'action': 'No operational action required.',
            'next_stage': 'ARCHIVED',
            'detail': 'Archived contracts are retained for evidence and reference only.',
        })
        return guidance

    # Renewal, expiry and termination signals become operational only after a
    # contract is executed/active.  Applying them while a record is still
    # drafting or under review makes the page claim two incompatible next
    # stages (for example, Drafting and Renewal at the same time).
    operational_lifecycle = (
        contract.status == 'ACTIVE'
        or contract.lifecycle_stage in {'EXECUTED', 'OBLIGATION_TRACKING', 'RENEWAL'}
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
                'next_stage': 'RENEWAL',
            })
        elif days_until_end <= 30:
            guidance.update({
                'state': 'Renewal Window',
                'severity': 'medium',
                'action': 'Prepare renewal or termination decision now.',
                'next_stage': 'RENEWAL',
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
                'next_stage': 'RENEWAL',
            })

    if operational_lifecycle and contract.auto_renew:
        guidance['signals'].append('Auto-renew is enabled.')
        if guidance['severity'] == 'low':
            guidance.update({
                'state': 'Auto-Renew Enabled',
                'severity': 'medium',
                'action': 'Set a cancellation checkpoint before the notice deadline.',
                'next_stage': 'RENEWAL',
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
                'next_stage': 'RENEWAL',
            })

    if guidance['severity'] == 'low' and contract.lifecycle_stage == 'EXECUTED' and not contract.end_date:
        guidance.update({
            'state': 'Execution Complete',
            'action': 'Capture renewal date and notice period to prepare for lifecycle management.',
            'next_stage': 'OBLIGATION_TRACKING',
        })

    return guidance


def get_signature_routing_blockers(contract):
    """Return truthful prerequisites for creating a new signature request.

    This helper is deliberately used by both the detail-page action model and
    the form endpoint so a hidden or stale UI cannot bypass the workflow.
    """
    from contracts.models import ApprovalRequest, Contract, RiskLog

    blockers = []
    if contract.status != Contract.Status.APPROVED:
        blockers.append('The contract must be fully approved before signature routing.')

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
            'risk_level': contract.risk_level,
            'open_risk_count': open_risk_count,
        },
    )


# ---------------------------------------------------------------------------
# Canonical Contract.status lifecycle (Phase 4B)
#
# `status` is the business lifecycle (distinct from `lifecycle_stage` above).
# Every status change must go through ContractLifecycleService.transition so the
# same graph, permissions, prerequisites, atomicity and chained audit apply to
# HTML, API, bulk, jobs and admin paths alike.
# ---------------------------------------------------------------------------

# Allowed status transitions. Terminal states have no outgoing edges; returning
# from a terminal state requires a separately designed restoration workflow
# (intentionally not provided here).
# Activation is reachable from the review states (PENDING/IN_REVIEW/APPROVED) but
# is gated by the ACTIVE precondition (an approved ApprovalRequest, plus signature
# completion where signatures exist). DRAFT->ACTIVE and any terminal->ACTIVE are
# blocked by the graph; the precondition then enforces approval/signature.
CONTRACT_STATUS_TRANSITIONS = {
    'DRAFT': {'IN_REVIEW', 'PENDING', 'CANCELLED'},
    'PENDING': {'IN_REVIEW', 'APPROVED', 'ACTIVE', 'DRAFT', 'CANCELLED'},   # submitted for approval
    'IN_REVIEW': {'APPROVED', 'PENDING', 'ACTIVE', 'DRAFT', 'CANCELLED'},
    'APPROVED': {'ACTIVE', 'CANCELLED'},
    'ACTIVE': {'EXPIRED', 'TERMINATED', 'COMPLETED'},
    'EXPIRED': set(),
    'TERMINATED': set(),
    'COMPLETED': set(),
    'CANCELLED': set(),
}
CONTRACT_TERMINAL_STATUSES = frozenset({'EXPIRED', 'TERMINATED', 'COMPLETED', 'CANCELLED'})


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


class ContractLifecycleService:
    """Single authority for Contract.status transitions."""

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
            # Lock only the contract row: select_related('organization') adds a
            # LEFT OUTER JOIN (organization is nullable) and PostgreSQL refuses
            # FOR UPDATE on the nullable side of an outer join, so scope the lock
            # with of=('self',).
            contract = (
                Contract.objects.select_for_update(of=('self',)).select_related('organization')
                .get(pk=contract_id)
            )
            old_status = contract.status

            if not system:
                if actor is None or not getattr(actor, 'is_authenticated', False):
                    raise ContractTransitionForbidden('Authentication required.', status_code=403)
                # Tenant + permission (can_access_contract_action checks org membership).
                if not can_access_contract_action(actor, contract, ContractAction.EDIT):
                    raise ContractTransitionForbidden(
                        'You do not have permission to change this contract.', status_code=403)

            # Idempotent no-op.
            if new_status == old_status:
                return contract

            if new_status not in get_allowed_contract_statuses(old_status):
                raise InvalidContractTransition(
                    f'Cannot move a contract from {old_status} to {new_status}.')

            self._check_preconditions(contract, new_status, ApprovalRequest, SignatureRequest)

            contract.status = new_status
            contract.save(update_fields=['status', 'updated_at'])

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
        if new_status == 'ACTIVE':
            has_approval = ApprovalRequest.objects.filter(
                contract=contract, status=ApprovalRequest.Status.APPROVED,
            ).exists()
            if not has_approval:
                raise ContractTransitionPreconditionFailed(
                    'A contract cannot be activated without an approved approval request.')
            # Signature prerequisite — evaluate only the CURRENT applicable
            # signing workflow, not every historical request. There is no packet
            # model, so the "current" request for each signer is the most recent
            # one (by created_at); a re-issued request supersedes older ones for
            # that signer. Rules for each signer's current request:
            #   SIGNED                       -> satisfied
            #   CANCELLED / EXPIRED          -> withdrawn (does NOT block)
            #   PENDING / SENT / VIEWED      -> in-flight (BLOCKS: not complete)
            #   DECLINED                     -> active refusal (BLOCKS)
            # This ensures cancelled/expired/superseded/abandoned historical
            # requests cannot wrongly block activation, while genuinely open or
            # refused current requests still do.
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


def get_contract_lifecycle_service():
    return ContractLifecycleService()
