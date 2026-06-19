from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Optional

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from contracts.models import AuditLog, Contract, Organization, SignatureRequest


TERMINAL_STATUSES = {
    SignatureRequest.Status.SIGNED,
    SignatureRequest.Status.DECLINED,
    SignatureRequest.Status.EXPIRED,
    SignatureRequest.Status.CANCELLED,
}


@dataclass(frozen=True)
class SignatureQueueRow:
    contract_id: int
    contract_title: str
    packet_label: str
    provider_label: str
    status: str
    status_display: str
    sent_at: Optional[str]
    due_at: Optional[str]
    signer_count: int
    completed_count: int
    completion_percent: int
    failed_count: int
    latest_request_id: Optional[int]
    detail_url: str
    packet_url: str
    resend_url: str
    cancel_url: str
    retry_url: str


@dataclass(frozen=True)
class SignatureTimelineEntry:
    timestamp: Optional[str]
    action: str
    actor: str
    summary: str
    status: Optional[str] = None
    is_system: bool = False


@dataclass(frozen=True)
class SignaturePacketSummary:
    contract_id: int
    contract_title: str
    provider_label: str
    status: str
    status_display: str
    signer_count: int
    active_count: int
    signed_count: int
    failed_count: int
    completion_percent: int
    current_position: Optional[int]
    current_signer_name: Optional[str]
    sent_at: Optional[str]
    due_at: Optional[str]
    can_resend: bool
    can_cancel: bool
    can_retry: bool
    detail_url: str
    resend_url: str
    cancel_url: str
    retry_url: str


def _display_user(user) -> str:
    if not user:
        return 'System'
    full_name = (getattr(user, 'get_full_name', lambda: '')() or '').strip()
    return full_name or getattr(user, 'username', None) or str(user)


def _provider_label(request: SignatureRequest) -> str:
    if request.external_id:
        return 'External provider'
    return 'Internal routing'


def _due_at(request: SignatureRequest) -> Optional[str]:
    if request.sent_at:
        return (request.sent_at + timedelta(days=7)).isoformat()
    return None


def _packet_status(requests: list[SignatureRequest]) -> str:
    if not requests:
        return 'PENDING'
    terminal_statuses = {request.status for request in requests if request.status in TERMINAL_STATUSES}
    active_statuses = {request.status for request in requests if request.status not in TERMINAL_STATUSES}
    if active_statuses:
        if SignatureRequest.Status.VIEWED in active_statuses:
            return SignatureRequest.Status.VIEWED
        if SignatureRequest.Status.SENT in active_statuses:
            return SignatureRequest.Status.SENT
        return SignatureRequest.Status.PENDING
    if terminal_statuses == {SignatureRequest.Status.SIGNED}:
        return SignatureRequest.Status.SIGNED
    if SignatureRequest.Status.DECLINED in terminal_statuses:
        return SignatureRequest.Status.DECLINED
    if SignatureRequest.Status.EXPIRED in terminal_statuses:
        return SignatureRequest.Status.EXPIRED
    if SignatureRequest.Status.CANCELLED in terminal_statuses:
        return SignatureRequest.Status.CANCELLED
    return SignatureRequest.Status.SIGNED if requests and all(item.status == SignatureRequest.Status.SIGNED for item in requests) else requests[-1].status


def _packet_status_display(requests: list[SignatureRequest]) -> str:
    status = _packet_status(requests)
    return dict(SignatureRequest.Status.choices).get(status, status.title())


def _packet_sent_at(requests: list[SignatureRequest]) -> Optional[str]:
    sent_values = [request.sent_at for request in requests if request.sent_at]
    if not sent_values:
        return None
    return min(sent_values).isoformat()


def _packet_completion_percent(requests: list[SignatureRequest]) -> int:
    total = len(requests)
    if total == 0:
        return 0
    completed = sum(1 for request in requests if request.status == SignatureRequest.Status.SIGNED)
    return min(100, int(round((completed / total) * 100)))


def _packet_failed_count(requests: list[SignatureRequest]) -> int:
    return sum(1 for request in requests if request.status in {SignatureRequest.Status.DECLINED, SignatureRequest.Status.EXPIRED, SignatureRequest.Status.CANCELLED})


