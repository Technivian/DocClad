"""Phase 5G — contract lifecycle rehearsal (graph, approval, signature, bypass, audit)."""
from __future__ import annotations

import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from contracts.models import (
    ApprovalRequest, AuditLog, Contract, Organization, OrganizationMembership, SignatureRequest,
)
from contracts.services.contract_lifecycle import (
    CONTRACT_STATUS_TRANSITIONS, ContractTransitionForbidden,
    ContractTransitionPreconditionFailed, InvalidContractTransition,
    get_contract_lifecycle_service,
)

User = get_user_model()
PW = 'Pw!12345xyz'
ALL = list(CONTRACT_STATUS_TRANSITIONS.keys())
SR = SignatureRequest.Status


def _org(slug):
    return Organization.objects.create(name=slug, slug=slug)


def _user(org, name, role=OrganizationMembership.Role.OWNER):
    u = User.objects.create_user(username=name, password=PW, email=f'{name}@ex.com')
    OrganizationMembership.objects.create(user=u, organization=org, role=role, is_active=True)
    return u


def _contract(org, creator, status='IN_PROGRESS'):
    kwargs = {'organization': org, 'title': 'C', 'created_by': creator, 'status': status}
    if status == 'ACTIVE':
        kwargs['lifecycle_stage'] = Contract.LifecycleStage.OBLIGATION_TRACKING
    return Contract.objects.create(**kwargs)


def _approve(contract, status='APPROVED'):
    return ApprovalRequest.objects.create(organization=contract.organization, contract=contract,
                                          approval_step='legal', status=status)


def _sig(contract, email, status, age_minutes=0):
    s = SignatureRequest.objects.create(organization=contract.organization, contract=contract,
                                        signer_name=email, signer_email=email, status=status)
    # deterministic ordering: older requests get an earlier created_at
    SignatureRequest.objects.filter(pk=s.pk).update(
        created_at=timezone.now() - timedelta(minutes=age_minutes))
    return s


class TransitionGraph(TestCase):
    def setUp(self):
        self.org = _org('g-org'); self.user = _user(self.org, 'g-owner')
        self.svc = get_contract_lifecycle_service()

    def test_full_graph_allowed_and_forbidden_non_active(self):
        for frm in ALL:
            allowed = CONTRACT_STATUS_TRANSITIONS[frm]
            for to in ALL:
                if to == frm or to == 'ACTIVE':
                    continue  # same-status + ACTIVE handled separately
                c = _contract(self.org, self.user, status=frm)
                if to in allowed:
                    self.svc.transition(c, to, self.user)
                    c.refresh_from_db()
                    self.assertEqual(c.status, to, f'{frm}->{to} should succeed')
                else:
                    with self.assertRaises(InvalidContractTransition, msg=f'{frm}->{to} must fail'):
                        self.svc.transition(c, to, self.user)
                    c.refresh_from_db()
                    self.assertEqual(c.status, frm, f'{frm}->{to} must not change status')

    def test_draft_to_active_rejected(self):
        c = _contract(self.org, self.user, 'IN_PROGRESS')
        with self.assertRaises(ContractTransitionPreconditionFailed):
            self.svc.transition(c, 'ACTIVE', self.user)

    def test_terminal_states_cannot_reopen(self):
        for term in ('EXPIRED', 'TERMINATED', 'ARCHIVED', 'CANCELLED'):
            c = _contract(self.org, self.user, term)
            for to in ('IN_PROGRESS', 'ACTIVE'):
                with self.assertRaises(InvalidContractTransition):
                    self.svc.transition(c, to, self.user)

    def test_same_status_is_idempotent_noop(self):
        c = _contract(self.org, self.user, 'IN_PROGRESS')
        before = AuditLog.objects.count()
        self.svc.transition(c, 'IN_PROGRESS', self.user)  # no error
        self.assertEqual(AuditLog.objects.count(), before)  # no audit


