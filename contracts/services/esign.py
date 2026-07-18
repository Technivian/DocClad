from __future__ import annotations

from datetime import datetime

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from contracts.models import AuditLog, SignatureRequest
from contracts.services.signature_audit import log_signature_packet_completed, log_signature_packet_sent


class ESignReconciliationError(RuntimeError):
    pass


class ESignTransitionError(RuntimeError):
    pass


PROVIDER_STATUS_MAP = {
    'created': SignatureRequest.Status.PENDING,
    'pending': SignatureRequest.Status.PENDING,
    'sent': SignatureRequest.Status.SENT,
    'delivered': SignatureRequest.Status.SENT,
    'viewed': SignatureRequest.Status.VIEWED,
    'opened': SignatureRequest.Status.VIEWED,
    'signed': SignatureRequest.Status.SIGNED,
    'completed': SignatureRequest.Status.SIGNED,
    'declined': SignatureRequest.Status.DECLINED,
    'rejected': SignatureRequest.Status.DECLINED,
    'expired': SignatureRequest.Status.EXPIRED,
    'cancelled': SignatureRequest.Status.CANCELLED,
    'canceled': SignatureRequest.Status.CANCELLED,
}


STATUS_PRECEDENCE = {
    SignatureRequest.Status.PENDING: 10,
    SignatureRequest.Status.SENT: 20,
    SignatureRequest.Status.VIEWED: 30,
    SignatureRequest.Status.SIGNED: 100,
    SignatureRequest.Status.DECLINED: 100,
    SignatureRequest.Status.EXPIRED: 100,
    SignatureRequest.Status.CANCELLED: 100,
}


def _parse_event_at(raw_value: str | None) -> datetime | None:
    raw = str(raw_value or '').strip()
    if not raw:
        return None
    parsed = parse_datetime(raw)
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.utc)
    return parsed


def _resolve_internal_status(provider_status: str | None) -> str:
    key = str(provider_status or '').strip().lower()
    status = PROVIDER_STATUS_MAP.get(key)
    if not status:
        raise ESignReconciliationError(f'Unsupported provider status: {provider_status}')
    return status


def _is_duplicate_event(signature_request: SignatureRequest, event_id: str) -> bool:
    token = f'event:{event_id}'
    return AuditLog.objects.filter(
        model_name='ESignEvent',
        object_id=signature_request.id,
        object_repr=token,
    ).exists()


def transition_signature_request(
    signature_request: SignatureRequest,
    new_status: str,
    *,
    actor=None,
    event_at: datetime | None = None,
    external_id: str | None = None,
    decline_reason: str | None = None,
    ip_address: str | None = None,
    execution_certificate_url: str | None = None,
    enforce_actor: bool = True,
    dry_run: bool = False,
):
    from_status = signature_request.status
    if not signature_request.can_transition_to(new_status):
        raise ESignTransitionError('Invalid signature status transition.')
    if enforce_actor and not signature_request.can_actor_transition(actor, new_status):
        raise ESignTransitionError('You are not authorized to perform this signature transition.')

    transition_at = event_at or timezone.now()
    if dry_run:
        return {
            'from_status': from_status,
            'to_status': new_status,
            'applied': False,
            'dry_run': True,
            'event_at': transition_at,
        }

    signature_request.status = new_status
    if external_id:
        signature_request.external_id = str(external_id).strip()
    if execution_certificate_url:
        signature_request.execution_certificate_url = str(execution_certificate_url).strip()
    if decline_reason:
        signature_request.decline_reason = str(decline_reason).strip()
    if ip_address:
        signature_request.ip_address = str(ip_address).strip()

    if new_status == SignatureRequest.Status.SENT:
        signature_request.sent_at = transition_at or signature_request.sent_at or timezone.now()
    elif new_status == SignatureRequest.Status.VIEWED:
        signature_request.viewed_at = transition_at or signature_request.viewed_at or timezone.now()
    elif new_status == SignatureRequest.Status.SIGNED:
        signature_request.signed_at = transition_at or signature_request.signed_at or timezone.now()
    elif new_status == SignatureRequest.Status.DECLINED:
        signature_request.declined_at = transition_at or signature_request.declined_at or timezone.now()
    signature_request.save()

    packet_request_ids = list(
        SignatureRequest.objects.filter(
            contract_id=signature_request.contract_id,
            organization_id=signature_request.organization_id,
        ).values_list('id', flat=True)
    )
    if new_status == SignatureRequest.Status.SENT:
        log_signature_packet_sent(
            user=actor,
            contract=signature_request.contract,
            organization=signature_request.organization,
            request_ids=packet_request_ids,
            request_count=len(packet_request_ids),
        )
    elif new_status == SignatureRequest.Status.SIGNED:
        all_signed = not SignatureRequest.objects.filter(
            contract_id=signature_request.contract_id,
            organization_id=signature_request.organization_id,
        ).exclude(status=SignatureRequest.Status.SIGNED).exists()
        if all_signed:
            log_signature_packet_completed(
                user=actor,
                contract=signature_request.contract,
                organization=signature_request.organization,
                request_ids=packet_request_ids,
                request_count=len(packet_request_ids),
            )
    return {
        'from_status': from_status,
        'to_status': new_status,
        'applied': True,
        'dry_run': False,
        'event_at': transition_at,
    }


