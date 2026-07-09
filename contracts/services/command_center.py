"""Command Center data projection helpers.

The dashboard should read a stable legal-ops workbench contract, not re-invent
queue semantics in the template. These helpers expose persisted Command Center
records when present and keep a non-mutating fallback for existing workspaces
that have not been projected yet.
"""

from datetime import date, datetime, time, timedelta

from django.urls import reverse
from django.utils import timezone

from contracts.models import (
    ApprovalRequest,
    CommandCenterRailItem,
    CommandCenterSavedView,
    CommandCenterWorkItem,
    Contract,
    Deadline,
    DPARiskItem,
    DPAReviewPack,
    ReviewMemo,
)


DEFAULT_SAVED_VIEWS = [
    {
        'key': 'all',
        'name': 'All',
        'description': 'All open legal work',
        'filters': {'status': ['OPEN', 'IN_PROGRESS', 'BLOCKED']},
        'is_default': True,
        'sort_order': 10,
    },
    {
        'key': 'mine',
        'name': 'My Queue',
        'description': 'Work assigned to the current user',
        'filters': {'owner': 'current_user'},
        'sort_order': 20,
    },
    {
        'key': 'dpa',
        'name': 'DPA Conflicts',
        'description': 'Cross-document DPA/MSA findings',
        'filters': {'source_type': 'DPA_CONFLICT'},
        'sort_order': 30,
    },
    {
        'key': 'high-risk',
        'name': 'High Risk',
        'description': 'High and critical legal risk',
        'filters': {'risk_level': ['HIGH', 'CRITICAL']},
        'sort_order': 40,
    },
    {
        'key': 'renewals',
        'name': 'Renewals',
        'description': 'Renewal and notice-window work',
        'filters': {'source_type': 'DEADLINE'},
        'sort_order': 50,
    },
    {
        'key': 'waiting',
        'name': 'Waiting on Business',
        'description': 'Business input, approvals, or blockers',
        'filters': {'status': ['BLOCKED'], 'source_type': ['APPROVAL']},
        'sort_order': 60,
    },
]

DEFAULT_RAIL_ITEMS = [
    {
        'kind': 'APPROVALS',
        'title': 'Blocking approvals',
        'summary': 'Business approvals assigned to you or waiting on owners.',
        'action_path': None,
        'sort_order': 10,
    },
    {
        'kind': 'DEADLINES',
        'title': 'Upcoming notice dates',
        'summary': 'Renewals, notice windows, and obligation deadlines.',
        'action_path': None,
        'sort_order': 20,
    },
    {
        'kind': 'DPA_CONFLICTS',
        'title': 'DPA / MSA conflicts',
        'summary': 'Cross-document findings ranked by legal severity.',
        'action_path': None,
        'sort_order': 30,
    },
    {
        'kind': 'REVIEW_MEMOS',
        'title': 'Recent review memos',
        'summary': 'Generated legal summaries ready for review or export.',
        'action_path': None,
        'sort_order': 40,
    },
]


def get_command_center_saved_views(organization):
    if not organization:
        return DEFAULT_SAVED_VIEWS
    rows = list(
        CommandCenterSavedView.objects
        .filter(organization=organization)
        .order_by('sort_order', 'name')
        .values('key', 'name', 'description', 'filters', 'is_default', 'sort_order')
    )
    return rows or DEFAULT_SAVED_VIEWS


def _date_from_datetime(value):
    if value is None:
        return None
    if hasattr(value, 'date'):
        return value.date()
    return value


def _format_due_label(due_date, today):
    if not due_date:
        return 'No due date'
    if due_date < today:
        return 'Overdue'
    if due_date == today:
        return 'Today'
    delta_days = (due_date - today).days
    if delta_days <= 7:
        return f'{delta_days} day' if delta_days == 1 else f'{delta_days} days'
    return due_date.strftime('%d %b %Y')


def _format_due_note(due_date, today):
    if not due_date:
        return 'No SLA'
    if due_date < today:
        return due_date.strftime('%d %b %Y')
    if due_date == today:
        return 'Requires action today'
    delta_days = (due_date - today).days
    if delta_days <= 7:
        return 'Due this week'
    if delta_days <= 30:
        return 'Due this month'
    return due_date.strftime('%d %b %Y')


