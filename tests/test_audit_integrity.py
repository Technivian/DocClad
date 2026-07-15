"""Phase 3 — audit integrity, immutability, completeness, and tenant safety."""
from __future__ import annotations

from contextlib import contextmanager

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import IntegrityError, connection, transaction
from django.test import Client, TestCase
from django.urls import reverse

from contracts.models import (
    AuditLog,
    AuditWriteError,
    Contract,
    Organization,
    OrganizationMembership,
)
from contracts.services.audit import (
    append_audit,
    compute_entry_hash,
    verify_chain,
    VERDICT_BROKEN_LINK,
    VERDICT_HASH_MISMATCH,
    VERDICT_MISSING_PREDECESSOR,
    VERDICT_VALID,
)

User = get_user_model()
PW = 'StrongPw!123'


@contextmanager
def _tamper_permitted():
    """Suppress the append-only triggers for the duration of the block.

    Uses SET LOCAL session_replication_role = 'replica', which disables all
    user-defined triggers for the current transaction only. Requires the test
    DB user to have the REPLICATION attribute or superuser — always true for
    the CLM One test database owner. This path is unavailable to the
    production application role, which holds only DML privileges.
    Use only in verifier tests that must simulate a tampered audit chain.
    """
    if connection.vendor != 'postgresql':
        yield
        return
    with connection.cursor() as cur:
        cur.execute("SET LOCAL session_replication_role = 'replica'")
    try:
        yield
    finally:
        pass  # SET LOCAL resets at transaction end automatically


def _org(name, slug):
    return Organization.objects.create(name=name, slug=slug)


def _member(org, username, role=OrganizationMembership.Role.OWNER):
    u = User.objects.create_user(username=username, password=PW, email=f'{username}@ex.com')
    OrganizationMembership.objects.create(user=u, organization=org, role=role, is_active=True)
    return u


def _append(org, n=1, **kw):
    rows = []
    for i in range(n):
        rows.append(append_audit(
            action='CREATE', model_name='Contract', organization=org,
            object_id=i, changes={'event': 'contract.created', 'i': i}, **kw,
        ))
    return rows


class HashChainTests(TestCase):
    def setUp(self):
        self.org = _org('Chain Org', 'chain-org')

    def test_hash_is_deterministic(self):
        kw = dict(prev_hash='', organization_id=1, seq=1, event_type='x', action='CREATE',
                  actor_type='human', actor_id=5, model_name='Contract', object_id=2,
                  outcome='success', request_id='r', job_run_id=None, changes={'a': 1, 'b': 2})
        self.assertEqual(compute_entry_hash(**kw), compute_entry_hash(**kw))

    def test_canonical_serialization_is_key_order_independent(self):
        base = dict(prev_hash='', organization_id=1, seq=1, event_type='x', action='CREATE',
                    actor_type='human', actor_id=5, model_name='Contract', object_id=2,
                    outcome='success', request_id='r', job_run_id=None)
        h1 = compute_entry_hash(changes={'a': 1, 'b': 2}, **base)
        h2 = compute_entry_hash(changes={'b': 2, 'a': 1}, **base)
        self.assertEqual(h1, h2)

    def test_genesis_and_multi_entry_chain_valid(self):
        rows = _append(self.org, 3)
        self.assertEqual(rows[0].seq, 1)
        self.assertEqual(rows[0].prev_hash, '')           # genesis
        self.assertEqual(rows[1].prev_hash, rows[0].entry_hash)
        self.assertEqual(rows[2].prev_hash, rows[1].entry_hash)
        self.assertEqual(verify_chain(self.org.id)['status'], VERDICT_VALID)

    def test_changed_protected_field_breaks_verification(self):
        rows = _append(self.org, 3)
        tampered = rows[1]
        with _tamper_permitted():
            with connection.cursor() as cur:
                cur.execute(
                    "UPDATE contracts_auditlog SET changes = %s WHERE id = %s",
                    ['{"event": "tampered"}', tampered.pk],
                )
        res = verify_chain(self.org.id)
        self.assertEqual(res['status'], VERDICT_HASH_MISMATCH)
        self.assertEqual(res['first_broken']['seq'], 2)

    def test_changed_prev_hash_breaks_link(self):
        rows = _append(self.org, 3)
        row = rows[2]
        with _tamper_permitted():
            with connection.cursor() as cur:
                cur.execute(
                    "UPDATE contracts_auditlog SET prev_hash = %s WHERE id = %s",
                    ['deadbeef', row.pk],
                )
        res = verify_chain(self.org.id)
        self.assertEqual(res['status'], VERDICT_BROKEN_LINK)
        self.assertEqual(res['first_broken']['seq'], 3)

    def test_missing_predecessor_detected(self):
        rows = _append(self.org, 4)
        middle = rows[1]  # seq 2
        with _tamper_permitted():
            with connection.cursor() as cur:
                cur.execute("DELETE FROM contracts_auditlog WHERE id = %s", [middle.pk])
        res = verify_chain(self.org.id)
        self.assertEqual(res['status'], VERDICT_MISSING_PREDECESSOR)

    def test_organization_chains_are_isolated(self):
        org_b = _org('Other Chain', 'other-chain')
        _append(self.org, 3)
        _append(org_b, 2)
        self.assertEqual(verify_chain(self.org.id)['status'], VERDICT_VALID)
        self.assertEqual(verify_chain(org_b.id)['status'], VERDICT_VALID)
        # Tampering org A leaves org B valid.
        row = AuditLog.objects.filter(organization=self.org, seq=2).first()
        with _tamper_permitted():
            with connection.cursor() as cur:
                cur.execute(
                    "UPDATE contracts_auditlog SET outcome = %s WHERE id = %s",
                    ['failure', row.pk],
                )
        self.assertNotEqual(verify_chain(self.org.id)['status'], VERDICT_VALID)
        self.assertEqual(verify_chain(org_b.id)['status'], VERDICT_VALID)


