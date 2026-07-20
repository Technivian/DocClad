"""Phase 2 tests — production-backed scheduled automation.

Covers job-run evidence, overlap protection, atomic claiming, idempotency,
tenant isolation, and partial/failure handling for the scheduled job system.
"""
from __future__ import annotations

from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from contracts.models import (
    BackgroundJob,
    Contract,
    Organization,
    RetentionPolicy,
    ScheduledJobRun,
)
from contracts.services.background_jobs import claim_background_job
from contracts.services.job_runs import record_job_run


def _org(name, slug):
    return Organization.objects.create(name=name, slug=slug)


def _retention_policy(org, days=30):
    return RetentionPolicy.objects.create(
        organization=org,
        title='Contracts 30d',
        category=RetentionPolicy.Category.CONTRACTS,
        retention_period_days=days,
        is_active=True,
    )


def _expired_contract(org, days_past_end=60):
    return Contract.objects.create(
        organization=org,
        title='Old Vendor MSA',
        end_date=timezone.now().date() - timedelta(days=days_past_end),
        lifecycle_stage='EXECUTED',
    )


class RecordJobRunTests(TestCase):
    def setUp(self):
        self.org = _org('Run Org', 'run-org')

    def test_success_records_counts_and_status(self):
        with record_job_run('demo_job', organization=self.org) as run:
            run.records_examined = 5
            run.records_changed = 2
            run.notifications_created = 1
        row = ScheduledJobRun.objects.get(job_name='demo_job', organization=self.org)
        self.assertEqual(row.status, ScheduledJobRun.Status.SUCCESS)
        self.assertEqual(row.records_examined, 5)
        self.assertEqual(row.records_changed, 2)
        self.assertEqual(row.notifications_created, 1)
        self.assertIsNotNone(row.finished_at)

    def test_exception_records_failed_and_reraises(self):
        with self.assertRaises(ValueError):
            with record_job_run('demo_job', organization=self.org) as run:
                run.records_examined = 3
                raise ValueError('boom')
        row = ScheduledJobRun.objects.get(job_name='demo_job', organization=self.org)
        self.assertEqual(row.status, ScheduledJobRun.Status.FAILED)
        self.assertEqual(row.records_examined, 3)
        self.assertIn('boom', row.error_summary)
        self.assertIn('ValueError', row.error_summary)

    def test_partial_flag_sets_partial_status(self):
        with record_job_run('demo_job', organization=self.org) as run:
            run.partial = True
        row = ScheduledJobRun.objects.get(job_name='demo_job', organization=self.org)
        self.assertEqual(row.status, ScheduledJobRun.Status.PARTIAL)

    def test_overlap_is_skipped(self):
        # Pre-existing in-flight run for the same (job, org).
        ScheduledJobRun.objects.create(
            job_name='demo_job', organization=self.org,
            status=ScheduledJobRun.Status.RUNNING, started_at=timezone.now(),
        )
        ran = False
        with record_job_run('demo_job', organization=self.org, prevent_overlap=True) as run:
            if run is not None:
                ran = True
        self.assertFalse(ran, 'overlapping run must not execute the body')
        self.assertTrue(
            ScheduledJobRun.objects.filter(
                job_name='demo_job', organization=self.org,
                status=ScheduledJobRun.Status.SKIPPED,
            ).exists()
        )

    def test_overlap_window_expires(self):
        # An old RUNNING row (stale) should not block a fresh run.
        stale = ScheduledJobRun.objects.create(
            job_name='demo_job', organization=self.org,
            status=ScheduledJobRun.Status.RUNNING,
        )
        ScheduledJobRun.objects.filter(pk=stale.pk).update(
            started_at=timezone.now() - timedelta(hours=2),
        )
        ran = False
        with record_job_run('demo_job', organization=self.org,
                            prevent_overlap=True, overlap_window=timedelta(minutes=30)) as run:
            if run is not None:
                ran = True
        self.assertTrue(ran)