def _latest_request(requests: list[SignatureRequest]) -> Optional[SignatureRequest]:
    if not requests:
        return None
    return max(requests, key=lambda item: (item.order, item.created_at or timezone.now(), item.pk or 0))


def _current_request(requests: list[SignatureRequest]) -> Optional[SignatureRequest]:
    active = [request for request in requests if request.status not in TERMINAL_STATUSES]
    if not active:
        return None
    return min(active, key=lambda item: (item.order or 0, item.created_at or timezone.now(), item.pk or 0))


def _group_requests_by_contract(queryset):
    grouped: dict[int, list[SignatureRequest]] = {}
    contracts: dict[int, Contract] = {}
    for request in queryset:
        grouped.setdefault(request.contract_id, []).append(request)
        contracts.setdefault(request.contract_id, request.contract)
    return contracts, grouped


def build_signature_workspace(organization: Organization | None):
    if organization is None:
        return {
            'kpis': {status.lower(): 0 for status in ['WAITING', 'SENT', 'VIEWED', 'SIGNED', 'COMPLETED', 'FAILED']},
            'queue_rows': [],
            'failed_packets': [],
        }

    queryset = list(
        SignatureRequest.objects.select_related('contract', 'created_by').filter(organization=organization).order_by('contract_id', 'order', 'created_at', 'pk')
    )
    contracts, grouped = _group_requests_by_contract(queryset)

    queue_rows: list[SignatureQueueRow] = []
    failed_packets = []
    kpis = {
        'waiting': 0,
        'sent': 0,
        'viewed': 0,
        'signed': 0,
        'completed': 0,
        'failed': 0,
    }
    for contract_id, requests in grouped.items():
        packet_status = _packet_status(requests)
        kpis['waiting'] += sum(1 for item in requests if item.status == SignatureRequest.Status.PENDING)
        kpis['sent'] += sum(1 for item in requests if item.status == SignatureRequest.Status.SENT)
        kpis['viewed'] += sum(1 for item in requests if item.status == SignatureRequest.Status.VIEWED)
        kpis['signed'] += sum(1 for item in requests if item.status == SignatureRequest.Status.SIGNED)
        kpis['completed'] += 1 if packet_status == SignatureRequest.Status.SIGNED else 0
        kpis['failed'] += 1 if packet_status in {SignatureRequest.Status.DECLINED, SignatureRequest.Status.EXPIRED, SignatureRequest.Status.CANCELLED} else 0

        latest = _latest_request(requests)
        signed_count = sum(1 for item in requests if item.status == SignatureRequest.Status.SIGNED)
        failed_count = _packet_failed_count(requests)
        queue_rows.append(
            SignatureQueueRow(
                contract_id=contract_id,
                contract_title=contracts[contract_id].title if contracts.get(contract_id) else '',
                packet_label=f'Packet #{contract_id}',
                provider_label=_provider_label(latest) if latest else 'Internal routing',
                status=packet_status,
                status_display=_packet_status_display(requests),
                sent_at=_packet_sent_at(requests),
                due_at=_due_at(latest) if latest else None,
                signer_count=len(requests),
                completed_count=signed_count,
                completion_percent=_packet_completion_percent(requests),
                failed_count=failed_count,
                latest_request_id=latest.pk if latest else None,
                detail_url=reverse('contracts:signature_packet_detail', kwargs={'contract_pk': contract_id}),
                packet_url=reverse('contracts:signature_packet_detail', kwargs={'contract_pk': contract_id}),
                resend_url=reverse('contracts:signature_packet_resend', kwargs={'contract_pk': contract_id}),
                cancel_url=reverse('contracts:signature_packet_cancel', kwargs={'contract_pk': contract_id}),
                retry_url=reverse('contracts:signature_packet_retry', kwargs={'contract_pk': contract_id}),
            )
        )
        if failed_count:
            failed_packets.append(queue_rows[-1])

    queue_rows.sort(key=lambda row: (row.status in {SignatureRequest.Status.SIGNED, SignatureRequest.Status.CANCELLED, SignatureRequest.Status.EXPIRED, SignatureRequest.Status.DECLINED}, row.sent_at or '', row.contract_title.lower()))
    return {'kpis': kpis, 'queue_rows': queue_rows, 'failed_packets': failed_packets}


