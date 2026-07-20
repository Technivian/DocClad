"""Standard sidebar coverage.

The legacy law-firm sidebar has been removed from the shell. Workspace mode
no longer exposes a second navigation system; old-layout pages remain direct
URL surfaces until rebuilt, but they are not product navigation.
"""
from django.contrib.auth import get_user_model
from django.test import Client as TestClient
from django.test import TestCase, override_settings
from django.urls import reverse

from contracts.models import (
    Contract,
    Counterparty,
    DPAReviewPack,
    Organization,
    OrganizationMembership,
)
from contracts.nav_config import nav_item_labels

User = get_user_model()

STANDARD_NAV_LABELS = [
    'Command Center',
    'My Work',
    'Contracts',
    'New Contract',
    'Reviews & Approvals',
    'Privacy Reviews',
    'Obligations',
    'Templates & Playbooks',
    'Workflow Designer',
]

STANDARD_NAV_LABELS_HTML = [
    'Command Center',
    'My Work',
    'Contracts',
    'New Contract',
    'Reviews &amp; Approvals',
    'Privacy Reviews',
    'Obligations',
    'Templates &amp; Playbooks',
    'Workflow Designer',
]

STANDARD_SECTION_LABELS = [
    'Workspace',
    'Create',
    'Governance',
    'Configuration',
]

MEMBER_NAV_LABELS = [
    'Command Center',
    'My Work',
    'Contracts',
    'New Contract',
    'Reviews & Approvals',
    'Privacy Reviews',
    'Obligations',
]

MEMBER_NAV_LABELS_HTML = [
    'Command Center',
    'My Work',
    'Contracts',
    'New Contract',
    'Reviews &amp; Approvals',
    'Privacy Reviews',
    'Obligations',
]

OLD_LAYOUT_NAV_LABELS = [
    'Escrow',            # Trust Accounts
    'Budget &amp; Capacity',
    'Signature Requests',
    'Tasks',
    'Repository',
    '>Approvals<',
    'Compliance',
    '>Privacy<',
    'Audit Trail',
    'Documents',
    'Clients',
    'Counterparties',
    'Matters',
    '>Playbooks<',
    'Reports',
    'Upload &amp; Review',
    'DPA Reviews',
]


