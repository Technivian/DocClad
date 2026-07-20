"""Phase 4C — automatic contract expiration job."""
from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from contracts.models import (
    ApprovalRequest,
    AuditLog,
    Contract,
    Organization,
    OrganizationMembership,
    ScheduledJobRun,
)

User = get_user_model()


def _org(name, slug):
    return Organization.objects.create(name=name, slug=slug)


def _active_contract(org, *, end_offset_days, auto_renew=False, status='ACTIVE'):
    return Contract.objects.create(
        organization=org, title='C', status=status, auto_renew=auto_renew,
        end_date=timezone.localdate() + timedelta(days=end_offset_days),
    )


class ContractExpirationTests(TestCase):
    def setUp(self):
        self.org = _org('Exp Org', 'exp-org')

    def test_expires_contract_past_end_date(self):
        c = _active_contract(self.org, end_offset_days=-1)
        call_command('run_contract_expiration')
        c.refresh_from_db()
        self.assertEqual(c.status, Contract.Status.EXPIRED)

    def test_does_not_expire_on_end_date_boundary(self):
        # Valid through end_date inclusive — today == end_date must NOT expire.
        c = _active_contract(self.org, end_offset_days=0)
        call_command('run_contract_expiration')
        c.refresh_from_db()
        self.assertEqual(c.status, Contract.Status.ACTIVE)

    def test_does_not_expire_future_contract(self):
        c = _active_contract(self.org, end_offset_days=30)
        call_command('run_contract_expiration')
        c.refresh_from_db()
        self.assertEqual(c.status, Contract.Status.ACTIVE)

    def test_auto_renew_excluded(self):
        c = _active_contract(self.org, end_offset_days=-5, auto_renew=True)
        call_command('run_contract_expiration')
        c.refresh_from_db()
        self.assertEqual(c.status, Contract.Status.ACTIVE)

    def test_non_active_statuses_excluded(self):
        c = _active_contract(self.org, end_offset_days=-5, status='ACTIVE')
        call_command('run_contract_expiration')
        c.refresh_from_db()
        self.assertEqual(c.status, 'APPROVED')

    def test_idempotent_second_run(self):
        c = _active_contract(self.org, end_offset_days=-1)
        call_command('run_contract_expiration')
        run2_before = ScheduledJobRun.objects.filter(job_name='run_contract_expiration').count()
        call_command('run_contract_expiration')
        c.refresh_from_db()
        self.assertEqual(c.status, Contract.Status.EXPIRED)
        latest = ScheduledJobRun.objects.filter(
            job_name='run_contract_expiration', organization=self.org,
        ).order_by('-started_at').first()
        self.assertEqual(latest.records_changed, 0)  # nothing left to expire

    def test_tenant_isolation(self):
        org_b = _org('Other', 'exp-other')
        c_a = _active_contract(self.org, end_offset_days=-1)
        c_b = _active_contract(org_b, end_offset_days=-1)
        call_command('run_contract_expiration', '--organization-slug', 'exp-org')
        c_a.refresh_from_db()
        c_b.refresh_from_db()
        self.assertEqual(c_a.status, Contract.Status.EXPIRED)
        self.assertEqual(c_b.status, Contract.Status.ACTIVE)  # untouched

    def test_audit_and_job_run_evidence(self):
        c = _active_contract(self.org, end_offset_days=-1)
        call_command('run_contract_expiration')
        run = ScheduledJobRun.objects.get(job_name='run_contract_expiration', organization=self.org)
        self.assertEqual(run.records_changed, 1)
        audit = AuditLog.objects.filter(
            event_type='contract.status_changed', object_id=c.pk,
        ).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.changes['to'], Contract.Status.EXPIRED)
        self.assertEqual(audit.actor_type, AuditLog.ActorType.SCHEDULED_JOB)
        self.assertEqual(str(audit.job_run_id), str(run.run_id))  # linked to run

    def test_dry_run_changes_nothing(self):
        c = _active_contract(self.org, end_offset_days=-1)
        call_command('run_contract_expiration', '--dry-run')
        c.refresh_from_db()
        self.assertEqual(c.status, Contract.Status.ACTIVE)
