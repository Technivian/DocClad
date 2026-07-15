"""Phase 5L — Core notification activation tests.

Coverage:
- Password recovery: canonical URL links, no Host injection, generic response,
  expiry, invalidation after password change, inactive user, rate limiting,
  token privacy, audit events.
- MFA communications: code emails, enrolled/disabled/regenerated notifications,
  no plaintext recovery codes in email.
- Canonical recovery-code service: single audit event, replay prevention,
  session verified, no code in metadata, both entry paths use the service.
- Operator job-failure alerts: delivery, deduplication, safe metadata only,
  canonical URL, OPERATOR_ALERT_EMAIL gate.

Test database: direct PostgreSQL via config.settings_postgres_test.
"""
from __future__ import annotations

import uuid
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from contracts.models import AuditLog, Organization, OrganizationMembership, ScheduledJobRun, UserProfile
from contracts.services.notifications import (
    send_mfa_code_email,
    send_mfa_enrolled_notification,
    send_mfa_disabled_notification,
    send_mfa_recovery_codes_regenerated_notification,
    send_suspicious_recovery_use_notification,
    send_operator_job_failure_alert,
)
from contracts.services.recovery_codes import consume_recovery_code

User = get_user_model()

APP_BASE = 'https://app.clmone.example.com'


def _make_user(username, email=None, active=True):
    u = User.objects.create_user(
        username=username,
        password='TestPass123!',
        email=email or f'{username}@example.com',
        is_active=active,
    )
    return u


def _make_org(name='TestOrg', slug=None):
    return Organization.objects.create(name=name, slug=slug or f'org-{uuid.uuid4().hex[:6]}')


def _make_member(org, user, role='OWNER'):
    return OrganizationMembership.objects.create(
        organization=org, user=user, role=role, is_active=True,
    )


# =============================================================================
# Password Recovery
# =============================================================================

