"""Tests for the Privacy & Compliance dashboard layout convergence pass.

Covers: the shared PageHeader (.arch-header) replacing the page-local
.page-header, the compact metric strip (.kpi-strip) replacing the oversized
default .kpi-card grid, and the Compliance Operations table replacing the
second card grid (which previously left "Ethical Walls" as a hollow card
with no metric).
"""
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from contracts.models import EthicalWall, Organization, OrganizationMembership


class PrivacyDashboardLayoutTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Layout Firm', slug='layout-firm')
        self.user = User.objects.create_user(username='layout_user', password='testpass123', email='layout@example.com')
        OrganizationMembership.objects.create(
            organization=self.organization, user=self.user,
            role=OrganizationMembership.Role.ADMIN, is_active=True,
        )
        self.client = Client()
        self.client.login(username='layout_user', password='testpass123')

    def _get(self):
        response = self.client.get(reverse('contracts:privacy_dashboard'))
        self.assertEqual(response.status_code, 200)
        return response

    def test_uses_shared_page_header_not_legacy_page_header(self):
        response = self._get()
        html = response.content.decode('utf-8')
        self.assertIn('arch-header', html)
        self.assertIn('Privacy &amp; Compliance', html)
        # The legacy per-page header classes should no longer be present on
        # this template — it now shares the same PageHeader pattern as
        # Dashboard/Repository instead of inventing its own.
        self.assertNotIn('page-header"', html)

    def test_metric_strip_is_compact_not_default_kpi_grid(self):
        response = self._get()
        html = response.content.decode('utf-8')
        self.assertIn('kpi-strip', html)

    def test_page_shell_uses_fluid_width(self):
        response = self._get()
        html = response.content.decode('utf-8')
        self.assertIn('page-wrap-fluid', html)

    def test_compliance_operations_table_replaces_second_card_grid(self):
        response = self._get()
        html = response.content.decode('utf-8')
        self.assertIn('Compliance Operations', html)
        for area in ('Retention Policies', 'Legal Holds', 'Ethical Walls'):
            self.assertIn(area, html)
        # Only one dash-grid remains (the 4-metric strip) — the former
        # second dash-grid-3 card grid (with a valueless Ethical Walls card)
        # is gone in favor of the operations table above. (`.dash-grid-3` as
        # a CSS rule still legitimately exists in base.html's shared
        # stylesheet for other pages, so check the class *usage* on an
        # element, not the substring anywhere in the response.)
        self.assertNotIn('dash-grid dash-grid-3', html)
        self.assertNotIn('class="dash-grid-3', html)

    def test_ethical_wall_count_is_scoped_to_organization(self):
        other_org = Organization.objects.create(name='Other Firm', slug='other-firm')
        EthicalWall.objects.create(organization=self.organization, name='In-scope wall', is_active=True)
        EthicalWall.objects.create(organization=other_org, name='Other org wall', is_active=True)

        response = self._get()
        self.assertEqual(response.context['ethical_wall_count'], 1)

    def test_recent_dsars_empty_state_renders_instead_of_disappearing(self):
        response = self._get()
        html = response.content.decode('utf-8')
        self.assertIn('No DSAR requests recorded yet.', html)
