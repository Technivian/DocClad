from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from contracts.models import CommandCenterWorkItem, Organization, OrganizationMembership
from contracts.services.demo_command_center import seed_demo_command_center_workflows

User = get_user_model()


class DemoCommandCenterSeedTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            name='Demo Command Center Org',
            slug='demo-command-center-org',
            workspace_mode=Organization.WorkspaceMode.IN_HOUSE_CLM,
        )
        self.user = User.objects.create_user(username='demo_owner', password='testpass123!')
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.user,
            role=OrganizationMembership.Role.OWNER,
            is_active=True,
        )
        self.client_ = TestClient()
        self.client_.login(username='demo_owner', password='testpass123!')

    def test_demo_seed_is_idempotent(self):
        seed_demo_command_center_workflows(organization=self.org, user=self.user)
        seed_demo_command_center_workflows(organization=self.org, user=self.user)

        self.assertEqual(CommandCenterWorkItem.objects.filter(organization=self.org, workflow__isnull=False).count(), 3)
        self.assertEqual(
            set(CommandCenterWorkItem.objects.filter(organization=self.org).values_list('contract__source_system_id', flat=True)),
            {'northwind-dpa', 'acme-msa', 'brightlane-nda'},
        )

    def test_management_command_seeds_demo_rows(self):
        call_command(
            'seed_demo_command_center',
            organization_slug=self.org.slug,
            username=self.user.username,
        )
        self.assertEqual(CommandCenterWorkItem.objects.filter(organization=self.org, workflow__isnull=False).count(), 3)

    def test_dashboard_renders_demo_personalities_and_workspace_links(self):
        seed_demo_command_center_workflows(organization=self.org, user=self.user)

        response = self.client_.get(reverse('dashboard'))

        self.assertContains(response, 'Northwind DPA Privacy Review Workflow')
        self.assertContains(response, 'Privacy risk')
        self.assertContains(response, 'EEA transfer + subprocessors')
        self.assertContains(response, 'Review SCC fallback')

        self.assertContains(response, 'Acme MSA Commercial Review Workflow')
        self.assertContains(response, 'Commercial risk')
        self.assertContains(response, 'Liability cap outside playbook + finance threshold')
        self.assertContains(response, 'Review fallback clause')

        self.assertContains(response, 'Brightlane NDA Self-Serve Workflow')
        self.assertContains(response, 'Self-serve eligible')
        self.assertContains(response, 'No legal risk detected')
        self.assertContains(response, 'Send for signature')

        for item in CommandCenterWorkItem.objects.filter(organization=self.org, workflow__isnull=False):
            self.assertContains(response, reverse('contracts:workflow_detail', kwargs={'pk': item.workflow_id}))
        self.assertContains(response, 'Open workspace')

    def test_dashboard_summary_strip_uses_real_workflow_counts(self):
        seed_demo_command_center_workflows(organization=self.org, user=self.user)

        response = self.client_.get(reverse('dashboard'))
        summary = response.context['workflow_type_summary']

        self.assertContains(response, 'Privacy reviews')
        self.assertContains(response, 'Commercial reviews')
        self.assertContains(response, 'Self-serve ready')
        self.assertContains(response, 'Blocking approvals')
        self.assertEqual(summary['privacy_reviews'], 1)
        self.assertEqual(summary['commercial_reviews'], 1)
        self.assertEqual(summary['self_serve_ready'], 1)
        self.assertEqual(summary['blocking_approvals'], 2)