class ClaimBackgroundJobTests(TestCase):
    def setUp(self):
        self.org = _org('Claim Org', 'claim-org')
        self.job = BackgroundJob.objects.create(
            organization=self.org, job_type='send_contract_reminders',
            status=BackgroundJob.Status.PENDING, payload={},
        )

    def test_only_one_claim_wins(self):
        job_a = BackgroundJob.objects.get(pk=self.job.pk)
        job_b = BackgroundJob.objects.get(pk=self.job.pk)
        self.assertTrue(claim_background_job(job_a))
        # Second processor sees it already RUNNING -> cannot claim.
        self.assertFalse(claim_background_job(job_b))
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, BackgroundJob.Status.RUNNING)
        self.assertEqual(self.job.attempt_count, 1)  # incremented exactly once

    def test_process_skips_already_claimed_job(self):
        from contracts.services.background_jobs import process_background_job
        self.job.status = BackgroundJob.Status.RUNNING
        self.job.save(update_fields=['status'])
        # Should be a no-op (cannot claim a RUNNING job), not an error.
        process_background_job(BackgroundJob.objects.get(pk=self.job.pk))
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, BackgroundJob.Status.RUNNING)


class RetentionJobEvidenceTests(TestCase):
    def test_run_records_evidence_and_archives(self):
        org = _org('Eviction City', 'eviction-city')
        _retention_policy(org, days=30)
        contract = _expired_contract(org)
        call_command('run_retention_jobs')
        contract.refresh_from_db()
        self.assertEqual(contract.status, Contract.Status.ARCHIVED)
        run = ScheduledJobRun.objects.get(job_name='run_retention_jobs', organization=org)
        self.assertEqual(run.status, ScheduledJobRun.Status.SUCCESS)
        self.assertGreaterEqual(run.records_examined, 1)
        self.assertEqual(run.records_changed, 1)

    def test_idempotent_second_run_changes_nothing(self):
        org = _org('Idem City', 'idem-city')
        _retention_policy(org, days=30)
        _expired_contract(org)
        call_command('run_retention_jobs')
        call_command('run_retention_jobs')
        # Already-archived contract is excluded on the second pass.
        second = ScheduledJobRun.objects.filter(
            job_name='run_retention_jobs', organization=org,
        ).order_by('-started_at').first()
        self.assertEqual(second.records_changed, 0)

    def test_tenant_isolation(self):
        org_a = _org('Tenant A', 'tenant-a')
        org_b = _org('Tenant B', 'tenant-b')
        _retention_policy(org_a, days=30)  # only A has a policy
        c_a = _expired_contract(org_a)
        c_b = _expired_contract(org_b)  # eligible by date but B has no policy
        call_command('run_retention_jobs')
        c_a.refresh_from_db()
        c_b.refresh_from_db()
        self.assertEqual(c_a.status, Contract.Status.ARCHIVED)
        self.assertNotEqual(c_b.status, Contract.Status.ARCHIVED)
        # B still gets an evidence row (examined 0, changed 0) — proof it ran.
        run_b = ScheduledJobRun.objects.get(job_name='run_retention_jobs', organization=org_b)
        self.assertEqual(run_b.records_changed, 0)


class QueueDispatchEvidenceTests(TestCase):
    def test_dispatch_records_evidence_and_is_idempotent(self):
        org = _org('Queue City', 'queue-city')
        call_command('queue_background_jobs')
        first = BackgroundJob.objects.filter(organization=org).count()
        self.assertGreater(first, 0)
        # Second immediate run is within the dedupe window -> no new jobs.
        call_command('queue_background_jobs')
        second = BackgroundJob.objects.filter(organization=org).count()
        self.assertEqual(first, second)
        self.assertTrue(
            ScheduledJobRun.objects.filter(
                job_name='queue_background_jobs',
                status=ScheduledJobRun.Status.SUCCESS,
            ).exists()
        )
