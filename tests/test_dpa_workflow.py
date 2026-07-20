"""DPA Privacy Review Workflow — the first flagship "workflow-first" flow.

Covers: seed data (contracts/migrations/0071_seed_dpa_workflow.py), the
service layer (contracts/services/dpa_workflow.py), the builder view
(contracts/views_domains/dpa_workflow.py), Stage 1 routing, and the
Command Center Priority Queue projection.
"""
from django.contrib.auth import get_user_model
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from contracts.models import (
    ApprovalRequest,
    ApprovalRoute,
    AuditLog,
    CommandCenterWorkItem,
    Contract,
    ContractTemplate,
    ContractType,
    FieldDefinition,
    FieldValue,
    Organization,
    OrganizationMembership,
    RiskSignal,
    Workflow,
    WorkflowStep,
    WorkflowTemplate,
    WorkflowTemplateStep,
)
from contracts.services.dpa_workflow import (
    create_dpa_workflow_instance,
    detect_dpa_risk_signals,
    get_dpa_workflow_template,
    get_field_definitions_by_section,
    render_dpa_live_preview,
)
from contracts.views_domains.dpa_workflow import _dpa_governance_results

User = get_user_model()


def _make_org_with_user(label, username, workspace_mode=None):
    kwargs = {}
    if workspace_mode:
        kwargs['workspace_mode'] = workspace_mode
    org = Organization.objects.create(name=f'{label} {username}', slug=f'{label.lower().replace(" ", "-")}-{username}', **kwargs)
    user = User.objects.create_user(username=username, password='testpass123!')
    OrganizationMembership.objects.create(organization=org, user=user, role=OrganizationMembership.Role.OWNER, is_active=True)
    client_ = TestClient()
    client_.login(username=username, password='testpass123!')
    return org, user, client_


class SeedDataTests(TestCase):
    def test_contract_type_seeded(self):
        ct = ContractType.objects.get(code='DPA')
        self.assertEqual(ct.name, 'Data Processing Agreement')
        self.assertTrue(ct.is_active)

    def test_workflow_template_seeded_and_linked(self):
        wt = WorkflowTemplate.objects.get(name='DPA Privacy Review Workflow')
        self.assertTrue(wt.is_active)
        self.assertEqual(wt.contract_type.code, 'DPA')
        self.assertEqual(wt.category, 'COMPLIANCE')

    def test_four_steps_in_order_with_correct_kinds(self):
        wt = WorkflowTemplate.objects.get(name='DPA Privacy Review Workflow')
        steps = list(WorkflowTemplateStep.objects.filter(template=wt).order_by('order'))
        self.assertEqual([s.name for s in steps], ['Draft', 'Legal Review', 'DPO / Privacy Review', 'Approval'])
        self.assertEqual([s.step_kind for s in steps], ['TASK', 'APPROVAL', 'APPROVAL', 'APPROVAL'])
        dpo_step = steps[2]
        self.assertEqual(dpo_step.condition_expression, 'data_transfer=true')

    def test_field_definitions_cover_all_sections(self):
        wt = WorkflowTemplate.objects.get(name='DPA Privacy Review Workflow')
        keys = set(FieldDefinition.objects.filter(workflow_template=wt).values_list('key', flat=True))
        for expected in ('counterparty', 'start_date', 'contract_owner', 'processing_purpose',
                          'personal_data_categories', 'data_subjects', 'governing_law',
                          'liability_position', 'personal_data_involved', 'cross_border_transfer',
                          'subprocessors_used', 'transfer_mechanism', 'breach_notification_hours',
                          'dpo_contact', 'special_categories_data', 'include_scc_fallback'):
            self.assertIn(expected, keys)

    def test_smart_question_toggles_are_consolidated_in_privacy_questions_section(self):
        """The five yes/no risk-routing toggles (AI Smart Questions) all live
        in one section so the cockpit can render them together, per
        contracts/migrations/0074_dpa_smart_questions_expansion.py."""
        wt = WorkflowTemplate.objects.get(name='DPA Privacy Review Workflow')
        toggle_keys = {'personal_data_involved', 'cross_border_transfer', 'subprocessors_used',
                       'special_categories_data', 'include_scc_fallback'}
        sections = {
            f.key: f.section
            for f in FieldDefinition.objects.filter(workflow_template=wt, key__in=toggle_keys)
        }
        self.assertEqual(set(sections.values()), {FieldDefinition.Section.PRIVACY_QUESTIONS})
        for key in toggle_keys:
            self.assertEqual(FieldDefinition.objects.get(workflow_template=wt, key=key).field_type, FieldDefinition.FieldType.BOOLEAN)

    def test_smart_question_help_text_explains_why_it_matters(self):
        wt = WorkflowTemplate.objects.get(name='DPA Privacy Review Workflow')
        help_text_by_key = {
            'personal_data_involved': 'Required for GDPR routing and DPO approval.',
            'cross_border_transfer': 'Triggers SCC review and international transfer language.',
            'subprocessors_used': 'Adds subprocessor review and approval checks.',
        }
        for key, expected_help in help_text_by_key.items():
            self.assertEqual(FieldDefinition.objects.get(workflow_template=wt, key=key).help_text, expected_help)

    def test_cross_border_transfer_still_maps_to_contract_field(self):
        """Moving the field into PRIVACY_QUESTIONS must not disturb its
        Contract.data_transfer_flag mapping (relied on by the workflow
        step condition_expression 'data_transfer=true')."""
        wt = WorkflowTemplate.objects.get(name='DPA Privacy Review Workflow')
        field = FieldDefinition.objects.get(workflow_template=wt, key='cross_border_transfer')
        self.assertEqual(field.maps_to_contract_field, 'data_transfer_flag')

    def test_approval_route_seeded_in_order_with_conditionals(self):
        wt = WorkflowTemplate.objects.get(name='DPA Privacy Review Workflow')
        routes = list(ApprovalRoute.objects.filter(workflow_template=wt).order_by('order'))
        self.assertEqual([r.name for r in routes], ['Contract Owner', 'Legal', 'DPO', 'Finance'])
        self.assertEqual([r.is_conditional for r in routes], [False, False, True, True])

    def test_dpa_contract_template_enriched_with_new_tokens(self):
        template = ContractTemplate.objects.get(name='Standard Data Processing Agreement')
        self.assertTrue(template.is_active)
        for token in ('{{processing_purpose}}', '{{personal_data_categories}}', '{{data_transfer_position}}',
                      '{{subprocessor_position}}', '{{transfer_mechanism}}', '{{dpo_contact}}',
                      '{{breach_notification_hours}}'):
            self.assertIn(token, template.body)


