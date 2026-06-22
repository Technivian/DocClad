"""Phase 4B — canonical Contract.status transition guardrails."""
from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from contracts.models import (
    ApprovalRequest,
    AuditLog,
    Contract,
    Organization,
    OrganizationMembership,
    SignatureRequest,
)
from contracts.services.contract_lifecycle import (
    ContractTransitionForbidden,
    ContractTransitionPreconditionFailed,
    InvalidContractTransition,
    get_contract_lifecycle_service,
)

User = get_user_model()
PW = 'StrongPw!123'


def _org(name, slug):
    return Organization.objects.create(name=name, slug=slug)


def _member(org, username, role=OrganizationMembership.Role.OWNER):
    u = User.objects.create_user(username=username, password=PW, email=f'{username}@ex.com')
    OrganizationMembership.objects.create(user=u, organization=org, role=role, is_active=True)
    return u


def _contract(org, creator, status='DRAFT'):
    return Contract.objects.create(organization=org, title='C', created_by=creator, status=status)


def _approve(contract):
    return ApprovalRequest.objects.create(
        organization=contract.organization, contract=contract, approval_step='legal',
        status=ApprovalRequest.Status.APPROVED,
    )


class TransitionGraphTests(TestCase):
    def setUp(self):
        self.org = _org('Lc Org', 'lc-org')
        self.user = _member(self.org, 'owner')
        self.svc = get_contract_lifecycle_service()

    def test_allowed_simple_transition(self):
        c = _contract(self.org, self.user, status='DRAFT')
        self.svc.transition(c, 'IN_REVIEW', self.user)
        c.refresh_from_db()
        self.assertEqual(c.status, 'IN_REVIEW')

    def test_forbidden_direct_jump_rejected(self):
        c = _contract(self.org, self.user, status='DRAFT')
        with self.assertRaises(InvalidContractTransition):
            self.svc.transition(c, 'COMPLETED', self.user)
        c.refresh_from_db()
        self.assertEqual(c.status, 'DRAFT')

    def test_terminal_state_cannot_reverse(self):
        c = _contract(self.org, self.user, status='EXPIRED')
        with self.assertRaises(InvalidContractTransition):
            self.svc.transition(c, 'ACTIVE', self.user)

    def test_idempotent_same_status_is_noop(self):
        c = _contract(self.org, self.user, status='DRAFT')
        before = AuditLog.objects.count()
        self.svc.transition(c, 'DRAFT', self.user)
        self.assertEqual(AuditLog.objects.count(), before)  # no audit, no error

    def test_active_requires_approval(self):
        c = _contract(self.org, self.user, status='APPROVED')
        with self.assertRaises(ContractTransitionPreconditionFailed):
            self.svc.transition(c, 'ACTIVE', self.user)

    def test_active_with_approval_succeeds(self):
        c = _contract(self.org, self.user, status='APPROVED')
        _approve(c)
        self.svc.transition(c, 'ACTIVE', self.user)
        c.refresh_from_db()
        self.assertEqual(c.status, 'ACTIVE')

    def test_active_blocked_by_unsigned_signature_request(self):
        c = _contract(self.org, self.user, status='APPROVED')
        _approve(c)
        SignatureRequest.objects.create(
            organization=self.org, contract=c, signer_email='s@x.com',
            signer_name='S', status=SignatureRequest.Status.PENDING,
        )
        with self.assertRaises(ContractTransitionPreconditionFailed):
            self.svc.transition(c, 'ACTIVE', self.user)

    def test_active_allowed_when_all_signed(self):
        c = _contract(self.org, self.user, status='APPROVED')
        _approve(c)
        SignatureRequest.objects.create(
            organization=self.org, contract=c, signer_email='s@x.com',
            signer_name='S', status=SignatureRequest.Status.SIGNED,
        )
        self.svc.transition(c, 'ACTIVE', self.user)
        c.refresh_from_db()
        self.assertEqual(c.status, 'ACTIVE')

    def test_chained_audit_event_written(self):
        c = _contract(self.org, self.user, status='DRAFT')
        self.svc.transition(c, 'IN_REVIEW', self.user, reason='submitting')
        row = AuditLog.objects.filter(event_type='contract.status_changed', object_id=c.pk).first()
        self.assertIsNotNone(row)
        self.assertEqual(row.organization_id, self.org.id)
        self.assertEqual(row.changes['from'], 'DRAFT')
        self.assertEqual(row.changes['to'], 'IN_REVIEW')
        self.assertIsNotNone(row.seq)  # part of the tamper-evident chain


