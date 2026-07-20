"""Cross-matter legal-signal aggregation for the in_house_clm Legal Intelligence Hub.

Normalizes already-persisted rows from RiskLog, DPARiskItem (including DPA
cross-document conflicts), pending/blocking ApprovalRequest items, and
upcoming/overdue Deadlines into one consistent LegalSignal shape. Read-only:
nothing here runs DPA analysis, conflict detection, or mutates approval/DPA
state — it only queries rows that other explicit actions already wrote.

There is no persisted "playbook deviation" model in this codebase today
(only reference/config tables: ClausePlaybook, ClauseVariant,
DPAPlaybookPosition) — no deviation events exist to surface, so playbook
signals are intentionally omitted rather than invented.
"""
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Dict, List, Optional

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from contracts.models import ApprovalRequest, Deadline, DPARiskItem, RiskLog

SEVERITY_ORDER = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
DEADLINE_WINDOW_DAYS = 30

SIGNAL_TYPES = ('contract_risk', 'dpa_risk', 'approval', 'deadline')


@dataclass
class LegalSignal:
    source_type: str
    source_id: int
    title: str
    summary: str
    severity: Optional[str]
    severity_display: Optional[str]
    status: Optional[str]
    status_display: Optional[str]
    owner: Optional[Any]
    owners_csv: Optional[str]
    matter: Optional[Any]
    contract: Optional[Any]
    counterparty: str
    due_date: Optional[Any]
    created_at: Optional[Any]
    updated_at: Optional[Any]
    source_url: str
    recommended_action: Optional[str]
    is_conflict: bool = False

    @property
    def severity_rank(self) -> int:
        return SEVERITY_ORDER.get(self.severity, 99)

    @property
    def is_high_severity(self) -> bool:
        return self.severity in ('HIGH', 'CRITICAL')


def _counterparty_for(contract, matter) -> str:
    if contract is not None and contract.counterparty:
        return contract.counterparty
    if matter is not None and matter.client_id:
        return matter.client.name
    return ''


def _map_risk_log(risk: RiskLog) -> LegalSignal:
    contract = risk.contract
    matter = risk.matter
    return LegalSignal(
        source_type='contract_risk',
        source_id=risk.pk,
        title=risk.title or (risk.description[:80] if risk.description else 'Risk'),
        summary=risk.description or '',
        severity=risk.risk_level,
        severity_display=risk.get_risk_level_display(),
        status=risk.status,
        status_display=risk.get_status_display(),
        owner=risk.assigned_to,
        owners_csv=None,
        matter=matter,
        contract=contract,
        counterparty=_counterparty_for(contract, matter),
        due_date=None,
        created_at=risk.created_at,
        updated_at=risk.updated_at,
        source_url=reverse('contracts:risk_log_update', kwargs={'pk': risk.pk}),
        recommended_action=risk.mitigation_plan or risk.follow_up or None,
    )


def _map_dpa_risk(item: DPARiskItem) -> LegalSignal:
    review_pack = item.review_pack
    contract = review_pack.contract if review_pack else None
    matter = review_pack.matter if review_pack else None
    return LegalSignal(
        source_type='dpa_risk',
        source_id=item.pk,
        title=item.title,
        summary=item.description or '',
        severity=item.severity,
        severity_display=item.get_severity_display(),
        status=item.status,
        status_display=item.get_status_display(),
        owner=None,
        owners_csv=item.owners or None,
        matter=matter,
        contract=contract,
        counterparty=_counterparty_for(contract, matter),
        due_date=None,
        created_at=item.created_at,
        updated_at=item.updated_at,
        source_url=reverse('contracts:dpa_review_pack_detail', kwargs={'pk': review_pack.pk}) if review_pack else '',
        recommended_action=item.fallback_recommendation or None,
        is_conflict=item.is_cross_document_conflict,
    )


def _map_approval(approval: ApprovalRequest) -> LegalSignal:
    contract = approval.contract
    matter = contract.matter if contract else None
    step_label = approval.approval_step or 'Approval'
    return LegalSignal(
        source_type='approval',
        source_id=approval.pk,
        title=f'{step_label} approval — {contract.title}' if contract else f'{step_label} approval',
        summary=approval.comments or '',
        severity=None,
        severity_display=None,
        status=approval.status,
        status_display=approval.get_status_display(),
        owner=approval.assigned_to,
        owners_csv=None,
        matter=matter,
        contract=contract,
        counterparty=_counterparty_for(contract, matter),
        due_date=approval.due_date,
        created_at=approval.created_at,
        updated_at=approval.created_at,
        source_url=reverse('contracts:approval_request_update', kwargs={'pk': approval.pk}),
        recommended_action=None,
    )


def _map_deadline(deadline: Deadline) -> LegalSignal:
    contract = deadline.contract
    matter = deadline.matter
    status = 'OVERDUE' if deadline.is_overdue else 'UPCOMING'
    status_display = 'Overdue' if deadline.is_overdue else 'Upcoming'
    return LegalSignal(
        source_type='deadline',
        source_id=deadline.pk,
        title=deadline.title,
        summary=deadline.description or '',
        severity=deadline.priority,
        severity_display=deadline.get_priority_display(),
        status=status,
        status_display=status_display,
        owner=deadline.assigned_to,
        owners_csv=None,
        matter=matter,
        contract=contract,
        counterparty=_counterparty_for(contract, matter),
        due_date=deadline.due_date,
        created_at=deadline.created_at,
        updated_at=deadline.created_at,
        source_url=reverse('contracts:deadline_update', kwargs={'pk': deadline.pk}),
        recommended_action=None,
    )


