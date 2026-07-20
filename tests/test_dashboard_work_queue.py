"""Tests for the Dashboard/work-queue conversion (WorkQueue foundation block).

Covers: role-gated rendering, queue rows free of raw enums/ISO timestamps/
model names, the onboarding/queue empty-state gate, and the three reusable
components (StageDots, AssigneeChip, ActivityLine).
"""
import re

from django.contrib.auth.models import User
from django.template import Context, Template
from django.test import Client, TestCase
from django.urls import reverse

from contracts.middleware import log_action
from contracts.models import (
    ApprovalRequest,
    AuditLog,
    Contract,
    Deadline,
    Organization,
    OrganizationMembership,
)
from contracts.tenancy import get_user_organization

ISO_TIMESTAMP_RE = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}')


def dashboard_body(html):
    """The actual rendered page, excluding Django Debug Toolbar's panels.

    DEBUG=True in the test environment means every response carries DjDT's
    own markup, including a raw dump of the full template context (so
    strings like 'In Progress' or 'IN_REVIEW' can appear there even when the
    real page body never rendered them). Assertions about what the page
    actually shows a user must be scoped to the body, not the DjDT sidebar.
    """
    start = html.find('CLMOneDashboard')
    end = html.find('id="djDebug"')
    if start == -1:
        return html
    return html[start:end] if end != -1 else html[start:]


class DashboardRoleRenderingTests(TestCase):
    """Any active org member — owner, admin, or plain member — can load the
    workflow queue dashboard; the view has no extra role gate beyond auth +
    org membership."""

    def setUp(self):
        self.organization = Organization.objects.create(name='Role Firm', slug='role-firm')

    def _client_for_role(self, role, username):
        user = User.objects.create_user(username=username, password='testpass123', email=f'{username}@example.com')
        OrganizationMembership.objects.create(organization=self.organization, user=user, role=role, is_active=True)
        client = Client()
        client.login(username=username, password='testpass123')
        return client

    def test_dashboard_renders_for_owner(self):
        client = self._client_for_role(OrganizationMembership.Role.OWNER, 'owner_user')
        response = client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_dashboard_renders_for_admin(self):
        client = self._client_for_role(OrganizationMembership.Role.ADMIN, 'admin_user')
        response = client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_dashboard_renders_for_member(self):
        client = self._client_for_role(OrganizationMembership.Role.MEMBER, 'member_user')
        response = client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)


class DashboardEmptyStateTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='emptyuser', password='testpass123', email='empty@example.com')
        self.client.login(username='emptyuser', password='testpass123')
        organization = get_user_organization(self.user)
        organization.workspace_mode = Organization.WorkspaceMode.IN_HOUSE_CLM
        organization.save(update_fields=['workspace_mode'])

    def test_onboarding_checklist_shown_when_no_data(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        body = dashboard_body(response.content.decode())
        self.assertIn('Establish your contract portfolio', body)
        self.assertIn('Health score unavailable', body)
        self.assertIn('Add first contract', body)
        self.assertIn('Risk findings', body)
        self.assertIn('Configure deadlines', body)

    def test_onboarding_checklist_hidden_once_a_contract_exists(self):
        organization = get_user_organization(self.user)
        Contract.objects.create(
            organization=organization,
            title='First Contract',
            content='Seed content',
            status='IN_PROGRESS',
            created_by=self.user,
        )
        response = self.client.get(reverse('dashboard'))
        self.assertNotContains(response, 'Set up contract operations')
        self.assertContains(response, 'Command Center')
        self.assertContains(response, 'Recent Matters')


class DashboardQueueRowContentTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='queueuser', password='testpass123', email='queue@example.com')
        self.client.login(username='queueuser', password='testpass123')
        self.organization = get_user_organization(self.user)

    def test_queue_rows_render_without_raw_enums_iso_timestamps_or_model_names(self):
        contract = Contract.objects.create(
            organization=self.organization,
            title='Raw Value Check Contract',
            content='Seed content',
            status='IN_PROGRESS',
            lifecycle_stage='NEGOTIATION',
            created_by=self.user,
        )
        Deadline.objects.create(
            title='Countersign the amendment',
            deadline_type='CONTRACT',
            contract=contract,
            assigned_to=self.user,
            due_date='2026-08-01',
        )
        ApprovalRequest.objects.create(
            organization=self.organization,
            contract=contract,
            approval_step='LEGAL',
            status='PENDING',
            assigned_to=self.user,
        )
        log_action(
            self.user, 'UPDATE', 'Contract', contract.id, str(contract),
            changes={'event': 'contract_updated'}, organization=self.organization,
        )

        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        html = dashboard_body(response.content.decode())

        # Human-readable stage labels only — never the raw TextChoices key.
        # The queue's Stage column shows the simplified lifecycle_stage chip
        # (NEGOTIATION -> "Legal Review"), not the Contract.status field.
        self.assertNotIn('IN_REVIEW', html)
        self.assertNotIn('IN_PROGRESS', html)
        self.assertNotIn('NEGOTIATION', html)
        self.assertIn('Legal Review', html)

        # No raw Python/ORM model class names leaking into the UI.
        for raw_name in ('ApprovalRequest', 'WorkflowStep', 'DSARRequest', 'CaseSignal'):
            self.assertNotIn(raw_name, html)

        # No machine ISO-8601 timestamps in visible copy.
        self.assertIsNone(ISO_TIMESTAMP_RE.search(html), 'Found a raw ISO timestamp in the dashboard response')

        # The contract and its assignee-carrying rows are present.
        self.assertIn('Raw Value Check Contract', html)
        self.assertIn('Countersign the amendment', html)

    def test_waiting_on_me_row_shows_assignee_and_due_date_for_current_user(self):
        contract = Contract.objects.create(
            organization=self.organization,
            title='Assigned To Me Contract',
            content='Seed content',
            status='IN_PROGRESS',
            created_by=self.user,
        )
        ApprovalRequest.objects.create(
            organization=self.organization,
            contract=contract,
            approval_step='FINANCE',
            status='PENDING',
            assigned_to=self.user,
        )
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'Assigned To Me Contract')
        # The signed-in user's own name/initial renders via AssigneeChip.
        self.assertContains(response, self.user.username)


class StageDotsComponentTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Stage Firm', slug='stage-firm')
        self.user = User.objects.create_user(username='stageuser', password='testpass123', email='stage@example.com')

    def _render(self, contract):
        return Template('{% load clmone_components %}{% stage_dots contract %}').render(Context({'contract': contract}))

    def test_stage_dots_marks_current_lifecycle_stage(self):
        contract = Contract.objects.create(
            organization=self.organization,
            title='Negotiation Contract',
            content='Seed content',
            status='IN_PROGRESS',
            lifecycle_stage='NEGOTIATION',
            created_by=self.user,
        )
        rendered = self._render(contract)
        self.assertIn('stage-dot-current', rendered)
        self.assertIn('Negotiation', rendered)

    def test_stage_dots_renders_placeholder_without_a_contract(self):
        rendered = self._render(None)
        self.assertIn('—', rendered)
        self.assertNotIn('stage-dot', rendered)


class AssigneeChipComponentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='chipuser', password='testpass123', email='chip@example.com', first_name='Priya',
        )

    def _render(self, user):
        return Template('{% load clmone_components %}{% assignee_chip user %}').render(Context({'user': user}))

    def test_assignee_chip_shows_assigned_user(self):
        rendered = self._render(self.user)
        self.assertIn('Priya', rendered)
        self.assertNotIn('Unassigned', rendered)

    def test_assignee_chip_shows_unassigned_placeholder(self):
        rendered = self._render(None)
        self.assertIn('Unassigned', rendered)


class ActivityLineComponentTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Activity Firm', slug='activity-firm')
        self.user = User.objects.create_user(
            username='activityuser', password='testpass123', email='activity@example.com', first_name='Sam',
        )

    def _render(self, log):
        return Template('{% load clmone_components %}{% activity_line log %}').render(Context({'log': log}))

    def test_activity_line_renders_human_readable_entry(self):
        contract = Contract.objects.create(
            organization=self.organization,
            title='Activity Contract',
            content='Seed content',
            status='ACTIVE',
            created_by=self.user,
        )
        log = log_action(
            self.user, 'UPDATE', 'Contract', contract.id, str(contract),
            changes={'event': 'contract_updated'}, organization=self.organization,
        )
        rendered = self._render(log)
        self.assertIn('Sam', rendered)
        self.assertIn('contract', rendered)
        self.assertNotIn('UPDATE', rendered)  # human label ("updated"), not the raw enum

    def test_activity_line_renders_placeholder_when_missing(self):
        rendered = self._render(None)
        self.assertIn('No recent activity', rendered)