def _derive_work_type(item, contract_type, risk_personality):
    if item.source_type == CommandCenterWorkItem.SourceType.WORKFLOW:
        if contract_type == 'DPA':
            return 'DPA review'
        if contract_type == 'MSA':
            return 'Legal review'
        if contract_type == 'NDA' and risk_personality == 'Self-serve eligible':
            return 'Signature'
        return 'Workflow'
    if item.source_type == CommandCenterWorkItem.SourceType.APPROVAL:
        return 'Approval'
    if item.source_type == CommandCenterWorkItem.SourceType.DEADLINE:
        return 'Renewal'
    if item.source_type == CommandCenterWorkItem.SourceType.DPA_CONFLICT:
        return 'Privacy review'
    if item.source_type == CommandCenterWorkItem.SourceType.RISK:
        return 'Risk review'
    return item.item_type or item.get_source_type_display()


def _work_item_href(item):
    if item.action_path:
        return item.action_path
    if item.contract_id:
        return reverse('contracts:contract_detail', kwargs={'pk': item.contract_id})
    if item.dpa_review_pack_id:
        return reverse('contracts:dpa_review_pack_detail', kwargs={'pk': item.dpa_review_pack_id})
    if item.approval_request_id:
        return reverse('contracts:approval_request_update', kwargs={'pk': item.approval_request_id})
    if item.deadline_id:
        return reverse('contracts:deadline_update', kwargs={'pk': item.deadline_id})
    if item.legal_task_id:
        return reverse('contracts:legal_task_update', kwargs={'pk': item.legal_task_id})
    if item.risk_log_id:
        return reverse('contracts:risk_log_update', kwargs={'pk': item.risk_log_id})
    return reverse('contracts:contract_list')


def command_center_work_item_to_row(item, current_user=None, today=None):
    due_date = _date_from_datetime(item.due_at)
    today = today or date.today()
    contract = item.contract
    flags = item.flags or {}
    contract_type = flags.get('contract_type') or (contract.contract_type if contract else '')
    risk_personality = flags.get('risk_personality', '')
    highest_risk_signal = flags.get('highest_risk_signal', '')
    blocking_issue = flags.get('blocking_issue', item.subtitle)
    next_action = flags.get('next_action', item.action_label)
    if item.stage:
        stage = item.stage
    elif contract:
        stage = contract.get_lifecycle_stage_display()
    else:
        stage = item.get_status_display()
    counterparty = ''
    if contract:
        counterparty = contract.counterparty
    elif item.dpa_review_pack and item.dpa_review_pack.counterparty:
        counterparty = item.dpa_review_pack.counterparty.name

    if not risk_personality:
        if flags.get('self_serve_eligible'):
            risk_personality = 'Self-serve eligible'
        elif contract_type == 'DPA':
            risk_personality = 'Privacy risk'
        elif contract_type == 'MSA':
            risk_personality = 'Commercial risk'
        elif contract_type == 'NDA' and (highest_risk_signal or '').lower() == 'self-serve eligible':
            risk_personality = 'Self-serve eligible'

    if not highest_risk_signal and risk_personality == 'Self-serve eligible':
        highest_risk_signal = 'No legal risk detected'

    work_type = _derive_work_type(item, contract_type, risk_personality)

    return {
        'title': item.title,
        'href': _work_item_href(item),
        'workspace_href': _work_item_href(item),
        'edit_href': _work_item_href(item),
        'meta': item.subtitle,
        'contract': contract,
        'assignee': item.owner,
        'owner_label': flags.get('owner_label') or (
            item.owner.get_full_name() or item.owner.username if item.owner else 'Unassigned'
        ),
        'owner_role': '',
        'activity': None,
        'due_date': due_date,
        'due_overdue': bool(due_date and due_date < today),
        'due_today': bool(due_date and due_date == today),
        'status_label': item.get_status_display(),
        'status_badge_class': 'badge-red' if item.status == CommandCenterWorkItem.Status.BLOCKED else 'badge-blue',
        'action_label': item.action_label,
        'item_type': item.item_type or item.get_source_type_display(),
        'work_type': work_type,
        'contract_type': contract_type,
        'stage': stage,
        'current_stage': flags.get('current_stage', stage),
        'risk_level': item.risk_level,
        'risk_label': item.get_risk_level_display() if item.risk_level else 'No legal risk detected',
        'risk_personality': risk_personality,
        'highest_risk_signal': highest_risk_signal,
        'blocking_issue': blocking_issue,
        'next_action': next_action,
        'approval_route': flags.get('approval_route', ''),
        'counterparty': counterparty,
        'due_label': _format_due_label(due_date, today),
        'due_note': _format_due_note(due_date, today),
        'is_workflow': item.source_type == CommandCenterWorkItem.SourceType.WORKFLOW,
        'filter_mine': bool(current_user and item.owner_id == current_user.id),
        'filter_dpa': item.source_type == CommandCenterWorkItem.SourceType.DPA_CONFLICT or (contract and contract.contract_type == 'DPA'),
        'filter_high_risk': item.risk_level in ('HIGH', 'CRITICAL'),
        'filter_renewals': item.source_type == CommandCenterWorkItem.SourceType.DEADLINE or bool(due_date),
        'filter_waiting': item.status == CommandCenterWorkItem.Status.BLOCKED or item.source_type == CommandCenterWorkItem.SourceType.APPROVAL or bool(flags.get('waiting_on_business')),
    }