class AuthorizationAndAudit(TestCase):
    def setUp(self):
        self.org_a = _org('ga'); self.org_b = _org('gb')
        self.owner = _user(self.org_a, 'ga-owner')
        self.member_b = _user(self.org_b, 'gb-member', OrganizationMembership.Role.MEMBER)
        self.svc = get_contract_lifecycle_service()

    def test_unauthenticated_actor_rejected(self):
        c = _contract(self.org_a, self.owner, 'IN_PROGRESS')
        with self.assertRaises(ContractTransitionForbidden):
            self.svc.transition(c, 'CANCELLED', actor=None)  # not system

    def test_cross_tenant_actor_rejected(self):
        c = _contract(self.org_a, self.owner, 'IN_PROGRESS')
        with self.assertRaises(ContractTransitionForbidden):
            self.svc.transition(c, 'CANCELLED', self.member_b)
        c.refresh_from_db(); self.assertEqual(c.status, 'IN_PROGRESS')

    def test_one_chained_audit_per_success(self):
        c = _contract(self.org_a, self.owner, 'IN_PROGRESS')
        self.svc.transition(c, 'CANCELLED', self.owner)
        rows = AuditLog.objects.filter(event_type='contract.status_changed', object_id=c.pk)
        self.assertEqual(rows.count(), 1)
        r = rows.first()
        self.assertEqual(r.organization_id, self.org_a.id)
        self.assertIsNotNone(r.seq)
        self.assertEqual((r.changes['from'], r.changes['to']), ('IN_PROGRESS', 'CANCELLED'))

    def test_rejected_transition_no_false_audit(self):
        c = _contract(self.org_a, self.owner, 'IN_PROGRESS')
        before = AuditLog.objects.filter(event_type='contract.status_changed').count()
        with self.assertRaises(InvalidContractTransition):
            self.svc.transition(c, 'EXPIRED', self.owner)
        after = AuditLog.objects.filter(event_type='contract.status_changed').count()
        self.assertEqual(before, after)


class ApprovalPrerequisite(TestCase):
    def setUp(self):
        self.org = _org('appr'); self.user = _user(self.org, 'appr-owner')
        self.other = _org('appr-other'); self.other_u = _user(self.other, 'other-owner')
        self.svc = get_contract_lifecycle_service()

    def _activate(self, c):
        return self.svc.transition(c, 'ACTIVE', self.user)

    def test_no_approval_blocks(self):
        c = _contract(self.org, self.user, 'IN_PROGRESS')
        with self.assertRaises(ContractTransitionPreconditionFailed):
            self._activate(c)

    def test_pending_approval_blocks(self):
        c = _contract(self.org, self.user, 'IN_PROGRESS'); _approve(c, 'PENDING')
        with self.assertRaises(ContractTransitionPreconditionFailed):
            self._activate(c)

    def test_rejected_approval_blocks(self):
        c = _contract(self.org, self.user, 'IN_PROGRESS'); _approve(c, 'REJECTED')
        with self.assertRaises(ContractTransitionPreconditionFailed):
            self._activate(c)

    def test_approved_request_allows(self):
        c = _contract(self.org, self.user, 'IN_PROGRESS'); _approve(c, 'APPROVED')
        self._activate(c); c.refresh_from_db(); self.assertEqual(c.status, 'ACTIVE')

    def test_approval_of_other_contract_does_not_satisfy(self):
        other_c = _contract(self.org, self.user, 'IN_PROGRESS'); _approve(other_c, 'APPROVED')
        c = _contract(self.org, self.user, 'IN_PROGRESS')  # no approval of its own
        with self.assertRaises(ContractTransitionPreconditionFailed):
            self._activate(c)

    def test_approval_in_other_org_does_not_satisfy(self):
        c = _contract(self.org, self.user, 'IN_PROGRESS')
        # an approved request on a different org's contract
        oc = _contract(self.other, self.other_u, 'IN_PROGRESS'); _approve(oc, 'APPROVED')
        with self.assertRaises(ContractTransitionPreconditionFailed):
            self._activate(c)


