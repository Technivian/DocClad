from django.contrib.auth import get_user_model
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from contracts.models import (
    ApprovalRoute,
    CommandCenterWorkItem,
    FieldDefinition,
    FieldValue,
    Organization,
    OrganizationMembership,
    Workflow,
)
from contracts.services.dpa_workflow import create_dpa_workflow_instance, get_dpa_workflow_template
from contracts.services.msa_workflow import create_msa_workflow_instance, get_msa_workflow_template

User = get_user_model()


def _make_org_with_user(label, username, workspace_mode=None):
    kwargs = {}
    if workspace_mode:
        kwargs['workspace_mode'] = workspace_mode
    org = Organization.objects.create(
        name=f'{label} {username}',
        slug=f'{label.lower().replace(" ", "-")}-{username}',
        **kwargs,
    )
    user = User.objects.create_user(username=username, password='testpass123!')
    OrganizationMembership.objects.create(
        organization=org,
        user=user,
        role=OrganizationMembership.Role.OWNER,
        is_active=True,
    )
    client_ = TestClient()
    client_.login(username=username, password='testpass123!')
    return org, user, client_


class WorkflowCockpitRegressionTests(TestCase):
    def setUp(self):
        self.org, self.user, self.client_ = _make_org_with_user(
            'Reference Cockpit Org',
            'reference_cockpit_user',
            workspace_mode=Organization.WorkspaceMode.IN_HOUSE_CLM,
        )

    def _dpa_payload(self):
        wt = get_dpa_workflow_template()
        ids = {f.key: f.id for f in FieldDefinition.objects.filter(workflow_template=wt)}
        return {
            f'field_{ids["counterparty"]}': 'Reference DPA Counterparty',
            f'field_{ids["start_date"]}': '2026-09-01',
            f'field_{ids["contract_owner"]}': 'Avery Brooks',
            f'field_{ids["processing_purpose"]}': 'Hosted analytics and support services.',
            f'field_{ids["personal_data_categories"]}': 'Business contact details.',
            f'field_{ids["data_subjects"]}': 'Customer administrators.',
            f'field_{ids["governing_law"]}': 'State of Delaware',
            f'field_{ids["transfer_mechanism"]}': 'SCC',
            f'field_{ids["breach_notification_hours"]}': '48',
            f'field_{ids["dpo_contact"]}': 'privacy@example.com',
            f'field_{ids["personal_data_involved"]}': 'on',
            f'field_{ids["cross_border_transfer"]}': 'on',
            f'field_{ids["subprocessors_used"]}': 'on',
        }

    def _msa_payload(self):
        wt = get_msa_workflow_template()
        ids = {f.key: f.id for f in FieldDefinition.objects.filter(workflow_template=wt)}
        return {
            f'field_{ids["counterparty"]}': 'Reference MSA Counterparty',
            f'field_{ids["start_date"]}': '2026-09-01',
            f'field_{ids["contract_owner"]}': 'Avery Brooks',
            f'field_{ids["business_unit"]}': 'Revenue Operations',
            f'field_{ids["internal_reference"]}': 'MSA-REF-001',
            f'field_{ids["value"]}': '350000',
            f'field_{ids["currency"]}': 'EUR',
            f'field_{ids["payment_terms"]}': 'Net 30',
            f'field_{ids["initial_term"]}': '24 months',
            f'field_{ids["renewal_type"]}': 'Auto-renew',
            f'field_{ids["termination_notice_period"]}': '60',
            f'field_{ids["services_description"]}': 'Managed logistics platform and support services.',
            f'field_{ids["governing_law"]}': 'Delaware',
            f'field_{ids["jurisdiction"]}': 'Amsterdam',
            f'field_{ids["liability_cap"]}': '2x annual fees',
            f'field_{ids["confidentiality_period"]}': '5 years',
            f'field_{ids["ip_ownership"]}': 'Customer',
            f'field_{ids["personal_data_involved"]}': 'on',
            f'field_{ids["value_above_threshold_confirmed"]}': 'on',
            f'field_{ids["liability_cap_nonstandard"]}': 'on',
            f'field_{ids["services_involve_personal_data"]}': 'on',
        }

    def test_reference_cockpits_render(self):
        dpa = self.client_.get(reverse('contracts:dpa_workflow_builder'))
        msa = self.client_.get(reverse('contracts:msa_workflow_builder'))

        self.assertContains(dpa, 'New DPA Draft')
        self.assertContains(msa, 'New MSA Draft')

    def test_reference_workflows_generate_records_and_render_workspaces(self):
        cases = [
            (
                'dpa',
                reverse('contracts:dpa_workflow_builder'),
                self._dpa_payload(),
                'Generated DPA Draft',
                'DPA',
                get_dpa_workflow_template,
            ),
            (
                'msa',
                reverse('contracts:msa_workflow_builder'),
                self._msa_payload(),
                'Generated MSA Draft',
                'MSA',
                get_msa_workflow_template,
            ),
        ]

        for _name, url, payload, workspace_marker, contract_type, template_getter in cases:
            before_workflows = Workflow.objects.count()
            response = self.client_.post(url, payload)
            self.assertEqual(Workflow.objects.count(), before_workflows + 1)

            workflow = Workflow.objects.latest('id')
            self.assertRedirects(response, reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))
            self.assertEqual(workflow.contract.contract_type, contract_type)
            self.assertTrue(
                ApprovalRoute.objects.filter(workflow_template=template_getter()).exists()
            )
            self.assertEqual(
                FieldValue.objects.filter(workflow=workflow).count(),
                FieldDefinition.objects.filter(workflow_template=workflow.template).count(),
            )
            self.assertTrue(workflow.risk_signals.exists())
            self.assertTrue(workflow.draft_documents.filter(is_current=True).exists())
            self.assertTrue(CommandCenterWorkItem.objects.filter(workflow=workflow).exists())

            workspace = self.client_.get(reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))
            self.assertContains(workspace, workspace_marker)
            self.assertContains(workspace, 'Approval Route')
            self.assertContains(workspace, 'Audit Trail Preview')

    def test_dashboard_renders_mixed_workflow_rows_with_workspace_links(self):
        dpa_workflow = create_dpa_workflow_instance(
            organization=self.org,
            user=self.user,
            cleaned_values={
                'counterparty': 'Mixed DPA Counterparty',
                'start_date': '2026-09-01',
                'contract_owner': 'Avery Brooks',
                'processing_purpose': 'Support services',
                'personal_data_categories': 'Business contact details',
                'data_subjects': 'Customer users',
                'governing_law': 'State of Delaware',
                'transfer_mechanism': 'None',
                'breach_notification_hours': 24,
                'dpo_contact': 'privacy@example.com',
                'personal_data_involved': True,
                'cross_border_transfer': True,
                'subprocessors_used': True,
            },
        )
        msa_workflow = create_msa_workflow_instance(
            organization=self.org,
            user=self.user,
            cleaned_values={
                'counterparty': 'Mixed MSA Counterparty',
                'start_date': '2026-09-01',
                'contract_owner': 'Avery Brooks',
                'business_unit': 'Revenue Operations',
                'internal_reference': 'MSA-MIX-001',
                'value': 350000,
                'currency': 'EUR',
                'payment_terms': 'Net 30',
                'initial_term': '24 months',
                'renewal_type': 'Auto-renew',
                'termination_notice_period': 60,
                'services_description': 'Managed logistics services.',
                'governing_law': 'Delaware',
                'jurisdiction': 'Amsterdam',
                'liability_cap': '2x annual fees',
                'confidentiality_period': '5 years',
                'ip_ownership': 'Customer',
                'personal_data_involved': True,
                'value_above_threshold_confirmed': True,
                'liability_cap_nonstandard': True,
                'services_involve_personal_data': True,
            },
        )

        response = self.client_.get(reverse('dashboard'))

        for workflow, contract_type in ((dpa_workflow, 'DPA'), (msa_workflow, 'MSA')):
            self.assertContains(response, workflow.title)
            self.assertContains(response, contract_type)
            self.assertContains(
                response,
                reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}),
            )
        self.assertContains(response, 'Open workspace')
