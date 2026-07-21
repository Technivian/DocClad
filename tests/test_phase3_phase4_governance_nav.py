"""Phase 3 governance UX + Phase 4 navigation retirement tests."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from contracts.models import (
    ApprovalRequest,
    ApprovalRule,
    AuditLog,
    Contract,
    Deadline,
    Organization,
    OrganizationMembership,
    UserProfile,
)
from contracts.services.approval_workflow import (
    ApprovalAccessDenied,
    get_approval_workflow_service,
)
from contracts.services.governance_ux import (
    approval_blocker_for_request,
    build_delegation_info,
    obligation_blocker_for_deadline,
    sla_priority_reason,
)

User = get_user_model()


class GovernanceUxHelperTests(TestCase):
    def test_delegation_preserves_original_and_acting(self):
        original = User(username='owner')
        acting = User(username='cover')
        info = build_delegation_info(
            original, acting, timezone.now(),
            reason='Out of office',
            ends_at=timezone.now() + timedelta(days=5),
        )
        self.assertEqual(info['original_assignee'], original)
        self.assertEqual(info['acting_assignee'], acting)
        self.assertEqual(info['reason'], 'Out of office')
        self.assertIsNotNone(info['effective_until'])

    def test_sla_priority_reason_includes_sla_hours_when_overdue(self):
        today = timezone.localdate()
        reason = sla_priority_reason(
            due_date=today - timedelta(days=2),
            today=today,
            sla_hours=48,
            overdue=True,
        )
        self.assertIn('Overdue by 2 days', reason)
        self.assertIn('SLA 48h', reason)

    def test_approval_blocker_waits_on_prior_step(self):
        prior = ApprovalRequest(pk=1, approval_step='LEGAL', sort_order=1, status='PENDING')
        prior.assigned_to = User(username='legal')
        later = ApprovalRequest(pk=2, approval_step='FINANCE', sort_order=2, status='PENDING')
        blocker = approval_blocker_for_request(later, sibling_pending=[prior, later])
        self.assertTrue(blocker['is_blocked'])
        self.assertIn('Legal', blocker['blocking_issue'])

    def test_obligation_blocker_when_unassigned(self):
        deadline = Deadline(title='Renew', due_date=timezone.localdate(), assigned_to=None)
        blocker = obligation_blocker_for_deadline(deadline)
        self.assertTrue(blocker['is_blocked'])
        self.assertEqual(blocker['blocking_issue'], 'No owner assigned')


class ApprovalDelegationAndReassignTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Gov Org', slug='gov-org')
        self.owner = User.objects.create_user('gov_owner', password='x')
        self.assignee = User.objects.create_user('gov_assignee', password='x')
        self.delegate = User.objects.create_user('gov_delegate', password='x')
        self.manager = User.objects.create_user('gov_manager', password='x')
        for user, role in (
            (self.owner, OrganizationMembership.Role.OWNER),
            (self.assignee, OrganizationMembership.Role.MEMBER),
            (self.delegate, OrganizationMembership.Role.MEMBER),
            (self.manager, OrganizationMembership.Role.ADMIN),
        ):
            OrganizationMembership.objects.create(
                organization=self.org, user=user, role=role, is_active=True,
            )
        self.contract = Contract.objects.create(
            organization=self.org,
            title='Coverage Contract',
            counterparty='Acme',
            content='Body',
            status=Contract.Status.IN_PROGRESS,
            created_by=self.owner,
        )
        self.rule = ApprovalRule.objects.create(
            organization=self.org,
            name='Legal',
            trigger_type=ApprovalRule.TriggerType.CONTRACT_TYPE,
            trigger_value='MSA',
            approval_step='LEGAL',
            approver_role=UserProfile.Role.ASSOCIATE,
            sla_hours=48,
            is_active=True,
        )
        self.approval = ApprovalRequest.objects.create(
            organization=self.org,
            contract=self.contract,
            rule=self.rule,
            approval_step='LEGAL',
            status=ApprovalRequest.Status.PENDING,
            assigned_to=self.assignee,
            due_date=timezone.now() + timedelta(days=2),
        )
        self.svc = get_approval_workflow_service()

    def test_delegate_keeps_original_assignee(self):
        ends = timezone.now() + timedelta(days=7)
        self.svc.delegate(
            self.approval.pk,
            self.delegate,
            self.assignee,
            reason='OOO coverage',
            ends_at=ends,
        )
        self.approval.refresh_from_db()
        self.assertEqual(self.approval.assigned_to_id, self.assignee.id)
        self.assertEqual(self.approval.delegated_to_id, self.delegate.id)
        self.assertEqual(self.approval.delegation_reason, 'OOO coverage')
        self.assertIsNotNone(self.approval.delegation_ends_at)
        self.assertTrue(
            AuditLog.objects.filter(
                event_type='approval.delegated',
                object_id=self.approval.pk,
            ).exists()
        )

    def test_reassign_requires_reason_and_admin(self):
        with self.assertRaises(ValueError):
            self.svc.reassign(self.approval.pk, self.delegate, self.manager, reason='')
        with self.assertRaises(ApprovalAccessDenied):
            self.svc.reassign(
                self.approval.pk, self.delegate, self.assignee, reason='Need coverage',
            )
        self.svc.reassign(
            self.approval.pk, self.delegate, self.manager, reason='Workload balance',
        )
        self.approval.refresh_from_db()
        self.assertEqual(self.approval.assigned_to_id, self.delegate.id)
        self.assertIsNone(self.approval.delegated_to_id)
        self.assertTrue(
            AuditLog.objects.filter(
                event_type='approval.reassigned',
                object_id=self.approval.pk,
            ).exists()
        )

    def test_approvals_queue_shows_blocked_and_coverage(self):
        self.svc.delegate(self.approval.pk, self.delegate, self.manager, reason='Coverage')
        self.client.force_login(self.delegate)
        response = self.client.get(reverse('contracts:approval_request_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'covering for')
        self.assertContains(response, 'gov_assignee')

    def test_reassign_api_requires_reason(self):
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse('contracts:approval_reassign_api', kwargs={'approval_id': self.approval.pk}),
            data='{"to_user_id": %d}' % self.delegate.id,
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)


class Phase4NavigationRetirementTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            name='Nav Org', slug='nav-org', workspace_mode=Organization.WorkspaceMode.IN_HOUSE_CLM,
        )
        self.user = User.objects.create_user('nav_user', password='x')
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.user,
            role=OrganizationMembership.Role.ADMIN,
            is_active=True,
        )
        self.client.force_login(self.user)

    def test_contract_list_redirects_to_repository(self):
        response = self.client.get(reverse('contracts:contract_list'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('contracts:repository'))

    def test_deadline_list_redirects_to_obligations(self):
        response = self.client.get(reverse('contracts:deadline_list') + '?show=overdue')
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('contracts:obligations_workspace'), response.url)
        self.assertIn('view=overdue', response.url)

    def test_command_center_points_deadlines_at_obligations(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('contracts:obligations_workspace'))
        self.assertContains(response, 'Open Obligations')
        self.assertContains(response, 'Contracts needing attention')
        self.assertNotContains(response, 'Recent Matters')

    @override_settings(CONTROLLED_PILOT_ENABLED=False)
    def test_law_firm_modules_redirect_for_in_house_clm(self):
        response = self.client.get('/contracts/clients/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('dashboard'))
        response = self.client.get('/contracts/invoices/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('dashboard'))