class SignaturePrerequisite(TestCase):
    """Activation evaluates the CURRENT request per signer (latest by created_at)."""

    def setUp(self):
        self.org = _org('sig'); self.user = _user(self.org, 'sig-owner')
        self.svc = get_contract_lifecycle_service()

    def _ready(self):
        c = _contract(self.org, self.user, 'IN_PROGRESS'); _approve(c, 'APPROVED'); return c

    def _try_activate(self, c):
        self.svc.transition(c, 'ACTIVE', self.user); c.refresh_from_db(); return c.status

    def test_no_signature_request_activates(self):
        c = self._ready()
        self.assertEqual(self._try_activate(c), 'ACTIVE')

    def test_one_signed_activates(self):
        c = self._ready(); _sig(c, 'a@x', SR.SIGNED)
        self.assertEqual(self._try_activate(c), 'ACTIVE')

    def test_one_pending_blocks(self):
        c = self._ready(); _sig(c, 'a@x', SR.PENDING)
        with self.assertRaises(ContractTransitionPreconditionFailed):
            self._try_activate(c)

    def test_signed_current_plus_old_cancelled_activates(self):
        c = self._ready()
        _sig(c, 'a@x', SR.CANCELLED, age_minutes=60)   # old
        _sig(c, 'a@x', SR.SIGNED, age_minutes=1)        # current
        self.assertEqual(self._try_activate(c), 'ACTIVE')

    def test_signed_current_plus_expired_historical_activates(self):
        c = self._ready()
        _sig(c, 'a@x', SR.EXPIRED, age_minutes=60)
        _sig(c, 'a@x', SR.SIGNED, age_minutes=1)
        self.assertEqual(self._try_activate(c), 'ACTIVE')

    def test_superseded_declined_then_signed_activates(self):
        c = self._ready()
        _sig(c, 'a@x', SR.DECLINED, age_minutes=60)     # old refusal
        _sig(c, 'a@x', SR.SIGNED, age_minutes=1)         # re-issued + signed
        self.assertEqual(self._try_activate(c), 'ACTIVE')

    def test_current_declined_blocks(self):
        c = self._ready(); _sig(c, 'a@x', SR.DECLINED)
        with self.assertRaises(ContractTransitionPreconditionFailed):
            self._try_activate(c)

    def test_abandoned_pending_blocks(self):
        c = self._ready(); _sig(c, 'a@x', SR.PENDING, age_minutes=120)
        with self.assertRaises(ContractTransitionPreconditionFailed):
            self._try_activate(c)

    def test_multi_signer_partly_signed_blocks(self):
        c = self._ready()
        _sig(c, 'a@x', SR.SIGNED)
        _sig(c, 'b@x', SR.SENT)   # second signer in-flight
        with self.assertRaises(ContractTransitionPreconditionFailed):
            self._try_activate(c)

    def test_all_signers_signed_activates(self):
        c = self._ready()
        _sig(c, 'a@x', SR.SIGNED); _sig(c, 'b@x', SR.SIGNED)
        self.assertEqual(self._try_activate(c), 'ACTIVE')

    def test_all_cancelled_workflow_withdrawn_activates(self):
        c = self._ready()
        _sig(c, 'a@x', SR.CANCELLED); _sig(c, 'b@x', SR.EXPIRED)
        self.assertEqual(self._try_activate(c), 'ACTIVE')

    def test_other_contract_signature_does_not_block(self):
        c = self._ready()
        other = _contract(self.org, self.user, 'IN_PROGRESS')
        _sig(other, 'a@x', SR.PENDING)   # in-flight on a DIFFERENT contract
        self.assertEqual(self._try_activate(c), 'ACTIVE')


class StaleInstanceReread(TestCase):
    def setUp(self):
        self.org = _org('stale'); self.user = _user(self.org, 'stale-owner')
        self.svc = get_contract_lifecycle_service()

    def test_service_uses_db_state_not_stale_instance(self):
        # Stale instance says DRAFT; DB is updated to ACTIVE by "someone else".
        c = _contract(self.org, self.user, 'IN_PROGRESS')
        stale = Contract.objects.get(pk=c.pk)          # in-memory status DRAFT
        Contract.objects.filter(pk=c.pk).update(status='ACTIVE')  # DB now ACTIVE
        # ACTIVE->EXPIRED is valid; DRAFT->EXPIRED is not. Success proves re-read.
        self.svc.transition(stale, 'EXPIRED', system=True)
        c.refresh_from_db(); self.assertEqual(c.status, 'EXPIRED')

    def test_approval_added_after_load_is_seen(self):
        c = _contract(self.org, self.user, 'IN_PROGRESS')
        stale = Contract.objects.get(pk=c.pk)
        _approve(c, 'APPROVED')  # approval added in DB after instance loaded
        self.svc.transition(stale, 'ACTIVE', self.user)  # re-reads -> sees approval
        c.refresh_from_db(); self.assertEqual(c.status, 'ACTIVE')


