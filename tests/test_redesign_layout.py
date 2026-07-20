
import os

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from contracts.models import Contract
from contracts.models import Organization
from contracts.tenancy import get_user_organization


class RedesignLayoutTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
        )
        os.environ['FEATURE_REDESIGN'] = 'true'
        self.client.login(username='testuser', password='testpass123')

    def _enable_clm_dashboard(self):
        organization = get_user_organization(self.user)
        organization.workspace_mode = Organization.WorkspaceMode.IN_HOUSE_CLM
        organization.save(update_fields=['workspace_mode'])
        return organization

    def test_base_shell_uses_casefile_light_mode(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'CLM One')
        self.assertContains(response, 'data-theme="light"')
        self.assertContains(response, 'data-design-system="casefile"')
        self.assertNotContains(response, 'data-action="toggle-theme"')
        self.assertContains(response, 'js/csp-handlers.js')
        self.assertContains(response, 'title="Search"')

    def test_sidebar_navigation_sections_and_links(self):
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'Command Center')
        self.assertContains(response, 'New Contract')
        self.assertContains(response, 'Contracts')
        self.assertContains(response, 'Privacy Reviews')
        self.assertContains(response, 'Obligations')
        self.assertContains(response, 'My Work')
        self.assertNotContains(response, 'REFERENCE')
        self.assertNotContains(response, 'RISK &amp; COMPLIANCE')
        self.assertNotContains(response, 'DPA Reviews')
        self.assertNotContains(response, 'Upload &amp; Review')

    def test_topbar_actions(self):
        response = self.client.get(reverse('dashboard'))
        # Sub-block C: hardcoded Dutch chrome replaced with English
        # (LANGUAGE_CODE is 'en-us' — see contracts/templatetags no i18n gate).
        self.assertContains(response, 'title="Notifications"')
        self.assertContains(response, 'New Contract')
        self.assertContains(response, 'Sign out')
        self.assertContains(response, '/profile/')

    def test_dashboard_kpis_and_panels(self):
        # The Command Center KPI strip and Priority Queue render on the
        # populated dashboard; empty workspaces get the onboarding checklist
        # instead. Seed a contract in the organization the login flow
        # auto-provisioned for this user.
        organization = self._enable_clm_dashboard()
        Contract.objects.create(
            organization=organization,
            title='Layout Contract',
            content='Seed so the dashboard renders its normal state.',
            status='ACTIVE',
            created_by=self.user,
        )
        # Legal Pulse shows a meaningful zero-state instead of a bare "0" —
        # a PENDING contract is needed for "Needs Legal Review" itself
        # (not its empty-state copy) to render.
        Contract.objects.create(
            organization=organization,
            title='Layout Contract Needing Review',
            content='Seed so the Legal Pulse metric has a nonzero value.',
            status='IN_PROGRESS',
            created_by=self.user,
        )
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'Command Center')
        self.assertContains(response, 'Risk findings')
        self.assertContains(response, 'Configure monitoring')
        self.assertContains(response, 'Configure tracking')
        self.assertContains(response, 'Top priority')
        self.assertContains(response, 'Layout Contract')
        self.assertContains(response, 'cc-v3-top-priority-insights')
        self.assertContains(response, 'Blocking issue')
        self.assertContains(response, 'Recommended action')

    def test_dashboard_right_rail(self):
        # The right rail (attention / AI insight / activity) only renders
        # on the populated dashboard; an empty workspace gets the
        # onboarding checklist instead.
        organization = self._enable_clm_dashboard()
        Contract.objects.create(
            organization=organization,
            title='Right Rail Contract',
            content='Seed so the dashboard renders its normal state.',
            status='ACTIVE',
            created_by=self.user,
        )
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'Action queue')
        self.assertContains(response, 'Upcoming Deadlines')
        self.assertContains(response, 'Recent Matters')

    def tearDown(self):
        if 'FEATURE_REDESIGN' in os.environ:
            del os.environ['FEATURE_REDESIGN']
