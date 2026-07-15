"""Centralized outbound notification service (Phase 5L).

Design rules:
- All outbound links use build_canonical_url(). Never request.build_absolute_uri().
- Never use fail_silently=True. Log provider errors with safe classification only
  (error class name; never raw exception message, stack trace, or payload).
- OTP values, recovery codes, session tokens, and raw provider payloads must
  never appear in audit metadata, logs, or email headers.
- Job failure alerts are deduplicated: one alert per job_name per hour maximum.
- Permitted MFA email content: 6-digit OTP codes in the body (email is an approved
  delivery channel for the OTP factor). Recovery code *values* must NOT be emailed.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

logger = logging.getLogger(__name__)

_ALERT_DEDUP_WINDOW = timedelta(hours=1)


def _from_email() -> str:
    return getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@clmone.local')


def _operator_email() -> str | None:
    return getattr(settings, 'OPERATOR_ALERT_EMAIL', None) or None


def _send(*, subject: str, body: str, to: str, event_tag: str) -> bool:
    """Attempt one email send. Never fail_silently. Returns True on success."""
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=_from_email(),
            recipient_list=[to],
            fail_silently=False,
        )
        logger.debug('notification sent tag=%s to=%s', event_tag, to)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            'notification send failed tag=%s error_class=%s',
            event_tag, type(exc).__name__,
        )
        return False


# ---------------------------------------------------------------------------
# MFA code email (OTP value permitted — email is the approved delivery channel)
# ---------------------------------------------------------------------------

def send_mfa_code_email(user, code: str) -> bool:
    """Send the 6-digit OTP to the user for MFA challenge or enrollment."""
    from contracts.services.url_builder import build_canonical_url
    challenge_url = build_canonical_url('/mfa/challenge/')
    body = (
        f'Your CLM One verification code is: {code}\n\n'
        'This code expires in 10 minutes. Do not share it with anyone.\n\n'
        f'Enter it at: {challenge_url}'
    )
    return _send(
        subject='Your CLM One verification code',
        body=body,
        to=user.email,
        event_tag='mfa.code_email',
    )


# ---------------------------------------------------------------------------
# MFA security-change notifications (no OTP values, no recovery codes)
# ---------------------------------------------------------------------------

def send_mfa_enrolled_notification(user) -> bool:
    """Notify the user that MFA was enabled on their account."""
    from contracts.services.url_builder import build_canonical_url
    settings_url = build_canonical_url('/settings/')
    body = (
        'Two-factor authentication has been enabled on your CLM One account.\n\n'
        'If you did not enable this, contact your organization administrator immediately.\n\n'
        f'Manage security settings: {settings_url}'
    )
    return _send(
        subject='Two-factor authentication enabled — CLM One',
        body=body,
        to=user.email,
        event_tag='mfa.enrolled_notification',
    )


def send_mfa_disabled_notification(user) -> bool:
    """Notify the user that MFA was disabled on their account."""
    from contracts.services.url_builder import build_canonical_url
    settings_url = build_canonical_url('/settings/')
    body = (
        'Two-factor authentication has been disabled on your CLM One account.\n\n'
        'If you did not make this change, contact your organization administrator immediately.\n\n'
        f'Re-enable MFA: {settings_url}'
    )
    return _send(
        subject='Two-factor authentication disabled — CLM One',
        body=body,
        to=user.email,
        event_tag='mfa.disabled_notification',
    )


def send_mfa_recovery_codes_regenerated_notification(user) -> bool:
    """Notify that recovery codes were regenerated. No code values included."""
    from contracts.services.url_builder import build_canonical_url
    profile_url = build_canonical_url('/profile/')
    body = (
        'New MFA recovery codes have been generated for your CLM One account.\n\n'
        'Your previous recovery codes are now invalid. '
        'Save the new codes from your profile page in a secure location.\n\n'
        'If you did not generate new codes, contact your administrator immediately.\n\n'
        f'View your profile: {profile_url}'
    )
    return _send(
        subject='New MFA recovery codes generated — CLM One',
        body=body,
        to=user.email,
        event_tag='mfa.recovery_codes_regenerated_notification',
    )


def send_suspicious_recovery_use_notification(user) -> bool:
    """Alert the user that a recovery code was used to access their account."""
    from contracts.services.url_builder import build_canonical_url
    settings_url = build_canonical_url('/settings/')
    body = (
        'A recovery code was used to access your CLM One account.\n\n'
        'If this was not you, your account may be compromised. '
        'Contact your organization administrator immediately and revoke all active sessions.\n\n'
        f'Review your security settings: {settings_url}'
    )
    return _send(
        subject='Recovery code used on your account — CLM One',
        body=body,
        to=user.email,
        event_tag='mfa.suspicious_recovery_use',
    )


# ---------------------------------------------------------------------------
# Operator job-failure alert (one alert per job_name per hour)
# ---------------------------------------------------------------------------

def send_operator_job_failure_alert(job_run) -> bool:
    """Email the operator when a scheduled job fails.

    Deduplication: skips if another run of the same job_name already sent an
    alert within the last hour. Stamps alert_sent_at on the run row on success.

    Safe metadata only: job name, run ID, scope, timestamps, record counts,
    error class. No stack traces, document content, personal data, or raw
    provider payloads.
    """
    from contracts.models import ScheduledJobRun
    from contracts.services.url_builder import build_canonical_url

    recipient = _operator_email()
    if not recipient:
        logger.debug('job_alert skipped: OPERATOR_ALERT_EMAIL not configured')
        return False

    cutoff = timezone.now() - _ALERT_DEDUP_WINDOW
    already_alerted = ScheduledJobRun.objects.filter(
        job_name=job_run.job_name,
        alert_sent_at__gte=cutoff,
    ).exclude(pk=job_run.pk).exists()
    if already_alerted:
        logger.debug('job_alert deduplicated: job=%s', job_run.job_name)
        return False

    ops_url = build_canonical_url('/operations/')
    scope = job_run.organization.slug if job_run.organization_id else 'global'
    duration = job_run.duration_seconds
    duration_str = f'{duration:.1f}s' if duration is not None else 'unknown'
    started = (
        job_run.started_at.strftime('%Y-%m-%d %H:%M:%S UTC')
        if job_run.started_at else 'unknown'
    )
    # Error summary is already truncated and sanitised in job_runs.py (max 2000
    # chars, type+message only, never a full traceback or raw provider payload).
    error_preview = (job_run.error_summary or 'unknown')[:200]

    body = (
        f'A scheduled job failed on CLM One.\n\n'
        f'Job name:        {job_run.job_name}\n'
        f'Run ID:          {job_run.run_id}\n'
        f'Scope:           {scope}\n'
        f'Started at:      {started}\n'
        f'Duration:        {duration_str}\n'
        f'Records seen:    {job_run.records_examined}\n'
        f'Records changed: {job_run.records_changed}\n'
        f'Error:           {error_preview}\n\n'
        f'Operations dashboard: {ops_url}\n\n'
        'This alert fires at most once per job per hour. '
        'Repeated failures within the window will not generate additional alerts.'
    )
    subject = f'[CLM One] Scheduled job failed: {job_run.job_name}'

    sent = _send(subject=subject, body=body, to=recipient, event_tag='job.failure_alert')
    if sent:
        ScheduledJobRun.objects.filter(pk=job_run.pk).update(alert_sent_at=timezone.now())
    return sent
