"""Wave 2 feature tests.

Covers:
  B5  — Retention hold blocks document deletion
  B6  — AI data controls page (toggle + org policy guard)
  B9  — Contract cannot be activated without an approved approval request
  C14 — CSP report endpoint returns 204 and accepts browser reports
  B2-lite — Background job queue: RQ enqueue, stale job recovery
"""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from contracts.models import (
    ApprovalRequest,
    Client,
    Contract,
    Document,
    LegalHold,
    Matter,
    Organization,
    OrganizationMembership,
    OrgPolicy,
    BackgroundJob,
)
from contracts.services.background_jobs import (
    process_pending_background_jobs,
    queue_background_job,
    reset_stale_running_jobs,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_org_and_user():
    org = Organization.objects.create(name='Test Org', slug='test-org-w2')
    user = User.objects.create_user(username='w2user', password='pass', email='w2@example.com')
    OrganizationMembership.objects.create(
        organization=org, user=user, role='ADMIN', is_active=True
    )
    return org, user


# ---------------------------------------------------------------------------
# B5 — Retention hold blocks document deletion
# ---------------------------------------------------------------------------

class RetentionHoldGuardTests(TestCase):

    def setUp(self):
        self.org, self.user = _make_org_and_user()
        self.client_obj = Client.objects.create(organization=self.org, name='Test Client')
        self.matter = Matter.objects.create(
            organization=self.org,
            client=self.client_obj,
            matter_number='M-W2-001',
            title='Test Matter',
        )

    def _make_document(self, matter=None):
        return Document.objects.create(
            organization=self.org,
            title='Test Doc',
            matter=matter,
        )

    def test_document_delete_blocked_when_matter_under_active_hold(self):
        doc = self._make_document(matter=self.matter)
        LegalHold.objects.create(
            organization=self.org,
            title='Active Hold',
            description='Test hold',
            status=LegalHold.Status.ACTIVE,
            matter=self.matter,
            hold_start_date=date.today(),
            issued_by=self.user,
        )
        with self.assertRaises(PermissionError):
            doc.delete()
        self.assertTrue(Document.objects.filter(pk=doc.pk).exists())

    def test_document_delete_allowed_when_hold_is_released(self):
        doc = self._make_document(matter=self.matter)
        LegalHold.objects.create(
            organization=self.org,
            title='Released Hold',
            description='',
            status=LegalHold.Status.RELEASED,
            matter=self.matter,
            hold_start_date=date.today(),
            issued_by=self.user,
        )
        doc.delete()
        self.assertFalse(Document.objects.filter(pk=doc.pk).exists())

    def test_document_delete_allowed_with_no_hold(self):
        doc = self._make_document(matter=self.matter)
        doc.delete()
        self.assertFalse(Document.objects.filter(pk=doc.pk).exists())

    def test_delete_view_shows_error_message_on_hold(self):
        self.client.force_login(self.user)
        doc = self._make_document(matter=self.matter)
        LegalHold.objects.create(
            organization=self.org,
            title='Active Hold',
            description='',
            status=LegalHold.Status.ACTIVE,
            matter=self.matter,
            hold_start_date=date.today(),
            issued_by=self.user,
        )
        url = reverse('contracts:document_delete', kwargs={'pk': doc.pk})
        response = self.client.post(url)
        self.assertRedirects(response, reverse('contracts:document_detail', kwargs={'pk': doc.pk}))
        self.assertTrue(Document.objects.filter(pk=doc.pk).exists())


# ---------------------------------------------------------------------------
# B6 — AI data controls
# ---------------------------------------------------------------------------

class AIDataControlsTests(TestCase):

    def setUp(self):
        self.org, self.user = _make_org_and_user()
        self.client.force_login(self.user)
        self.url = reverse('contracts:ai_data_controls')

    def test_page_renders_for_admin(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'AI Data Controls')

    def test_disable_ai_features(self):
        OrgPolicy.objects.get_or_create(organization=self.org, defaults={'ai_features_enabled': True})
        self.client.post(self.url, {'ai_features_enabled': '0'})
        policy = OrgPolicy.objects.get(organization=self.org)
        self.assertFalse(policy.ai_features_enabled)

    def test_enable_ai_features(self):
        OrgPolicy.objects.update_or_create(
            organization=self.org, defaults={'ai_features_enabled': False}
        )
        self.client.post(self.url, {'ai_features_enabled': '1'})
        policy = OrgPolicy.objects.get(organization=self.org)
        self.assertTrue(policy.ai_features_enabled)

    def test_non_admin_cannot_change_controls(self):
        other = User.objects.create_user(username='w2member', password='pass')
        OrganizationMembership.objects.create(
            organization=self.org, user=other, role='MEMBER', is_active=True
        )
        self.client.force_login(other)
        OrgPolicy.objects.get_or_create(organization=self.org, defaults={'ai_features_enabled': True})
        response = self.client.post(self.url, {'ai_features_enabled': '0'})
        self.assertEqual(response.status_code, 403)
        policy = OrgPolicy.objects.get(organization=self.org)
        self.assertTrue(policy.ai_features_enabled)

    def test_build_action_plan_returns_empty_when_ai_disabled(self):
        from contracts.services.ai_actions import build_action_plan
        policy, _ = OrgPolicy.objects.get_or_create(organization=self.org)
        policy.ai_features_enabled = False
        policy.save()
        contract = Contract.objects.create(
            organization=self.org, title='Test', status=Contract.Status.IN_PROGRESS
        )
        result = build_action_plan(contract, 'create a workflow')
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# B9 — Contract activation requires approved approval request
# ---------------------------------------------------------------------------

class ContractActivationGuardTests(TestCase):

    def setUp(self):
        self.org, self.user = _make_org_and_user()
        self.client.force_login(self.user)

    def _make_contract(self, status=Contract.Status.IN_PROGRESS, lifecycle_stage=Contract.LifecycleStage.DRAFTING):
        if status == Contract.Status.ACTIVE and lifecycle_stage == Contract.LifecycleStage.DRAFTING:
            lifecycle_stage = Contract.LifecycleStage.OBLIGATION_TRACKING
        return Contract.objects.create(
            organization=self.org,
            title='Guard Test Contract',
            status=status,
            lifecycle_stage=lifecycle_stage,
            created_by=self.user,
        )

    _VALID_FORM_BASE = {
        'contract_type': 'OTHER',
        'counterparty': 'Acme Corp',
        'governing_law': 'Delaware',
        'currency': 'USD',
        'risk_level': 'LOW',
        'lifecycle_stage': 'DRAFTING',
    }

    def test_activation_blocked_without_approval(self):
        from contracts.services.contract_lifecycle import (
            ContractTransitionError,
            get_contract_lifecycle_service,
        )

        contract = self._make_contract()
        with self.assertRaises(ContractTransitionError):
            get_contract_lifecycle_service().transition(
                contract, Contract.Status.ACTIVE, self.user,
            )
        contract.refresh_from_db()
        self.assertNotEqual(contract.status, Contract.Status.ACTIVE)

    def test_activation_allowed_with_approved_request(self):
        from contracts.services.contract_lifecycle import get_contract_lifecycle_service

        contract = self._make_contract(
            status=Contract.Status.IN_PROGRESS,
            lifecycle_stage=Contract.LifecycleStage.SIGNATURE,
        )
        ApprovalRequest.objects.create(
            organization=self.org,
            contract=contract,
            approval_step='LEGAL',
            status=ApprovalRequest.Status.APPROVED,
            assigned_to=self.user,
            decided_by=self.user,
            decided_at=timezone.now(),
        )
        get_contract_lifecycle_service().transition(
            contract, Contract.Status.ACTIVE, self.user,
        )
        contract.refresh_from_db()
        self.assertEqual(contract.status, Contract.Status.ACTIVE)

    def test_already_active_contract_can_be_updated_without_approval(self):
        contract = self._make_contract(status=Contract.Status.ACTIVE)
        url = reverse('contracts:contract_update', kwargs={'pk': contract.pk})
        response = self.client.post(url, {
            **self._VALID_FORM_BASE,
            'title': 'Updated Title',
            'owner': self.user.pk,
        })
        contract.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(contract.title, 'Updated Title')


# ---------------------------------------------------------------------------
# C14 — CSP report endpoint
# ---------------------------------------------------------------------------

class CSPReportEndpointTests(TestCase):

    def test_returns_204_for_valid_report(self):
        import json
        payload = json.dumps({
            'csp-report': {
                'document-uri': 'https://example.com/',
                'violated-directive': 'script-src',
                'blocked-uri': 'inline',
            }
        }).encode()
        response = self.client.post(
            '/csp-report/',
            data=payload,
            content_type='application/csp-report',
        )
        self.assertEqual(response.status_code, 204)

    def test_returns_204_for_empty_body(self):
        response = self.client.post('/csp-report/', data=b'', content_type='application/csp-report')
        self.assertEqual(response.status_code, 204)

    def test_get_returns_405(self):
        response = self.client.get('/csp-report/')
        self.assertEqual(response.status_code, 405)


# ---------------------------------------------------------------------------
# B2-lite — Background job queue
# ---------------------------------------------------------------------------

class BackgroundJobQueueTests(TestCase):

    def setUp(self):
        self.org, self.user = _make_org_and_user()

    def test_queue_background_job_creates_db_record(self):
        job = queue_background_job('send_contract_reminders', organization=self.org)
        self.assertIsNotNone(job.pk)
        self.assertEqual(job.status, BackgroundJob.Status.PENDING)

    @patch('contracts.services.background_jobs._enqueue_rq')
    def test_queue_deduplicates_recent_pending_job(self, _mock_enqueue):
        job1 = queue_background_job('send_contract_reminders', organization=self.org)
        job2 = queue_background_job('send_contract_reminders', organization=self.org)
        self.assertEqual(job1.pk, job2.pk)

    def test_reset_stale_running_jobs(self):
        stale_job = BackgroundJob.objects.create(
            organization=self.org,
            job_type='send_contract_reminders',
            status=BackgroundJob.Status.RUNNING,
            started_at=timezone.now() - timedelta(minutes=60),
        )
        reset_count = reset_stale_running_jobs()
        self.assertGreaterEqual(reset_count, 1)
        stale_job.refresh_from_db()
        self.assertEqual(stale_job.status, BackgroundJob.Status.PENDING)

    def test_fresh_running_job_not_reset(self):
        fresh_job = BackgroundJob.objects.create(
            organization=self.org,
            job_type='send_contract_reminders',
            status=BackgroundJob.Status.RUNNING,
            started_at=timezone.now() - timedelta(minutes=5),
        )
        reset_stale_running_jobs()
        fresh_job.refresh_from_db()
        self.assertEqual(fresh_job.status, BackgroundJob.Status.RUNNING)

    def test_process_pending_calls_reset_stale(self):
        with patch('contracts.services.background_jobs.reset_stale_running_jobs') as mock_reset:
            mock_reset.return_value = 0
            process_pending_background_jobs(limit=0)
            mock_reset.assert_called_once()
