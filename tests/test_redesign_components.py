
import os

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from contracts.models import Budget, Client as ClientModel, Contract, Matter, Organization, OrganizationMembership, TrademarkRequest


class RedesignComponentsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com',
        )
        self.organization = Organization.objects.create(
            name='Test Firm',
            slug='test-firm',
            workspace_mode=Organization.WorkspaceMode.IN_HOUSE_CLM,
        )
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.user,
            role=OrganizationMembership.Role.OWNER,
            is_active=True,
        )
        self.client.login(username='testuser', password='testpass123')
        os.environ['FEATURE_REDESIGN'] = 'true'

    def _enable_clm_dashboard(self):
        self.organization.workspace_mode = Organization.WorkspaceMode.IN_HOUSE_CLM
        self.organization.save(update_fields=['workspace_mode'])

    def test_dashboard_component_labels(self):
        # The priority action strip and the workflow queue render on the
        # populated dashboard; empty workspaces get the onboarding checklist
        # instead. The queue tabs (In Progress / Waiting on Me / Needs
        # Review / Renewals / Completed) are the primary object on the page.
        Contract.objects.create(
            organization=self.organization,
            title='Component Label Contract',
            content='Seed so the dashboard renders its normal state.',
            status='ACTIVE',
            created_by=self.user,
        )
        # Legal Pulse shows a meaningful zero-state instead of a bare "0" —
        # a PENDING contract is needed for "Needs Legal Review" itself
        # (not its empty-state copy) to render.
        Contract.objects.create(
            organization=self.organization,
            title='Component Label Contract Needing Review',
            content='Seed so the Legal Pulse metric has a nonzero value.',
            status='IN_PROGRESS',
            created_by=self.user,
        )
        self._enable_clm_dashboard()
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Risk findings')
        self.assertContains(response, 'Component Label Contract')
        self.assertContains(response, 'Top priority')
        self.assertContains(response, 'Governance controls')
        self.assertContains(response, 'Action queue')

    def test_contracts_list_core_components(self):
        Contract.objects.create(
            organization=self.organization,
            title='Test Contract',
            content='Test content',
            status=Contract.Status.IN_PROGRESS,
            created_by=self.user,
        )

        response = self.client.get(reverse('contracts:contract_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Contract')
        self.assertContains(response, 'Search active contract work...')
        self.assertContains(response, 'All')
        self.assertContains(response, 'New Contract')

    def test_navigation_structure(self):
        # The legacy sectioned sidebar has been removed from the product
        # shell; every organization sees the same compact standard nav.
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Command Center')
        self.assertContains(response, 'New Contract')
        self.assertContains(response, 'Contracts')
        self.assertContains(response, 'Privacy Reviews')
        self.assertContains(response, 'Obligations')
        self.assertContains(response, 'My Work')
        self.assertContains(response, 'Reviews &amp; Approvals')
        self.assertContains(response, 'role="menuitem">Settings</a>')
        self.assertNotContains(response, 'RISK &amp; COMPLIANCE')
        self.assertNotContains(response, 'Upload &amp; Review')
        self.assertNotContains(response, 'DPA Reviews')

    def test_accessibility_and_responsive_markers(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'title="Search"')
        self.assertContains(response, 'css/command-center.css')
        self.assertContains(response, 'aria-label="Operational queues"')
        self.assertContains(response, 'aria-label="Governance controls"')

    def test_budget_list_matches_dashboard_style(self):
        Budget.objects.create(
            organization=self.organization,
            year=2025,
            quarter=Budget.Quarter.Q3,
            department='Legal Ops',
            allocated_amount='120000.00',
            description='Core operations budget',
            created_by=self.user,
        )

        response = self.client.get(reverse('contracts:budget_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Budgets')
        self.assertContains(response, 'Search budgets by department or description...')
        self.assertContains(response, 'New Budget')
        self.assertContains(response, 'Legal Ops')

    def test_trademark_request_list_uses_real_model_fields(self):
        client_record = ClientModel.objects.create(
            organization=self.organization,
            name='Acme Client',
            created_by=self.user,
        )
        matter = Matter.objects.create(
            organization=self.organization,
            matter_number='TM-0001',
            title='Brand Protection',
            client=client_record,
            created_by=self.user,
        )
        TrademarkRequest.objects.create(
            mark_text='CLMONE MARK',
            description='Primary trademark filing for the platform.',
            goods_services='Legal software services',
            filing_basis='Use in commerce',
            status=TrademarkRequest.Status.PENDING,
            client=client_record,
            matter=matter,
        )

        response = self.client.get(reverse('contracts:trademark_request_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Trademark Requests')
        self.assertContains(response, 'Search marks, clients, matters, or descriptions...')
        self.assertContains(response, 'CLMONE MARK')
        self.assertContains(response, 'Brand Protection')
        self.assertContains(response, 'Use in commerce')

    def test_repository_page_preserves_js_hooks_in_new_shell(self):
        response = self.client.get(reverse('contracts:repository'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Contracts')
        self.assertContains(response, 'id="search-input"')
        self.assertContains(response, 'id="sort-select"')
        self.assertContains(response, 'id="contracts-table"')
        self.assertContains(response, 'id="details-drawer"')

    def test_global_search_uses_case_flow_semantics(self):
        contract = Contract.objects.create(
            organization=self.organization,
            title='Case Search Contract',
            content='Searchable contract content',
            status=Contract.Status.ACTIVE,
            created_by=self.user,
        )

        response = self.client.get(reverse('contracts:global_search'), {'q': 'Case Search'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Search across contracts, matters, documents, and task signals with relevance ranking.')
        self.assertContains(response, 'Search contracts and workflows…')
        self.assertContains(response, 'Cases (1)')
        self.assertContains(response, contract.title)

    def tearDown(self):
        if 'FEATURE_REDESIGN' in os.environ:
            del os.environ['FEATURE_REDESIGN']
