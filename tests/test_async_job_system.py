"""Tests for async job worker, dead-letter review, and job status API."""
from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import MagicMock, call, patch

from django.test import SimpleTestCase
from django.utils import timezone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_job(
    id=1,
    job_type='send_contract_reminders',
    status='PENDING',
    attempt_count=0,
    max_attempts=3,
    error_message='',
    result=None,
    payload=None,
    scheduled_at=None,
    started_at=None,
    completed_at=None,
    dead_lettered_at=None,
    created_at=None,
    organization_id=1,
    organization=None,
):
    m = MagicMock()
    m.id = id
    m.job_type = job_type
    m.status = status
    m.attempt_count = attempt_count
    m.max_attempts = max_attempts
    m.error_message = error_message
    m.result = result or {}
    m.payload = payload or {}
    m.scheduled_at = scheduled_at
    m.started_at = started_at
    m.completed_at = completed_at
    m.dead_lettered_at = dead_lettered_at
    m.created_at = created_at or timezone.now()
    m.organization_id = organization_id
    m.organization = organization or MagicMock()
    return m


# ---------------------------------------------------------------------------
# background_jobs service — run_obligation_reminders dispatch
# ---------------------------------------------------------------------------

class TestBackgroundJobsObligationReminders(SimpleTestCase):

    def test_dispatches_run_obligation_reminders(self):
        job = _make_job(job_type='run_obligation_reminders')
        job.organization.slug = 'test-org'
        with patch('contracts.services.background_jobs.call_command') as mock_cmd:
            from contracts.services.background_jobs import process_background_job
            process_background_job(job)
        mock_cmd.assert_called_once_with(
            'run_obligation_reminders',
            organization_slug='test-org',
            dry_run=False,
        )

    def test_obligation_reminders_requires_organization(self):
        job = _make_job(job_type='run_obligation_reminders')
        job.organization = None
        job.organization_id = None
        with self.assertRaises(RuntimeError):
            from contracts.services.background_jobs import process_background_job
            process_background_job(job)


# ---------------------------------------------------------------------------
# run_worker command — unit tests (no DB, mock process_background_job)
# ---------------------------------------------------------------------------

class TestRunWorkerCommand(SimpleTestCase):

    def _call(self, **kwargs):
        from contracts.management.commands.run_worker import Command
        cmd = Command()
        cmd.stdout = MagicMock()
        cmd.stderr = MagicMock()
        cmd.style = MagicMock()
        cmd.style.SUCCESS = lambda x: x
        cmd.style.WARNING = lambda x: x
        return cmd, kwargs

    def test_max_cycles_stops_loop(self):
        with (
            patch('contracts.management.commands.run_worker.BackgroundJob') as MockJob,
            patch('contracts.management.commands.run_worker.process_background_job') as mock_proc,
        ):
            MockJob.objects.filter.return_value.filter.return_value.filter.return_value.order_by.return_value.__getitem__.return_value = []
            MockJob.objects.filter.return_value.filter.return_value.order_by.return_value.__getitem__.return_value = []
            MockJob.Status.PENDING = 'PENDING'
            mock_proc.return_value = None

            from contracts.management.commands.run_worker import Command
            cmd = Command()
            cmd.stdout = MagicMock()
            cmd.stderr = MagicMock()
            cmd.style = MagicMock()
            cmd.style.SUCCESS = lambda x: x
            cmd.style.WARNING = lambda x: x

            with patch('contracts.management.commands.run_worker.time.sleep') as mock_sleep:
                cmd.handle(poll_interval=1, batch_size=5, max_cycles=2, job_types='')
            # sleep called once (between cycle 1 and 2, not after final cycle)
            self.assertEqual(mock_sleep.call_count, 1)

    def test_processes_jobs_in_batch(self):
        job1 = _make_job(id=1)
        job2 = _make_job(id=2)

        with (
            patch('contracts.management.commands.run_worker.BackgroundJob') as MockJob,
            patch('contracts.management.commands.run_worker.process_background_job') as mock_proc,
            patch('contracts.management.commands.run_worker.time.sleep'),
        ):
            MockJob.Status.PENDING = 'PENDING'
            qs_mock = MagicMock()
            qs_mock.__getitem__ = MagicMock(return_value=[job1, job2])
            MockJob.objects.filter.return_value.filter.return_value.order_by.return_value = qs_mock

            from contracts.management.commands.run_worker import Command
            cmd = Command()
            cmd.stdout = MagicMock()
            cmd.stderr = MagicMock()
            cmd.style = MagicMock()
            cmd.style.SUCCESS = lambda x: x
            cmd.style.WARNING = lambda x: x

            cmd.handle(poll_interval=1, batch_size=5, max_cycles=1, job_types='')

        self.assertEqual(mock_proc.call_count, 2)

    def test_failure_counted_not_raised(self):
        job = _make_job(id=1)

        with (
            patch('contracts.management.commands.run_worker.BackgroundJob') as MockJob,
            patch('contracts.management.commands.run_worker.process_background_job') as mock_proc,
            patch('contracts.management.commands.run_worker.time.sleep'),
        ):
            MockJob.Status.PENDING = 'PENDING'
            qs_mock = MagicMock()
            qs_mock.__getitem__ = MagicMock(return_value=[job])
            MockJob.objects.filter.return_value.filter.return_value.order_by.return_value = qs_mock
            mock_proc.side_effect = RuntimeError('boom')

            from contracts.management.commands.run_worker import Command
            cmd = Command()
            cmd.stdout = MagicMock()
            cmd.stderr = MagicMock()
            cmd.style = MagicMock()
            cmd.style.SUCCESS = lambda x: x
            cmd.style.WARNING = lambda x: x

            # Should not raise
            cmd.handle(poll_interval=1, batch_size=5, max_cycles=1, job_types='')
        cmd.stderr.write.assert_called_once()


