"""Approval workflow service — initiate, approve, reject, delegate, SLA escalation."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Optional

from django.db import transaction
from django.utils import timezone

from contracts.models import ApprovalRequest, ApprovalRule, AuditLog, Contract, Organization, User
from contracts.services.workflow_routing import (
    build_approval_request_plan_for_contract,
    select_approval_rules_for_contract,
)

logger = logging.getLogger(__name__)


class ApprovalAccessDenied(Exception):
    """Raised when an actor is not permitted to act on an approval request.

    Carries an HTTP ``status_code`` so callers can map it directly:
    404 for a cross-tenant request (do not reveal existence), 403 otherwise.
    """

    def __init__(self, message: str = 'You are not allowed to act on this approval.', status_code: int = 403):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class ApprovalRequestDTO:
    id: int
    contract_id: int
    contract_title: str
    approval_step: str
    status: str
    assigned_to_id: Optional[int]
    assigned_to_username: Optional[str]
    delegated_to_id: Optional[int]
    due_date: Optional[str]
    sla_hours: Optional[int]
    is_overdue: bool
    comments: str
    created_at: str


@dataclass
class WorkflowSummary:
    contract_id: int
    requests: list[ApprovalRequestDTO] = field(default_factory=list)
    all_approved: bool = False
    any_rejected: bool = False
    any_pending: bool = False


def _to_dto(ar: ApprovalRequest) -> ApprovalRequestDTO:
    now = timezone.now()
    is_overdue = (
        ar.status == 'PENDING'
        and ar.due_date is not None
        and ar.due_date < now
    )
    sla_hours = ar.rule.sla_hours if ar.rule_id and ar.rule else None
    return ApprovalRequestDTO(
        id=ar.pk,
        contract_id=ar.contract_id,
        contract_title=ar.contract.title if ar.contract_id else '',
        approval_step=ar.approval_step,
        status=ar.status,
        assigned_to_id=ar.assigned_to_id,
        assigned_to_username=ar.assigned_to.username if ar.assigned_to_id and ar.assigned_to else None,
        delegated_to_id=ar.delegated_to_id,
        due_date=ar.due_date.isoformat() if ar.due_date else None,
        sla_hours=sla_hours,
        is_overdue=is_overdue,
        comments=ar.comments or '',
        created_at=ar.created_at.isoformat(),
    )


def authorize_approval_actor(ar: ApprovalRequest, actor: User, *, action: str) -> None:
    """Single source of truth for approval authorization (used by API AND HTML).

    Enforces tenant isolation, assignee/admin ownership, and segregation of
    duties. Raises ``ApprovalAccessDenied`` (404 across tenants, 403 within).
    Centralizing here means the HTML form/view cannot apply a weaker rule than
    the API — the self-approval bypass (blocker A5) is closed everywhere.
    """
    from contracts.models import OrganizationMembership
    from contracts.tenancy import get_user_organization

    if actor is None or not getattr(actor, 'is_authenticated', False):
        raise ApprovalAccessDenied('Authentication required.', status_code=403)

    actor_org = get_user_organization(actor)
    effective_org_id = ar.organization_id or (ar.contract.organization_id if ar.contract_id else None)

    # Tenant boundary. Behave as "not found" so IDs cannot be enumerated
    # across organizations.
    if actor_org is None or effective_org_id is None or effective_org_id != actor_org.id:
        raise ApprovalAccessDenied('Approval request not found.', status_code=404)

    is_admin = OrganizationMembership.objects.filter(
        organization_id=effective_org_id,
        user=actor,
        is_active=True,
        role__in=[OrganizationMembership.Role.OWNER, OrganizationMembership.Role.ADMIN],
    ).exists()

    is_assignee = actor.id in {ar.assigned_to_id, ar.delegated_to_id}
    if not (is_admin or is_assignee):
        raise ApprovalAccessDenied('This approval is assigned to someone else.', status_code=403)

    # Segregation of duties: nobody (not even an org admin/owner) may decide on
    # an approval for a contract they themselves created.
    if action in ('approve', 'reject', 'request_changes') and ar.contract_id:
        accountable_user_id = ar.contract.owner_id or ar.contract.created_by_id
        if accountable_user_id is not None and accountable_user_id == actor.id:
            raise ApprovalAccessDenied(
                'You cannot decide on an approval for a contract you own.',
                status_code=403,
            )


def actor_can_decide(ar: ApprovalRequest, actor: User, action: str) -> bool:
    """Boolean form of :func:`authorize_approval_actor` for form-level checks."""
    try:
        authorize_approval_actor(ar, actor, action=action)
        return True
    except ApprovalAccessDenied:
        return False


def _audit_approval_decision(
    ar: ApprovalRequest,
    actor: User,
    action: str,
    *,
    allowed: bool,
    previous_status: str = '',
    comments: str = '',
) -> None:
    """Audit successful and blocked approve/reject decisions (no sensitive data).

    Audit writes must never break the decision itself, so failures are logged and
    suppressed here (the decision has already been authorized and persisted).
    """
    try:
        from contracts.middleware import log_action
        from contracts.models import AuditLog

        action_map = {
            'approve': AuditLog.Action.APPROVE,
            'reject': AuditLog.Action.REJECT,
            'request_changes': AuditLog.Action.UPDATE,
        }
        log_action(
            actor if getattr(actor, 'is_authenticated', False) else None,
            action_map.get(action, AuditLog.Action.UPDATE),
            'ApprovalRequest',
            object_id=ar.pk,
            object_repr=f'ApprovalRequest #{ar.pk} ({ar.approval_step})',
            changes={
                'event': f'approval_{action}_{"succeeded" if allowed else "blocked"}',
                'contract_id': ar.contract_id,
                'previous_state': previous_status,
                'new_state': ar.status if allowed else previous_status,
                'comment': comments,
            },
        )
    except Exception:
        logger.warning('approval audit logging failed for action=%s', action, exc_info=True)


class ApprovalWorkflowService:
    def initiate_approval_workflow(self, contract: Contract, actor: User | None = None) -> list[ApprovalRequestDTO]:
        """Evaluate all matching rules and create ApprovalRequest rows for the contract."""
        plan = build_approval_request_plan_for_contract(contract)
        if not plan:
            return []
        created = []
        if actor is not None:
            from contracts.permissions import ContractAction, can_access_contract_action
            if not can_access_contract_action(actor, contract, ContractAction.EDIT):
                raise ApprovalAccessDenied('Only the contract owner or a workspace admin can submit it.', 403)
        with transaction.atomic():
            for step_data in plan:
                if ApprovalRequest.objects.filter(
                    contract=contract,
                    approval_step=step_data['approval_step'],
                    status='PENDING',
                ).exists():
                    continue
                ar = ApprovalRequest.objects.create(**step_data)
                if actor is not None:
                    from contracts.middleware import log_action
                    log_action(
                        actor, AuditLog.Action.CREATE, 'ApprovalRequest',
                        object_id=ar.pk, object_repr=str(ar), organization=contract.organization,
                        event_type='approval.created',
                        changes={
                            'event': 'approval.created',
                            'contract_id': contract.pk,
                            'from': None,
                            'to': ApprovalRequest.Status.PENDING,
                            'assigned_to_id': ar.assigned_to_id,
                        },
                    )
                # Eager-load related fields for DTO
                ar.contract = contract
                if ar.rule_id:
                    ar.rule = step_data.get('rule')
                created.append(_to_dto(ar))
            if actor is not None and created and contract.status == Contract.Status.DRAFT:
                from contracts.services.contract_lifecycle import get_contract_lifecycle_service
                get_contract_lifecycle_service().transition(
                    contract,
                    Contract.Status.PENDING,
                    actor,
                    reason='Approval workflow initiated',
                )
        return created

    def submit_for_review(
        self,
        contract: Contract,
        actor: User,
        reviewer: User,
        *,
        comment: str = '',
        request=None,
    ) -> ApprovalRequestDTO:
        """Submit or resubmit a draft into one accountable review step."""
        from contracts.middleware import log_action
        from contracts.models import OrganizationMembership
        from contracts.permissions import ContractAction, can_access_contract_action
        from contracts.services.contract_lifecycle import get_contract_lifecycle_service

        if not can_access_contract_action(actor, contract, ContractAction.EDIT):
            raise ApprovalAccessDenied('Only the contract owner or a workspace admin can submit it.', 403)
        if contract.status != Contract.Status.DRAFT:
            raise ValueError(f'Only a draft can be submitted; current status is {contract.status}.')
        if reviewer.pk == (contract.owner_id or contract.created_by_id):
            raise ApprovalAccessDenied('The reviewer must be different from the contract owner.', 400)
        if not OrganizationMembership.objects.filter(
            organization=contract.organization,
            user=reviewer,
            is_active=True,
        ).exists():
            raise ApprovalAccessDenied('Reviewer must be an active member of this workspace.', 400)

        with transaction.atomic():
            locked_contract = Contract.objects.select_for_update().get(pk=contract.pk)
            if locked_contract.status != Contract.Status.DRAFT:
                raise ValueError(f'Only a draft can be submitted; current status is {locked_contract.status}.')
            approval = ApprovalRequest.objects.create(
                organization=locked_contract.organization,
                contract=locked_contract,
                approval_step='LEGAL',
                status=ApprovalRequest.Status.PENDING,
                assigned_to=reviewer,
                comments=comment.strip(),
            )
            dpa_pack = locked_contract.dpa_review_packs.order_by('-created_at').first()
            if dpa_pack and not dpa_pack.reviewer_id:
                dpa_pack.reviewer = reviewer
                dpa_pack.save(update_fields=['reviewer', 'updated_at'])
            log_action(
                actor, AuditLog.Action.CREATE, 'ApprovalRequest',
                object_id=approval.pk, object_repr=str(approval),
                organization=locked_contract.organization, request=request,
                event_type='approval.submitted',
                changes={
                    'event': 'approval.submitted',
                    'contract_id': locked_contract.pk,
                    'previous_state': None,
                    'new_state': ApprovalRequest.Status.PENDING,
                    'assigned_to_id': reviewer.pk,
                    'comment': comment.strip(),
                },
            )
            get_contract_lifecycle_service().transition(
                locked_contract,
                Contract.Status.PENDING,
                actor,
                reason='Submitted for approval',
                request=request,
            )
        return _to_dto(
            ApprovalRequest.objects.select_related('contract', 'assigned_to', 'rule').get(pk=approval.pk)
        )

    def get_contract_approvals(self, contract: Contract) -> WorkflowSummary:
        requests_qs = (
            ApprovalRequest.objects
            .filter(contract=contract)
            .select_related('contract', 'rule', 'assigned_to', 'delegated_to')
            .order_by('created_at')
        )
        dtos = [_to_dto(ar) for ar in requests_qs]
        statuses = {d.status for d in dtos}
        return WorkflowSummary(
            contract_id=contract.pk,
            requests=dtos,
            all_approved=bool(dtos) and statuses == {ApprovalRequest.Status.APPROVED},
            any_rejected=ApprovalRequest.Status.REJECTED in statuses,
            any_pending=ApprovalRequest.Status.PENDING in statuses,
        )

    def _authorize_actor(self, ar: ApprovalRequest, actor: User, *, action: str) -> None:
        """Delegate to the shared module-level rule (single source of truth)."""
        authorize_approval_actor(ar, actor, action=action)

    def _decide(self, approval_id: int, actor: User, *, action: str, new_status: str, comments: str) -> ApprovalRequestDTO:
        """Shared approve/reject body: authorize, transition, audit.

        A blocked decision is audited OUTSIDE the (rolled-back) transaction so
        the denial record persists; a successful decision is audited inside it.
        """
        try:
            with transaction.atomic():
                ar = (
                    ApprovalRequest.objects
                    .select_related('contract', 'rule', 'assigned_to')
                    .select_for_update(of=('self',))
                    .get(pk=approval_id)
                )
                self._authorize_actor(ar, actor, action=action)
                if ar.status not in ('PENDING', 'ESCALATED'):
                    raise ValueError(f'Cannot {action} from status {ar.status}')
                previous_status = ar.status
                if action in ('reject', 'request_changes') and not comments.strip():
                    raise ValueError('A comment is required for this decision.')
                ar.status = new_status
                ar.comments = comments
                ar.decided_at = timezone.now()
                ar.decided_by = actor
                ar.save(update_fields=['status', 'comments', 'decided_at', 'decided_by'])
                target_contract_status = {
                    'approve': Contract.Status.APPROVED,
                    'reject': Contract.Status.CANCELLED,
                    'request_changes': Contract.Status.DRAFT,
                }[action]
                if isinstance(ar.contract, Contract):
                    from contracts.services.contract_lifecycle import get_contract_lifecycle_service
                    lifecycle = get_contract_lifecycle_service()
                    # Older/manual approval requests can exist while their
                    # contract is still DRAFT. Normalize that persisted state
                    # through the same lifecycle graph before applying the
                    # decision; never jump DRAFT -> APPROVED directly.
                    if ar.contract.status == Contract.Status.DRAFT and action == 'approve':
                        ar.contract = lifecycle.transition(
                            ar.contract,
                            Contract.Status.PENDING,
                            actor,
                            system=True,
                            actor_type=AuditLog.ActorType.HUMAN,
                            reason='Normalized legacy approval submission',
                        )
                    lifecycle.transition(
                        ar.contract,
                        target_contract_status,
                        actor,
                        system=True,
                        actor_type=AuditLog.ActorType.HUMAN,
                        reason=comments,
                    )
                    if action == 'approve':
                        Contract.objects.filter(pk=ar.contract_id).update(
                            approved_by=actor,
                            approved_at=timezone.now(),
                        )
                _audit_approval_decision(
                    ar,
                    actor,
                    action,
                    allowed=True,
                    previous_status=previous_status,
                    comments=comments,
                )
            return _to_dto(ar)
        except ApprovalAccessDenied:
            # The transaction rolled back; record the blocked attempt separately.
            try:
                blocked_ar = ApprovalRequest.objects.select_related('contract').get(pk=approval_id)
                _audit_approval_decision(blocked_ar, actor, action, allowed=False, comments=comments)
            except ApprovalRequest.DoesNotExist:
                pass
            raise

    def approve(self, approval_id: int, actor: User, comments: str = '') -> ApprovalRequestDTO:
        return self._decide(approval_id, actor, action='approve', new_status='APPROVED', comments=comments)

    def reject(self, approval_id: int, actor: User, comments: str = '') -> ApprovalRequestDTO:
        return self._decide(approval_id, actor, action='reject', new_status='REJECTED', comments=comments)

    def request_changes(self, approval_id: int, actor: User, comments: str = '') -> ApprovalRequestDTO:
        return self._decide(
            approval_id,
            actor,
            action='request_changes',
            new_status=ApprovalRequest.Status.CHANGES_REQUESTED,
            comments=comments,
        )

    def delegate(self, approval_id: int, to_user: User, actor: User) -> ApprovalRequestDTO:
        from contracts.models import OrganizationMembership

        with transaction.atomic():
            ar = (
                ApprovalRequest.objects
                .select_related('contract', 'rule', 'assigned_to')
                .select_for_update(of=('self',))
                .get(pk=approval_id)
            )
            self._authorize_actor(ar, actor, action='delegate')
            if ar.status != 'PENDING':
                raise ValueError(f'Can only delegate PENDING approvals, current status: {ar.status}')

            # The delegate must belong to the same organization — never assign an
            # approval to a user outside the tenant.
            effective_org_id = ar.organization_id or (ar.contract.organization_id if ar.contract_id else None)
            in_org = OrganizationMembership.objects.filter(
                organization_id=effective_org_id,
                user=to_user,
                is_active=True,
            ).exists()
            if not in_org:
                raise ApprovalAccessDenied(
                    'Delegate must be a member of this organization.', status_code=400,
                )

            ar.delegated_to = to_user
            ar.delegated_at = timezone.now()
            ar.assigned_to = to_user
            ar.save(update_fields=['delegated_to', 'delegated_at', 'assigned_to'])
            # Audit the delegation atomically with the state change.
            from contracts.middleware import log_action
            log_action(
                actor, AuditLog.Action.UPDATE, 'ApprovalRequest',
                object_id=ar.pk, object_repr=f'ApprovalRequest #{ar.pk} ({ar.approval_step})',
                organization_id=effective_org_id, event_type='approval.delegated',
                changes={
                    'event': 'approval.delegated',
                    'contract_id': ar.contract_id,
                    'delegated_to_id': to_user.id,
                },
            )
        return _to_dto(ar)

    def escalate(self, approval_id: int) -> ApprovalRequestDTO:
        ar = ApprovalRequest.objects.select_related('contract', 'rule', 'assigned_to').get(pk=approval_id)
        if ar.status != 'PENDING':
            raise ValueError(f'Cannot escalate from status {ar.status}')
        ar.status = 'ESCALATED'
        ar.escalated_at = timezone.now()
        ar.save(update_fields=['status', 'escalated_at'])
        return _to_dto(ar)

    def get_overdue_approvals(self, org: Organization) -> list[ApprovalRequestDTO]:
        now = timezone.now()
        overdue_qs = (
            ApprovalRequest.objects
            .filter(
                organization=org,
                status='PENDING',
                due_date__lt=now,
            )
            .select_related('contract', 'rule', 'assigned_to')
            .order_by('due_date')
        )
        return [_to_dto(ar) for ar in overdue_qs]

    def escalate_overdue_for_org(self, org: Organization) -> int:
        """Auto-escalate all overdue PENDING approvals. Returns count escalated."""
        overdue = self.get_overdue_approvals(org)
        count = 0
        for dto in overdue:
            try:
                self.escalate(dto.id)
                count += 1
            except ValueError:
                pass
        return count

    def list_approvals(self, org: Organization, status: str = None) -> list[ApprovalRequestDTO]:
        qs = (
            ApprovalRequest.objects
            .filter(organization=org)
            .select_related('contract', 'rule', 'assigned_to')
            .order_by('-created_at')
        )
        if status:
            qs = qs.filter(status=status.upper())
        return [_to_dto(ar) for ar in qs]


def get_approval_workflow_service() -> ApprovalWorkflowService:
    return ApprovalWorkflowService()
