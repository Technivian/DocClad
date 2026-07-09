"""Baseline capture of the current ("law_firm_ops") sidebar, taken BEFORE the
Phase 1 nav-config refactor (see docs/product-strategy: Product Coherence
Redesign memo). This test exists to prove the refactor is a pure rendering
change: every nav item, section, ordering, permission gate, and active-state
rule captured here must still hold once base.html loops over
contracts/nav_config.get_nav_for() instead of hardcoded markup.

Do not relax these assertions to make the refactor pass — if the refactor
breaks one, the refactor is wrong, not the test.
"""
from django.contrib.auth import get_user_model
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from contracts.models import Organization, OrganizationMembership

User = get_user_model()

# (label, url_name, section). Order matters — it is the current DOM order.
LAW_FIRM_NAV_ITEMS = [
    ('Dashboard', 'dashboard', None),
    # Intentionally updated post-baseline: New Contract now routes through
    # the Stage 1 contract-type picker (contracts/new/start/) instead of
    # straight to the plain create form, so the sidebar's primary entry
    # point actually surfaces the workflow-first flows (e.g. DPA).
    ('New Contract', 'contracts:contract_template_picker', 'EXECUTION'),
    ('Contract Workspace', 'contracts:contract_list', 'EXECUTION'),
    ('Repository', 'contracts:repository', 'EXECUTION'),
    ('Tasks', 'contracts:legal_task_kanban', 'EXECUTION'),
    ('Workflows', 'contracts:workflow_dashboard', 'EXECUTION'),
    ('Approvals', 'contracts:approval_request_list', 'EXECUTION'),
    ('Signature Requests', 'contracts:signature_request_list', 'EXECUTION'),
    ('Risk Register', 'contracts:risk_log_list', 'RISK &amp; COMPLIANCE'),
    ('Compliance', 'contracts:compliance_checklist_list', 'RISK &amp; COMPLIANCE'),
    ('Privacy', 'contracts:privacy_dashboard', 'RISK &amp; COMPLIANCE'),
    ('Audit Trail', 'contracts:audit_log_list', 'RISK &amp; COMPLIANCE'),
    ('DPA Reviews', 'contracts:dpa_review_pack_list', 'RISK &amp; COMPLIANCE'),
    ('Documents', 'contracts:document_list', 'REFERENCE'),
    ('Counterparties', 'contracts:counterparty_list', 'REFERENCE'),
    ('Clients', 'contracts:client_list', 'REFERENCE'),
    ('Reports', 'contracts:reports_dashboard', 'REFERENCE'),
    ('Budget &amp; Capacity', 'contracts:budget_list', 'PLANNING'),
    ('Escrow', 'contracts:trust_account_list', 'ADMIN'),  # owner/admin only
    ('Settings', 'settings_hub', 'ADMIN'),
]

SECTION_ORDER = ['EXECUTION', 'RISK &amp; COMPLIANCE', 'REFERENCE', 'PLANNING', 'ADMIN']


def sidebar_html(response):
    """Scope assertions to the sidebar <nav> only — several nav labels
    (Reports, Documents, Clients...) also appear in dashboard body content
    (Quick Links, work-queue rows), which would give false-positive ordering
    matches if we searched the whole page."""
    content = response.content.decode()
    start = content.index('<nav class="sidebar-container"')
    end = content.index('</nav>', start)
    return content[start:end]