def build_signature_packet(organization: Organization | None, contract: Contract):
    queryset = list(
        SignatureRequest.objects.select_related('contract', 'created_by').filter(contract=contract, organization=organization).order_by('order', 'created_at', 'pk')
    )
    latest = _latest_request(queryset)
    packet_status = _packet_status(queryset)
    completed_count = sum(1 for item in queryset if item.status == SignatureRequest.Status.SIGNED)
    failed_count = _packet_failed_count(queryset)
    active_count = sum(1 for item in queryset if item.status not in TERMINAL_STATUSES)
    current_request = _current_request(queryset)
    signer_rows = []
    for index, request in enumerate(queryset, start=1):
        signer_rows.append({
            'request': request,
            'position': index,
            'provider_label': _provider_label(request),
            'sent_at': request.sent_at.isoformat() if request.sent_at else None,
            'viewed_at': request.viewed_at.isoformat() if request.viewed_at else None,
            'signed_at': request.signed_at.isoformat() if request.signed_at else None,
            'declined_at': request.declined_at.isoformat() if request.declined_at else None,
            'due_at': _due_at(request),
            'progress_percent': 100 if request.status == SignatureRequest.Status.SIGNED else (75 if request.status == SignatureRequest.Status.VIEWED else (50 if request.status == SignatureRequest.Status.SENT else 0)),
            'is_current': bool(current_request and current_request.pk == request.pk),
            'is_terminal': request.status in TERMINAL_STATUSES,
        })

    timeline = build_signature_packet_timeline(contract, queryset)
    return {
        'contract': contract,
        'requests': queryset,
        'latest_request': latest,
        'packet_status': packet_status,
        'packet_status_display': dict(SignatureRequest.Status.choices).get(packet_status, packet_status.title()),
        'signer_rows': signer_rows,
        'signer_count': len(queryset),
        'timeline': timeline,
        'provider_label': _provider_label(latest) if latest else 'Internal routing',
        'current_position': current_request.order if current_request else None,
        'current_signer_name': current_request.signer_name if current_request else None,
        'sent_at': _packet_sent_at(queryset),
        'due_at': _due_at(latest) if latest else None,
        'active_count': active_count,
        'signed_count': completed_count,
        'failed_count': failed_count,
        'completion_percent': _packet_completion_percent(queryset),
        'can_resend': packet_status in {SignatureRequest.Status.PENDING, SignatureRequest.Status.SENT, SignatureRequest.Status.VIEWED},
        'can_cancel': packet_status not in TERMINAL_STATUSES,
        'can_retry': bool(failed_count or active_count),
        'detail_url': reverse('contracts:signature_packet_detail', kwargs={'contract_pk': contract.pk}),
        'resend_url': reverse('contracts:signature_packet_resend', kwargs={'contract_pk': contract.pk}),
        'cancel_url': reverse('contracts:signature_packet_cancel', kwargs={'contract_pk': contract.pk}),
        'retry_url': reverse('contracts:signature_packet_retry', kwargs={'contract_pk': contract.pk}),
    }


