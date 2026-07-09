"""Contract Launch Setup — recommended template, playbook, review/approval
route, and required fields per contract type on the New Contract Request
page (contracts/services/contract_launch_setup.py).

Covers: per-type service output (NDA/DPA/MSA/Other from the "Initial
mappings"), the blank "Select contract type" default (not "Other"),
required-field count varying by type, and that none of this disturbs
law_firm_ops behavior or in_house_clm route-preview parity.
"""
import json

from django.contrib.auth import get_user_model
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from contracts.models import Contract, ContractTemplate, Organization, OrganizationMembership
from contracts.services.contract_launch_setup import (
    CUSTOM_DRAFTING_ROUTE_COPY,
    CUSTOM_DRAFTING_ROUTE_TITLE,
    MSA_FINANCE_APPROVAL_THRESHOLD,
    get_launch_setup_for_type,
    get_launch_setup_map,
)

User = get_user_model()


class _LaunchSetupFixtureMixin:
    def _make_org_with_user(self, workspace_mode, label, username):
        kwargs = {}
        if workspace_mode:
            kwargs['workspace_mode'] = workspace_mode
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


class LaunchSetupServiceTests(TestCase):
    """Service-level: fast, precise, independent of any HTML rendering."""

    def test_nda_recommends_seeded_template_and_light_review(self):
        setup = get_launch_setup_for_type(Contract.ContractType.NDA)
        self.assertIsNotNone(setup.template)
        self.assertIn('NDA', setup.template.name)
        self.assertIn('NDA', setup.playbook)
        self.assertIn('light', setup.review_route.lower())

    def test_dpa_recommends_privacy_route(self):
        setup = get_launch_setup_for_type(Contract.ContractType.DPA)
        self.assertIsNotNone(setup.template)
        self.assertIn('DPA', setup.playbook.upper())
        self.assertIn('Privacy', setup.review_route)
        self.assertIn('Privacy', setup.approval_route)

    def test_msa_shows_finance_threshold_messaging(self):
        setup = get_launch_setup_for_type(Contract.ContractType.MSA)
        self.assertIsNotNone(setup.template)
        self.assertIn(f'{MSA_FINANCE_APPROVAL_THRESHOLD:,.0f}', setup.approval_route)
        self.assertIn('finance', setup.approval_route.lower())

    def test_other_has_no_automatic_template(self):
        setup = get_launch_setup_for_type(Contract.ContractType.OTHER)
        self.assertIsNone(setup.template)

    def test_other_has_no_template_even_if_one_existed(self):
        """OTHER must never recommend a template, even if a row happens to
        exist for it — this is an explicit rule (see module docstring), not
        an accident of empty seed data."""
        ContractTemplate.objects.create(name='Rogue Other Template', contract_type=Contract.ContractType.OTHER)
        setup = get_launch_setup_for_type(Contract.ContractType.OTHER)
        self.assertIsNone(setup.template)

    def test_type_with_no_seeded_template_recommends_none_not_invented(self):
        setup = get_launch_setup_for_type(Contract.ContractType.LEASE)
        self.assertIsNone(setup.template)
        # Still gets real routing copy, just no fabricated template.
        self.assertTrue(setup.review_route)
        self.assertTrue(setup.approval_route)

    def test_required_field_count_varies_by_type(self):
        nda_setup = get_launch_setup_for_type(Contract.ContractType.NDA)
        other_setup = get_launch_setup_for_type(Contract.ContractType.OTHER)
        amendment_setup = get_launch_setup_for_type(Contract.ContractType.AMENDMENT)

        self.assertEqual(set(nda_setup.required_fields), {'counterparty', 'governing_law', 'jurisdiction'})
        self.assertEqual(other_setup.required_fields, [])
        self.assertIn('content', amendment_setup.required_fields)
        self.assertNotEqual(len(nda_setup.required_fields), len(other_setup.required_fields))

    def test_every_contract_type_choice_has_a_setup_entry(self):
        launch_map = get_launch_setup_map()
        for value, _label in Contract.ContractType.choices:
            with self.subTest(contract_type=value):
                self.assertIn(value, launch_map)
                self.assertTrue(launch_map[value]['review_route'])
                self.assertTrue(launch_map[value]['approval_route'])

    def test_template_lookup_prefers_active_rows_only(self):
        ContractTemplate.objects.create(
            name='Inactive Vendor Template', contract_type=Contract.ContractType.VENDOR, is_active=False,
        )
        setup = get_launch_setup_for_type(Contract.ContractType.VENDOR)
        self.assertIsNone(setup.template)

    def test_unmapped_type_gets_custom_drafting_route_flag(self):
        """LEASE has no LAUNCH_SETUP_CONFIG entry and no seeded template —
        it must read as an intentional 'custom drafting route', not missing
        configuration."""
        setup = get_launch_setup_for_type(Contract.ContractType.LEASE)
        self.assertTrue(setup.is_custom_drafting_route)

    def test_type_with_template_but_no_explicit_copy_is_not_custom_drafting_route(self):
        """CONSULTING has a seeded template (from the migration data) but no
        bespoke LAUNCH_SETUP_CONFIG entry — it must show its real template,
        not the custom-drafting-route fallback that would hide it."""
        setup = get_launch_setup_for_type(Contract.ContractType.CONSULTING)
        self.assertIsNotNone(setup.template)
        self.assertFalse(setup.is_custom_drafting_route)

    def test_mapped_types_are_not_flagged_as_custom_drafting_route(self):
        for contract_type in (
            Contract.ContractType.NDA, Contract.ContractType.DPA, Contract.ContractType.MSA,
            Contract.ContractType.OTHER, Contract.ContractType.SETTLEMENT, Contract.ContractType.AMENDMENT,
            Contract.ContractType.VENDOR, Contract.ContractType.SAAS,
        ):
            with self.subTest(contract_type=contract_type):
                setup = get_launch_setup_for_type(contract_type)
                self.assertFalse(setup.is_custom_drafting_route)

    def test_every_unmapped_type_still_has_usable_routing_copy(self):
        """The custom-drafting-route flag only changes template/playbook
        framing — review/approval routing copy must still be present."""
        launch_map = get_launch_setup_map()
        for contract_type, setup in launch_map.items():
            if setup['is_custom_drafting_route']:
                with self.subTest(contract_type=contract_type):
                    self.assertIsNone(setup['template'])
                    self.assertTrue(setup['review_route'])
                    self.assertTrue(setup['approval_route'])


