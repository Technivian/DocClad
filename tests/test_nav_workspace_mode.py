"""Standard sidebar coverage.

The legacy law-firm sidebar has been removed from the shell. Workspace mode
no longer exposes a second navigation system; old-layout pages remain direct
URL surfaces until rebuilt, but they are not product navigation.
"""
from django.contrib.auth import get_user_model
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from contracts.models import (
    Contract,
    Counterparty,
    DPAReviewPack,
    Organization,
    OrganizationMembership,
)

User = get_user_model()

STANDARD_NAV_LABELS = [
    'Command Center',
    'New Contract',
    'Contracts',
    'DPA Reviews',
    'Obligations',
    'Admin',
]

OLD_LAYOUT_NAV_LABELS = [
    'Escrow',            # Trust Accounts
    'Budget &amp; Capacity',
    'Workflows',
    'Signature Requests',
    'Tasks',
    'Repository',
    'Approvals',
    'Compliance',
    'Privacy',
    'Audit Trail',
    'Documents',
    'Clients',
    'Counterparties',
    'Matters',
    'Playbooks',
    'Reports',
]


def sidebar_html(response):
    content = response.content.decode()
    start = content.index('<nav class="sidebar-container"')
    end = content.index('</nav>', start)
    return content[start:end]


class WorkspaceModeFieldTests(TestCase):
    def test_default_is_in_house_clm(self):
        org = Organization.objects.create(name='Default Mode Org', slug='default-mode-org')
        self.assertEqual(org.workspace_mode, Organization.WorkspaceMode.IN_HOUSE_CLM)


class WorkspaceModeSettingsExposureTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Settings Org', slug='settings-org')
        self.owner = User.objects.create_user(username='wm_owner', password='testpass123!')
        OrganizationMembership.objects.create(
            organization=self.org, user=self.owner,
            role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        self.member = User.objects.create_user(username='wm_member', password='testpass123!')
        OrganizationMembership.objects.create(
            organization=self.org, user=self.member,
            role=OrganizationMembership.Role.MEMBER, is_active=True,
        )
        self.owner_client = TestClient()
        self.owner_client.login(username='wm_owner', password='testpass123!')
        self.member_client = TestClient()
        self.member_client.login(username='wm_member', password='testpass123!')

    def test_workspace_mode_control_is_not_rendered(self):
        response = self.owner_client.get(reverse('organization_security_settings'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Workspace mode')
        self.assertNotContains(response, 'name="workspace_mode"')
        self.assertNotContains(response, 'Law firm operations')

    def test_workspace_mode_post_cannot_switch_to_legacy_mode(self):
        response = self.owner_client.post(
            reverse('organization_security_settings'),
            {'action': 'save_workspace_mode', 'workspace_mode': 'law_firm_ops'},
        )
        self.assertEqual(response.status_code, 302)
        self.org.refresh_from_db()
        self.assertEqual(self.org.workspace_mode, 'in_house_clm')

    def test_member_cannot_reach_the_settings_page_at_all(self):
        # organization_security_settings is already owner/admin-gated —
        # workspace_mode rides on that existing gate, it doesn't add a new one.
        response = self.member_client.get(reverse('organization_security_settings'))
        self.assertEqual(response.status_code, 403)

    def test_invalid_mode_value_does_not_change_standard_mode(self):
        response = self.owner_client.post(
            reverse('organization_security_settings'),
            {'action': 'save_workspace_mode', 'workspace_mode': 'something_bogus'},
        )
        self.assertEqual(response.status_code, 302)
        self.org.refresh_from_db()
        self.assertEqual(self.org.workspace_mode, 'in_house_clm')


class StandardNavTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            name='Payrollminds', slug='payrollminds', workspace_mode='in_house_clm',
        )
        self.owner = User.objects.create_user(username='clm_owner', password='testpass123!')
        OrganizationMembership.objects.create(
            organization=self.org, user=self.owner,
            role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        self.member = User.objects.create_user(username='clm_member', password='testpass123!')
        OrganizationMembership.objects.create(
            organization=self.org, user=self.member,
            role=OrganizationMembership.Role.MEMBER, is_active=True,
        )
        self.owner_client = TestClient()
        self.owner_client.login(username='clm_owner', password='testpass123!')
        self.member_client = TestClient()
        self.member_client.login(username='clm_member', password='testpass123!')

    def test_standard_primary_nav_items_present_in_order(self):
        response = self.owner_client.get(reverse('dashboard'))
        content = sidebar_html(response)
        positions = []
        for label in STANDARD_NAV_LABELS:
            self.assertIn(label, content, msg=f'Missing standard nav label: {label}')
            positions.append(content.index(label))
        self.assertEqual(positions, sorted(positions), 'standard nav items are out of order')

    def test_old_layout_pages_are_not_primary_nav_items(self):
        response = self.owner_client.get(reverse('dashboard'))
        content = sidebar_html(response)
        for label in OLD_LAYOUT_NAV_LABELS:
            self.assertNotIn(label, content, msg=f'{label} should not render as a primary nav item')

    def test_no_section_headers_in_standard_nav(self):
        response = self.owner_client.get(reverse('dashboard'))
        content = sidebar_html(response)
        for section in ('EXECUTION', 'RISK &amp; COMPLIANCE', 'REFERENCE', 'PLANNING', 'ADMIN'):
            self.assertNotIn(f'>{section}<', content)

    def test_member_also_sees_the_standard_nav(self):
        response = self.member_client.get(reverse('dashboard'))
        content = sidebar_html(response)
        for label in STANDARD_NAV_LABELS:
            self.assertIn(label, content)

    def test_command_center_links_to_dashboard(self):
        response = self.owner_client.get(reverse('dashboard'))
        content = sidebar_html(response)
        href = reverse('dashboard')
        self.assertRegex(content, rf'<a href="{href}" class="nav-link[^\"]*\bactive\b')
        self.assertIn('Command Center', content)

    def test_new_contract_links_to_contract_type_picker(self):
        response = self.owner_client.get(reverse('dashboard'))
        content = sidebar_html(response)
        href = reverse('contracts:contract_template_picker')
        self.assertIn(f'href="{href}"', content)

    def test_contracts_links_to_the_canonical_repository(self):
        response = self.owner_client.get(reverse('dashboard'))
        content = sidebar_html(response)
        self.assertIn(f'href="{reverse("contracts:repository")}"', content)
        self.assertNotIn(f'href="{reverse("contracts:contract_list")}"', content)

    def test_active_state_still_works_in_standard_nav(self):
        response = self.owner_client.get(reverse('contracts:dpa_review_pack_list'))
        content = sidebar_html(response)
        href = reverse('contracts:dpa_review_pack_list')
        self.assertRegex(content, rf'<a href="{href}" class="nav-link[^\"]*\bactive\b')


class SpecialistModuleDirectUrlAccessTests(TestCase):
    """Hidden from nav must not mean blocked — direct URL access for an
    authorized user must be unaffected by workspace_mode."""

    def setUp(self):
        self.org = Organization.objects.create(
            name='Payrollminds Direct', slug='payrollminds-direct', workspace_mode='in_house_clm',
        )
        self.owner = User.objects.create_user(username='direct_owner', password='testpass123!')
        OrganizationMembership.objects.create(
            organization=self.org, user=self.owner,
            role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        self.member = User.objects.create_user(username='direct_member', password='testpass123!')
        OrganizationMembership.objects.create(
            organization=self.org, user=self.member,
            role=OrganizationMembership.Role.MEMBER, is_active=True,
        )
        self.owner_client = TestClient()
        self.owner_client.login(username='direct_owner', password='testpass123!')
        self.member_client = TestClient()
        self.member_client.login(username='direct_member', password='testpass123!')

    def test_owner_can_still_open_trust_accounts_directly(self):
        response = self.owner_client.get(reverse('contracts:trust_account_list'))
        self.assertEqual(response.status_code, 200)

    def test_member_hitting_trust_accounts_directly_is_still_403(self):
        # Same permission behavior as law_firm_ops — mode never changes
        # server-side authorization.
        response = self.member_client.get(reverse('contracts:trust_account_list'))
        self.assertEqual(response.status_code, 403)

    def test_budget_list_still_reachable_directly(self):
        response = self.member_client.get(reverse('contracts:budget_list'))
        self.assertEqual(response.status_code, 200)

    def test_workflow_dashboard_still_reachable_directly(self):
        response = self.member_client.get(reverse('contracts:workflow_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_compliance_checklist_list_still_reachable_directly(self):
        response = self.member_client.get(reverse('contracts:compliance_checklist_list'))
        self.assertEqual(response.status_code, 200)

    def test_settings_hub_still_accessible_to_admins(self):
        response = self.owner_client.get(reverse('settings_hub'))
        self.assertEqual(response.status_code, 200)

    def test_organization_security_settings_still_accessible_to_admins(self):
        response = self.owner_client.get(reverse('organization_security_settings'))
        self.assertEqual(response.status_code, 200)


class DPAAndApprovalBehaviorUnchangedTests(TestCase):
    """Phase 1 is IA-only — this locks down that switching workspace_mode
    does not alter DPA Review Pack or approval logic in any way."""

    def setUp(self):
        self.org = Organization.objects.create(
            name='Payrollminds DPA Check', slug='payrollminds-dpa-check', workspace_mode='in_house_clm',
        )
        self.user = User.objects.create_user(username='dpa_user', password='testpass123!')
        OrganizationMembership.objects.create(
            organization=self.org, user=self.user,
            role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        self.client_ = TestClient()
        self.client_.login(username='dpa_user', password='testpass123!')

        self.counterparty = Counterparty.objects.create(organization=self.org, name='Acme Corp')
        self.contract = Contract.objects.create(
            organization=self.org, title='Acme DPA', content='DPA content',
            status='ACTIVE', created_by=self.user,
        )
        self.review_pack = DPAReviewPack.objects.create(
            organization=self.org, contract=self.contract, counterparty=self.counterparty,
            liability_uncapped=True,
        )

    def test_dpa_review_pack_list_renders_normally_in_in_house_clm(self):
        response = self.client_.get(reverse('contracts:dpa_review_pack_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Acme DPA')

    def test_dpa_review_pack_detail_renders_normally_in_in_house_clm(self):
        response = self.client_.get(reverse('contracts:dpa_review_pack_detail', kwargs={'pk': self.review_pack.pk}))
        self.assertEqual(response.status_code, 200)

    def test_dpa_conflict_detection_service_untouched(self):
        from contracts.services.dpa_conflict import check_cross_document_conflicts
        # Smoke test only — Phase 1 changes zero conflict-detection logic;
        # this just proves the service still imports and runs.
        check_cross_document_conflicts(self.review_pack)

    def test_approval_request_list_renders_normally_in_in_house_clm(self):
        response = self.client_.get(reverse('contracts:approval_request_list'))
        self.assertEqual(response.status_code, 200)
