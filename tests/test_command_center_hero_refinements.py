from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from contracts.models import ApprovalRequest, CommandCenterWorkItem, Contract, Organization, OrganizationMembership, RiskLog


User = get_user_model()


class CommandCenterHeroRefinementTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name='Hero Refinement Org',
            slug='hero-refinement-org',
            workspace_mode=Organization.WorkspaceMode.IN_HOUSE_CLM,
        )
        self.user = User.objects.create_user(username='hero-owner', password='testpass123!')
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.user,
            role=OrganizationMembership.Role.OWNER,
            is_active=True,
        )
        self.client = Client()
        self.client.login(username='hero-owner', password='testpass123!')

    def test_score_breakdown_and_finance_status_are_traceable(self):
        contract = Contract.objects.create(
            organization=self.organization,
            title='Finance approval contract',
            content='x',
            created_by=self.user,
        )
        RiskLog.objects.create(
            contract=contract,
            title='High-risk liability term',
            description='Needs finance sign-off.',
            risk_level=RiskLog.RiskLevel.HIGH,
            created_by=self.user,
        )
        ApprovalRequest.objects.create(
            organization=self.organization,
            contract=contract,
            approval_step='Finance',
            status=ApprovalRequest.Status.PENDING,
            assigned_to=self.user,
        )
        CommandCenterWorkItem.objects.create(
            organization=self.organization,
            source_type=CommandCenterWorkItem.SourceType.CONTRACT,
            source_model='Contract',
            source_object_id=contract.pk,
            title=contract.title,
            contract=contract,
            owner=self.user,
            stage='Draft',
            status=CommandCenterWorkItem.Status.OPEN,
            risk_level=Contract.RiskLevel.HIGH,
            priority=CommandCenterWorkItem.Priority.HIGH,
        )

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['portfolio_health_score'], 83)
        self.assertEqual(response.context['priority_feature_status'], 'Finance review required')
        self.assertEqual(
            [(factor['label'], factor['penalty']) for factor in response.context['portfolio_health_factors']],
            [
                ('High-risk findings', 12),
                ('Pending approvals', 5),
                ('Upcoming or overdue deadlines', 0),
                ('Policy exceptions', 0),
                ('Cross-document conflicts', 0),
            ],
        )
        self.assertContains(response, 'View score breakdown')
        self.assertContains(response, 'Finance review required')
        self.assertContains(response, 'High-risk findings')
