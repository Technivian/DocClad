"""Phase 9 — My Work reassign + privacy conflict resolve + Correct kebab."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from contracts.models import (
    ApprovalRequest,
    Contract,
    Counterparty,
    DPAReviewPack,
    DPARiskItem,
    Organization,
    OrganizationMembership,
)
from contracts.services.assignments import get_active_work_items

User = get_user_model()


class Phase9MyWorkGovernanceActionsTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='P9 Org', slug='p9-org')
        self.owner = User.objects.create_user('p9_owner', password='x')
        self.admin = User.objects.create_user('p9_admin', password='x')
        self.member = User.objects.create_user('p9_member', password='x')
        self.delegate = User.objects.create_user('p9_delegate', password='x')
        for user, role in (
            (self.owner, OrganizationMembership.Role.OWNER),
            (self.admin, OrganizationMembership.Role.ADMIN),
            (self.member, OrganizationMembership.Role.MEMBER),
            (self.delegate, OrganizationMembership.Role.MEMBER),
        ):
            OrganizationMembership.objects.create(
                organization=self.org, user=user, role=role, is_active=True,
            )
        self.contract = Contract.objects.create(
            organization=self.org,
            title='P9 Contract',
            counterparty='Acme',
            content='Body',
            status=Contract.Status.IN_PROGRESS,
            contract_type='MSA',
            created_by=self.owner,
        )
        self.approval = ApprovalRequest.objects.create(
            organization=self.org,
            contract=self.contract,
            approval_step='LEGAL',
            status=ApprovalRequest.Status.PENDING,
            assigned_to=self.admin,
            due_date=timezone.now() + timedelta(days=2),
        )
        self.member_approval = ApprovalRequest.objects.create(
            organization=self.org,
            contract=self.contract,
            approval_step='FINANCE',
            status=ApprovalRequest.Status.PENDING,
            assigned_to=self.member,
            due_date=timezone.now() + timedelta(days=3),
        )
        self.counterparty = Counterparty.objects.create(
            organization=self.org, name='Acme CP',
        )
        self.pack = DPAReviewPack.objects.create(
            organization=self.org,
            contract=self.contract,
            counterparty=self.counterparty,
            reviewer=self.admin,
            approval_status=DPAReviewPack.ApprovalStatus.UNDER_REVIEW,
            created_by=self.owner,
        )
        self.conflict = DPARiskItem.objects.create(
            review_pack=self.pack,
            category=DPARiskItem.Category.LIABILITY,
            title='DPA liability overrides MSA cap',
            description='Conflict between linked agreements',
            severity=DPARiskItem.Severity.HIGH,
            owners='LEGAL',
            is_cross_document_conflict=True,
            status=DPARiskItem.Status.OPEN,
        )

    def test_admin_assignee_gets_reassign_flags(self):
        rows = [
            r for r in get_active_work_items(self.org, self.admin)
            if r.get('id') == f'approval:{self.approval.pk}'
        ]
        self.assertTrue(rows)
        self.assertTrue(rows[0].get('can_reassign'))
        self.assertIn('/reassign/', rows[0]['reassign_url'])

    def test_member_assignee_does_not_get_reassign(self):
        rows = [
            r for r in get_active_work_items(self.org, self.member)
            if r.get('id') == f'approval:{self.member_approval.pk}'
        ]
        self.assertTrue(rows)
        self.assertFalse(rows[0].get('can_reassign'))

    def test_my_work_template_shows_reassign_and_conflict_actions(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('contracts:my_work'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-my-work-action="reassign"')
        self.assertContains(response, 'data-reassign-url')
        self.assertContains(response, 'data-my-work-action="resolve-conflict"')
        self.assertContains(response, 'Mark false positive')
        self.assertContains(response, 'tab=risks')

    def test_reassign_api_from_my_work_surface(self):
        self.client.force_login(self.admin)
        url = reverse('contracts:approval_reassign_api', kwargs={'approval_id': self.approval.pk})
        response = self.client.post(
            url,
            data='{"to_user_id": %d, "reason": "Coverage handoff", "surface": "my_work"}' % self.delegate.pk,
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.approval.refresh_from_db()
        self.assertEqual(self.approval.assigned_to_id, self.delegate.pk)

    def test_reassign_requires_reason(self):
        self.client.force_login(self.admin)
        url = reverse('contracts:approval_reassign_api', kwargs={'approval_id': self.approval.pk})
        response = self.client.post(
            url,
            data='{"to_user_id": %d, "reason": ""}' % self.delegate.pk,
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_privacy_conflict_row_points_to_risks_tab(self):
        rows = [
            r for r in get_active_work_items(self.org, self.admin)
            if r.get('id') == f'privacy-conflict:{self.conflict.pk}'
        ]
        self.assertTrue(rows)
        self.assertIn('tab=risks', rows[0]['action_href'])
        self.assertTrue(rows[0].get('can_resolve_conflict'))
        self.assertTrue(rows[0].get('conflict_status_url'))

    def test_resolve_conflict_removes_from_active_work(self):
        self.client.force_login(self.admin)
        url = reverse('contracts:dpa_risk_item_set_status', kwargs={'pk': self.conflict.pk})
        response = self.client.post(
            url,
            data='{"status":"RESOLVED"}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.conflict.refresh_from_db()
        self.assertEqual(self.conflict.status, DPARiskItem.Status.RESOLVED)
        remaining = [
            r for r in get_active_work_items(self.org, self.admin)
            if r.get('id') == f'privacy-conflict:{self.conflict.pk}'
        ]
        self.assertEqual(remaining, [])

    def test_returned_row_kebab_has_correct_on_contract(self):
        ApprovalRequest.objects.create(
            organization=self.org,
            contract=self.contract,
            approval_step='LEGAL',
            status=ApprovalRequest.Status.CHANGES_REQUESTED,
            assigned_to=self.admin,
            decided_by=self.admin,
            comments='Please revise schedule',
        )
        self.client.force_login(self.owner)
        response = self.client.get(reverse('contracts:my_work'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Correct on contract')
        self.assertContains(response, 'section=approvals')