class NavLawFirmBaselineTests(TestCase):
    """Captured against an org with no workspace_mode set explicitly — proving
    the default (law_firm_ops) renders today's sidebar unchanged."""

    def setUp(self):
        self.org = Organization.objects.create(name='Baseline Firm', slug='baseline-firm')

        self.owner = User.objects.create_user(username='baseline_owner', password='testpass123!')
        OrganizationMembership.objects.create(
            organization=self.org, user=self.owner,
            role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        self.member = User.objects.create_user(username='baseline_member', password='testpass123!')
        OrganizationMembership.objects.create(
            organization=self.org, user=self.member,
            role=OrganizationMembership.Role.MEMBER, is_active=True,
        )

        self.owner_client = TestClient()
        self.owner_client.login(username='baseline_owner', password='testpass123!')
        self.member_client = TestClient()
        self.member_client.login(username='baseline_member', password='testpass123!')

    def test_every_current_url_name_still_resolves(self):
        """Route-existence check — doubles as a break-the-glass alarm if a
        route is ever renamed/removed."""
        for label, url_name, _section in LAW_FIRM_NAV_ITEMS:
            reverse(url_name)  # raises NoReverseMatch on failure

    def test_owner_sees_every_nav_item_in_order(self):
        response = self.owner_client.get(reverse('dashboard'))
        content = sidebar_html(response)
        positions = []
        for label, _url_name, _section in LAW_FIRM_NAV_ITEMS:
            self.assertIn(label, content, msg=f'Missing nav label: {label}')
            positions.append(content.index(label))
        self.assertEqual(positions, sorted(positions), 'Nav items are out of order')

    def test_section_headers_present_in_order(self):
        response = self.owner_client.get(reverse('dashboard'))
        content = sidebar_html(response)
        positions = [content.index(f'>{s}<') for s in SECTION_ORDER]
        self.assertEqual(positions, sorted(positions), 'Section headers are out of order')

    def test_items_render_under_their_section(self):
        response = self.owner_client.get(reverse('dashboard'))
        content = sidebar_html(response)
        section_positions = {s: content.index(f'>{s}<') for s in SECTION_ORDER}
        for label, _url_name, section in LAW_FIRM_NAV_ITEMS:
            item_pos = content.index(label)
            if section is None:
                # Dashboard renders before any section header.
                self.assertLess(item_pos, section_positions['EXECUTION'])
                continue
            self.assertGreater(item_pos, section_positions[section], f'{label} should render after >{section}<')
            later_sections = SECTION_ORDER[SECTION_ORDER.index(section) + 1:]
            for later in later_sections:
                self.assertLess(item_pos, section_positions[later], f'{label} should render before >{later}<')

    def test_member_does_not_see_escrow(self):
        response = self.member_client.get(reverse('dashboard'))
        self.assertNotContains(response, 'Escrow')

    def test_owner_sees_escrow(self):
        response = self.owner_client.get(reverse('dashboard'))
        self.assertContains(response, 'Escrow')

    def test_member_sees_every_non_admin_item(self):
        response = self.member_client.get(reverse('dashboard'))
        content = response.content.decode()
        for label, _url_name, section in LAW_FIRM_NAV_ITEMS:
            if label == 'Escrow':
                continue
            self.assertIn(label, content, msg=f'Member is missing nav label: {label}')

    def test_active_state_on_dashboard(self):
        response = self.owner_client.get(reverse('dashboard'))
        content = response.content.decode()
        href = reverse('dashboard')
        self.assertRegex(content, rf'<a href="{href}" class="nav-link active"')

    def test_active_state_on_contract_detail_highlights_contract_workspace(self):
        from contracts.models import Contract
        contract = Contract.objects.create(
            organization=self.org, title='Baseline Contract', content='x',
            status='DRAFT', created_by=self.owner,
        )
        response = self.owner_client.get(reverse('contracts:contract_detail', kwargs={'pk': contract.pk}))
        content = response.content.decode()
        href = reverse('contracts:contract_list')
        self.assertRegex(content, rf'<a href="{href}" class="nav-link active"')

    def test_active_state_on_risk_log_list_highlights_risk_register(self):
        response = self.owner_client.get(reverse('contracts:risk_log_list'))
        content = response.content.decode()
        href = reverse('contracts:risk_log_list')
        self.assertRegex(content, rf'<a href="{href}" class="nav-link active"')

    def test_settings_link_present_for_all_roles(self):
        for client in (self.owner_client, self.member_client):
            response = client.get(reverse('dashboard'))
            self.assertContains(response, 'Settings')

    def test_member_hitting_escrow_url_directly_is_still_403(self):
        response = self.member_client.get(reverse('contracts:trust_account_list'))
        self.assertEqual(response.status_code, 403)

    def test_member_hitting_budget_url_directly_still_succeeds(self):
        response = self.member_client.get(reverse('contracts:budget_list'))
        self.assertEqual(response.status_code, 200)
