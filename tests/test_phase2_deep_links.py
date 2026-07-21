"""Phase 2 action-context deep link tests."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from contracts.models import (
    ApprovalRequest,
    Contract,
    Organization,
    OrganizationMembership,
)
from contracts.services.assignments import get_active_work_items
from contracts.services.contract_detail_workspace import contract_detail_workflow_url

User = get_user_model()


class Phase2DeepLinkTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Deep Link Org', slug='deep-link-org')
        self.user = User.objects.create_user(username='deep_link_user', password='testpass123!')
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.user,
            role=OrganizationMembership.Role.OWNER,
            is_active=True,
        )
        self.contract = Contract.objects.create(
            organization=self.org,
            title='Deep Link Contract',
            content='Body',
            status=Contract.Status.IN_PROGRESS,
            created_by=self.user,
        )

    def test_contract_detail_workflow_url_targets_review_section(self):
        url = contract_detail_workflow_url(self.contract.pk, section='review')
        self.assertIn(f'/contracts/{self.contract.pk}/', url)
        self.assertIn('tab=workflow', url)
        self.assertIn('section=review', url)

    def test_returned_approval_links_to_workflow_approvals_context(self):
        ApprovalRequest.objects.create(
            organization=self.org,
            contract=self.contract,
            approval_step='legal',
            assigned_to=self.user,
            status=ApprovalRequest.Status.CHANGES_REQUESTED,
            due_date=timezone.now() + timedelta(days=1),
        )
        rows = get_active_work_items(self.org, self.user)
        returned = next((row for row in rows if row['id'].startswith('approval-returned:')), None)
        self.assertIsNotNone(returned)
        self.assertIn('section=approvals', returned['action_href'])
        self.assertIn('tab=workflow', returned['action_href'])