class ImmutabilityTests(TestCase):
    def setUp(self):
        self.org = _org('Immutable Org', 'immutable-org')
        self.row = _append(self.org, 1)[0]

    def test_update_through_save_is_rejected(self):
        self.row.outcome = 'failure'
        with self.assertRaises(AuditWriteError):
            self.row.save()

    def test_delete_is_rejected(self):
        with self.assertRaises(AuditWriteError):
            self.row.delete()

    def test_queryset_update_is_rejected(self):
        with self.assertRaises(AuditWriteError):
            AuditLog.objects.filter(pk=self.row.pk).update(outcome='failure')

    def test_queryset_delete_is_rejected(self):
        with self.assertRaises(AuditWriteError):
            AuditLog.objects.filter(pk=self.row.pk).delete()

    def test_admin_is_read_only(self):
        from contracts.admin import AuditLogAdmin
        from django.contrib.admin.sites import site
        a = AuditLogAdmin(AuditLog, site)
        self.assertFalse(a.has_add_permission(None))
        self.assertFalse(a.has_change_permission(None))
        self.assertFalse(a.has_delete_permission(None))


class EventCompletenessTests(TestCase):
    def setUp(self):
        self.org = _org('Events Org', 'events-org')
        self.user = _member(self.org, 'eventuser')

    def _has_event(self, event_type, **filters):
        return AuditLog.objects.filter(event_type=event_type, **filters).exists()

    def test_login_success_is_audited(self):
        c = Client()
        ok = c.post(reverse('login'), {'username': 'eventuser', 'password': PW})
        self.assertIn(ok.status_code, (302, 200))
        self.assertTrue(self._has_event('auth.login_succeeded'))

    def test_login_failure_is_audited_without_password(self):
        c = Client()
        c.post(reverse('login'), {'username': 'eventuser', 'password': 'wrong'})
        row = AuditLog.objects.filter(event_type='auth.login_failed').first()
        self.assertIsNotNone(row)
        self.assertEqual(row.outcome, AuditLog.Outcome.FAILURE)
        # The attempted password must never be stored.
        import json
        self.assertNotIn('wrong', json.dumps(row.changes))

    def test_logout_is_audited(self):
        c = Client()
        c.force_login(self.user)
        c.logout()
        self.assertTrue(self._has_event('auth.logout'))

    def test_scheduled_job_failure_is_audited_and_linked(self):
        from contracts.services.job_runs import record_job_run
        try:
            with record_job_run('demo_failer', organization=self.org) as run:
                run.records_examined = 1
                raise RuntimeError('kaboom')
        except RuntimeError:
            pass
        row = AuditLog.objects.filter(event_type='job.failed', organization=self.org).first()
        self.assertIsNotNone(row)
        self.assertEqual(row.actor_type, AuditLog.ActorType.SCHEDULED_JOB)
        self.assertIsNotNone(row.job_run_id)  # links to the ScheduledJobRun

    def test_obligation_completion_is_audited(self):
        from contracts.models import Deadline
        from contracts.services.obligations import get_obligation_service
        contract = Contract.objects.create(organization=self.org, title='C', created_by=self.user)
        d = Deadline.objects.create(
            contract=contract, title='File report',
            due_date='2026-07-01', deadline_type=Deadline.DeadlineType.PAYMENT,
        )
        get_obligation_service(self.org).update_obligation(str(d.pk), status='completed')
        self.assertTrue(self._has_event('obligation.completed', organization=self.org))


