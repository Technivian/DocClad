"""Regression coverage for the four Workflow Designer workspaces."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from contracts.models import (
    Organization,
    OrganizationMembership,
    UserProfile,
    Workflow,
    WorkflowTemplate,
    WorkflowTemplateScenario,
    WorkflowTemplateStep,
)
from contracts.services.workflow_designer import validate_template_for_publish
from contracts.services.workflow_execution import (
    compile_condition_rules,
    evaluate_condition_expression,
    evaluate_condition_rules,
)
from contracts.services.workflow_simulation import simulate_workflow_template

User = get_user_model()


class WorkflowDesignerCanvasTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Designer Org', slug='designer-org')
        self.user = User.objects.create_user(username='designer', password='pass12345', first_name='Alex')
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.user,
            role=OrganizationMembership.Role.ADMIN,
            is_active=True,
        )
        self.client = Client()
        self.client.login(username='designer', password='pass12345')
        self.template = WorkflowTemplate.objects.create(
            name='MSA Path',
            description='Canvas workflow',
            organization=self.org,
            category=WorkflowTemplate.Category.CONTRACT_REVIEW,
            version=1,
            is_active=False,
        )
        self.draft = WorkflowTemplateStep.objects.create(
            template=self.template,
            name='Draft',
            order=1,
            step_kind=WorkflowTemplateStep.StepKind.TASK,
        )
        self.review = WorkflowTemplateStep.objects.create(
            template=self.template,
            name='Legal review',
            order=2,
            step_kind=WorkflowTemplateStep.StepKind.REVIEW,
            assignee_role=UserProfile.Role.ASSOCIATE,
            sla_hours=24,
        )
        self.signature = WorkflowTemplateStep.objects.create(
            template=self.template,
            name='Signature',
            order=3,
            step_kind=WorkflowTemplateStep.StepKind.SIGNATURE,
        )

    def test_detail_uses_canvas_tabs_and_hides_footer(self):
        response = self.client.get(reverse('contracts:workflow_template_detail', args=[self.template.pk]))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertTrue(response.context['hide_app_footer'])
        for label in ('Design', 'Test', 'Versions', 'Activity'):
            self.assertIn(label, body)
        self.assertIn('Workflow Designer', body)
        self.assertEqual(body.count('wf-designer-header__title'), 1)
        self.assertIn(f'>{self.template.name}<', body)
        self.assertNotIn('topbar-page-title">' + self.template.name, body)
        self.assertIn('Save changes', body)
        self.assertIn('Test workflow', body)
        self.assertIn('Publish', body)
        self.assertNotIn('Create new version', body)
        self.assertNotIn('Add a step', body)
        self.assertNotIn('name="order"', body)
        self.assertIn('data-workflow-designer', body)
        self.assertIn('Move left', body)
        self.assertIn('Move right', body)
        self.assertIn('data-drag-handle', body)
        self.assertIn('aria-label="Add step"', body)
        self.assertIn('aria-labelledby="workflow-inspector-title"', body)
        self.assertIn('aria-label="Start"', body)
        self.assertIn('aria-label="Completed"', body)
        self.assertIn('data-zoom-fit', body)
        self.assertIn('wf-designer-insert', body)
        self.assertIn('wf-designer-connector', body)
        self.assertNotIn('aria-label="Move Legal review up"', body)
        self.assertIn('data-save-changes', body)
        self.assertIn('hidden disabled', body)  # Save only appears when dirty
        # First editable step is selected so the inspector is useful immediately.
        self.assertEqual(response.context['selected_step_id'], self.draft.pk)
        self.assertIn('Configure step', body)
        self.assertIn('Select a workflow step', body)
        self.assertIn('Signer configuration missing', body)

    def test_published_version_is_read_only_with_actions_menu(self):
        self.signature.assignee_role = UserProfile.Role.PARTNER
        self.signature.save(update_fields=['assignee_role'])
        self.template.is_active = True
        self.template.save(update_fields=['is_active'])
        response = self.client.get(reverse('contracts:workflow_template_detail', args=[self.template.pk]))
        body = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn('Test workflow', body)
        self.assertIn('Create new version', body)
        self.assertIn('Unpublish', body)
        self.assertIn('Archive', body)
        self.assertIn('View template details', body)
        self.assertIn('wf-designer-inspector__readonly', body)
        self.assertNotIn('data-save-changes', body)
        self.assertNotIn('data-drag-handle', body)
        self.assertNotIn('wf-designer-insert', body)
        self.assertFalse(response.context['can_edit_template'])

        versions = self.client.get(
            reverse('contracts:workflow_template_detail', args=[self.template.pk]) + '?tab=versions'
        )
        self.assertContains(versions, 'Create new version')

        blocked = self.client.post(
            reverse('contracts:workflow_template_step_add', args=[self.template.pk]),
            data={'name': 'Blocked', 'step_kind': 'TASK', 'assignment_mode': 'role'},
        )
        self.assertEqual(blocked.status_code, 403)

    def test_create_new_version_only_when_published(self):
        response = self.client.get(
            reverse('contracts:workflow_template_detail', args=[self.template.pk]) + '?tab=versions'
        )
        self.assertNotContains(response, 'Create new version')

        blocked = self.client.post(reverse('contracts:workflow_template_clone_version', args=[self.template.pk]))
        self.assertEqual(blocked.status_code, 302)
        self.assertEqual(WorkflowTemplate.objects.filter(parent_template=self.template).count(), 0)

        self.template.is_active = True
        self.template.save(update_fields=['is_active'])
        response = self.client.get(
            reverse('contracts:workflow_template_detail', args=[self.template.pk]) + '?tab=versions'
        )
        body = response.content.decode()
        self.assertTrue(
            'Create new version' in body or 'Create corrected version' in body,
            'Published versions must expose a create-version action',
        )

        created = self.client.post(reverse('contracts:workflow_template_clone_version', args=[self.template.pk]))
        self.assertEqual(created.status_code, 302)
        clone = WorkflowTemplate.objects.get(parent_template=self.template)
        self.assertFalse(clone.is_active)
        self.assertIn(f'/workflows/templates/{clone.pk}/', created['Location'])
        self.assertIn('tab=design', created['Location'])

        draft_page = self.client.get(reverse('contracts:workflow_template_detail', args=[clone.pk]))
        self.assertContains(draft_page, 'Save changes')
        self.assertContains(draft_page, 'Publish')
        self.assertTrue(draft_page.context['can_edit_template'])

    def test_condition_summary_and_branch_markup(self):
        self.review.condition_rules = {
            'logic': 'AND',
            'clauses': [{'field': 'risk_level', 'op': '=', 'value': 'HIGH'}],
        }
        self.review.condition_expression = 'risk_level=HIGH'
        self.review.save(update_fields=['condition_rules', 'condition_expression'])
        response = self.client.get(reverse('contracts:workflow_template_detail', args=[self.template.pk]))
        body = response.content.decode()
        self.assertIn('Runs when Risk level is High', body)
        self.assertIn('wf-designer-branch', body)
        self.assertIn('When matched', body)
        self.assertIn('Otherwise', body)
        self.assertIn('1-day SLA', body)

    def test_signature_requires_signer_configuration_for_publish(self):
        result = validate_template_for_publish(self.template)
        self.assertFalse(result.ok)
        self.assertTrue(any('Signer configuration missing' in err for err in result.errors))

        self.signature.assignee_role = UserProfile.Role.PARTNER
        self.signature.save(update_fields=['assignee_role'])
        result = validate_template_for_publish(self.template)
        self.assertTrue(result.ok, result.errors)

        orphan_approval = WorkflowTemplate.objects.create(
            name='Needs approval owner',
            organization=self.org,
            category=WorkflowTemplate.Category.GENERAL,
            version=1,
            is_active=False,
        )
        WorkflowTemplateStep.objects.create(
            template=orphan_approval,
            name='Legal approval',
            order=1,
            step_kind=WorkflowTemplateStep.StepKind.APPROVAL,
        )
        blocked = validate_template_for_publish(orphan_approval)
        self.assertFalse(blocked.ok)
        self.assertTrue(blocked.step_issues)
        self.assertEqual(blocked.step_issues[0]['step_name'], 'Legal approval')

    def test_invalid_published_workflow_shows_legacy_warning(self):
        self.template.is_active = True
        self.template.save(update_fields=['is_active'])
        response = self.client.get(reverse('contracts:workflow_template_detail', args=[self.template.pk]))
        self.assertTrue(response.context['published_has_blocking_issues'])
        body = response.content.decode()
        self.assertIn('Published configuration issue', body)
        self.assertIn('Create corrected version', body)
        self.assertIn('This immutable published version contains configuration that no longer passes validation.', body)
        self.assertIn('wf-identity-chip--published', body)
        self.assertIn('wf-identity-chip--issue', body)
        self.assertIn('wf-identity-chip--readonly', body)
        self.assertRegex(body, r'wf-identity-chip--published[^>]*>Published<')
        self.assertRegex(body, r'wf-identity-chip--issue[^>]*>Configuration issue<')
        self.assertRegex(body, r'wf-identity-chip--readonly[^>]*>Read-only<')
        self.assertNotIn('Published · Issues', body)
        self.assertNotIn('Published · Action required', body)
        self.assertNotRegex(body, r'wf-identity-chip--draft[^>]*>Draft<')
        # Header owns primary Create corrected version; card may also include it.
        self.assertGreaterEqual(body.count('Create corrected version'), 1)
        self.assertTrue(response.context['new_launches_blocked'])

    def test_launch_blocked_for_unassigned_required_steps(self):
        from contracts.services.workflow_designer import WorkflowLaunchBlocked, template_launch_block_reason
        from contracts.services.workflow_execution import materialize_workflow_from_template

        self.template.is_active = True
        self.template.save(update_fields=['is_active'])
        self.assertTrue(template_launch_block_reason(self.template))
        workflow = Workflow.objects.create(
            organization=self.org,
            title='Blocked launch',
            template=self.template,
            status=Workflow.Status.ACTIVE,
            created_by=self.user,
        )
        with self.assertRaises(WorkflowLaunchBlocked):
            materialize_workflow_from_template(workflow)

    def test_step_update_and_exclusive_assignment(self):
        response = self.client.post(
            reverse('contracts:workflow_template_step_update', args=[self.template.pk, self.review.pk]),
            data={
                'name': 'Legal review',
                'description': 'Updated',
                'step_kind': WorkflowTemplateStep.StepKind.REVIEW,
                'assignment_mode': 'role',
                'assignee_role': UserProfile.Role.ASSOCIATE,
                'specific_assignee': self.user.pk,
                'sla_hours': '24',
                'escalation_after_hours': '',
                'condition_rules_json': '',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.review.refresh_from_db()
        self.assertEqual(self.review.description, 'Updated')
        self.assertEqual(self.review.assignee_role, UserProfile.Role.ASSOCIATE)
        self.assertIsNone(self.review.specific_assignee_id)

        response = self.client.post(
            reverse('contracts:workflow_template_step_update', args=[self.template.pk, self.review.pk]),
            data={
                'name': 'Legal review',
                'description': 'Person assigned',
                'step_kind': WorkflowTemplateStep.StepKind.REVIEW,
                'assignment_mode': 'user',
                'assignee_role': UserProfile.Role.ASSOCIATE,
                'specific_assignee': self.user.pk,
                'sla_hours': '24',
                'escalation_after_hours': '',
                'condition_rules_json': '',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.review.refresh_from_db()
        self.assertEqual(self.review.specific_assignee_id, self.user.pk)
        self.assertEqual(self.review.assignee_role, '')

    def test_and_or_condition_rules_evaluate(self):
        rules = {
            'logic': 'AND',
            'clauses': [
                {'field': 'value', 'op': '>=', 'value': '100000'},
                {'field': 'data_transfer_flag', 'op': '=', 'value': 'true'},
            ],
        }
        self.assertEqual(compile_condition_rules(rules), 'value>=100000 and data_transfer_flag=true')

        class Obj:
            value = 150000
            data_transfer_flag = True

        self.assertTrue(evaluate_condition_rules(Obj(), rules))
        self.assertTrue(evaluate_condition_expression(Obj(), 'value>=100000 and data_transfer_flag=true'))

        rules['logic'] = 'OR'
        Obj.data_transfer_flag = False
        self.assertTrue(evaluate_condition_rules(Obj(), rules))

    def test_scenario_runner_workspace(self):
        self.draft.condition_rules = {
            'logic': 'AND',
            'clauses': [{'field': 'value', 'op': '>=', 'value': '1'}],
        }
        self.draft.condition_expression = 'value>=1'
        self.draft.save(update_fields=['condition_rules', 'condition_expression'])

        result = simulate_workflow_template(
            self.template,
            {'value': 5000, 'contract_type': 'MSA', 'status': 'IN_PROGRESS'},
            organization=self.org,
            user=self.user,
        )
        self.assertGreaterEqual(result.active_step_count, 1)
        self.assertTrue(result.resulting_route)
        self.assertIn('Draft', result.resulting_route)

        response = self.client.post(
            reverse('contracts:workflow_template_preview', args=[self.template.pk]),
            data={
                'contract_type': 'MSA',
                'value': '5000',
                'jurisdiction': 'Netherlands',
                'governing_law': 'Netherlands',
                'data_transfer_flag': '',
                'risk_level': '',
                'counterparty_name': '',
                'scenario_name': '',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['active_tab'], 'test')
        self.assertIsNotNone(response.context['preview_result'])
        body = response.content.decode()
        self.assertIn('Matched route', body)
        self.assertIn('Triggered conditions', body)
        self.assertIn('Skipped steps', body)
        self.assertIn('Assignments', body)
        self.assertIn('SLA and escalation', body)
        self.assertIn('Standard NDA', body)
        self.assertIn('High-risk international transfer', body)
        self.assertNotIn('Simulate routing without affecting live contracts.', body)
        self.assertNotIn('id_status', body)
        self.assertNotIn('wf-test-sim-badge', body)
        self.assertNotIn('>Simulation</', body)
        self.assertNotIn('Completed ·', body)
        self.assertNotIn('steps would run', body)
        result = response.context['preview_result']
        self.assertTrue(result.simulation_completed)
        self.assertIn(result.result_tone, {'pass', 'blocked', 'fail'})
        if result.execution_blocked:
            self.assertIn('Simulation completed with blocking issues', body)
            self.assertIn('View blocking issues', body)
            self.assertIn('Assignments evaluated', body)
            self.assertIn('execution would be blocked', body.lower())
        else:
            self.assertIn('Simulation completed — executable', body)

    def test_save_named_scenario(self):
        blocked = self.client.post(
            reverse('contracts:workflow_template_scenario_save', args=[self.template.pk]),
            data={
                'scenario_name': 'Standard NDA',
                'contract_type': 'NDA',
                'value': '0',
                'jurisdiction': 'Netherlands',
                'governing_law': 'Netherlands',
                'data_transfer_flag': '',
                'risk_level': 'LOW',
                'counterparty_name': 'Acme',
            },
        )
        self.assertEqual(blocked.status_code, 302)
        self.assertFalse(WorkflowTemplateScenario.objects.filter(template=self.template, name='Standard NDA').exists())

        response = self.client.post(
            reverse('contracts:workflow_template_scenario_save', args=[self.template.pk]),
            data={
                'scenario_name': 'Standard NDA',
                'scenario_ran': '1',
                'contract_type': 'NDA',
                'value': '0',
                'jurisdiction': 'Netherlands',
                'governing_law': 'Netherlands',
                'data_transfer_flag': '',
                'risk_level': 'LOW',
                'counterparty_name': 'Acme',
            },
        )
        self.assertEqual(response.status_code, 302)
        scenario = WorkflowTemplateScenario.objects.get(template=self.template, name='Standard NDA')
        self.assertEqual(scenario.payload.get('contract_type'), 'NDA')

    def test_versions_table_and_restore_as_draft(self):
        self.template.is_active = True
        self.template.save(update_fields=['is_active'])
        Workflow.objects.create(
            organization=self.org,
            title='Live MSA',
            template=self.template,
            status=Workflow.Status.ACTIVE,
            created_by=self.user,
        )
        versions = self.client.get(
            reverse('contracts:workflow_template_detail', args=[self.template.pk]) + '?tab=versions'
        )
        body = versions.content.decode()
        self.assertIn('Usage', body)
        self.assertIn('Restore as new draft', body)
        self.assertIn('1 active', body)
        self.assertNotIn('Unavailable', body)

        restored = self.client.post(reverse('contracts:workflow_template_restore_version', args=[self.template.pk]))
        self.assertEqual(restored.status_code, 302)
        draft = WorkflowTemplate.objects.get(version=2)
        self.assertFalse(draft.is_active)
        self.assertIn('tab=design', restored['Location'])

    def test_audit_trail_tab_filters_and_export(self):
        from contracts.services.workflow_audit import log_workflow_template_step_added

        log_workflow_template_step_added(self.review, self.user, request=None)
        response = self.client.get(
            reverse('contracts:workflow_template_detail', args=[self.template.pk]) + '?tab=audit'
        )
        body = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn('Activity', body)
        self.assertIn('Export activity', body)
        self.assertNotIn('View all activity', body)
        self.assertIn('Previous value', body)
        self.assertIn('Event ID', body)
        self.assertEqual(response.context['active_tab'], 'activity')

        canonical = self.client.get(
            reverse('contracts:workflow_template_detail', args=[self.template.pk]) + '?tab=activity'
        )
        self.assertEqual(canonical.context['active_tab'], 'activity')

        export = self.client.get(reverse('contracts:workflow_template_audit_export', args=[self.template.pk]))
        self.assertEqual(export.status_code, 200)
        self.assertIn('text/csv', export['Content-Type'])
        csv_body = export.content.decode()
        self.assertIn('Timestamp', csv_body)
        self.assertIn('Event ID', csv_body)
        self.assertIn('exported_at', csv_body)
        self.assertIn('workflow_template_id', csv_body)
