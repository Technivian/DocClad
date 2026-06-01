"""Approval workflow service — initiate, approve, reject, delegate, SLA escalation."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Optional

from django.db import transaction
from django.utils import timezone

from contracts.models import ApprovalRequest, ApprovalRule, Contract, Organization, User
from contracts.services.workflow_routing import (
    build_approval_request_plan_for_contract,
    select_approval_rules_for_contract,
)


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


class ApprovalWorkflowService:
    def initiate_approval_workflow(self, contract: Contract) -> list[ApprovalRequestDTO]:
        """Evaluate all matching rules and create ApprovalRequest rows for the contract."""
        plan = build_approval_request_plan_for_contract(contract)
        if not plan:
            return []
        created = []
        with transaction.atomic():
            for step_data in plan:
                if ApprovalRequest.objects.filter(
                    contract=contract,
                    approval_step=step_data['approval_step'],
                    status='PENDING',
                ).exists():
                    continue
                ar = ApprovalRequest.objects.create(**step_data)
                # Eager-load related fields for DTO
                ar.contract = contract
                if ar.rule_id:
                    ar.rule = step_data.get('rule')
                created.append(_to_dto(ar))
        return created

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

    def approve(self, approval_id: int, actor: User, comments: str = '') -> ApprovalRequestDTO:
        ar = ApprovalRequest.objects.select_related('contract', 'rule', 'assigned_to').get(pk=approval_id)
        if ar.status not in ('PENDING', 'ESCALATED'):
            raise ValueError(f'Cannot approve from status {ar.status}')
        ar.status = 'APPROVED'
        ar.comments = comments
        ar.decided_at = timezone.now()
        ar.decided_by = actor
        ar.save(update_fields=['status', 'comments', 'decided_at', 'decided_by'])
        return _to_dto(ar)

    def reject(self, approval_id: int, actor: User, comments: str = '') -> ApprovalRequestDTO:
        ar = ApprovalRequest.objects.select_related('contract', 'rule', 'assigned_to').get(pk=approval_id)
        if ar.status not in ('PENDING', 'ESCALATED'):
            raise ValueError(f'Cannot reject from status {ar.status}')
        ar.status = 'REJECTED'
        ar.comments = comments
        ar.decided_at = timezone.now()
        ar.decided_by = actor
        ar.save(update_fields=['status', 'comments', 'decided_at', 'decided_by'])
        return _to_dto(ar)

    def delegate(self, approval_id: int, to_user: User, actor: User) -> ApprovalRequestDTO:
        ar = ApprovalRequest.objects.select_related('contract', 'rule', 'assigned_to').get(pk=approval_id)
        if ar.status != 'PENDING':
            raise ValueError(f'Can only delegate PENDING approvals, current status: {ar.status}')
        ar.delegated_to = to_user
        ar.delegated_at = timezone.now()
        ar.assigned_to = to_user
        ar.save(update_fields=['delegated_to', 'delegated_at', 'assigned_to'])
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
