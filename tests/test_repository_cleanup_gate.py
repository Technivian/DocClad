"""Tests for the Repository cleanup gate: the saved-view rail becoming
functional (All documents / Active paper / Draft paper / 30d attention),
and removal of the "Assign to Me" placeholder alert.
"""
import json
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from contracts.models import Contract, Organization, OrganizationMembership


class RepositoryRailMarkupTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Rail Firm', slug='rail-firm')
        self.user = User.objects.create_user(username='rail_user', password='testpass123', email='rail@example.com')
        OrganizationMembership.objects.create(
            organization=self.organization, user=self.user,
            role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        self.client.login(username='rail_user', password='testpass123')

    def test_rail_views_are_real_buttons_with_data_attributes(self):
        response = self.client.get(reverse('contracts:repository'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        for key in ('all', 'active', 'draft', 'expiring_30d'):
            self.assertIn(f'data-rail-view="{key}"', html)
        # No more fake "click here and nothing happens" anchors for these views.
        self.assertNotIn('<a href="#" class="views-rail-link', html)

    def test_assign_to_me_is_disabled_with_no_alert_wiring(self):
        response = self.client.get(reverse('contracts:repository'))
        html = response.content.decode()
        self.assertIn('id="repo-bulk-assign"', html)
        self.assertIn('disabled', html.split('id="repo-bulk-assign"')[1].split('>')[0])

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
            'Upload first contract',
            'No views have been saved in this browser',
            'Saved views appear here after you preserve',
            'Save current view',
        ):
            self.assertIn(copy, js)

    def test_repository_selected_controls_use_accessible_pressed_state(self):
        response = self.client.get(reverse('contracts:repository'))
        html = response.content.decode()
        self.assertIn('data-rail-view="all" aria-pressed="true"', html)
        self.assertIn('data-status-filter="" aria-pressed="true"', html)

        with open('theme/static/js/clmone-repository.js') as source:
            js = source.read()
        self.assertIn("setAttribute('aria-pressed'", js)


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
            status='DRAFT', end_date=today + timedelta(days=10), created_by=self.user,
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
            status='DRAFT', created_by=self.user,
        )
        response = self.client.get(reverse('contracts:contracts_api'))
        payload = json.loads(response.content)
        titles = [c['title'] for c in payload['contracts']]
        self.assertIn('Plain Draft', titles)
