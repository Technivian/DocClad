"""Phase 7 — priority reason visible on every work queue."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from contracts.models import (
    ApprovalRequest,
    Contract,
    Deadline,
    LegalTask,
    Organization,
    OrganizationMembership,
)
from contracts.services.assignments import _base_row
from contracts.services.governance_ux import priority_tone_for_label, sla_priority_reason

User = get_user_model()


class Phase7PriorityReasonTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='P7 Org', slug='p7-org')
        self.owner = User.objects.create_user('p7_owner', password='x')
        self.member = User.objects.create_user('p7_member', password='x')
        for user, role in (
            (self.owner, OrganizationMembership.Role.OWNER),
            (self.member, OrganizationMembership.Role.MEMBER),
        ):
            OrganizationMembership.objects.create(
                organization=self.org, user=user, role=role, is_active=True,
            )
        self.contract = Contract.objects.create(
            organization=self.org,
            title='Priority Contract',
            counterparty='Acme',
            content='Body',
            status=Contract.Status.IN_PROGRESS,
            contract_type='MSA',
            created_by=self.owner,
            risk_level='HIGH',
        )
        today = timezone.localdate()
        self.approval = ApprovalRequest.objects.create(
            organization=self.org,
            contract=self.contract,
            approval_step='LEGAL',
            status=ApprovalRequest.Status.PENDING,
            assigned_to=self.member,
            due_date=timezone.now() - timedelta(days=2),
        )
        self.task = LegalTask.objects.create(
            contract=self.contract,
            title='Overdue task',
            description='Needs completion',
            status=LegalTask.Status.PENDING,
            priority=LegalTask.Priority.HIGH,
            assigned_to=self.member,
            due_date=today - timedelta(days=1),
        )
        self.obligation = Deadline.objects.create(
            contract=self.contract,
            title='Overdue obligation',
            deadline_type=Deadline.DeadlineType.RENEWAL,
            priority=Deadline.Priority.HIGH,
            assigned_to=self.member,
            created_by=self.owner,
            due_date=today - timedelta(days=3),
        )

    def test_priority_tone_helper(self):
        self.assertEqual(priority_tone_for_label('Critical'), 'danger')
        self.assertEqual(priority_tone_for_label('High'), 'warning')
        self.assertEqual(priority_tone_for_label('Normal'), 'info')

    def test_my_work_renders_governance_priority_with_reason(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('contracts:my_work'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'gov-priority')
        self.assertContains(response, 'Why this priority')
        # Desktop table and mobile cards both use the shared component.
        self.assertContains(response, 'title=')
        rows = response.context['my_work_rows']
        self.assertTrue(any(r.get('priority_reason') for r in rows))
        self.assertTrue(any(r.get('priority_tone') for r in rows))

    def test_approvals_queue_shows_why_this_priority(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('contracts:approval_request_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'gov-priority')
        self.assertContains(response, 'Why this priority')
        self.assertContains(response, 'Overdue')

    def test_tasks_queue_includes_priority_reason(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('contracts:legal_task_kanban'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'gov-priority')
        self.assertContains(response, 'Why this priority')
        tabs = response.context['queue_tabs']
        assigned = next(t for t in tabs if t['key'] == 'assigned_to_me')
        self.assertTrue(any(r.get('priority_reason') for r in assigned['rows']))

    def test_obligations_queue_uses_shared_priority_component(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('contracts:obligations_workspace'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'gov-priority')
        self.assertContains(response, 'Why this priority')
        self.assertContains(response, 'Overdue by')

    def test_base_row_carries_priority_tone(self):
        today = timezone.localdate()
        row = _base_row(
            row_id='task:1',
            title='X',
            work_kind='task',
            work_type_key='tasks',
            work_type_label='Task',
            contract=self.contract,
            user=self.member,
            assigned_date=today,
            due_date=today - timedelta(days=1),
            priority_value='LOW',
            priority_reason=sla_priority_reason(
                due_date=today - timedelta(days=1), today=today, overdue=True,
            ),
            today=today,
        )
        self.assertEqual(row['priority_label'], 'High')
        self.assertEqual(row['priority_tone'], 'warning')
        self.assertIn('Overdue', row['priority_reason'])