def send_signature_request(signature_request: SignatureRequest, *, actor=None, provider=None):
    """Dispatch a PENDING signature request to the configured e-sign provider.

    Resolves the outbound provider, records the returned external reference and
    signing URL, and transitions the request PENDING -> SENT (which also emits
    the packet-sent audit event). Idempotent: a request that is already SENT (or
    further along) is returned unchanged rather than re-dispatched.
    """
    from contracts.services.signature_providers import get_signature_provider

    if signature_request.status != SignatureRequest.Status.PENDING:
        # Already sent / signed / cancelled — nothing to dispatch.
        return {
            'sent': False,
            'reason': 'not_pending',
            'status': signature_request.status,
            'signature_request_id': signature_request.id,
        }

    provider = provider or get_signature_provider()
    result = provider.send(signature_request)

    signature_request.external_id = result.external_id
    signature_request.esign_provider = result.provider
    signature_request.signing_url = result.signing_url

    transition_signature_request(
        signature_request,
        SignatureRequest.Status.SENT,
        actor=actor,
        external_id=result.external_id,
        enforce_actor=False,
    )
    # transition_signature_request saves; persist the provider metadata too.
    signature_request.save(update_fields=['esign_provider', 'signing_url'])

    return {
        'sent': True,
        'provider': result.provider,
        'external_id': result.external_id,
        'signing_url': result.signing_url,
        'signature_request_id': signature_request.id,
    }


def refresh_signature_request(signature_request: SignatureRequest, *, provider=None) -> dict:
    """Refresh an externally dispatched request without relying on webhooks.

    Documenso webhooks require a team account, while its free personal plan
    still supports API sends. This explicit refresh keeps the free-plan demo
    honest and updates the same governed status/audit path used by webhooks.
    """
    from contracts.services.signature_providers import SignatureProviderError, get_signature_provider

    if signature_request.esign_provider != 'documenso':
        raise SignatureProviderError('Status refresh is currently available for Documenso requests only.')
    if not signature_request.external_id:
        raise SignatureProviderError('This request does not have a Documenso envelope id.')

    provider = provider or get_signature_provider()
    fetch_status = getattr(provider, 'fetch_status', None)
    if not callable(fetch_status):
        raise SignatureProviderError('The configured e-signature provider does not support status refresh.')

    raw = fetch_status(signature_request.external_id)
    provider_status = str(raw.get('status') or '').strip().upper()
    recipients = raw.get('recipients') or raw.get('Recipient') or []

    rejected_recipient = next(
        (
            recipient for recipient in recipients
            if str(recipient.get('signingStatus') or '').strip().upper() == 'REJECTED'
        ),
        None,
    )
    if rejected_recipient or provider_status == 'REJECTED':
        normalized_status = 'rejected'
    elif provider_status == 'COMPLETED':
        normalized_status = 'completed'
    elif any(str(recipient.get('readStatus') or '').strip().upper() == 'OPENED' for recipient in recipients):
        normalized_status = 'opened'
    elif provider_status == 'PENDING':
        normalized_status = 'sent'
    elif provider_status == 'DRAFT':
        normalized_status = 'created'
    else:
        raise ESignReconciliationError(f'Unsupported Documenso envelope status: {provider_status}')

    target_status = _resolve_internal_status(normalized_status)
    event_at = str(raw.get('completedAt') or raw.get('updatedAt') or raw.get('createdAt') or '').strip()
    if signature_request.status == target_status:
        return {
            'refreshed': True,
            'changed': False,
            'status': signature_request.status,
            'provider_status': provider_status,
            'signature_request_id': signature_request.id,
        }

    result = apply_esign_event(
        signature_request,
        {
            'event_id': f'documenso-refresh-{signature_request.external_id}-{normalized_status}-{event_at or "current"}',
            'provider': 'documenso',
            'external_id': signature_request.external_id,
            'status': normalized_status,
            'event_at': event_at or None,
            'decline_reason': (rejected_recipient or {}).get('rejectionReason', ''),
        },
        dry_run=False,
    )
    return {
        'refreshed': True,
        'changed': result.get('result') == 'applied',
        'status': signature_request.status,
        'provider_status': provider_status,
        'signature_request_id': signature_request.id,
        'result': result.get('result'),
    }