def _risk_log_queryset(org=None, matter=None):
    qs = (
        RiskLog.objects
        .exclude(status=RiskLog.Status.RESOLVED)
        .select_related('contract', 'matter', 'matter__client', 'assigned_to')
    )
    if matter is not None:
        return qs.filter(Q(matter=matter) | Q(contract__matter=matter))
    return qs.for_organization(org)


def _dpa_risk_queryset(org=None, matter=None):
    qs = (
        DPARiskItem.objects
        .exclude(status__in=['RESOLVED', 'FALSE_POSITIVE'])
        .select_related(
            'review_pack', 'review_pack__contract', 'review_pack__matter',
            'review_pack__matter__client', 'review_pack__counterparty',
        )
    )
    if matter is not None:
        return qs.filter(review_pack__matter=matter)
    return qs.filter(review_pack__organization=org)


def _approval_queryset(org=None, matter=None):
    qs = (
        ApprovalRequest.objects
        .filter(status__in=[ApprovalRequest.Status.PENDING, ApprovalRequest.Status.ESCALATED])
        .select_related('contract', 'contract__matter', 'contract__matter__client', 'assigned_to')
    )
    if matter is not None:
        return qs.filter(contract__matter=matter)
    return qs.filter(organization=org)


def _deadline_queryset(org=None, matter=None):
    window_end = timezone.now().date() + timedelta(days=DEADLINE_WINDOW_DAYS)
    qs = (
        Deadline.objects
        .filter(is_completed=False, due_date__lte=window_end)
        .select_related('contract', 'matter', 'matter__client', 'assigned_to')
    )
    if matter is not None:
        return qs.filter(Q(matter=matter) | Q(contract__matter=matter))
    return qs.for_organization(org)


def _collect_signals(org=None, matter=None) -> List[LegalSignal]:
    """Build the full, unfiltered signal list for an org or a single matter.

    Exactly one org (or matter) is scoped per source model. Every source
    query is scoped via `select_related`, so this is a fixed handful of
    queries regardless of row count — no N+1 as the data set grows.
    """
    signals: List[LegalSignal] = []
    signals.extend(_map_risk_log(r) for r in _risk_log_queryset(org=org, matter=matter))
    signals.extend(_map_dpa_risk(i) for i in _dpa_risk_queryset(org=org, matter=matter))
    signals.extend(_map_approval(a) for a in _approval_queryset(org=org, matter=matter))
    signals.extend(_map_deadline(d) for d in _deadline_queryset(org=org, matter=matter))
    # Two stable passes: newest-first within a severity band, most severe band first.
    signals.sort(key=lambda s: s.created_at or timezone.now(), reverse=True)
    signals.sort(key=lambda s: s.severity_rank)
    return signals


def _apply_filters(signals: List[LegalSignal], filters: Optional[Dict[str, Any]]) -> List[LegalSignal]:
    if not filters:
        return signals
    signal_type = filters.get('type')
    if signal_type and signal_type != 'all':
        if signal_type == 'conflicts':
            signals = [s for s in signals if s.is_conflict]
        else:
            signals = [s for s in signals if s.source_type == signal_type]
    severity = filters.get('severity')
    if severity:
        signals = [s for s in signals if s.severity == severity]
    query = (filters.get('q') or '').strip().lower()
    if query:
        signals = [
            s for s in signals
            if query in (s.title or '').lower() or query in (s.summary or '').lower()
        ]
    return signals


def get_legal_signals_for_org(org, user=None, filters=None) -> List[LegalSignal]:
    """All normalized legal signals for an organization, optionally filtered.

    `user` is accepted for future scoping (e.g. "assigned to me") but is not
    currently used to narrow results — every signal an org's legal team may
    act on is shown, not just the requesting user's own queue.
    """
    if org is None:
        return []
    return _apply_filters(_collect_signals(org=org), filters)


def get_legal_signal_counts_for_org(org) -> Dict[str, int]:
    """KPI-strip counts derived from the same persisted rows, no extra queries beyond _collect_signals."""
    if org is None:
        return {
            'critical_high_count': 0, 'conflict_count': 0, 'pending_approval_count': 0,
            'upcoming_deadline_count': 0, 'total_count': 0,
            'by_type': {t: 0 for t in SIGNAL_TYPES},
        }
    signals = _collect_signals(org=org)
    return {
        'critical_high_count': sum(
            1 for s in signals if s.source_type in ('contract_risk', 'dpa_risk') and s.is_high_severity
        ),
        'conflict_count': sum(1 for s in signals if s.is_conflict),
        'pending_approval_count': sum(1 for s in signals if s.source_type == 'approval'),
        'upcoming_deadline_count': sum(1 for s in signals if s.source_type == 'deadline'),
        'total_count': len(signals),
        'by_type': {t: sum(1 for s in signals if s.source_type == t) for t in SIGNAL_TYPES},
    }


def get_matter_legal_signals(matter) -> List[LegalSignal]:
    """Normalized legal signals scoped to a single matter (for future Matter Workspace use)."""
    if matter is None:
        return []
    return _collect_signals(matter=matter)
