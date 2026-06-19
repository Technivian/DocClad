from __future__ import annotations

from contracts.middleware import log_action
from contracts.models import AuditLog, Contract, Organization, SignatureRequest


def _packet_object_repr(contract: Contract) -> str:
    return f'Signature packet: {contract.title}'


def log_signature_packet_event(
    *,
    user,
    contract: Contract,
    organization: Organization | None,
    event: str,
    changes: dict | None = None,
    action: str = AuditLog.Action.UPDATE,
    request=None,
):
    payload = {
        'event': event,
        'organization_id': getattr(organization, 'id', None),
    }
    if changes:
        payload.update(changes)
    log_action(
        user,
        action,
        'SignaturePacket',
        object_id=contract.id,
        object_repr=_packet_object_repr(contract),
        changes=payload,
        request=request,
    )


def log_signature_packet_created(*, user, contract: Contract, organization: Organization | None, request_count: int, request=None):
    log_signature_packet_event(
        user=user,
        contract=contract,
        organization=organization,
        event='signature_packet_created',
        action=AuditLog.Action.CREATE,
        changes={'request_count': request_count},
        request=request,
    )


def log_signature_packet_sent(
    *,
    user,
    contract: Contract,
    organization: Organization | None,
    request_ids: list[int],
    request_count: int,
    request=None,
):
    log_signature_packet_event(
        user=user,
        contract=contract,
        organization=organization,
        event='signature_packet_sent',
        changes={'request_ids': request_ids, 'request_count': request_count},
        request=request,
    )


def log_signature_packet_completed(
    *,
    user,
    contract: Contract,
    organization: Organization | None,
    request_ids: list[int],
    request_count: int,
    request=None,
):
    log_signature_packet_event(
        user=user,
        contract=contract,
        organization=organization,
        event='signature_packet_completed',
        changes={'request_ids': request_ids, 'request_count': request_count},
        request=request,
    )


def log_signature_packet_resend(
    *,
    user,
    contract: Contract,
    organization: Organization | None,
    request_ids: list[int],
    request_count: int,
    request=None,
):
    log_signature_packet_event(
        user=user,
        contract=contract,
        organization=organization,
        event='signature_packet_resend',
        changes={'request_ids': request_ids, 'request_count': request_count},
        request=request,
    )


def log_signature_packet_cancel(
    *,
    user,
    contract: Contract,
    organization: Organization | None,
    request_ids: list[int],
    request_count: int,
    request=None,
):
    log_signature_packet_event(
        user=user,
        contract=contract,
        organization=organization,
        event='signature_packet_cancel',
        changes={'request_ids': request_ids, 'request_count': request_count},
        request=request,
    )


def log_signature_packet_retry(
    *,
    user,
    contract: Contract,
    organization: Organization | None,
    request_ids: list[int],
    request_count: int,
    request=None,
):
    log_signature_packet_event(
        user=user,
        contract=contract,
        organization=organization,
        event='signature_packet_retry',
        changes={'request_ids': request_ids, 'request_count': request_count},
        request=request,
    )