# ---------------------------------------------------------------------------
# review_dead_letter_jobs command
# ---------------------------------------------------------------------------

class TestReviewDeadLetterJobsCommand(SimpleTestCase):

    def _run(self, action, jobs, **kwargs):
        with patch('contracts.management.commands.review_dead_letter_jobs.BackgroundJob') as MockJob:
            MockJob.objects.filter.return_value.filter.return_value.filter.return_value.order_by.return_value = jobs
            MockJob.objects.filter.return_value.filter.return_value.order_by.return_value = jobs
            MockJob.objects.filter.return_value.order_by.return_value = jobs
            MockJob.Status.FAILED = 'FAILED'
            MockJob.Status.PENDING = 'PENDING'
            from contracts.management.commands.review_dead_letter_jobs import Command
            cmd = Command()
            cmd.stdout = MagicMock()
            cmd.stderr = MagicMock()
            cmd.style = MagicMock()
            cmd.style.SUCCESS = lambda x: x
            options = {'action': action, 'job_type': '', 'job_id': 0, 'limit': 50, 'output': ''}
            options.update(kwargs)
            cmd.handle(**options)
            return cmd, MockJob

    def test_list_prints_jobs(self):
        job = _make_job(id=1, job_type='sync_salesforce_contracts', status='FAILED',
                        error_message='connection refused', dead_lettered_at=timezone.now())
        cmd, _ = self._run('list', [job])
        cmd.stdout.write.assert_called()
        output = ' '.join(str(c) for c in cmd.stdout.write.call_args_list)
        self.assertIn('1', output)

    def test_retry_resets_job(self):
        job = _make_job(id=1, status='FAILED', attempt_count=3, result={}, payload={},
                        scheduled_at=None, started_at=None, completed_at=None,
                        dead_lettered_at=None)
        cmd, MockJob = self._run('retry', [job])
        self.assertEqual(job.status, 'PENDING')
        self.assertEqual(job.attempt_count, 0)
        self.assertEqual(job.error_message, '')
        job.save.assert_called_once()

    def test_purge_deletes_jobs(self):
        job = _make_job(id=1, status='FAILED')
        with patch('contracts.management.commands.review_dead_letter_jobs.BackgroundJob') as MockJob:
            qs_mock = MagicMock()
            qs_mock.values_list.return_value = [1]
            MockJob.objects.filter.return_value.order_by.return_value = qs_mock
            MockJob.Status.FAILED = 'FAILED'
            from contracts.management.commands.review_dead_letter_jobs import Command
            cmd = Command()
            cmd.stdout = MagicMock()
            cmd.stderr = MagicMock()
            cmd.style = MagicMock()
            cmd.style.SUCCESS = lambda x: x
            cmd.handle(action='purge', job_type='', job_id=0, limit=50, output='')
        MockJob.objects.filter.return_value.delete.assert_called_once()


# ---------------------------------------------------------------------------
# Job status API
# ---------------------------------------------------------------------------