def apply_esign_event(signature_request: SignatureRequest, event: dict, *, dry_run: bool = False) -> dict:
    event_id = str(event.get('event_id') or '').strip()
    if not event_id:
        raise ESignReconciliationError('Event is missing event_id.')
    if _is_duplicate_event(signature_request, event_id):
        return {'result': 'duplicate', 'event_id': event_id, 'signature_request_id': signature_request.id}

    target_status = _resolve_internal_status(event.get('status'))
    event_at = _parse_event_at(event.get('event_at'))
    current_score = STATUS_PRECEDENCE.get(signature_request.status, 0)
    target_score = STATUS_PRECEDENCE.get(target_status, 0)
    should_apply = target_score >= current_score
    if signature_request.status in {
        SignatureRequest.Status.SIGNED,
        SignatureRequest.Status.DECLINED,
        SignatureRequest.Status.EXPIRED,
        SignatureRequest.Status.CANCELLED,
    } and target_score < current_score:
        should_apply = False

    change_payload = {
        'event_id': event_id,
        'provider': str(event.get('provider') or '').strip(),
        'external_id': str(event.get('external_id') or '').strip(),
        'from_status': signature_request.status,
        'to_status': target_status,
        'applied': should_apply and not dry_run,
        'dry_run': dry_run,
        'event_at': event_at.isoformat() if event_at else None,
    }

    if should_apply and not dry_run:
        external_id = str(event.get('external_id') or '').strip()
        transition_signature_request(
            signature_request,
            target_status,
            actor=None,
            event_at=event_at,
            external_id=external_id,
            decline_reason=event.get('decline_reason'),
            ip_address=event.get('ip_address'),
            execution_certificate_url=event.get('execution_certificate_url'),
            enforce_actor=False,
        )

    if not dry_run:
        # Webhook reconciliation is a DELIVERY/reconcile event (not itself a
        # business state transition — the transition above is the state change).
        # Route through the canonical chain as a 'webhook' actor. Dedup upstream
        # (_is_duplicate_event) prevents duplicate-delivery noise.
        from contracts.middleware import log_action
        _esign_org_id = getattr(signature_request, 'organization_id', None) or (
            signature_request.contract.organization_id if getattr(signature_request, 'contract_id', None) else None
        )
        log_action(
            None, AuditLog.Action.UPDATE, 'ESignEvent',
            object_id=signature_request.id, object_repr=f'event:{event_id}',
            organization_id=_esign_org_id, actor_type='webhook',
            event_type='signature.webhook_reconciled',
            changes={'event': 'signature.webhook_reconciled', **(change_payload or {})},
        )

    if not should_apply:
        return {'result': 'stale', 'event_id': event_id, 'signature_request_id': signature_request.id}
    return {'result': 'applied' if not dry_run else 'would_apply', 'event_id': event_id, 'signature_request_id': signature_request.id}
