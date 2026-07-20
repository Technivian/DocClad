from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from contracts.models import AuditLog, Contract, Organization, OrganizationMembership, UserProfile, Workflow, WorkflowStep, WorkflowTemplate, WorkflowTemplateStep
from contracts.services.workflow_audit import log_workflow_created, log_workflow_template_step_added


User = get_user_model()


class WorkflowAuditTrailTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='audit-user', password='testpass123')
        self.org = Organization.objects.create(name='Audit Org', slug='audit-org')
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.user,
            role=OrganizationMembership.Role.OWNER,
            is_active=True,
        )
        UserProfile.objects.get_or_create(user=self.user, defaults={'role': UserProfile.Role.ADMIN})

        self.contract = Contract.objects.create(
            organization=self.org,
            title='Audit Contract',
            contract_type=Contract.ContractType.MSA,
            status=Contract.Status.IN_PROGRESS,
            created_by=self.user,
        )
        self.template = WorkflowTemplate.objects.create(
            name='Audit Template',
            description='Template for audit tests',
            organization=self.org,
            category=WorkflowTemplate.Category.CONTRACT_REVIEW,
            version=1,
            is_active=True,
        )
        self.template_step = WorkflowTemplateStep.objects.create(
            template=self.template,
            name='Template Intake',
            description='Initial step',
            order=1,
        )
        WorkflowTemplateStep.objects.create(
            template=self.template,
            name='Template Review',
            description='Second step',
            order=2,
        )
        self.workflow = Workflow.objects.create(
            organization=self.org,
            title='Audit Workflow',
            description='Workflow for audit tests',
            contract=self.contract,
            template=self.template,
            created_by=self.user,
        )
        self.workflow_step = WorkflowStep.objects.create(
            workflow=self.workflow,
            name='Workflow Review',
            description='Review work',
            status=WorkflowStep.Status.PENDING,
            order=1,
        )

    def test_workflow_created_writes_audit_log(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('contracts:workflow_create'),
            data={
                'title': 'Fresh Workflow',
                'description': 'Created from the form',
                'contract': self.contract.pk,
                'template': self.template.pk,
            },
        )
        self.assertEqual(response.status_code, 302)
        workflow = Workflow.objects.get(title='Fresh Workflow')
        log = AuditLog.objects.get(model_name='Workflow', object_id=workflow.pk, action=AuditLog.Action.CREATE)
        self.assertEqual(log.changes['event'], 'workflow_created')

    def test_workflow_step_completed_writes_audit_log(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('contracts:workflow_step_complete', args=[self.workflow_step.pk]))
        self.assertEqual(response.status_code, 302)
        log = AuditLog.objects.get(model_name='WorkflowStep', object_id=self.workflow_step.pk, action=AuditLog.Action.UPDATE)
        self.assertEqual(log.changes['event'], 'workflow_step_completed')

    def test_workflow_step_updated_writes_audit_log(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('contracts:update_workflow_step', args=[self.workflow_step.pk]),
            data={'status': WorkflowStep.Status.PENDING, 'description': 'Updated review notes'},
        )
        self.assertEqual(response.status_code, 302)
        log = AuditLog.objects.get(model_name='WorkflowStep', object_id=self.workflow_step.pk, action=AuditLog.Action.UPDATE)
        self.assertEqual(log.changes['event'], 'workflow_step_updated')

    def test_template_cloned_writes_audit_log(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('contracts:workflow_template_clone_version', args=[self.template.pk]))
        self.assertEqual(response.status_code, 302)
        log = AuditLog.objects.get(model_name='WorkflowTemplate', action=AuditLog.Action.CREATE, changes__event='workflow_template_cloned')
        self.assertEqual(log.changes['source_template_id'], self.template.pk)

    def test_template_updated_writes_audit_log(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('contracts:workflow_template_update', args=[self.template.pk]),
            data={
                'name': 'Audit Template Updated',
                'description': 'Updated template description',
                'category': WorkflowTemplate.Category.COMPLIANCE,
            },
        )
        self.assertEqual(response.status_code, 302)
        log = AuditLog.objects.get(model_name='WorkflowTemplate', action=AuditLog.Action.UPDATE, changes__event='workflow_template_updated')
        self.assertEqual(log.changes['template_id'], self.template.pk)

    def test_template_restored_writes_audit_log(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('contracts:workflow_template_restore_version', args=[self.template.pk]))
        self.assertEqual(response.status_code, 302)
        log = AuditLog.objects.get(model_name='WorkflowTemplate', action=AuditLog.Action.CREATE, changes__event='workflow_template_restored')
        self.assertEqual(log.changes['restored_from_template_id'], self.template.pk)

    def test_template_step_added_writes_audit_log(self):
        self.client.force_login(self.user)
        self.template.is_active = False
        self.template.save(update_fields=['is_active'])
        response = self.client.post(
            reverse('contracts:workflow_template_step_add', args=[self.template.pk]),
            data={
                'name': 'Added Step',
                'description': 'Added through UI',
                'step_kind': WorkflowTemplateStep.StepKind.TASK,
                'assignment_mode': 'role',
            },
        )
        self.assertEqual(response.status_code, 302)
        log = AuditLog.objects.get(model_name='WorkflowTemplateStep', action=AuditLog.Action.CREATE, changes__event='workflow_template_step_added')
        self.assertEqual(log.changes['template_id'], self.template.pk)

    def test_template_step_deleted_writes_audit_log(self):
        self.client.force_login(self.user)
        self.template.is_active = False
        self.template.save(update_fields=['is_active'])
        response = self.client.post(reverse('contracts:workflow_template_step_delete', args=[self.template.pk, self.template_step.pk]))
        self.assertEqual(response.status_code, 302)
        log = AuditLog.objects.get(model_name='WorkflowTemplateStep', action=AuditLog.Action.DELETE, changes__event='workflow_template_step_deleted')
        self.assertEqual(log.changes['template_id'], self.template.pk)

    def test_template_reordered_writes_audit_log(self):
        self.client.force_login(self.user)
        self.template.is_active = False
        self.template.save(update_fields=['is_active'])
        step_ids = list(self.template.steps.order_by('order').values_list('pk', flat=True))
        response = self.client.post(
            reverse('contracts:workflow_template_step_reorder', args=[self.template.pk]),
            data={'step_ids': [step_ids[1], step_ids[0]]},
        )
        self.assertEqual(response.status_code, 302)
        log = AuditLog.objects.get(model_name='WorkflowTemplate', action=AuditLog.Action.UPDATE, changes__event='workflow_template_reordered')
        self.assertEqual(log.changes['template_id'], self.template.pk)

    def test_publish_unpublish_writes_audit_log(self):
        self.client.force_login(self.user)
        before_count = AuditLog.objects.filter(
            model_name='WorkflowTemplate',
            action=AuditLog.Action.UPDATE,
            changes__event='workflow_template_publish_toggled',
        ).count()

        response = self.client.post(reverse('contracts:workflow_template_publish_toggle', args=[self.template.pk]))
        self.assertEqual(response.status_code, 302)
        self.template.refresh_from_db()
        self.assertFalse(self.template.is_active)

        response = self.client.post(reverse('contracts:workflow_template_publish_toggle', args=[self.template.pk]))
        self.assertEqual(response.status_code, 302)
        self.template.refresh_from_db()
        self.assertTrue(self.template.is_active)

        after_count = AuditLog.objects.filter(
            model_name='WorkflowTemplate',
            action=AuditLog.Action.UPDATE,
            changes__event='workflow_template_publish_toggled',
        ).count()
        self.assertEqual(after_count - before_count, 2)

    def test_workflow_detail_renders_audit_panel(self):
        self.client.force_login(self.user)
        log_workflow_created(self.workflow, self.user, request=None)
        response = self.client.get(reverse('contracts:workflow_detail', args=[self.workflow.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Activity History')
        self.assertContains(response, 'Workflow created')

    def test_template_detail_renders_audit_panel(self):
        self.client.force_login(self.user)
        log_workflow_template_step_added(self.template_step, self.user, request=None)
        response = self.client.get(
            reverse('contracts:workflow_template_detail', args=[self.template.pk]) + '?tab=activity'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['active_tab'], 'activity')
        self.assertContains(response, 'Activity')
        self.assertContains(response, 'Create')
        self.assertNotContains(response, 'View all activity')