def get_persisted_command_center_rows(organization, current_user=None, limit=50, today=None):
    if not organization:
        return []
    items = (
        CommandCenterWorkItem.objects
        .filter(organization=organization, status__in=[
            CommandCenterWorkItem.Status.OPEN,
            CommandCenterWorkItem.Status.IN_PROGRESS,
            CommandCenterWorkItem.Status.BLOCKED,
        ])
        .select_related(
            'owner',
            'contract',
            'dpa_review_pack',
            'dpa_review_pack__counterparty',
            'approval_request',
            'deadline',
            'legal_task',
            'risk_log',
        )
        .order_by('-priority', 'due_at', '-updated_at')[:limit]
    )
    return [command_center_work_item_to_row(item, current_user=current_user, today=today) for item in items]


def get_workflow_type_summary(rows):
    workflow_rows = [row for row in (rows or []) if row.get('is_workflow')]
    return {
        'privacy_reviews': sum(1 for row in workflow_rows if row.get('risk_personality') == 'Privacy risk'),
        'commercial_reviews': sum(1 for row in workflow_rows if row.get('risk_personality') == 'Commercial risk'),
        'self_serve_ready': sum(1 for row in workflow_rows if row.get('risk_personality') == 'Self-serve eligible'),
        'blocking_approvals': sum(1 for row in workflow_rows if row.get('status_label') == 'Blocked'),
    }


def get_command_center_rail_items(organization, counts):
    paths = {
        'APPROVALS': reverse('contracts:approval_request_list'),
        'DEADLINES': reverse('contracts:deadline_list'),
        'DPA_CONFLICTS': reverse('contracts:dpa_review_pack_list'),
        'REVIEW_MEMOS': reverse('contracts:dpa_review_pack_list'),
        'RISK': reverse('contracts:risk_log_list'),
    }
    if organization:
        rows = list(CommandCenterRailItem.objects.filter(organization=organization, is_active=True).order_by('sort_order', 'title'))
        if rows:
            return [
                {
                    'kind': row.kind,
                    'title': row.title,
                    'summary': row.summary,
                    'count': row.count,
                    'severity': row.severity,
                    'action_label': row.action_label,
                    'action_path': row.action_path or paths.get(row.kind, reverse('contracts:legal_task_kanban')),
                }
                for row in rows
            ]

    count_by_kind = {
        'APPROVALS': counts.get('approvals', 0),
        'DEADLINES': counts.get('deadlines', 0),
        'DPA_CONFLICTS': counts.get('dpa_conflicts', 0),
        'REVIEW_MEMOS': counts.get('review_memos', 0),
    }
    return [
        {
            **entry,
            'count': count_by_kind.get(entry['kind'], 0),
            'severity': 'LOW',
            'action_label': 'Open',
            'action_path': paths.get(entry['kind'], reverse('contracts:legal_task_kanban')),
        }
        for entry in DEFAULT_RAIL_ITEMS
    ]


def get_recent_review_memos(organization, fallback_packs=None, limit=5):
    if not organization:
        return []
    memos = list(
        ReviewMemo.objects
        .filter(organization=organization)
        .select_related('contract', 'dpa_review_pack')
        .order_by('-generated_at')[:limit]
    )
    if memos:
        return memos
    return list(fallback_packs or [])


def _aware_date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    return timezone.make_aware(datetime.combine(value, time.min))


def _priority_for_risk(risk_level):
    return {
        'CRITICAL': CommandCenterWorkItem.Priority.CRITICAL,
        'HIGH': CommandCenterWorkItem.Priority.HIGH,
        'MEDIUM': CommandCenterWorkItem.Priority.MEDIUM,
        'LOW': CommandCenterWorkItem.Priority.LOW,
    }.get(risk_level, CommandCenterWorkItem.Priority.MEDIUM)


def ensure_default_saved_views(organization, created_by=None):
    if not organization:
        return []
    rows = []
    for entry in DEFAULT_SAVED_VIEWS:
        row, _ = CommandCenterSavedView.objects.update_or_create(
            organization=organization,
            key=entry['key'],
            defaults={
                'name': entry['name'],
                'description': entry['description'],
                'filters': entry['filters'],
                'is_default': entry.get('is_default', False),
                'sort_order': entry['sort_order'],
                'created_by': created_by,
            },
        )
        rows.append(row)
    return rows


