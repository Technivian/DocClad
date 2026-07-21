"""Shared governance UX helpers — blocked state, priority reasons, coverage.

Phase 3 makes CLM One's governance rules visible in every queue, not only in
My Work detail panels. Keep reason copy rule-based (SLA / risk / workflow),
never decorative urgency.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta


def format_user_label(user) -> str:
    if not user:
        return ''
    return (user.get_full_name() or user.username or '').strip()


def build_delegation_info(
    assigned_to,
    delegated_to,
    delegated_at=None,
    *,
    reason='',
    ends_at=None,
):
    """Return coverage metadata when an acting assignee differs from the owner."""
    if not delegated_to:
        return None
    if assigned_to and delegated_to == assigned_to and not reason and not ends_at:
        return None
    return {
        'original_assignee': assigned_to,
        'acting_assignee': delegated_to,
        'effective_from': delegated_at,
        'effective_until': ends_at,
        'reason': (reason or '').strip() or 'Delegated coverage',
    }


def sla_priority_reason(*, due_date, today=None, sla_hours=None, overdue=False, risk_level='', escalated=False, fallback=''):
    """Build a rule-based priority reason for queue tooltips."""
    today = today or date.today()
    due = due_date
    if isinstance(due, datetime):
        due = due.date()
    if overdue and due:
        days = (today - due).days
        base = f'Overdue by {days} day{"s" if days != 1 else ""}'
        if sla_hours:
            return f'{base} (SLA {sla_hours}h)'
        return base
    if escalated:
        return 'Escalated past SLA / escalation threshold'
    if sla_hours and due:
        # Approaching SLA window: due within half the SLA period (min 1 day).
        window_days = max(1, int(sla_hours / 24 / 2) or 1)
        if due <= today + timedelta(days=window_days):
            return f'Due within SLA window ({sla_hours}h)'
    if risk_level in ('HIGH', 'CRITICAL'):
        return f'{risk_level.title()}-risk contract'
    return fallback or ''


def priority_tone_for_label(label: str) -> str:
    """Map display priority labels to design-system badge tones."""
    return {
        'critical': 'danger',
        'urgent': 'danger',
        'high': 'warning',
        'normal': 'info',
        'medium': 'info',
        'low': 'neutral',
    }.get(str(label or '').strip().lower(), 'neutral')


def approval_blocker_for_request(approval, sibling_pending=None):
    """Explain who must act next when an approval is blocked on a prior step."""
    if getattr(approval, 'status', None) == 'ESCALATED':
        owner = approval.delegated_to or approval.assigned_to
        return {
            'is_blocked': True,
            'blocking_issue': 'Escalated — requires urgent decision',
            'blocker_owner': format_user_label(owner) or 'Assigned approver',
        }
    if not sibling_pending:
        return {'is_blocked': False, 'blocking_issue': '', 'blocker_owner': ''}
    prior = [
        step for step in sibling_pending
        if step.pk != approval.pk
        and (step.sort_order or 0) < (approval.sort_order or 0)
        and step.status in ('PENDING', 'ESCALATED')
    ]
    if not prior:
        return {'is_blocked': False, 'blocking_issue': '', 'blocker_owner': ''}
    blocker = sorted(prior, key=lambda s: (s.sort_order or 0, s.pk))[-1]
    owner = blocker.delegated_to or blocker.assigned_to
    step = (blocker.approval_step or 'prior step').replace('_', ' ').strip().title()
    return {
        'is_blocked': True,
        'blocking_issue': f'Waiting on {step}',
        'blocker_owner': format_user_label(owner) or 'Prior-step assignee',
    }


def privacy_blocker_for_pack(pack, *, unresolved_critical=0, conflict_count=0):
    if conflict_count:
        return {
            'is_blocked': True,
            'blocking_issue': 'Cross-document conflicts must be resolved',
            'blocker_owner': format_user_label(getattr(pack, 'reviewer', None)) or 'Privacy reviewer',
        }
    if unresolved_critical:
        return {
            'is_blocked': True,
            'blocking_issue': f'{unresolved_critical} critical risk{"s" if unresolved_critical != 1 else ""} open',
            'blocker_owner': format_user_label(getattr(pack, 'reviewer', None)) or 'Privacy reviewer',
        }
    return {'is_blocked': False, 'blocking_issue': '', 'blocker_owner': ''}


def obligation_blocker_for_deadline(deadline, today=None):
    today = today or date.today()
    due = deadline.due_date
    if isinstance(due, datetime):
        due = due.date()
    if not deadline.assigned_to_id:
        return {
            'is_blocked': True,
            'blocking_issue': 'No owner assigned',
            'blocker_owner': 'Legal ops / manager',
        }
    if due and due < today and deadline.priority in ('HIGH', 'CRITICAL'):
        return {
            'is_blocked': True,
            'blocking_issue': 'High-priority obligation overdue',
            'blocker_owner': format_user_label(deadline.assigned_to),
        }
    return {'is_blocked': False, 'blocking_issue': '', 'blocker_owner': ''}
