"""Phase 5: workspace-mode containment contract.

Companion to docs/WORKSPACE_MODE_CONTAINMENT.md, which documents the full
route classification and shared-shell-vs-mode-specific-content policy this
file encodes as tests. This is the single place that proves the containment
contract across all mode-aware routes together, rather than each Phase's
own test file only proving its own corner.

Three buckets, matching the architecture note:

1. Shared shell, mode-specific content (matter detail, risk review) —
   law_firm_ops must never render in_house_clm-only content and vice versa.
   The dashboard used to live in this bucket (a plain law_firm_ops variant
   vs. a rich in_house_clm Command Center); it has since moved to bucket 2 —
   the Command Center is now the standard dashboard for every organization,
   regardless of workspace_mode. See DashboardModeNeutralTests below.
2. Shared / mode-neutral routes (Dashboard, Repository, Counterparties,
   DPA Reviews, Approvals, Reports) — reachable and organization-scoped for
   both modes, with no mode-conditional branching at all.
3. Primary navigation — mode-neutral. Playbooks remains directly reachable
   while its product framing is finalized, but it is deliberately not a
   primary-shell entry for either workspace mode. Obligations has a dedicated
   workspace (contracts:obligations_workspace, Phase 4).
"""
from django.contrib.auth import get_user_model
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from contracts.models import (
    ApprovalRequest,
    Client as ClientModel,
    Contract,
    Counterparty,
    DPAReviewPack,
    Matter,
    Organization,
    OrganizationMembership,
)
from contracts.nav_config import get_nav_for

User = get_user_model()


