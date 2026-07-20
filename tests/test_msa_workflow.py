from django.contrib.auth import get_user_model
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from contracts.models import (
    ApprovalRequest,
    ApprovalRule,
    AuditLog,
    CommandCenterWorkItem,
    Contract,
    Deadline,
    Document,
    FieldDefinition,
    FieldValue,
    Organization,
    OrganizationMembership,
    RiskSignal,
    UserProfile,
    Workflow,
)
from contracts.services.finance_approval_policy import get_finance_approval_threshold
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

    def test_nonstandard_payment_terms_trigger_finance_signal(self):
        detect_msa_risk_signals(self.workflow, {'payment_terms': 'Net 45'})
        self.assertTrue(RiskSignal.objects.filter(workflow=self.workflow, code='nonstandard_payment_terms').exists())

    def test_standard_payment_terms_do_not_trigger_finance_signal(self):
        detect_msa_risk_signals(self.workflow, {'payment_terms': 'Net 30'})
        self.assertFalse(RiskSignal.objects.filter(workflow=self.workflow, code='nonstandard_payment_terms').exists())


class CreateMSAWorkflowInstanceTests(TestCase):
    def setUp(self):
        self.org, self.user, _ = _make_org_with_user('MSA Create Org', 'msa_create_user')

    def _cleaned_values(self, **overrides):
        values = {
            'counterparty': 'Northwind Services B.V.',
            'payrollminds_contracting_entity': 'Payrollminds B.V.',
            'client_contact_name': 'Nina Client',
            'client_contact_email': 'nina.client@northwind.example',
            'start_date': '2026-09-01',
            'end_date': '2028-08-31',
            'contract_owner': 'Avery Brooks',
            'business_unit': 'Revenue Operations',
            'internal_reference': 'MSA-2026-001',
            'value': 350000,
            'currency': 'EUR',
            'payment_terms': 'Net 30',
            'rate': 125,
            'travel_km_rate': 0.23,
            'administrative_fee': 1500,
            'initial_term': '24 months',
            'renewal_type': 'Auto-renew',
            'termination_notice_period': 60,
            'consultant_service_type': 'Payroll consulting',
            'services_description': 'Managed logistics platform and support services.',
            'worker_classification': 'Independent contractor',
            'payrollminds_professional_involved': True,
            'sow_required': True,
            'deliverables_defined': True,
            'acceptance_criteria_required': True,
            'governing_law': 'Delaware',
            'jurisdiction': 'Amsterdam',
            'liability_cap': '2x annual fees',
            'confidentiality_period': '5 years',
            'ip_ownership': 'Customer',
            'special_conditions': 'Client requires monthly service reporting.',
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
        obligation = Deadline.objects.get(contract=workflow.contract, auto_generated=True)
        self.assertEqual(obligation.deadline_type, Deadline.DeadlineType.RENEWAL)
        self.assertEqual(obligation.assigned_to, self.user)
        self.assertTrue(AuditLog.objects.filter(organization=self.org, event_type='obligation.auto_created').exists())


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
            f'field_{ids["payrollminds_contracting_entity"]}': 'Payrollminds B.V.',
            f'field_{ids["client_contact_name"]}': 'Nina Client',
            f'field_{ids["client_contact_email"]}': 'nina.client@northwind.example',
            f'field_{ids["start_date"]}': '2026-09-01',
            f'field_{ids["end_date"]}': '2028-08-31',
            f'field_{ids["contract_owner"]}': 'Avery Brooks',
            f'field_{ids["business_unit"]}': 'Revenue Operations',
            f'field_{ids["internal_reference"]}': 'MSA-2026-001',
            f'field_{ids["value"]}': '350000',
            f'field_{ids["currency"]}': 'EUR',
            f'field_{ids["payment_terms"]}': 'Net 30',
            f'field_{ids["rate"]}': '125',
            f'field_{ids["travel_km_rate"]}': '0.23',
            f'field_{ids["administrative_fee"]}': '1500',
            f'field_{ids["initial_term"]}': '24 months',
            f'field_{ids["renewal_type"]}': 'Auto-renew',
            f'field_{ids["termination_notice_period"]}': '60',
            f'field_{ids["consultant_service_type"]}': 'Payroll consulting',
            f'field_{ids["services_description"]}': 'Managed logistics platform and support services.',
            f'field_{ids["worker_classification"]}': 'Independent contractor',
            f'field_{ids["payrollminds_professional_involved"]}': 'on',
            f'field_{ids["sow_required"]}': 'on',
            f'field_{ids["deliverables_defined"]}': 'on',
            f'field_{ids["acceptance_criteria_required"]}': 'on',
            f'field_{ids["governing_law"]}': 'Delaware',
            f'field_{ids["jurisdiction"]}': 'Amsterdam',
            f'field_{ids["liability_cap"]}': '2x annual fees',
            f'field_{ids["confidentiality_period"]}': '5 years',
            f'field_{ids["ip_ownership"]}': 'Customer',
            f'field_{ids["special_conditions"]}': 'Client requires monthly service reporting.',
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
            'MSA Commercial Review Workflow',
            'A focused, governed workspace for commercial terms, legal positions, and approval-ready drafting.',
            'Drafting steps',
            'Live contract preview',
            'Decision panel',
            'Contract setup',
            'Commercial terms',
            'Services and scope',
            'Legal positions',
            'Review and generate',
            'Generate governed draft',
        ):
            self.assertContains(response, text)
        self.assertContains(response, 'Actions and governance for this draft.')
        self.assertContains(response, 'Payrollminds contracting entity')
        self.assertContains(response, 'Client contact email')

    def test_post_valid_redirects_to_msa_workspace(self):
        response = self.client_.post(reverse('contracts:msa_workflow_builder'), self._valid_payload())
        workflow = Workflow.objects.latest('id')
        self.assertRedirects(response, reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))

        workspace = self.client_.get(reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))
        for text in (
            'Guided drafting',
            'Live contract preview',
            'Document overview',
            'Governance details',
            'Risk monitoring',
            'Approval route',
            'Audit details',
            'Resolve ',
            'exception',
            'Actions',
            'Review approval route',
            'Send to Finance · blocked',
            'Download MSA summary',
            'Export Word',
            'Finance approval signal',
            'Liability cap deviation',
            'DPA / privacy review signal',
            'Triggered by:',
            'Commercial review',
            'Active stage owner',
            'Exception',
            'Open clause',
        ):
            self.assertContains(workspace, text)
        self.assertContains(workspace, 'MSA ·')
        self.assertNotContains(workspace, ' - Exception')
        self.assertNotContains(workspace, 'MSA clause')
        self.assertNotContains(workspace, 'Generated MSA draft')
        self.assertNotContains(workspace, 'Enterprise Services MSA · Netherlands · B2B</p>')
        self.assertNotContains(workspace, '>Send to Legal Review</button>')
        self.assertNotContains(workspace, '>Send to Finance</button>')
        self.assertNotContains(workspace, 'Edit clause')
        msa = workspace.context['msa_workspace']
        self.assertEqual(msa['timeline'], [
            'Intake', 'Drafting', 'Commercial review', 'Legal review',
            'Finance approval', 'Signature', 'Active',
        ])
        self.assertTrue(msa['open_exceptions'] >= 1)
        self.assertTrue(msa['primary_cta'].startswith('Resolve '))
        self.assertTrue(msa['risk_drivers'])
        titles = [section['title'] for section in msa['document_sections']]
        self.assertEqual(len(titles), len(set(titles)))
        self.assertTrue(any(section.get('state') for section in msa['document_sections']))
        self.assertTrue(any(section['state'] == 'Needs review' for section in msa['document_sections'] if section.get('tone') == 'ai'))

    def test_invalid_client_contact_email_returns_clear_error(self):
        payload = self._valid_payload()
        payload[f'field_{self._field_ids()["client_contact_email"]}'] = 'not-an-email'
        response = self.client_.post(reverse('contracts:msa_workflow_builder'), payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Enter a valid email address for client contact email.')

    def test_nonstandard_payment_term_routes_to_finance(self):
        payload = self._valid_payload()
        payload[f'field_{self._field_ids()["value"]}'] = '50000'
        payload.pop(f'field_{self._field_ids()["value_above_threshold_confirmed"]}', None)
        payload[f'field_{self._field_ids()["payment_terms"]}'] = 'Net 45'
        self.client_.post(reverse('contracts:msa_workflow_builder'), payload)
        workflow = Workflow.objects.latest('id')
        self.assertTrue(RiskSignal.objects.filter(workflow=workflow, code='nonstandard_payment_terms').exists())
        workspace = self.client_.get(reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))
        self.assertContains(workspace, 'Payment-term deviation')
        self.assertContains(workspace, 'Send to Finance · blocked')
        self.assertContains(workspace, 'Resolve ')
        self.assertContains(workspace, 'Review approval route')
        self.assertNotContains(workspace, 'Review Finance approval route')
        self.assertNotContains(workspace, '>Send to Finance</button>')

    def test_command_center_row_links_back_to_generated_workspace(self):
        self.client_.post(reverse('contracts:msa_workflow_builder'), self._valid_payload())
        workflow = Workflow.objects.latest('id')
        response = self.client_.get(reverse('dashboard'))
        self.assertContains(response, workflow.title)
        self.assertContains(response, 'MSA')
        self.assertContains(response, reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))
        self.assertContains(response, 'Resolve ')

    def _configure_msa_reviewer(self, *, username, approval_step, profile_role):
        reviewer = User.objects.create_user(username=username, password='reviewpass123!')
        OrganizationMembership.objects.create(
            organization=self.org,
            user=reviewer,
            role=OrganizationMembership.Role.MEMBER,
            is_active=True,
        )
        UserProfile.objects.create(user=reviewer, role=profile_role, department=approval_step.title())
        ApprovalRule.objects.create(
            organization=self.org,
            name=f'MSA {approval_step.title()} reviewer',
            trigger_type=ApprovalRule.TriggerType.CONTRACT_TYPE,
            trigger_value='MSA',
            approval_step=approval_step,
            approver_role=profile_role,
            specific_approver=reviewer,
            sla_hours=24,
            escalation_after_hours=48,
            is_active=True,
        )
        return reviewer

    def _resolve_open_exceptions(self, workflow):
        RiskSignal.objects.filter(workflow=workflow, is_resolved=False).update(
            is_resolved=True,
            resolved_at=timezone.now(),
        )

    def _confirm_needs_review_sections(self, workflow, *, kind='msa'):
        detail = self.client_.get(reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))
        workspace = detail.context[f'{kind}_workspace']
        for section in workspace['document_sections']:
            if section.get('state') == 'Needs review':
                self.client_.post(
                    reverse(
                        f'contracts:{kind}_confirm_section',
                        kwargs={'pk': workflow.pk, 'section_id': section['section_id']},
                    ),
                )

    def test_msa_submission_creates_real_approvals_and_requires_each_review(self):
        legal = self._configure_msa_reviewer(
            username='msa_legal_reviewer', approval_step='LEGAL', profile_role=UserProfile.Role.ASSOCIATE,
        )
        finance = self._configure_msa_reviewer(
            username='msa_finance_reviewer', approval_step='FINANCE', profile_role=UserProfile.Role.ADMIN,
        )
        self.client_.post(reverse('contracts:msa_workflow_builder'), self._valid_payload())
        workflow = Workflow.objects.latest('id')
        self._resolve_open_exceptions(workflow)
        self._confirm_needs_review_sections(workflow)

        legal_submit = self.client_.post(
            reverse('contracts:msa_submit_for_review', kwargs={'pk': workflow.pk, 'approval_step': 'legal'}),
        )
        self.assertRedirects(legal_submit, reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))
        finance_submit = self.client_.post(
            reverse('contracts:msa_submit_for_review', kwargs={'pk': workflow.pk, 'approval_step': 'finance'}),
        )
        self.assertRedirects(finance_submit, reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))
        self.assertEqual(ApprovalRequest.objects.filter(contract=workflow.contract, status=ApprovalRequest.Status.PENDING).count(), 2)
        workflow.contract.refresh_from_db()
        self.assertEqual(workflow.contract.status, Contract.Status.IN_PROGRESS)
        self.assertEqual(workflow.contract.lifecycle_stage, Contract.LifecycleStage.APPROVAL)

        legal_approval = ApprovalRequest.objects.get(contract=workflow.contract, approval_step='LEGAL')
        self.client_.login(username=legal.username, password='reviewpass123!')
        self.client_.post(
            reverse('contracts:contract_approval_decision', kwargs={
                'pk': workflow.contract.pk, 'approval_id': legal_approval.pk, 'decision': 'approve',
            }),
            {'comment': 'Legal review complete.'},
        )
        workflow.contract.refresh_from_db()
        self.assertEqual(workflow.contract.status, Contract.Status.IN_PROGRESS)
        self.assertEqual(workflow.contract.lifecycle_stage, Contract.LifecycleStage.APPROVAL)

        finance_approval = ApprovalRequest.objects.get(contract=workflow.contract, approval_step='FINANCE')
        self.client_.login(username=finance.username, password='reviewpass123!')
        self.client_.post(
            reverse('contracts:contract_approval_decision', kwargs={
                'pk': workflow.contract.pk, 'approval_id': finance_approval.pk, 'decision': 'approve',
            }),
            {'comment': 'Finance review complete.'},
        )
        workflow.contract.refresh_from_db()
        self.assertEqual(workflow.contract.status, Contract.Status.IN_PROGRESS)
        self.assertEqual(workflow.contract.lifecycle_stage, Contract.LifecycleStage.SIGNATURE)
        self.assertTrue(AuditLog.objects.filter(organization=self.org, event_type='approval.submitted').exists())

    def test_msa_exports_persist_downloadable_docx_artifacts(self):
        self.client_.post(reverse('contracts:msa_workflow_builder'), self._valid_payload())
        workflow = Workflow.objects.latest('id')
        response = self.client_.post(
            reverse('contracts:msa_export_document', kwargs={'pk': workflow.pk, 'artifact_type': 'word'}),
        )
        document = Document.objects.get(contract=workflow.contract, tags__contains='word')
        self.assertRedirects(
            response,
            reverse('contracts:document_download', kwargs={'pk': document.pk}),
            fetch_redirect_response=False,
        )
        self.assertTrue(document.file.name.endswith('.docx'))
        self.assertIn('Payrollminds_MSA_Northwind_Services_B_V', document.file.name)
        self.assertTrue(document.file.size > 0)
        self.assertTrue(AuditLog.objects.filter(organization=self.org, event_type='msa.word_exported').exists())

    def test_exception_resolution_uses_approved_wording_and_updates_counts(self):
        self.client_.post(reverse('contracts:msa_workflow_builder'), self._valid_payload())
        workflow = Workflow.objects.latest('id')
        signal = RiskSignal.objects.filter(workflow=workflow, is_resolved=False).first()
        self.assertIsNotNone(signal)
        before = RiskSignal.objects.filter(workflow=workflow, is_resolved=False).count()
        response = self.client_.post(
            reverse('contracts:msa_exception_action', kwargs={'pk': workflow.pk, 'signal_id': signal.pk}),
            {'action': 'use_approved_wording', 'comment': 'Aligned to playbook.'},
        )
        self.assertRedirects(response, reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))
        signal.refresh_from_db()
        self.assertTrue(signal.is_resolved)
        after = RiskSignal.objects.filter(workflow=workflow, is_resolved=False).count()
        self.assertEqual(after, before - 1)
        workspace = self.client_.get(reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))
        self.assertEqual(workspace.context['msa_workspace']['open_exceptions'], after)

    def test_keep_exception_requires_reason_and_owner(self):
        self.client_.post(reverse('contracts:msa_workflow_builder'), self._valid_payload())
        workflow = Workflow.objects.latest('id')
        signal = RiskSignal.objects.filter(workflow=workflow, is_resolved=False).first()
        response = self.client_.post(
            reverse('contracts:msa_exception_action', kwargs={'pk': workflow.pk, 'signal_id': signal.pk}),
            {'action': 'keep_exception'},
        )
        self.assertRedirects(response, reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))
        signal.refresh_from_db()
        self.assertFalse(signal.is_resolved)

    def test_msa_workspace_highlights_contracts_nav(self):
        self.client_.post(reverse('contracts:msa_workflow_builder'), self._valid_payload())
        workflow = Workflow.objects.latest('id')
        response = self.client_.get(reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))
        nav = response.context['SIDEBAR_NAV']
        contracts = next(item for item in nav if item.get('label') == 'Contracts')
        designer = next(item for item in nav if item.get('label') == 'Workflow Designer')
        self.assertTrue(contracts['is_active'])
        self.assertFalse(designer['is_active'])
        self.assertContains(response, 'Back to contract')

    def test_submit_for_review_blocked_while_exceptions_open(self):
        self.client_.post(reverse('contracts:msa_workflow_builder'), self._valid_payload())
        workflow = Workflow.objects.latest('id')
        self.assertTrue(RiskSignal.objects.filter(workflow=workflow, is_resolved=False).exists())
        response = self.client_.post(
            reverse('contracts:msa_submit_for_review', kwargs={'pk': workflow.pk, 'approval_step': 'legal'}),
        )
        detail_url = reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk})
        self.assertRedirects(response, detail_url, fetch_redirect_response=False)
        self.assertFalse(ApprovalRequest.objects.filter(contract=workflow.contract).exists())
        follow = self.client_.get(detail_url)
        self.assertContains(follow, 'before submitting this MSA for review')

    def test_submit_for_review_blocked_until_sections_confirmed(self):
        self.client_.post(reverse('contracts:msa_workflow_builder'), self._valid_payload())
        workflow = Workflow.objects.latest('id')
        self._resolve_open_exceptions(workflow)
        detail = self.client_.get(reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))
        msa = detail.context['msa_workspace']
        self.assertGreater(msa['document_overview']['needs_review'], 0)
        self.assertFalse(msa['can_submit_commercial'])
        self.assertContains(detail, 'need review')
        self.assertContains(detail, 'Send to Legal Review · blocked')

        response = self.client_.post(
            reverse('contracts:msa_submit_for_review', kwargs={'pk': workflow.pk, 'approval_step': 'legal'}),
        )
        self.assertRedirects(
            response,
            reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}),
            fetch_redirect_response=False,
        )
        follow = self.client_.get(reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))
        self.assertContains(follow, 'Confirm')
        self.assertContains(follow, 'before submitting this MSA for review')
        self.assertFalse(ApprovalRequest.objects.filter(contract=workflow.contract).exists())

        before = msa['document_overview']['needs_review']
        section = next(s for s in msa['document_sections'] if s['state'] == 'Needs review')
        confirm = self.client_.post(
            reverse('contracts:msa_confirm_section', kwargs={'pk': workflow.pk, 'section_id': section['section_id']}),
            follow=True,
        )
        self.assertContains(confirm, 'Section confirmed')
        after = confirm.context['msa_workspace']['document_overview']['needs_review']
        self.assertEqual(after, before - 1)

        self._confirm_needs_review_sections(workflow)
        ready = self.client_.get(reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))
        self.assertTrue(ready.context['msa_workspace']['can_submit_commercial'])
        self.assertContains(ready, '>Send to Legal Review</button>')

    def test_pilot_path_resolve_confirm_legal_finance_export(self):
        self._configure_msa_reviewer(
            username='msa_pilot_legal', approval_step='LEGAL', profile_role=UserProfile.Role.ASSOCIATE,
        )
        self._configure_msa_reviewer(
            username='msa_pilot_finance', approval_step='FINANCE', profile_role=UserProfile.Role.ADMIN,
        )
        self.client_.post(reverse('contracts:msa_workflow_builder'), self._valid_payload())
        workflow = Workflow.objects.latest('id')
        self.assertTrue(RiskSignal.objects.filter(workflow=workflow, is_resolved=False).exists())

        for signal in RiskSignal.objects.filter(workflow=workflow, is_resolved=False):
            self.client_.post(
                reverse('contracts:msa_exception_action', kwargs={'pk': workflow.pk, 'signal_id': signal.pk}),
                {'action': 'use_approved_wording', 'comment': 'Aligned to playbook.'},
            )
        self.assertFalse(RiskSignal.objects.filter(workflow=workflow, is_resolved=False).exists())
        self._confirm_needs_review_sections(workflow)

        legal = self.client_.post(
            reverse('contracts:msa_submit_for_review', kwargs={'pk': workflow.pk, 'approval_step': 'legal'}),
        )
        self.assertRedirects(legal, reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))
        finance = self.client_.post(
            reverse('contracts:msa_submit_for_review', kwargs={'pk': workflow.pk, 'approval_step': 'finance'}),
        )
        self.assertRedirects(finance, reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))
        self.assertEqual(
            ApprovalRequest.objects.filter(contract=workflow.contract, status=ApprovalRequest.Status.PENDING).count(),
            2,
        )

        export = self.client_.post(
            reverse('contracts:msa_export_document', kwargs={'pk': workflow.pk, 'artifact_type': 'word'}),
        )
        document = Document.objects.get(contract=workflow.contract, tags__contains='word')
        self.assertRedirects(
            export,
            reverse('contracts:document_download', kwargs={'pk': document.pk}),
            fetch_redirect_response=False,
        )
