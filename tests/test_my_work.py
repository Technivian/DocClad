"""Tests for the My Work personal action hub."""

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

User = get_user_model()


class MyWorkPageTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='My Work Org', slug='my-work-org')
        self.owner = User.objects.create_user(username='mw_owner', password='testpass123!')
        self.reviewer = User.objects.create_user(username='mw_reviewer', password='testpass123!')
        OrganizationMembership.objects.create(
            organization=self.org, user=self.owner,
            role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        OrganizationMembership.objects.create(
            organization=self.org, user=self.reviewer,
            role=OrganizationMembership.Role.MEMBER, is_active=True,
        )
        self.client = Client()
        self.client.login(username='mw_owner', password='testpass123!')
        self.counterparty = Counterparty.objects.create(organization=self.org, name='Acme Corp')
        self.contract = Contract.objects.create(
            organization=self.org,
            title='Acme Master Agreement',
            content='Agreement body',
            status=Contract.Status.IN_PROGRESS,
            created_by=self.owner,
            counterparty='Acme Corp',
        )

    def test_my_work_renders_unified_queue(self):
        response = self.client.get(reverse('contracts:my_work'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'My Work')
        self.assertContains(response, 'Review and complete the work currently assigned to you.')
        self.assertNotContains(response, 'Your personal queue')
        self.assertNotContains(response, 'Until that queue ships')
        self.assertNotContains(response, 'Reviews &amp; Approvals</a>')
        self.assertContains(response, 'id="my-work-root"')
        self.assertContains(response, 'id="my-work-search"')
        self.assertContains(response, 'Refresh')
        self.assertContains(response, 'my-work-toolbar-actions')
        self.assertContains(response, 'class="my-work-scope-tabs" role="group"')
        self.assertNotContains(response, '<nav class="my-work-scope-tabs"')
        self.assertContains(response, 'id="my-work-filters-toggle"')
        self.assertContains(response, '>Filters</button>')
        content = response.content.decode()
        self.assertLess(content.index('id="my-work-search"'), content.index('id="my-work-filters-toggle"'))
        self.assertLess(content.index('my-work-inline-summary'), content.index('id="my-work-search"'))
        self.assertNotIn('my-work-summary-wrap', content)

    def test_my_work_shows_assigned_approval(self):
        ApprovalRequest.objects.create(
            organization=self.org,
            contract=self.contract,
            approval_step='finance_director',
            assigned_to=self.owner,
            status=ApprovalRequest.Status.PENDING,
            due_date=timezone.now() + timedelta(days=1),
        )
        response = self.client.get(reverse('contracts:my_work'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Approve Finance Director')
        self.assertContains(response, 'Awaiting your approval')
        self.assertContains(response, 'Approve')

    def test_my_work_shows_assigned_task_and_obligation(self):
        LegalTask.objects.create(
            title='Provide missing counterparty information',
            description='Collect vendor address details.',
            assigned_to=self.owner,
            contract=self.contract,
            due_date=date.today() + timedelta(days=3),
            status=LegalTask.Status.PENDING,
        )
        Deadline.objects.create(
            title='Complete renewal obligation',
            contract=self.contract,
            assigned_to=self.owner,
            due_date=date.today() + timedelta(days=14),
            created_by=self.owner,
        )
        response = self.client.get(reverse('contracts:my_work'))
        self.assertContains(response, 'Provide missing counterparty information')
        self.assertContains(response, 'Complete renewal obligation')

    def test_my_work_shows_privacy_review_for_reviewer(self):
        DPAReviewPack.objects.create(
            organization=self.org,
            contract=self.contract,
            counterparty=self.counterparty,
            reviewer=self.owner,
            approval_status=DPAReviewPack.ApprovalStatus.UNDER_REVIEW,
        )
        response = self.client.get(reverse('contracts:my_work'))
        self.assertContains(response, 'Complete data transfer assessment')
        self.assertContains(response, 'Privacy')

    def test_my_work_empty_state_when_no_assignments(self):
        other_client = Client()
        other_client.login(username='mw_reviewer', password='testpass123!')
        response = other_client.get(reverse('contracts:my_work'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You're all caught up")
        self.assertContains(response, 'View recently completed work')

    def test_my_work_json_refresh_endpoint(self):
        response = self.client.get(reverse('contracts:my_work'), {'format': 'json'})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('count', payload)
        self.assertIn('summary', payload)
        self.assertIn('last_updated', payload)

    def test_my_work_summary_counts_overdue(self):
        ApprovalRequest.objects.create(
            organization=self.org,
            contract=self.contract,
            approval_step='legal',
            assigned_to=self.owner,
            status=ApprovalRequest.Status.PENDING,
            due_date=timezone.now() - timedelta(days=2),
        )
        response = self.client.get(reverse('contracts:my_work'))
        self.assertContains(response, 'data-summary-filter="overdue"')
        self.assertContains(response, 'Overdue')
