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
from contracts.services.msa_workflow import (
    FINANCE_APPROVAL_THRESHOLD,
    create_msa_workflow_instance,
    detect_msa_risk_signals,
    get_field_definitions_by_section,
    get_msa_workflow_template,
    render_msa_live_preview,
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


class MSASeedAndPreviewTests(TestCase):
    def test_workflow_template_seeded(self):
        wt = get_msa_workflow_template()
        self.assertIsNotNone(wt)
        self.assertEqual(wt.name, 'MSA Commercial Review Workflow')
        self.assertEqual(wt.contract_type.code, 'MSA')

    def test_field_definitions_grouped_for_all_sections(self):
        grouped = get_field_definitions_by_section(get_msa_workflow_template())
        self.assertTrue(grouped[FieldDefinition.Section.BASIC_DETAILS])
        self.assertTrue(grouped[FieldDefinition.Section.COMMERCIAL_TERMS])
        self.assertTrue(grouped[FieldDefinition.Section.SERVICES_SCOPE])
        self.assertTrue(grouped[FieldDefinition.Section.LEGAL_POSITION])
        self.assertTrue(grouped[FieldDefinition.Section.SMART_QUESTIONS])

    def test_live_preview_substitutes_template_fields(self):
        result = render_msa_live_preview(
            'Value {{value}} {{currency}} for {{services_description}}',
            {'value': 125000, 'currency': 'EUR', 'services_description': 'Managed support services'},
        )
        self.assertIn('125000', result)
        self.assertIn('EUR', result)
        self.assertIn('Managed support services', result)

    def test_live_preview_includes_data_protection_clause_when_personal_data_involved(self):
        result = render_msa_live_preview('{{data_protection_clause}}', {'personal_data_involved': True})
        self.assertIn('Data Protection Addendum review is required', result)


class DetectMSARiskSignalsTests(TestCase):
    def setUp(self):
        self.org, self.user, _ = _make_org_with_user('MSA Risk Org', 'msa_risk_user')
        contract = Contract.objects.create(organization=self.org, title='MSA test', contract_type=Contract.ContractType.MSA)
        self.workflow = Workflow.objects.create(title='msa', organization=self.org, template=get_msa_workflow_template(), contract=contract)

    def test_contract_value_threshold_triggers_finance_signal(self):
        detect_msa_risk_signals(self.workflow, {'value': FINANCE_APPROVAL_THRESHOLD + 1})
        signal = RiskSignal.objects.get(workflow=self.workflow, code='finance_approval_required')
        self.assertEqual(signal.severity, RiskSignal.Severity.HIGH)

    def test_liability_cap_deviation_triggers_legal_risk(self):
        detect_msa_risk_signals(self.workflow, {'liability_cap_nonstandard': True})
        self.assertTrue(RiskSignal.objects.filter(workflow=self.workflow, code='liability_cap_nonstandard').exists())

    def test_personal_data_involved_triggers_dpa_privacy_review(self):
        detect_msa_risk_signals(self.workflow, {'personal_data_involved': True})
        self.assertTrue(RiskSignal.objects.filter(workflow=self.workflow, code='msa_dpa_review_required').exists())

    def test_auto_renewal_triggers_notice_signal(self):
        detect_msa_risk_signals(self.workflow, {'auto_renewal_included': True})
        self.assertTrue(RiskSignal.objects.filter(workflow=self.workflow, code='renewal_notice_review').exists())


class CreateMSAWorkflowInstanceTests(TestCase):
    def setUp(self):
        self.org, self.user, _ = _make_org_with_user('MSA Create Org', 'msa_create_user')

    def _cleaned_values(self, **overrides):
        values = {
            'counterparty': 'Northwind Services B.V.',
            'start_date': '2026-09-01',
            'contract_owner': 'Avery Brooks',
            'business_unit': 'Revenue Operations',
            'internal_reference': 'MSA-2026-001',
            'value': 350000,
            'currency': 'EUR',
            'payment_terms': 'Net 30',
            'initial_term': '24 months',
            'renewal_type': 'Auto-renew',
            'termination_notice_period': 60,
            'services_description': 'Managed logistics platform and support services.',
            'sow_required': True,
            'deliverables_defined': True,
            'acceptance_criteria_required': True,
            'governing_law': 'Delaware',
            'jurisdiction': 'Amsterdam',
            'liability_cap': '2x annual fees',
            'confidentiality_period': '5 years',
            'ip_ownership': 'Customer',
            'personal_data_involved': True,
            'value_above_threshold_confirmed': True,
            'liability_cap_nonstandard': True,
            'services_involve_personal_data': True,
            'auto_renewal_included': True,
            'ip_ownership_nonstandard': True,
            'governing_law_nonpreferred': True,
        }
        values.update(overrides)
        return values

    def test_generate_governed_draft_creates_persisted_rows(self):
        workflow = create_msa_workflow_instance(organization=self.org, user=self.user, cleaned_values=self._cleaned_values())
        self.assertEqual(workflow.contract.contract_type, Contract.ContractType.MSA)
        self.assertEqual(workflow.template.name, 'MSA Commercial Review Workflow')
        self.assertEqual(FieldValue.objects.filter(workflow=workflow).count(), FieldDefinition.objects.filter(workflow_template=workflow.template).count())
        self.assertTrue(workflow.draft_documents.filter(is_current=True).exists())
        self.assertTrue(workflow.risk_signals.exists())
        self.assertTrue(CommandCenterWorkItem.objects.filter(workflow=workflow).exists())


class MSAWorkflowBuilderIntegrationTests(TestCase):
    def setUp(self):
        self.org, self.user, self.client_ = _make_org_with_user('MSA Builder Org', 'msa_builder_user', workspace_mode=Organization.WorkspaceMode.IN_HOUSE_CLM)

    def _field_ids(self):
        wt = get_msa_workflow_template()
        return {f.key: f.id for f in FieldDefinition.objects.filter(workflow_template=wt)}

    def _valid_payload(self):
        ids = self._field_ids()
        return {
            f'field_{ids["counterparty"]}': 'Northwind Services B.V.',
            f'field_{ids["start_date"]}': '2026-09-01',
            f'field_{ids["contract_owner"]}': 'Avery Brooks',
            f'field_{ids["business_unit"]}': 'Revenue Operations',
            f'field_{ids["internal_reference"]}': 'MSA-2026-001',
            f'field_{ids["value"]}': '350000',
            f'field_{ids["currency"]}': 'EUR',
            f'field_{ids["payment_terms"]}': 'Net 30',
            f'field_{ids["initial_term"]}': '24 months',
            f'field_{ids["renewal_type"]}': 'Auto-renew',
            f'field_{ids["termination_notice_period"]}': '60',
            f'field_{ids["services_description"]}': 'Managed logistics platform and support services.',
            f'field_{ids["sow_required"]}': 'on',
            f'field_{ids["deliverables_defined"]}': 'on',
            f'field_{ids["acceptance_criteria_required"]}': 'on',
            f'field_{ids["governing_law"]}': 'Delaware',
            f'field_{ids["jurisdiction"]}': 'Amsterdam',
            f'field_{ids["liability_cap"]}': '2x annual fees',
            f'field_{ids["confidentiality_period"]}': '5 years',
            f'field_{ids["ip_ownership"]}': 'Customer',
            f'field_{ids["personal_data_involved"]}': 'on',
            f'field_{ids["value_above_threshold_confirmed"]}': 'on',
            f'field_{ids["liability_cap_nonstandard"]}': 'on',
            f'field_{ids["services_involve_personal_data"]}': 'on',
            f'field_{ids["auto_renewal_included"]}': 'on',
            f'field_{ids["ip_ownership_nonstandard"]}': 'on',
            f'field_{ids["governing_law_nonpreferred"]}': 'on',
        }

    def test_contract_type_selection_routes_msa_to_builder(self):
        response = self.client_.get(reverse('contracts:contract_template_picker'))
        self.assertContains(response, reverse('contracts:msa_workflow_builder'))

    def test_msa_builder_renders_cockpit(self):
        response = self.client_.get(reverse('contracts:msa_workflow_builder'))
        self.assertEqual(response.status_code, 200)
        for text in (
            'New MSA Draft',
            'AI-assisted drafting from approved templates and playbooks.',
            'MSA Commercial Review Workflow',
            'Drafting inputs',
            'Draft workspace',
            'Workflow controls',
            'Value, term, and notice',
            'Review triggers',
            'Generate governed draft',
        ):
            self.assertContains(response, text)
        self.assertContains(response, 'Service definition controls')

    def test_post_valid_redirects_to_msa_workspace(self):
        response = self.client_.post(reverse('contracts:msa_workflow_builder'), self._valid_payload())
        workflow = Workflow.objects.latest('id')
        self.assertRedirects(response, reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))

        workspace = self.client_.get(reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))
        for text in (
            'Generated MSA Draft',
            'Risk Signals',
            'Approval Route',
            'Audit Trail Preview',
            'Send to Legal Review',
            'Send to Finance',
            'Generate MSA summary',
            'Export Word',
            'Finance approval signal',
            'Liability cap deviation',
            'DPA / privacy review signal',
            'Workflow created',
        ):
            self.assertContains(workspace, text)

    def test_command_center_row_links_back_to_generated_workspace(self):
        self.client_.post(reverse('contracts:msa_workflow_builder'), self._valid_payload())
        workflow = Workflow.objects.latest('id')
        response = self.client_.get(reverse('dashboard'))
        self.assertContains(response, workflow.title)
        self.assertContains(response, 'MSA')
        self.assertContains(response, reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))
        self.assertContains(response, 'Review Finance approval route')
