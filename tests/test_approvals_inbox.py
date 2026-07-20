"""Tests for the Approvals Inbox conversion (WorkQueue foundation block).

Covers: role-gated rendering, per-tab filtering correctness, the reusable
StageDots/AssigneeChip/ActivityLine components on approval rows, real
approve/reject actions reusing the existing authorized/audited API
endpoints, safety against repeated invalid transitions, cross-tenant
isolation, and copy free of raw enums/ISO timestamps/model names.
"""
import json
import re

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from contracts.models import (
    ApprovalRequest,
    AuditLog,
    Contract,
    Organization,
    OrganizationMembership,
)
from contracts.tenancy import get_user_organization

ISO_TIMESTAMP_RE = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}')


def approvals_body(html):
    """The main Approvals content region only — excludes both the sidebar
    nav (which has its own unrelated 'RISK & COMPLIANCE' nav-section label
    that collides with ApprovalRequest.approval_step's 'COMPLIANCE' value)
    and Django Debug Toolbar's panels (DEBUG=True dumps the full template
    context, so raw values can appear there even when the real page body
    never renders them).

    Anchored on the stable `id="approvals-root"` marker rather than a class
    string — the class list on that element is the canonical list scaffold
    plus the route marker, and shell-convergence tests exercise it directly.
    This helper must not depend on its exact contents or order.
    """
    start = html.find('id="approvals-root"')
    end = html.find('id="djDebug"')
    if start == -1:
        return html
    return html[start:end] if end != -1 else html[start:]


class ApprovalsRoleRenderingTests(TestCase):
    """Any active org member can load the Approvals inbox; no extra role gate."""

    def setUp(self):
        self.organization = Organization.objects.create(name='Role Firm', slug='approvals-role-firm')

    def _client_for_role(self, role, username):
        user = User.objects.create_user(username=username, password='testpass123', email=f'{username}@example.com')
        OrganizationMembership.objects.create(organization=self.organization, user=user, role=role, is_active=True)
        client = Client()
        client.login(username=username, password='testpass123')
        return client

    def test_approvals_renders_for_owner(self):
        client = self._client_for_role(OrganizationMembership.Role.OWNER, 'approvals_owner')
        response = client.get(reverse('contracts:approval_request_list'))
        self.assertEqual(response.status_code, 200)

    def test_approvals_renders_for_admin(self):
        client = self._client_for_role(OrganizationMembership.Role.ADMIN, 'approvals_admin')
        response = client.get(reverse('contracts:approval_request_list'))
        self.assertEqual(response.status_code, 200)

    def test_approvals_renders_for_member(self):
        client = self._client_for_role(OrganizationMembership.Role.MEMBER, 'approvals_member')
        response = client.get(reverse('contracts:approval_request_list'))
        self.assertEqual(response.status_code, 200)


