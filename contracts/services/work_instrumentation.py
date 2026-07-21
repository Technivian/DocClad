"""Phase 5 — work operating-loop instrumentation.

Discovery events (surfaced / opened) live on WorkInteractionEvent.
Outcome mutations continue to write AuditLog; this module also mirrors
completed/returned/rejected/sla_breached into WorkInteractionEvent with
surface attribution so hub vs specialist completion can be measured.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Iterable

from django.db.models import Count, Q
from django.utils import timezone

logger = logging.getLogger(__name__)

VALID_SURFACES = frozenset({
    'my_work', 'approvals', 'obligations', 'privacy', 'tasks',
    'contract_detail', 'api', 'job',
})


def resolve_surface(request=None, explicit: str = '') -> str:
    """Best-effort surface attribution from explicit value, query, or referrer."""
    candidate = (explicit or '').strip()
    if candidate in VALID_SURFACES:
        return candidate
    if request is not None:
        q = (request.GET.get('from') or request.POST.get('from') or '').strip()
        if q in VALID_SURFACES:
            return q
        try:
            import json
            if request.body and request.content_type and 'json' in request.content_type:
                data = json.loads(request.body.decode('utf-8') or '{}')
                q = (data.get('surface') or data.get('from') or '').strip()
                if q in VALID_SURFACES:
                    return q
        except Exception:
            pass
        referer = request.META.get('HTTP_REFERER') or ''
        if '/contracts/my-work' in referer:
            return 'my_work'
        if '/contracts/approvals' in referer:
            return 'approvals'
        if '/contracts/obligations' in referer or '/contracts/deadlines' in referer:
            return 'obligations'
        if '/contracts/dpa-reviews' in referer:
            return 'privacy'
        if '/contracts/legal-tasks' in referer:
            return 'tasks'
        if '/contracts/' in referer and '/detail' not in referer:
            # contract detail URLs vary; treat contract pages as contract_detail
            if '/contracts/' in referer and referer.rstrip('/').split('/')[-1].isdigit():
                return 'contract_detail'
    return 'api'


def record_work_event(
    *,
    organization,
    user=None,
    event: str,
    work_item_id: str,
    work_kind: str = '',
    surface: str = 'my_work',
    contract_id=None,
    contract_type: str = '',
    is_restricted: bool = False,
    is_blocked: bool = False,
    is_overdue: bool = False,
    metadata: dict | None = None,
    dedupe_days: int | None = None,
) -> None:
    """Append a work interaction event. Never raises to callers."""
    try:
        if organization is None or not work_item_id or not event:
            return
        from contracts.models import WorkInteractionEvent

        surface = surface if surface in VALID_SURFACES else 'api'
        if dedupe_days is not None:
            since = timezone.now() - timedelta(days=dedupe_days)
            exists = WorkInteractionEvent.objects.filter(
                organization=organization,
                user=user,
                event=event,
                work_item_id=work_item_id,
                occurred_at__gte=since,
            ).exists()
            if exists:
                return
        WorkInteractionEvent.objects.create(
            organization=organization,
            user=user if getattr(user, 'is_authenticated', False) else None,
            event=event,
            work_item_id=str(work_item_id)[:80],
            work_kind=(work_kind or '')[:40],
            surface=surface,
            contract_id=contract_id,
            contract_type=(contract_type or '')[:40],
            is_restricted=bool(is_restricted),
            is_blocked=bool(is_blocked),
            is_overdue=bool(is_overdue),
            metadata=metadata or {},
        )
    except Exception:
        logger.warning('work instrumentation failed event=%s item=%s', event, work_item_id, exc_info=True)


def record_rows_surfaced(organization, user, rows: Iterable[dict], *, surface: str = 'my_work') -> int:
    """Record surfaced events for a queue render (deduped per user/item/day)."""
    count = 0
    for row in rows or []:
        work_item_id = row.get('id') or ''
        if not work_item_id:
            continue
        due = row.get('due_context') or {}
        contract = row.get('contract')
        record_work_event(
            organization=organization,
            user=user,
            event='surfaced',
            work_item_id=work_item_id,
            work_kind=row.get('work_kind') or row.get('work_type_key') or '',
            surface=surface,
            contract_id=getattr(contract, 'pk', None) or row.get('contract_id'),
            contract_type=row.get('contract_type') or getattr(contract, 'contract_type', '') or '',
            is_restricted=bool(row.get('is_restricted')),
            is_blocked=bool(row.get('is_blocked')),
            is_overdue=bool(due.get('due_overdue')),
            dedupe_days=1,
        )
        count += 1
    return count


def record_outcome(
    *,
    organization,
    user=None,
    event: str,
    work_item_id: str,
    work_kind: str = '',
    surface: str = 'api',
    contract=None,
    contract_id=None,
    is_overdue: bool = False,
    metadata: dict | None = None,
) -> None:
    """Mirror a completed/returned/rejected/sla outcome with surface attribution."""
    cid = contract_id
    ctype = ''
    if contract is not None:
        cid = getattr(contract, 'pk', cid)
        ctype = getattr(contract, 'contract_type', '') or ''
    record_work_event(
        organization=organization,
        user=user,
        event=event,
        work_item_id=work_item_id,
        work_kind=work_kind,
        surface=surface,
        contract_id=cid,
        contract_type=ctype,
        is_overdue=is_overdue,
        metadata=metadata,
    )


def build_operating_metrics(organization, *, days: int = 30) -> dict:
    """Aggregate the five Phase 5 operating metrics for an organization."""
    from contracts.models import ApprovalRequest, AuditLog, WorkInteractionEvent

    if organization is None:
        return {'window_days': days, 'metrics': {}}

    since = timezone.now() - timedelta(days=max(1, days))
    events = WorkInteractionEvent.objects.filter(organization=organization, occurred_at__gte=since)

    # Time to first action: opened/primary_action after first surfaced for same item.
    time_to_action_hours = None
    pairs = []
    surfaced = {
        e.work_item_id: e.occurred_at
        for e in events.filter(event='surfaced').order_by('occurred_at')
    }
    actions = events.filter(event__in=['opened', 'primary_action', 'completed']).order_by('occurred_at')
    seen = set()
    for action in actions:
        if action.work_item_id in seen:
            continue
        first_surfaced = surfaced.get(action.work_item_id)
        if not first_surfaced or action.occurred_at < first_surfaced:
            continue
        pairs.append((action.occurred_at - first_surfaced).total_seconds() / 3600.0)
        seen.add(action.work_item_id)
    if pairs:
        time_to_action_hours = round(sum(pairs) / len(pairs), 2)

    surfaced_qs = events.filter(event='surfaced')
    by_kind = {}
    for row in surfaced_qs.values('work_kind').annotate(
        total=Count('id'),
        overdue=Count('id', filter=Q(is_overdue=True)),
    ):
        kind = row['work_kind'] or 'unknown'
        total = row['total'] or 0
        by_kind[kind] = {
            'total': total,
            'overdue': row['overdue'] or 0,
            'overdue_rate': round((row['overdue'] or 0) / total, 3) if total else 0.0,
        }

    decision_qs = events.filter(event__in=['returned', 'rejected', 'completed'])
    by_contract_type = {}
    for row in decision_qs.values('contract_type').annotate(
        total=Count('id'),
        returned=Count('id', filter=Q(event='returned')),
        rejected=Count('id', filter=Q(event='rejected')),
    ):
        ctype = row['contract_type'] or 'unknown'
        total = row['total'] or 0
        by_contract_type[ctype] = {
            'total': total,
            'returned': row['returned'] or 0,
            'rejected': row['rejected'] or 0,
            'return_reject_rate': round(
                ((row['returned'] or 0) + (row['rejected'] or 0)) / total, 3
            ) if total else 0.0,
        }

    completed = events.filter(event='completed')
    completed_total = completed.count()
    completed_my_work = completed.filter(surface='my_work').count()
    completed_from_my_work_pct = (
        round(completed_my_work / completed_total, 3) if completed_total else None
    )

    surfaced_total = surfaced_qs.count()
    restricted = surfaced_qs.filter(is_restricted=True).count()
    blocked = surfaced_qs.filter(is_blocked=True).count()

    approval_lag_hours = None
    decided = (
        ApprovalRequest.objects
        .filter(organization=organization, decided_at__gte=since, decided_at__isnull=False)
        .exclude(created_at__isnull=True)
    )
    lags = []
    for ar in decided.only('created_at', 'decided_at')[:500]:
        if ar.created_at and ar.decided_at and ar.decided_at >= ar.created_at:
            lags.append((ar.decided_at - ar.created_at).total_seconds() / 3600.0)
    if lags:
        approval_lag_hours = round(sum(lags) / len(lags), 2)

    sla_breaches = list(
        events.filter(event='sla_breached').order_by('-occurred_at')[:25].values(
            'work_item_id', 'work_kind', 'contract_id', 'contract_type', 'occurred_at', 'surface',
        )
    )
    for row in sla_breaches:
        if row.get('occurred_at'):
            row['occurred_at'] = row['occurred_at'].isoformat()

    audit_breaches = list(
        AuditLog.objects.filter(
            organization_id=organization.id,
            event_type='approval.sla_breached',
            timestamp__gte=since,
        ).order_by('-timestamp')[:25].values(
            'object_id', 'object_repr', 'timestamp', 'changes',
        )
    )
    for row in audit_breaches:
        if row.get('timestamp'):
            row['timestamp'] = row['timestamp'].isoformat()

    # Bottleneck work kinds: highest overdue rate among kinds with enough volume.
    bottlenecks = sorted(
        (
            {'work_kind': kind, **stats}
            for kind, stats in by_kind.items()
            if stats.get('total', 0) >= 1 and stats.get('overdue', 0) >= 1
        ),
        key=lambda item: (-item['overdue_rate'], -item['overdue'], item['work_kind']),
    )[:8]

    # Daily activity series for work-health charts (last N days, inclusive).
    day_count = max(1, min(int(days or 30), 180))
    day_buckets = {
        (since.date() + timedelta(days=offset)).isoformat(): {
            'day': (since.date() + timedelta(days=offset)).isoformat(),
            'surfaced': 0,
            'completed': 0,
            'returned': 0,
            'rejected': 0,
        }
        for offset in range(day_count + 1)
    }
    for row in events.filter(event__in=['surfaced', 'completed', 'returned', 'rejected']).values(
        'event', 'occurred_at',
    ):
        occurred = row.get('occurred_at')
        if not occurred:
            continue
        key = timezone.localtime(occurred).date().isoformat() if timezone.is_aware(occurred) else occurred.date().isoformat()
        bucket = day_buckets.get(key)
        if not bucket:
            continue
        event_name = row.get('event') or ''
        if event_name in bucket:
            bucket[event_name] += 1
    daily_activity = [day_buckets[k] for k in sorted(day_buckets.keys())]

    return {
        'window_days': days,
        'generated_at': timezone.now().isoformat(),
        'metrics': {
            'time_to_first_action_hours': time_to_action_hours,
            'approval_decision_lag_hours': approval_lag_hours,
            'overdue_rate_by_work_type': by_kind,
            'return_reject_rate_by_contract_type': by_contract_type,
            'completed_from_my_work_pct': completed_from_my_work_pct,
            'completed_total': completed_total,
            'completed_from_my_work': completed_my_work,
            'restricted_blocked_frequency': {
                'surfaced_total': surfaced_total,
                'restricted': restricted,
                'blocked': blocked,
                'restricted_rate': round(restricted / surfaced_total, 3) if surfaced_total else 0.0,
                'blocked_rate': round(blocked / surfaced_total, 3) if surfaced_total else 0.0,
            },
            'event_counts': {
                row['event']: row['c']
                for row in events.values('event').annotate(c=Count('id'))
            },
            'bottlenecks': bottlenecks,
            'sla_breaches': sla_breaches,
            'audit_sla_breaches': audit_breaches,
            'daily_activity': daily_activity,
        },
    }


def overdue_rate_by_work_type(organization, *, days: int = 30) -> dict:
    """Lightweight overdue rates for rule-based My Work prioritization."""
    from contracts.models import WorkInteractionEvent

    if organization is None:
        return {}
    since = timezone.now() - timedelta(days=max(1, min(int(days or 30), 180)))
    by_kind = {}
    for row in (
        WorkInteractionEvent.objects
        .filter(organization=organization, occurred_at__gte=since, event='surfaced')
        .values('work_kind')
        .annotate(total=Count('id'), overdue=Count('id', filter=Q(is_overdue=True)))
    ):
        kind = row['work_kind'] or 'unknown'
        total = row['total'] or 0
        by_kind[kind] = {
            'total': total,
            'overdue': row['overdue'] or 0,
            'overdue_rate': round((row['overdue'] or 0) / total, 3) if total else 0.0,
        }
    return by_kind


def measured_priority_boost(*, work_kind: str, org_overdue_rates: dict | None = None) -> int:
    """Return sort-tier nudge (0–1) from measured overdue rate for a work kind.

    Rule-based only — high measured overdue rate nudges the item earlier.
    """
    if not org_overdue_rates:
        return 0
    stats = org_overdue_rates.get(work_kind) or org_overdue_rates.get(work_kind or 'unknown') or {}
    rate = float(stats.get('overdue_rate') or 0)
    if rate >= 0.35:
        return 1
    return 0
