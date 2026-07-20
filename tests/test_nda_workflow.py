from django.contrib.auth import get_user_model
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from contracts.models import (
    CommandCenterWorkItem,
    Contract,
    FieldDefinition,
    FieldValue,
    Organization,
    OrganizationMembership,
    RiskSignal,
    Workflow,
)
from contracts.services.nda_workflow import (
    STANDARD_CONFIDENTIALITY_YEARS,
    create_nda_workflow_instance,
    detect_nda_risk_signals,
    get_field_definitions_by_section,
    get_nda_workflow_template,
    render_nda_live_preview,
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


class NDASeedAndPreviewTests(TestCase):
    def test_workflow_template_seeded(self):
        wt = get_nda_workflow_template()
        self.assertIsNotNone(wt)
        self.assertEqual(wt.name, 'NDA Self-Serve Workflow')
        self.assertEqual(wt.contract_type.code, 'NDA')

    def test_field_definitions_grouped_for_all_sections(self):
        grouped = get_field_definitions_by_section(get_nda_workflow_template())
        self.assertTrue(grouped[FieldDefinition.Section.BASIC_DETAILS])
        self.assertTrue(grouped[FieldDefinition.Section.NDA_TERMS])
        self.assertTrue(grouped[FieldDefinition.Section.LEGAL_POSITION])
        self.assertTrue(grouped[FieldDefinition.Section.SMART_QUESTIONS])

    def test_live_preview_substitutes_template_fields(self):
        result = render_nda_live_preview(
            'Purpose {{confidentiality_purpose}} for {{counterparty}}',
            {'confidentiality_purpose': 'product diligence', 'counterparty': 'Northwind B.V.'},
        )
        self.assertIn('product diligence', result)
        self.assertIn('Northwind B.V.', result)

    def test_live_preview_includes_personal_data_language_when_flagged(self):
        result = render_nda_live_preview('{{personal_data_clause}}', {'personal_data_involved': True})
        self.assertIn('linked DPA', result)


class DetectNDARiskSignalsTests(TestCase):
    def setUp(self):
        self.org, self.user, _ = _make_org_with_user('NDA Risk Org', 'nda_risk_user')
        contract = Contract.objects.create(organization=self.org, title='NDA test', contract_type=Contract.ContractType.NDA)
        self.workflow = Workflow.objects.create(title='nda', organization=self.org, template=get_nda_workflow_template(), contract=contract)

    def test_long_confidentiality_period_triggers_legal_signal(self):
        detect_nda_risk_signals(self.workflow, {'confidentiality_period': STANDARD_CONFIDENTIALITY_YEARS + 2})
        self.assertTrue(RiskSignal.objects.filter(workflow=self.workflow, code='confidentiality_period_nonstandard').exists())

    def test_personal_data_triggers_privacy_review(self):
        detect_nda_risk_signals(self.workflow, {'personal_data_involved': True})
        self.assertTrue(RiskSignal.objects.filter(workflow=self.workflow, code='nda_privacy_review_required').exists())

    def test_residual_knowledge_triggers_legal_risk(self):
        detect_nda_risk_signals(self.workflow, {'residual_knowledge_included': True})
        self.assertTrue(RiskSignal.objects.filter(workflow=self.workflow, code='residual_knowledge_risk').exists())

    def test_nonpreferred_governing_law_triggers_escalation(self):
        detect_nda_risk_signals(self.workflow, {'governing_law': 'Delaware'})
        self.assertTrue(RiskSignal.objects.filter(workflow=self.workflow, code='nonpreferred_governing_law').exists())


class CreateNDAWorkflowInstanceTests(TestCase):
    def setUp(self):
        self.org, self.user, _ = _make_org_with_user('NDA Create Org', 'nda_create_user')

    def _cleaned_values(self, **overrides):
        values = {
            'counterparty': 'Northwind B.V.',
            'start_date': '2026-09-01',
            'contract_owner': 'Avery Brooks',
            'business_unit': 'Revenue Operations',
            'internal_reference': 'NDA-2026-001',
            'nda_type': 'Mutual',
            'confidentiality_purpose': 'product diligence and commercial evaluation',
            'confidentiality_period': 2,
            'disclosure_scope': 'technical architecture, pricing, and roadmap information',
            'permitted_recipients': 'employees and external counsel with a need to know',
            'governing_law': 'Netherlands',
            'jurisdiction': 'Amsterdam',
            'residual_knowledge_included': False,
            'injunctive_relief_included': True,
            'personal_data_involved': False,
            'confidentiality_period_nonstandard': False,
            'personal_data_confirmed': False,
            'residual_knowledge_nonstandard': False,
            'governing_law_nonpreferred': False,
        }
        values.update(overrides)
        return values

    def test_generate_governed_draft_creates_persisted_rows(self):
        workflow = create_nda_workflow_instance(organization=self.org, user=self.user, cleaned_values=self._cleaned_values())
        self.assertEqual(workflow.contract.contract_type, Contract.ContractType.NDA)
        self.assertEqual(workflow.template.name, 'NDA Self-Serve Workflow')
        self.assertEqual(FieldValue.objects.filter(workflow=workflow).count(), FieldDefinition.objects.filter(workflow_template=workflow.template).count())
        self.assertTrue(workflow.draft_documents.filter(is_current=True).exists())
        self.assertTrue(CommandCenterWorkItem.objects.filter(workflow=workflow).exists())

    def test_low_risk_workflow_remains_self_serve(self):
        workflow = create_nda_workflow_instance(organization=self.org, user=self.user, cleaned_values=self._cleaned_values())
        self.assertEqual(workflow.contract.risk_level, Contract.RiskLevel.LOW)
        self.assertFalse(workflow.risk_signals.exists())
        legal_step = workflow.steps.get(name='Legal Review')
        self.assertEqual(legal_step.status, legal_step.Status.SKIPPED)


class NDAWorkflowBuilderIntegrationTests(TestCase):
    def setUp(self):
        self.org, self.user, self.client_ = _make_org_with_user('NDA Builder Org', 'nda_builder_user', workspace_mode=Organization.WorkspaceMode.IN_HOUSE_CLM)

    def _field_ids(self):
        wt = get_nda_workflow_template()
        return {f.key: f.id for f in FieldDefinition.objects.filter(workflow_template=wt)}

    def _low_risk_payload(self):
        ids = self._field_ids()
        return {
            f'field_{ids["counterparty"]}': 'Northwind B.V.',
            f'field_{ids["start_date"]}': '2026-09-01',
            f'field_{ids["contract_owner"]}': 'Avery Brooks',
            f'field_{ids["business_unit"]}': 'Revenue Operations',
            f'field_{ids["internal_reference"]}': 'NDA-2026-001',
            f'field_{ids["nda_type"]}': 'Mutual',
            f'field_{ids["confidentiality_purpose"]}': 'product diligence and commercial evaluation',
            f'field_{ids["confidentiality_period"]}': '2',
            f'field_{ids["disclosure_scope"]}': 'technical architecture and pricing details',
            f'field_{ids["permitted_recipients"]}': 'employees and external counsel with a need to know',
            f'field_{ids["governing_law"]}': 'Netherlands',
            f'field_{ids["jurisdiction"]}': 'Amsterdam',
            f'field_{ids["injunctive_relief_included"]}': 'on',
        }

    def _high_risk_payload(self):
        payload = self._low_risk_payload()
        ids = self._field_ids()
        payload.update({
            f'field_{ids["confidentiality_period"]}': '5',
            f'field_{ids["personal_data_involved"]}': 'on',
            f'field_{ids["residual_knowledge_included"]}': 'on',
            f'field_{ids["confidentiality_period_nonstandard"]}': 'on',
            f'field_{ids["residual_knowledge_nonstandard"]}': 'on',
            f'field_{ids["governing_law"]}': 'Delaware',
            f'field_{ids["governing_law_nonpreferred"]}': 'on',
        })
        return payload

    def test_contract_type_selection_routes_nda_to_builder(self):
        response = self.client_.get(reverse('contracts:contract_template_picker'))
        self.assertContains(response, reverse('contracts:nda_workflow_builder'))

    def test_nda_builder_renders_cockpit(self):
        response = self.client_.get(reverse('contracts:nda_workflow_builder'))
        self.assertEqual(response.status_code, 200)
        for text in (
            'New NDA Draft',
            'AI-assisted drafting from approved templates and playbooks.',
            'Purpose and confidentiality scope',
            'Review triggers',
            'Generate governed draft',
        ):
            self.assertContains(response, text)

    def test_low_risk_nda_workspace_shows_self_serve_eligibility(self):
        response = self.client_.post(reverse('contracts:nda_workflow_builder'), self._low_risk_payload())
        workflow = Workflow.objects.latest('id')
        self.assertRedirects(response, reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))

        workspace = self.client_.get(reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))
        for text in (
            'Guided drafting',
            'Document overview',
            'View contract record',
            'No NDA risk triggers were detected',
            'Audit details',
            'Send to Legal Review · not required',
        ):
            self.assertContains(workspace, text)
        for hidden in (
            'Generate NDA summary',
            'Export Word',
        ):
            self.assertNotContains(workspace, hidden)
        self.assertNotContains(workspace, 'type="button" class="dc-ds-button dc-ds-button--primary">Send for signature')
        nda = workspace.context['nda_workspace']
        self.assertTrue(nda['self_serve_eligible'])
        self.assertEqual(nda['open_exceptions'], 0)

    def test_high_risk_nda_workspace_renders_risks_and_legal_action(self):
        self.client_.post(reverse('contracts:nda_workflow_builder'), self._high_risk_payload())
        workflow = Workflow.objects.latest('id')
        workspace = self.client_.get(reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))
        for text in (
            'Long confidentiality period',
            'Privacy / DPA review signal',
            'Residual knowledge risk',
            'Governing law escalation',
            'Resolve ',
            'Send to Legal Review · blocked',
            'Audit details',
        ):
            self.assertContains(workspace, text)
        self.assertNotContains(workspace, '>Send to Legal Review</button>')
        nda = workspace.context['nda_workspace']
        self.assertTrue(nda['legal_review_triggered'])
        self.assertTrue(nda['open_exceptions'] >= 1)

    def test_nda_workspace_highlights_contracts_nav(self):
        self.client_.post(reverse('contracts:nda_workflow_builder'), self._low_risk_payload())
        workflow = Workflow.objects.latest('id')
        response = self.client_.get(reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))
        nav = response.context['SIDEBAR_NAV']
        contracts = next(item for item in nav if item.get('label') == 'Contracts')
        designer = next(item for item in nav if item.get('label') == 'Workflow Designer')
        self.assertTrue(contracts['is_active'])
        self.assertFalse(designer['is_active'])
        self.assertContains(response, 'Back to contract')

    def test_nda_submit_for_review_blocked_while_exceptions_open(self):
        self.client_.post(reverse('contracts:nda_workflow_builder'), self._high_risk_payload())
        workflow = Workflow.objects.latest('id')
        response = self.client_.post(
            reverse('contracts:nda_submit_for_review', kwargs={'pk': workflow.pk, 'approval_step': 'legal'}),
        )
        self.assertRedirects(
            response,
            reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}),
            fetch_redirect_response=False,
        )
        follow = self.client_.get(reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))
        self.assertContains(follow, 'before submitting this NDA for review')

    def test_command_center_row_links_back_to_generated_workspace(self):
        self.client_.post(reverse('contracts:nda_workflow_builder'), self._low_risk_payload())
        workflow = Workflow.objects.latest('id')
        response = self.client_.get(reverse('dashboard'))
        self.assertContains(response, workflow.title)
        self.assertContains(response, 'NDA')
        self.assertContains(response, 'Self-serve eligible')
        self.assertContains(response, reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))