class _ContainmentFixtureMixin:
    def _make_org_with_user(self, workspace_mode, label, username):
        # Organization defaults to in_house_clm, so test fixtures must set
        # law_firm_ops explicitly rather than relying on an omitted value.
        kwargs = {'workspace_mode': workspace_mode or Organization.WorkspaceMode.LAW_FIRM_OPS}
        org = Organization.objects.create(
            name=f'{label} {id(self)}-{username}',
            slug=f'{label.lower().replace(" ", "-")}-{id(self)}-{username}',
            **kwargs,
        )
        user = User.objects.create_user(username=username, password='testpass123!')
        OrganizationMembership.objects.create(
            organization=org, user=user, role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        client_ = TestClient()
        client_.login(username=username, password='testpass123!')
        return org, user, client_


# ═══════════════════════════════════════════════════════════════════════
# Bucket 1 — shared shell, mode-specific content
# ═══════════════════════════════════════════════════════════════════════

class MatterDetailContainmentTests(_ContainmentFixtureMixin, TestCase):
    def setUp(self):
        self.firm_org, self.firm_user, self.firm_client = self._make_org_with_user(
            None, 'Containment Firm Matter', 'containment_firm_matter_user',
        )
        self.clm_org, self.clm_user, self.clm_client = self._make_org_with_user(
            'in_house_clm', 'Containment CLM Matter', 'containment_clm_matter_user',
        )
        self.firm_matter = self._make_matter(self.firm_org, self.firm_user, 'M-CONT-FIRM')
        self.clm_matter = self._make_matter(self.clm_org, self.clm_user, 'M-CONT-CLM')

    def _make_matter(self, org, user, number):
        client_obj = ClientModel.objects.create(organization=org, name='Containment Client', created_by=user)
        return Matter.objects.create(
            organization=org, matter_number=number, title=f'{number} Engagement',
            client=client_obj, created_by=user,
        )

    def test_law_firm_ops_matter_detail_shows_no_clm_sections(self):
        response = self.firm_client.get(reverse('contracts:matter_detail', kwargs={'pk': self.firm_matter.pk}))
        content = response.content.decode()
        self.assertIn('Billing Summary', content)
        self.assertIn('Recent Time Entries', content)
        for forbidden in ('Linked Contracts', 'DPA Review Packs', 'Open Approvals', 'Review Memos'):
            self.assertNotIn(forbidden, content)

    def test_in_house_clm_matter_detail_shows_no_billing_content(self):
        response = self.clm_client.get(reverse('contracts:matter_detail', kwargs={'pk': self.clm_matter.pk}))
        content = response.content.decode()
        self.assertIn('Linked Contracts', content)
        self.assertIn('DPA Review Packs', content)
        for forbidden in ('Billing Summary', 'Recent Time Entries'):
            self.assertNotIn(forbidden, content)


class RiskReviewContainmentTests(_ContainmentFixtureMixin, TestCase):
    def setUp(self):
        self.firm_org, self.firm_user, self.firm_client = self._make_org_with_user(
            None, 'Containment Firm Risk', 'containment_firm_risk_user',
        )
        self.clm_org, self.clm_user, self.clm_client = self._make_org_with_user(
            'in_house_clm', 'Containment CLM Risk', 'containment_clm_risk_user',
        )

    def test_law_firm_ops_risk_review_shows_no_hub_content(self):
        response = self.firm_client.get(reverse('contracts:risk_log_list'))
        content = response.content.decode()
        self.assertIn('Risk Register', content)
        self.assertNotIn('Legal Intelligence Hub', content)
        self.assertNotIn('Cross-Document Conflicts', content)

    def test_in_house_clm_risk_review_shows_no_register_content(self):
        response = self.clm_client.get(reverse('contracts:risk_log_list'))
        content = response.content.decode()
        self.assertIn('Legal Intelligence Hub', content)
        self.assertNotIn('Risk Register', content)


# ═══════════════════════════════════════════════════════════════════════
# Bucket 2 — shared / mode-neutral routes: reachable + org-scoped for both
# modes, with no mode-conditional branching
# ═══════════════════════════════════════════════════════════════════════

class DashboardModeNeutralTests(_ContainmentFixtureMixin, TestCase):
    """The Command Center is the standard dashboard for every organization —
    law_firm_ops and in_house_clm orgs see the identical rich dashboard."""

    def setUp(self):
        self.firm_org, self.firm_user, self.firm_client = self._make_org_with_user(
            None, 'Containment Firm', 'containment_firm_user',
        )
        self.clm_org, self.clm_user, self.clm_client = self._make_org_with_user(
            'in_house_clm', 'Containment CLM', 'containment_clm_user',
        )
        for org, user in ((self.firm_org, self.firm_user), (self.clm_org, self.clm_user)):
            Contract.objects.create(
                organization=org, title=f'Seed Contract {org.pk}', content='x',
                status='ACTIVE', created_by=user,
            )

    def test_law_firm_ops_dashboard_shows_command_center(self):
        response = self.firm_client.get(reverse('dashboard'))
        content = response.content.decode()
        self.assertIn('Command Center', content)

    def test_in_house_clm_dashboard_shows_command_center(self):
        response = self.clm_client.get(reverse('dashboard'))
        content = response.content.decode()
        self.assertIn('Command Center', content)

    def test_dashboard_never_shows_law_firm_billing_content(self):
        for client_ in (self.firm_client, self.clm_client):
            response = client_.get(reverse('dashboard'))
            content = response.content.decode()
            for forbidden in ('Billable hours', 'Trust balance', 'Invoice aging'):
                self.assertNotIn(forbidden, content)


class SharedNeutralRoutesAccessibilityTests(_ContainmentFixtureMixin, TestCase):
    """Repository, Counterparties, DPA Reviews, Approvals, Reports."""

    def setUp(self):
        self.firm_org, self.firm_user, self.firm_client = self._make_org_with_user(
            None, 'Containment Firm Neutral', 'containment_firm_neutral_user',
        )
        self.clm_org, self.clm_user, self.clm_client = self._make_org_with_user(
            'in_house_clm', 'Containment CLM Neutral', 'containment_clm_neutral_user',
        )

    def test_neutral_routes_reachable_in_both_modes(self):
        neutral_routes = [
            'contracts:repository',
            'contracts:counterparty_list',
            'contracts:dpa_review_pack_list',
            'contracts:approval_request_list',
            'contracts:reports_dashboard',
        ]
        for route_name in neutral_routes:
            url = reverse(route_name)
            with self.subTest(route=route_name, mode='law_firm_ops'):
                self.assertEqual(self.firm_client.get(url).status_code, 200)
            with self.subTest(route=route_name, mode='in_house_clm'):
                self.assertEqual(self.clm_client.get(url).status_code, 200)


class SharedNeutralRoutesTenantScopingTests(_ContainmentFixtureMixin, TestCase):
    """Cross-org data must not leak across a mode boundary either —
    scoping is an organization concern, not a workspace_mode concern, and
    these tests prove workspace_mode never becomes a backdoor around it."""

    def setUp(self):
        self.firm_org, self.firm_user, self.firm_client = self._make_org_with_user(
            None, 'Containment Firm Scope', 'containment_firm_scope_user',
        )
        self.clm_org, self.clm_user, self.clm_client = self._make_org_with_user(
            'in_house_clm', 'Containment CLM Scope', 'containment_clm_scope_user',
        )

    def test_counterparties_not_shared_across_modes(self):
        Counterparty.objects.create(organization=self.firm_org, name='Firm-Only Counterparty')
        response = self.clm_client.get(reverse('contracts:counterparty_list'))
        self.assertNotContains(response, 'Firm-Only Counterparty')

    def test_dpa_review_packs_not_shared_across_modes(self):
        counterparty = Counterparty.objects.create(organization=self.clm_org, name='CLM Counterparty')
        contract = Contract.objects.create(
            organization=self.clm_org, title='CLM-Only DPA Contract', content='x',
            status='ACTIVE', created_by=self.clm_user,
        )
        DPAReviewPack.objects.create(organization=self.clm_org, contract=contract, counterparty=counterparty)
        response = self.firm_client.get(reverse('contracts:dpa_review_pack_list'))
        self.assertNotContains(response, 'CLM-Only DPA Contract')

    def test_approvals_not_shared_across_modes(self):
        contract = Contract.objects.create(
            organization=self.firm_org, title='Firm-Only Approval Contract', content='x',
            status='ACTIVE', created_by=self.firm_user,
        )
        ApprovalRequest.objects.create(
            organization=self.firm_org, contract=contract, approval_step='Legal',
            status='PENDING', assigned_to=self.firm_user,
        )
        response = self.clm_client.get(reverse('contracts:approval_request_list'))
        self.assertNotContains(response, 'Firm-Only Approval Contract')


# ═══════════════════════════════════════════════════════════════════════
# Bucket 3 — standard navigation contract
# ═══════════════════════════════════════════════════════════════════════

class NavigationContractTests(_ContainmentFixtureMixin, TestCase):
    """The primary shell is shared. Secondary routes stay directly reachable
    without leaking a temporary, mode-specific information architecture."""

    def setUp(self):
        self.clm_org, self.clm_user, self.clm_client = self._make_org_with_user(
            'in_house_clm', 'Containment CLM Stopgap', 'containment_clm_stopgap_user',
        )
        self.firm_org, self.firm_user, self.firm_client = self._make_org_with_user(
            None, 'Containment Firm Stopgap', 'containment_firm_stopgap_user',
        )

    def test_in_house_clm_obligations_nav_item_points_at_dedicated_workspace(self):
        """Phase 4 replaced the deadline_list stopgap with a dedicated
        ObligationsWorkspaceView — see tests/test_obligations_workspace.py."""
        nav = get_nav_for(self.clm_org, self.clm_user)
        obligations_items = [e for e in nav if e.get('kind') == 'item' and e.get('label') == 'Obligations']
        self.assertEqual(len(obligations_items), 1)
        self.assertEqual(obligations_items[0]['url_name'], 'contracts:obligations_workspace')

    def test_primary_navigation_is_mode_neutral_and_has_no_playbooks_stopgap(self):
        firm_labels = [e.get('label') for e in get_nav_for(self.firm_org, self.firm_user)
                       if e.get('kind') == 'item']
        clm_labels = [e.get('label') for e in get_nav_for(self.clm_org, self.clm_user)
                      if e.get('kind') == 'item']
        self.assertEqual(firm_labels, clm_labels)
        self.assertNotIn('Playbooks', firm_labels)

    def test_deadline_list_redirects_to_obligations_for_in_house_clm(self):
        response = self.clm_client.get(reverse('contracts:deadline_list'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('contracts:obligations_workspace'))

    def test_dpa_playbook_list_renders_for_in_house_clm(self):
        response = self.clm_client.get(reverse('contracts:dpa_playbook_list'))
        self.assertEqual(response.status_code, 200)
