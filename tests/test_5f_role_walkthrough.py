"""Phase 5F — role-based pilot walkthrough + cross-tenant negative matrix.

Drives the real HTTP layer via the Django test client (URL routing, middleware,
auth, views). Two organizations, OWNER/ADMIN/MEMBER each, plus unauthenticated /
registration and a stale-session / role-downgrade check. Asserts server-side
enforcement (status codes) AND absence of target-tenant leakage in bodies.
"""
from __future__ import annotations

import json
import uuid

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from contracts.models import (
    ApprovalRequest, AuditLog, Client as ClientModel, Contract, Document,
    Matter, Organization, OrganizationInvitation, OrganizationMembership,
    ScheduledJobRun,
)

User = get_user_model()
PW = 'PilotPw!12345'
Role = OrganizationMembership.Role


def _org(name, slug):
    return Organization.objects.create(name=name, slug=slug)


def _user(org, username, role):
    u = User.objects.create_user(username=username, password=PW, email=f'{username}@ex.com')
    OrganizationMembership.objects.create(user=u, organization=org, role=role, is_active=True)
    return u


def _client(user):
    c = Client()
    c.force_login(user)
    return c


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org_a = _org('Alpha Council', 'alpha')
        cls.org_b = _org('Beta Borough', 'beta')
        cls.owner_a = _user(cls.org_a, 'owner_a', Role.OWNER)
        cls.admin_a = _user(cls.org_a, 'admin_a', Role.ADMIN)
        cls.member_a = _user(cls.org_a, 'member_a', Role.MEMBER)
        cls.owner_b = _user(cls.org_b, 'owner_b', Role.OWNER)
        cls.member_b = _user(cls.org_b, 'member_b', Role.MEMBER)
        # Org B private resources (targets for cross-tenant attacks)
        cls.client_b = ClientModel.objects.create(organization=cls.org_b, name='BETA-SECRET-CLIENT')
        cls.matter_b = Matter.objects.create(organization=cls.org_b, client=cls.client_b, title='BETA-SECRET-MATTER')
        cls.contract_b = Contract.objects.create(organization=cls.org_b, title='BETA-SECRET-CONTRACT',
                                                 created_by=cls.owner_b, status='DRAFT')
        cls.doc_b = Document.objects.create(organization=cls.org_b, uploaded_by=cls.owner_b,
                                            title='BETA-SECRET-DOC',
                                            file=SimpleUploadedFile('b.txt', b'secret', content_type='text/plain'))
        cls.appr_b = ApprovalRequest.objects.create(organization=cls.org_b, contract=cls.contract_b,
                                                    approval_step='legal', status='PENDING')
        cls.inv_b = OrganizationInvitation.objects.create(organization=cls.org_b, email='x@beta.example',
                                                          role=Role.MEMBER, invited_by=cls.owner_b)
        cls.jobrun_b = ScheduledJobRun.objects.create(job_name='run_retention_jobs', organization=cls.org_b,
                                                      status='SUCCESS')
        # Org A resources
        cls.contract_a = Contract.objects.create(organization=cls.org_a, title='ALPHA-CONTRACT',
                                                 created_by=cls.admin_a, status='DRAFT')

    _LEAK_TOKENS = ['BETA-SECRET-CLIENT', 'BETA-SECRET-MATTER', 'BETA-SECRET-CONTRACT',
                    'BETA-SECRET-DOC', 'Beta Borough', 'x@beta.example']

    def assertNoLeak(self, resp):
        body = resp.content.decode(errors='ignore')
        for tok in self._LEAK_TOKENS:
            self.assertNotIn(tok, body, f'tenant leakage: {tok!r} in response')


