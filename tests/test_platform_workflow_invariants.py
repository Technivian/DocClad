"""Platform workflow invariant tests (ENGINEERING_GUARDRAILS §16 subset)."""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from contracts.models import (
    AuditLog,
    Organization,
    OrganizationMembership,
    UserProfile,
    Workflow,
    WorkflowTemplate,
    WorkflowTemplateStep,
)
from contracts.services.workflow_designer import can_mutate_workflow_template, validate_template_for_publish
from contracts.services.workflow_simulation import simulate_workflow_template
from contracts.services.workflow_templates import migrate_workflows_to_template


User = get_user_model()


class PlatformWorkflowInvariantTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='inv-user', password='pass12345')
        self.org = Organization.objects.create(name='Invariant Org', slug='invariant-org')
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.user,
            role=OrganizationMembership.Role.OWNER,
            is_active=True,
        )
        self.template = WorkflowTemplate.objects.create(
            name='Invariant Review',
            description='Invariant test template',
            organization=self.org,
            category=WorkflowTemplate.Category.GENERAL,
            version=1,
            is_active=True,
        )
        WorkflowTemplateStep.objects.create(
            template=self.template,
            name='Legal approval',
            order=1,
            step_kind=WorkflowTemplateStep.StepKind.APPROVAL,
            assignee_role=UserProfile.Role.ADMIN,
            sla_hours=24,
        )

    def test_new_template_defaults_unpublished(self):
        draft = WorkflowTemplate.objects.create(
            name='Fresh Draft',
            description='Should default unpublished',
            organization=self.org,
            category=WorkflowTemplate.Category.GENERAL,
        )
        self.assertFalse(draft.is_active)

    def test_published_template_is_not_mutable(self):
        self.assertFalse(can_mutate_workflow_template(self.user, self.org, self.template))

    def test_update_view_blocks_published_template(self):
        self.client.force_login(self.user)
        url = reverse('contracts:workflow_template_update', args=[self.template.pk])
        response = self.client.post(url, {
            'name': 'Hacked Published Name',
            'description': self.template.description,
            'category': self.template.category,
        })
        self.assertEqual(response.status_code, 302)
        self.template.refresh_from_db()
        self.assertEqual(self.template.name, 'Invariant Review')
        self.assertIn(
            reverse('contracts:workflow_template_detail', args=[self.template.pk]),
            response['Location'],
        )

    def test_simulation_does_not_create_live_workflows(self):
        before = Workflow.objects.count()
        result = simulate_workflow_template(self.template, {})
        self.assertIsNotNone(result)
        self.assertEqual(Workflow.objects.count(), before)

    def test_migration_requires_reason_and_writes_audit(self):
        target = WorkflowTemplate.objects.create(
            name='Invariant Review v2',
            description='Target',
            organization=self.org,
            category=WorkflowTemplate.Category.GENERAL,
            version=2,
            parent_template=self.template,
            is_active=False,
        )
        workflow = Workflow.objects.create(
            organization=self.org,
            title='Pinned instance',
            template=self.template,
            status=Workflow.Status.ACTIVE,
            created_by=self.user,
        )
        with self.assertRaises(ValidationError):
            migrate_workflows_to_template(self.template, target)
        before_logs = AuditLog.objects.count()
        result = migrate_workflows_to_template(
            self.template,
            target,
            workflows=[workflow],
            actor=self.user,
            reason='Governed cutover for invariant test',
        )
        self.assertEqual(result.migrated_workflow_count, 1)
        workflow.refresh_from_db()
        self.assertEqual(workflow.template_id, target.pk)
        self.assertGreater(AuditLog.objects.count(), before_logs)
        self.assertTrue(
            AuditLog.objects.filter(changes__event='workflow_instance_template_migrated').exists()
        )

    def test_publish_blocked_when_validation_fails(self):
        broken = WorkflowTemplate.objects.create(
            name='Broken Publish',
            description='Missing assignees',
            organization=self.org,
            category=WorkflowTemplate.Category.GENERAL,
            is_active=False,
        )
        WorkflowTemplateStep.objects.create(
            template=broken,
            name='Unsigned approval',
            order=1,
            step_kind=WorkflowTemplateStep.StepKind.APPROVAL,
        )
        validation = validate_template_for_publish(broken)
        self.assertFalse(validation.ok)