class BypassPaths(TestCase):
    def setUp(self):
        self.org = _org('bp'); self.user = _user(self.org, 'bp-owner')
        self.client = Client(); self.client.force_login(self.user)

    def test_html_path_cannot_bypass(self):
        c = _contract(self.org, self.user, 'IN_PROGRESS')
        r = self.client.post(reverse('contracts:contract_update', args=[c.pk]), {
            'title': c.title, 'contract_type': 'OTHER', 'content': 'body', 'status': 'ACTIVE',
            'counterparty': 'X', 'value': '0', 'currency': 'USD',
            'governing_law': 'Delaware', 'owner': self.user.pk,
            'risk_level': 'LOW', 'lifecycle_stage': 'DRAFTING'})
        self.assertIn(r.status_code, (200, 302))
        c.refresh_from_db(); self.assertEqual(c.status, 'IN_PROGRESS')

    def test_bulk_api_cannot_bypass(self):
        c = _contract(self.org, self.user, 'IN_PROGRESS')
        r = self.client.post(reverse('contracts:contracts_bulk_update_api'),
                             data=json.dumps({'contract_ids': [c.pk], 'updates': {'status': 'ACTIVE'}}),
                             content_type='application/json')
        self.assertEqual(r.status_code, 400)
        c.refresh_from_db(); self.assertEqual(c.status, 'IN_PROGRESS')

    def test_bulk_api_valid_transition_goes_through_service(self):
        c = _contract(self.org, self.user, 'IN_PROGRESS')
        r = self.client.post(reverse('contracts:contracts_bulk_update_api'),
                             data=json.dumps({'contract_ids': [c.pk], 'updates': {'status': 'CANCELLED'}}),
                             content_type='application/json')
        self.assertEqual(r.status_code, 200)
        c.refresh_from_db(); self.assertEqual(c.status, 'CANCELLED')
        self.assertTrue(AuditLog.objects.filter(event_type='contract.status_changed', object_id=c.pk).exists())


# ---------------------------------------------------------------------------
# Concurrency (PostgreSQL only): row locking, duplicate activation, races
# ---------------------------------------------------------------------------
import threading
from unittest import skipUnless
from django.db import connection, connections
from django.test import TransactionTestCase


@skipUnless(connection.vendor == 'postgresql', 'PostgreSQL-only (row-lock concurrency)')
class LifecycleConcurrencyPostgres(TransactionTestCase):
    reset_sequences = True

    def _run(self, contract, attempts):
        """attempts: list of (new_status, kwargs). Returns (results, errors)."""
        svc = get_contract_lifecycle_service()
        results, errors = [], []

        def worker(new_status, kwargs):
            try:
                svc.transition(contract, new_status, **kwargs)
                results.append(new_status)
            except Exception as exc:  # noqa: BLE001
                errors.append(type(exc).__name__)
            finally:
                connections.close_all()

        threads = [threading.Thread(target=worker, args=(s, k)) for s, k in attempts]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        return results, errors

    def _audit_count(self, contract):
        return AuditLog.objects.filter(event_type='contract.status_changed', object_id=contract.pk).count()

    def test_duplicate_activation_commits_once(self):
        org = _org('cc1'); u = _user(org, 'cc1-owner')
        c = _contract(org, u, 'IN_PROGRESS'); _approve(c, 'APPROVED')
        results, errors = self._run(c, [('ACTIVE', {'actor': u}), ('ACTIVE', {'actor': u})])
        c.refresh_from_db()
        self.assertEqual(c.status, 'ACTIVE')
        self.assertEqual(self._audit_count(c), 1, 'exactly one status_changed audit')
        self.assertEqual(errors, [], f'no uncaught errors: {errors}')

    def test_racing_terminal_transitions_one_winner(self):
        org = _org('cc2'); u = _user(org, 'cc2-owner')
        c = _contract(org, u, 'ACTIVE')
        results, errors = self._run(c, [
            ('EXPIRED', {'actor': None, 'system': True}),
            ('ARCHIVED', {'actor': u}),
        ])
        c.refresh_from_db()
        self.assertIn(c.status, ('EXPIRED', 'ARCHIVED'))  # exactly one valid terminal
        self.assertEqual(self._audit_count(c), 1, 'only the winning transition is audited')
        # the loser is rejected as an invalid terminal->terminal move (not a DB error)
        self.assertEqual(len(results), 1)
        self.assertTrue(all(e in ('InvalidContractTransition',) for e in errors), errors)
