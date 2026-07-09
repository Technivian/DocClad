
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

    def test_base_shell_and_theme_controls(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'DocClad')
        self.assertContains(response, 'data-theme="dark"')
        # Theme toggle is wired via a delegated handler (CSP: no inline onclick).
        self.assertContains(response, 'data-action="toggle-theme"')
        self.assertContains(response, 'js/csp-handlers.js')
        self.assertContains(response, 'title="Search"')

    def test_sidebar_navigation_sections_and_links(self):
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'REFERENCE')
        self.assertContains(response, 'Contract Workspace')
        self.assertContains(response, 'RISK &amp; COMPLIANCE')
        self.assertContains(response, 'Dashboard')
        self.assertContains(response, 'Counterparties')
        self.assertContains(response, 'Workflows')

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
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'Command Center')
        self.assertContains(response, 'Needs Legal Review')
        self.assertContains(response, 'Exposure Review')
        self.assertContains(response, 'Notice / Renewal Risk')
        self.assertContains(response, 'Priority Legal Work Queue')
        self.assertContains(response, 'Layout Contract')

    def test_dashboard_right_rail(self):
        # The right rail (risk intelligence/recommended actions) only
        # renders on the populated dashboard; an empty workspace gets the
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
        self.assertContains(response, 'New Contract')
        self.assertContains(response, 'Upcoming Obligations')
        self.assertContains(response, 'High-Attention Records')
        self.assertContains(response, 'Recent Review Memos')

    def tearDown(self):
        if 'FEATURE_REDESIGN' in os.environ:
            del os.environ['FEATURE_REDESIGN']
