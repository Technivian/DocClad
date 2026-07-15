"""Sidebar nav previously grouped Budget & Capacity under an "ADMIN" section
even though any active org member can access it (see
tests/test_budget_access_policy.py) — misleadingly implying admin-only
access. Budget & Capacity now lives under its own "PLANNING" section;
"ADMIN" is reserved for Settings and the org-admin-only Escrow (trust
accounts) link, which is now also hidden from non-admin/owner members in
the nav itself (it already 403'd server-side; this just stops advertising a
link a member can't use). No RBAC or view-level permission changed — only
nav markup + a CAN_MANAGE_ORGANIZATION context flag."""
from django.contrib.auth import get_user_model
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from contracts.models import Organization, OrganizationMembership

User = get_user_model()


class NavSectionGroupingTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Nav Grouping Org', slug='nav-grouping-org')

        self.member_user = User.objects.create_user(username='nav_member', password='testpass123!')
        OrganizationMembership.objects.create(
            organization=self.org, user=self.member_user,
            role=OrganizationMembership.Role.MEMBER, is_active=True,
        )

        self.admin_user = User.objects.create_user(username='nav_admin', password='testpass123!')
        OrganizationMembership.objects.create(
            organization=self.org, user=self.admin_user,
            role=OrganizationMembership.Role.ADMIN, is_active=True,
        )

        self.owner_user = User.objects.create_user(username='nav_owner', password='testpass123!')
        OrganizationMembership.objects.create(
            organization=self.org, user=self.owner_user,
            role=OrganizationMembership.Role.OWNER, is_active=True,
        )

        self.member_client = TestClient()
        self.member_client.login(username='nav_member', password='testpass123!')
        self.admin_client = TestClient()
        self.admin_client.login(username='nav_admin', password='testpass123!')
        self.owner_client = TestClient()
        self.owner_client.login(username='nav_owner', password='testpass123!')

    def test_specialist_tools_are_not_in_standard_nav_for_member(self):
        response = self.member_client.get(reverse('dashboard'))
        content = response.content.decode()
        self.assertNotIn('Budget &amp; Capacity', content)
        self.assertNotIn('Escrow', content)

    def test_member_does_not_see_escrow_nav_link(self):
        response = self.member_client.get(reverse('dashboard'))
        self.assertNotContains(response, 'Escrow')

    def test_admin_does_not_see_escrow_nav_link(self):
        response = self.admin_client.get(reverse('dashboard'))
        self.assertNotContains(response, 'Escrow')

    def test_owner_does_not_see_escrow_nav_link(self):
        response = self.owner_client.get(reverse('dashboard'))
        self.assertNotContains(response, 'Escrow')

    def test_member_does_not_see_budget_nav_link(self):
        response = self.member_client.get(reverse('dashboard'))
        self.assertNotContains(response, 'Budget &amp; Capacity')

    def test_settings_link_still_present_for_all_roles(self):
        for client in (self.member_client, self.admin_client, self.owner_client):
            response = client.get(reverse('dashboard'))
            self.assertContains(response, 'Settings')

    # ---- server-side enforcement is independent of nav visibility ----

    def test_member_hitting_escrow_url_directly_is_still_403(self):
        response = self.member_client.get(reverse('contracts:trust_account_list'))
        self.assertEqual(response.status_code, 403)

    def test_member_hitting_budget_url_directly_still_succeeds(self):
        response = self.member_client.get(reverse('contracts:budget_list'))
        self.assertEqual(response.status_code, 200)
