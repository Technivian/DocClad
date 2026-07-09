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
    ApprovalRoute,
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

    def test_scc_fallback_toggle_changes_transfer_position_copy(self):
        with_fallback = render_dpa_live_preview('{{data_transfer_position}}', {'cross_border_transfer': True, 'include_scc_fallback': True})
        without_fallback = render_dpa_live_preview('{{data_transfer_position}}', {'cross_border_transfer': True, 'include_scc_fallback': False})
        self.assertIn('SCC', with_fallback)
        self.assertIn('fallback language', with_fallback)
        self.assertNotIn('fallback language', without_fallback)


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

    def test_clean_submission_creates_no_signals(self):
        detect_dpa_risk_signals(self.workflow, {
            'personal_data_involved': False, 'cross_border_transfer': False, 'subprocessors_used': False, 'transfer_mechanism': 'None',
            'dpo_contact': 'privacy@acme.com', 'breach_notification_hours': 24, 'liability_position': '',
        })
        self.assertEqual(RiskSignal.objects.filter(workflow=self.workflow).count(), 0)

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
        self.assertEqual(contract.status, Contract.Status.DRAFT)
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

    def test_get_renders_smart_questions_and_template_body(self):
        response = self.client_.get(reverse('contracts:dpa_workflow_builder'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        for label in ('Processing purpose', 'Personal data categories', 'Data subjects',
                      'Data Protection Officer contact', 'Cross-border transfer mechanism', 'Breach notification window'):
            self.assertIn(label, content)
        self.assertIn('AI-assisted drafting from approved templates and playbooks.', content)

    def test_get_renders_ai_smart_questions_with_why_it_matters_copy(self):
        response = self.client_.get(reverse('contracts:dpa_workflow_builder'))
        content = response.content.decode()
        self.assertContains(response, 'AI Smart Questions')
        self.assertContains(response, 'DocClad is checking whether this DPA requires SCC language, subprocessor review, Legal approval, or DPO approval.')
        for question in (
            'Will the counterparty process personal data?',
            'Will data leave the EEA?',
            'Are subprocessors involved?',
            'Are special categories of personal data processed?',
            'Should SCC fallback language be included?',
        ):
            self.assertIn(question, content)
        for why in (
            'Required for GDPR routing and DPO approval.',
            'Triggers SCC review and international transfer language.',
            'Adds subprocessor review and approval checks.',
            'Elevates privacy risk',
            'Adds the approved SCC fallback clause',
        ):
            self.assertIn(why, content)

    def test_get_renders_header_progress_and_readiness_markup(self):
        response = self.client_.get(reverse('contracts:dpa_workflow_builder'))
        self.assertContains(response, 'id="dpa-progress-pct"')
        self.assertContains(response, 'id="dpa-progress-copy"')
        self.assertContains(response, 'id="dpa-header-progress-fill"')
        self.assertContains(response, 'Draft Readiness')
        self.assertContains(response, 'Required fields completed')
        self.assertContains(response, 'Missing required fields')
        self.assertContains(response, 'Active risk signals')
        self.assertContains(response, 'Required approvals')
        self.assertContains(response, 'Blocking errors')
        self.assertContains(response, 'Audit trail')
        self.assertContains(response, 'Activates on generate')
        self.assertContains(response, 'id="dpa-gov-approval-reasons"')

    def test_get_renders_governed_ai_action_bar_copy(self):
        response = self.client_.get(reverse('contracts:dpa_workflow_builder'))
        for label in ('Suggest missing values', 'Suggest fallback clause', 'Explain clause',
                      'Generate DPA summary', 'Compare to playbook'):
            self.assertContains(response, label)
        # Guards against AI-decides framing that oversells drafting autonomy.
        self.assertNotContains(response, 'AI wrote this')
        self.assertNotContains(response, 'Let AI decide')

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
        self.assertContains(workspace, 'Generated DPA Draft')
        self.assertContains(workspace, 'Workflow Timeline')
        self.assertContains(workspace, 'AI-assisted drafting from approved templates and playbooks.')
        self.assertContains(workspace, 'GDPR Processor DPA · Netherlands · B2B')
        self.assertContains(workspace, 'Review DPA risk signals')

    def test_contract_workspace_displays_risk_signal_details(self):
        payload = self._valid_payload()
        ids = self._field_ids()
        payload[f'field_{ids["subprocessors_used"]}'] = 'on'
        payload[f'field_{ids["transfer_mechanism"]}'] = 'None'
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
        self.assertContains(response, 'Approval Route')
        self.assertContains(response, 'Contract owner')
        self.assertContains(response, 'Legal')
        self.assertContains(response, 'DPO')
        self.assertContains(response, 'Why triggered')
        self.assertContains(response, 'Privacy and transfer risk rules')

    def test_contract_workspace_displays_audit_trail_preview(self):
        self.client_.post(reverse('contracts:dpa_workflow_builder'), self._valid_payload())
        workflow = Workflow.objects.latest('id')

        response = self.client_.get(reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))
        for event in (
            'Workflow created',
            'Approved template applied',
            'Field values captured',
            'Risk checks run',
            'Approval route generated',
        ):
            self.assertContains(response, event)

    def test_contract_workspace_renders_actions_and_risk_clause_links(self):
        payload = self._valid_payload()
        ids = self._field_ids()
        payload[f'field_{ids["subprocessors_used"]}'] = 'on'
        self.client_.post(reverse('contracts:dpa_workflow_builder'), payload)
        workflow = Workflow.objects.latest('id')

        response = self.client_.get(reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))
        self.assertContains(response, 'Send to Legal Review')
        self.assertContains(response, 'Send to DPO')
        self.assertContains(response, 'Generate DPA review memo')
        self.assertContains(response, 'Export Word')
        self.assertContains(response, 'Open related draft section')
        self.assertContains(response, 'id="processing-details"', html=False)
        self.assertContains(response, 'id="international-transfers"', html=False)
        self.assertContains(response, 'id="subprocessors"', html=False)


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
        self.assertContains(response, 'Data may leave the EEA; SCC transfer position and DPO approval are required.')
        self.assertContains(response, 'Review SCC position and DPO route')
        self.assertContains(response, reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))
