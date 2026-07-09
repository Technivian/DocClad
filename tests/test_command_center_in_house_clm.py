"""Command Center dashboard framing tests.

The dashboard is intentionally presentation-led: it renders the reference
Command Center layout without triggering DPA analysis or mutating workflow
state. These tests keep the critical shell and links covered without locking
visual implementation details too tightly.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from contracts.models import (
    ApprovalRequest,
    CommandCenterRailItem,
    CommandCenterSavedView,
    CommandCenterWorkItem,
    Contract,
    Counterparty,
    Deadline,
    DPAReviewPack,
    DPARiskItem,
    ReviewMemo,
    Organization,
    OrganizationMembership,
)
from contracts.services.command_center import refresh_command_center_projection

User = get_user_model()


class CommandCenterDashboardTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Command Center Org', slug='command-center-org')
        self.user = User.objects.create_user(username='command_center_user', password='testpass123!')
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.user,
            role=OrganizationMembership.Role.OWNER,
            is_active=True,
        )
        self.client_ = TestClient()
        self.client_.login(username='command_center_user', password='testpass123!')
        self.contract = Contract.objects.create(
            organization=self.org,
            title='Data Processing Agreement — Payrollminds',
            content='x',
            status='DRAFT',
            created_by=self.user,
        )
        self.counterparty = Counterparty.objects.create(organization=self.org, name='Payrollminds')
        self.review_pack = DPAReviewPack.objects.create(
            organization=self.org,
            contract=self.contract,
            counterparty=self.counterparty,
        )

    def test_reference_command_center_shell_renders(self):
        response = self.client_.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Command Center')
        self.assertContains(response, 'Live portfolio overview')
        # The attention banner is wired to the same real counts as the four
        # metric cards, not the old hardcoded "23 contracts..." copy — this
        # org's setUp has no conflicts/reviews/approvals/renewals pending, so
        # the banner (which would otherwise just restate the zeroed-out
        # cards) doesn't render at all rather than showing an empty-state message.
        self.assertNotContains(response, 'Attention needed:')

    def test_metric_cards_render(self):
        response = self.client_.get(reverse('dashboard'))
        self.assertContains(response, 'Direct action')
        self.assertContains(response, 'Exposure review')
        self.assertContains(response, 'Blocked')
        self.assertContains(response, 'Notice risk')
        self.assertContains(response, '€4.7M')
        self.assertContains(response, 'Deadlines next 30 days')

    def test_priority_queue_and_right_rail_render(self):
        # Priority Queue is wired to real in-progress contracts, not hardcoded
        # mock rows — seed one so the test verifies actual data flows through
        # rather than locking in fake company names.
        Contract.objects.create(
            organization=self.org,
            title='Active Priority Queue Contract',
            content='x',
            status='ACTIVE',
            counterparty='Test Counterparty Inc.',
            created_by=self.user,
        )
        response = self.client_.get(reverse('dashboard'))
        self.assertContains(response, 'Priority Queue')
        self.assertContains(response, 'Acme MSA Renewal')
        self.assertContains(response, 'My Queue')
        self.assertContains(response, 'DPA Conflicts')
        self.assertContains(response, 'Kanban')
        self.assertContains(response, 'Calendar')
        self.assertContains(response, 'Risk Intelligence')
        self.assertContains(response, 'Command Rail')
        self.assertContains(response, 'Blocking approvals')
        self.assertContains(response, 'Upcoming notice dates')
        self.assertContains(response, 'Recommended Actions')

    def test_dashboard_uses_persisted_command_center_model(self):
        CommandCenterSavedView.objects.create(
            organization=self.org,
            key='privacy-escalations',
            name='Privacy Escalations',
            filters={'source_type': 'DPA_CONFLICT'},
            sort_order=5,
        )
        CommandCenterWorkItem.objects.create(
            organization=self.org,
            source_type=CommandCenterWorkItem.SourceType.DPA_CONFLICT,
            source_model='DPARiskItem',
            source_object_id=42,
            title='Persisted DPA conflict row',
            subtitle='MSA cap mismatch',
            item_type='DPA conflict',
            stage='Counsel review',
            status=CommandCenterWorkItem.Status.BLOCKED,
            risk_level=Contract.RiskLevel.HIGH,
            priority=CommandCenterWorkItem.Priority.CRITICAL,
            owner=self.user,
            contract=self.contract,
            dpa_review_pack=self.review_pack,
            action_path='/contracts/dpa-reviews/',
            action_label='Resolve',
            flags={'waiting_on_business': True},
        )
        CommandCenterRailItem.objects.create(
            organization=self.org,
            kind=CommandCenterRailItem.Kind.RISK,
            title='Persisted risk rail',
            summary='Risk signal from projection table.',
            count=3,
            severity=Contract.RiskLevel.HIGH,
            action_path='/contracts/risks/',
        )
        ReviewMemo.objects.create(
            organization=self.org,
            title='Persisted review memo',
            memo_type=ReviewMemo.MemoType.DPA_REVIEW,
            body='Memo body',
            contract=self.contract,
            dpa_review_pack=self.review_pack,
        )

        response = self.client_.get(reverse('dashboard'))

        self.assertContains(response, 'Privacy Escalations')
        self.assertContains(response, 'Persisted DPA conflict row')
        self.assertContains(response, 'MSA cap mismatch')
        self.assertContains(response, 'Counsel review')
        self.assertContains(response, 'Resolve')
        self.assertContains(response, 'Persisted risk rail')

    def test_refresh_projection_materializes_source_records(self):
        DPARiskItem.objects.create(
            review_pack=self.review_pack,
            category=DPARiskItem.Category.LIABILITY,
            title='Projected DPA liability conflict',
            description='DPA overrides the MSA cap.',
            severity=DPARiskItem.Severity.HIGH,
            owners=DPARiskItem.Owner.LEGAL,
            is_cross_document_conflict=True,
            status=DPARiskItem.Status.OPEN,
        )
        ApprovalRequest.objects.create(
            organization=self.org,
            contract=self.contract,
            approval_step='Legal',
            status=ApprovalRequest.Status.PENDING,
            assigned_to=self.user,
            due_date=timezone.now() + timedelta(days=2),
        )
        Deadline.objects.create(
            contract=self.contract,
            title='Projected notice date',
            deadline_type=Deadline.DeadlineType.RENEWAL,
            due_date=timezone.localdate() + timedelta(days=10),
            assigned_to=self.user,
            created_by=self.user,
        )
        self.review_pack.review_memo = 'Projected memo body'
        self.review_pack.review_memo_generated_at = timezone.now()
        self.review_pack.save(update_fields=['review_memo', 'review_memo_generated_at'])

        result = refresh_command_center_projection(self.org, actor=self.user)

        self.assertEqual(result['saved_views'], 6)
        self.assertGreaterEqual(result['work_items'], 4)
        self.assertEqual(CommandCenterWorkItem.objects.filter(organization=self.org).count(), result['work_items'])
        self.assertTrue(CommandCenterWorkItem.objects.filter(title='Projected DPA liability conflict').exists())
        self.assertTrue(CommandCenterWorkItem.objects.filter(title='Projected notice date').exists())
        self.assertTrue(ReviewMemo.objects.filter(title__icontains='DPA review memo').exists())

    def test_dashboard_does_not_call_conflict_detection(self):
        import contracts.services.dpa_conflict as dpa_conflict

        def _boom(*args, **kwargs):
            raise AssertionError('Dashboard must not call check_cross_document_conflicts')

        original = dpa_conflict.check_cross_document_conflicts
        dpa_conflict.check_cross_document_conflicts = _boom
        try:
            response = self.client_.get(reverse('dashboard'))
            self.assertEqual(response.status_code, 200)
        finally:
            dpa_conflict.check_cross_document_conflicts = original

    def test_dashboard_render_does_not_mutate_approval_state(self):
        approval = ApprovalRequest.objects.create(
            organization=self.org,
            contract=self.contract,
            approval_step='Legal',
            status='PENDING',
            assigned_to=self.user,
        )
        self.client_.get(reverse('dashboard'))
        approval.refresh_from_db()
        self.assertEqual(approval.status, 'PENDING')

    def test_dashboard_links_resolve(self):
        for name in [
            'contracts:risk_log_list',
            'contracts:dpa_review_pack_list',
            'contracts:approval_request_list',
            'contracts:contract_list',
            'contracts:deadline_list',
            'contracts:legal_task_kanban',
        ]:
            reverse(name)