class ApprovalsQueueTabFilteringTests(TestCase):
    """Each saved-view tab must contain exactly the rows its label promises."""

    def setUp(self):
        self.organization = Organization.objects.create(name='Tab Firm', slug='approvals-tab-firm')
        self.requester = User.objects.create_user(username='tab_requester', password='testpass123', email='req@example.com')
        self.assignee = User.objects.create_user(username='tab_assignee', password='testpass123', email='assignee@example.com')
        self.other = User.objects.create_user(username='tab_other', password='testpass123', email='other@example.com')
        for u in (self.requester, self.assignee, self.other):
            OrganizationMembership.objects.create(organization=self.organization, user=u, role=OrganizationMembership.Role.MEMBER, is_active=True)

        self.contract = Contract.objects.create(
            organization=self.organization, title='Tab Contract', content='Seed', status='IN_PROGRESS',
            created_by=self.requester,
        )

        self.waiting = ApprovalRequest.objects.create(
            organization=self.organization, contract=self.contract, approval_step='LEGAL',
            status='PENDING', assigned_to=self.assignee,
        )
        self.approved = ApprovalRequest.objects.create(
            organization=self.organization, contract=self.contract, approval_step='FINANCE',
            status='APPROVED', assigned_to=self.assignee,
        )
        self.rejected = ApprovalRequest.objects.create(
            organization=self.organization, contract=self.contract, approval_step='PRIVACY',
            status='REJECTED', assigned_to=self.assignee,
        )
        self.escalated = ApprovalRequest.objects.create(
            organization=self.organization, contract=self.contract, approval_step='EXECUTIVE',
            status='ESCALATED', assigned_to=self.other,
        )
        self.overdue = ApprovalRequest.objects.create(
            organization=self.organization, contract=self.contract, approval_step='COMPLIANCE',
            status='PENDING', assigned_to=self.other, due_date=timezone.now() - timezone.timedelta(days=2),
        )

        self.client = Client()
        self.client.login(username='tab_assignee', password='testpass123')

    def _tab(self, response, key):
        tabs = response.context['queue_tabs']
        return next(t for t in tabs if t['key'] == key)

    def test_waiting_on_me_only_shows_approvals_assigned_to_current_user(self):
        response = self.client.get(reverse('contracts:approval_request_list'))
        ids = [r['id'] for r in self._tab(response, 'waiting_on_me')['rows']]
        self.assertIn(self.waiting.id, ids)
        self.assertNotIn(self.escalated.id, ids)
        self.assertNotIn(self.overdue.id, ids)
        self.assertNotIn(self.approved.id, ids)

    def test_requested_by_me_only_shows_approvals_for_contracts_current_user_created(self):
        client = Client()
        client.login(username='tab_requester', password='testpass123')
        response = client.get(reverse('contracts:approval_request_list'))
        ids = [r['id'] for r in self._tab(response, 'requested_by_me')['rows']]
        for ar in (self.waiting, self.approved, self.rejected, self.escalated, self.overdue):
            self.assertIn(ar.id, ids)

        response_other = self.client.get(reverse('contracts:approval_request_list'))
        ids_other = [r['id'] for r in self._tab(response_other, 'requested_by_me')['rows']]
        self.assertEqual(ids_other, [])

    def test_all_open_shows_pending_and_escalated_only(self):
        response = self.client.get(reverse('contracts:approval_request_list'))
        ids = [r['id'] for r in self._tab(response, 'all_open')['rows']]
        self.assertIn(self.waiting.id, ids)
        self.assertIn(self.escalated.id, ids)
        self.assertIn(self.overdue.id, ids)
        self.assertNotIn(self.approved.id, ids)
        self.assertNotIn(self.rejected.id, ids)

    def test_approved_tab_shows_only_approved(self):
        response = self.client.get(reverse('contracts:approval_request_list'))
        ids = [r['id'] for r in self._tab(response, 'approved')['rows']]
        self.assertEqual(ids, [self.approved.id])

    def test_rejected_tab_shows_only_rejected(self):
        response = self.client.get(reverse('contracts:approval_request_list'))
        ids = [r['id'] for r in self._tab(response, 'rejected')['rows']]
        self.assertEqual(ids, [self.rejected.id])

    def test_escalated_or_overdue_tab_shows_escalated_and_overdue_pending(self):
        response = self.client.get(reverse('contracts:approval_request_list'))
        ids = [r['id'] for r in self._tab(response, 'escalated_overdue')['rows']]
        self.assertIn(self.escalated.id, ids)
        self.assertIn(self.overdue.id, ids)
        self.assertNotIn(self.waiting.id, ids)
        self.assertNotIn(self.approved.id, ids)
        self.assertNotIn(self.rejected.id, ids)


class ApprovalsRowComponentTests(TestCase):
    """Approval rows reuse StageDots/AssigneeChip/ActivityLine, not bespoke markup."""

    def setUp(self):
        self.organization = Organization.objects.create(name='Row Firm', slug='approvals-row-firm')
        self.user = User.objects.create_user(username='row_user', password='testpass123', email='row@example.com', first_name='Rowan')
        OrganizationMembership.objects.create(organization=self.organization, user=self.user, role=OrganizationMembership.Role.MEMBER, is_active=True)
        self.client = Client()
        self.client.login(username='row_user', password='testpass123')

    def test_row_renders_stage_dots_assignee_chip_and_activity_line(self):
        contract = Contract.objects.create(
            organization=self.organization, title='Component Row Contract', content='Seed',
            status='IN_PROGRESS', lifecycle_stage='NEGOTIATION', created_by=self.user,
        )
        ar = ApprovalRequest.objects.create(
            organization=self.organization, contract=contract, approval_step='LEGAL',
            status='PENDING', assigned_to=self.user,
        )
        from contracts.middleware import log_action
        log_action(
            self.user, 'CREATE', 'ApprovalRequest', ar.id, str(ar),
            changes={'event': 'approval_created'}, organization=self.organization,
        )

        response = self.client.get(reverse('contracts:approval_request_list'))
        body = approvals_body(response.content.decode())
        self.assertIn('stage-dot-current', body)
        self.assertIn('Negotiation', body)
        self.assertIn('Rowan', body)
        self.assertIn('Component Row Contract', body)


