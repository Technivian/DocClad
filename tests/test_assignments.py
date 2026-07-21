"""Tests for the canonical assignments service."""

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from contracts.models import (
    ApprovalRequest,
    Contract,
    Counterparty,
    Deadline,
    DPAReviewPack,
    LegalTask,
    Organization,
    OrganizationMembership,
)
from contracts.services.assignments import (
    build_summary_counts,
    get_active_work_items,
    open_obligations_queryset,
    open_tasks_queryset,
    pending_approvals_queryset,
    reviewer_privacy_packs_queryset,
)
from contracts.services.my_work import get_active_work_items as facade_get_active_work_items

User = get_user_model()


class AssignmentsServiceTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Assignments Org', slug='assignments-org')
        self.user = User.objects.create_user(username='assign_user', password='testpass123!')
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.user,
            role=OrganizationMembership.Role.OWNER,
            is_active=True,
        )
        self.contract = Contract.objects.create(
            organization=self.org,
            title='Assignments Contract',
            content='Body',
            status=Contract.Status.IN_PROGRESS,
            created_by=self.user,
        )

    def test_get_active_work_items_returns_assigned_approval(self):
        ApprovalRequest.objects.create(
            organization=self.org,
            contract=self.contract,
            approval_step='legal',
            assigned_to=self.user,
            status=ApprovalRequest.Status.PENDING,
            due_date=timezone.now() + timedelta(days=1),
        )
        rows = get_active_work_items(self.org, self.user)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['work_kind'], 'approval')
        self.assertEqual(rows[0]['action_label'], 'Approve')

    def test_my_work_facade_reexports_assignments_service(self):
        ApprovalRequest.objects.create(
            organization=self.org,
            contract=self.contract,
            approval_step='finance',
            assigned_to=self.user,
            status=ApprovalRequest.Status.PENDING,
        )
        canonical = get_active_work_items(self.org, self.user)
        facade = facade_get_active_work_items(self.org, self.user)
        self.assertEqual([row['id'] for row in canonical], [row['id'] for row in facade])

    def test_summary_counts_include_overdue_tag(self):
        ApprovalRequest.objects.create(
            organization=self.org,
            contract=self.contract,
            approval_step='legal',
            assigned_to=self.user,
            status=ApprovalRequest.Status.PENDING,
            due_date=timezone.now() - timedelta(days=1),
        )
        rows = get_active_work_items(self.org, self.user)
        counts = build_summary_counts(rows)
        self.assertGreaterEqual(counts['overdue'], 1)

    def test_queryset_helpers_match_my_work_collectors(self):
        ApprovalRequest.objects.create(
            organization=self.org,
            contract=self.contract,
            approval_step='legal',
            assigned_to=self.user,
            status=ApprovalRequest.Status.PENDING,
        )
        LegalTask.objects.create(
            title='Canonical task',
            description='Task body',
            assigned_to=self.user,
            contract=self.contract,
            due_date=date.today() + timedelta(days=2),
            status=LegalTask.Status.PENDING,
        )
        Deadline.objects.create(
            title='Canonical obligation',
            contract=self.contract,
            assigned_to=self.user,
            due_date=date.today() + timedelta(days=5),
            created_by=self.user,
        )
        counterparty = Counterparty.objects.create(organization=self.org, name='Privacy Co')
        DPAReviewPack.objects.create(
            organization=self.org,
            contract=self.contract,
            counterparty=counterparty,
            reviewer=self.user,
            approval_status=DPAReviewPack.ApprovalStatus.UNDER_REVIEW,
        )

        rows = get_active_work_items(self.org, self.user)
        self.assertEqual(pending_approvals_queryset(self.org, self.user).count(), 1)
        self.assertEqual(open_tasks_queryset(self.org, self.user).count(), 1)
        self.assertEqual(open_obligations_queryset(self.org, self.user).count(), 1)
        self.assertEqual(reviewer_privacy_packs_queryset(self.org, self.user).count(), 1)
        self.assertGreaterEqual(len(rows), 4)

    def test_approvals_waiting_tab_uses_shared_queryset(self):
        ApprovalRequest.objects.create(
            organization=self.org,
            contract=self.contract,
            approval_step='legal',
            assigned_to=self.user,
            status=ApprovalRequest.Status.PENDING,
        )
        client = Client()
        client.login(username='assign_user', password='testpass123!')
        response = client.get(reverse('contracts:approval_request_list'))
        waiting = next(tab for tab in response.context['queue_tabs'] if tab['key'] == 'waiting_on_me')
        self.assertEqual(len(waiting['rows']), 1)
        self.assertTrue(waiting['personal_hub'])
