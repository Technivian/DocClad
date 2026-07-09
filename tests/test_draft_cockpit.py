"""AI Draft Builder cockpit — entry cards (Stage 1) and governance panel
data (Stage 2) built for the "New Contract" redesign.

Covers: contract_launch_setup.get_entry_cards(), draft_cockpit.py's service
functions, and the governance-panel/readiness context the generic New
Contract page renders. All assertions check real, persisted data — no
fabricated AI output.

Note: the "Live Contract Draft" preview column and its AI action pills
were removed from this page (server-rendered client-side preview reading
governance_panel.merge_fields/gemini_ai_enabled) — that data is still
computed by get_governance_panel() and used elsewhere (e.g. the DPA
workflow builder, see test_dpa_workflow.py), just no longer rendered here.
"""
from django.contrib.auth import get_user_model
from django.test import Client as TestClient
from django.test import TestCase, override_settings
from django.urls import reverse

from contracts.models import ClauseTemplate, Contract, ContractTemplate, Organization, OrganizationMembership, RiskLog
from contracts.services.contract_launch_setup import get_entry_cards
from contracts.services.draft_cockpit import (
    CLAUSE_ACTION_AVAILABILITY,
    get_approval_route_preview,
    get_clause_library_count,
    get_governance_panel,
    get_preview_template_body,
    get_risk_summary,
)

User = get_user_model()


class EntryCardsTests(TestCase):
    def test_returns_the_six_curated_types_in_order(self):
        cards = get_entry_cards()
        self.assertEqual(
            [c.contract_type for c in cards],
            [Contract.ContractType.MSA, Contract.ContractType.DPA, Contract.ContractType.NDA,
             Contract.ContractType.SOW, Contract.ContractType.VENDOR, Contract.ContractType.AMENDMENT],
        )

    def test_card_shows_real_recommended_template_name(self):
        ContractTemplate.objects.create(name='Standard MSA', contract_type=Contract.ContractType.MSA, body='x', is_active=True)
        cards = get_entry_cards()
        msa_card = next(c for c in cards if c.contract_type == Contract.ContractType.MSA)
        self.assertEqual(msa_card.template_name, 'Standard MSA')

    def test_card_has_no_template_name_when_none_exists(self):
        cards = get_entry_cards()
        amendment_card = next(c for c in cards if c.contract_type == Contract.ContractType.AMENDMENT)
        self.assertIsNone(amendment_card.template_name)

    def test_start_url_for_callback_is_used_when_provided(self):
        cards = get_entry_cards(start_url_for=lambda ct: f'/custom/{ct}')
        self.assertTrue(all(c.start_url == f'/custom/{c.contract_type}' for c in cards))

    def test_start_url_falls_back_to_query_string_without_callback(self):
        cards = get_entry_cards()
        msa_card = next(c for c in cards if c.contract_type == Contract.ContractType.MSA)
        self.assertEqual(msa_card.start_url, '?type=MSA')

    def test_every_card_has_a_non_empty_description(self):
        for card in get_entry_cards():
            with self.subTest(contract_type=card.contract_type):
                self.assertTrue(card.description)


class GetPreviewTemplateBodyTests(TestCase):
    """Uses AMENDMENT/VENDOR — contract types with no seeded ContractTemplate
    (see contracts/migrations/0067_seed_contract_templates.py, which only
    seeds NDA/MSA/DPA/SOW/CONSULTING) — so "no template exists" assertions
    aren't accidentally satisfied or contradicted by seed data."""

    def test_returns_none_for_other_type_with_no_selection(self):
        self.assertIsNone(get_preview_template_body(Contract.ContractType.OTHER))

    def test_returns_none_when_no_active_template_exists(self):
        self.assertIsNone(get_preview_template_body(Contract.ContractType.AMENDMENT))

    def test_prefers_explicitly_selected_template_over_type_lookup(self):
        ContractTemplate.objects.create(name='Type default', contract_type=Contract.ContractType.VENDOR, body='default body', is_active=True)
        selected = ContractTemplate.objects.create(name='Chosen', contract_type=Contract.ContractType.VENDOR, body='chosen body', is_active=True)
        self.assertEqual(get_preview_template_body(Contract.ContractType.VENDOR, selected_template=selected), 'chosen body')

    def test_falls_back_to_active_type_template(self):
        ContractTemplate.objects.create(name='Only', contract_type=Contract.ContractType.VENDOR, body='vendor body', is_active=True)
        self.assertEqual(get_preview_template_body(Contract.ContractType.VENDOR), 'vendor body')

    def test_ignores_inactive_templates(self):
        ContractTemplate.objects.create(name='Inactive', contract_type=Contract.ContractType.AMENDMENT, body='amendment body', is_active=False)
        self.assertIsNone(get_preview_template_body(Contract.ContractType.AMENDMENT))


class GetClauseLibraryCountTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Clause Org', slug='clause-org')

    def test_counts_approved_clauses_applicable_to_type(self):
        baseline = get_clause_library_count(self.org, Contract.ContractType.NDA)
        ClauseTemplate.objects.create(
            organization=self.org, title='Confidentiality', content='x', is_approved=True,
            applicable_contract_types='NDA,MSA',
        )
        ClauseTemplate.objects.create(
            organization=self.org, title='Unrelated', content='x', is_approved=True,
            applicable_contract_types='DPA',
        )
        self.assertEqual(get_clause_library_count(self.org, Contract.ContractType.NDA), baseline + 1)

    def test_blank_applicable_types_means_applies_to_all(self):
        baseline = get_clause_library_count(self.org, Contract.ContractType.NDA)
        ClauseTemplate.objects.create(organization=self.org, title='Universal', content='x', is_approved=True)
        self.assertEqual(get_clause_library_count(self.org, Contract.ContractType.NDA), baseline + 1)

    def test_excludes_unapproved_clauses(self):
        baseline = get_clause_library_count(self.org, Contract.ContractType.NDA)
        ClauseTemplate.objects.create(organization=self.org, title='Draft clause', content='x', is_approved=False)
        self.assertEqual(get_clause_library_count(self.org, Contract.ContractType.NDA), baseline)

    def test_returns_zero_for_blank_contract_type(self):
        self.assertEqual(get_clause_library_count(self.org, ''), 0)


class GetApprovalRoutePreviewTests(TestCase):
    def test_low_risk_type_has_no_finance_or_dpo_step(self):
        steps = get_approval_route_preview(Contract.ContractType.NDA)
        names = [s.name for s in steps]
        self.assertEqual(names, ['Contract Owner', 'Legal'])

    def test_dpa_adds_a_dpo_step(self):
        steps = get_approval_route_preview(Contract.ContractType.DPA)
        names = [s.name for s in steps]
        self.assertIn('DPO', names)

    def test_high_risk_type_adds_a_finance_step(self):
        from contracts.services.workflow_routing import HIGH_RISK_TYPES
        high_risk_type = next(iter(HIGH_RISK_TYPES))
        steps = get_approval_route_preview(high_risk_type)
        names = [s.name for s in steps]
        self.assertIn('Finance', names)


class GetRiskSummaryTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Risk Org', slug='risk-org')

    def test_unsaved_contract_has_no_data(self):
        summary = get_risk_summary(Contract(organization=self.org, title='Draft', contract_type=Contract.ContractType.MSA))
        self.assertEqual(summary, {'has_data': False, 'open_count': 0, 'high_or_critical_count': 0})

    def test_none_contract_has_no_data(self):
        self.assertEqual(get_risk_summary(None)['has_data'], False)

    def test_saved_contract_counts_open_and_high_risks(self):
        contract = Contract.objects.create(organization=self.org, title='Saved', contract_type=Contract.ContractType.MSA)
        RiskLog.objects.create(contract=contract, description='x', risk_level=RiskLog.RiskLevel.HIGH, status=RiskLog.Status.OPEN)
        RiskLog.objects.create(contract=contract, description='x', risk_level=RiskLog.RiskLevel.LOW, status=RiskLog.Status.OPEN)
        RiskLog.objects.create(contract=contract, description='x', risk_level=RiskLog.RiskLevel.CRITICAL, status=RiskLog.Status.RESOLVED)
        summary = get_risk_summary(contract)
        self.assertTrue(summary['has_data'])
        self.assertEqual(summary['open_count'], 2)
        self.assertEqual(summary['high_or_critical_count'], 1)


class GetGovernancePanelTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Gov Org', slug='gov-org')

    def test_gemini_ai_enabled_defaults_false(self):
        panel = get_governance_panel(self.org, Contract.ContractType.MSA, None)
        self.assertFalse(panel['gemini_ai_enabled'])

    @override_settings(GEMINI_AI_ENABLED=True)
    def test_gemini_ai_enabled_reflects_setting(self):
        panel = get_governance_panel(self.org, Contract.ContractType.MSA, None)
        self.assertTrue(panel['gemini_ai_enabled'])

    def test_panel_includes_approval_route_and_merge_fields(self):
        panel = get_governance_panel(self.org, Contract.ContractType.DPA, None)
        self.assertTrue(panel['approval_route'])
        self.assertIsInstance(panel['merge_fields'], dict)

    def test_panel_template_none_when_no_template_exists(self):
        panel = get_governance_panel(self.org, Contract.ContractType.AMENDMENT, None)
        self.assertIsNone(panel['template'])

    def test_clause_action_availability_marks_generative_actions(self):
        self.assertEqual(CLAUSE_ACTION_AVAILABILITY['explain_clause'], 'generative')
        self.assertEqual(CLAUSE_ACTION_AVAILABILITY['generate_summary'], 'generative')
        self.assertEqual(CLAUSE_ACTION_AVAILABILITY['suggest_fallback'], 'persisted')
        self.assertEqual(CLAUSE_ACTION_AVAILABILITY['compare_playbook'], 'persisted')


class ContractTemplatePickerEntryCardsPageTests(TestCase):
    """Integration: Stage 1 entry-card grid on the actual picker page."""

    def setUp(self):
        self.org = Organization.objects.create(name='Picker Firm', slug='picker-firm')
        self.user = User.objects.create_user(username='picker_user', password='testpass123!')
        OrganizationMembership.objects.create(
            organization=self.org, user=self.user, role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        self.client_ = TestClient()
        self.client_.login(username='picker_user', password='testpass123!')

    def test_entry_cards_render_with_expected_titles(self):
        response = self.client_.get(reverse('contracts:contract_template_picker'))
        self.assertEqual(response.status_code, 200)
        for title in ('MSA', 'DPA', 'NDA', 'SOW', 'Supplier Agreement', 'Addendum'):
            self.assertContains(response, title)

    def test_selecting_a_type_still_shows_the_template_list(self):
        response = self.client_.get(reverse('contracts:contract_template_picker'), {'type': 'NDA'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'New Non-Disclosure Agreement')


class ContractFormCockpitDataPageTests(TestCase):
    """Integration: Stage 2 create-page context/json_script data for the
    live draft preview, governance panel, and AI action gating."""

    def setUp(self):
        self.org = Organization.objects.create(name='Cockpit Firm', slug='cockpit-firm')
        self.user = User.objects.create_user(username='cockpit_user', password='testpass123!')
        OrganizationMembership.objects.create(
            organization=self.org, user=self.user, role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        self.client_ = TestClient()
        self.client_.login(username='cockpit_user', password='testpass123!')

    def _get(self, **params):
        return self.client_.get(reverse('contracts:contract_create'), params)

    def test_governance_panel_present_in_context(self):
        response = self._get(type='MSA')
        self.assertIn('governance_panel', response.context)
        self.assertIn('gemini_ai_enabled', response.context['governance_panel'])

    def test_no_live_draft_column_or_ai_action_pills_on_create_page(self):
        """The "Live Contract Draft" preview column and its AI action pills
        were removed from this page — governance panel and readiness stay,
        server-rendered from context, with no client-side draft preview."""
        response = self._get(type='MSA')
        self.assertNotContains(response, 'id="cform-draft-doc"')
        for action in ('complete_missing', 'suggest_fallback', 'explain_clause', 'generate_summary', 'compare_playbook'):
            self.assertNotContains(response, f'data-ai-action="{action}"')

    def test_editing_an_existing_contract_also_has_no_live_draft_column(self):
        contract = Contract.objects.create(organization=self.org, title='Existing', contract_type=Contract.ContractType.MSA)
        response = self.client_.get(reverse('contracts:contract_update', args=[contract.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="cform-draft-doc"')

    def test_no_leaked_django_template_comment_markers(self):
        response = self._get(type='MSA')
        content = response.content.decode()
        self.assertNotIn('{#', content)