class TransactionalityTests(TestCase):
    def setUp(self):
        self.org = _org('Txn Org', 'txn-org')

    def test_rolled_back_transaction_leaves_no_false_success(self):
        from contracts.middleware import log_action
        before = AuditLog.objects.count()
        try:
            with transaction.atomic():
                log_action(None, 'CREATE', 'Contract', object_id=1,
                           organization=self.org, changes={'event': 'contract.created'})
                raise RuntimeError('business failure after audit')
        except RuntimeError:
            pass
        # The audit row participated in the rolled-back transaction.
        self.assertEqual(AuditLog.objects.count(), before)


class AuditReadTenantSafetyTests(TestCase):
    def setUp(self):
        self.org_a = _org('Tenant A', 'tenant-a')
        self.org_b = _org('Tenant B', 'tenant-b')
        self.user_a = _member(self.org_a, 'alice')
        self.user_b = _member(self.org_b, 'bob')
        _append(self.org_a, 2)
        _append(self.org_b, 2)

    def test_anonymous_cannot_view_audit(self):
        resp = Client().get(reverse('contracts:audit_log_list'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login', resp.url)

    def test_org_a_user_sees_only_org_a_rows(self):
        c = Client()
        c.force_login(self.user_a)
        resp = c.get(reverse('contracts:audit_log_list'))
        self.assertEqual(resp.status_code, 200)
        logs = resp.context['logs']
        org_ids = {log.organization_id for log in logs}
        self.assertEqual(org_ids, {self.org_a.id})
        self.assertNotIn(self.org_b.id, org_ids)

    def test_filter_by_action(self):
        c = Client()
        c.force_login(self.user_a)
        resp = c.get(reverse('contracts:audit_log_list'), {'action': 'CREATE'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(all(log.action == 'CREATE' for log in resp.context['logs']))

    def test_chain_status_present_for_org(self):
        c = Client()
        c.force_login(self.user_a)
        resp = c.get(reverse('contracts:audit_log_list'))
        self.assertEqual(resp.context['chain_status']['status'], VERDICT_VALID)


class SeqUniquenessTests(TestCase):
    """Both chains enforce sequence uniqueness via partial unique constraints."""

    def test_system_chain_duplicate_seq_rejected(self):
        AuditLog.objects.create(organization=None, action='LOGIN', model_name='User',
                                event_type='auth.login_failed', seq=1, hash_version=2,
                                entry_hash='a')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AuditLog.objects.create(organization=None, action='LOGIN', model_name='User',
                                        event_type='auth.login_failed', seq=1, hash_version=2,
                                        entry_hash='b')

    def test_tenant_chain_duplicate_seq_rejected(self):
        org = _org('UniqOrg', 'uniq-org')
        AuditLog.objects.create(organization=org, action='CREATE', model_name='Contract',
                                event_type='contract.created', seq=1, hash_version=2, entry_hash='a')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AuditLog.objects.create(organization=org, action='CREATE', model_name='Contract',
                                        event_type='contract.created', seq=1, hash_version=2,
                                        entry_hash='b')

    def test_two_orgs_may_share_seq_number(self):
        a = _org('SeqA', 'seq-a')
        b = _org('SeqB', 'seq-b')
        _append(a, 1)
        _append(b, 1)
        self.assertEqual(verify_chain(a.id)['status'], VERDICT_VALID)
        self.assertEqual(verify_chain(b.id)['status'], VERDICT_VALID)


class TenantAttributionGuardTests(TestCase):
    """Org-owned events must never silently fall onto the system chain."""

    def setUp(self):
        self.org = _org('Attr Org', 'attr-org')
        self.user = _member(self.org, 'attruser')

    def test_org_resolved_from_target_when_omitted(self):
        from contracts.services.audit import append_audit
        contract = Contract.objects.create(organization=self.org, title='C', created_by=self.user)
        entry = append_audit(action='UPDATE', model_name='Contract', object_id=contract.pk,
                             changes={'event': 'contract.updated'})
        self.assertEqual(entry.organization_id, self.org.id)  # auto-resolved

    def test_unresolvable_org_owned_event_is_rejected(self):
        from contracts.services.audit import append_audit, AuditMisclassificationError
        with self.assertRaises(AuditMisclassificationError):
            append_audit(action='UPDATE', model_name='Contract', object_id=999999,
                         changes={'event': 'contract.updated'})

    def test_log_action_reraises_misclassification(self):
        from contracts.middleware import log_action
        from contracts.services.audit import AuditMisclassificationError
        with self.assertRaises(AuditMisclassificationError):
            log_action(None, 'UPDATE', 'Contract', object_id=999999,
                       changes={'event': 'contract.updated'})

    def test_platform_event_allowed_on_system_chain(self):
        from contracts.services.audit import append_audit
        # 'User' is a platform target -> system chain is legitimate, no raise.
        entry = append_audit(action='LOGIN', model_name='User',
                             event_type='auth.login_failed', outcome='failure')
        self.assertIsNone(entry.organization_id)


class VerifierDuplicateSeqTests(TestCase):
    """Verifier flags duplicate seq explicitly (defense even if DB allows it).

    The unique constraint normally prevents duplicates, so we drop it for this
    test to simulate 'database protection absent' and prove the verifier still
    catches it. TransactionTestCase-free via schema_editor within the test txn.
    """

    def test_verifier_detects_duplicate_seq_without_db_constraint(self):
        from django.db import connection
        from contracts.services.audit import VERDICT_DUPLICATE_SEQ, verify_chain
        org = _org('DupOrg', 'dup-org')
        _append(org, 2)  # valid seq 1,2
        # Simulate absent DB protection: drop the unique index, inject a
        # duplicate seq=2, and prove the verifier still rejects it.
        with connection.cursor() as cur:
            cur.execute('DROP INDEX IF EXISTS audit_org_seq_uniq')
        AuditLog.objects.create(
            organization=org, action='CREATE', model_name='Contract',
            event_type='contract.created', seq=2, hash_version=2, entry_hash='dup',
        )
        res = verify_chain(org.id)
        self.assertEqual(res['status'], VERDICT_DUPLICATE_SEQ)


class LoginFailureAbuseTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()  # avoid leaking throttle/rate-limit counters to other tests

    def test_login_failure_audit_is_throttled(self):
        # Fire the auth signal directly to test the audit throttle in isolation
        # (without tripping the HTTP login rate-limiter).
        from django.contrib.auth.signals import user_login_failed
        for _ in range(12):
            user_login_failed.send(sender='test', credentials={'username': 'GHOST@x.com'}, request=None)
        rows = AuditLog.objects.filter(event_type='auth.login_failed')
        # Capped well below 12 attempts (throttle window).
        self.assertLessEqual(rows.count(), 5)
        self.assertGreaterEqual(rows.count(), 1)
        # Never tenant-attributed; username normalized; no password stored.
        self.assertTrue(all(r.organization_id is None for r in rows))
        self.assertTrue(all(r.changes.get('username') == 'ghost@x.com' for r in rows))


class VerifyCommandTests(TestCase):
    def setUp(self):
        self.org = _org('Verify Org', 'verify-org')
        _append(self.org, 3)

    def test_command_passes_on_valid_chain(self):
        from django.core.management import call_command
        call_command('verify_audit_chain', '--organization', 'verify-org')  # no raise

    def test_command_raises_on_tampered_chain(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError
        row = AuditLog.objects.filter(organization=self.org, seq=2).first()
        with _tamper_permitted():
            with connection.cursor() as cur:
                cur.execute(
                    "UPDATE contracts_auditlog SET outcome = %s WHERE id = %s",
                    ['failure', row.pk],
                )
        # Non-zero exit is surfaced as CommandError by Django's BaseCommand.
        with self.assertRaises(CommandError):
            call_command('verify_audit_chain', '--organization', 'verify-org')