class TestJobListApi(SimpleTestCase):

    def _get(self, jobs, get_params=None):
        with (
            patch('contracts.api.views.get_user_organization') as mock_org,
            patch('contracts.api.views.BackgroundJob') as MockJob,
        ):
            mock_org.return_value = MagicMock()
            qs = MagicMock()
            qs.filter.return_value = qs
            qs.order_by.return_value = qs
            qs.__getitem__ = MagicMock(return_value=jobs)
            qs.__iter__ = MagicMock(return_value=iter(jobs))
            MockJob.objects.filter.return_value = qs
            from contracts.api.views import job_list_api
            req = MagicMock()
            req.method = 'GET'
            req.user = MagicMock()
            req.GET = get_params or {}
            return job_list_api(req)

    def test_returns_200(self):
        resp = self._get([])
        self.assertEqual(resp.status_code, 200)

    def test_response_has_status_counts(self):
        jobs = [_make_job(id=i, status='COMPLETED') for i in range(3)]
        resp = self._get(jobs)
        data = json.loads(resp.content)
        self.assertIn('status_counts', data)
        self.assertIn('jobs', data)


class TestJobDetailApi(SimpleTestCase):

    def test_returns_job(self):
        job = _make_job(id=5)
        with (
            patch('contracts.api.views.get_user_organization') as mock_org,
            patch('contracts.api.views.BackgroundJob') as MockJob,
        ):
            mock_org.return_value = MagicMock()
            MockJob.objects.get.return_value = job
            from contracts.api.views import job_detail_api
            req = MagicMock()
            req.method = 'GET'
            req.user = MagicMock()
            resp = job_detail_api(req, job_id=5)
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data['job']['id'], 5)

    def test_not_found_returns_404(self):
        with (
            patch('contracts.api.views.get_user_organization') as mock_org,
            patch('contracts.api.views.BackgroundJob') as MockJob,
        ):
            mock_org.return_value = MagicMock()
            MockJob.DoesNotExist = Exception
            MockJob.objects.get.side_effect = MockJob.DoesNotExist
            from contracts.api.views import job_detail_api
            req = MagicMock()
            req.method = 'GET'
            req.user = MagicMock()
            resp = job_detail_api(req, job_id=999)
        self.assertEqual(resp.status_code, 404)


class TestJobRetryApi(SimpleTestCase):

    def test_retries_failed_job(self):
        job = _make_job(id=1, status='FAILED', attempt_count=3, result={}, payload={},
                        scheduled_at=None, started_at=None, completed_at=None,
                        dead_lettered_at=None)
        with (
            patch('contracts.api.views.get_user_organization') as mock_org,
            patch('contracts.api.views.BackgroundJob') as MockJob,
        ):
            mock_org.return_value = MagicMock()
            MockJob.objects.get.return_value = job
            MockJob.Status.FAILED = 'FAILED'
            MockJob.Status.PENDING = 'PENDING'
            from contracts.api.views import job_retry_api
            req = MagicMock()
            req.method = 'POST'
            req.user = MagicMock()
            resp = job_retry_api(req, job_id=1)
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data['ok'])
        self.assertEqual(job.status, 'PENDING')
        self.assertEqual(job.attempt_count, 0)

    def test_retry_non_failed_returns_400(self):
        job = _make_job(id=1, status='RUNNING')
        with (
            patch('contracts.api.views.get_user_organization') as mock_org,
            patch('contracts.api.views.BackgroundJob') as MockJob,
        ):
            mock_org.return_value = MagicMock()
            MockJob.objects.get.return_value = job
            MockJob.Status.FAILED = 'FAILED'
            from contracts.api.views import job_retry_api
            req = MagicMock()
            req.method = 'POST'
            req.user = MagicMock()
            resp = job_retry_api(req, job_id=1)
        self.assertEqual(resp.status_code, 400)

    def test_retry_not_found_returns_404(self):
        with (
            patch('contracts.api.views.get_user_organization') as mock_org,
            patch('contracts.api.views.BackgroundJob') as MockJob,
        ):
            mock_org.return_value = MagicMock()
            MockJob.DoesNotExist = Exception
            MockJob.objects.get.side_effect = MockJob.DoesNotExist
            from contracts.api.views import job_retry_api
            req = MagicMock()
            req.method = 'POST'
            req.user = MagicMock()
            resp = job_retry_api(req, job_id=999)
        self.assertEqual(resp.status_code, 404)