class GetFieldDefinitionsBySectionTests(TestCase):
    def test_returns_non_empty_ordered_sections(self):
        wt = get_dpa_workflow_template()
        grouped = get_field_definitions_by_section(wt)
        self.assertEqual(
            list(grouped.keys()),
            [
                FieldDefinition.Section.BASIC_DETAILS,
                FieldDefinition.Section.PRIVACY_DETAILS,
                FieldDefinition.Section.LEGAL_POSITION,
                FieldDefinition.Section.PRIVACY_QUESTIONS,
            ],
        )
        self.assertTrue(grouped[FieldDefinition.Section.BASIC_DETAILS])
        self.assertTrue(grouped[FieldDefinition.Section.PRIVACY_QUESTIONS])
        for fields in grouped.values():
            orders = [f.order for f in fields]
            self.assertEqual(orders, sorted(orders))

    def test_none_template_returns_empty_sections(self):
        grouped = get_field_definitions_by_section(None)
        self.assertTrue(all(v == [] for v in grouped.values()))


class RenderDpaLivePreviewTests(TestCase):
    def test_substitutes_field_definition_token(self):
        result = render_dpa_live_preview('Contact: {{dpo_contact}}', {'dpo_contact': 'privacy@acme.com'})
        self.assertEqual(result, 'Contact: privacy@acme.com')

    def test_substitutes_merge_field_alias(self):
        result = render_dpa_live_preview('Effective {{effective_date}}', {'start_date': '2026-09-01'})
        self.assertEqual(result, 'Effective 2026-09-01')

    def test_leaves_unrecognized_token_untouched(self):
        result = render_dpa_live_preview('Party: {{title}}', {'counterparty': 'Acme'})
        self.assertEqual(result, 'Party: {{title}}')

    def test_blank_body_returns_blank(self):
        self.assertEqual(render_dpa_live_preview(None, {}), '')

    def test_confirmed_scc_changes_transfer_position_copy(self):
        confirmed_scc = render_dpa_live_preview(
            '{{data_transfer_position}}',
            {'cross_border_transfer': True, 'transfer_mechanism': 'SCC'},
        )
        unconfirmed = render_dpa_live_preview(
            '{{data_transfer_position}}',
            {'cross_border_transfer': True, 'transfer_mechanism': 'None'},
        )
        self.assertIn('SCC', confirmed_scc)
        self.assertIn('confirmed transfer safeguard', unconfirmed)


