"""Authorization tests for the approval API (audit findings B3 / C2).

Covers the broken-access-control holes the audit found in
``contracts/api/admin.py`` + ``contracts/services/approval_workflow.py``:

  1. Cross-tenant IDOR — a user in org B must not approve/reject/delegate
     an approval that belongs to org A (must 404, no state change).
  2. Cross-tenant contract endpoints — initiate / list approvals on another
     org's contract must 404.
  3. Assignee ownership — a same-org user who is neither the assignee nor an
     admin must not act (403).
  4. Segregation of duties — the contract creator must not approve their own
     contract, even as org owner (403).
  5. Happy path — the assigned approver (who did not create the contract) can
     approve (200).

Run: DJANGO_SETTINGS_MODULE=config.settings_test python manage.py test \
        tests.test_approval_authorization
"""
import json

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from contracts.models import (
    Organization,
    OrganizationMembership,
    Contract,
    ApprovalRequest,
)

User = get_user_model()


class ApprovalAuthorizationTests(TestCase):
    def setUp(self):
        # ---- Org A: creator (owner) + a separate assigned approver ----
        self.org_a = Organization.objects.create(name='Firm Alpha', slug='firm-alpha')
        self.creator_a = User.objects.create_user(username='creator_a', password='passA1234!')
        OrganizationMembership.objects.create(
            organization=self.org_a, user=self.creator_a,
            role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        self.approver_a = User.objects.create_user(username='approver_a', password='passA1234!')
        OrganizationMembership.objects.create(
            organization=self.org_a, user=self.approver_a,
            role=OrganizationMembership.Role.MEMBER, is_active=True,
        )
        # A third org-A member who is neither approver nor admin.
        self.bystander_a = User.objects.create_user(username='bystander_a', password='passA1234!')
        OrganizationMembership.objects.create(
            organization=self.org_a, user=self.bystander_a,
            role=OrganizationMembership.Role.MEMBER, is_active=True,
        )

        # ---- Org B: an attacker in a different tenant ----
        self.org_b = Organization.objects.create(name='Firm Beta', slug='firm-beta')
        self.attacker_b = User.objects.create_user(username='attacker_b', password='passB1234!')
        OrganizationMembership.objects.create(
            organization=self.org_b, user=self.attacker_b,
            role=OrganizationMembership.Role.OWNER, is_active=True,
        )

        # Org A contract created by creator_a, with a PENDING approval assigned
        # to approver_a.
        self.contract_a = Contract.objects.create(
            organization=self.org_a, title='Alpha NDA',
            contract_type='NDA', status='IN_PROGRESS', created_by=self.creator_a,
        )
        self.approval_a = ApprovalRequest.objects.create(
            organization=self.org_a, contract=self.contract_a,
            approval_step='LEGAL', status='PENDING', assigned_to=self.approver_a,
        )

    # ---- helpers ----
    def _post(self, name, **kwargs):
        body = kwargs.pop('body', {})
        return self.client.post(
            reverse(f'contracts:{name}', kwargs=kwargs),
            data=json.dumps(body), content_type='application/json',
        )

    def _refresh_status(self):
        self.approval_a.refresh_from_db()
        return self.approval_a.status

    # ---- 1. Cross-tenant IDOR on approve/reject/delegate ----
    def test_cross_tenant_approve_is_blocked(self):
        self.client.force_login(self.attacker_b)
        resp = self._post('approval_approve_api', approval_id=self.approval_a.id)
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(self._refresh_status(), 'PENDING')
        self.approval_a.refresh_from_db()
        self.assertIsNone(self.approval_a.decided_by_id)

    def test_cross_tenant_reject_is_blocked(self):
        self.client.force_login(self.attacker_b)
        resp = self._post('approval_reject_api', approval_id=self.approval_a.id)
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(self._refresh_status(), 'PENDING')

    def test_cross_tenant_delegate_is_blocked(self):
        self.client.force_login(self.attacker_b)
        resp = self._post(
            'approval_delegate_api', approval_id=self.approval_a.id,
            body={'to_user_id': self.attacker_b.id},
        )
        self.assertEqual(resp.status_code, 404)
        self.approval_a.refresh_from_db()
        self.assertEqual(self.approval_a.assigned_to_id, self.approver_a.id)

    # ---- 2. Cross-tenant contract endpoints ----
    def test_cross_tenant_initiate_is_blocked(self):
        self.client.force_login(self.attacker_b)
        resp = self._post('approval_initiate_api', contract_id=self.contract_a.id)
        self.assertEqual(resp.status_code, 404)

    def test_cross_tenant_contract_list_is_blocked(self):
        self.client.force_login(self.attacker_b)
        resp = self.client.get(
            reverse('contracts:approval_contract_list_api', kwargs={'contract_id': self.contract_a.id})
        )
        self.assertEqual(resp.status_code, 404)

    # ---- 3. Same-org non-assignee, non-admin ----
    def test_same_org_non_assignee_cannot_approve(self):
        self.client.force_login(self.bystander_a)
        resp = self._post('approval_approve_api', approval_id=self.approval_a.id)
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(self._refresh_status(), 'PENDING')

    # ---- 4. Segregation of duties: creator can't self-approve ----
    def test_creator_cannot_approve_own_contract(self):
        # creator_a is org OWNER (admin) AND the contract creator → still blocked.
        self.client.force_login(self.creator_a)
        resp = self._post('approval_approve_api', approval_id=self.approval_a.id)
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(self._refresh_status(), 'PENDING')

    # ---- 5. Happy path: assigned approver who didn't create it ----
    def test_assigned_approver_can_approve(self):
        self.client.force_login(self.approver_a)
        resp = self._post(
            'approval_approve_api', approval_id=self.approval_a.id,
            body={'comments': 'looks good'},
        )
        self.assertEqual(resp.status_code, 200)
        self.approval_a.refresh_from_db()
        self.assertEqual(self.approval_a.status, 'APPROVED')
        self.assertEqual(self.approval_a.decided_by_id, self.approver_a.id)
