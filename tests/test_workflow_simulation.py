from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from contracts.models import Contract, Organization, OrganizationMembership, UserProfile, Workflow, WorkflowStep, WorkflowTemplate, WorkflowTemplateStep
from contracts.services.workflow_simulation import simulate_workflow_template


User = get_user_model()


class WorkflowSimulationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='sim-owner', password='testpass123')
        self.admin = User.objects.create_user(username='sim-admin', password='testpass123')
        self.other_user = User.objects.create_user(username='sim-other', password='testpass123')

        self.org_a = Organization.objects.create(name='Simulation Org A', slug='simulation-org-a')
        self.org_b = Organization.objects.create(name='Simulation Org B', slug='simulation-org-b')
        OrganizationMembership.objects.create(
            organization=self.org_a,
            user=self.owner,
            role=OrganizationMembership.Role.OWNER,
            is_active=True,
        )
        OrganizationMembership.objects.create(
            organization=self.org_a,
            user=self.admin,
            role=OrganizationMembership.Role.ADMIN,
            is_active=True,
        )
        OrganizationMembership.objects.create(
            organization=self.org_b,
            user=self.other_user,
            role=OrganizationMembership.Role.OWNER,
            is_active=True,
        )
        UserProfile.objects.get_or_create(user=self.owner, defaults={'role': UserProfile.Role.ADMIN})
        UserProfile.objects.get_or_create(user=self.admin, defaults={'role': UserProfile.Role.ADMIN})
        UserProfile.objects.get_or_create(user=self.other_user, defaults={'role': UserProfile.Role.ASSOCIATE})

        self.template = WorkflowTemplate.objects.create(
            name='Simulation Template',
            description='Template used for dry-run simulation tests',
            organization=self.org_a,
            category=WorkflowTemplate.Category.CONTRACT_REVIEW,
            version=1,
            is_active=True,
        )
        WorkflowTemplateStep.objects.create(
            template=self.template,
            name='Intake',
            description='Initial intake',
            order=1,
            step_kind=WorkflowTemplateStep.StepKind.TASK,
        )
        WorkflowTemplateStep.objects.create(
            template=self.template,
            name='High Value Approval',
            description='Value gate',
            order=2,
            step_kind=WorkflowTemplateStep.StepKind.APPROVAL,
            condition_expression='value>=250000',
            assignee_role=UserProfile.Role.ADMIN,
            sla_hours=24,
            escalation_after_hours=48,
        )
        WorkflowTemplateStep.objects.create(
            template=self.template,
            name='Data Transfer Review',
            description='Privacy gate',
            order=3,
            step_kind=WorkflowTemplateStep.StepKind.TASK,
            condition_expression='data_transfer=true',
        )
        WorkflowTemplateStep.objects.create(
            template=self.template,
            name='Risk Review',
            description='Risk gate',
            order=4,
            step_kind=WorkflowTemplateStep.StepKind.TASK,
            condition_expression='risk=HIGH',
        )
        WorkflowTemplateStep.objects.create(
            template=self.template,
            name='Auto Archive',
            description='Automatic closeout',
            order=5,
            step_kind=WorkflowTemplateStep.StepKind.AUTOMATION,
        )

        self.high_value_data = {
            'contract_type': Contract.ContractType.MSA,
            'value': 500000,
            'jurisdiction': 'New York',
            'governing_law': 'Delaware',
            'data_transfer_flag': False,
            'risk_level': Contract.RiskLevel.LOW,
            'counterparty_name': 'Acme',
            'status': Contract.Status.IN_PROGRESS,
        }
        self.low_value_data = {
            'contract_type': Contract.ContractType.NDA,
            'value': 5000,
            'jurisdiction': 'New York',
            'governing_law': 'Delaware',
            'data_transfer_flag': False,
            'risk_level': Contract.RiskLevel.LOW,
            'counterparty_name': 'Acme',
            'status': Contract.Status.IN_PROGRESS,
        }

    def test_simulate_workflow_template_returns_all_steps_and_does_not_create_records(self):
        before_workflows = Workflow.objects.count()
        before_steps = WorkflowStep.objects.count()

        result = simulate_workflow_template(self.template, self.high_value_data, organization=self.org_a, user=self.owner)

        self.assertEqual(len(result.preview_steps), 5)
        self.assertEqual(Workflow.objects.count(), before_workflows)
        self.assertEqual(WorkflowStep.objects.count(), before_steps)

    def test_empty_condition_applies(self):
        result = simulate_workflow_template(self.template, self.high_value_data, organization=self.org_a)
        self.assertTrue(result.preview_steps[0].would_apply)
        self.assertEqual(result.preview_steps[0].preview_status, 'WOULD_START')

    def test_value_condition_applies_for_high_value_data(self):
        result = simulate_workflow_template(self.template, self.high_value_data, organization=self.org_a)
        self.assertTrue(result.preview_steps[1].would_apply)
        self.assertEqual(result.preview_steps[1].preview_status, 'WOULD_WAIT')

    def test_value_condition_skips_for_low_value_data(self):
        result = simulate_workflow_template(self.template, self.low_value_data, organization=self.org_a)
        self.assertFalse(result.preview_steps[1].would_apply)
        self.assertEqual(result.preview_steps[1].preview_status, 'WOULD_SKIP')

    def test_data_transfer_condition_applies_correctly(self):
        data = dict(self.low_value_data)
        data['data_transfer_flag'] = True
        result = simulate_workflow_template(self.template, data, organization=self.org_a)
        self.assertTrue(result.preview_steps[2].would_apply)
        self.assertEqual(result.preview_steps[2].preview_status, 'WOULD_WAIT')

    def test_risk_condition_applies_correctly(self):
        data = dict(self.low_value_data)
        data['risk_level'] = Contract.RiskLevel.HIGH
        result = simulate_workflow_template(self.template, data, organization=self.org_a)
        self.assertTrue(result.preview_steps[3].would_apply)
        self.assertEqual(result.preview_steps[3].preview_status, 'WOULD_WAIT')

    def test_automatic_step_completes_automatically(self):
        result = simulate_workflow_template(self.template, self.high_value_data, organization=self.org_a)
        self.assertEqual(result.preview_steps[4].preview_status, 'WOULD_COMPLETE_AUTOMATICALLY')

    def test_first_actionable_step_starts_and_later_applicable_step_waits(self):
        result = simulate_workflow_template(self.template, self.high_value_data, organization=self.org_a)
        self.assertEqual(result.preview_steps[0].preview_status, 'WOULD_START')
        self.assertEqual(result.preview_steps[1].preview_status, 'WOULD_WAIT')

    def test_preview_route_allows_unpublished_templates(self):
        self.client.force_login(self.owner)
        self.template.is_active = False
        self.template.save(update_fields=['is_active'])

        response = self.client.post(
            reverse('contracts:workflow_template_preview', args=[self.template.pk]),
            data={
                'contract_type': Contract.ContractType.MSA,
                'value': '500000',
                'jurisdiction': 'New York',
                'governing_law': 'Delaware',
                'data_transfer_flag': '',
                'risk_level': Contract.RiskLevel.LOW,
                'counterparty_name': 'Acme',
                'status': Contract.Status.IN_PROGRESS,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Matched route')
        self.assertContains(response, 'Triggered conditions')
        self.assertIsNotNone(response.context['preview_result'])
        self.assertGreater(response.context['preview_result'].active_step_count, 0)
        self.assertIn(response.context['preview_result'].result_tone, {'pass', 'blocked', 'fail'})
        body = response.content.decode()
        self.assertIn('Simulation completed', body)
        self.assertNotIn('Completed ·', body)
        self.assertNotIn('steps would run', body)
        self.assertNotIn('Assignments resolved</strong> — for each', body)

    def test_cross_tenant_preview_is_blocked(self):
        self.client.force_login(self.other_user)
        response = self.client.get(reverse('contracts:workflow_template_detail', args=[self.template.pk]))
        self.assertEqual(response.status_code, 404)
        preview_response = self.client.post(
            reverse('contracts:workflow_template_preview', args=[self.template.pk]),
            data={'value': '250000'},
        )
        self.assertEqual(preview_response.status_code, 404)

    def test_invalid_preview_form_does_not_crash(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('contracts:workflow_template_preview', args=[self.template.pk]),
            data={
                'contract_type': Contract.ContractType.MSA,
                'value': 'not-a-number',
                'jurisdiction': 'New York',
                'governing_law': 'Delaware',
                'data_transfer_flag': '',
                'risk_level': Contract.RiskLevel.LOW,
                'counterparty_name': 'Acme',
                'status': Contract.Status.IN_PROGRESS,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['preview_form'].errors)
        self.assertIsNone(response.context['preview_result'])

    def test_finance_threshold_skip_is_humanised(self):
        WorkflowTemplateStep.objects.create(
            template=self.template,
            name='Finance Review',
            description='Finance gate',
            order=6,
            step_kind=WorkflowTemplateStep.StepKind.APPROVAL,
            condition_expression='finance_threshold=true',
            assignee_role=UserProfile.Role.ADMIN,
        )
        result = simulate_workflow_template(self.template, self.low_value_data, organization=self.org_a)
        finance = next(step for step in result.preview_steps if step.name == 'Finance Review')
        self.assertFalse(finance.would_apply)
        self.assertIn('did not meet the finance approval threshold', finance.reason)
        self.assertNotIn('finance_threshold=', finance.reason)

    def test_unresolved_assignments_block_execution_but_simulation_completes(self):
        result = simulate_workflow_template(self.template, self.high_value_data, organization=self.org_a)
        self.assertTrue(result.simulation_completed)
        self.assertGreater(result.unresolved_assignment_count, 0)
        self.assertTrue(result.execution_blocked)
        self.assertEqual(result.result_tone, 'blocked')
        self.assertEqual(result.execution_outcome_label, 'Blocked before launch')
        self.assertIn('unresolved assignments', result.final_outcome_label)
        self.assertTrue(any('Assignment unresolved' in message for message in result.validation_messages))