class DetectDpaRiskSignalsTests(TestCase):
    def setUp(self):
        self.org, self.user, _ = _make_org_with_user('Risk Org', 'risk_user')
        contract = Contract.objects.create(organization=self.org, title='DPA test', contract_type=Contract.ContractType.DPA)
        wt = get_dpa_workflow_template()
        self.workflow = Workflow.objects.create(title='t', organization=self.org, template=wt, contract=contract)

    def test_cross_border_without_mechanism_creates_high_signal(self):
        detect_dpa_risk_signals(self.workflow, {'cross_border_transfer': True, 'transfer_mechanism': 'None', 'dpo_contact': 'x@y.com', 'breach_notification_hours': 24})
        signal = RiskSignal.objects.get(workflow=self.workflow, code='cross_border_no_mechanism')
        self.assertEqual(signal.severity, RiskSignal.Severity.HIGH)

    def test_blank_dpo_contact_creates_medium_signal(self):
        detect_dpa_risk_signals(self.workflow, {'cross_border_transfer': False, 'dpo_contact': '', 'breach_notification_hours': 24})
        signal = RiskSignal.objects.get(workflow=self.workflow, code='missing_dpo_contact')
        self.assertEqual(signal.severity, RiskSignal.Severity.MEDIUM)

    def test_clean_submission_keeps_required_dpa_review_signal(self):
        detect_dpa_risk_signals(self.workflow, {
            'personal_data_involved': False, 'cross_border_transfer': False, 'subprocessors_used': False, 'transfer_mechanism': 'None',
            'dpo_contact': 'privacy@acme.com', 'breach_notification_hours': 24, 'liability_position': '',
        })
        signals = RiskSignal.objects.filter(workflow=self.workflow)
        self.assertEqual(signals.count(), 1)
        self.assertEqual(signals.get().code, 'dpa_review_required')

    def test_signals_are_persisted_not_just_returned(self):
        created = detect_dpa_risk_signals(self.workflow, {'cross_border_transfer': False, 'dpo_contact': '', 'breach_notification_hours': 24})
        self.assertEqual(RiskSignal.objects.filter(workflow=self.workflow).count(), len(created))
        self.assertGreater(len(created), 0)

    def test_special_categories_data_creates_high_signal(self):
        detect_dpa_risk_signals(self.workflow, {
            'special_categories_data': True, 'dpo_contact': 'x@y.com', 'breach_notification_hours': 24,
        })
        signal = RiskSignal.objects.get(workflow=self.workflow, code='special_categories_risk')
        self.assertEqual(signal.severity, RiskSignal.Severity.HIGH)
        self.assertIn('Legal and DPO review', signal.description)

    def test_uncertain_privacy_fact_blocks_approval_and_signature(self):
        detect_dpa_risk_signals(self.workflow, {
            'dpo_contact': 'x@y.com', 'breach_notification_hours': 24,
            '_dpa_step3': {'subprocessors_answer': 'not_sure'},
        })
        signal = RiskSignal.objects.get(workflow=self.workflow, code='privacy_fact_uncertain')
        self.assertEqual(signal.severity, RiskSignal.Severity.HIGH)
        self.assertIn('before approval or signature', signal.description)

    def test_scc_fallback_included_creates_low_signal(self):
        detect_dpa_risk_signals(self.workflow, {
            'include_scc_fallback': True, 'dpo_contact': 'x@y.com', 'breach_notification_hours': 24,
        })
        signal = RiskSignal.objects.get(workflow=self.workflow, code='scc_fallback_included')
        self.assertEqual(signal.severity, RiskSignal.Severity.LOW)

    def test_no_special_categories_or_scc_fallback_signals_when_unset(self):
        detect_dpa_risk_signals(self.workflow, {
            'personal_data_involved': False, 'special_categories_data': False, 'include_scc_fallback': False,
            'dpo_contact': 'x@y.com', 'breach_notification_hours': 24,
        })
        self.assertFalse(RiskSignal.objects.filter(workflow=self.workflow, code='special_categories_risk').exists())
        self.assertFalse(RiskSignal.objects.filter(workflow=self.workflow, code='scc_fallback_included').exists())


