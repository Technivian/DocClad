"""Regression coverage for the canonical CLM One workspace tabs pattern."""
from django.contrib.auth.models import User
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from contracts.models import Contract, Organization, OrganizationMembership
from contracts.services.contract_detail_workspace import (
    build_contract_detail_tabs,
    build_workflow_section_tabs,
    contract_operations_hub_tabs,
    normalize_contract_detail_tab,
    normalize_workflow_section,
)


def page_body(html: str) -> str:
    return html.split('<div id="djDebug"', 1)[0]


class WorkspaceTabsCanonicalPatternTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Tabs Firm', slug='workspace-tabs-firm')
        self.user = User.objects.create_user(username='tabs_user', password='testpass123')
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.user,
            role=OrganizationMembership.Role.MEMBER,
            is_active=True,
        )
        self.client = TestClient()
        self.client.login(username='tabs_user', password='testpass123')
        self.contract = Contract.objects.create(
            organization=self.organization,
            title='Tabs Contract',
            content='Seed',
            status=Contract.Status.IN_PROGRESS,
            created_by=self.user,
        )

    def test_normalize_aliases_preserve_deep_links(self):
        self.assertEqual(normalize_contract_detail_tab('review'), 'workflow')
        self.assertEqual(normalize_contract_detail_tab('approvals'), 'workflow')
        self.assertEqual(normalize_contract_detail_tab('audit-trail'), 'activity')
        self.assertEqual(normalize_workflow_section(None, raw_tab='approvals'), 'approvals')
        self.assertEqual(normalize_workflow_section('signatures'), 'signatures')

    def test_build_tabs_shape_for_canonical_component(self):
        tabs = build_contract_detail_tabs(self.contract.pk, 'documents')
        self.assertEqual([t['key'] for t in tabs], [
            'overview', 'documents', 'workflow', 'risks', 'obligations', 'activity',
        ])
        active = next(t for t in tabs if t['active'])
        self.assertEqual(active['key'], 'documents')
        self.assertEqual(active['label'], 'Documents')
        self.assertTrue(active['panel_id'].startswith('contract-tab-'))

        sections = build_workflow_section_tabs(self.contract.pk, 'approvals')
        self.assertEqual([t['label'] for t in sections], ['Review findings', 'Approvals'])
        self.assertTrue(any(t['active'] and t['key'] == 'approvals' for t in sections))

        hub = contract_operations_hub_tabs(active='repository')
        self.assertTrue(hub[0]['active'])
        self.assertEqual(hub[0]['label'], 'All contracts')

    def test_contract_detail_renders_canonical_markup_and_lifecycle_separation(self):
        url = reverse('contracts:contract_detail', kwargs={'pk': self.contract.pk})
        response = self.client.get(url)
        body = page_body(response.content.decode())
        self.assertEqual(response.status_code, 200)
        self.assertIn('data-workspace-tabs', body)
        self.assertIn('dc-ds-workspace-tabs__tab', body)
        self.assertIn('role="tablist"', body)
        self.assertIn('aria-selected="true"', body)
        self.assertIn('Contract lifecycle', body)
        self.assertIn('contract-progress-track--lifecycle', body)
        tabs_chunk = body.split('data-workspace-tabs', 1)[1].split('dc-ds-workspace__layout', 1)[0]
        self.assertNotIn('chip-active', tabs_chunk)
        self.assertNotIn('dc-ds-choice', tabs_chunk)
        self.assertNotIn('Quick links', body)

    def test_active_state_routing_and_tenant_isolation(self):
        url = reverse('contracts:contract_detail', kwargs={'pk': self.contract.pk})
        response = self.client.get(f'{url}?tab=workflow&section=approvals')
        self.assertEqual(response.context['active_tab'], 'workflow')
        self.assertEqual(response.context['workflow_section'], 'approvals')
        body = page_body(response.content.decode())
        self.assertIn('id="contract-tab-workflow"', body)
        self.assertIn('data-tab-key="workflow"', body)
        workflow_tab = next(t for t in response.context['workspace_tabs'] if t['key'] == 'workflow')
        self.assertTrue(workflow_tab['active'])

        other_org = Organization.objects.create(name='Other Tabs Firm', slug='workspace-tabs-other')
        outsider = User.objects.create_user(username='tabs_outsider', password='testpass123')
        OrganizationMembership.objects.create(
            organization=other_org,
            user=outsider,
            role=OrganizationMembership.Role.MEMBER,
            is_active=True,
        )
        outsider_client = TestClient()
        outsider_client.login(username='tabs_outsider', password='testpass123')
        forbidden = outsider_client.get(url)
        self.assertIn(forbidden.status_code, (403, 404))

    def test_list_surfaces_use_canonical_component(self):
        for name in (
            'contracts:repository',
            'contracts:obligations_workspace',
            'contracts:dpa_review_pack_list',
            'contracts:workflow_dashboard',
        ):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, name)
            body = page_body(response.content.decode())
            self.assertIn('data-workspace-tabs', body, name)
            self.assertIn('dc-ds-workspace-tabs__tab', body, name)

    def test_workspace_tabs_script_overflow_shell_and_styles_wired(self):
        response = self.client.get(reverse('contracts:repository'))
        html = response.content.decode()
        self.assertIn('clmone-workspace-tabs.js', html)
        self.assertIn('data-workspace-tabs-more', html)
        css = open('theme/static_src/src/design-system/components.css').read()
        self.assertIn('.dc-ds-workspace-tabs', css)
        self.assertIn('border-bottom: 3px solid transparent', css)
        js = open('theme/static/js/clmone-workspace-tabs.js').read()
        self.assertIn('ArrowRight', js)
        self.assertIn('data-workspace-tabs-more', js)
