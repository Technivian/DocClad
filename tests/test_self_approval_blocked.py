"""Regression tests for the self-approval blocker (A5).

Segregation of duties (a contract's creator may not decide its approval) was
enforced only in the service layer used by the JSON API; the HTML form/view
applied a weaker rule, so a creator who was also assignee/ADMIN/OWNER could
self-approve through the UI.

These tests prove the rule now holds across BOTH interfaces, for the creator in
each privileged position, and that a separate authorized actor still succeeds.
"""
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
)
from contracts.services.approval_workflow import (
    ApprovalAccessDenied,
    get_approval_workflow_service,
)

User = get_user_model()
PW = 'StrongPw!123'


class _Base(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='City', slug='city')
        self.svc = get_approval_workflow_service()

    def _user(self, username, role):
        u = User.objects.create_user(username=username, password=PW, email=f'{username}@ex.com')
        OrganizationMembership.objects.create(
            user=u, organization=self.org, role=role, is_active=True,
        )
        return u

    def _contract(self, creator):
        return Contract.objects.create(
            organization=self.org, title='Vendor MSA', created_by=creator,
        )

    def _approval(self, contract, assigned_to):
        return ApprovalRequest.objects.create(
            organization=self.org,
            contract=contract,
            approval_step='legal',
            status=ApprovalRequest.Status.PENDING,
            assigned_to=assigned_to,
        )

    def _html_approve(self, user, ar):
        c = Client()
        c.force_login(user)
        return c.post(
            reverse('contracts:approval_request_update', args=[ar.id]),
            data={
                'contract': ar.contract_id,
                'approval_step': ar.approval_step,
                'status': ApprovalRequest.Status.APPROVED,
                'assigned_to': ar.assigned_to_id or '',
                'comments': 'approving my own',
                'due_date': '',
            },
        )

    def _api_approve(self, user, ar):
        c = Client()
        c.force_login(user)
        return c.post(
            reverse('contracts:approval_approve_api', args=[ar.id]),
            data=json.dumps({'comments': 'approving my own'}),
            content_type='application/json',
        )


class CreatorCannotSelfApprove(_Base):
    def test_service_blocks_creator_who_is_assignee(self):
        creator = self._user('creator1', OrganizationMembership.Role.MEMBER)
        ar = self._approval(self._contract(creator), assigned_to=creator)
        with self.assertRaises(ApprovalAccessDenied):
            self.svc.approve(ar.id, creator)
        ar.refresh_from_db()
        self.assertEqual(ar.status, ApprovalRequest.Status.PENDING)

    def test_service_blocks_creator_who_is_admin(self):
        creator = self._user('creator2', OrganizationMembership.Role.ADMIN)
        ar = self._approval(self._contract(creator), assigned_to=None)
        with self.assertRaises(ApprovalAccessDenied):
            self.svc.approve(ar.id, creator)

    def test_service_blocks_creator_who_is_owner(self):
        creator = self._user('creator3', OrganizationMembership.Role.OWNER)
        ar = self._approval(self._contract(creator), assigned_to=creator)
        with self.assertRaises(ApprovalAccessDenied):
            self.svc.approve(ar.id, creator)

    def test_html_blocks_creator_who_is_assignee(self):
        creator = self._user('creator4', OrganizationMembership.Role.MEMBER)
        ar = self._approval(self._contract(creator), assigned_to=creator)
        resp = self._html_approve(creator, ar)
        # Form re-renders (200) with the SoD error; no redirect, no state change.
        self.assertEqual(resp.status_code, 200)
        ar.refresh_from_db()
        self.assertEqual(ar.status, ApprovalRequest.Status.PENDING)
        self.assertIsNone(ar.decided_by_id)

    def test_html_blocks_creator_who_is_admin(self):
        creator = self._user('creator5', OrganizationMembership.Role.ADMIN)
        ar = self._approval(self._contract(creator), assigned_to=creator)
        resp = self._html_approve(creator, ar)
        self.assertEqual(resp.status_code, 200)
        ar.refresh_from_db()
        self.assertEqual(ar.status, ApprovalRequest.Status.PENDING)

    def test_html_blocks_creator_who_is_owner(self):
        creator = self._user('creator6', OrganizationMembership.Role.OWNER)
        ar = self._approval(self._contract(creator), assigned_to=creator)
        resp = self._html_approve(creator, ar)
        self.assertEqual(resp.status_code, 200)
        ar.refresh_from_db()
        self.assertEqual(ar.status, ApprovalRequest.Status.PENDING)

    def test_api_blocks_creator_who_is_owner(self):
        creator = self._user('creator7', OrganizationMembership.Role.OWNER)
        ar = self._approval(self._contract(creator), assigned_to=creator)
        resp = self._api_approve(creator, ar)
        self.assertEqual(resp.status_code, 403)
        ar.refresh_from_db()
        self.assertEqual(ar.status, ApprovalRequest.Status.PENDING)

    def test_api_and_html_produce_consistent_error_text(self):
        creator = self._user('creator8', OrganizationMembership.Role.OWNER)
        ar = self._approval(self._contract(creator), assigned_to=creator)
        api = self._api_approve(creator, ar)
        html = self._html_approve(creator, ar)
        msg = 'You cannot decide on an approval for a contract you own.'
        self.assertIn(msg, api.json().get('error', ''))
        self.assertContains(html, msg)


class SeparateActorCanApprove(_Base):
    def test_html_separate_authorized_actor_approves(self):
        creator = self._user('author', OrganizationMembership.Role.MEMBER)
        approver = self._user('approver', OrganizationMembership.Role.ADMIN)
        ar = self._approval(self._contract(creator), assigned_to=approver)
        resp = self._html_approve(approver, ar)
        self.assertEqual(resp.status_code, 302)
        ar.refresh_from_db()
        self.assertEqual(ar.status, ApprovalRequest.Status.APPROVED)
        self.assertEqual(ar.decided_by_id, approver.id)

    def test_api_separate_authorized_actor_approves(self):
        creator = self._user('author2', OrganizationMembership.Role.MEMBER)
        approver = self._user('approver2', OrganizationMembership.Role.OWNER)
        ar = self._approval(self._contract(creator), assigned_to=approver)
        resp = self._api_approve(approver, ar)
        self.assertEqual(resp.status_code, 200)
        ar.refresh_from_db()
        self.assertEqual(ar.status, ApprovalRequest.Status.APPROVED)


class ApprovalDecisionAuditing(_Base):
    def test_successful_approval_is_audited(self):
        creator = self._user('a_author', OrganizationMembership.Role.MEMBER)
        approver = self._user('a_approver', OrganizationMembership.Role.ADMIN)
        ar = self._approval(self._contract(creator), assigned_to=approver)
        self.svc.approve(ar.id, approver)
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.APPROVE,
                object_id=ar.id,
            ).exists()
        )

    def test_blocked_approval_is_audited(self):
        creator = self._user('b_author', OrganizationMembership.Role.OWNER)
        ar = self._approval(self._contract(creator), assigned_to=creator)
        with self.assertRaises(ApprovalAccessDenied):
            self.svc.approve(ar.id, creator)
        entry = AuditLog.objects.filter(action=AuditLog.Action.APPROVE, object_id=ar.id).first()
        self.assertIsNotNone(entry)
        self.assertIn('blocked', entry.changes.get('event', ''))
        # No sensitive comment text is copied into the audit metadata.
        self.assertNotIn('approving my own', json.dumps(entry.changes))
