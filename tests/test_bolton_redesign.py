
import os
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from contracts.models import Contract, Organization, OrganizationMembership


class BoltonRedesignTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com'
        )
        self.organization = Organization.objects.create(name='Bolton Firm', slug='bolton-firm')
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.user,
            role=OrganizationMembership.Role.OWNER,
            is_active=True,
        )
        self.client.login(username='testuser', password='testpass123')
        
        # Set feature flag
        os.environ['FEATURE_REDESIGN'] = 'true'

    def _enable_clm_dashboard(self):
        self.organization.workspace_mode = Organization.WorkspaceMode.IN_HOUSE_CLM
        self.organization.save(update_fields=['workspace_mode'])

    def _seed_contract(self):
        """The KPI strip and portfolio panels only render once the workspace
        has data; empty workspaces get the onboarding checklist instead."""
        return Contract.objects.create(
            organization=self.organization,
            title='Seeded Contract',
            content='Seeded content',
            status='ACTIVE',
            created_by=self.user,
        )

    def test_dashboard_kpi_cards(self):
        self._seed_contract()
        self._enable_clm_dashboard()
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, 'Needs Legal Review')
        self.assertContains(response, 'Exposure Review')
        self.assertContains(response, 'Blocked')
        self.assertContains(response, 'Notice / Renewal Risk')
        self.assertContains(response, 'Priority Legal Work Queue')

    def test_dashboard_empty_state_hides_kpis(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Start building your legal workspace')
        # The CSS definitions always mention the priority-strip classes;
        # assert on the rendered markup instead: no priority card labels in
        # the onboarding state.
        self.assertNotContains(response, 'Needs Legal Review')
        self.assertNotContains(response, 'Awaiting Approval')

    def test_dashboard_container_constraint(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'max-width: 1400px')

    def test_dashboard_top_bar(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, 'title="Search"')
        self.assertContains(response, 'title="Toggle theme"')
        self.assertContains(response, 'title="Notifications"')
        self.assertContains(response, 'New Contract')
        self.assertContains(response, 'Sign out')

    def test_dashboard_panels(self):
        # The dashboard is a legal-ops command desk: a priority action strip,
        # a workflow queue (saved-view tabs + a single queue table), a
        # restrained lifecycle status overview, and a right rail (deadlines/
        # risk watch/activity). The old placeholder-only "Recent Contracts" /
        # "Case Portfolio" panels were removed as part of that conversion.
        self._seed_contract()
        self._enable_clm_dashboard()
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Priority Legal Work Queue')
        self.assertContains(response, 'Lifecycle Status Overview')
        self.assertContains(response, 'Top Review Blockers')
        self.assertContains(response, 'Queue Health')
        self.assertContains(response, 'Upcoming Obligations')
        self.assertContains(response, 'Recent Review Memos')

    def test_contracts_table_structure(self):
        Contract.objects.create(
            organization=self.organization,
            title='Test Contract',
            content='Test content',
            status='DRAFT',
            created_by=self.user
        )

        response = self.client.get(reverse('contracts:contract_list'))
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, 'Contract')
        self.assertContains(response, 'Counterparty')
        self.assertContains(response, 'Stage')
        self.assertContains(response, 'Last activity')
        self.assertContains(response, 'Risk')
        self.assertContains(response, 'Test Contract')

    def test_contracts_list_filters_and_actions(self):
        response = self.client.get(reverse('contracts:contract_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Search active contract work...')
        self.assertContains(response, 'All')
        self.assertContains(response, 'Search')
        self.assertContains(response, 'New Contract')

    def test_accessibility_features(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, 'title="Search"')
        self.assertContains(response, 'title="Toggle theme"')
        self.assertContains(response, 'title="Search"')
        self.assertContains(response, 'type="submit"')

    def test_typography_and_spacing(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        # Inter is the sole product typeface per the approved brand kit and
        # the "Ledger" design system (DOCCLAD_DESIGN_SYSTEM.md) — Manrope/Sora
        # were retired in the 2026-07-05 rebrand.
        self.assertContains(response, "font-family: 'Inter'")
        self.assertNotContains(response, "font-family: 'Manrope'")
        self.assertContains(response, 'dash-grid')
        self.assertContains(response, 'gap: 20px')

    def tearDown(self):
        """Clean up environment variables"""
        if 'FEATURE_REDESIGN' in os.environ:
            del os.environ['FEATURE_REDESIGN']