class NewContractRequestPageTests(_LaunchSetupFixtureMixin, TestCase):
    """Integration: the actual New Contract Request page for law_firm_ops."""

    def setUp(self):
        self.org, self.user, self.client_ = self._make_org_with_user(None, 'Launch Setup Firm', 'launch_setup_firm_user')

    def _get(self, **params):
        return self.client_.get(reverse('contracts:contract_create'), params)

    def test_page_renders(self):
        response = self._get()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'New Contract Request')

    def test_contract_type_defaults_to_blank_not_other(self):
        response = self._get()
        # The bound field's rendered value is what's actually pre-selected.
        self.assertEqual(response.context['form']['contract_type'].value(), '')
        self.assertContains(response, 'Select contract type')

    def test_type_query_param_still_preselects_type(self):
        """Regression guard: the existing ?type= prefill (used by the
        contract template picker's "start blank" link) must still work
        after adding the blank-default behavior."""
        response = self._get(type='NDA')
        self.assertEqual(response.context['form']['contract_type'].value(), 'NDA')

    def test_template_query_param_still_prefills_type_and_content(self):
        template = ContractTemplate.objects.create(
            name='Regression Template', contract_type=Contract.ContractType.MSA, body='MSA body {{title}}',
        )
        response = self._get(template=template.pk)
        self.assertEqual(response.context['form']['contract_type'].value(), 'MSA')
        self.assertEqual(response.context['form']['content'].value(), 'MSA body {{title}}')
        self.assertEqual(response.context['selected_template'], template)

    def test_launch_setup_data_present_and_correct_for_nda(self):
        response = self._get()
        self.assertContains(response, 'id="launch-setup-data"')
        content = response.content.decode()
        start = content.index('id="launch-setup-data"')
        script_start = content.index('>', start) + 1
        script_end = content.index('</script>', script_start)
        payload = json.loads(content[script_start:script_end])
        self.assertIn('NDA', payload)
        self.assertIn('NDA', payload['NDA']['template']['name'])
        self.assertEqual(payload['OTHER']['template'], None)

    def test_submit_button_present_for_js_gating(self):
        response = self._get()
        self.assertContains(response, 'id="submit-contract-btn"')

    def test_law_firm_ops_core_sections_unchanged(self):
        """Preservation check: the pre-existing intake sections are all
        still there, untouched by this feature."""
        response = self._get()
        for text in ('Contract identity', 'Commercial terms and jurisdiction', 'Review triggers', 'Dates and lifecycle management'):
            self.assertContains(response, text)

    def test_no_leaked_django_template_comment_markers(self):
        """Regression guard: a multi-line {# #} comment does not get
        stripped by Django's template engine (unlike {% comment %}) and
        renders as literal text — this must never appear in the page."""
        response = self._get()
        content = response.content.decode()
        self.assertNotIn('{#', content)
        self.assertNotIn('Contract Launch Setup data', content)

    def test_collapsible_sections_present_and_collapsed_by_default(self):
        """Contract identity stays visible; Legal posture, Lifecycle
        control, and Draft brief are collapsible and start closed."""
        response = self._get()
        content = response.content.decode()
        self.assertIn('data-collapsible="legal-posture"', content)
        self.assertIn('data-collapsible="lifecycle-control"', content)
        self.assertIn('data-collapsible="draft-brief"', content)
        for key in ('legal-posture', 'lifecycle-control', 'draft-brief'):
            idx = content.index(f'data-collapsible="{key}"')
            # The <details ...> tag itself must not carry the `open` attribute.
            tag_start = content.rindex('<details', 0, idx + 1)
            tag_end = content.index('>', tag_start)
            self.assertNotIn(' open', content[tag_start:tag_end])

    def test_sticky_support_rail_cards_present(self):
        response = self._get()
        for text in ('Readiness', 'Required now', 'Selected setup', 'Route preview', 'After create'):
            self.assertContains(response, text)

    def test_creating_a_contract_still_works_end_to_end(self):
        """Preserve existing contract creation behavior end-to-end."""
        response = self.client_.post(reverse('contracts:contract_create'), {
            'title': 'Launch Setup Regression Contract',
            'contract_type': Contract.ContractType.NDA,
            'content': 'Body',
            'status': Contract.Status.DRAFT,
            'counterparty': 'Acme Corp',
            'currency': Contract.Currency.USD,
            'governing_law': 'State of Delaware',
            'jurisdiction': 'New York',
            'risk_level': Contract.RiskLevel.LOW,
            'lifecycle_stage': 'DRAFTING',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Contract.objects.filter(title='Launch Setup Regression Contract').exists())


class InHouseClmNewContractRequestPageTests(_LaunchSetupFixtureMixin, TestCase):
    """in_house_clm parity: the launch setup card must work identically for
    CLM tenants — nothing here is (or should be) gated by workspace_mode."""

    def setUp(self):
        self.org, self.user, self.client_ = self._make_org_with_user(
            'in_house_clm', 'Launch Setup CLM', 'launch_setup_clm_user',
        )

    def test_page_renders_for_clm_org(self):
        response = self.client_.get(reverse('contracts:contract_create'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'New Contract Request')

    def test_launch_setup_data_present_for_clm_org(self):
        response = self.client_.get(reverse('contracts:contract_create'))
        self.assertContains(response, 'id="launch-setup-data"')
        content = response.content.decode()
        start = content.index('id="launch-setup-data"')
        script_start = content.index('>', start) + 1
        script_end = content.index('</script>', script_start)
        payload = json.loads(content[script_start:script_end])
        self.assertIn('DPA', payload)
        self.assertIn('Privacy', payload['DPA']['review_route'])

    def test_contract_type_defaults_to_blank_for_clm_org_too(self):
        response = self.client_.get(reverse('contracts:contract_create'))
        self.assertEqual(response.context['form']['contract_type'].value(), '')
