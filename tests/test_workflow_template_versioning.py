from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from contracts.forms import WorkflowTemplateStepForm
from contracts.models import AuditLog, Contract, Organization, OrganizationMembership, UserProfile, Workflow, WorkflowTemplate, WorkflowTemplateStep
from contracts.services.workflow_templates import clone_template_version, list_template_versions


User = get_user_model()


class WorkflowTemplateVersioningTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='template-user', password='pass12345')
        self.org = Organization.objects.create(name='Template Org', slug='template-org')
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.user,
            role=OrganizationMembership.Role.OWNER,
            is_active=True,
        )
        self.contract = Contract.objects.create(
            organization=self.org,
            title='Template Contract',
            content='Template content',
            status=Contract.Status.ACTIVE,
            created_by=self.user,
        )
        self.template = WorkflowTemplate.objects.create(
            name='Contract Review',
            description='Base contract review flow',
            category=WorkflowTemplate.Category.CONTRACT_REVIEW,
            version=1,
            is_active=True,
        )
        self.alt_template = WorkflowTemplate.objects.create(
            name='Compliance Review',
            description='Alternate flow',
            category=WorkflowTemplate.Category.COMPLIANCE,
            version=1,
            is_active=True,
        )
        WorkflowTemplateStep.objects.create(
            template=self.template,
            name='Intake',
            description='Initial intake',
            order=1,
        )
        WorkflowTemplateStep.objects.create(
            template=self.template,
            name='Review',
            description='Legal review',
            order=2,
        )
        self.workflow = Workflow.objects.create(
            organization=self.org,
            title='Workflow One',
            description='First workflow',
            contract=self.contract,
            template=self.template,
            created_by=self.user,
        )

    def test_clone_template_version_copies_steps_and_links_lineage(self):
        first_step = self.template.steps.get(order=1)
        first_step.step_kind = WorkflowTemplateStep.StepKind.APPROVAL
        first_step.condition_expression = 'value>=250000'
        first_step.assignee_role = UserProfile.Role.ADMIN
        first_step.sla_hours = 12
        first_step.escalation_after_hours = 24
        first_step.save(
            update_fields=['step_kind', 'condition_expression', 'assignee_role', 'sla_hours', 'escalation_after_hours']
        )

        clone = clone_template_version(self.template, name='Contract Review v2')

        self.assertEqual(clone.version, 2)
        self.assertEqual(clone.parent_template_id, self.template.id)
        self.assertEqual(clone.name, 'Contract Review v2')
        self.assertEqual(clone.steps.count(), 2)
        cloned_step = clone.steps.get(order=1)
        self.assertEqual(cloned_step.name, 'Intake')
        self.assertEqual(cloned_step.step_kind, WorkflowTemplateStep.StepKind.APPROVAL)
        self.assertEqual(cloned_step.condition_expression, 'value>=250000')
        self.assertEqual(cloned_step.assignee_role, UserProfile.Role.ADMIN)
        self.assertEqual(cloned_step.sla_hours, 12)
        self.assertEqual(cloned_step.escalation_after_hours, 24)

    def test_list_template_versions_returns_latest_first(self):
        clone = clone_template_version(self.template)
        versions = list_template_versions(clone)

        self.assertGreaterEqual(len(versions), 2)
        self.assertEqual(versions[0].version, 2)
        self.assertEqual(versions[1].version, 1)

    def test_management_command_clones_and_migrates_workflows(self):
        call_command(
            'migrate_workflow_template',
            source_template_id=self.template.id,
            migrate_workflows=True,
            migration_reason='Test governed cutover',
            deactivate_source=True,
        )

        refreshed_workflow = Workflow.objects.get(pk=self.workflow.pk)
        new_template = refreshed_workflow.template
        self.assertNotEqual(new_template.pk, self.template.pk)
        self.assertEqual(new_template.version, 2)
        self.assertEqual(new_template.parent_template_id, self.template.id)

        self.template.refresh_from_db()
        self.assertFalse(self.template.is_active)

    def test_template_views_render_version_and_steps(self):
        self.client.force_login(self.user)

        list_response = self.client.get(reverse('contracts:workflow_template_list'))
        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, 'Contract Review')
        self.assertContains(list_response, 'Published')
        body = list_response.content.decode()
        self.assertNotIn('Not published', body)
        self.assertIn('template-tile__secondary', body)
        self.assertIn('template-status-dot--live', body)
        self.assertIn('>Live</span>', body)
        self.assertNotIn('0 Live', body)
        self.assertRegex(body, r'Used by \d+|Not used yet')

        detail_response = self.client.get(reverse('contracts:workflow_template_detail', args=[self.template.pk]))
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, 'v1')
        self.assertContains(detail_response, 'Design')
        self.assertContains(detail_response, 'Audit trail')
        self.assertContains(detail_response, 'Intake')
        self.assertNotContains(detail_response, 'data-save-changes')
        self.assertNotContains(detail_response, 'Add a step')
        self.assertNotContains(detail_response, 'Workflow Steps')
        versions_response = self.client.get(
            reverse('contracts:workflow_template_detail', args=[self.template.pk]) + '?tab=versions'
        )
        self.assertContains(versions_response, 'Create new version')
        self.assertContains(versions_response, 'Restore as new draft')

    def test_template_detail_add_step_creates_step_and_redirects(self):
        self.client.force_login(self.user)
        self.template.is_active = False
        self.template.save(update_fields=['is_active'])

        response = self.client.post(
            reverse('contracts:workflow_template_step_add', args=[self.template.pk]),
            data={
                'name': 'Signature',
                'description': 'Collect signatures',
                'step_kind': 'SIGNATURE',
                'assignment_mode': 'role',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse('contracts:workflow_template_detail', args=[self.template.pk]),
            response['Location'],
        )

        self.template.refresh_from_db()
        created_step = WorkflowTemplateStep.objects.get(template=self.template, name='Signature')
        self.assertEqual(created_step.description, 'Collect signatures')
        self.assertEqual(created_step.order, 3)
        self.assertEqual(created_step.step_kind, WorkflowTemplateStep.StepKind.SIGNATURE)

    def test_template_detail_delete_step_is_post_only_and_scoped(self):
        self.client.force_login(self.user)
        self.template.is_active = False
        self.template.save(update_fields=['is_active'])
        step = self.template.steps.get(order=1)

        get_response = self.client.get(reverse('contracts:workflow_template_step_delete', args=[self.template.pk, step.pk]))
        self.assertEqual(get_response.status_code, 405)

        response = self.client.post(reverse('contracts:workflow_template_step_delete', args=[self.template.pk, step.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(WorkflowTemplateStep.objects.filter(pk=step.pk).exists())
        self.assertTrue(
            AuditLog.objects.filter(
                model_name='WorkflowTemplateStep',
                action=AuditLog.Action.DELETE,
                object_id=step.pk,
            ).exists()
        )

    def test_template_detail_reorder_steps(self):
        self.client.force_login(self.user)
        self.template.is_active = False
        self.template.save(update_fields=['is_active'])
        ordered_ids = list(self.template.steps.order_by('order').values_list('id', flat=True))
        response = self.client.post(
            reverse('contracts:workflow_template_step_reorder', args=[self.template.pk]),
            data={'step_ids': [ordered_ids[1], ordered_ids[0]]},
        )
        self.assertEqual(response.status_code, 302)
        refreshed = list(self.template.steps.order_by('order').values_list('id', flat=True))
        self.assertEqual(refreshed, [ordered_ids[1], ordered_ids[0]])

    def test_template_publish_toggle_requires_steps_and_hides_inactive_from_new_workflows(self):
        self.client.force_login(self.user)

        empty_template = WorkflowTemplate.objects.create(
            name='Empty Template',
            description='No steps yet',
            organization=self.org,
            category=WorkflowTemplate.Category.CONTRACT_REVIEW,
            version=1,
            is_active=False,
        )
        empty_response = self.client.post(reverse('contracts:workflow_template_publish_toggle', args=[empty_template.pk]))
        self.assertEqual(empty_response.status_code, 302)
        empty_template.refresh_from_db()
        self.assertFalse(empty_template.is_active)

        active_response = self.client.post(reverse('contracts:workflow_template_publish_toggle', args=[self.template.pk]))
        self.assertEqual(active_response.status_code, 302)
        self.template.refresh_from_db()
        self.assertFalse(self.template.is_active)

        create_response = self.client.get(reverse('contracts:workflow_create'))
        self.assertEqual(create_response.status_code, 200)
        self.assertNotIn(self.template.pk, list(create_response.context['form'].fields['template'].queryset.values_list('pk', flat=True)))

        republish_response = self.client.post(reverse('contracts:workflow_template_publish_toggle', args=[self.template.pk]))
        self.assertEqual(republish_response.status_code, 302)
        self.template.refresh_from_db()
        self.assertTrue(self.template.is_active)

    def test_new_template_is_created_unpublished_even_though_model_default_is_active(self):
        """Sub-block D4: WorkflowTemplate.is_active defaults to True at the
        model level (used by 15+ other call sites that assume an
        immediately-usable template, e.g. cloning one that already has
        steps) — but a template created through this form always has zero
        steps, so this specific path must not inherit that default."""
        self.client.force_login(self.user)
        response = self.client.post(reverse('contracts:workflow_template_create'), {
            'name': 'Freshly Created Template',
            'description': 'Has no steps yet',
            'category': WorkflowTemplate.Category.GENERAL,
            'source_mode': 'blank',
        })
        self.assertEqual(response.status_code, 302)
        created = WorkflowTemplate.objects.get(name='Freshly Created Template')
        self.assertFalse(created.is_active)
        self.assertEqual(created.steps.count(), 0)

    def test_crafted_post_cannot_publish_a_stepless_template_bypassing_the_disabled_button(self):
        """The UI disables the Publish button when there are no steps, but a
        crafted POST (bypassing the disabled attribute entirely) must still
        be rejected server-side — this is the actual D4 requirement, not the
        disabled attribute, which is cosmetic."""
        self.client.force_login(self.user)
        stepless = WorkflowTemplate.objects.create(
            name='Stepless', description='', organization=self.org,
            category=WorkflowTemplate.Category.GENERAL, version=1, is_active=False,
        )
        response = self.client.post(reverse('contracts:workflow_template_publish_toggle', args=[stepless.pk]))
        self.assertEqual(response.status_code, 302)
        stepless.refresh_from_db()
        self.assertFalse(stepless.is_active, 'a stepless template must never become published, even via a direct POST')

    def test_template_becomes_publishable_once_a_step_exists(self):
        self.client.force_login(self.user)
        template = WorkflowTemplate.objects.create(
            name='Gains A Step', description='', organization=self.org,
            category=WorkflowTemplate.Category.GENERAL, version=1, is_active=False,
        )
        WorkflowTemplateStep.objects.create(template=template, name='Only step', order=1)
        response = self.client.post(reverse('contracts:workflow_template_publish_toggle', args=[template.pk]))
        self.assertEqual(response.status_code, 302)
        template.refresh_from_db()
        self.assertTrue(template.is_active)

    def test_approval_stage_without_owner_cannot_publish(self):
        self.client.force_login(self.user)
        template = WorkflowTemplate.objects.create(
            name='Needs Owner', description='', organization=self.org,
            category=WorkflowTemplate.Category.GENERAL, version=1, is_active=False,
        )
        WorkflowTemplateStep.objects.create(
            template=template,
            name='Legal approval',
            order=1,
            step_kind=WorkflowTemplateStep.StepKind.APPROVAL,
        )
        response = self.client.post(reverse('contracts:workflow_template_publish_toggle', args=[template.pk]))
        self.assertEqual(response.status_code, 302)
        template.refresh_from_db()
        self.assertFalse(template.is_active)

    def test_list_marks_standard_zero_stage_as_draft_incomplete(self):
        self.client.force_login(self.user)
        WorkflowTemplate.objects.create(
            name='Standard',
            description='Standard workflow placeholder',
            organization=self.org,
            category=WorkflowTemplate.Category.GENERAL,
            version=1,
            is_active=True,
        )
        response = self.client.get(reverse('contracts:workflow_template_list'))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn('Setup required', body)
        self.assertIn('Open designer', body)
        self.assertIn('No workflow stages configured', body)
        self.assertIn('Add at least one stage to continue', body)
        self.assertIn('Drafts', body)
        standard = WorkflowTemplate.objects.get(name='Standard', organization=self.org)
        self.assertFalse(standard.is_active)

    def test_create_duplicate_opens_designer_with_copied_stages(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('contracts:workflow_template_create'), {
            'name': 'Copied Contract Review',
            'description': 'Duplicated from existing',
            'category': WorkflowTemplate.Category.CONTRACT_REVIEW,
            'source_mode': 'duplicate',
            'source_template': self.template.pk,
        })
        self.assertEqual(response.status_code, 302)
        created = WorkflowTemplate.objects.get(name='Copied Contract Review')
        self.assertFalse(created.is_active)
        self.assertEqual(created.steps.count(), self.template.steps.count())
        self.assertEqual(response['Location'], reverse('contracts:workflow_template_detail', args=[created.pk]))

    def test_condition_expression_validation(self):
        import json
        valid_form = WorkflowTemplateStepForm(
            data={
                'name': 'Approval',
                'description': '',
                'step_kind': WorkflowTemplateStep.StepKind.APPROVAL,
                'assignment_mode': 'role',
                'condition_rules_json': json.dumps({
                    'logic': 'AND',
                    'clauses': [{'field': 'value', 'op': '>=', 'value': '250000'}],
                }),
                'assignee_role': '',
                'specific_assignee': '',
                'sla_hours': '',
                'escalation_after_hours': '',
            }
        )
        self.assertTrue(valid_form.is_valid(), valid_form.errors)
        self.assertEqual(valid_form.cleaned_data['condition_expression'], 'value>=250000')

        invalid_field = WorkflowTemplateStepForm(
            data={
                'name': 'Approval',
                'description': '',
                'step_kind': WorkflowTemplateStep.StepKind.APPROVAL,
                'assignment_mode': 'role',
                'condition_rules_json': json.dumps({
                    'logic': 'AND',
                    'clauses': [{'field': 'unknown', 'op': '=', 'value': 'HIGH'}],
                }),
                'assignee_role': '',
                'specific_assignee': '',
                'sla_hours': '',
                'escalation_after_hours': '',
            }
        )
        self.assertFalse(invalid_field.is_valid())
        self.assertIn('condition_rules_json', invalid_field.errors)

        invalid_syntax = WorkflowTemplateStepForm(
            data={
                'name': 'Approval',
                'description': '',
                'step_kind': WorkflowTemplateStep.StepKind.APPROVAL,
                'assignment_mode': 'role',
                'condition_rules_json': '{not-json',
                'assignee_role': '',
                'specific_assignee': '',
                'sla_hours': '',
                'escalation_after_hours': '',
            }
        )
        self.assertFalse(invalid_syntax.is_valid())
        self.assertIn('condition_rules_json', invalid_syntax.errors)

    def test_template_list_scopes_other_org_templates_out(self):
        other_org = Organization.objects.create(name='Other Org', slug='other-org')
        other_user = User.objects.create_user(username='other-user', password='pass12345')
        OrganizationMembership.objects.create(
            organization=other_org,
            user=other_user,
            role=OrganizationMembership.Role.OWNER,
            is_active=True,
        )
        other_template = WorkflowTemplate.objects.create(
            name='Other Review',
            description='Other org flow',
            organization=other_org,
            category=WorkflowTemplate.Category.CONTRACT_REVIEW,
            version=1,
            is_active=True,
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse('contracts:workflow_template_list'))
        self.assertEqual(response.status_code, 200)
        template_ids = [item.id for item in response.context['workflow_templates']]
        self.assertIn(self.template.id, template_ids)
        self.assertNotIn(other_template.id, template_ids)

    def test_template_detail_clone_action_creates_new_version(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse('contracts:workflow_template_clone_version', args=[self.template.pk]))
        self.assertEqual(response.status_code, 302)

        clone = WorkflowTemplate.objects.get(version=2)
        self.assertEqual(clone.parent_template_id, self.template.id)
        self.assertEqual(clone.steps.count(), 2)
        self.assertFalse(clone.is_active)
        self.assertRedirects(
            response,
            reverse('contracts:workflow_template_detail', args=[clone.pk]) + '?tab=design',
            fetch_redirect_response=False,
        )

    def test_template_restore_action_creates_follow_on_version(self):
        self.client.force_login(self.user)
        clone = clone_template_version(self.template)

        response = self.client.post(reverse('contracts:workflow_template_restore_version', args=[self.template.pk]))
        self.assertEqual(response.status_code, 302)

        restored = WorkflowTemplate.objects.get(version=3)
        self.assertEqual(restored.parent_template_id, self.template.id)
        self.assertEqual(restored.steps.count(), 2)
        self.assertFalse(restored.is_active)
        self.assertRedirects(
            response,
            reverse('contracts:workflow_template_detail', args=[restored.pk]) + '?tab=design',
            fetch_redirect_response=False,
        )

    def test_template_compare_view_shows_field_and_step_differences(self):
        self.client.force_login(self.user)
        clone = clone_template_version(self.template, name='Contract Review Revised')
        clone.description = 'Changed flow'
        clone.save(update_fields=['description'])

        response = self.client.get(reverse('contracts:workflow_template_compare', args=[self.template.pk, clone.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Template Comparison')
        self.assertContains(response, 'Field Differences')
        self.assertContains(response, 'name')

    def test_template_compare_view_supports_legal_ops_preset(self):
        self.client.force_login(self.user)
        clone = clone_template_version(self.template, name='Contract Review Revised')
        clone.description = 'Changed flow'
        clone.save(update_fields=['description'])

        response = self.client.get(
            reverse('contracts:workflow_template_compare', args=[self.template.pk, clone.pk]) + '?preset=legal_ops'
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Legal ops review')
        self.assertNotContains(response, 'description')

    def test_workflow_editor_surfaces_suggested_template_summary(self):
        self.client.force_login(self.user)
        request_url = reverse('contracts:workflow_create')
        response = self.client.get(
            f"{request_url}?contract_pk={self.contract.pk}&template_pk={self.alt_template.pk}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Suggested template')
        self.assertContains(response, 'Compare against selected template')
        self.assertContains(response, 'Open legal ops diff')

    def test_duplicate_names_use_copy_n_not_nested_copy_of(self):
        from contracts.services.workflow_designer import duplicate_workflow_template, next_duplicate_template_name

        first = next_duplicate_template_name(self.template)
        self.assertEqual(first, 'Contract Review Copy 2')
        clone = duplicate_workflow_template(self.template)
        self.assertEqual(clone.name, 'Contract Review Copy 2')
        self.assertFalse(clone.is_active)
        second = duplicate_workflow_template(self.template)
        self.assertEqual(second.name, 'Contract Review Copy 3')
        nested_source = WorkflowTemplate.objects.create(
            name='Copy of Copy of NDA Self-Serve Workflow',
            description='Legacy nested name',
            category=WorkflowTemplate.Category.GENERAL,
            version=1,
            is_active=False,
        )
        cleaned = duplicate_workflow_template(nested_source)
        self.assertEqual(cleaned.name, 'NDA Self-Serve Workflow Copy 2')
        self.assertNotIn('Copy of', cleaned.name)

    def test_duplicate_action_prompts_rename_before_designer(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('contracts:workflow_template_duplicate', args=[self.template.pk]))
        self.assertEqual(response.status_code, 302)
        clone = WorkflowTemplate.objects.get(name='Contract Review Copy 2')
        self.assertIn(
            reverse('contracts:workflow_template_update', args=[clone.pk]),
            response['Location'],
        )
        self.assertIn('after_duplicate=1', response['Location'])
        rename_page = self.client.get(response['Location'])
        self.assertEqual(rename_page.status_code, 200)
        self.assertContains(rename_page, 'Rename duplicated template')
        self.assertContains(rename_page, 'Contract Review Copy 2')