class ApprovalsActionEligibilityTests(TestCase):
    """Approve/Reject buttons are eligible-only; the API stays the enforcement boundary."""

    def setUp(self):
        self.organization = Organization.objects.create(name='Action Firm', slug='approvals-action-firm')
        self.creator = User.objects.create_user(username='action_creator', password='testpass123', email='creator@example.com')
        self.assignee = User.objects.create_user(username='action_assignee', password='testpass123', email='assignee2@example.com')
        self.bystander = User.objects.create_user(username='action_bystander', password='testpass123', email='bystander@example.com')
        for u in (self.creator, self.assignee, self.bystander):
            OrganizationMembership.objects.create(organization=self.organization, user=u, role=OrganizationMembership.Role.MEMBER, is_active=True)

        self.contract = Contract.objects.create(
            organization=self.organization, title='Action Contract', content='Seed', status='IN_PROGRESS',
            created_by=self.creator,
        )
        self.ar = ApprovalRequest.objects.create(
            organization=self.organization, contract=self.contract, approval_step='LEGAL',
            status='PENDING', assigned_to=self.assignee,
        )

    def test_eligible_assignee_sees_approve_and_reject_buttons(self):
        client = Client()
        client.login(username='action_assignee', password='testpass123')
        response = client.get(reverse('contracts:approval_request_list'))
        body = approvals_body(response.content.decode())
        self.assertIn('data-approval-action="approve"', body)
        self.assertIn('data-approval-action="reject"', body)

    def test_already_decided_row_never_shows_decide_buttons_even_for_eligible_actor(self):
        """An eligible actor (assignee or admin) must not see live Approve/Reject
        buttons on a row that can no longer be decided — the API's own status
        guard would reject the attempt, so showing the buttons would be a
        control that always fails."""
        self.ar.status = 'APPROVED'
        self.ar.save(update_fields=['status'])
        client = Client()
        client.login(username='action_assignee', password='testpass123')
        response = client.get(reverse('contracts:approval_request_list'))
        tabs = response.context['queue_tabs']
        row = next(r for t in tabs for r in t['rows'] if r['id'] == self.ar.id)
        self.assertFalse(row['can_decide'])
        body = approvals_body(response.content.decode())
        self.assertNotIn('data-approval-action="approve"', body)
        self.assertNotIn('data-approval-action="reject"', body)

    def test_contract_creator_does_not_see_decide_buttons_segregation_of_duties(self):
        client = Client()
        client.login(username='action_creator', password='testpass123')
        response = client.get(reverse('contracts:approval_request_list'))
        body = approvals_body(response.content.decode())
        self.assertNotIn('data-approval-action="approve"', body)
        self.assertNotIn('data-approval-action="reject"', body)

    def test_bystander_does_not_see_decide_buttons(self):
        client = Client()
        client.login(username='action_bystander', password='testpass123')
        response = client.get(reverse('contracts:approval_request_list'))
        body = approvals_body(response.content.decode())
        self.assertNotIn('data-approval-action="approve"', body)
        self.assertNotIn('data-approval-action="reject"', body)

    def test_every_row_keeps_an_edit_link_regardless_of_decide_eligibility(self):
        client = Client()
        client.login(username='action_bystander', password='testpass123')
        response = client.get(reverse('contracts:approval_request_list'))
        body = approvals_body(response.content.decode())
        self.assertIn(reverse('contracts:approval_request_update', kwargs={'pk': self.ar.pk}), body)

    def test_eligible_assignee_can_approve_via_the_existing_api(self):
        client = Client()
        client.login(username='action_assignee', password='testpass123')
        response = client.post(
            reverse('contracts:approval_approve_api', kwargs={'approval_id': self.ar.pk}),
            data=json.dumps({'comments': ''}), content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.ar.refresh_from_db()
        self.assertEqual(self.ar.status, 'APPROVED')

    def test_eligible_assignee_can_reject_via_the_existing_api(self):
        client = Client()
        client.login(username='action_assignee', password='testpass123')
        response = client.post(
            reverse('contracts:approval_reject_api', kwargs={'approval_id': self.ar.pk}),
            data=json.dumps({'comments': 'Needs revision'}), content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.ar.refresh_from_db()
        self.assertEqual(self.ar.status, 'REJECTED')

    def test_unauthorized_bystander_cannot_approve_via_direct_post(self):
        client = Client()
        client.login(username='action_bystander', password='testpass123')
        response = client.post(
            reverse('contracts:approval_approve_api', kwargs={'approval_id': self.ar.pk}),
            data=json.dumps({'comments': ''}), content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        self.ar.refresh_from_db()
        self.assertEqual(self.ar.status, 'PENDING')

    def test_contract_creator_cannot_approve_via_direct_post_segregation_of_duties(self):
        client = Client()
        client.login(username='action_creator', password='testpass123')
        response = client.post(
            reverse('contracts:approval_approve_api', kwargs={'approval_id': self.ar.pk}),
            data=json.dumps({'comments': ''}), content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        self.ar.refresh_from_db()
        self.assertEqual(self.ar.status, 'PENDING')

    def test_repeated_invalid_transition_fails_safely(self):
        client = Client()
        client.login(username='action_assignee', password='testpass123')
        first = client.post(
            reverse('contracts:approval_approve_api', kwargs={'approval_id': self.ar.pk}),
            data=json.dumps({'comments': ''}), content_type='application/json',
        )
        self.assertEqual(first.status_code, 200)

        second = client.post(
            reverse('contracts:approval_approve_api', kwargs={'approval_id': self.ar.pk}),
            data=json.dumps({'comments': ''}), content_type='application/json',
        )
        self.assertEqual(second.status_code, 400)
        self.ar.refresh_from_db()
        self.assertEqual(self.ar.status, 'APPROVED')

        third = client.post(
            reverse('contracts:approval_reject_api', kwargs={'approval_id': self.ar.pk}),
            data=json.dumps({'comments': ''}), content_type='application/json',
        )
        self.assertEqual(third.status_code, 400)
        self.ar.refresh_from_db()
        self.assertEqual(self.ar.status, 'APPROVED')

    def test_approve_decision_is_audit_logged(self):
        client = Client()
        client.login(username='action_assignee', password='testpass123')
        client.post(
            reverse('contracts:approval_approve_api', kwargs={'approval_id': self.ar.pk}),
            data=json.dumps({'comments': ''}), content_type='application/json',
        )
        entry = AuditLog.objects.filter(model_name='ApprovalRequest', object_id=self.ar.pk).order_by('-timestamp').first()
        self.assertIsNotNone(entry)
        self.assertEqual((entry.changes or {}).get('event'), 'approval_approve_succeeded')

    def test_blocked_approve_attempt_is_also_audit_logged(self):
        client = Client()
        client.login(username='action_bystander', password='testpass123')
        client.post(
            reverse('contracts:approval_approve_api', kwargs={'approval_id': self.ar.pk}),
            data=json.dumps({'comments': ''}), content_type='application/json',
        )
        entry = AuditLog.objects.filter(model_name='ApprovalRequest', object_id=self.ar.pk).order_by('-timestamp').first()
        self.assertIsNotNone(entry)
        self.assertEqual((entry.changes or {}).get('event'), 'approval_approve_blocked')


class ApprovalsCrossTenantIsolationTests(TestCase):
    def setUp(self):
        self.org_a = Organization.objects.create(name='Org A', slug='approvals-org-a')
        self.org_b = Organization.objects.create(name='Org B', slug='approvals-org-b')
        self.user_a = User.objects.create_user(username='iso_user_a', password='testpass123', email='a@example.com')
        self.user_b = User.objects.create_user(username='iso_user_b', password='testpass123', email='b@example.com')
        OrganizationMembership.objects.create(organization=self.org_a, user=self.user_a, role=OrganizationMembership.Role.MEMBER, is_active=True)
        OrganizationMembership.objects.create(organization=self.org_b, user=self.user_b, role=OrganizationMembership.Role.MEMBER, is_active=True)

        self.contract_a = Contract.objects.create(
            organization=self.org_a, title='Org A Contract', content='Seed', status='IN_PROGRESS', created_by=self.user_a,
        )
        self.ar_a = ApprovalRequest.objects.create(
            organization=self.org_a, contract=self.contract_a, approval_step='LEGAL', status='PENDING', assigned_to=self.user_a,
        )

    def test_other_org_member_does_not_see_approval_in_any_tab(self):
        client = Client()
        client.login(username='iso_user_b', password='testpass123')
        response = client.get(reverse('contracts:approval_request_list'))
        for tab in response.context['queue_tabs']:
            ids = [r['id'] for r in tab['rows']]
            self.assertNotIn(self.ar_a.id, ids)

    def test_other_org_member_cannot_approve_via_direct_post_gets_404(self):
        client = Client()
        client.login(username='iso_user_b', password='testpass123')
        response = client.post(
            reverse('contracts:approval_approve_api', kwargs={'approval_id': self.ar_a.pk}),
            data=json.dumps({'comments': ''}), content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)


class ApprovalsCopyQualityTests(TestCase):
    """No raw enums, ISO timestamps, ORM names, or placeholder labels leak into the inbox."""

    def setUp(self):
        self.organization = Organization.objects.create(name='Copy Firm', slug='approvals-copy-firm')
        self.user = User.objects.create_user(username='copy_user', password='testpass123', email='copy@example.com')
        OrganizationMembership.objects.create(organization=self.organization, user=self.user, role=OrganizationMembership.Role.MEMBER, is_active=True)
        self.client = Client()
        self.client.login(username='copy_user', password='testpass123')

    def test_no_raw_internals_leak_into_the_page(self):
        contract = Contract.objects.create(
            organization=self.organization, title='Copy Quality Contract', content='Seed',
            status='IN_PROGRESS', created_by=self.user,
        )
        ApprovalRequest.objects.create(
            organization=self.organization, contract=contract, approval_step='COMPLIANCE',
            status='ESCALATED', assigned_to=self.user, due_date=timezone.now() - timezone.timedelta(days=1),
        )
        response = self.client.get(reverse('contracts:approval_request_list'))
        body = approvals_body(response.content.decode())

        self.assertNotIn('ApprovalRequest', body)
        self.assertNotIn('COMPLIANCE', body)
        self.assertIn('Compliance Review', body)
        self.assertNotIn('ESCALATED', body)
        self.assertIsNone(ISO_TIMESTAMP_RE.search(body), 'Found a raw ISO timestamp in the Approvals response')

    def test_empty_states_render_exact_specified_copy(self):
        response = self.client.get(reverse('contracts:approval_request_list'))
        body = approvals_body(response.content.decode())
        self.assertIn('No approvals waiting on you.', body)
        self.assertIn('No approvals requested by you.', body)
        self.assertIn('No open approvals.', body)
        self.assertIn('No approved approvals yet.', body)
        self.assertIn('No rejected approvals.', body)
        self.assertIn('Nothing escalated or overdue.', body)


class ApprovalsShellConvergenceTests(TestCase):
    """Approvals must use the canonical list scaffold, not a private page
    recipe or a legacy page-wrap/architecture-header composition."""

    def setUp(self):
        self.organization = Organization.objects.create(name='Shell Firm', slug='approvals-shell-firm')
        self.user = User.objects.create_user(username='shell_user', password='testpass123', email='shell@example.com')
        OrganizationMembership.objects.create(organization=self.organization, user=self.user, role=OrganizationMembership.Role.MEMBER, is_active=True)
        self.client = Client()
        self.client.login(username='shell_user', password='testpass123')

    def test_uses_shared_list_scaffold(self):
        response = self.client.get(reverse('contracts:approval_request_list'))
        html = response.content.decode()
        self.assertIn('dc-ds-page--wide', html)
        self.assertIn('dc-ds-page-flow', html)
        self.assertIn('dc-ds-list-page', html)
        self.assertIn('approvals-page', html)
        self.assertIn('>Next action</th>', html)

    def test_no_longer_defines_its_own_private_shell_dimensions(self):
        response = self.client.get(reverse('contracts:approval_request_list'))
        html = response.content.decode()
        # The old duplicate shell hardcoded these exact values locally —
        # asserting they're gone proves the page no longer competes with a
        # private recipe for "what is the page shell".
        self.assertNotIn('.approvals-page { max-width', html)
        self.assertNotIn('max-width: 1480px', html)

    def test_uses_shared_list_header_pattern(self):
        response = self.client.get(reverse('contracts:approval_request_list'))
        html = response.content.decode()
        self.assertIn('clm-list-shell', html)
        self.assertIn('dc-ds-list-toolbar', html)
        self.assertIn('topbar-page-title">Reviews &amp; Approvals', html)
        self.assertIn('clm-list-view-tabs', html)
        self.assertIn('approvals-queue-chip', html)
        self.assertIn('aria-label="Approval queue filters"', html)
        self.assertNotIn('approvals-queue-tabs', html)
