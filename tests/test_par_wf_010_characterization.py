"""PAR-WF-010 characterization tests — lock interim WorkflowTemplate semantics before cutover.

These tests document current behavior that MUST remain truthful during dual-read
and MUST be preserved or explicitly migrated during Definition/Version cutover.
No production schema changes; no cutover flags enabled.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from contracts.models import (
    Contract,
    Organization,
    OrganizationMembership,
    Workflow,
    WorkflowTemplate,
    WorkflowTemplateStep,
)
from contracts.services.contract_provenance import pin_workflow_provenance
from contracts.services.workflow_execution import materialize_workflow_from_template
from contracts.services.workflow_templates import list_template_versions


User = get_user_model()


class WorkflowTemplateInterimCharacterizationTests(TestCase):
    """Baseline semantics while WorkflowTemplate row = interim Workflow Version."""

    def setUp(self):
        self.user = User.objects.create_user(username='wf-char-user', password='pass12345')
        self.org = Organization.objects.create(name='WF Char Org', slug='wf-char-org')
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.user,
            role=OrganizationMembership.Role.OWNER,
            is_active=True,
        )
        self.v1 = WorkflowTemplate.objects.create(
            name='Char Workflow',
            description='v1',
            organization=self.org,
            category=WorkflowTemplate.Category.GENERAL,
            version=1,
            is_active=True,
        )
        WorkflowTemplateStep.objects.create(
            template=self.v1,
            name='Review',
            order=1,
            step_kind=WorkflowTemplateStep.StepKind.TASK,
        )
        self.v2 = WorkflowTemplate.objects.create(
            name='Char Workflow',
            description='v2',
            organization=self.org,
            category=WorkflowTemplate.Category.GENERAL,
            version=2,
            parent_template=self.v1,
            is_active=False,
        )
        WorkflowTemplateStep.objects.create(
            template=self.v2,
            name='Review v2',
            order=1,
            step_kind=WorkflowTemplateStep.StepKind.TASK,
        )

    def test_template_family_lineage_groups_by_name_category_org(self):
        versions = list_template_versions(self.v2)
        self.assertEqual(len(versions), 2)
        self.assertEqual({v.pk for v in versions}, {self.v1.pk, self.v2.pk})

    def test_workflow_instance_pins_specific_template_row_version(self):
        contract = Contract.objects.create(
            organization=self.org,
            title='Char Contract',
            contract_type=Contract.ContractType.MSA,
            status=Contract.Status.IN_PROGRESS,
            lifecycle_stage=Contract.LifecycleStage.DRAFTING,
            created_by=self.user,
        )
        workflow = Workflow.objects.create(
            organization=self.org,
            title='Char Instance',
            template=self.v1,
            contract=contract,
            created_by=self.user,
        )
        materialize_workflow_from_template(workflow)
        step = workflow.steps.get()
        self.assertEqual(workflow.template_id, self.v1.pk)
        self.assertEqual(step.template_step.template_id, self.v1.pk)
        self.assertEqual(step.name, 'Review')

    def test_contract_provenance_pins_template_id_and_version_number(self):
        contract = Contract.objects.create(
            organization=self.org,
            title='Prov Contract',
            contract_type=Contract.ContractType.MSA,
            status=Contract.Status.IN_PROGRESS,
            lifecycle_stage=Contract.LifecycleStage.DRAFTING,
            created_by=self.user,
        )
        workflow = Workflow.objects.create(
            organization=self.org,
            title='Prov Instance',
            template=self.v1,
            contract=contract,
            created_by=self.user,
        )
        pin_workflow_provenance(contract, workflow, actor=self.user, channel='characterization_test')
        contract.refresh_from_db()
        self.assertEqual(contract.origin_workflow_id, workflow.pk)
        self.assertEqual(contract.origin_workflow_template_id, self.v1.pk)
        self.assertEqual(contract.origin_workflow_template_version, 1)

    def test_materialized_steps_reference_pinned_version_not_latest_draft(self):
        """Instance launched on v1 must not pick up v2 step definitions."""
        contract = Contract.objects.create(
            organization=self.org,
            title='Pin Contract',
            contract_type=Contract.ContractType.MSA,
            status=Contract.Status.IN_PROGRESS,
            lifecycle_stage=Contract.LifecycleStage.DRAFTING,
            created_by=self.user,
        )
        workflow = Workflow.objects.create(
            organization=self.org,
            title='Pin Instance',
            template=self.v1,
            contract=contract,
            created_by=self.user,
        )
        materialize_workflow_from_template(workflow)
        self.assertEqual(workflow.steps.get().name, 'Review')
        self.assertNotEqual(workflow.steps.get().name, 'Review v2')