class CreateDpaWorkflowInstanceTests(TestCase):
    def setUp(self):
        self.org, self.user, _ = _make_org_with_user('Create Org', 'create_user')

    def _cleaned_values(self, **overrides):
        values = {
            'counterparty': 'Acme Robotics Inc.',
            'start_date': '2026-09-01',
            'contract_owner': 'Avery Brooks',
            'processing_purpose': 'Providing hosted logistics analytics.',
            'personal_data_categories': 'Business contact details and account identifiers.',
            'data_subjects': 'Customer administrators and end users.',
            'governing_law': 'State of Delaware',
            'liability_position': '',
            'personal_data_involved': True,
            'cross_border_transfer': True,
            'subprocessors_used': False,
            'transfer_mechanism': 'SCC',
            'breach_notification_hours': 48,
            'dpo_contact': 'privacy@acme.com',
        }
        values.update(overrides)
        return values

    def test_creates_contract_with_mapped_fields(self):
        workflow = create_dpa_workflow_instance(organization=self.org, user=self.user, cleaned_values=self._cleaned_values())
        contract = workflow.contract
        self.assertEqual(contract.status, Contract.Status.IN_PROGRESS)
        self.assertEqual(contract.contract_type, Contract.ContractType.DPA)
        self.assertEqual(contract.counterparty, 'Acme Robotics Inc.')
        self.assertTrue(contract.data_transfer_flag)

    def test_creates_workflow_linked_to_dpa_template(self):
        workflow = create_dpa_workflow_instance(organization=self.org, user=self.user, cleaned_values=self._cleaned_values())
        self.assertEqual(workflow.template.name, 'DPA Privacy Review Workflow')
        self.assertEqual(workflow.status, Workflow.Status.ACTIVE)

    def test_materializes_four_steps_dpo_step_pending_when_cross_border(self):
        workflow = create_dpa_workflow_instance(organization=self.org, user=self.user, cleaned_values=self._cleaned_values(cross_border_transfer=True))
        steps = {s.name: s.status for s in workflow.steps.all()}
        self.assertEqual(len(steps), 4)
        self.assertEqual(steps['Draft'], WorkflowStep.Status.IN_PROGRESS)
        self.assertEqual(steps['DPO / Privacy Review'], WorkflowStep.Status.PENDING)

    def test_dpo_step_skipped_when_no_cross_border_transfer(self):
        workflow = create_dpa_workflow_instance(organization=self.org, user=self.user, cleaned_values=self._cleaned_values(cross_border_transfer=False))
        dpo_step = workflow.steps.get(name='DPO / Privacy Review')
        self.assertEqual(dpo_step.status, WorkflowStep.Status.SKIPPED)

    def test_field_values_created_for_every_field_definition(self):
        workflow = create_dpa_workflow_instance(organization=self.org, user=self.user, cleaned_values=self._cleaned_values())
        expected_count = FieldDefinition.objects.filter(workflow_template=workflow.template).count()
        self.assertEqual(FieldValue.objects.filter(workflow=workflow).count(), expected_count)

    def test_draft_document_created_current_with_substituted_content(self):
        workflow = create_dpa_workflow_instance(organization=self.org, user=self.user, cleaned_values=self._cleaned_values())
        doc = workflow.draft_documents.get(is_current=True)
        self.assertEqual(doc.version, 1)
        self.assertIn('Acme Robotics Inc.', doc.content)

    def test_command_center_work_item_created(self):
        workflow = create_dpa_workflow_instance(organization=self.org, user=self.user, cleaned_values=self._cleaned_values())
        item = CommandCenterWorkItem.objects.get(workflow=workflow)
        self.assertEqual(item.source_type, CommandCenterWorkItem.SourceType.WORKFLOW)
        self.assertEqual(item.contract, workflow.contract)
        self.assertEqual(item.action_path, reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))

    def test_risk_level_high_when_high_severity_signal_detected(self):
        # cross_border_transfer with no transfer_mechanism is a HIGH signal.
        workflow = create_dpa_workflow_instance(
            organization=self.org, user=self.user,
            cleaned_values=self._cleaned_values(cross_border_transfer=True, transfer_mechanism=''),
        )
        self.assertEqual(workflow.contract.risk_level, Contract.RiskLevel.HIGH)

    def test_risk_level_medium_when_only_medium_signals_detected(self):
        # personal_data_involved (default True) alone is a MEDIUM signal with no HIGH signals present.
        workflow = create_dpa_workflow_instance(
            organization=self.org, user=self.user,
            cleaned_values=self._cleaned_values(
                cross_border_transfer=False, subprocessors_used=False,
                dpo_contact='privacy@acme.com', breach_notification_hours=48,
            ),
        )
        self.assertEqual(workflow.contract.risk_level, Contract.RiskLevel.MEDIUM)

    def test_risk_level_keeps_dpa_baseline_review_when_no_conditional_signals_detected(self):
        workflow = create_dpa_workflow_instance(
            organization=self.org, user=self.user,
            cleaned_values=self._cleaned_values(
                personal_data_involved=False, cross_border_transfer=False, subprocessors_used=False,
                dpo_contact='privacy@acme.com', breach_notification_hours=48,
            ),
        )
        self.assertEqual(workflow.contract.risk_level, Contract.RiskLevel.MEDIUM)

    def test_special_categories_and_scc_fallback_field_values_and_signals_created(self):
        workflow = create_dpa_workflow_instance(
            organization=self.org, user=self.user,
            cleaned_values=self._cleaned_values(special_categories_data=True, include_scc_fallback=True),
        )
        special_categories_value = FieldValue.objects.get(workflow=workflow, field_definition__key='special_categories_data')
        scc_fallback_value = FieldValue.objects.get(workflow=workflow, field_definition__key='include_scc_fallback')
        self.assertTrue(special_categories_value.value)
        self.assertTrue(scc_fallback_value.value)
        self.assertTrue(RiskSignal.objects.filter(workflow=workflow, code='special_categories_risk').exists())
        self.assertTrue(RiskSignal.objects.filter(workflow=workflow, code='scc_fallback_included').exists())


