"""Phase 5H — automatic expiration rehearsal.

Canonical timezone is UTC (settings TIME_ZONE='UTC', USE_TZ=True), so the
expiration boundary is the UTC date: a fixed-term contract is valid THROUGH its
end_date (inclusive) and expires once the UTC date passes it (end_date < today).
No DST ambiguity (UTC). auto_renew contracts are excluded.
"""
from __future__ import annotations

import threading
from datetime import timedelta
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection, connections
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from contracts.models import (
    AuditLog, Contract, Notification, Organization, OrganizationMembership, ScheduledJobRun,
)
from contracts.services import contract_lifecycle as lc

User = get_user_model()


def _org(slug):
    return Organization.objects.create(name=slug, slug=slug)


def _contract(org, *, end_offset, status='ACTIVE', auto_renew=False, title='C'):
    return Contract.objects.create(
        organization=org, title=title, status=status, auto_renew=auto_renew,
        end_date=timezone.localdate() + timedelta(days=end_offset))


def _expired_audit(contract):
    return AuditLog.objects.filter(event_type='contract.status_changed', object_id=contract.pk,
                                   changes__to='EXPIRED').count()


class ExpirationBoundary(TestCase):
    def setUp(self):
        self.org = _org('exp-h')

    def test_expires_strictly_after_end_date(self):
        past = _contract(self.org, end_offset=-1)
        call_command('run_contract_expiration')
        past.refresh_from_db()
        self.assertEqual(past.status, 'EXPIRED')

    def test_not_expired_on_end_date_today_utc(self):
        today = _contract(self.org, end_offset=0)  # valid through end_date inclusive
        call_command('run_contract_expiration')
        today.refresh_from_db()
        self.assertEqual(today.status, 'ACTIVE')

    def test_not_expired_before_end_date(self):
        future = _contract(self.org, end_offset=1)
        call_command('run_contract_expiration')
        future.refresh_from_db()
        self.assertEqual(future.status, 'ACTIVE')


class ExpirationEligibility(TestCase):
    def setUp(self):
        self.org = _org('elig-h')

    def test_terminal_and_non_active_excluded(self):
        kept = {}
        for st in ('TERMINATED', 'COMPLETED', 'CANCELLED', 'DRAFT', 'APPROVED'):
            kept[st] = _contract(self.org, end_offset=-30, status=st, title=f'C-{st}')
        call_command('run_contract_expiration')
        for st, c in kept.items():
            c.refresh_from_db()
            self.assertEqual(c.status, st, f'{st} must not be auto-expired')

    def test_auto_renew_excluded(self):
        ar = _contract(self.org, end_offset=-30, auto_renew=True)
        call_command('run_contract_expiration')
        ar.refresh_from_db()
        self.assertEqual(ar.status, 'ACTIVE')


class ExpirationIdempotency(TestCase):
    def setUp(self):
        self.org = _org('idem-h')

    def test_already_expired_not_reprocessed(self):
        c = _contract(self.org, end_offset=-5)
        call_command('run_contract_expiration')
        self.assertEqual(_expired_audit(c), 1)
        # second run: nothing to do, no duplicate audit, no duplicate notification
        n_before = Notification.objects.count()
        call_command('run_contract_expiration')
        c.refresh_from_db()
        self.assertEqual(c.status, 'EXPIRED')
        self.assertEqual(_expired_audit(c), 1)  # NOT duplicated
        self.assertEqual(Notification.objects.count(), n_before)  # no notifications emitted
        latest = ScheduledJobRun.objects.filter(job_name='run_contract_expiration', organization=self.org)\
            .order_by('-started_at').first()
        self.assertEqual(latest.records_changed, 0)

    def test_job_run_evidence_recorded(self):
        c = _contract(self.org, end_offset=-5)
        call_command('run_contract_expiration')
        run = ScheduledJobRun.objects.get(job_name='run_contract_expiration', organization=self.org)
        self.assertEqual(run.records_changed, 1)
        self.assertGreaterEqual(run.records_examined, 1)


class ExpirationTenantIsolationAndPartialFailure(TestCase):
    def setUp(self):
        self.org_a = _org('exp-a'); self.org_b = _org('exp-b')
        self.c_a = _contract(self.org_a, end_offset=-3, title='A')
        self.c_b = _contract(self.org_b, end_offset=-3, title='B')

    def test_tenant_isolation_single_org(self):
        call_command('run_contract_expiration', '--organization-slug', 'exp-a')
        self.c_a.refresh_from_db(); self.c_b.refresh_from_db()
        self.assertEqual(self.c_a.status, 'EXPIRED')
        self.assertEqual(self.c_b.status, 'ACTIVE')  # untouched

    def test_partial_tenant_failure_does_not_block_others(self):
        real = lc.get_contract_lifecycle_service()

        class FailingForA:
            def transition(self, contract, new_status, **kw):
                if contract.organization_id == self.org_a_id:
                    raise RuntimeError('simulated tenant A failure')
                return real.transition(contract, new_status, **kw)
        wrapper = FailingForA(); wrapper.org_a_id = self.org_a.id

        with patch('contracts.management.commands.run_contract_expiration.get_contract_lifecycle_service',
                   return_value=wrapper):
            call_command('run_contract_expiration')
        self.c_a.refresh_from_db(); self.c_b.refresh_from_db()
        self.assertEqual(self.c_a.status, 'ACTIVE')    # failed tenant unchanged
        self.assertEqual(self.c_b.status, 'EXPIRED')   # other tenant still processed


@skipUnless(connection.vendor == 'postgresql', 'PostgreSQL-only (duplicate-cron concurrency)')
class ExpirationDuplicateCronPostgres(TransactionTestCase):
    reset_sequences = True

    def test_duplicate_concurrent_cron_expires_once(self):
        org = _org('dup-cron');
        c = _contract(org, end_offset=-3)
        errors = []

        def run():
            try:
                call_command('run_contract_expiration')
            except Exception as exc:  # noqa: BLE001
                errors.append(repr(exc))
            finally:
                connections.close_all()

        threads = [threading.Thread(target=run) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        c.refresh_from_db()
        self.assertEqual(c.status, 'EXPIRED')
        self.assertEqual(errors, [], f'no uncaught errors: {errors}')
        # exactly one EXPIRED transition audit despite duplicate concurrent cron
        self.assertEqual(_expired_audit(c), 1)