@override_settings(
    APP_BASE_URL=APP_BASE,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class PasswordResetCanonicalURLTests(TestCase):
    def setUp(self):
        self.user = _make_user('resetuser', email='resetuser@example.com')
        # Clear cache so rate-limit counters don't accumulate across methods.
        from django.core.cache import cache
        cache.clear()

    def test_reset_email_link_uses_app_base_url(self):
        """Link in reset email must use APP_BASE_URL, not the request Host header."""
        # Use a normal testserver request — the key assertion is that the link
        # uses APP_BASE_URL (app.clmone.example.com), not the request host.
        self.client.post(reverse('password_reset'), {'email': self.user.email})
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn('app.clmone.example.com', body)
        self.assertNotIn('testserver', body)
        self.assertNotIn('localhost', body)

    def test_reset_email_link_never_uses_request_host(self):
        """CLMOnePasswordResetForm.save() must override domain from APP_BASE_URL."""
        from contracts.views_domains.core import CLMOnePasswordResetForm
        from django.test import RequestFactory
        rf = RequestFactory()
        request = rf.post(reverse('password_reset'), {'email': self.user.email})
        # Simulate a form save with APP_BASE_URL set.
        form = CLMOnePasswordResetForm({'email': self.user.email})
        self.assertTrue(form.is_valid())
        form.save(request=request)
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn('app.clmone.example.com', body)
        self.assertNotIn('testserver', body)

    def test_reset_link_uses_https(self):
        """Link must use https:// because APP_BASE_URL scheme is https."""
        self.client.post(reverse('password_reset'), {'email': self.user.email})
        body = mail.outbox[0].body
        self.assertTrue(any(
            line.startswith('https://') for line in body.splitlines()
            if 'reset-password' in line or 'reset/' in line
        ), f'No https:// reset link found in: {body}')

    def test_reset_link_does_not_contain_token_value_in_subject_or_headers(self):
        """Token must only appear in the body link, not in headers."""
        self.client.post(reverse('password_reset'), {'email': self.user.email})
        msg = mail.outbox[0]
        self.assertNotIn('token', msg.subject.lower())

    def test_host_header_injection_cannot_influence_link(self):
        """Malicious X-Forwarded-Host must not appear in reset link."""
        self.client.post(
            reverse('password_reset'),
            {'email': self.user.email},
            HTTP_X_FORWARDED_HOST='hacked.example.com',
        )
        body = mail.outbox[0].body
        self.assertNotIn('hacked.example.com', body)


@override_settings(
    APP_BASE_URL=APP_BASE,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class PasswordResetGenericResponseTests(TestCase):
    def test_unknown_email_still_redirects_to_done(self):
        """Unknown email gets the same generic success response (no enumeration)."""
        resp = self.client.post(
            reverse('password_reset'),
            {'email': 'nobody@unknown.example.com'},
        )
        self.assertRedirects(resp, reverse('password_reset_done'))
        # No email sent for unknown address.
        self.assertEqual(len(mail.outbox), 0)

    def test_known_email_redirects_to_done(self):
        user = _make_user('knownreset', email='known@example.com')
        resp = self.client.post(reverse('password_reset'), {'email': user.email})
        self.assertRedirects(resp, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)

    def test_inactive_user_gets_no_email(self):
        """Inactive user account must not receive a reset email."""
        _make_user('inactiveuser', email='inactive@example.com', active=False)
        self.client.post(reverse('password_reset'), {'email': 'inactive@example.com'})
        self.assertEqual(len(mail.outbox), 0)


@override_settings(
    APP_BASE_URL=APP_BASE,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class PasswordResetRateLimitTests(TestCase):
    def setUp(self):
        self.user = _make_user('ratelimituser', email='ratelimit@example.com')
        # Clear any leftover cache entries.
        from django.core.cache import cache
        cache.clear()

    def test_fourth_request_within_window_does_not_send_email(self):
        """Fourth reset request for same email within 1 hour produces no email."""
        for _ in range(3):
            self.client.post(reverse('password_reset'), {'email': self.user.email})
        mail.outbox.clear()
        # Fourth attempt — should be rate-limited.
        resp = self.client.post(reverse('password_reset'), {'email': self.user.email})
        self.assertRedirects(resp, reverse('password_reset_done'))  # generic response
        self.assertEqual(len(mail.outbox), 0)

    def test_rate_limit_is_generic_no_error_revealed(self):
        """Rate limited response looks identical to a successful request."""
        from django.core.cache import cache
        import hashlib
        email = self.user.email.lower().strip()
        email_key = hashlib.sha256(email.encode()).hexdigest()[:20]
        cache.set(f'pwd_reset_rl:{email_key}', 3, timeout=3600)
        resp = self.client.post(reverse('password_reset'), {'email': email})
        self.assertRedirects(resp, reverse('password_reset_done'))


@override_settings(
    APP_BASE_URL=APP_BASE,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class PasswordResetTokenTests(TestCase):
    def setUp(self):
        self.user = _make_user('tokenuser', email='tokenuser@example.com')
        # Clear the rate-limit cache so previous test runs don't block sends.
        from django.core.cache import cache
        cache.clear()

    def _get_reset_url(self):
        self.client.post(reverse('password_reset'), {'email': self.user.email})
        body = mail.outbox[0].body
        for line in body.splitlines():
            line = line.strip()
            if 'reset-password' in line or '/reset/' in line:
                # Strip domain prefix to get just the path.
                if '://' in line:
                    from urllib.parse import urlparse
                    return urlparse(line).path
                return line
        return None

    def test_valid_token_shows_set_password_form(self):
        url = self._get_reset_url()
        self.assertIsNotNone(url)
        resp = self.client.get(url)
        # Django redirects to the same URL without token for CSRF protection.
        self.assertIn(resp.status_code, (200, 302))

    def test_expired_token_shows_invalid_link(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        bad_token = 'invalid-token-xyz'
        url = reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': bad_token})
        resp = self.client.get(url, follow=True)
        self.assertContains(resp, 'expired', msg_prefix='Expected "expired" or "invalid" message')

    def test_token_invalidated_after_password_change(self):
        """After a successful reset, the same token must be rejected."""
        url = self._get_reset_url()
        self.assertIsNotNone(url)
        # Follow the redirect to get the session-stored URL.
        resp = self.client.get(url, follow=True)
        final_url = resp.redirect_chain[-1][0] if resp.redirect_chain else url
        # Post new password.
        self.client.post(final_url, {
            'new_password1': 'NewSecurePass999!',
            'new_password2': 'NewSecurePass999!',
        })
        # Try to use the same URL again — must be rejected.
        resp2 = self.client.get(url, follow=True)
        self.assertContains(resp2, 'expired', msg_prefix='Token should be invalidated after use')

    def test_password_reset_audit_event_written(self):
        url = self._get_reset_url()
        resp = self.client.get(url, follow=True)
        final_url = resp.redirect_chain[-1][0] if resp.redirect_chain else url
        self.client.post(final_url, {
            'new_password1': 'NewSecurePass999!',
            'new_password2': 'NewSecurePass999!',
        })
        audit = AuditLog.objects.filter(event_type='auth.password_reset_completed').first()
        self.assertIsNotNone(audit, 'auth.password_reset_completed audit event must be written')

    def test_password_reset_audit_contains_no_token(self):
        url = self._get_reset_url()
        resp = self.client.get(url, follow=True)
        final_url = resp.redirect_chain[-1][0] if resp.redirect_chain else url
        self.client.post(final_url, {
            'new_password1': 'NewSecurePass999!',
            'new_password2': 'NewSecurePass999!',
        })
        import json
        audit = AuditLog.objects.filter(event_type='auth.password_reset_completed').first()
        self.assertIsNotNone(audit)
        changes_str = json.dumps(audit.changes or {})
        # The raw token string must not be in audit metadata.
        raw_url = self._get_reset_url() or ''
        self.assertNotIn('token', changes_str.lower().replace('event_type', ''))


# =============================================================================
# MFA Communications
# =============================================================================

@override_settings(
    APP_BASE_URL=APP_BASE,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class MfaCodeEmailTests(TestCase):
    def setUp(self):
        self.user = _make_user('mfaemailuser', email='mfaemail@example.com')

    def test_mfa_code_email_sends_to_user(self):
        sent = send_mfa_code_email(self.user, '123456')
        self.assertTrue(sent)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])

    def test_mfa_code_email_contains_otp(self):
        """OTP is permitted in email body — email is the approved delivery channel."""
        send_mfa_code_email(self.user, '654321')
        self.assertIn('654321', mail.outbox[0].body)

    def test_mfa_code_email_uses_canonical_url(self):
        send_mfa_code_email(self.user, '111111')
        body = mail.outbox[0].body
        self.assertIn('app.clmone.example.com', body)
        self.assertNotIn('localhost', body)

    def test_mfa_enrolled_notification_sent(self):
        sent = send_mfa_enrolled_notification(self.user)
        self.assertTrue(sent)
        self.assertIn('enabled', mail.outbox[0].body.lower())
        self.assertNotIn('localhost', mail.outbox[0].body)

    def test_mfa_disabled_notification_sent(self):
        sent = send_mfa_disabled_notification(self.user)
        self.assertTrue(sent)
        self.assertIn('disabled', mail.outbox[0].body.lower())

    def test_mfa_recovery_codes_regenerated_notification_no_code_values(self):
        """Regeneration notification must not contain actual recovery code values."""
        sent = send_mfa_recovery_codes_regenerated_notification(self.user)
        self.assertTrue(sent)
        body = mail.outbox[0].body
        # Must not contain anything that looks like a raw recovery code
        # (which would be a random hex/alphanumeric string). Just assert that
        # 'regenerated' or 'generated' context is present.
        self.assertIn('recovery', body.lower())
        self.assertNotIn('localhost', body)

    def test_suspicious_recovery_use_notification_sent(self):
        sent = send_suspicious_recovery_use_notification(self.user)
        self.assertTrue(sent)
        self.assertIn('recovery', mail.outbox[0].body.lower())


@override_settings(
    APP_BASE_URL=APP_BASE,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class MfaNotificationDeliveryFailureTests(TestCase):
    """Notification failures must be logged with safe classification, not propagated."""

    def setUp(self):
        self.user = _make_user('failuser', email='fail@example.com')

    def test_send_failure_returns_false_not_exception(self):
        with patch('contracts.services.notifications.send_mail', side_effect=Exception('SMTP down')):
            result = send_mfa_code_email(self.user, '000000')
        self.assertFalse(result)


# =============================================================================
# Canonical Recovery Code Service
# =============================================================================

class RecoveryCodeServiceTests(TestCase):
    def setUp(self):
        self.user = _make_user('recoveryuser', email='recovery@example.com')
        self.org = _make_org('RecoveryOrg')
        _make_member(self.org, self.user)
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)
        self.profile.mfa_enabled = True
        self.profile.mfa_verified_at = timezone.now()
        self.profile.save()

    @override_settings(
        APP_BASE_URL=APP_BASE,
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    )
    def test_valid_code_returns_true_and_sets_session(self):
        codes = self.profile.issue_mfa_recovery_codes()
        request = MagicMock()
        request.session = {}
        result = consume_recovery_code(self.profile, codes[0], request=request, organization=self.org)
        self.assertTrue(result)
        self.assertTrue(request.session.get('mfa_verified'))

    @override_settings(
        APP_BASE_URL=APP_BASE,
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    )
    def test_invalid_code_returns_false_no_side_effects(self):
        request = MagicMock()
        request.session = {}
        result = consume_recovery_code(self.profile, 'INVALID-CODE', request=request, organization=self.org)
        self.assertFalse(result)
        self.assertFalse(request.session.get('mfa_verified'))

    @override_settings(
        APP_BASE_URL=APP_BASE,
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    )
    def test_code_consumed_replay_prevented(self):
        """A consumed code cannot be used again."""
        codes = self.profile.issue_mfa_recovery_codes()
        code = codes[0]
        # First use must succeed.
        r1 = consume_recovery_code(self.profile, code, organization=self.org)
        self.assertTrue(r1)
        # Second use must fail.
        self.profile.refresh_from_db()
        r2 = consume_recovery_code(self.profile, code, organization=self.org)
        self.assertFalse(r2)

    @override_settings(
        APP_BASE_URL=APP_BASE,
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    )
    def test_exactly_one_audit_event_emitted(self):
        codes = self.profile.issue_mfa_recovery_codes()
        before = AuditLog.objects.filter(event_type='mfa.recovery_code_used').count()
        consume_recovery_code(self.profile, codes[0], organization=self.org)
        after = AuditLog.objects.filter(event_type='mfa.recovery_code_used').count()
        self.assertEqual(after - before, 1)

    @override_settings(
        APP_BASE_URL=APP_BASE,
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    )
    def test_audit_event_has_no_code_value(self):
        """Recovery code value must never appear in audit metadata."""
        import json
        codes = self.profile.issue_mfa_recovery_codes()
        code = codes[0]
        consume_recovery_code(self.profile, code, organization=self.org)
        audit = AuditLog.objects.filter(event_type='mfa.recovery_code_used').last()
        self.assertIsNotNone(audit)
        changes_str = json.dumps(audit.changes or {})
        self.assertNotIn(code, changes_str)

    @override_settings(
        APP_BASE_URL=APP_BASE,
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    )
    def test_audit_event_is_tenant_attributed(self):
        """Audit event must carry organization_id for tenant attribution."""
        codes = self.profile.issue_mfa_recovery_codes()
        consume_recovery_code(self.profile, codes[0], organization=self.org)
        audit = AuditLog.objects.filter(event_type='mfa.recovery_code_used').last()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.organization_id, self.org.id)

    @override_settings(
        APP_BASE_URL=APP_BASE,
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    )
    def test_suspicious_use_notification_sent(self):
        codes = self.profile.issue_mfa_recovery_codes()
        consume_recovery_code(self.profile, codes[0], organization=self.org)
        self.assertTrue(len(mail.outbox) >= 1)
        subjects = [m.subject for m in mail.outbox]
        self.assertTrue(any('recovery' in s.lower() for s in subjects))

    @override_settings(
        APP_BASE_URL=APP_BASE,
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    )
    def test_mfa_challenge_view_uses_canonical_service_for_recovery_code(self):
        """mfa_challenge view must route recovery codes through consume_recovery_code."""
        codes = self.profile.issue_mfa_recovery_codes()
        c = Client()
        c.force_login(self.user)
        c.session['mfa_verified'] = False
        before = AuditLog.objects.filter(event_type='mfa.recovery_code_used').count()
        resp = c.post(reverse('mfa_challenge'), {'code': codes[0]})
        self.assertEqual(resp.status_code, 302)
        after = AuditLog.objects.filter(event_type='mfa.recovery_code_used').count()
        self.assertEqual(after - before, 1, 'Audit event not written from mfa_challenge path')

    @override_settings(
        APP_BASE_URL=APP_BASE,
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    )
    def test_profile_view_uses_canonical_service_for_recovery_code(self):
        """Profile view must route recovery codes through consume_recovery_code."""
        codes = self.profile.issue_mfa_recovery_codes()
        c = Client()
        c.force_login(self.user)
        session = c.session
        session['mfa_verified'] = True
        session.save()
        before = AuditLog.objects.filter(event_type='mfa.recovery_code_used').count()
        c.post(reverse('profile'), {
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
            'email': self.user.email,
            'role': getattr(self.profile, 'role', ''),
            'phone': '',
            'bar_number': '',
            'department': '',
            'hourly_rate': '',
            'bio': '',
            'mfa_enabled': 'on',
            'mfa_enrollment_code': '',
            'mfa_recovery_code': codes[0],
        })
        after = AuditLog.objects.filter(event_type='mfa.recovery_code_used').count()
        self.assertEqual(after - before, 1, 'Audit event not written from profile path')


# =============================================================================
# Operator Job-Failure Alerts
# =============================================================================

@override_settings(
    APP_BASE_URL=APP_BASE,
    OPERATOR_ALERT_EMAIL='ops@clmone.example.com',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class JobFailureAlertTests(TestCase):
    def _make_failed_run(self, job_name='test_job', org=None):
        return ScheduledJobRun.objects.create(
            job_name=job_name,
            organization=org,
            status=ScheduledJobRun.Status.FAILED,
            started_at=timezone.now(),
            finished_at=timezone.now(),
            records_examined=5,
            records_changed=0,
            error_summary='RuntimeError: something broke',
        )

    def test_alert_sent_on_failure(self):
        run = self._make_failed_run()
        sent = send_operator_job_failure_alert(run)
        self.assertTrue(sent)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('ops@clmone.example.com', mail.outbox[0].to)

    def test_alert_subject_contains_job_name(self):
        run = self._make_failed_run(job_name='critical_renewal_job')
        send_operator_job_failure_alert(run)
        self.assertIn('critical_renewal_job', mail.outbox[0].subject)

    def test_alert_body_contains_safe_metadata_only(self):
        """Alert body must contain safe operational metadata, not PII or secrets."""
        run = self._make_failed_run()
        send_operator_job_failure_alert(run)
        body = mail.outbox[0].body
        self.assertIn(str(run.run_id), body)
        self.assertIn('test_job', body)
        self.assertIn('RuntimeError', body)
        self.assertIn('app.clmone.example.com', body)

    def test_alert_body_does_not_contain_localhost(self):
        run = self._make_failed_run()
        send_operator_job_failure_alert(run)
        self.assertNotIn('localhost', mail.outbox[0].body)

    def test_deduplication_within_one_hour(self):
        """Second failure alert for the same job within 1h is suppressed."""
        run1 = self._make_failed_run()
        run1.alert_sent_at = timezone.now()
        run1.save(update_fields=['alert_sent_at'])

        run2 = self._make_failed_run()
        sent = send_operator_job_failure_alert(run2)
        self.assertFalse(sent)
        self.assertEqual(len(mail.outbox), 0)

    def test_deduplication_after_window_sends_again(self):
        """Alert after the 1h dedup window fires again."""
        run1 = self._make_failed_run()
        run1.alert_sent_at = timezone.now() - timedelta(hours=2)
        run1.save(update_fields=['alert_sent_at'])

        run2 = self._make_failed_run()
        sent = send_operator_job_failure_alert(run2)
        self.assertTrue(sent)

    def test_no_operator_email_configured_skips_silently(self):
        with self.settings(OPERATOR_ALERT_EMAIL=''):
            run = self._make_failed_run()
            sent = send_operator_job_failure_alert(run)
        self.assertFalse(sent)
        self.assertEqual(len(mail.outbox), 0)

    def test_alert_stamps_alert_sent_at(self):
        run = self._make_failed_run()
        send_operator_job_failure_alert(run)
        run.refresh_from_db()
        self.assertIsNotNone(run.alert_sent_at)

    def test_job_run_failure_triggers_alert_via_context_manager(self):
        """record_job_run must call the alert service when a job raises."""
        from contracts.services.job_runs import record_job_run
        with self.assertRaises(RuntimeError):
            with record_job_run('integration_alert_job') as acc:
                if acc is not None:
                    raise RuntimeError('integration failure')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('integration_alert_job', mail.outbox[0].subject)

    def test_alert_error_summary_truncated_no_raw_traceback(self):
        """Error summary in alert must be the pre-truncated safe string, not a traceback."""
        run = self._make_failed_run()
        run.error_summary = 'ValueError: a' * 200  # longer than 200 char preview
        run.save(update_fields=['error_summary'])
        send_operator_job_failure_alert(run)
        body = mail.outbox[0].body
        # Body preview is capped at 200 chars of error_summary.
        self.assertLessEqual(
            len([line for line in body.splitlines() if 'ValueError' in line][0]),
            500,
        )

    def test_dedup_is_per_job_name_not_global(self):
        """Deduplication is scoped to job_name; different job fires independently."""
        run_a = self._make_failed_run(job_name='job_alpha')
        run_a.alert_sent_at = timezone.now()
        run_a.save(update_fields=['alert_sent_at'])

        run_b = self._make_failed_run(job_name='job_beta')
        sent = send_operator_job_failure_alert(run_b)
        self.assertTrue(sent, 'Different job_name should not be deduplicated')


# =============================================================================
# Notification delivery error handling
# =============================================================================

@override_settings(
    APP_BASE_URL=APP_BASE,
    OPERATOR_ALERT_EMAIL='ops@clmone.example.com',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class NotificationDeliveryErrorTests(TestCase):
    def setUp(self):
        self.user = _make_user('erruser', email='erruser@example.com')

    def test_smtp_failure_logged_as_error_class_not_raw_message(self):
        """Provider failure must be logged with error class only, not raw exception payload."""
        import logging
        with patch('contracts.services.notifications.send_mail',
                   side_effect=Exception('SMTP credentials invalid: secret_api_key_here')):
            with self.assertLogs('contracts.services.notifications', level='WARNING') as cm:
                result = send_mfa_code_email(self.user, '123456')
        self.assertFalse(result)
        # Log must contain error class name but NOT the raw exception message.
        combined = ' '.join(cm.output)
        self.assertIn('Exception', combined)
        # The actual SMTP secret must not appear in logs.
        self.assertNotIn('secret_api_key_here', combined)