class DPAWorkflowBuilderViewIntegrationTests(TestCase):
    def setUp(self):
        self.org, self.user, self.client_ = _make_org_with_user('Builder Org', 'builder_user')

    def _field_ids(self):
        wt = get_dpa_workflow_template()
        return {f.key: f.id for f in FieldDefinition.objects.filter(workflow_template=wt)}

    def _valid_payload(self):
        ids = self._field_ids()
        return {
            f'field_{ids["counterparty"]}': 'Northwind Logistics',
            f'field_{ids["start_date"]}': '2026-09-01',
            f'field_{ids["contract_owner"]}': 'Avery Brooks',
            f'field_{ids["processing_purpose"]}': 'Providing hosted logistics analytics.',
            f'field_{ids["personal_data_categories"]}': 'Business contact details and account identifiers.',
            f'field_{ids["data_subjects"]}': 'Customer administrators and end users.',
            f'field_{ids["governing_law"]}': 'State of Delaware',
            f'field_{ids["transfer_mechanism"]}': 'SCC',
            f'field_{ids["breach_notification_hours"]}': '48',
            f'field_{ids["personal_data_involved"]}': 'on',
            f'field_{ids["cross_border_transfer"]}': 'on',
        }

    def test_get_renders_a_focused_first_intake_step(self):
        response = self.client_.get(reverse('contracts:dpa_workflow_builder'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        for label in ('Agreement details', 'Counterparty name', 'Contract owner', 'Effective date'):
            self.assertIn(label, content)
        self.assertIn('Step 1 of 4', content)
        self.assertNotIn('Live contract preview', content)

    def test_intake_does_not_expose_pre_generation_governance_or_ai_controls(self):
        response = self.client_.get(reverse('contracts:dpa_workflow_builder'))
        content = response.content.decode()
        for removed_control in ('Live contract preview', 'Contract draft', 'Governance', 'Audit trail',
                                'Suggest missing values', 'Compare to playbook'):
            self.assertNotIn(removed_control, content)

    def test_get_renders_wizard_actions_without_a_progress_bar(self):
        response = self.client_.get(reverse('contracts:dpa_workflow_builder'))
        for label in ('Save and exit', 'Continue'):
            self.assertContains(response, label)
        self.assertNotContains(response, 'Required questions')

    def test_processing_purpose_explains_what_to_enter(self):
        response = self.client_.get(f"{reverse('contracts:dpa_workflow_builder')}?step=2")
        content = response.content.decode()
        self.assertContains(response, 'State the service purpose in plain language.')
        self.assertContains(response, 'What should I enter for Processing purpose?')
        self.assertContains(response, 'To provide, operate and support the service')
        self.assertIn('aria-describedby="field-', content)

    def test_step3_uses_operational_questions_without_legacy_legal_controls(self):
        response = self.client_.get(f"{reverse('contracts:dpa_workflow_builder')}?step=3")
        self.assertContains(response, 'What personal data will be processed?')
        self.assertContains(response, 'Whose data will be processed?')
        self.assertContains(response, 'Choose data categories')
        self.assertContains(response, 'Choose data subjects')
        self.assertContains(response, 'Search processing countries')
        self.assertContains(response, 'Not sure')
        self.assertContains(response, 'confirm whether sensitive or criminal-offence data is involved')
        self.assertNotContains(response, 'Will the counterparty process personal data?')
        self.assertNotContains(response, 'Should SCC fallback language be included?')
        self.assertNotContains(response, 'Derived outcomes')

    def test_save_and_resume_intake(self):
        ids = self._field_ids()
        response = self.client_.post(reverse('contracts:dpa_workflow_builder'), {
            'action': 'continue', 'step': '1',
            f'field_{ids["counterparty"]}': 'Resume Co.',
            f'field_{ids["contract_owner"]}': 'Avery Brooks',
            f'field_{ids["start_date"]}': '2026-09-01',
        })
        self.assertRedirects(response, f'{reverse("contracts:dpa_workflow_builder")}?step=2')
        resumed = self.client_.get(reverse('contracts:dpa_workflow_builder'))
        self.assertContains(resumed, 'Step 2 of 4')
        response = self.client_.post(reverse('contracts:dpa_workflow_builder'), {
            'action': 'save_exit', 'step': '2', f'field_{ids["processing_purpose"]}': 'Hosted analytics.',
        })
        self.assertRedirects(response, reverse('contracts:contract_template_picker'))
        resumed = self.client_.get(reverse('contracts:dpa_workflow_builder'))
        self.assertContains(resumed, 'Hosted analytics.')

    def test_completed_prior_step_is_available_from_step_navigation(self):
        ids = self._field_ids()
        self.client_.post(reverse('contracts:dpa_workflow_builder'), {
            'action': 'continue', 'step': '1',
            f'field_{ids["counterparty"]}': 'Return Co.',
            f'field_{ids["contract_owner"]}': 'Avery Brooks',
            f'field_{ids["start_date"]}': '2026-09-01',
        })
        response = self.client_.get(f"{reverse('contracts:dpa_workflow_builder')}?step=2")
        self.assertContains(response, f'href="{reverse("contracts:dpa_workflow_builder")}?step=1"')

    def test_review_shows_only_answer_derived_scc_governance(self):
        ids = self._field_ids()
        session = self.client_.session
        session['dpa_intake_v1'] = {
            'organization_id': self.org.pk,
            'step': 4,
            'values': {
                'counterparty': 'Review Co.', 'contract_owner': 'Avery Brooks', 'start_date': '2026-09-01',
                'processing_purpose': 'Hosted analytics.', 'personal_data_categories': 'Contact data',
                'data_subjects': 'Administrators', 'personal_data_involved': True,
                'cross_border_transfer': True, 'subprocessors_used': False, 'transfer_mechanism': 'SCC',
                'breach_notification_hours': 48, 'governing_law': 'Delaware',
            },
        }
        session.save()
        response = self.client_.get(reverse('contracts:dpa_workflow_review'))
        self.assertContains(response, 'DPA summary')
        self.assertContains(response, 'SCC review required')
        self.assertContains(response, 'DPO approval before signature')
        self.assertNotContains(response, 'Live contract preview')

    def _step3_payload(self, **overrides):
        payload = {
            'action': 'continue', 'step': '3',
            'step3_data_categories': ['Identity and contact details'],
            'step3_data_subjects': ['Employees'],
            'step3_sensitive_data': 'no',
            'step3_subprocessors': 'no',
            'step3_processing_countries': ['Netherlands'],
        }
        payload.update(overrides)
        return payload

    def test_step3_eea_only_processing_derives_no_transfer_review(self):
        response = self.client_.post(reverse('contracts:dpa_workflow_builder'), self._step3_payload())
        self.assertRedirects(response, f'{reverse("contracts:dpa_workflow_builder")}?step=4')
        values = self.client_.session['dpa_intake_v1']['values']
        self.assertFalse(values['cross_border_transfer'])
        self.assertEqual(values['transfer_mechanism'], 'None')
        self.assertFalse(values['include_scc_fallback'])

    def test_step3_non_eea_scc_derives_scc_and_dpo_review(self):
        response = self.client_.post(reverse('contracts:dpa_workflow_builder'), self._step3_payload(
            step3_processing_countries=['Netherlands', 'United States'],
            step3_transfer_safeguard='Standard Contractual Clauses',
        ))
        self.assertRedirects(response, f'{reverse("contracts:dpa_workflow_builder")}?step=4')
        values = self.client_.session['dpa_intake_v1']['values']
        self.assertTrue(values['cross_border_transfer'])
        self.assertEqual(values['transfer_mechanism'], 'SCC')
        self.assertTrue(values['include_scc_fallback'])
        self.assertIn('SCC review required', [item['title'] for item in _dpa_governance_results(values)])

    def test_step3_unconfirmed_safeguard_blocks_progression(self):
        response = self.client_.post(reverse('contracts:dpa_workflow_builder'), self._step3_payload(
            step3_processing_countries=['United States'], step3_transfer_safeguard='Not confirmed',
        ))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'A confirmed safeguard is required before this DPA can progress.')

    def test_step3_requires_complete_subprocessor_details(self):
        response = self.client_.post(reverse('contracts:dpa_workflow_builder'), self._step3_payload(
            step3_subprocessors='yes', step3_subprocessor_name=['Analytics provider'],
        ))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Complete the name, service, processing location, and data involved for every subprocessor.')

    def test_step3_special_category_and_uncertain_answers_require_privacy_review(self):
        response = self.client_.post(reverse('contracts:dpa_workflow_builder'), self._step3_payload(
            step3_sensitive_data='yes', step3_subprocessors='not_sure',
        ))
        self.assertRedirects(response, f'{reverse("contracts:dpa_workflow_builder")}?step=4')
        values = self.client_.session['dpa_intake_v1']['values']
        outcome_titles = [item['title'] for item in _dpa_governance_results(values)]
        self.assertIn('Elevated privacy review required', outcome_titles)
        self.assertIn('Privacy review required', outcome_titles)
        privacy_review = next(item for item in _dpa_governance_results(values) if item['title'] == 'Privacy review required')
        self.assertEqual(privacy_review['status'], 'Blocked')

    def test_post_valid_redirects_to_workflow_detail_and_creates_rows(self):
        before = Workflow.objects.count()
        response = self.client_.post(reverse('contracts:dpa_workflow_builder'), self._valid_payload())
        self.assertEqual(Workflow.objects.count(), before + 1)
        workflow = Workflow.objects.latest('id')
        self.assertRedirects(response, reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))

    def test_post_missing_required_field_creates_nothing(self):
        payload = self._valid_payload()
        ids = self._field_ids()
        del payload[f'field_{ids["counterparty"]}']
        before_contracts = Contract.objects.count()
        before_workflows = Workflow.objects.count()
        response = self.client_.post(reverse('contracts:dpa_workflow_builder'), payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'is required')
        self.assertEqual(Contract.objects.count(), before_contracts)
        self.assertEqual(Workflow.objects.count(), before_workflows)

    def test_generated_workflow_routes_to_contract_workspace(self):
        response = self.client_.post(reverse('contracts:dpa_workflow_builder'), self._valid_payload())
        workflow = Workflow.objects.latest('id')
        self.assertRedirects(response, reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))

        workspace = self.client_.get(reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))
        self.assertEqual(workspace.status_code, 200)
        self.assertContains(workspace, 'Guided drafting')
        self.assertContains(workspace, 'Lifecycle')
        self.assertContains(workspace, 'Document overview')
        self.assertContains(workspace, 'DPA ·')
        self.assertContains(workspace, 'Resolve ')
        self.assertContains(workspace, 'Send to Legal Review · blocked')
        dpa = workspace.context['dpa_workspace']
        self.assertTrue(dpa['open_exceptions'] >= 1)
        self.assertTrue(dpa['primary_cta'].startswith('Resolve '))

    def test_contract_workspace_displays_risk_signal_details(self):
        payload = self._valid_payload()
        ids = self._field_ids()
        payload[f'field_{ids["subprocessors_used"]}'] = 'on'
        payload[f'field_{ids["transfer_mechanism"]}'] = 'SCC'
        self.client_.post(reverse('contracts:dpa_workflow_builder'), payload)
        workflow = Workflow.objects.latest('id')

        response = self.client_.get(reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))
        self.assertContains(response, 'Personal data processing review')
        self.assertContains(response, 'EEA/SCC risk')
        self.assertContains(response, 'Subprocessor review')
        self.assertContains(response, 'Recommended action')
        self.assertContains(response, 'Approval impact')
        self.assertContains(response, 'Open')

    def test_contract_workspace_displays_special_categories_risk_and_dpo_trigger(self):
        """special_categories_data alone (no personal_data_involved or
        cross_border_transfer) must still trigger DPO — the elevated-risk
        routing rule added alongside the AI Smart Questions expansion."""
        payload = self._valid_payload()
        ids = self._field_ids()
        del payload[f'field_{ids["personal_data_involved"]}']
        del payload[f'field_{ids["cross_border_transfer"]}']
        payload[f'field_{ids["special_categories_data"]}'] = 'on'
        self.client_.post(reverse('contracts:dpa_workflow_builder'), payload)
        workflow = Workflow.objects.latest('id')

        response = self.client_.get(reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))
        self.assertContains(response, 'Special categories risk')
        self.assertContains(response, 'DPO')

    def test_contract_workspace_displays_approval_route_reasons(self):
        self.client_.post(reverse('contracts:dpa_workflow_builder'), self._valid_payload())
        workflow = Workflow.objects.latest('id')

        response = self.client_.get(reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))
        self.assertContains(response, 'Approval route')
        self.assertContains(response, 'Contract owner')
        self.assertContains(response, 'Legal')
        self.assertContains(response, 'DPO')
        self.assertContains(response, 'Why triggered')
        self.assertContains(response, 'Privacy and transfer risk rules')

    def test_contract_workspace_displays_persisted_audit_history(self):
        self.client_.post(reverse('contracts:dpa_workflow_builder'), self._valid_payload())
        workflow = Workflow.objects.latest('id')
        AuditLog.objects.create(
            organization=self.org,
            user=self.user,
            action=AuditLog.Action.CREATE,
            model_name='Workflow',
            object_id=workflow.pk,
            object_repr=str(workflow)[:300],
            event_type='workflow.created',
            changes={'event': 'workflow.created'},
        )

        response = self.client_.get(reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))
        self.assertContains(response, 'Audit details')
        self.assertContains(response, 'Workflow Created')
        self.assertNotContains(response, 'Approved template applied')

    def test_contract_workspace_renders_actions_and_risk_clause_links(self):
        payload = self._valid_payload()
        ids = self._field_ids()
        payload[f'field_{ids["subprocessors_used"]}'] = 'on'
        self.client_.post(reverse('contracts:dpa_workflow_builder'), payload)
        workflow = Workflow.objects.latest('id')

        response = self.client_.get(reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))
        self.assertContains(response, 'View contract record')
        self.assertContains(response, 'Open clause')
        self.assertContains(response, 'id="processing-details"', html=False)
        self.assertContains(response, 'id="international-transfers"', html=False)
        self.assertContains(response, 'id="subprocessors"', html=False)
        self.assertContains(response, 'Send to Legal Review · blocked')
        self.assertContains(response, 'Send to Privacy / DPO · blocked')
        for hidden in (
            'Generate DPA review memo',
            'Export Word',
        ):
            self.assertNotContains(response, f'>{hidden}<')

    def test_dpa_workspace_highlights_contracts_nav(self):
        self.client_.post(reverse('contracts:dpa_workflow_builder'), self._valid_payload())
        workflow = Workflow.objects.latest('id')
        response = self.client_.get(reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))
        nav = response.context['SIDEBAR_NAV']
        contracts = next(item for item in nav if item.get('label') == 'Contracts')
        designer = next(item for item in nav if item.get('label') == 'Workflow Designer')
        self.assertTrue(contracts['is_active'])
        self.assertFalse(designer['is_active'])
        self.assertContains(response, 'Back to contract')

    def test_dpa_submit_for_review_blocked_while_exceptions_open(self):
        self.client_.post(reverse('contracts:dpa_workflow_builder'), self._valid_payload())
        workflow = Workflow.objects.latest('id')
        self.assertTrue(RiskSignal.objects.filter(workflow=workflow, is_resolved=False).exists())
        response = self.client_.post(
            reverse('contracts:dpa_submit_for_review', kwargs={'pk': workflow.pk, 'approval_step': 'legal'}),
        )
        self.assertRedirects(
            response,
            reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}),
            fetch_redirect_response=False,
        )
        follow = self.client_.get(reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))
        self.assertContains(follow, 'before submitting this DPA for review')
        self.assertFalse(ApprovalRequest.objects.filter(contract=workflow.contract).exists())


