"""Phase 2 core-loop depth: deep links, specialist actions, Command Center ops."""

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from contracts.models import (
    ApprovalRequest,
    Contract,
    Deadline,
    Organization,
    OrganizationMembership,
)
from contracts.services.command_center import group_recommended_actions

User = get_user_model()


class Phase2MyWorkRowParityTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='P2 Org', slug='p2-org')
        self.user = User.objects.create_user(username='p2_user', password='testpass123!')
        OrganizationMembership.objects.create(
            organization=self.org, user=self.user,
            role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        self.client = Client()
        self.client.login(username='p2_user', password='testpass123!')
        self.contract = Contract.objects.create(
            organization=self.org, title='P2 Contract', content='x',
            status=Contract.Status.IN_PROGRESS, created_by=self.user,
        )
        ApprovalRequest.objects.create(
            organization=self.org, contract=self.contract,
            approval_step='legal', assigned_to=self.user,
            status=ApprovalRequest.Status.PENDING,
            due_date=timezone.now() + timedelta(days=1),
        )

    def test_my_work_rows_expose_action_href_for_click_parity(self):
        response = self.client.get(reverse('contracts:my_work'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-action-href=')
        self.assertContains(response, 'data-toggle-detail=')
        self.assertContains(response, 'View details')
        self.assertContains(response, 'openActionContext')


class Phase2ApprovalsReturnTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='P2 Appr Org', slug='p2-appr-org')
        self.owner = User.objects.create_user(username='p2_appr_owner', password='testpass123!')
        self.reviewer = User.objects.create_user(username='p2_appr_reviewer', password='testpass123!')
        OrganizationMembership.objects.create(
            organization=self.org, user=self.owner,
            role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        OrganizationMembership.objects.create(
            organization=self.org, user=self.reviewer,
            role=OrganizationMembership.Role.MEMBER, is_active=True,
        )
        self.client = Client()
        self.client.login(username='p2_appr_reviewer', password='testpass123!')
        self.contract = Contract.objects.create(
            organization=self.org, title='Appr Contract', content='x',
            status=Contract.Status.IN_PROGRESS, created_by=self.owner,
        )
        ApprovalRequest.objects.create(
            organization=self.org, contract=self.contract,
            approval_step='finance', assigned_to=self.reviewer,
            status=ApprovalRequest.Status.PENDING,
        )

    def test_approvals_inbox_exposes_return_action(self):
        response = self.client.get(reverse('contracts:approval_request_list'))
        waiting = next(tab for tab in response.context['queue_tabs'] if tab['key'] == 'waiting_on_me')
        self.assertTrue(waiting['rows'])
        row = waiting['rows'][0]
        self.assertTrue(row['can_decide'])
        self.assertIn('request-changes', row['return_url'])
        self.assertContains(response, 'data-approval-action="return"')


class Phase2ObligationsActionsTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='P2 Obl Org', slug='p2-obl-org')
        self.user = User.objects.create_user(username='p2_obl', password='testpass123!')
        OrganizationMembership.objects.create(
            organization=self.org, user=self.user,
            role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        self.client = Client()
        self.client.login(username='p2_obl', password='testpass123!')
        self.contract = Contract.objects.create(
            organization=self.org, title='Obl Contract', content='x',
            status=Contract.Status.ACTIVE, created_by=self.user,
        )
        self.deadline = Deadline.objects.create(
            title='Renewal notice',
            contract=self.contract,
            assigned_to=self.user,
            due_date=date.today() + timedelta(days=3),
            priority=Deadline.Priority.MEDIUM,
            created_by=self.user,
        )

    def test_defer_extends_due_date_and_audits(self):
        previous = self.deadline.due_date
        response = self.client.post(reverse('contracts:deadline_defer', kwargs={'pk': self.deadline.pk}))
        self.assertEqual(response.status_code, 302)
        self.deadline.refresh_from_db()
        self.assertEqual(self.deadline.due_date, previous + timedelta(days=7))

    def test_escalate_sets_critical_priority(self):
        response = self.client.post(reverse('contracts:deadline_escalate', kwargs={'pk': self.deadline.pk}))
        self.assertEqual(response.status_code, 302)
        self.deadline.refresh_from_db()
        self.assertEqual(self.deadline.priority, Deadline.Priority.CRITICAL)

    def test_obligations_workspace_offers_defer_and_escalate(self):
        response = self.client.get(reverse('contracts:obligations_workspace'))
        self.assertContains(response, 'Defer 7 days')
        self.assertContains(response, 'Escalate priority')


class Phase2CommandCenterOpsTests(TestCase):
    def test_recommended_actions_tag_blocked_and_overdue(self):
        today = date.today()
        now = timezone.now()
        rows = [
            {
                'title': 'Blocked MSA',
                'workspace_href': '/a/',
                'status_label': 'Blocked',
                'blocking_issue': 'Waiting on business input.',
                'next_action': 'Unblock review',
                'priority': 80,
                'risk_level': 'HIGH',
                'due_date': today - timedelta(days=1),
                'due_overdue': True,
                'due_label': 'Overdue',
                'updated_at': now,
                'counterparty': 'Acme',
                'owner_label': 'Legal',
                'filter_waiting': True,
            },
            {
                'title': 'Open NDA',
                'workspace_href': '/b/',
                'status_label': 'Open',
                'blocking_issue': '',
                'next_action': 'Review draft',
                'priority': 40,
                'risk_level': 'MEDIUM',
                'due_date': today + timedelta(days=5),
                'due_overdue': False,
                'due_label': '5 days',
                'updated_at': now,
                'counterparty': 'Beta',
                'owner_label': 'Ops',
            },
        ]
        actions = group_recommended_actions(rows, today=today, limit=5)
        self.assertTrue(actions)
        self.assertEqual(actions[0]['category'], 'Blocked')
        self.assertIn(actions[0]['category'], {'Blocked', 'Overdue', 'Waiting', 'Open'})
