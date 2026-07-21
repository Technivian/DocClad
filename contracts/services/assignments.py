"""Canonical assignment model for personal and org-wide work surfaces.

This module is the single source of truth for actionable work assigned to a
user. My Work, specialist inboxes, and (eventually) Command Center projections
should read from these helpers rather than re-aggregating domain models in views.

Each assignment row exposes a stable shape: owner/acting assignee, source type,
priority, user-language status, deep link, and permission-safe restricted states.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from contracts.models import (
    ApprovalRequest,
    Contract,
    ContractReviewFinding,
    Deadline,
    DPAReviewPack,
    DPARiskItem,
    LegalTask,
    WorkflowStep,
)
from contracts.permissions import ContractAction, can_access_contract_action, get_active_org_membership
from contracts.services.contract_detail_workspace import contract_detail_workflow_url
from contracts.services.queue_rows import latest_activity_map
from contracts.tenancy import scope_queryset_for_organization

PRIORITY_RANK = {'Critical': 4, 'High': 3, 'Normal': 2, 'Low': 1}
DUE_SOON_DAYS = 7
UPCOMING_OBLIGATION_DAYS = 30
RECENTLY_COMPLETED_DAYS = 30


def can_actor_complete_task(task, user, org) -> bool:
    """Whether the actor may complete this task (shared by My Work + Tasks).

    Mirrors LegalTaskUpdateView: contract-linked tasks need contract EDIT;
    matter-linked tasks must belong to the actor's organization.
    """
    if task.contract_id and not can_access_contract_action(user, task.contract, ContractAction.EDIT):
        return False
    if task.matter_id and (not org or task.matter.organization_id != org.id):
        return False
    return True

WORK_TYPE_CHOICES = (
    ('all', 'All'),
    ('reviews', 'Reviews'),
    ('approvals', 'Approvals'),
    ('tasks', 'Tasks'),
    ('questions', 'Questions'),
    ('privacy', 'Privacy'),
    ('obligations', 'Obligations'),
)

SUMMARY_FILTERS = (
    ('due_today', 'Due today'),
    ('overdue', 'Overdue'),
    ('awaiting_review', 'Awaiting my review'),
    ('questions_for_me', 'Questions for me'),
    ('returned_to_me', 'Returned to me'),
    ('upcoming_obligations', 'Upcoming obligations'),
)

# Standard empty-state copy for work queues (Phase 1.3 honesty baseline).
QUEUE_EMPTY_PERSONAL = {
    'approvals_waiting': (
        'No approvals waiting on you',
        'Nothing in this specialist inbox requires your decision right now.',
        'Personal assignments also appear on My Work when they need action.',
    ),
    'tasks_assigned': (
        'No tasks assigned to you',
        'You have no open legal tasks in this workspace.',
        'Assigned tasks also surface on My Work alongside approvals and obligations.',
    ),
    'obligations_mine': (
        'No obligations assigned to you',
        'You are not the owner of any open obligation in this workspace.',
        'Your assigned obligations also appear on My Work.',
    ),
    'privacy_mine': (
        'No privacy reviews assigned to you',
        'You have no open DPA review packs assigned as reviewer.',
        'Privacy assignments also appear on My Work when action is required.',
    ),
}


def pending_approvals_queryset(organization, user, *, queryset=None, scope='personal'):
    """Approvals pending on the signed-in user (or org-wide for team scope)."""
    qs = queryset or scope_queryset_for_organization(
        ApprovalRequest.objects.select_related(
            'contract', 'contract__created_by', 'assigned_to', 'delegated_to',
        ),
        organization,
    )
    qs = qs.filter(
        status__in=[ApprovalRequest.Status.PENDING, ApprovalRequest.Status.ESCALATED],
    )
    if scope != 'team':
        qs = qs.filter(Q(assigned_to=user) | Q(delegated_to=user))
    return qs


def open_tasks_queryset(organization, user, *, queryset=None, scope='personal'):
    """Open legal tasks assigned to the signed-in user (or org-wide for team scope)."""
    if organization is None:
        return LegalTask.objects.none()
    qs = queryset or LegalTask.objects.select_related(
        'contract', 'matter', 'assigned_to',
    ).filter(Q(contract__organization=organization) | Q(matter__organization=organization))
    qs = qs.filter(status__in=[LegalTask.Status.PENDING, LegalTask.Status.IN_PROGRESS])
    if scope != 'team':
        qs = qs.filter(assigned_to=user)
    return qs


def open_obligations_queryset(organization, user, *, scope='personal'):
    """Incomplete obligations owned by the signed-in user (or org-wide for team scope)."""
    if organization is None:
        return Deadline.objects.none()
    qs = (
        Deadline.objects.for_organization(organization)
        .select_related('matter', 'contract', 'assigned_to', 'created_by')
        .filter(is_completed=False)
    )
    if scope != 'team':
        qs = qs.filter(assigned_to=user)
    return qs


def reviewer_privacy_packs_queryset(organization, user, *, scope='personal'):
    """Non-approved DPA review packs assigned to the signed-in reviewer (or org-wide)."""
    if organization is None:
        return DPAReviewPack.objects.none()
    qs = (
        DPAReviewPack.objects.filter(organization=organization)
        .exclude(approval_status__in=[DPAReviewPack.ApprovalStatus.APPROVED])
        .select_related('contract', 'counterparty', 'reviewer')
    )
    if scope != 'team':
        qs = qs.filter(reviewer=user)
    return qs


def _date_only(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return value.date()
    return value


def _contract_accessible(user, contract):
    if contract is None:
        return True
    return can_access_contract_action(user, contract)


def _safe_contract_title(contract):
    if contract is None:
        return ''
    return contract.title or f'Contract #{contract.pk}'


def _safe_counterparty(contract, fallback=''):
    if contract is None:
        return fallback
    return contract.counterparty or ''


def _priority_label(priority_value):
    mapping = {
        'CRITICAL': 'Critical',
        'URGENT': 'Critical',
        'HIGH': 'High',
        'MEDIUM': 'Normal',
        'LOW': 'Low',
    }
    if isinstance(priority_value, int):
        if priority_value >= 90:
            return 'Critical'
        if priority_value >= 70:
            return 'High'
        if priority_value >= 50:
            return 'Normal'
        return 'Low'
    return mapping.get(str(priority_value or '').upper(), 'Normal')


def _priority_rank(label):
    return PRIORITY_RANK.get(label, 2)


def _due_context(due_date, today):
    due_date = _date_only(due_date)
    if not due_date:
        return {
            'due_date': None,
            'due_overdue': False,
            'due_today': False,
            'due_soon': False,
        }
    overdue = due_date < today
    due_today = due_date == today
    due_soon = not overdue and (due_date - today).days <= DUE_SOON_DAYS
    return {
        'due_date': due_date,
        'due_overdue': overdue,
        'due_today': due_today,
        'due_soon': due_soon,
    }


def _status_for_row(*, work_kind, source_status='', due_ctx=None, is_returned=False, is_rejected=False, is_blocked=False):
    due_ctx = due_ctx or {}
    if is_blocked:
        return 'Blocked'
    if is_rejected:
        return 'Rejected, correction required'
    if is_returned:
        return 'Returned to you'
    if due_ctx.get('due_overdue'):
        return 'Overdue'
    if due_ctx.get('due_today'):
        return 'Due today'
    if work_kind == 'approval':
        return 'Awaiting your approval'
    if work_kind in ('review', 'privacy', 'finding'):
        if due_ctx.get('due_soon'):
            return 'Due soon'
        return 'Awaiting your review'
    if work_kind == 'question':
        return 'Assigned to you'
    if due_ctx.get('due_soon'):
        return 'Due soon'
    return 'Assigned to you'


def _status_tone(status_label):
    if status_label in ('Overdue', 'Rejected, correction required'):
        return 'danger'
    if status_label in ('Due today', 'Due soon', 'Returned to you'):
        return 'warning'
    if status_label in ('Awaiting your review', 'Awaiting your approval', 'Assigned to you'):
        return 'info'
    if status_label == 'Blocked':
        return 'neutral'
    return 'neutral'


def _action_for_kind(work_kind, *, approval_step=''):
    if work_kind == 'approval':
        return 'Approve'
    if work_kind == 'question':
        return 'Respond'
    if work_kind in ('task', 'obligation'):
        return 'Complete'
    if work_kind in ('returned', 'rejected'):
        return 'Correct'
    if work_kind == 'privacy':
        return 'Review'
    return 'Open'


def _summary_tags(*, work_kind, due_ctx, is_returned=False, is_rejected=False, is_question=False):
    tags = []
    if due_ctx.get('due_today'):
        tags.append('due_today')
    if due_ctx.get('due_overdue'):
        tags.append('overdue')
    if work_kind in ('review', 'privacy', 'finding') and not is_question:
        tags.append('awaiting_review')
    if is_question:
        tags.append('questions_for_me')
    if is_returned:
        tags.append('returned_to_me')
    if work_kind == 'obligation' and due_ctx.get('due_date') and not due_ctx.get('due_overdue'):
        today = date.today()
        if (due_ctx['due_date'] - today).days <= UPCOMING_OBLIGATION_DAYS:
            tags.append('upcoming_obligations')
    if is_rejected:
        tags.append('returned_to_me')
    return tags


def _sort_key(row, today, org_overdue_rates=None):
    due_ctx = row.get('due_context') or {}
    tier = 5
    if due_ctx.get('due_overdue'):
        tier = 0
    elif due_ctx.get('due_today'):
        tier = 1
    elif row.get('is_returned') or row.get('is_rejected'):
        tier = 2
    elif _priority_rank(row.get('priority_label')) >= 3:
        tier = 3
    elif due_ctx.get('due_soon'):
        tier = 4
    # Measured overdue rate for this work kind can nudge one tier earlier.
    if org_overdue_rates and tier > 0:
        from contracts.services.work_instrumentation import measured_priority_boost
        boost = measured_priority_boost(
            work_kind=row.get('work_kind') or '',
            org_overdue_rates=org_overdue_rates,
        )
        if boost:
            tier = max(0, tier - boost)
    return (
        tier,
        due_ctx.get('due_date') or date.max,
        row.get('assigned_date') or date.max,
        -_priority_rank(row.get('priority_label')),
        row.get('id') or '',
    )


def _delegation_info(assigned_to, delegated_to, delegated_at, reason='', ends_at=None):
    from contracts.services.governance_ux import build_delegation_info
    return build_delegation_info(
        assigned_to,
        delegated_to,
        delegated_at,
        reason=reason,
        ends_at=ends_at,
    )


def _base_row(
    *,
    row_id,
    title,
    work_kind,
    work_type_key,
    work_type_label,
    contract,
    user,
    assigned_date,
    due_date,
    assigned_by=None,
    requestor=None,
    description='',
    workflow_stage='',
    priority_reason='',
    blocking_issue='',
    blocker_owner='',
    action_href='',
    action_label='',
    source_status='',
    is_returned=False,
    is_rejected=False,
    is_blocked=False,
    is_question=False,
    priority_value='MEDIUM',
    delegation=None,
    reference='',
    today=None,
):
    today = today or date.today()
    if contract and not _contract_accessible(user, contract):
        return {
            'id': row_id,
            'title': 'Restricted assignment',
            'work_kind': work_kind,
            'work_type_key': work_type_key,
            'work_type_label': work_type_label,
            'contract': None,
            'contract_title': 'Restricted record',
            'contract_reference': '',
            'counterparty': '',
            'contract_type': '',
            'assigned_date': assigned_date,
            'due_context': _due_context(due_date, today),
            'status_label': 'Blocked',
            'status_tone': 'neutral',
            'priority_label': 'Normal',
            'priority_tone': 'neutral',
            'priority_reason': 'You no longer have access to this record.',
            'action_label': 'Open',
            'action_href': '',
            'href': '',
            'assigned_by': None,
            'requestor': None,
            'description': 'This assignment exists but the underlying record is not accessible with your current permissions.',
            'workflow_stage': '',
            'blocking_issue': 'Access revoked or restricted by confidentiality controls.',
            'blocker_owner': 'Workspace administrator',
            'recent_activity': '',
            'delegation': None,
            'summary_tags': [],
            'is_returned': False,
            'is_rejected': False,
            'is_blocked': True,
            'is_restricted': True,
            'reference': reference,
        }

    due_ctx = _due_context(due_date, today)
    status_label = _status_for_row(
        work_kind=work_kind,
        source_status=source_status,
        due_ctx=due_ctx,
        is_returned=is_returned,
        is_rejected=is_rejected,
        is_blocked=is_blocked,
    )
    if not action_label:
        action_label = _action_for_kind('returned' if is_returned else 'rejected' if is_rejected else work_kind)
    summary_tags = _summary_tags(
        work_kind=work_kind,
        due_ctx=due_ctx,
        is_returned=is_returned,
        is_rejected=is_rejected,
        is_question=is_question,
    )
    # Phase 6: overdue / escalated / blocked work rises by rule — not decorative urgency.
    priority_label = _priority_label(priority_value)
    if due_ctx.get('due_overdue') and _priority_rank(priority_label) < 3:
        priority_label = 'High'
        if not priority_reason:
            priority_reason = 'Overdue — elevated by SLA rule'
    if source_status == 'ESCALATED' and _priority_rank(priority_label) < 4:
        priority_label = 'Critical'
        if not priority_reason:
            priority_reason = 'Escalated past SLA / escalation threshold'
    if is_blocked and _priority_rank(priority_label) < 3:
        priority_label = 'High'
        if not priority_reason:
            priority_reason = blocking_issue or 'Blocked — waiting on a dependency'
    from contracts.services.governance_ux import priority_tone_for_label
    return {
        'id': row_id,
        'title': title,
        'work_kind': work_kind,
        'work_type_key': work_type_key,
        'work_type_label': work_type_label,
        'contract': contract,
        'contract_title': _safe_contract_title(contract),
        'contract_reference': reference or (f'#{contract.pk}' if contract else ''),
        'counterparty': _safe_counterparty(contract),
        'contract_type': contract.contract_type if contract else '',
        'assigned_date': assigned_date,
        'due_context': due_ctx,
        'status_label': status_label,
        'status_tone': _status_tone(status_label),
        'priority_label': priority_label,
        'priority_tone': priority_tone_for_label(priority_label),
        'priority_reason': priority_reason,
        'action_label': action_label,
        'action_href': action_href,
        'href': action_href,
        'assigned_by': assigned_by,
        'requestor': requestor or (contract.created_by if contract else None),
        'description': description,
        'workflow_stage': workflow_stage,
        'blocking_issue': blocking_issue,
        'blocker_owner': blocker_owner,
        'recent_activity': '',
        'delegation': delegation,
        'summary_tags': summary_tags,
        'is_returned': is_returned,
        'is_rejected': is_rejected,
        'is_blocked': is_blocked,
        'is_restricted': False,
        'reference': reference,
    }


def _attach_activity(rows, org):
    contract_ids = [row['contract'].pk for row in rows if row.get('contract')]
    activity_map = latest_activity_map(org, contract_ids)
    for row in rows:
        contract = row.get('contract')
        if not contract:
            continue
        log = activity_map.get(contract.pk)
        if not log:
            continue
        actor = 'System'
        if log.user:
            actor = log.user.get_full_name() or log.user.username
        row['recent_activity'] = f'{actor} {log.get_action_display().lower()} {log.model_name}'


def _assignee_fields(assignee):
    if assignee is None:
        return {'assignee_id': None, 'assignee_label': 'Unassigned'}
    return {
        'assignee_id': assignee.pk,
        'assignee_label': assignee.get_full_name() or assignee.username,
    }


def _collect_approval_rows(org, user, today, *, scope='personal'):
    from contracts.services.governance_ux import approval_blocker_for_request, sla_priority_reason

    rows = []
    qs = scope_queryset_for_organization(
        ApprovalRequest.objects.select_related(
            'contract', 'contract__created_by', 'assigned_to', 'delegated_to', 'rule',
        ),
        org,
    )
    pending = pending_approvals_queryset(org, user, queryset=qs, scope=scope)
    pending_list = list(pending)
    # Sibling open steps on the same contract — used for prior-step blockers.
    contract_ids = {a.contract_id for a in pending_list if a.contract_id}
    siblings_by_contract = {}
    if contract_ids:
        sibling_qs = qs.filter(
            contract_id__in=contract_ids,
            status__in=['PENDING', 'ESCALATED'],
        ).select_related('assigned_to', 'delegated_to')
        for step in sibling_qs:
            siblings_by_contract.setdefault(step.contract_id, []).append(step)

    for approval in pending_list:
        contract = approval.contract
        due = _date_only(approval.due_date)
        overdue = bool(due and due < today)
        sla_hours = approval.rule.sla_hours if approval.rule_id and approval.rule else None
        priority_reason = sla_priority_reason(
            due_date=due,
            today=today,
            sla_hours=sla_hours,
            overdue=overdue,
            risk_level=contract.risk_level if contract else '',
            escalated=approval.status == ApprovalRequest.Status.ESCALATED,
        )
        blocker = approval_blocker_for_request(
            approval,
            sibling_pending=siblings_by_contract.get(approval.contract_id),
        )
        row = _base_row(
            row_id=f'approval:{approval.pk}',
            title=f'Approve {approval.approval_step.replace("_", " ").strip().title()}',
            work_kind='approval',
            work_type_key='approvals',
            work_type_label='Approval',
            contract=contract,
            user=user,
            assigned_date=_date_only(approval.created_at),
            due_date=approval.due_date,
            assigned_by=contract.created_by if contract else None,
            requestor=contract.created_by if contract else None,
            description=approval.comments or f'Approval required for {approval.approval_step}.',
            workflow_stage='Approval',
            priority_reason=priority_reason,
            blocking_issue=blocker['blocking_issue'],
            blocker_owner=blocker['blocker_owner'],
            is_blocked=blocker['is_blocked'],
            action_href=reverse('contracts:approval_request_update', kwargs={'pk': approval.pk}),
            action_label='Approve',
            source_status=approval.status,
            priority_value=contract.risk_level if contract else 'HIGH' if approval.status == 'ESCALATED' else 'MEDIUM',
            delegation=_delegation_info(
                approval.assigned_to,
                approval.delegated_to,
                approval.delegated_at,
                reason=getattr(approval, 'delegation_reason', ''),
                ends_at=getattr(approval, 'delegation_ends_at', None),
            ),
            reference=f'APR-{approval.pk}',
            today=today,
        )
        if not row.get('is_restricted'):
            from contracts.permissions import can_manage_organization
            from contracts.services.approval_workflow import actor_can_decide
            can_decide = (
                approval.status in (ApprovalRequest.Status.PENDING, ApprovalRequest.Status.ESCALATED)
                and actor_can_decide(approval, user, 'approve')
            )
            row['can_decide'] = can_decide
            if can_decide:
                row['approve_url'] = reverse('contracts:approval_approve_api', kwargs={'approval_id': approval.pk})
                row['reject_url'] = reverse('contracts:approval_reject_api', kwargs={'approval_id': approval.pk})
                row['return_url'] = reverse(
                    'contracts:approval_request_changes_api', kwargs={'approval_id': approval.pk},
                )
                row['suggest_decision_url'] = reverse(
                    'contracts:approval_suggest_decision_api', kwargs={'approval_id': approval.pk},
                )
            can_reassign = (
                approval.status in (ApprovalRequest.Status.PENDING, ApprovalRequest.Status.ESCALATED)
                and can_manage_organization(user, org)
            )
            row['can_reassign'] = can_reassign
            if can_reassign:
                row['reassign_url'] = reverse(
                    'contracts:approval_reassign_api', kwargs={'approval_id': approval.pk},
                )
                row['current_assignee_id'] = approval.assigned_to_id
                row['current_assignee_label'] = (
                    (approval.assigned_to.get_full_name() or approval.assigned_to.username)
                    if approval.assigned_to_id else 'unassigned'
                )
            row.update(_assignee_fields(
                approval.delegated_to if approval.delegated_to_id else approval.assigned_to
            ))
        rows.append(row)

    if scope == 'team':
        return rows

    returned = qs.filter(
        status=ApprovalRequest.Status.CHANGES_REQUESTED,
        contract__created_by=user,
        contract__status=Contract.Status.IN_PROGRESS,
    )
    for approval in returned:
        contract = approval.contract
        rows.append(_base_row(
            row_id=f'approval-returned:{approval.pk}',
            title='Revise after requested changes',
            work_kind='returned',
            work_type_key='reviews',
            work_type_label='Review',
            contract=contract,
            user=user,
            assigned_date=_date_only(approval.created_at),
            due_date=approval.due_date,
            assigned_by=approval.decided_by,
            requestor=user,
            description=approval.comments or 'Changes were requested on this approval.',
            workflow_stage='Returned',
            priority_reason='Returned for correction',
            action_href=contract_detail_workflow_url(contract.pk, section='approvals') if contract else '',
            action_label='Correct',
            is_returned=True,
            source_status=approval.status,
            priority_value='HIGH',
            reference=f'APR-{approval.pk}',
            today=today,
        ))

    rejected = qs.filter(
        status=ApprovalRequest.Status.REJECTED,
        contract__created_by=user,
        contract__status=Contract.Status.IN_PROGRESS,
    )
    for approval in rejected:
        contract = approval.contract
        rows.append(_base_row(
            row_id=f'approval-rejected:{approval.pk}',
            title='Correct rejected contract request',
            work_kind='rejected',
            work_type_key='approvals',
            work_type_label='Approval',
            contract=contract,
            user=user,
            assigned_date=_date_only(approval.created_at),
            due_date=approval.due_date,
            assigned_by=approval.decided_by,
            requestor=user,
            description=approval.comments or 'This approval was rejected and requires correction.',
            workflow_stage='Rejected',
            priority_reason='Approval rejected',
            action_href=contract_detail_workflow_url(contract.pk, section='approvals') if contract else '',
            action_label='Correct',
            is_rejected=True,
            source_status=approval.status,
            priority_value='HIGH',
            reference=f'APR-{approval.pk}',
            today=today,
        ))
    return rows


def _collect_task_rows(org, user, today, *, scope='personal'):
    from contracts.services.governance_ux import sla_priority_reason

    rows = []
    tasks = open_tasks_queryset(org, user, scope=scope)
    for task in tasks:
        contract = task.contract
        due = _date_only(task.due_date)
        overdue = bool(due and due < today)
        priority_reason = sla_priority_reason(
            due_date=due,
            today=today,
            overdue=overdue,
            fallback=(
                task.get_priority_display() + ' priority task'
                if task.priority in ('HIGH', 'URGENT') else ''
            ),
        )
        row = _base_row(
            row_id=f'task:{task.pk}',
            title=task.title,
            work_kind='task',
            work_type_key='tasks',
            work_type_label='Task',
            contract=contract,
            user=user,
            assigned_date=_date_only(task.created_at),
            due_date=task.due_date,
            description=task.description,
            workflow_stage=task.get_status_display(),
            priority_reason=priority_reason,
            action_href=reverse('contracts:legal_task_update', kwargs={'pk': task.pk}),
            action_label='Complete',
            source_status=task.status,
            priority_value=task.priority,
            reference=f'TASK-{task.pk}',
            today=today,
        )
        if (
            not row.get('is_restricted')
            and task.status in (LegalTask.Status.PENDING, LegalTask.Status.IN_PROGRESS)
            and can_actor_complete_task(task, user, org)
        ):
            row['can_complete'] = True
            row['complete_url'] = reverse('contracts:legal_task_complete', kwargs={'pk': task.pk})
        if not row.get('is_restricted'):
            row.update(_assignee_fields(task.assigned_to))
        rows.append(row)
    return rows


def _collect_obligation_rows(org, user, today, *, scope='personal'):
    from contracts.services.governance_ux import obligation_blocker_for_deadline, sla_priority_reason

    rows = []
    deadlines = open_obligations_queryset(org, user, scope=scope)
    for deadline in deadlines:
        contract = deadline.contract
        title = deadline.title
        if deadline.deadline_type == Deadline.DeadlineType.RENEWAL:
            title = title or 'Complete renewal obligation'
        due = _date_only(deadline.due_date)
        overdue = bool(due and due < today)
        priority_reason = sla_priority_reason(
            due_date=due,
            today=today,
            overdue=overdue,
            fallback=(
                deadline.get_priority_display() + ' priority obligation'
                if deadline.priority in ('HIGH', 'CRITICAL') else ''
            ),
        )
        blocker = obligation_blocker_for_deadline(deadline, today=today)
        row = _base_row(
            row_id=f'obligation:{deadline.pk}',
            title=title,
            work_kind='obligation',
            work_type_key='obligations',
            work_type_label='Obligation',
            contract=contract,
            user=user,
            assigned_date=_date_only(deadline.created_at),
            due_date=deadline.due_date,
            assigned_by=deadline.created_by,
            description=deadline.description,
            workflow_stage=deadline.get_deadline_type_display(),
            priority_reason=priority_reason,
            blocking_issue=blocker['blocking_issue'],
            blocker_owner=blocker['blocker_owner'],
            is_blocked=blocker['is_blocked'],
            action_href=reverse('contracts:deadline_update', kwargs={'pk': deadline.pk}),
            action_label='Complete',
            source_status='OPEN',
            priority_value=deadline.priority,
            reference=f'OBL-{deadline.pk}',
            today=today,
        )
        if not row.get('is_restricted') and not deadline.is_completed:
            can_mutate = True
            if deadline.contract_id and not can_access_contract_action(
                user, deadline.contract, ContractAction.EDIT,
            ):
                can_mutate = False
            if can_mutate:
                row['can_complete'] = True
                row['complete_url'] = reverse('contracts:deadline_complete', kwargs={'pk': deadline.pk})
                row['defer_url'] = reverse('contracts:deadline_defer', kwargs={'pk': deadline.pk})
                row['escalate_url'] = reverse('contracts:deadline_escalate', kwargs={'pk': deadline.pk})
                row['deadline_id'] = deadline.pk
        if not row.get('is_restricted'):
            row.update(_assignee_fields(deadline.assigned_to))
        rows.append(row)
    return rows


def _collect_privacy_rows(org, user, today, *, scope='personal'):
    from contracts.services.governance_ux import privacy_blocker_for_pack

    rows = []
    packs = reviewer_privacy_packs_queryset(org, user, scope=scope).prefetch_related('risk_items')
    for pack in packs:
        contract = pack.contract
        risk_items = list(pack.risk_items.all())
        unresolved_critical = sum(
            1 for item in risk_items
            if getattr(item, 'severity', '') == 'CRITICAL'
            and getattr(item, 'status', '') not in ('RESOLVED', 'FALSE_POSITIVE')
        )
        conflict_count = sum(
            1 for item in risk_items
            if getattr(item, 'is_cross_document_conflict', False)
            and getattr(item, 'status', '') not in ('RESOLVED', 'FALSE_POSITIVE')
        )
        blocker = privacy_blocker_for_pack(
            pack,
            unresolved_critical=unresolved_critical,
            conflict_count=conflict_count,
        )
        priority_reason = ''
        if conflict_count:
            priority_reason = 'Cross-document conflicts blocking completion'
        elif pack.approval_status == DPAReviewPack.ApprovalStatus.ESCALATED:
            priority_reason = 'Privacy assessment blocking signature'
        elif unresolved_critical:
            priority_reason = f'{unresolved_critical} critical privacy risk{"s" if unresolved_critical != 1 else ""}'
        risks_href = f"{reverse('contracts:dpa_review_pack_detail', kwargs={'pk': pack.pk})}?tab=risks"
        row = _base_row(
            row_id=f'privacy:{pack.pk}',
            title='Answer privacy questionnaire' if pack.approval_status == DPAReviewPack.ApprovalStatus.DRAFT else 'Complete data transfer assessment',
            work_kind='privacy',
            work_type_key='privacy',
            work_type_label='Privacy',
            contract=contract,
            user=user,
            assigned_date=_date_only(pack.created_at if hasattr(pack, 'created_at') else None),
            due_date=None,
            description='Privacy review pack assigned to you.',
            workflow_stage=pack.get_approval_status_display(),
            priority_reason=priority_reason,
            blocking_issue=blocker['blocking_issue'],
            blocker_owner=blocker['blocker_owner'],
            is_blocked=blocker['is_blocked'],
            action_href=reverse('contracts:dpa_review_pack_detail', kwargs={'pk': pack.pk}),
            action_label='Review',
            source_status=pack.approval_status,
            priority_value='HIGH' if pack.approval_status == DPAReviewPack.ApprovalStatus.ESCALATED or conflict_count or unresolved_critical else 'MEDIUM',
            reference=f'DPA-{pack.pk}',
            today=today,
        )
        if not row.get('is_restricted') and conflict_count:
            row['risks_href'] = risks_href
        if not row.get('is_restricted'):
            row.update(_assignee_fields(pack.reviewer))
        rows.append(row)

    conflict_qs = DPARiskItem.objects.filter(
        review_pack__organization=org,
        is_cross_document_conflict=True,
    ).exclude(status__in=['RESOLVED', 'FALSE_POSITIVE']).select_related(
        'review_pack', 'review_pack__contract', 'review_pack__reviewer',
    )
    if scope != 'team':
        conflict_qs = conflict_qs.filter(review_pack__reviewer=user)
    for item in conflict_qs:
        pack = item.review_pack
        contract = pack.contract
        risks_href = f"{reverse('contracts:dpa_review_pack_detail', kwargs={'pk': pack.pk})}?tab=risks"
        status_url = reverse('contracts:dpa_risk_item_set_status', kwargs={'pk': item.pk})
        row = _base_row(
            row_id=f'privacy-conflict:{item.pk}',
            title=item.title or 'Review non-standard liability clause',
            work_kind='privacy',
            work_type_key='privacy',
            work_type_label='Privacy',
            contract=contract,
            user=user,
            assigned_date=_date_only(item.created_at if hasattr(item, 'created_at') else None),
            due_date=None,
            description=item.description,
            workflow_stage='Privacy review',
            priority_reason=item.get_severity_display() + ' severity finding' if hasattr(item, 'get_severity_display') else '',
            action_href=risks_href,
            action_label='Resolve',
            source_status=item.status,
            priority_value=getattr(item, 'severity', 'MEDIUM'),
            reference=f'DPA-{pack.pk}',
            today=today,
        )
        if not row.get('is_restricted'):
            row['can_resolve_conflict'] = True
            row['conflict_status_url'] = status_url
            row['risks_href'] = risks_href
            row['risk_item_id'] = item.pk
            row.update(_assignee_fields(pack.reviewer))
        rows.append(row)
    return rows


def _collect_review_rows(org, user, today, *, scope='personal'):
    rows = []
    findings = (
        ContractReviewFinding.objects
        .filter(contract__organization=org)
        .exclude(status__in=['RESOLVED', 'DISMISSED'])
        .select_related('contract', 'created_by', 'assigned_reviewer')
    )
    if scope != 'team':
        findings = findings.filter(assigned_reviewer=user)
    for finding in findings:
        contract = finding.contract
        is_question = finding.status == ContractReviewFinding.Status.INFORMATION_REQUESTED
        row = _base_row(
            row_id=f'finding:{finding.pk}',
            title=finding.title,
            work_kind='question' if is_question else 'finding',
            work_type_key='questions' if is_question else 'reviews',
            work_type_label='Question' if is_question else 'Review',
            contract=contract,
            user=user,
            assigned_date=_date_only(finding.created_at),
            due_date=None,
            assigned_by=finding.created_by,
            description=finding.explanation or finding.recommended_action,
            workflow_stage=finding.get_status_display(),
            priority_reason=finding.get_severity_display() + ' severity finding',
            action_href=contract_detail_workflow_url(contract.pk, section='review'),
            action_label='Respond' if is_question else 'Review',
            source_status=finding.status,
            is_question=is_question,
            priority_value=finding.severity,
            reference=f'FIND-{finding.pk}',
            today=today,
        )
        if not row.get('is_restricted'):
            row.update(_assignee_fields(finding.assigned_reviewer))
        rows.append(row)
    return rows


def _collect_workflow_step_rows(org, user, today, *, scope='personal'):
    rows = []
    steps = (
        WorkflowStep.objects
        .filter(
            workflow__organization=org,
            status__in=[
                WorkflowStep.Status.PENDING,
                WorkflowStep.Status.IN_PROGRESS,
                WorkflowStep.Status.ESCALATED,
            ],
        )
        .select_related('workflow', 'workflow__contract', 'assigned_to')
    )
    if scope != 'team':
        steps = steps.filter(assigned_to=user)
    for step in steps:
        contract = step.workflow.contract if step.workflow else None
        blocked = bool(step.blocked_reason)
        row = _base_row(
            row_id=f'workflow-step:{step.pk}',
            title=step.name,
            work_kind='review',
            work_type_key='reviews',
            work_type_label='Review',
            contract=contract,
            user=user,
            assigned_date=None,
            due_date=step.due_date,
            description=step.description,
            workflow_stage=step.workflow.title if step.workflow else '',
            priority_reason='Renewal deadline approaching' if step.name and 'renewal' in step.name.lower() else '',
            blocking_issue=step.blocked_reason,
            blocker_owner=step.assigned_to.get_full_name() if blocked and step.assigned_to else '',
            action_href=reverse('contracts:workflow_step_update', kwargs={'pk': step.pk}),
            action_label='Review',
            source_status=step.status,
            is_blocked=blocked,
            priority_value='HIGH' if step.status == WorkflowStep.Status.ESCALATED else 'MEDIUM',
            reference=f'WF-{step.pk}',
            today=today,
        )
        if not row.get('is_restricted'):
            row.update(_assignee_fields(step.assigned_to))
        rows.append(row)
    return rows


def _dedupe_rows(rows):
    seen = set()
    result = []
    for row in rows:
        if row['id'] in seen:
            continue
        seen.add(row['id'])
        result.append(row)
    return result


def _sort_rows(rows, today, org_overdue_rates=None):
    return sorted(rows, key=lambda row: _sort_key(row, today, org_overdue_rates=org_overdue_rates))


def build_summary_counts(rows):
    counts = {key: 0 for key, _ in SUMMARY_FILTERS}
    for row in rows:
        for tag in row.get('summary_tags') or []:
            if tag in counts:
                counts[tag] += 1
    return counts


TEAM_QUEUE_ROW_LIMIT = 250


def get_active_work_items(organization, user, *, today=None, scope='personal', row_limit=None):
    """Return active work rows for personal or team scope.

    Team scope is capped (``TEAM_QUEUE_ROW_LIMIT``) so org-wide triage stays
    responsive; callers can read ``truncated`` via ``get_active_work_items_result``.
    """
    result = get_active_work_items_result(
        organization, user, today=today, scope=scope, row_limit=row_limit,
    )
    return result['rows']


def get_active_work_items_result(organization, user, *, today=None, scope='personal', row_limit=None):
    if organization is None or user is None or not getattr(user, 'is_authenticated', False):
        return {'rows': [], 'truncated': False, 'scope': 'personal', 'total_before_cap': 0}
    if get_active_org_membership(user, organization) is None:
        return {'rows': [], 'truncated': False, 'scope': 'personal', 'total_before_cap': 0}

    scope = 'team' if scope == 'team' else 'personal'
    today = today or timezone.localdate()
    rows = []
    rows.extend(_collect_approval_rows(organization, user, today, scope=scope))
    rows.extend(_collect_task_rows(organization, user, today, scope=scope))
    rows.extend(_collect_obligation_rows(organization, user, today, scope=scope))
    rows.extend(_collect_privacy_rows(organization, user, today, scope=scope))
    rows.extend(_collect_review_rows(organization, user, today, scope=scope))
    rows.extend(_collect_workflow_step_rows(organization, user, today, scope=scope))
    rows = _dedupe_rows(rows)

    # Team queues can be large — skip expensive activity fan-out when over half cap.
    limit = TEAM_QUEUE_ROW_LIMIT if row_limit is None else max(1, int(row_limit))
    if scope != 'team' or len(rows) <= max(50, limit // 2):
        _attach_activity(rows, organization)
    org_overdue_rates = None
    try:
        from contracts.services.work_instrumentation import overdue_rate_by_work_type
        org_overdue_rates = overdue_rate_by_work_type(organization, days=30)
    except Exception:
        org_overdue_rates = None
    rows = _sort_rows(rows, today, org_overdue_rates=org_overdue_rates)
    total = len(rows)
    truncated = False
    if scope == 'team' and total > limit:
        rows = rows[:limit]
        truncated = True
    return {
        'rows': rows,
        'truncated': truncated,
        'scope': scope,
        'total_before_cap': total,
        'row_limit': limit if scope == 'team' else None,
    }


def get_recently_completed_items(organization, user, *, today=None, days=RECENTLY_COMPLETED_DAYS):
    if organization is None or user is None or not getattr(user, 'is_authenticated', False):
        return []
    if get_active_org_membership(user, organization) is None:
        return []

    today = today or timezone.localdate()
    cutoff = timezone.now() - timedelta(days=days)
    completed = []

    approvals = scope_queryset_for_organization(
        ApprovalRequest.objects.select_related('contract'),
        organization,
    ).filter(decided_by=user, decided_at__gte=cutoff, status__in=[
        ApprovalRequest.Status.APPROVED,
        ApprovalRequest.Status.REJECTED,
    ])
    for approval in approvals:
        contract = approval.contract
        if contract and not _contract_accessible(user, contract):
            continue
        completed.append({
            'id': f'approval-completed:{approval.pk}',
            'title': f'{approval.get_status_display()} · {approval.approval_step}',
            'contract_title': _safe_contract_title(contract),
            'work_type_label': 'Approval',
            'completed_at': approval.decided_at,
            'outcome': approval.get_status_display(),
            'href': reverse('contracts:approval_request_update', kwargs={'pk': approval.pk}),
        })

    deadlines = (
        Deadline.objects.for_organization(organization)
        .select_related('contract')
        .filter(completed_by=user, completed_at__gte=cutoff, is_completed=True)
    )
    for deadline in deadlines:
        contract = deadline.contract
        if contract and not _contract_accessible(user, contract):
            continue
        completed.append({
            'id': f'obligation-completed:{deadline.pk}',
            'title': deadline.title,
            'contract_title': _safe_contract_title(contract),
            'work_type_label': 'Obligation',
            'completed_at': deadline.completed_at,
            'outcome': 'Completed',
            'href': reverse('contracts:deadline_update', kwargs={'pk': deadline.pk}),
        })

    tasks = (
        LegalTask.objects.for_organization(organization)
        .select_related('contract')
        .filter(assigned_to=user, status=LegalTask.Status.COMPLETED, updated_at__gte=cutoff)
    )
    for task in tasks:
        contract = task.contract
        if contract and not _contract_accessible(user, contract):
            continue
        completed.append({
            'id': f'task-completed:{task.pk}',
            'title': task.title,
            'contract_title': _safe_contract_title(contract),
            'work_type_label': 'Task',
            'completed_at': task.updated_at,
            'outcome': 'Completed',
            'href': reverse('contracts:legal_task_update', kwargs={'pk': task.pk}),
        })

    findings = (
        ContractReviewFinding.objects
        .filter(contract__organization=organization, resolved_by=user, resolved_at__gte=cutoff)
        .select_related('contract')
    )
    for finding in findings:
        contract = finding.contract
        if contract and not _contract_accessible(user, contract):
            continue
        completed.append({
            'id': f'finding-completed:{finding.pk}',
            'title': finding.title,
            'contract_title': _safe_contract_title(contract),
            'work_type_label': 'Review',
            'completed_at': finding.resolved_at,
            'outcome': finding.get_status_display(),
            'href': reverse('contracts:contract_detail', kwargs={'pk': contract.pk}),
        })

    return sorted(completed, key=lambda row: row.get('completed_at') or timezone.now(), reverse=True)


def build_filter_options(rows):
    contract_types = sorted({row['contract_type'] for row in rows if row.get('contract_type')})
    counterparties = sorted({row['counterparty'] for row in rows if row.get('counterparty')})
    assigners = []
    assignees = []
    seen_assigners = set()
    seen_assignees = set()
    for row in rows:
        user = row.get('assigned_by')
        if user and user.pk not in seen_assigners:
            seen_assigners.add(user.pk)
            assigners.append({
                'id': user.pk,
                'label': user.get_full_name() or user.username,
            })
        assignee_id = row.get('assignee_id')
        if assignee_id and assignee_id not in seen_assignees:
            seen_assignees.add(assignee_id)
            assignees.append({
                'id': assignee_id,
                'label': row.get('assignee_label') or f'User {assignee_id}',
            })
    assigners.sort(key=lambda item: item['label'].casefold())
    assignees.sort(key=lambda item: item['label'].casefold())
    return {
        'contract_types': contract_types,
        'counterparties': counterparties,
        'assigners': assigners,
        'assignees': assignees,
    }
