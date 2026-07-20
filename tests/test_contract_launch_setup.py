"""Contract Launch Setup — recommended template, playbook, review/approval
route, and required fields per contract type on the New Contract Request
page (contracts/services/contract_launch_setup.py).

Covers: per-type service output (NDA/DPA/MSA/Other from the "Initial
mappings"), the blank "Select contract type" default (not "Other"),
required-field count varying by type, and that none of this disturbs
law_firm_ops behavior or in_house_clm route-preview parity.
"""
import json
from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from contracts.models import AuditLog, Contract, ContractTemplate, Organization, OrganizationMembership
from contracts.services.contract_launch_setup import (
    CUSTOM_DRAFTING_ROUTE_COPY,
    CUSTOM_DRAFTING_ROUTE_TITLE,
    MSA_FINANCE_APPROVAL_THRESHOLD,
    get_launch_setup_for_type,
    get_launch_setup_map,
)
from contracts.services.intake_risk import assess_intake_risk
from contracts.services.intake_routing import derive_intake_route

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


class IntakeRiskAssessmentTests(TestCase):
    def _values(self, **overrides):
        values = {
            'contract_type': Contract.ContractType.SOW,
            'governing_law': 'State of Delaware',
            'jurisdiction': 'New York',
            'start_date': date(2026, 7, 15),
            'end_date': date(2027, 7, 15),
            'paper_source': Contract.PaperSource.OUR_PAPER,
            'value': None,
            'data_transfer_flag': False,
            'dpa_attached': False,
            'scc_attached': False,
            'auto_renew': False,
        }
        values.update(overrides)
        return values

    def test_routing_risk_scenarios_are_explainable_and_preliminary(self):
        scenarios = {
            'standard_sow': (self._values(), True, 'PRELIMINARY', Contract.RiskLevel.LOW),
            'personal_data': (self._values(personal_data_processing=True), True, 'PRELIMINARY', Contract.RiskLevel.MEDIUM),
            'cross_border': (self._values(data_transfer_flag=True), True, 'PRELIMINARY', Contract.RiskLevel.MEDIUM),
            'high_value': (self._values(value='150000'), True, 'PRELIMINARY', Contract.RiskLevel.HIGH),
            'non_standard_law': (self._values(governing_law='Singapore', jurisdiction='Singapore'), True, 'PRELIMINARY', Contract.RiskLevel.MEDIUM),
            'no_playbook': (self._values(contract_type=Contract.ContractType.OTHER), False, 'PRELIMINARY', Contract.RiskLevel.MEDIUM),
            'third_party_paper': (self._values(paper_source=Contract.PaperSource.COUNTERPARTY_PAPER), True, 'PRELIMINARY', Contract.RiskLevel.MEDIUM),
            'missing_inputs': (self._values(governing_law=''), True, 'NOT_ASSESSED', None),
            'auto_renew': (self._values(auto_renew=True), True, 'PRELIMINARY', Contract.RiskLevel.LOW),
        }
        for name, (values, template_applied, expected_state, expected_level) in scenarios.items():
            with self.subTest(name=name):
                assessment = assess_intake_risk(values, template_applied=template_applied)
                self.assertEqual(assessment.state, expected_state)
                self.assertEqual(assessment.level, expected_level)
                self.assertTrue(assessment.review_route)
                self.assertTrue(assessment.approval_route)

    def test_not_assessed_never_claims_low_risk(self):
        assessment = assess_intake_risk(self._values(paper_source=''), template_applied=True)
        self.assertEqual(assessment.label, 'Risk not assessed')
        self.assertIsNone(assessment.level)
        self.assertIn('paper_source', assessment.blocking_fields)

    def test_routing_distinguishes_privacy_safeguards_and_third_party_paper(self):
        protected_transfer = derive_intake_route(
            self._values(data_transfer_flag=True, scc_attached=True), template_applied=True,
        )
        self.assertNotIn('Privacy', [item['role'] for item in protected_transfer.reviewers])

        unresolved_transfer = derive_intake_route(
            self._values(data_transfer_flag=True, scc_attached=False), template_applied=True,
        )
        privacy_reason = next(item['reason'] for item in unresolved_transfer.reviewers if item['role'] == 'Privacy')
        self.assertIn('without confirmed approved safeguards', privacy_reason)

        third_party = derive_intake_route(
            self._values(paper_source=Contract.PaperSource.COUNTERPARTY_PAPER), template_applied=True,
        )
        self.assertEqual(third_party.template_status, 'Not applicable')
        self.assertEqual(third_party.review_mode, 'Deviation review')
        self.assertEqual(third_party.playbook, 'Commercial playbook')
        self.assertTrue(third_party.comparison_baseline)

    def test_high_value_uses_named_finance_approver(self):
        route = derive_intake_route(self._values(value='150000'), template_applied=True)
        self.assertEqual(route.approvers[0]['role'], 'Finance Director')
        self.assertIn('threshold', route.approvers[0]['reason'].lower())


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

    def test_new_request_hides_manual_state_controls_and_uses_custom_validation(self):
        response = self._get()
        form = response.context['form']
        content = response.content.decode()

        self.assertNotIn('status', form.fields)
        self.assertNotIn('lifecycle_stage', form.fields)
        self.assertNotIn('risk_level', form.fields)
        self.assertIn('id="contract-form" novalidate', content)
        self.assertIn('Starting template', content)
        self.assertIn('Review playbook', content)
        self.assertIn('id="launch-setup-playbook-copy"', content)
        self.assertNotIn('Playbook applied', content)
        self.assertIn('Save draft', content)
        self.assertIn('Create contract', content)
        self.assertIn('Risk not assessed', content)

    def test_new_request_right_rail_avoids_unnecessary_header_dividers(self):
        content = self._get().content.decode()
        self.assertIn('.cform-rail-head {', content)
        self.assertEqual(content.count('class="cform-rail-head"'), 3)

    def test_new_request_has_sticky_action_bar_and_no_footer(self):
        response = self._get()
        content = response.content.decode()
        self.assertIn('cform-bottom-actions', content)
        self.assertIn('cform-bottom-actions__cluster', content)
        self.assertIn('position: fixed', content)
        self.assertIn('width: max-content', content)
        self.assertIn('pointer-events: none;', content)
        self.assertIn('pointer-events: auto;', content)
        self.assertIn('flex-direction: column;', content)
        self.assertIn('id="contract-form-top-actions"', content)
        self.assertIn('id="contract-form-sticky-actions"', content)
        self.assertIn("stickyActions.classList.toggle('is-docked-hidden', topActionsVisible);", content)
        self.assertContains(response, 'Save draft')
        self.assertContains(response, 'Create contract')
        self.assertNotContains(response, 'CLM One B.V. All rights reserved.')
        self.assertNotIn('submit-contract-btn" disabled', content)

    def test_new_request_workflow_header_is_intake_first_and_compact(self):
        """The new-request strip is a compact intake context bar."""
        self.user.first_name = 'Alex'
        self.user.last_name = 'Admin'
        self.user.save(update_fields=['first_name', 'last_name'])

        response = self._get()
        content = response.content.decode()
        workflow_start = content.index('class="cform-context-bar cform-stepper"')
        workflow_end = content.index('id="contract-identity-heading"', workflow_start)
        workflow = content[workflow_start:workflow_end]

        self.assertIn('Contract intake', workflow)
        self.assertIn('In progress', workflow)
        self.assertIn('Owner: <strong>Alex Admin</strong>', workflow)
        self.assertIn('Stage 1 of 6 · Intake', workflow)
        self.assertIn('id="command-progress"', workflow)
        self.assertIn('required fields complete', workflow)
        self.assertIn('View workflow', workflow)
        self.assertIn('cform-workflow-reveal', workflow)
        self.assertNotIn('cform-kicker', workflow)
        self.assertNotIn('>Workflow<', workflow)
        self.assertNotIn('cform-command-stats', workflow)
        self.assertNotIn('cform-command-meta', workflow)
        self.assertNotIn('command-next-action', workflow)
        self.assertNotIn('command-blocker', workflow)
        self.assertNotIn('Next <strong', workflow)
        self.assertNotIn('Remaining <strong', workflow)
        self.assertNotIn('Capture the parties, commercial terms, and review path needed to open this request.', workflow)
        self.assertNotIn('Complete the required intake fields to create the contract and begin drafting.', content)
        # Full lifecycle is present but collapsed behind View workflow.
        self.assertNotIn('<details class="cform-workflow-reveal" open', workflow)
        expected_stages = ('Intake', 'Drafting', 'Internal review', 'Negotiation', 'Approval', 'Signature')
        for stage in expected_stages:
            self.assertIn(f'<span class="lc-label">{stage}</span>', workflow)
        # Actions live in the shell title row with New Contract Request.
        self.assertIn('id="contract-form-top-actions"', content)
        self.assertIn('topbar-page-actions', content)
        self.assertIn('form="contract-form"', content)

    def test_new_request_create_ctas_use_standard_teal_button_treatment(self):
        response = self._get()
        content = response.content.decode()

        # Form CTAs only (shell topbar also uses --primary for New Contract).
        self.assertEqual(content.count('id="submit-contract-btn"'), 1)
        self.assertIn('form="contract-form" class="dc-ds-button dc-ds-button--primary"', content)
        self.assertIn('id="submit-contract-btn">Create contract</button>', content)
        self.assertNotIn('btn-cta', content)
        self.assertNotIn('cform-create-cta', content)
        self.assertNotIn('var(--copper-700)', content)
        self.assertIn('background: var(--seal);', content)

    def test_new_request_uses_compact_checkbox_tiles_and_consistent_disclosures(self):
        response = self._get()
        content = response.content.decode()
        self.assertIn('align-items: center;', content)
        self.assertIn('min-height: 0;', content)
        self.assertIn('padding: 8px 10px;', content)
        self.assertIn('.cform-disclosure[open] .details-chevron', content)
        self.assertEqual(
            content.count('cform-collapsible cform-disclosure"'),
            3,
        )
        self.assertIn('card-l1 cform-disclosure"', content)
        risk_start = content.index('aria-labelledby="risk-signals-heading"')
        risk_end = content.index('</section>', risk_start)
        self.assertNotIn('details-chevron', content[risk_start:risk_end])

    def test_new_request_validation_scrolls_to_first_invalid_field_and_expands_sections(self):
        response = self._get()
        content = response.content.decode()
        self.assertIn('missing.forEach(revealField);', content)
        self.assertIn("scrollIntoView({ behavior: 'smooth', block: 'center' });", content)
        self.assertIn("focus({ preventScroll: true });", content)
        self.assertNotIn('submitBtn.disabled = missing.length > 0', content)

    def test_owner_choices_use_display_names_not_internal_usernames(self):
        self.user.first_name = 'Alex'
        self.user.last_name = 'Admin'
        self.user.save(update_fields=['first_name', 'last_name'])

        response = self._get()
        self.assertContains(response, f'<option value="{self.user.pk}" selected>Alex Admin</option>', html=True)

    def test_create_ignores_forged_manual_state_and_derives_privacy_risk(self):
        response = self.client_.post(reverse('contracts:contract_create'), {
            'title': 'Derived risk contract',
            'contract_type': Contract.ContractType.NDA,
            'content': 'Body',
            'counterparty': 'Acme Corp',
            'owner': self.user.pk,
            'currency': Contract.Currency.USD,
            'governing_law': 'State of Delaware',
            'jurisdiction': 'New York',
            'start_date': '2026-07-15',
            'end_date': '2027-07-15',
            'paper_source': Contract.PaperSource.OUR_PAPER,
            'data_transfer_flag': 'on',
            # A forged POST must not bypass the intake state model.
            'status': Contract.Status.ACTIVE,
            'lifecycle_stage': 'EXECUTED',
            'risk_level': Contract.RiskLevel.CRITICAL,
        })

        self.assertEqual(response.status_code, 302)
        created = Contract.objects.get(title='Derived risk contract')
        self.assertEqual(created.status, Contract.Status.IN_PROGRESS)
        self.assertEqual(created.lifecycle_stage, 'DRAFTING')
        self.assertEqual(created.risk_level, Contract.RiskLevel.MEDIUM)

    def test_new_request_uses_plain_language_privacy_prompts_and_calculates_notice_deadline(self):
        response = self._get()
        self.assertContains(response, 'Will this agreement involve transferring personal data across borders?')
        self.assertContains(response, 'Is a data processing agreement already included?')
        self.assertContains(response, 'Are standard contractual clauses already included?')

        response = self.client_.post(reverse('contracts:contract_create'), {
            'title': 'Calculated notice deadline contract',
            'contract_type': Contract.ContractType.NDA,
            'content': 'Body',
            'counterparty': 'Acme Corp',
            'owner': self.user.pk,
            'currency': Contract.Currency.USD,
            'governing_law': 'State of Delaware',
            'jurisdiction': 'New York',
            'start_date': '2026-07-15',
            'end_date': '2027-07-15',
            'notice_period_days': '30',
        })

        self.assertEqual(response.status_code, 302)
        created = Contract.objects.get(title='Calculated notice deadline contract')
        self.assertEqual(str(created.termination_notice_date), '2027-06-15')

    def test_law_firm_ops_core_sections_unchanged(self):
        """Preservation check: the pre-existing intake sections are all
        still there, untouched by this feature."""
        response = self._get()
        for text in ('Contract identity', 'Commercial terms and jurisdiction', 'Review triggers', 'Dates and lifecycle management'):
            self.assertContains(response, text)

    def test_privacy_section_uses_the_same_header_affordance_as_legal_posture(self):
        response = self._get()
        self.assertContains(
            response,
            'data-required-note-fields="personal_data_processing sensitive_data_flag counterparty_privacy_review_required data_transfer_flag dpa_attached scc_attached"',
        )
        self.assertContains(response, 'details-chevron')
        self.assertContains(response, 'Controls routing')

    def test_no_leaked_django_template_comment_markers(self):
        """Regression guard: a multi-line {# #} comment does not get
        stripped by Django's template engine (unlike {% comment %}) and
        renders as literal text — this must never appear in the page."""
        response = self._get()
        content = response.content.decode()
        self.assertNotIn('{#', content)
        self.assertNotIn('Contract Launch Setup data', content)

    def test_collapsible_sections_present_and_collapsed_by_default(self):
        """Contract identity stays visible; Legal posture and Draft brief
        start closed, while Lifecycle control stays open because it holds the
        required launch fields."""
        response = self._get()
        content = response.content.decode()
        self.assertIn('data-collapsible="legal-posture"', content)
        self.assertIn('data-collapsible="lifecycle-control"', content)
        self.assertIn('data-collapsible="draft-brief"', content)
        for key in ('legal-posture', 'draft-brief'):
            idx = content.index(f'data-collapsible="{key}"')
            # The <details ...> tag itself must not carry the `open` attribute.
            tag_start = content.rindex('<details', 0, idx + 1)
            tag_end = content.index('>', tag_start)
            self.assertNotIn(' open', content[tag_start:tag_end])

        lifecycle_idx = content.index('data-collapsible="lifecycle-control"')
        lifecycle_tag_start = content.rindex('<details', 0, lifecycle_idx + 1)
        lifecycle_tag_end = content.index('>', lifecycle_tag_start)
        self.assertIn(' open', content[lifecycle_tag_start:lifecycle_tag_end])

    def test_sticky_support_rail_cards_present(self):
        response = self._get()
        for text in ('Readiness', 'Required now', 'Selected setup', 'Risk &amp; review route'):
            self.assertContains(response, text)
        for text in ('Route preview', 'AI Governance Panel', 'After create'):
            self.assertNotContains(response, text)

    def test_create_audit_records_derived_risk_and_routing(self):
        response = self.client_.post(reverse('contracts:contract_create'), {
            'title': 'Audited draft',
            'contract_type': Contract.ContractType.SOW,
            'counterparty': 'Acme Corp',
            'owner': self.user.pk,
            'currency': Contract.Currency.USD,
            'governing_law': 'State of Delaware',
            'jurisdiction': 'New York',
            'paper_source': Contract.PaperSource.OUR_PAPER,
            'start_date': '2026-07-15',
            'end_date': '2027-07-15',
        })
        self.assertEqual(response.status_code, 302)
        contract = Contract.objects.get(title='Audited draft')
        audit = AuditLog.objects.filter(model_name='Contract', object_id=contract.pk).latest('timestamp')
        self.assertEqual(audit.changes['risk_assessment']['state'], 'PRELIMINARY')
        self.assertEqual(audit.changes['risk_assessment']['level'], Contract.RiskLevel.LOW)
        self.assertTrue(audit.changes['review_route'])
        self.assertTrue(audit.changes['approval_route'])
        self.assertEqual(audit.changes['selected_playbook'], 'Commercial playbook')
        detail = self.client_.get(reverse('contracts:contract_detail', kwargs={'pk': contract.pk}))
        self.assertContains(detail, 'Preliminary Low risk')

    def test_empty_and_invalid_submissions_keep_values_and_return_field_errors(self):
        response = self.client_.post(reverse('contracts:contract_create'), {})
        self.assertEqual(response.status_code, 200)
        for field_name in ('title', 'contract_type', 'counterparty', 'owner', 'governing_law', 'start_date', 'end_date'):
            self.assertIn(field_name, response.context['form'].errors)

        response = self.client_.post(reverse('contracts:contract_create'), {
            'title': 'Keep this title',
            'contract_type': Contract.ContractType.SOW,
            'owner': self.user.pk,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['form']['title'].value(), 'Keep this title')
        self.assertIn('counterparty', response.context['form'].errors)

    def test_member_cannot_assign_another_owner_or_inactive_owner(self):
        member = User.objects.create_user(username='drafting_member', password='testpass123!')
        active_owner = User.objects.create_user(username='other_active_owner', password='testpass123!')
        inactive_owner = User.objects.create_user(username='inactive_owner', password='testpass123!')
        OrganizationMembership.objects.create(organization=self.org, user=member, role=OrganizationMembership.Role.MEMBER, is_active=True)
        OrganizationMembership.objects.create(organization=self.org, user=active_owner, role=OrganizationMembership.Role.MEMBER, is_active=True)
        OrganizationMembership.objects.create(organization=self.org, user=inactive_owner, role=OrganizationMembership.Role.MEMBER, is_active=False)
        member_client = TestClient()
        member_client.login(username=member.username, password='testpass123!')

        response = member_client.get(reverse('contracts:contract_create'))
        owner_queryset = response.context['form'].fields['owner'].queryset
        self.assertEqual(list(owner_queryset), [member])
        self.assertEqual(response.context['form']['owner'].value(), member.pk)

        response = member_client.post(reverse('contracts:contract_create'), {
            'title': 'Forged owner draft', 'contract_type': Contract.ContractType.SOW,
            'counterparty': 'Acme Corp', 'owner': active_owner.pk, 'currency': Contract.Currency.USD,
            'governing_law': 'State of Delaware', 'jurisdiction': 'New York',
            'paper_source': Contract.PaperSource.OUR_PAPER,
            'start_date': '2026-07-15', 'end_date': '2027-07-15',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Contract.objects.filter(title='Forged owner draft').exists())
        self.assertIn('owner', response.context['form'].errors)

    def test_setup_copy_distinguishes_new_drafts_from_existing_agreements(self):
        response = self._get()
        self.assertContains(response, 'Start a new draft here.')
        self.assertContains(response, 'Upload &amp; Review')

    def test_creating_a_contract_still_works_end_to_end(self):
        """Preserve existing contract creation behavior end-to-end."""
        response = self.client_.post(reverse('contracts:contract_create'), {
            'title': 'Launch Setup Regression Contract',
            'contract_type': Contract.ContractType.NDA,
            'content': 'Body',
            'status': Contract.Status.IN_PROGRESS,
            'counterparty': 'Acme Corp',
            'owner': self.user.pk,
            'currency': Contract.Currency.USD,
            'governing_law': 'State of Delaware',
            'jurisdiction': 'New York',
            'risk_level': Contract.RiskLevel.LOW,
            'lifecycle_stage': 'DRAFTING',
            'start_date': '2026-07-15',
            'end_date': '2027-07-15',
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
