"""Tests for the Repository cleanup gate and contract-first filters."""
import json
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from contracts.models import ApprovalRequest, Contract, Organization, OrganizationMembership


class RepositoryFilterMarkupTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Rail Firm', slug='rail-firm')
        self.user = User.objects.create_user(username='rail_user', password='testpass123', email='rail@example.com')
        OrganizationMembership.objects.create(
            organization=self.organization, user=self.user,
            role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        self.client.login(username='rail_user', password='testpass123')

    def test_filters_drawer_exists_without_duplicated_quick_views(self):
        response = self.client.get(reverse('contracts:repository'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('id="repository-filters"', html)
        self.assertNotIn('data-rail-view=', html)
        self.assertNotIn('Quick views', html)
        self.assertNotIn('dc-ds-scaffold--with-rail', html)
        self.assertIn('Legal Intelligence Hub', html)
        self.assertIn('dc-ds-button--ghost">Legal Intelligence Hub</a>', html)
        self.assertIn('Start new contract', html)
        self.assertNotIn('repo-split-btn', html)
        self.assertNotIn('More new contract options', html)
        self.assertNotIn('Upload existing agreement', html)
        self.assertNotIn('>Add contract<', html)
        self.assertNotIn('>Risks</a>', html)
        self.assertNotIn('>Risk Register</a>', html)

    def test_no_placeholder_assignment_control_is_rendered(self):
        response = self.client.get(reverse('contracts:repository'))
        html = response.content.decode()
        self.assertNotIn('repo-bulk-assign', html)

        js_path = 'theme/static/js/clmone-repository.js'
        with open(js_path) as f:
            js = f.read()
        self.assertNotIn('Bulk assignment will follow the status update path', js)
        self.assertNotIn("getElementById('repo-bulk-assign')", js)

    def test_repository_empty_states_explain_cause_population_and_next_action(self):
        with open('theme/static/js/clmone-repository.js') as source:
            js = source.read()

        for copy in (
            'The current search or filters exclude every contract',
            'Contracts appear here as soon as they match',
            'Clear filters',
            'No governed agreements have been added',
            'Uploaded agreements and governed drafts appear here automatically',
            'Start new contract',
        ):
            self.assertIn(copy, js)

    def test_repository_table_controls_expose_sort_and_column_visibility(self):
        response = self.client.get(reverse('contracts:repository'))
        html = response.content.decode()
        self.assertIn('id="repo-result-count"', html)
        self.assertIn('id="repo-col-toggle"', html)
        self.assertIn('data-sort="title"', html)
        self.assertIn('data-sort="updated"', html)
        self.assertIn('>Owner</', html)
        self.assertIn('>Type</', html)
        self.assertIn('min-width: 1200px', html)
        self.assertIn('position: sticky; left: 44px', html)
        self.assertIn('repo-result-count', html)
        self.assertIn('background: transparent', html)

        with open('theme/static/js/clmone-repository.js') as source:
            js = source.read()
        self.assertIn('applyColumnVisibility', js)
        self.assertIn('updateResultCount', js)
        self.assertIn('repo-contract-title', js)
        self.assertIn('renderStatusMeta', js)
        self.assertIn('repo-status-sep', js)
        self.assertIn('repo-type-label', js)
        self.assertIn('repo-empty-label', js)
        self.assertIn('dc-ds-table-cell-text', js)
        self.assertIn('renderTruncatedText', js)
        self.assertIn('renderRowActions', js)
        self.assertIn('repo-row-menu', js)
        import re
        self.assertIn('activity:false', re.sub(r'\s+', '', js))
        self.assertIn('dc-ds-table--fixed', html)
        self.assertIn('overflow: hidden', html)
        self.assertIn('text-overflow: ellipsis', html)
        self.assertIn('min-width: 145px', html)
        self.assertIn('min-width: 230px', html)
        self.assertIn('padding: 16px 12px', html)
        self.assertNotIn('data-col="next_action"', js)


class RepositoryExpiringFilterTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Rail Filter Firm', slug='rail-filter-firm')
        self.user = User.objects.create_user(username='rail_filter_user', password='testpass123', email='rail_filter@example.com')
        OrganizationMembership.objects.create(
            organization=self.organization, user=self.user,
            role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        self.client.login(username='rail_filter_user', password='testpass123')

    def test_expiring_within_days_filters_to_active_soon_expiring_contracts(self):
        today = date.today()
        Contract.objects.create(
            organization=self.organization, title='Expiring Soon Contract', content='seed',
            status='ACTIVE', end_date=today + timedelta(days=10), created_by=self.user,
        )
        Contract.objects.create(
            organization=self.organization, title='Far Future Contract', content='seed',
            status='ACTIVE', end_date=today + timedelta(days=200), created_by=self.user,
        )
        Contract.objects.create(
            organization=self.organization, title='Expiring Soon But Draft', content='seed',
            status='IN_PROGRESS', end_date=today + timedelta(days=10), created_by=self.user,
        )

        response = self.client.get(reverse('contracts:contracts_api'), {'expiring_within_days': '30'})
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        titles = [c['title'] for c in payload['contracts']]
        self.assertIn('Expiring Soon Contract', titles)
        self.assertNotIn('Far Future Contract', titles)
        self.assertNotIn('Expiring Soon But Draft', titles)

    def test_expiring_within_days_matches_repository_kpi_count(self):
        today = date.today()
        for i in range(3):
            Contract.objects.create(
                organization=self.organization, title=f'Soon Contract {i}', content='seed',
                status='ACTIVE', end_date=today + timedelta(days=5), created_by=self.user,
            )
        page_response = self.client.get(reverse('contracts:repository'))
        api_response = self.client.get(reverse('contracts:contracts_api'), {'expiring_within_days': '30'})
        payload = json.loads(api_response.content)
        self.assertEqual(payload['total_count'], 3)
        # The rail's "30d attention" count (server-rendered KPI) must match
        # what clicking that rail item actually returns — no contradiction
        # between what the rail advertises and what it filters to.
        self.assertEqual(page_response.context['expiring_documents'], 3)

    def test_no_expiring_filter_returns_all_statuses(self):
        Contract.objects.create(
            organization=self.organization, title='Plain Draft', content='seed',
            status='IN_PROGRESS', created_by=self.user,
        )
        response = self.client.get(reverse('contracts:contracts_api'))
        payload = json.loads(response.content)
        titles = [c['title'] for c in payload['contracts']]
        self.assertIn('Plain Draft', titles)

    def test_owner_counterparty_risk_and_approval_filters_are_server_backed(self):
        other_user = User.objects.create_user(username='rail_filter_other', password='testpass123')
        OrganizationMembership.objects.create(
            organization=self.organization, user=other_user,
            role=OrganizationMembership.Role.MEMBER, is_active=True,
        )
        matching = Contract.objects.create(
            organization=self.organization, title='Atlas approval contract', content='seed',
            counterparty='Atlas Workforce B.V.', owner=self.user, risk_level=Contract.RiskLevel.HIGH,
            status=Contract.Status.IN_PROGRESS, created_by=self.user,
        )
        Contract.objects.create(
            organization=self.organization, title='Other contract', content='seed',
            counterparty='Other Co', owner=other_user, risk_level=Contract.RiskLevel.LOW,
            status=Contract.Status.IN_PROGRESS, created_by=other_user,
        )
        ApprovalRequest.objects.create(
            organization=self.organization, contract=matching, approval_step='LEGAL',
            status=ApprovalRequest.Status.PENDING, assigned_to=self.user,
        )

        response = self.client.get(reverse('contracts:contracts_api'), {
            'owner': str(self.user.pk),
            'counterparty': 'Atlas Workforce B.V.',
            'risk_level': Contract.RiskLevel.HIGH,
            'approval_state': ApprovalRequest.Status.PENDING,
        })
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual([row['title'] for row in payload['contracts']], ['Atlas approval contract'])
