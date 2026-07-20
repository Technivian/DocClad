"""Workflow Operations helpers — instance queue rows and filter context.

Separates the operating queue (live Workflow instances) from Workflow Designer
(template authoring: definitions, conditions, stages, versioning, publishing).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional
from urllib.parse import urlencode

from django.db.models import Prefetch, Q, QuerySet
from django.urls import reverse

from contracts.models import ApprovalRequest, Contract, Workflow, WorkflowStep

EXCEPTION_LABEL_RE = re.compile(r'\s*[-–—]\s*Exception\s*$', re.IGNORECASE)
EXCEPTION_WORD_RE = re.compile(r'(^|\s)Exception(\s|$)', re.IGNORECASE)

OPEN_STEP_STATUSES = {
    WorkflowStep.Status.PENDING,
    WorkflowStep.Status.IN_PROGRESS,
    WorkflowStep.Status.ESCALATED,
}
DONE_STEP_STATUSES = {
    WorkflowStep.Status.COMPLETED,
    WorkflowStep.Status.SKIPPED,
}


@dataclass(frozen=True)
class WorkflowOperationsFilters:
    search: str = ''
    status: str = ''
    contract_type: str = ''
    owner: str = ''
    exception_only: bool = False
    jurisdiction: str = ''
    business_unit: str = ''

    @classmethod
    def from_request(cls, request) -> 'WorkflowOperationsFilters':
        get = request.GET
        return cls(
            search=(get.get('q') or get.get('search') or '').strip(),
            status=(get.get('status') or '').strip(),
            contract_type=(get.get('contract_type') or '').strip(),
            owner=(get.get('owner') or '').strip(),
            exception_only=(get.get('exception') or '').strip().lower() in {'1', 'true', 'yes', 'on'},
            jurisdiction=(get.get('jurisdiction') or '').strip(),
            business_unit=(get.get('business_unit') or '').strip(),
        )

    @property
    def active(self) -> bool:
        return bool(
            self.search
            or self.status
            or self.contract_type
            or self.owner
            or self.exception_only
            or self.jurisdiction
            or self.business_unit
        )

    @property
    def more_filters_active(self) -> bool:
        # Any non-search filter opens the Filters drawer (Contracts/DPA pattern).
        return bool(
            self.status
            or self.contract_type
            or self.owner
            or self.exception_only
            or self.jurisdiction
            or self.business_unit
        )


def workflow_operations_tabs(*, active: str) -> list[dict]:
    """Backward-compatible alias for the unified Workflow Designer hub tabs."""
    from contracts.services.workflow_designer import workflow_hub_tabs

    return workflow_hub_tabs(active=active)


def split_exception_from_title(title: str) -> tuple[str, bool]:
    """Return (display_name, has_exception) with Exception removed from the name."""
    raw = (title or '').strip()
    if not raw:
        return 'Untitled workflow', False
    cleaned = EXCEPTION_LABEL_RE.sub('', raw).strip()
    if cleaned != raw:
        return cleaned or 'Untitled workflow', True
    if EXCEPTION_WORD_RE.search(raw):
        cleaned = EXCEPTION_WORD_RE.sub(r'\1', raw).strip(' -–—')
        return cleaned or 'Untitled workflow', True
    return raw, False


def _current_stage(workflow: Workflow, steps: list[WorkflowStep]) -> str:
    current = next((step for step in steps if step.status in OPEN_STEP_STATUSES), None)
    if current:
        return current.name
    if workflow.status == Workflow.Status.COMPLETED:
        return 'Completed'
    if workflow.status == Workflow.Status.CANCELLED:
        return 'Cancelled'
    contract = workflow.contract
    if contract and contract.lifecycle_stage:
        return contract.get_lifecycle_stage_display()
    return 'Intake'


def _progress_percentage(workflow: Workflow, steps: list[WorkflowStep]) -> int:
    if not steps:
        return 100 if workflow.status == Workflow.Status.COMPLETED else 0
    done = sum(1 for step in steps if step.status in DONE_STEP_STATUSES)
    return int(round((done / len(steps)) * 100))


def _owner_label(workflow: Workflow) -> str:
    contract = workflow.contract
    owner = getattr(contract, 'owner', None) if contract else None
    if owner:
        return owner.get_full_name() or owner.username
    if workflow.created_by_id:
        return workflow.created_by.get_full_name() or workflow.created_by.username
    return 'Unassigned'


def build_workflow_operations_row(workflow: Workflow) -> dict:
    contract = workflow.contract
    source_title = (contract.title if contract and contract.title else workflow.title) or ''
    display_name, title_exception = split_exception_from_title(source_title)
    steps = list(workflow.steps.all())
    escalated = any(step.status == WorkflowStep.Status.ESCALATED for step in steps)
    has_exception = title_exception or escalated
    agreement_date = None
    key_date = None
    if contract:
        agreement_date = contract.start_date or (contract.created_at.date() if contract.created_at else None)
        key_date = contract.end_date or contract.renewal_date
    return {
        'workflow': workflow,
        'pk': workflow.pk,
        'detail_url': reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}),
        'display_name': display_name,
        'counterparty': (contract.counterparty if contract else '') or '—',
        'has_exception': has_exception,
        'status': workflow.status,
        'status_label': workflow.get_status_display(),
        'stage': _current_stage(workflow, steps),
        'agreement_type': contract.get_contract_type_display() if contract else '—',
        'business_unit': (contract.business_unit if contract and contract.business_unit else '—'),
        'jurisdiction': (contract.jurisdiction if contract and contract.jurisdiction else '—'),
        'agreement_date': agreement_date,
        'key_date': key_date,
        'value': contract.value if contract else None,
        'currency': contract.currency if contract else Contract.Currency.USD,
        'owner_label': _owner_label(workflow),
        'progress_percentage': _progress_percentage(workflow, steps),
    }


def filter_workflow_operations_queryset(
    queryset: QuerySet[Workflow],
    filters: WorkflowOperationsFilters,
) -> QuerySet[Workflow]:
    qs = queryset
    if filters.search:
        term = filters.search
        qs = qs.filter(
            Q(title__icontains=term)
            | Q(description__icontains=term)
            | Q(contract__title__icontains=term)
            | Q(contract__counterparty__icontains=term)
            | Q(contract__business_unit__icontains=term)
            | Q(contract__jurisdiction__icontains=term)
        )
    if filters.status:
        qs = qs.filter(status=filters.status)
    if filters.contract_type:
        qs = qs.filter(contract__contract_type=filters.contract_type)
    if filters.owner == 'unassigned':
        qs = qs.filter(Q(contract__owner__isnull=True) & Q(created_by__isnull=True))
    elif filters.owner:
        qs = qs.filter(Q(contract__owner_id=filters.owner) | Q(created_by_id=filters.owner))
    if filters.jurisdiction:
        qs = qs.filter(contract__jurisdiction__icontains=filters.jurisdiction)
    if filters.business_unit:
        qs = qs.filter(contract__business_unit__icontains=filters.business_unit)
    return qs.distinct()


def annotate_workflow_operations_queryset(queryset: QuerySet[Workflow]) -> QuerySet[Workflow]:
    return queryset.select_related(
        'contract',
        'contract__owner',
        'created_by',
        'template',
    ).prefetch_related(
        Prefetch('steps', queryset=WorkflowStep.objects.order_by('order')),
    )


def build_workflow_operations_rows(
    workflows: Iterable[Workflow],
    *,
    exception_only: bool = False,
) -> list[dict]:
    rows = [build_workflow_operations_row(workflow) for workflow in workflows]
    if exception_only:
        rows = [row for row in rows if row['has_exception']]
    return rows


def clear_filters_url(base_url: str, *, keep: Optional[dict] = None) -> str:
    params = {key: value for key, value in (keep or {}).items() if value}
    if not params:
        return base_url
    return f'{base_url}?{urlencode(params)}'


def pending_approval_count(organization) -> int:
    if not organization:
        return 0
    return ApprovalRequest.objects.filter(
        organization=organization,
        status=ApprovalRequest.Status.PENDING,
    ).count()


def active_workflow_count(queryset: QuerySet[Workflow]) -> int:
    return queryset.filter(status=Workflow.Status.ACTIVE).count()
