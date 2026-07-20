
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
        self.organization = Organization.objects.create(
            name='Bolton Firm',
            slug='bolton-firm',
            workspace_mode=Organization.WorkspaceMode.IN_HOUSE_CLM,
        )
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
        # Legal Pulse shows a meaningful zero-state instead of a bare "0" —
        # a PENDING contract is needed for the "Needs Legal Review" metric
        # itself (not its empty-state copy) to render.
        Contract.objects.create(
            organization=self.organization,
            title='Needs Review Contract',
            content='Seeded content',
            status='IN_PROGRESS',
            created_by=self.user,
        )
        self._enable_clm_dashboard()
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, 'Risk findings')
        self.assertContains(response, 'dc-ds-metric__value--clear')
        self.assertContains(response, 'Configure monitoring')
        self.assertContains(response, 'Configure tracking')
        self.assertContains(response, 'Top priority')

    def test_dashboard_empty_state_is_intentional(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Establish your contract portfolio')
        self.assertContains(response, 'Health score unavailable')
        self.assertContains(response, 'Add first contract')
        self.assertContains(response, 'dc-ds-metric__value--clear')
        self.assertContains(response, 'No active issues')

    def test_dashboard_container_constraint(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'css/command-center.css')
        self.assertContains(response, 'class="command-center cc-v3"')

    def test_dashboard_top_bar(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, 'title="Search"')
        self.assertContains(response, 'data-theme="light"')
        self.assertContains(response, 'title="Notifications"')
        self.assertContains(response, 'New Contract')
        self.assertContains(response, 'Sign out')

    def test_dashboard_panels(self):
        # The Command Center dashboard is a legal-ops workbench: a compact
        # Legal Pulse strip, "Today's Legal Priorities" as the primary
        # focus (saved-view tabs + a single filter system + queue table),
        # a restrained lifecycle status overview, a clause/cross-document
        # conflict marker, and a compact right rail (attention / AI insight
        # / activity). The old placeholder-only "Recent Contracts" /
        # "Case Portfolio" panels were removed as part of that conversion.
        self._seed_contract()
        self._enable_clm_dashboard()
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Top priority')
        self.assertContains(response, 'Governance controls')
        self.assertContains(response, 'Action queue')
        self.assertContains(response, 'Upcoming Deadlines')
        self.assertContains(response, 'Recent Matters')

    def test_legal_pulse_zero_states_are_meaningful_not_bare_zeros(self):
        # No seeded data at all: every Legal Pulse metric is zero, so each
        # one must show useful copy instead of a bare "0".
        self._enable_clm_dashboard()
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'dc-ds-metric__value--clear')
        self.assertContains(response, 'Configure tracking')

    def test_priority_queue_empty_state_copy(self):
        self._enable_clm_dashboard()
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Establish your contract portfolio')
        self.assertContains(response, 'Add your first contract to begin monitoring approvals, risks, deadlines, obligations and policy exceptions.')

    def test_single_filter_system_no_duplicate_rows(self):
        # There must be exactly one filter system: saved-view tabs plus a
        # single Filters popover. The old second row of workflow-type
        # summary pills (Privacy reviews / Commercial reviews / ...) that
        # duplicated the saved-view tabs must be gone.
        self._seed_contract()
        self._enable_clm_dashboard()
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'data-filters-popover')
        self.assertNotContains(response, 'data-filters-toggle')
        self.assertContains(response, 'Action queue')
        self.assertNotContains(response, 'Privacy reviews')
        self.assertNotContains(response, 'Commercial reviews')
        self.assertNotContains(response, 'Self-serve ready')

    def test_priority_row_has_detail_sheet_data_and_risk_indicator(self):
        self._seed_contract()
        self._enable_clm_dashboard()
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-risk-score')
        self.assertContains(response, 'Portfolio health score')
        self.assertContains(response, 'Blocking issue')
        self.assertContains(response, 'Top priority')

    def test_contracts_table_structure(self):
        Contract.objects.create(
            organization=self.organization,
            title='Test Contract',
            content='Test content',
            status='IN_PROGRESS',
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
        self.assertContains(response, 'data-command-input')
        self.assertContains(response, 'type="submit"')

    def test_typography_and_spacing(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        # Inter remains the product typeface (Google Fonts load + CSS stacks).
        self.assertContains(response, 'family=Inter')
        self.assertNotContains(response, "font-family: 'Manrope'")
        self.assertContains(response, 'cc-v3')
        self.assertContains(response, 'data-risk-score')

    def tearDown(self):
        """Clean up environment variables"""
        if 'FEATURE_REDESIGN' in os.environ:
            del os.environ['FEATURE_REDESIGN']