class TransitionAuthorizationTests(TestCase):
    def setUp(self):
        self.org_a = _org('A', 'lc-a')
        self.org_b = _org('B', 'lc-b')
        self.owner_a = _member(self.org_a, 'owner_a')
        self.member_b = _member(self.org_b, 'member_b', OrganizationMembership.Role.MEMBER)
        self.svc = get_contract_lifecycle_service()

    def test_cross_tenant_actor_forbidden(self):
        c = _contract(self.org_a, self.owner_a, status='DRAFT')
        with self.assertRaises(ContractTransitionForbidden):
            self.svc.transition(c, 'IN_REVIEW', self.member_b)
        c.refresh_from_db()
        self.assertEqual(c.status, 'DRAFT')

    def test_system_transition_bypasses_user_permission(self):
        c = _contract(self.org_a, self.owner_a, status='ACTIVE')
        # System (job) expiry — no actor, system=True.
        self.svc.transition(c, 'EXPIRED', actor=None, system=True, reason='auto-expire')
        c.refresh_from_db()
        self.assertEqual(c.status, 'EXPIRED')


class TransitionHTMLPathTests(TestCase):
    def setUp(self):
        self.org = _org('Html Org', 'html-org')
        self.user = _member(self.org, 'htmluser')
        self.client = Client()
        self.client.force_login(self.user)

    def _post_status(self, contract, status):
        return self.client.post(
            reverse('contracts:contract_update', args=[contract.pk]),
            data={'title': contract.title, 'contract_type': 'OTHER', 'content': '',
                  'status': status, 'counterparty': 'X', 'value': '0', 'currency': 'USD'},
        )

    def test_html_illegal_transition_rejected(self):
        c = _contract(self.org, self.user, status='DRAFT')
        resp = self._post_status(c, 'ACTIVE')  # DRAFT->ACTIVE not allowed
        self.assertEqual(resp.status_code, 200)  # re-render with error
        c.refresh_from_db()
        self.assertEqual(c.status, 'DRAFT')

    def test_html_active_without_approval_rejected(self):
        c = _contract(self.org, self.user, status='APPROVED')
        resp = self._post_status(c, 'ACTIVE')
        self.assertEqual(resp.status_code, 200)
        c.refresh_from_db()
        self.assertEqual(c.status, 'APPROVED')

    def test_create_forces_draft(self):
        resp = self.client.post(reverse('contracts:contract_create'), data={
            'title': 'New', 'contract_type': 'OTHER', 'content': '',
            'status': 'ACTIVE', 'counterparty': 'X', 'value': '0', 'currency': 'USD',
        })
        self.assertIn(resp.status_code, (302, 200))
        c = Contract.objects.filter(organization=self.org, title='New').first()
        if c:  # created
            self.assertEqual(c.status, 'DRAFT')


class TransitionBulkAPITests(TestCase):
    def setUp(self):
        self.org = _org('Bulk Org', 'bulk-org')
        self.user = _member(self.org, 'bulkuser')
        self.client = Client()
        self.client.force_login(self.user)

    def test_bulk_illegal_status_rejected(self):
        c = _contract(self.org, self.user, status='DRAFT')
        resp = self.client.post(
            reverse('contracts:contracts_bulk_update_api'),
            data=json.dumps({'contract_ids': [c.pk], 'updates': {'status': 'ACTIVE'}}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
        c.refresh_from_db()
        self.assertEqual(c.status, 'DRAFT')

    def test_bulk_legal_status_succeeds(self):
        c = _contract(self.org, self.user, status='DRAFT')
        resp = self.client.post(
            reverse('contracts:contracts_bulk_update_api'),
            data=json.dumps({'contract_ids': [c.pk], 'updates': {'status': 'IN_REVIEW'}}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        c.refresh_from_db()
        self.assertEqual(c.status, 'IN_REVIEW')


class TransitionRollbackTests(TestCase):
    def test_failed_precondition_leaves_no_status_change_or_audit(self):
        org = _org('Rb Org', 'rb-org')
        user = _member(org, 'rbuser')
        c = _contract(org, user, status='APPROVED')
        before = AuditLog.objects.filter(event_type='contract.status_changed').count()
        with self.assertRaises(ContractTransitionPreconditionFailed):
            get_contract_lifecycle_service().transition(c, 'ACTIVE', user)
        c.refresh_from_db()
        self.assertEqual(c.status, 'APPROVED')
        after = AuditLog.objects.filter(event_type='contract.status_changed').count()
        self.assertEqual(before, after)  # no false success audit