def refresh_command_center_projection(organization, actor=None, today=None):
    """Refresh persisted Command Center projections from existing source rows.

    This is deliberately deterministic and non-advisory: it copies the current
    state of existing DPA findings, approvals, deadlines, contracts, and memos
    into normalized dashboard rows. It does not run scanners, change approval
    state, or advance lifecycle stages.
    """

    if not organization:
        return {'saved_views': 0, 'work_items': 0, 'rail_items': 0, 'review_memos': 0}

    today = today or timezone.localdate()
    thirty_days = today + timedelta(days=30)
    ensure_default_saved_views(organization, created_by=actor)
    work_item_count = 0

    conflict_qs = (
        DPARiskItem.objects
        .filter(review_pack__organization=organization, is_cross_document_conflict=True)
        .exclude(status__in=['RESOLVED', 'FALSE_POSITIVE'])
        .select_related('review_pack', 'review_pack__contract', 'review_pack__counterparty')
    )
    for item in conflict_qs:
        pack = item.review_pack
        contract = pack.contract
        CommandCenterWorkItem.objects.update_or_create(
            organization=organization,
            source_type=CommandCenterWorkItem.SourceType.DPA_CONFLICT,
            source_model='DPARiskItem',
            source_object_id=item.pk,
            defaults={
                'title': item.title,
                'subtitle': item.description[:300],
                'item_type': 'DPA conflict',
                'stage': 'Counsel review',
                'status': CommandCenterWorkItem.Status.BLOCKED if item.severity in ('HIGH', 'CRITICAL') else CommandCenterWorkItem.Status.OPEN,
                'risk_level': item.severity,
                'priority': _priority_for_risk(item.severity),
                'contract': contract,
                'dpa_review_pack': pack,
                'dpa_risk_item': item,
                'action_label': 'Resolve',
                'action_path': reverse('contracts:dpa_review_pack_detail', kwargs={'pk': pack.pk}),
                'flags': {'dpa_conflict': True, 'waiting_on_business': item.status == 'NEEDS_BUSINESS_INPUT'},
                'last_source_synced_at': timezone.now(),
            },
        )
        work_item_count += 1

    approval_qs = (
        ApprovalRequest.objects
        .filter(organization=organization, status=ApprovalRequest.Status.PENDING)
        .select_related('contract', 'assigned_to')
    )
    for approval in approval_qs:
        CommandCenterWorkItem.objects.update_or_create(
            organization=organization,
            source_type=CommandCenterWorkItem.SourceType.APPROVAL,
            source_model='ApprovalRequest',
            source_object_id=approval.pk,
            defaults={
                'title': approval.contract.title,
                'subtitle': f'Approval · {approval.approval_step}',
                'item_type': 'Approval',
                'stage': 'Approval',
                'status': CommandCenterWorkItem.Status.BLOCKED if approval.due_date and approval.due_date < timezone.now() else CommandCenterWorkItem.Status.OPEN,
                'risk_level': approval.contract.risk_level,
                'priority': _priority_for_risk(approval.contract.risk_level),
                'owner': approval.assigned_to,
                'contract': approval.contract,
                'approval_request': approval,
                'due_at': approval.due_date,
                'action_label': 'Approve',
                'action_path': reverse('contracts:approval_request_update', kwargs={'pk': approval.pk}),
                'flags': {'waiting_on_business': True},
                'last_source_synced_at': timezone.now(),
            },
        )
        work_item_count += 1

    deadline_qs = (
        Deadline.objects
        .for_organization(organization)
        .filter(is_completed=False, due_date__gte=today, due_date__lte=thirty_days)
        .select_related('contract', 'matter', 'assigned_to')
    )
    for deadline in deadline_qs:
        contract = deadline.contract
        CommandCenterWorkItem.objects.update_or_create(
            organization=organization,
            source_type=CommandCenterWorkItem.SourceType.DEADLINE,
            source_model='Deadline',
            source_object_id=deadline.pk,
            defaults={
                'title': deadline.title,
                'subtitle': 'Deadline · renewal / notice window',
                'item_type': 'Deadline',
                'stage': 'Renewal',
                'status': CommandCenterWorkItem.Status.BLOCKED if deadline.due_date < today else CommandCenterWorkItem.Status.OPEN,
                'risk_level': contract.risk_level if contract else Contract.RiskLevel.MEDIUM,
                'priority': _priority_for_risk(contract.risk_level if contract else Contract.RiskLevel.MEDIUM),
                'owner': deadline.assigned_to,
                'contract': contract,
                'deadline': deadline,
                'due_at': _aware_date(deadline.due_date),
                'action_label': 'Review',
                'action_path': reverse('contracts:deadline_update', kwargs={'pk': deadline.pk}),
                'flags': {'renewal': deadline.deadline_type == Deadline.DeadlineType.RENEWAL},
                'last_source_synced_at': timezone.now(),
            },
        )
        work_item_count += 1

    contract_qs = (
        Contract.objects
        .filter(organization=organization, status__in=[Contract.Status.PENDING, Contract.Status.IN_REVIEW])
        .order_by('-updated_at')[:100]
    )
    for contract in contract_qs:
        CommandCenterWorkItem.objects.update_or_create(
            organization=organization,
            source_type=CommandCenterWorkItem.SourceType.CONTRACT,
            source_model='Contract',
            source_object_id=contract.pk,
            defaults={
                'title': contract.title,
                'subtitle': contract.counterparty,
                'item_type': contract.get_contract_type_display(),
                'stage': contract.get_lifecycle_stage_display(),
                'status': CommandCenterWorkItem.Status.OPEN,
                'risk_level': contract.risk_level,
                'priority': _priority_for_risk(contract.risk_level),
                'contract': contract,
                'due_at': _aware_date(contract.end_date),
                'action_label': 'Review',
                'action_path': reverse('contracts:contract_detail', kwargs={'pk': contract.pk}),
                'flags': {},
                'last_source_synced_at': timezone.now(),
            },
        )
        work_item_count += 1

    review_memo_count = 0
    for pack in (
        DPAReviewPack.objects
        .filter(organization=organization, review_memo_generated_at__isnull=False)
        .select_related('contract')
    ):
        memo, _ = ReviewMemo.objects.update_or_create(
            organization=organization,
            dpa_review_pack=pack,
            defaults={
                'title': f'DPA review memo · {pack.contract.title}',
                'memo_type': ReviewMemo.MemoType.DPA_REVIEW,
                'body': pack.review_memo,
                'contract': pack.contract,
                'generated_at': pack.review_memo_generated_at,
                'source': 'DPAReviewPack.review_memo',
            },
        )
        CommandCenterWorkItem.objects.update_or_create(
            organization=organization,
            source_type=CommandCenterWorkItem.SourceType.REVIEW_MEMO,
            source_model='ReviewMemo',
            source_object_id=memo.pk,
            defaults={
                'title': memo.title,
                'subtitle': 'Review memo ready',
                'item_type': 'Review memo',
                'stage': 'Memo',
                'status': CommandCenterWorkItem.Status.OPEN,
                'risk_level': Contract.RiskLevel.LOW,
                'priority': CommandCenterWorkItem.Priority.LOW,
                'contract': memo.contract,
                'dpa_review_pack': pack,
                'action_label': 'Open memo',
                'action_path': reverse('contracts:dpa_review_pack_memo', kwargs={'pk': pack.pk}),
                'flags': {},
                'last_source_synced_at': timezone.now(),
            },
        )
        work_item_count += 1
        review_memo_count += 1

    rail_counts = {
        'APPROVALS': approval_qs.count(),
        'DEADLINES': deadline_qs.count(),
        'DPA_CONFLICTS': conflict_qs.count(),
        'REVIEW_MEMOS': ReviewMemo.objects.filter(organization=organization).count(),
    }
    rail_meta = {item['kind']: item for item in DEFAULT_RAIL_ITEMS}
    for kind, count in rail_counts.items():
        entry = rail_meta[kind]
        CommandCenterRailItem.objects.update_or_create(
            organization=organization,
            kind=kind,
            defaults={
                'title': entry['title'],
                'summary': entry['summary'],
                'count': count,
                'severity': Contract.RiskLevel.HIGH if kind == 'DPA_CONFLICTS' and count else Contract.RiskLevel.LOW,
                'action_path': {
                    'APPROVALS': reverse('contracts:approval_request_list'),
                    'DEADLINES': reverse('contracts:deadline_list'),
                    'DPA_CONFLICTS': reverse('contracts:dpa_review_pack_list'),
                    'REVIEW_MEMOS': reverse('contracts:dpa_review_pack_list'),
                }[kind],
                'sort_order': entry['sort_order'],
                'generated_at': timezone.now(),
            },
        )

    return {
        'saved_views': len(DEFAULT_SAVED_VIEWS),
        'work_items': work_item_count,
        'rail_items': len(rail_counts),
        'review_memos': review_memo_count,
    }