class StageOneRoutingTests(TestCase):
    def setUp(self):
        self.org, self.user, self.client_ = _make_org_with_user('Routing Org', 'routing_user')

    def test_dpa_card_points_at_workflow_builder(self):
        response = self.client_.get(reverse('contracts:contract_template_picker'))
        content = response.content.decode()
        self.assertIn(reverse('contracts:dpa_workflow_builder'), content)

    def test_other_cards_still_point_at_contract_create(self):
        response = self.client_.get(reverse('contracts:contract_template_picker'))
        content = response.content.decode()
        self.assertIn(reverse('contracts:msa_workflow_builder'), content)
        self.assertIn(reverse('contracts:nda_workflow_builder'), content)
        self.assertIn(f"{reverse('contracts:contract_create')}?type=SOW", content)


class CommandCenterKanbanProjectionTests(TestCase):
    def setUp(self):
        self.org, self.user, self.client_ = _make_org_with_user('Kanban Org', 'kanban_user', workspace_mode=Organization.WorkspaceMode.IN_HOUSE_CLM)

    def test_new_dpa_workflow_appears_in_dashboard_kanban_draft_column(self):
        workflow = create_dpa_workflow_instance(organization=self.org, user=self.user, cleaned_values={
            'counterparty': 'Kanban Test Co.', 'start_date': '2026-09-01', 'governing_law': 'Delaware',
            'contract_owner': 'Avery Brooks', 'processing_purpose': 'Support services',
            'personal_data_categories': 'Business contact details', 'data_subjects': 'Customer users',
            'transfer_mechanism': 'SCC', 'breach_notification_hours': 24,
            'personal_data_involved': True, 'cross_border_transfer': True,
        })
        response = self.client_.get(reverse('dashboard'))
        self.assertContains(response, workflow.title)

    def test_generated_dpa_workflow_row_renders_workspace_operational_fields(self):
        workflow = create_dpa_workflow_instance(organization=self.org, user=self.user, cleaned_values={
            'counterparty': 'Queue Test Co.', 'start_date': '2026-09-01', 'governing_law': 'Delaware',
            'contract_owner': 'Avery Brooks', 'processing_purpose': 'Support services',
            'personal_data_categories': 'Business contact details', 'data_subjects': 'Customer users',
            'transfer_mechanism': 'None', 'breach_notification_hours': 24,
            'personal_data_involved': True, 'cross_border_transfer': True, 'subprocessors_used': True,
        })

        response = self.client_.get(reverse('dashboard'))

        self.assertContains(response, workflow.title)
        self.assertContains(response, 'DPA')
        self.assertContains(response, 'Draft')
        self.assertContains(response, self.user.username)
        self.assertContains(response, 'Cross-border transfer flagged but no transfer mechanism selected.')
        self.assertContains(response, 'Review SCC position and DPO route')
        self.assertContains(response, reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))
