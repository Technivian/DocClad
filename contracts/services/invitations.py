"""Invitation email delivery (Phase 4D).

Separates invitation STATE from delivery STATE: a mail-provider failure records a
safe, classified delivery error and leaves the invitation valid (the admin gets
an actionable message + copy-link and can retry). Never uses fail_silently, never
logs the invitation token, and never stores raw exception internals.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

logger = logging.getLogger(__name__)


def build_invitation_message(invitation, personal_message: str | None = None):
    from contracts.services.url_builder import build_invitation_url
    invite_url = build_invitation_url(invitation.token)
    subject = f"You're invited to join {invitation.organization.name}"
    body_parts = [
        f"You have been invited to join {invitation.organization.name} as "
        f"{invitation.get_role_display()}.",
    ]
    note = (personal_message or '').strip()
    if note:
        body_parts.append(f'\nMessage from your inviter:\n{note}')
    body_parts.append(f'\nAccept invitation: {invite_url}\n\nThis link expires in 7 days.')
    return subject, '\n'.join(body_parts)


def deliver_invitation(invitation, *, actor=None, request=None, personal_message: str | None = None):
    """Attempt delivery; record delivery state + chained audit. Returns bool sent.

    Does not raise on provider failure — the caller decides how to surface it.
    """
    from contracts.middleware import log_action
    from contracts.models import AuditLog, OrganizationInvitation

    subject, body = build_invitation_message(invitation, personal_message=personal_message)
    invitation.last_delivery_attempt_at = timezone.now()
    try:
        send_mail(
            subject=subject, message=body,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
            recipient_list=[invitation.email], fail_silently=False,
        )
    except Exception as exc:  # noqa: BLE001
        # Safe classification only — never the message/traceback or the token.
        invitation.delivery_status = OrganizationInvitation.DeliveryStatus.FAILED
        invitation.delivery_error = type(exc).__name__[:100]
        invitation.save(update_fields=['delivery_status', 'delivery_error', 'last_delivery_attempt_at'])
        logger.warning('invitation delivery failed id=%s error_class=%s',
                       invitation.id, type(exc).__name__)
        log_action(
            actor, AuditLog.Action.UPDATE, 'OrganizationInvitation',
            object_id=invitation.id, object_repr=invitation.email,
            organization=invitation.organization, request=request,
            event_type='invite.delivery_failed', outcome='failure',
            changes={'event': 'invite.delivery_failed', 'error_class': type(exc).__name__},
        )
        return False

    invitation.delivery_status = OrganizationInvitation.DeliveryStatus.SENT
    invitation.delivery_error = ''
    invitation.save(update_fields=['delivery_status', 'delivery_error', 'last_delivery_attempt_at'])
    log_action(
        actor, AuditLog.Action.UPDATE, 'OrganizationInvitation',
        object_id=invitation.id, object_repr=invitation.email,
        organization=invitation.organization, request=request,
        event_type='invite.delivery_succeeded',
        changes={'event': 'invite.delivery_succeeded'},
    )
    return True
