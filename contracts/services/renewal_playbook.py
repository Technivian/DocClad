"""Renewal playbook service.

Auto-generates Deadline tasks for contracts whose end_date or renewal_date is
approaching. Designed to be called from a scheduled management command or a
cron job.

All generated deadlines carry ``auto_generated=True`` and
``deadline_type=RENEWAL`` so they can be distinguished from manually created
obligations.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from django.contrib.auth import get_user_model
from django.utils import timezone

from contracts.models import Contract, Deadline, Organization

User = get_user_model()

# Default reminder window before the due date a task should alert.
_DEFAULT_REMINDER_DAYS = 14

# Playbook templates keyed by (trigger_field, days_before_event).
# Each entry defines the Deadline that should be auto-created.
_PLAYBOOK: list[dict] = [
    {
        'trigger': 'renewal_date',
        'days_before': 60,
        'title': 'Renewal decision required in 60 days',
        'description': (
            'The contract renewal date is 60 days away. '
            'Assign a business owner and initiate the renewal/termination decision process.'
        ),
        'priority': Deadline.Priority.HIGH,
        'reminder_days': 14,
    },
    {
        'trigger': 'renewal_date',
        'days_before': 30,
        'title': 'Renewal notice deadline: 30 days remaining',
        'description': (
            'Renewal notice period is expiring in 30 days. '
            'Send written notice of intent to renew or terminate per contractual requirements.'
        ),
        'priority': Deadline.Priority.CRITICAL,
        'reminder_days': 7,
    },
    {
        'trigger': 'end_date',
        'days_before': 60,
        'title': 'Contract expiry approaching — 60-day review',
        'description': (
            'The contract expires in 60 days. '
            'Confirm whether obligations are fulfilled and arrange close-out or extension.'
        ),
        'priority': Deadline.Priority.HIGH,
        'reminder_days': 14,
    },
    {
        'trigger': 'end_date',
        'days_before': 14,
        'title': 'Contract expiry in 14 days — final action required',
        'description': (
            'The contract expires in 14 days. '
            'Ensure all outstanding obligations are addressed and obtain sign-off.'
        ),
        'priority': Deadline.Priority.CRITICAL,
        'reminder_days': 3,
    },
]


def _task_dedup_key(contract: Contract, trigger: str, days_before: int) -> str:
    """Stable key to detect already-generated tasks for this contract+milestone."""
    return f'renewal-playbook|{contract.pk}|{trigger}|{days_before}'


def generate_renewal_tasks(
    organization: Organization,
    days_lookahead: int = 90,
    dry_run: bool = False,
) -> dict:
    """Scan contracts in *organization* and create renewal-playbook Deadline tasks.

    Args:
        organization: Tenant to scope the scan to.
        days_lookahead: How many days into the future to look for approaching dates.
        dry_run: If True, compute what would be created but do not write to DB.

    Returns:
        dict with keys ``created``, ``skipped`` (already exists), ``contracts_scanned``.
    """
    today = date.today()
    horizon = today + timedelta(days=days_lookahead)

    # Contracts with either end_date or renewal_date within the horizon
    contracts = (
        Contract.objects
        .filter(organization=organization)
        .exclude(status__in=[Contract.Status.ARCHIVED, Contract.Status.TERMINATED])
        .select_related('created_by')
    )

    created = 0
    skipped = 0
    contracts_scanned = 0

    for contract in contracts:
        contracts_scanned += 1
        for entry in _PLAYBOOK:
            trigger_date: Optional[date] = getattr(contract, entry['trigger'], None)
            if trigger_date is None:
                continue

            task_due = trigger_date - timedelta(days=entry['days_before'])
            # Only create if the task is still in the future (or today) and within horizon
            if task_due < today or task_due > horizon:
                continue

            dedup_key = _task_dedup_key(contract, entry['trigger'], entry['days_before'])
            already_exists = Deadline.objects.filter(
                contract=contract,
                auto_generated=True,
                title=entry['title'],
            ).exists()

            if already_exists:
                skipped += 1
                continue

            if not dry_run:
                Deadline.objects.create(
                    title=entry['title'],
                    description=entry['description'],
                    deadline_type=Deadline.DeadlineType.RENEWAL,
                    auto_generated=True,
                    generation_source='MANUAL',  # closest available choice; marks playbook origin
                    priority=entry['priority'],
                    due_date=task_due,
                    reminder_days=entry['reminder_days'],
                    contract=contract,
                    assigned_to=None,
                    created_by=contract.created_by,
                )
            created += 1

    return {
        'contracts_scanned': contracts_scanned,
        'created': created,
        'skipped': skipped,
        'dry_run': dry_run,
        'generated_at': timezone.now().isoformat(),
    }


def get_renewal_tasks_for_contract(contract: Contract) -> list[Deadline]:
    """Return all auto-generated renewal-playbook tasks for a contract."""
    return list(
        Deadline.objects
        .filter(contract=contract, auto_generated=True, deadline_type=Deadline.DeadlineType.RENEWAL)
        .order_by('due_date')
    )
