"""Command Center data projection helpers.

The dashboard should read a stable legal-ops workbench contract, not re-invent
queue semantics in the template. These helpers expose persisted Command Center
records when present and keep a non-mutating fallback for existing workspaces
that have not been projected yet.
"""

from datetime import date, datetime, time, timedelta
import re

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

COMPACT_LIFECYCLE_LABELS = {
    'DRAFTING': 'Draft',
    'INTERNAL_REVIEW': 'Legal Review',
    'NEGOTIATION': 'Legal Review',
    'APPROVAL': 'Approval',
    'SIGNATURE': 'Signature',
    'EXECUTED': 'Active',
    'OBLIGATION_TRACKING': 'Active',
    'RENEWAL': 'Renewal',
    'ARCHIVED': 'Archived',
}

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

RISK_RANK = {'CRITICAL': 4, 'HIGH': 3, 'MEDIUM': 2, 'LOW': 1}


def rank_command_center_rows(rows, today=None):
    """Return a deterministic urgency ordering for accessible work items."""
    today = today or date.today()

    def key(row):
        due_date = row.get('due_date')
        return (
            0 if row.get('due_overdue') else 1,
            0 if row.get('status_label') == 'Blocked' else 1,
            -(row.get('priority') or 0),
            -RISK_RANK.get(row.get('risk_level'), 0),
            due_date or date.max,
            row.get('updated_at') or (timezone.now() + timedelta(days=36500)),
            (row.get('title') or '').casefold(),
            row.get('workspace_href') or row.get('href') or '',
        )

    return sorted(rows or [], key=key)


def governed_recommendation(row):
    """Separate persisted risk evidence from the governed next action."""
    blocker = (row.get('blocking_issue') or '').strip()
    blocker_lower = blocker.lower()
    meaningful = blocker and not blocker_lower.startswith('no legal risk detected')
    finance_threshold = re.search(r'finance approval threshold of\s+([\d,.]+)', blocker, re.IGNORECASE)
    if finance_threshold:
        threshold = finance_threshold.group(1).rstrip('.,')
        return {
            'explanation': f'Contract value exceeds the €{threshold} approval threshold.',
            'title': 'Finance approval required',
            'action': 'Route to Finance Director for approval.',
        }
    if 'liability' in blocker_lower:
        return {
            'explanation': blocker,
            'title': 'Review liability deviation',
            'action': row.get('next_action') or 'Review the liability position.',
        }
    if 'scc' in blocker_lower or 'transfer' in blocker_lower:
        return {
            'explanation': blocker,
            'title': 'Confirm SCC transfer position',
            'action': row.get('next_action') or 'Confirm the governed transfer position.',
        }
    next_action = row.get('next_action') or 'Open review'
    return {
        'explanation': blocker if meaningful else row.get('highest_risk_signal') or 'Action is required.',
        'title': next_action,
        'action': next_action,
    }


def explainable_risk_score(risk_level, contributors, history=None):
    """Compose one explainable score from persisted contributor counts."""
    counts = {
        'high_risk_deviations': max(0, int(contributors.get('high_risk_deviations', 0))),
        'pending_approvals': max(0, int(contributors.get('pending_approvals', 0))),
        'dpa_conflicts': max(0, int(contributors.get('dpa_conflicts', 0))),
        'unresolved_blockers': max(0, int(contributors.get('unresolved_blockers', 0))),
        'expired_exceptions': max(0, int(contributors.get('expired_exceptions', 0))),
        'missing_approval_authority': max(0, int(contributors.get('missing_approval_authority', 0))),
    }
    score = {'CRITICAL': 58, 'HIGH': 42, 'MEDIUM': 24, 'LOW': 8}.get(risk_level, 0)
    score += min(counts['high_risk_deviations'] * 12, 36)
    score += min(counts['pending_approvals'] * 8, 16)
    score += min(counts['dpa_conflicts'] * 15, 30)
    score += min(counts['unresolved_blockers'] * 10, 20)
    score += min(counts['expired_exceptions'] * 12, 24)
    score += min(counts['missing_approval_authority'] * 8, 8)
    score = min(score, 100)
    band = 'Critical attention' if score >= 85 else 'High attention' if score >= 65 else 'Moderate attention' if score >= 35 else 'Low attention'
    history = history or []
    return {
        'score': score,
        'band': band,
        'contributors': counts,
        'has_history': bool(history),
        'history_label': 'Prior snapshot available' if history else 'No prior snapshot',
    }


