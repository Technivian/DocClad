"""PAR-APR-002 ApprovalRoute reconciliation characterization.

These tests record the current boundary only.  They must not make an
ApprovalRoute authoritative or change the legacy ApprovalRequest read path.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from contracts.models import (
    ApprovalRequest,
    ApprovalRequirement,
    ApprovalRoute,
    ApprovalRule,
    Contract,
    Organization,
    OrganizationMembership,
    WorkflowTemplate,
)
from contracts.services.approval_workflow import ApprovalWorkflowService
from contracts.services.workflow_routing import build_approval_request_plan_for_contract


User = get_user_model()


class ApprovalRouteReconciliationInventoryTests(TestCase):
    """Characterize configuration ownership, missing linkage, and tenant scope."""

    def setUp(self):
        self.organization = Organization.objects.create(name='Route Org', slug='apr-route-org')
        self.foreign_organization = Organization.objects.create(
            name='Foreign Route Org', slug='apr-route-foreign-org',
        )
        self.owner = User.objects.create_user(username='apr-route-owner', password='pass12345')
        self.foreign_owner = User.objects.create_user(
            username='apr-route-foreign-owner', password='pass12345',
        )
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.owner,
            role=OrganizationMembership.Role.OWNER,
            is_active=True,
        )
        OrganizationMembership.objects.create(
            organization=self.foreign_organization,
            user=self.foreign_owner,
            role=OrganizationMembership.Role.OWNER,
            is_active=True,
        )
        self.template = WorkflowTemplate.objects.create(
            organization=self.organization,
            name='Route inventory template',
            description='Characterization fixture',
            is_active=True,
            created_by=self.owner,
        )
        self.foreign_template = WorkflowTemplate.objects.create(
            organization=self.foreign_organization,
            name='Foreign route inventory template',
            description='Foreign characterization fixture',
            is_active=True,
            created_by=self.foreign_owner,
        )
        self.route = ApprovalRoute.objects.create(
            workflow_template=self.template,
            name='LEGAL',
            order=1,
            role_label='Legal reviewer',
        )
        ApprovalRoute.objects.create(
            workflow_template=self.foreign_template,
            name='FOREIGN_LEGAL',
            order=1,
            role_label='Foreign legal reviewer',
        )
        self.contract = Contract.objects.create(
            organization=self.organization,
            title='Route characterization contract',
            contract_type=Contract.ContractType.MSA,
            status=Contract.Status.IN_PROGRESS,
            lifecycle_stage=Contract.LifecycleStage.APPROVAL,
            owner=self.owner,
            created_by=self.owner,
        )

    def test_routes_are_template_configuration_not_runtime_requirement_inputs(self):
        """A configured route neither creates nor keys a runtime requirement."""
        self.assertEqual(build_approval_request_plan_for_contract(self.contract), [])
        self.assertFalse(ApprovalRequirement.objects.filter(contract=self.contract).exists())

        rule = ApprovalRule.objects.create(
            organization=self.organization,
            name='MSA legal rule',
            trigger_type=ApprovalRule.TriggerType.CONTRACT_TYPE,
            trigger_value=Contract.ContractType.MSA,
            approval_step='LEGAL',
            specific_approver=self.owner,
            sla_hours=24,
            order=1,
        )
        plan = build_approval_request_plan_for_contract(self.contract)
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]['rule'], rule)
        self.assertNotIn('approval_route', plan[0])

        ApprovalWorkflowService().initiate_approval_workflow(self.contract, actor=self.owner)
        legacy = ApprovalRequest.objects.get(contract=self.contract, rule=rule)
        requirement = ApprovalRequirement.objects.get(legacy_request=legacy)
        self.assertEqual(requirement.authority_basis, ApprovalRequirement.AuthorityBasis.RULE)
        self.assertEqual(requirement.authority_reference, {'rule_id': rule.pk})
        self.assertNotIn('approval_route', requirement.authority_reference)

    def test_route_schema_allows_duplicate_order_and_has_no_direct_tenant_or_requirement_key(self):
        """Duplicate and ambiguous route categories remain unreconciled facts."""
        ApprovalRoute.objects.create(
            workflow_template=self.template,
            name='LEGAL-SECONDARY',
            order=self.route.order,
            role_label='Secondary legal reviewer',
        )

        self.assertEqual(
            ApprovalRoute.objects.filter(workflow_template=self.template, order=self.route.order).count(),
            2,
        )
        route_field_names = {field.name for field in ApprovalRoute._meta.fields}
        requirement_field_names = {field.name for field in ApprovalRequirement._meta.fields}
        self.assertNotIn('organization', route_field_names)
        self.assertNotIn('approval_requirement', route_field_names)
        self.assertNotIn('approval_route', requirement_field_names)

    def test_route_list_is_scoped_through_template_organization_and_requires_login(self):
        """The current UI avoids cross-tenant route disclosure via its template query."""
        route_list_url = reverse('contracts:workflow_approval_route_list')
        unauthenticated = self.client.get(route_list_url)
        self.assertEqual(unauthenticated.status_code, 302)

        self.client.login(username='apr-route-owner', password='pass12345')
        response = self.client.get(route_list_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'LEGAL')
        self.assertNotContains(response, 'FOREIGN_LEGAL')