def sidebar_html(response):
    content = response.content.decode()
    start = content.index('<nav class="dc-ds-shell__sidebar"')
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
        self.assertEqual(nav_item_labels(self.org, self.owner), STANDARD_NAV_LABELS)
        response = self.owner_client.get(reverse('dashboard'))
        content = sidebar_html(response)
        positions = []
        for label in STANDARD_NAV_LABELS_HTML:
            self.assertIn(label, content, msg=f'Missing standard nav label: {label}')
            positions.append(content.index(label))
        self.assertEqual(positions, sorted(positions), 'standard nav items are out of order')

    def test_section_labels_are_present(self):
        response = self.owner_client.get(reverse('dashboard'))
        content = sidebar_html(response)
        for section in STANDARD_SECTION_LABELS:
            self.assertIn(f'>{section}<', content)

    def test_old_layout_pages_are_not_primary_nav_items(self):
        response = self.owner_client.get(reverse('dashboard'))
        content = sidebar_html(response)
        for label in OLD_LAYOUT_NAV_LABELS:
            self.assertNotIn(label, content, msg=f'{label} should not render as a primary nav item')

    def test_upload_and_review_removed_from_sidebar_but_reachable_from_new_contract(self):
        response = self.owner_client.get(reverse('dashboard'))
        content = sidebar_html(response)
        self.assertNotIn('Upload &amp; Review', content)
        self.assertNotIn(reverse('contracts:upload_signed_contract'), content)

        picker = self.owner_client.get(reverse('contracts:contract_template_picker'))
        self.assertEqual(picker.status_code, 200)
        self.assertContains(picker, reverse('contracts:upload_signed_contract'))
        self.assertContains(picker, 'Upload &amp; review agreement')

        upload = self.owner_client.get(reverse('contracts:upload_signed_contract'))
        self.assertEqual(upload.status_code, 200)

    def test_settings_stays_in_profile_menu_not_sidebar(self):
        response = self.owner_client.get(reverse('dashboard'))
        body = response.content.decode()
        content = sidebar_html(response)
        self.assertNotIn('>Settings<', content)
        self.assertNotIn(reverse('settings_hub'), content)
        self.assertIn('role="menuitem">Settings</a>', body)
        self.assertIn(reverse('settings_hub'), body)

    def test_member_sees_workspace_and_governance_without_configuration(self):
        self.assertEqual(nav_item_labels(self.org, self.member), MEMBER_NAV_LABELS)
        response = self.member_client.get(reverse('dashboard'))
        content = sidebar_html(response)
        for label in MEMBER_NAV_LABELS_HTML:
            self.assertIn(label, content)
        self.assertNotIn('Templates &amp; Playbooks', content)
        self.assertNotIn('Workflow Designer', content)

    def test_command_center_links_to_dashboard(self):
        response = self.owner_client.get(reverse('dashboard'))
        content = sidebar_html(response)
        href = reverse('dashboard')
        self.assertRegex(content, rf'<a href="{href}" class="nav-link[^\"]*\bactive\b')
        self.assertIn('Command Center', content)

    def test_profile_menu_exposes_settings_and_operations_for_owner(self):
        response = self.owner_client.get(reverse('dashboard'))
        body = response.content.decode()
        self.assertIn('href="' + reverse('profile') + '"', body)
        self.assertIn('profile-menu-header__name', body)
        self.assertNotIn('role="menuitem">Account</a>', body)
        self.assertIn('role="menuitem">Settings</a>', body)
        self.assertIn('role="menuitem">Operations</a>', body)
        self.assertIn('role="menuitem">Notifications</a>', body)
        self.assertNotIn('nav-icon-svg--admin', sidebar_html(response))

    def test_sidebar_uses_distinct_nav_icons(self):
        response = self.owner_client.get(reverse('dashboard'))
        content = sidebar_html(response)
        for class_name in (
            'nav-icon-svg--dashboard',
            'nav-icon-svg--my-work',
            'nav-icon-svg--new-contract',
            'nav-icon-svg--contracts',
            'nav-icon-svg--reviews-approvals',
            'nav-icon-svg--privacy-reviews',
            'nav-icon-svg--obligations',
            'nav-icon-svg--templates-playbooks',
            'nav-icon-svg--workflows',
        ):
            self.assertIn(class_name, content)
        self.assertNotIn('nav-icon-svg--upload-review', content)
        self.assertNotIn('nav-icon-svg--admin', content)
        self.assertNotIn('nav-icon-svg--settings', content)

    def test_collapsed_tooltips_present_on_nav_items(self):
        response = self.owner_client.get(reverse('dashboard'))
        content = sidebar_html(response)
        for label in STANDARD_NAV_LABELS_HTML:
            self.assertIn(f'title="{label}"', content)
            self.assertIn(f'aria-label="{label}"', content)

    def test_workflow_designer_links_to_active_workflows_hub(self):
        response = self.owner_client.get(reverse('dashboard'))
        content = sidebar_html(response)
        href = reverse('contracts:workflow_dashboard')
        self.assertIn(f'href="{href}"', content)
        self.assertIn('Workflow Designer', content)
        self.assertNotIn('Workflow Operations', content)

    def test_workflow_designer_active_on_routing_rules(self):
        response = self.owner_client.get(reverse('contracts:approval_rule_list'))
        content = sidebar_html(response)
        href = reverse('contracts:workflow_dashboard')
        self.assertRegex(content, rf'<a href="{href}" class="nav-link[^\"]*\bactive\b')
        self.assertIn('Workflow Designer', content)

    def test_workflow_designer_active_on_templates(self):
        response = self.owner_client.get(reverse('contracts:workflow_template_list'))
        content = sidebar_html(response)
        href = reverse('contracts:workflow_dashboard')
        self.assertRegex(content, rf'<a href="{href}" class="nav-link[^\"]*\bactive\b')
        self.assertIn('Workflow Designer', content)

    def test_reviews_approvals_active_on_approval_queue(self):
        response = self.owner_client.get(reverse('contracts:approval_request_list'))
        content = sidebar_html(response)
        href = reverse('contracts:approval_request_list')
        self.assertRegex(content, rf'<a href="{href}" class="nav-link[^\"]*\bactive\b')
        designer_href = reverse('contracts:workflow_dashboard')
        self.assertNotRegex(content, rf'<a href="{designer_href}" class="nav-link[^\"]*\bactive\b')

    def test_my_work_route_and_active_state(self):
        response = self.owner_client.get(reverse('contracts:my_work'))
        self.assertEqual(response.status_code, 200)
        content = sidebar_html(response)
        href = reverse('contracts:my_work')
        self.assertRegex(content, rf'<a href="{href}" class="nav-link[^\"]*\bactive\b')
        self.assertContains(response, 'My Work')

    def test_templates_playbooks_hub_owner_only(self):
        owner_response = self.owner_client.get(reverse('contracts:templates_playbooks_hub'))
        self.assertEqual(owner_response.status_code, 200)
        self.assertContains(owner_response, 'Templates &amp; Playbooks')
        self.assertContains(
            owner_response,
            'Manage the reusable content, workflow blueprints, and approval policies that govern contract creation and review.',
        )
        self.assertContains(owner_response, 'Clause Library')
        self.assertContains(owner_response, 'Privacy Playbooks')
        self.assertContains(owner_response, 'Workflow Templates')
        self.assertContains(owner_response, 'Approval Policies')
        self.assertNotContains(owner_response, 'DPA playbooks')
        self.assertNotContains(owner_response, 'Approval thresholds')
        self.assertContains(owner_response, reverse('contracts:clause_template_list'))
        self.assertContains(owner_response, reverse('contracts:dpa_playbook_list'))
        self.assertContains(owner_response, reverse('contracts:workflow_template_list'))
        self.assertContains(owner_response, reverse('contracts:approval_rule_list'))
        self.assertContains(owner_response, 'tph-grid')
        self.assertContains(owner_response, 'tph-card__stat')
        self.assertContains(owner_response, 'tph-card__icon')
        self.assertContains(owner_response, 'clauses')
        self.assertContains(owner_response, 'positions')
        self.assertContains(owner_response, 'templates')
        self.assertContains(owner_response, 'policies')
        body = owner_response.content.decode()
        self.assertIn('M14 2H6a2', body)  # file-text glyph
        self.assertIn('M8 11V7a4', body)  # lock glyph
        self.assertNotContains(owner_response, 'Coming soon')
        self.assertNotContains(owner_response, 'N/A')
        content = sidebar_html(owner_response)
        href = reverse('contracts:templates_playbooks_hub')
        self.assertRegex(content, rf'<a href="{href}" class="nav-link[^\"]*\bactive\b')

        member_response = self.member_client.get(reverse('contracts:templates_playbooks_hub'))
        self.assertEqual(member_response.status_code, 403)

    def test_new_contract_links_to_contract_type_picker(self):
        response = self.owner_client.get(reverse('dashboard'))
        content = sidebar_html(response)
        href = reverse('contracts:contract_template_picker')
        self.assertIn(f'href="{href}"', content)

    def test_new_contract_request_has_one_active_navigation_item(self):
        response = self.owner_client.get(reverse('contracts:contract_create'))
        content = sidebar_html(response)

        new_contract_href = reverse('contracts:contract_template_picker')
        contracts_href = reverse('contracts:repository')
        self.assertRegex(content, rf'<a href="{new_contract_href}" class="nav-link[^\"]*\bactive\b')
        self.assertNotRegex(content, rf'<a href="{contracts_href}" class="nav-link[^\"]*\bactive\b')

    def test_upload_keeps_new_contract_active(self):
        response = self.owner_client.get(reverse('contracts:upload_signed_contract'))
        content = sidebar_html(response)
        new_contract_href = reverse('contracts:contract_template_picker')
        self.assertRegex(content, rf'<a href="{new_contract_href}" class="nav-link[^\"]*\bactive\b')

    def test_contracts_links_to_the_canonical_repository(self):
        response = self.owner_client.get(reverse('dashboard'))
        content = sidebar_html(response)
        self.assertIn(f'href="{reverse("contracts:repository")}"', content)
        self.assertNotIn(f'href="{reverse("contracts:contract_list")}"', content)

    def test_privacy_reviews_active_on_list(self):
        response = self.owner_client.get(reverse('contracts:dpa_review_pack_list'))
        content = sidebar_html(response)
        href = reverse('contracts:dpa_review_pack_list')
        self.assertRegex(content, rf'<a href="{href}" class="nav-link[^\"]*\bactive\b')
        self.assertIn('Privacy Reviews', content)
        self.assertNotIn('DPA Reviews', content)

    @override_settings(CONTROLLED_PILOT_ENABLED=True)
    def test_pilot_hides_governance_and_configuration(self):
        labels = nav_item_labels(self.org, self.owner)
        self.assertEqual(
            labels,
            ['Command Center', 'My Work', 'Contracts', 'New Contract', 'Reviews & Approvals'],
        )
        response = self.owner_client.get(reverse('dashboard'))
        content = sidebar_html(response)
        self.assertNotIn('Privacy Reviews', content)
        self.assertNotIn('Obligations', content)
        self.assertNotIn('Workflow Designer', content)
        self.assertNotIn('Templates &amp; Playbooks', content)


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
        self.assertContains(response, 'Privacy Reviews')

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
        self.assertContains(response, 'Reviews &amp; Approvals')
