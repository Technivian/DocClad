"""Reusable UI component inclusion tags shared across queue-style screens.

Each tag renders one component partial under theme/templates/components/ so
Dashboard, Repository, Tasks, and Approvals can share the same markup instead
of re-implementing stage dots, assignee chips, and activity lines per page.
"""
from django import template

from .clmone_format import lifecycle_steps

register = template.Library()


@register.inclusion_tag('components/_stage_dots.html')
def stage_dots(contract):
    """Compact lifecycle indicator for a queue/table row.

    Renders nothing but an em dash when there is no contract to derive a
    stage from (e.g. a DSAR request with no linked contract) — never guesses.
    """
    if not contract:
        return {'steps': [], 'current_label': ''}
    steps = lifecycle_steps(contract)
    current = next((s for s in steps if s['state'] == 'current'), None)
    if not current:
        done = [s for s in steps if s['state'] == 'done']
        current = done[-1] if done else None
    return {'steps': steps, 'current_label': current['label'] if current else 'Not started'}


@register.inclusion_tag('components/_assignee_chip.html')
def assignee_chip(user):
    """Avatar-initial chip for an assigned user, or an "Unassigned" state."""
    return {'user': user}


@register.inclusion_tag('components/_activity_line.html')
def activity_line(audit_log):
    """Human-readable audit line for a queue row, or a "No recent activity" placeholder."""
    return {'log': audit_log}


@register.inclusion_tag('components/_work_queue_table.html')
def work_queue_table(panel_key, rows, empty_message, is_active=False):
    """Shared queue table for Dashboard/Repository/Tasks/Approvals saved views."""
    return {
        'panel_key': panel_key,
        'rows': rows,
        'empty_message': empty_message,
        'is_active': is_active,
    }


@register.inclusion_tag('components/_approval_queue_table.html')
def approval_queue_table(
    panel_key,
    rows,
    empty_message,
    is_active=False,
    personal_hub=False,
    empty_title='',
    empty_copy='',
    empty_how='',
):
    """Approvals-inbox queue table — same StageDots/AssigneeChip/ActivityLine
    components and .wq-table styling as work_queue_table, with the extra
    Requested-by and Actions columns a decision inbox needs. A different
    column layout on the same visual system, not a second design system —
    the same divergence Repository already has from Dashboard's table."""
    return {
        'panel_key': panel_key,
        'rows': rows,
        'empty_message': empty_message,
        'is_active': is_active,
        'personal_hub': personal_hub,
        'empty_title': empty_title or empty_message,
        'empty_copy': empty_copy or empty_message,
        'empty_how': empty_how,
    }


@register.inclusion_tag('components/_task_queue_table.html')
def task_queue_table(
    panel_key,
    rows,
    empty_message,
    is_active=False,
    personal_hub=False,
    empty_title='',
    empty_copy='',
    empty_how='',
):
    """Tasks-inbox queue table — same visual system as work_queue_table/
    approval_queue_table, with a priority badge on the item cell and a
    single-action (Complete) Actions column instead of approve/reject."""
    return {
        'panel_key': panel_key,
        'rows': rows,
        'empty_message': empty_message,
        'is_active': is_active,
        'personal_hub': personal_hub,
        'empty_title': empty_title or empty_message,
        'empty_copy': empty_copy or empty_message,
        'empty_how': empty_how,
    }
