"""Phase 8 — My Work in-place action parity with specialist queues."""
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
    WorkInteractionEvent,
)
from contracts.services.assignments import get_active_work_items

User = get_user_model()


class Phase8MyWorkActionParityTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='P8 Org', slug='p8-org')
        self.owner = User.objects.create_user('p8_owner', password='x')
        self.member = User.objects.create_user('p8_member', password='x')
        for user, role in (
            (self.owner, OrganizationMembership.Role.OWNER),
            (self.member, OrganizationMembership.Role.ADMIN),
        ):
            OrganizationMembership.objects.create(
                organization=self.org, user=user, role=role, is_active=True,
            )
        self.contract = Contract.objects.create(
            organization=self.org,
            title='Action Parity Contract',
            counterparty='Acme',
            content='Body',
            status=Contract.Status.IN_PROGRESS,
            contract_type='MSA',
            created_by=self.owner,
        )
        today = timezone.localdate()
        self.approval = ApprovalRequest.objects.create(
            organization=self.org,
            contract=self.contract,
            approval_step='LEGAL',
            status=ApprovalRequest.Status.PENDING,
            assigned_to=self.member,
            due_date=timezone.now() + timedelta(days=2),
        )
        self.task = LegalTask.objects.create(
            contract=self.contract,
            title='Finish intake notes',
            description='Capture missing fields',
            status=LegalTask.Status.PENDING,
            priority=LegalTask.Priority.HIGH,
            assigned_to=self.member,
            due_date=today + timedelta(days=1),
        )
        self.obligation = Deadline.objects.create(
            contract=self.contract,
            title='Renewal follow-up',
            deadline_type=Deadline.DeadlineType.RENEWAL,
            priority=Deadline.Priority.HIGH,
            assigned_to=self.member,
            created_by=self.owner,
            due_date=today + timedelta(days=5),
        )

    def _rows_by_kind(self, kind):
        return [
            row for row in get_active_work_items(self.org, self.member)
            if row.get('work_kind') == kind and not row.get('is_restricted')
        ]

    def test_assignment_rows_expose_mutation_urls(self):
        approvals = self._rows_by_kind('approval')
        self.assertTrue(approvals)
        self.assertTrue(approvals[0].get('can_decide'))
        self.assertIn('/approve/', approvals[0]['approve_url'])
        self.assertIn('/reject/', approvals[0]['reject_url'])
        self.assertTrue(approvals[0]['return_url'])

        tasks = self._rows_by_kind('task')
        self.assertTrue(tasks)
        self.assertTrue(tasks[0].get('can_complete'))
        self.assertIn('/complete/', tasks[0]['complete_url'])

        obligations = self._rows_by_kind('obligation')
        self.assertTrue(obligations)
        self.assertTrue(obligations[0].get('can_complete'))
        self.assertTrue(obligations[0].get('defer_url'))
        self.assertTrue(obligations[0].get('escalate_url'))

    def test_my_work_template_renders_mutation_kebab(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('contracts:my_work'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-my-work-action="approve"')
        self.assertContains(response, 'data-my-work-action="complete"')
        self.assertContains(response, 'data-action-href')
        self.assertContains(response, 'data-approve-url')

    def test_approve_from_my_work_stamps_surface(self):
        self.client.force_login(self.member)
        url = reverse('contracts:approval_approve_api', kwargs={'approval_id': self.approval.pk})
        response = self.client.post(
            url,
            data='{"comments":"ok","surface":"my_work"}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.approval.refresh_from_db()
        self.assertEqual(self.approval.status, ApprovalRequest.Status.APPROVED)
        self.assertTrue(
            WorkInteractionEvent.objects.filter(
                organization=self.org,
                event='completed',
                work_item_id=f'approval:{self.approval.pk}',
                surface='my_work',
            ).exists()
        )

    def test_task_complete_from_my_work_records_outcome(self):
        self.client.force_login(self.member)
        url = reverse('contracts:legal_task_complete', kwargs={'pk': self.task.pk})
        response = self.client.post(
            url,
            data='{"surface":"my_work"}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, LegalTask.Status.COMPLETED)
        self.assertTrue(
            WorkInteractionEvent.objects.filter(
                event='completed',
                work_item_id=f'task:{self.task.pk}',
                surface='my_work',
            ).exists()
        )

    def test_obligation_complete_json_mode(self):
        self.client.force_login(self.member)
        url = reverse('contracts:deadline_complete', kwargs={'pk': self.obligation.pk})
        response = self.client.post(
            url + '?from=my_work',
            data={},
            HTTP_ACCEPT='application/json',
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload.get('ok'))
        self.obligation.refresh_from_db()
        self.assertTrue(self.obligation.is_completed)
        self.assertTrue(
            WorkInteractionEvent.objects.filter(
                event='completed',
                work_item_id=f'obligation:{self.obligation.pk}',
                surface='my_work',
            ).exists()
        )

    def test_reject_requires_reason(self):
        self.client.force_login(self.member)
        url = reverse('contracts:approval_reject_api', kwargs={'approval_id': self.approval.pk})
        response = self.client.post(
            url,
            data='{"comments":"","surface":"my_work"}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.approval.refresh_from_db()
        self.assertEqual(self.approval.status, ApprovalRequest.Status.PENDING)