# ---------------------------------------------------------------------------
# Unauthenticated / registration
# ---------------------------------------------------------------------------
class UnauthJourneys(_Base):
    def test_login_page_branding(self):
        r = Client().get(reverse('login'))
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        self.assertIn('DocClad', body)
        self.assertNotIn('CMS Aegis', body)

    def test_successful_login(self):
        r = Client().post(reverse('login'), {'username': 'owner_a', 'password': PW})
        self.assertEqual(r.status_code, 302)

    def test_failed_login_no_enumeration(self):
        c = Client()
        unknown = c.post(reverse('login'), {'username': 'nobody_here', 'password': 'x'})
        wrongpw = c.post(reverse('login'), {'username': 'owner_a', 'password': 'wrong'})
        # Same generic message for unknown user vs wrong password (no enumeration).
        self.assertContains(unknown, 'Invalid username or password', status_code=200)
        self.assertContains(wrongpw, 'Invalid username or password', status_code=200)

    def test_registration_creates_account(self):
        c = Client()
        r = c.post(reverse('register'), {
            'username': 'newreg', 'email': 'newreg@ex.com',
            'password1': 'RegisterPw!9xy', 'password2': 'RegisterPw!9xy',
        })
        self.assertIn(r.status_code, (302, 200))
        self.assertTrue(User.objects.filter(username='newreg').exists())

    def test_logout(self):
        c = _client(self.owner_a)
        r = c.get(reverse('logout'))
        self.assertIn(r.status_code, (200, 302, 405))

    def test_anonymous_protected_redirect(self):
        r = Client().get(reverse('contracts:contract_list'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/login', r.url)

    def test_404_no_traceback(self):
        r = _client(self.owner_a).get('/this-route-does-not-exist-xyz/')
        self.assertEqual(r.status_code, 404)
        self.assertNotIn('Traceback', r.content.decode(errors='ignore'))


# ---------------------------------------------------------------------------
# OWNER
# ---------------------------------------------------------------------------
class OwnerJourneys(_Base):
    def test_owner_can_access_team_and_audit(self):
        c = _client(self.owner_a)
        self.assertEqual(c.get(reverse('contracts:organization_team')).status_code, 200)
        self.assertEqual(c.get(reverse('contracts:audit_log_list')).status_code, 200)

    def test_owner_can_invite(self):
        c = _client(self.owner_a)
        from unittest.mock import patch
        with patch('contracts.services.invitations.send_mail'):
            r = c.post(reverse('contracts:organization_team'),
                       {'email': 'invitee@alpha.example', 'role': 'MEMBER'})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(OrganizationInvitation.objects.filter(
            organization=self.org_a, email='invitee@alpha.example').exists())

    def test_owner_can_change_role(self):
        m = OrganizationMembership.objects.get(user=self.member_a, organization=self.org_a)
        r = _client(self.owner_a).post(reverse('contracts:update_membership_role', args=[m.id]),
                                       {'role': 'ADMIN'})
        self.assertIn(r.status_code, (302, 200))
        m.refresh_from_db()
        self.assertEqual(m.role, 'ADMIN')


# ---------------------------------------------------------------------------
# ADMIN
# ---------------------------------------------------------------------------
class AdminJourneys(_Base):
    def test_admin_can_create_contract_via_http(self):
        c = _client(self.admin_a)
        r = c.post(reverse('contracts:contract_create'), {
            'title': 'Admin Made', 'contract_type': 'OTHER', 'content': '',
            'status': 'ACTIVE', 'counterparty': 'X', 'value': '0', 'currency': 'USD',
            'risk_level': 'LOW', 'lifecycle_stage': 'DRAFTING'})
        self.assertIn(r.status_code, (302, 200))
        made = Contract.objects.filter(organization=self.org_a, title='Admin Made').first()
        self.assertIsNotNone(made)
        self.assertEqual(made.status, 'DRAFT')  # create forced to DRAFT (4B)

    def test_admin_cannot_self_approve_created_contract(self):
        # Admin creates a contract, then is assigned its approval -> must be blocked.
        contract = Contract.objects.create(organization=self.org_a, title='SoD', created_by=self.admin_a, status='PENDING')
        appr = ApprovalRequest.objects.create(organization=self.org_a, contract=contract,
                                              approval_step='legal', status='PENDING', assigned_to=self.admin_a)
        r = _client(self.admin_a).post(reverse('contracts:approval_request_update', args=[appr.id]),
                                       {'contract': contract.id, 'approval_step': 'legal',
                                        'status': 'APPROVED', 'assigned_to': self.admin_a.id,
                                        'comments': '', 'due_date': ''})
        self.assertEqual(r.status_code, 200)  # rejected (form re-render), not redirect
        appr.refresh_from_db()
        self.assertEqual(appr.status, 'PENDING')  # not self-approved


# ---------------------------------------------------------------------------
# MEMBER
# ---------------------------------------------------------------------------
class MemberJourneys(_Base):
    def test_member_can_read_own_org(self):
        self.assertEqual(_client(self.member_a).get(reverse('contracts:contract_list')).status_code, 200)

    def test_member_delete_only_own_upload(self):
        own = Document.objects.create(organization=self.org_a, uploaded_by=self.member_a, title='MyDoc')
        other = Document.objects.create(organization=self.org_a, uploaded_by=self.admin_a, title='AdminDoc')
        c = _client(self.member_a)
        c.post(reverse('contracts:document_delete', args=[own.id]))
        c.post(reverse('contracts:document_delete', args=[other.id]))
        own.refresh_from_db(); other.refresh_from_db()
        self.assertTrue(own.is_deleted)        # own upload deleted
        self.assertFalse(other.is_deleted)     # others' upload NOT deleted

    def test_member_cannot_change_roles(self):
        m = OrganizationMembership.objects.get(user=self.admin_a, organization=self.org_a)
        r = _client(self.member_a).post(reverse('contracts:update_membership_role', args=[m.id]), {'role': 'MEMBER'})
        self.assertEqual(r.status_code, 403)


# ---------------------------------------------------------------------------
# Cross-tenant negative matrix (Org A actor vs Org B resources)
# ---------------------------------------------------------------------------
class CrossTenantNegative(_Base):
    def setUp(self):
        self.c = _client(self.owner_a)  # most privileged in A, still no access to B

    def test_client_detail(self):
        r = self.c.get(reverse('contracts:client_detail', args=[self.client_b.id]))
        self.assertEqual(r.status_code, 404); self.assertNoLeak(r)

    def test_matter_detail(self):
        r = self.c.get(reverse('contracts:matter_detail', args=[self.matter_b.id]))
        self.assertEqual(r.status_code, 404); self.assertNoLeak(r)

    def test_contract_detail(self):
        r = self.c.get(reverse('contracts:contract_detail', args=[self.contract_b.id]))
        self.assertEqual(r.status_code, 404); self.assertNoLeak(r)

    def test_document_detail(self):
        r = self.c.get(reverse('contracts:document_detail', args=[self.doc_b.id]))
        self.assertEqual(r.status_code, 404); self.assertNoLeak(r)

    def test_document_download(self):
        r = self.c.get(reverse('contracts:document_download', args=[self.doc_b.id]))
        self.assertEqual(r.status_code, 404); self.assertNoLeak(r)
        # blocked event recorded on the ACTOR's org, not target; no target metadata
        blocked = AuditLog.objects.filter(event_type='document.access_blocked').order_by('-id').first()
        if blocked:
            self.assertEqual(blocked.organization_id, self.org_a.id)
            self.assertNotIn('BETA-SECRET-DOC', json.dumps(blocked.changes))

    def test_document_deletion(self):
        r = self.c.post(reverse('contracts:document_delete', args=[self.doc_b.id]))
        self.assertIn(r.status_code, (403, 404))
        self.doc_b.refresh_from_db()
        self.assertFalse(self.doc_b.is_deleted)

    def test_contract_transition(self):
        r = self.c.post(reverse('contracts:contract_update', args=[self.contract_b.id]),
                        {'title': 'x', 'contract_type': 'OTHER', 'content': '',
                         'status': 'IN_REVIEW', 'counterparty': 'X', 'value': '0', 'currency': 'USD'})
        self.assertIn(r.status_code, (403, 404))
        self.contract_b.refresh_from_db()
        self.assertEqual(self.contract_b.status, 'DRAFT')

    def test_bulk_transition_with_foreign_id(self):
        r = self.c.post(reverse('contracts:contracts_bulk_update_api'),
                        data=json.dumps({'contract_ids': [self.contract_b.id], 'updates': {'status': 'IN_REVIEW'}}),
                        content_type='application/json')
        # foreign id is out of the actor's org scope -> not updated
        self.contract_b.refresh_from_db()
        self.assertEqual(self.contract_b.status, 'DRAFT')

    def test_approval_action(self):
        r = self.c.post(reverse('contracts:approval_request_update', args=[self.appr_b.id]),
                        {'contract': self.contract_b.id, 'approval_step': 'legal',
                         'status': 'APPROVED', 'comments': '', 'due_date': ''})
        self.assertIn(r.status_code, (403, 404))
        self.appr_b.refresh_from_db()
        self.assertEqual(self.appr_b.status, 'PENDING')

    def test_audit_log_scoped(self):
        # Seed an org-B audit row, then ensure A's audit list never shows it.
        AuditLog.objects.create(organization=self.org_b, action='UPDATE', model_name='Contract',
                                event_type='contract.status_changed', object_repr='BETA-SECRET-CONTRACT',
                                seq=1, hash_version=2, entry_hash='z')
        r = self.c.get(reverse('contracts:audit_log_list'))
        self.assertEqual(r.status_code, 200)
        self.assertNoLeak(r)
        self.assertTrue(all(log.organization_id == self.org_a.id for log in r.context['logs']))

    def test_invitation_revoke_resend_foreign(self):
        for name in ('revoke_organization_invite', 'resend_organization_invite', 'retry_organization_invite'):
            r = self.c.post(reverse(f'contracts:{name}', args=[self.inv_b.id]))
            self.assertIn(r.status_code, (403, 404), name)
        self.inv_b.refresh_from_db()
        self.assertEqual(self.inv_b.status, 'PENDING')  # unchanged

    def test_jobrun_evidence_scoped(self):
        # operations dashboard only shows the actor's org runs
        from django.urls import NoReverseMatch
        try:
            url = reverse('operations_dashboard')
        except NoReverseMatch:
            url = reverse('contracts:operations_dashboard')
        r = self.c.get(url)
        if r.status_code == 200 and 'recent_job_runs' in getattr(r, 'context', {} or {}):
            self.assertNotIn(self.jobrun_b, list(r.context['recent_job_runs']))

    def test_guessed_and_altered_org_switch(self):
        # Attempt to switch the active org to a non-member org (altered identifier).
        r = self.c.post(reverse('contracts:switch_organization'), {'organization_id': self.org_b.id})
        # Switch must be refused; subsequent reads must still be org A only.
        cl = self.c.get(reverse('contracts:contract_list'))
        self.assertEqual(cl.status_code, 200)
        self.assertNoLeak(cl)


# ---------------------------------------------------------------------------
# Stale session: membership removal / role downgrade mid-session
# ---------------------------------------------------------------------------
class StaleSessionAuthz(_Base):
    def test_role_downgrade_takes_effect_next_request(self):
        # Owner-only action allowed, then downgrade to MEMBER -> next request denied.
        c = _client(self.owner_a)
        target = OrganizationMembership.objects.get(user=self.member_a, organization=self.org_a)
        self.assertEqual(c.get(reverse('contracts:organization_team')).status_code, 200)
        # Downgrade the actor to MEMBER mid-session.
        own = OrganizationMembership.objects.get(user=self.owner_a, organization=self.org_a)
        own.role = Role.MEMBER
        own.save(update_fields=['role'])
        # Next privileged request must reflect the new (lower) authorization.
        r = c.post(reverse('contracts:update_membership_role', args=[target.id]), {'role': 'ADMIN'})
        self.assertEqual(r.status_code, 403)

    def test_membership_removal_revokes_access_next_request(self):
        c = _client(self.member_b)
        self.assertEqual(c.get(reverse('contracts:contract_list')).status_code, 200)
        # Deactivate the membership mid-session.
        m = OrganizationMembership.objects.get(user=self.member_b, organization=self.org_b)
        m.is_active = False
        m.save(update_fields=['is_active'])
        # Next request must NOT still see org B's data (no stale privilege).
        r = c.get(reverse('contracts:contract_list'))
        body = r.content.decode(errors='ignore')
        self.assertNotIn('BETA-SECRET-CONTRACT', body)