def group_recommended_actions(rows, today=None, limit=3):
    """Group identical governed actions, retaining auditable row context."""
    ranked = rank_command_center_rows(rows, today=today)
    groups = {}
    for row in ranked:
        recommendation = governed_recommendation(row)
        key = recommendation['title'].strip().casefold()
        group = groups.setdefault(key, {
            'title': recommendation['title'],
            'explanation': recommendation['explanation'],
            'href': row.get('workspace_href') or row.get('href'),
            'count': 0,
            'counterparties': [],
            'owners': [],
            'urgency': row.get('recommendation_reason') or row.get('risk_label') or 'Action required',
            'due_label': row.get('due_label') if row.get('due_date') else '',
            'updated_at': row.get('updated_at'),
            'sort_key': (
                0 if row.get('status_label') == 'Blocked' else 1,
                0 if row.get('due_overdue') else 1,
                row.get('updated_at') or timezone.now(),
                -RISK_RANK.get(row.get('risk_level'), 0),
                recommendation['title'].casefold(),
            ),
        })
        group['count'] += 1
        counterparty = row.get('counterparty') or 'No counterparty'
        if counterparty not in group['counterparties']:
            group['counterparties'].append(counterparty)
        owner = row.get('owner_label') or 'Unassigned'
        if owner not in group['owners']:
            group['owners'].append(owner)
        if row.get('due_overdue'):
            group['urgency'] = 'Overdue'
        if row.get('updated_at') and (not group.get('updated_at') or row['updated_at'] < group['updated_at']):
            group['updated_at'] = row['updated_at']

    result = []
    for group in sorted(groups.values(), key=lambda item: item['sort_key'])[:limit]:
        counterparties = group.pop('counterparties')
        owners = group.pop('owners')
        group.pop('sort_key', None)
        group['counterparty_text'] = counterparties[0] if len(counterparties) == 1 else f'{counterparties[0]} +{len(counterparties) - 1} more'
        group['owner_text'] = ', '.join(owners[:2]) + (f' +{len(owners) - 2}' if len(owners) > 2 else '')
        result.append(group)
    return result


def format_deadline_status(due_date, today=None):
    today = today or date.today()
    if not due_date:
        return 'Date not configured'
    delta = (due_date - today).days
    if delta < 0:
        days = abs(delta)
        return f"Overdue by {days} day{'s' if days != 1 else ''}"
    if delta == 0:
        return 'Due today'
    if delta == 1:
        return 'Due tomorrow'
    return f"Due {due_date.strftime('%-d %B')}"


def build_upcoming_deadlines(items, today=None, limit=3):
    """Deduplicate and order dated obligations before unconfigured workflow dates."""
    today = today or date.today()
    unique = {}
    for item in items or []:
        key = ((item.get('title') or '').casefold(), item.get('due_date'))
        unique.setdefault(key, item)
    ordered = sorted(
        unique.values(),
        key=lambda item: (
            item.get('due_date') is None,
            item.get('due_date') or date.max,
            (item.get('title') or '').casefold(),
            item.get('href') or '',
        ),
    )[:limit]
    for item in ordered:
        item['status_label'] = format_deadline_status(item.get('due_date'), today=today)
        item['status_tone'] = 'overdue' if item.get('due_date') and item['due_date'] < today else 'attention'
    return ordered


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


def format_activity_age(value, now=None):
    if not value:
        return 'No activity yet'
    now = now or timezone.now()
    seconds = max(0, int((now - value).total_seconds()))
    if seconds >= 86400:
        days = seconds // 86400
        return f'{days}d ago'
    if seconds >= 3600:
        return f'{seconds // 3600}h ago'
    if seconds >= 60:
        return f'{seconds // 60}m ago'
    return 'Just now'


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
    return reverse('contracts:repository')


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
    if contract and (
        item.source_type == CommandCenterWorkItem.SourceType.CONTRACT
        or not item.stage
        or item.stage.strip().lower() == 'review'
    ):
        stage = COMPACT_LIFECYCLE_LABELS.get(
            contract.lifecycle_stage,
            contract.get_lifecycle_stage_display(),
        )
    elif item.stage:
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
        'updated_at': item.updated_at,
        'updated_label': format_activity_age(item.updated_at),
        'due_date': due_date,
        'due_overdue': bool(due_date and due_date < today),
        'due_today': bool(due_date and due_date == today),
        'status_label': item.get_status_display(),
        'source_type': item.source_type,
        'priority': item.priority,
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
        'score_history': flags.get('risk_score_history') or [],
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
    if current_user is not None:
        from contracts.permissions import get_active_org_membership
        if get_active_org_membership(current_user, organization) is None:
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
    rows = [command_center_work_item_to_row(item, current_user=current_user, today=today) for item in items]
    return rank_command_center_rows(rows, today=today)


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