def build_signature_packet_timeline(contract: Contract, requests: list[SignatureRequest]) -> list[SignatureTimelineEntry]:
    request_ids = [request.pk for request in requests]
    audit_logs = list(
        AuditLog.objects.select_related('user').filter(
            Q(model_name='SignatureRequest', object_id__in=request_ids)
            | Q(model_name='SignaturePacket', object_id=contract.pk)
            | Q(model_name='ESignEvent', object_id__in=request_ids)
        ).order_by('timestamp', 'pk')
    )

    events: list[tuple[Optional[str], SignatureTimelineEntry]] = []
    for request in requests:
        events.append((request.created_at.isoformat() if request.created_at else None, SignatureTimelineEntry(
            timestamp=request.created_at.isoformat() if request.created_at else None,
            action='created',
            actor=_display_user(request.created_by),
            summary=f"{request.signer_name} added to packet",
            status=request.status,
        )))
        if request.sent_at:
            events.append((request.sent_at.isoformat(), SignatureTimelineEntry(
                timestamp=request.sent_at.isoformat(),
                action='sent',
                actor=_display_user(request.created_by),
                summary=f"{request.signer_name} sent for signature",
                status=SignatureRequest.Status.SENT,
            )))
        if request.viewed_at:
            events.append((request.viewed_at.isoformat(), SignatureTimelineEntry(
                timestamp=request.viewed_at.isoformat(),
                action='viewed',
                actor=request.signer_name,
                summary=f"{request.signer_name} viewed the request",
                status=SignatureRequest.Status.VIEWED,
            )))
        if request.signed_at:
            events.append((request.signed_at.isoformat(), SignatureTimelineEntry(
                timestamp=request.signed_at.isoformat(),
                action='signed',
                actor=request.signer_name,
                summary=f"{request.signer_name} signed the packet",
                status=SignatureRequest.Status.SIGNED,
            )))
        if request.declined_at:
            events.append((request.declined_at.isoformat(), SignatureTimelineEntry(
                timestamp=request.declined_at.isoformat(),
                action='failed',
                actor=request.signer_name,
                summary=f"{request.signer_name} declined the packet",
                status=SignatureRequest.Status.DECLINED,
            )))

    for log in audit_logs:
        changes = log.changes or {}
        event_name = changes.get('event', '')
        if event_name == 'signature_request_reminder_sent':
            events.append((log.timestamp.isoformat(), SignatureTimelineEntry(
                timestamp=log.timestamp.isoformat(),
                action='resent',
                actor=_display_user(log.user),
                summary=f"Reminder sent to {changes.get('notification_count', 0)} recipient(s)",
                is_system=True,
            )))
        elif event_name == 'signature_packet_created':
            events.append((log.timestamp.isoformat(), SignatureTimelineEntry(
                timestamp=log.timestamp.isoformat(),
                action='created',
                actor=_display_user(log.user),
                summary=f"Packet created for {changes.get('request_count', 0)} request(s)",
                is_system=True,
            )))
        elif event_name == 'signature_packet_sent':
            events.append((log.timestamp.isoformat(), SignatureTimelineEntry(
                timestamp=log.timestamp.isoformat(),
                action='sent',
                actor=_display_user(log.user),
                summary=f"Packet sent for {changes.get('request_count', 0)} request(s)",
                is_system=True,
            )))
        elif event_name == 'signature_packet_completed':
            events.append((log.timestamp.isoformat(), SignatureTimelineEntry(
                timestamp=log.timestamp.isoformat(),
                action='signed',
                actor=_display_user(log.user),
                summary=f"Packet completed with {changes.get('request_count', 0)} request(s)",
                is_system=True,
            )))
        elif event_name == 'signature_request_transition':
            events.append((log.timestamp.isoformat(), SignatureTimelineEntry(
                timestamp=log.timestamp.isoformat(),
                action='updated',
                actor=_display_user(log.user),
                summary=f"Transitioned to {changes.get('to_status')}",
                status=changes.get('to_status'),
            )))
        elif event_name == 'signature_packet_resend':
            events.append((log.timestamp.isoformat(), SignatureTimelineEntry(
                timestamp=log.timestamp.isoformat(),
                action='resent',
                actor=_display_user(log.user),
                summary=f"Packet resend requested for {changes.get('count', 0)} request(s)",
                is_system=True,
            )))
        elif event_name == 'signature_packet_cancel':
            events.append((log.timestamp.isoformat(), SignatureTimelineEntry(
                timestamp=log.timestamp.isoformat(),
                action='cancelled',
                actor=_display_user(log.user),
                summary=f"Packet cancel requested for {changes.get('count', 0)} request(s)",
                is_system=True,
            )))
        elif event_name == 'signature_packet_retry':
            events.append((log.timestamp.isoformat(), SignatureTimelineEntry(
                timestamp=log.timestamp.isoformat(),
                action='retried',
                actor=_display_user(log.user),
                summary=f"Packet retry requested for {changes.get('count', 0)} request(s)",
                is_system=True,
            )))
        elif log.model_name == 'ESignEvent':
            events.append((log.timestamp.isoformat(), SignatureTimelineEntry(
                timestamp=log.timestamp.isoformat(),
                action='provider',
                actor='Provider',
                summary=f"Provider event {changes.get('to_status') or changes.get('status') or 'processed'}",
                is_system=True,
            )))

    events.sort(key=lambda item: item[0] or '')
    return [entry for _, entry in events]
