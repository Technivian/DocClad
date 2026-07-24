"""PAR-APR-002 characterization: preserve the current legacy/canonical boundary."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from contracts.models import (
    ApprovalDecision,
    ApprovalRequirement,
    ApprovalRequest,
    Contract,
    Organization,
    OrganizationMembership,
)
from contracts.services.approval_canonical import ApprovalCanonicalError, create_approval_requirement, record_approval_decision
from contracts.services.approval_workflow import ApprovalWorkflowService


User = get_user_model()


class ApprovalCutoverBaselineTests(TestCase):
    """Characterize current behaviour; these tests intentionally do not cut over reads."""

    def setUp(self):
        self.organization = Organization.objects.create(name='APR-002 Org', slug='apr-002-org')
        self.owner = User.objects.create_user(username='apr-002-owner', password='pass12345')
        self.reviewer = User.objects.create_user(username='apr-002-reviewer', password='pass12345')
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.owner,
            role=OrganizationMembership.Role.OWNER,
            is_active=True,
        )
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.reviewer,
            role=OrganizationMembership.Role.ADMIN,
            is_active=True,
        )
        self.contract = Contract.objects.create(
            organization=self.organization,
            title='APR-002 characterization contract',
            contract_type=Contract.ContractType.MSA,
            status=Contract.Status.IN_PROGRESS,
            lifecycle_stage=Contract.LifecycleStage.APPROVAL,
            owner=self.owner,
            created_by=self.owner,
        )

    def test_legacy_creation_retains_a_canonical_mirror(self):
        legacy = ApprovalRequest.objects.create(
            organization=self.organization,
            contract=self.contract,
            approval_step='LEGAL',
            status=ApprovalRequest.Status.PENDING,
            assigned_to=self.reviewer,
        )

        requirement = ApprovalRequirement.objects.get(legacy_request=legacy)

        self.assertEqual(requirement.status, ApprovalRequirement.Status.OPEN)
        self.assertEqual(requirement.approval_step, legacy.approval_step)
        self.assertEqual(requirement.assigned_to_id, legacy.assigned_to_id)
        self.assertEqual(legacy.status, ApprovalRequest.Status.PENDING)

    def test_workflow_decision_updates_legacy_and_canonical_records(self):
        legacy = ApprovalRequest.objects.create(
            organization=self.organization,
            contract=self.contract,
            approval_step='FINANCE',
            status=ApprovalRequest.Status.PENDING,
            assigned_to=self.reviewer,
        )

        ApprovalWorkflowService().approve(legacy.pk, self.reviewer, comments='characterization')

        legacy.refresh_from_db()
        requirement = ApprovalRequirement.objects.get(legacy_request=legacy)
        self.assertEqual(legacy.status, ApprovalRequest.Status.APPROVED)
        self.assertEqual(requirement.status, ApprovalRequirement.Status.SATISFIED)
        self.assertEqual(requirement.decisions.count(), 1)
        self.assertEqual(requirement.decisions.get().outcome, ApprovalDecision.Outcome.APPROVED)

    def test_abstain_and_direct_revoke_are_not_supported_actions(self):
        for action in ('abstain', 'revoke'):
            requirement = create_approval_requirement(
                organization=self.organization,
                contract=self.contract,
                approval_step=f'LEGAL-{action}',
                assigned_to=self.reviewer,
                actor=self.owner,
            )

            with self.assertRaises(ApprovalCanonicalError):
                record_approval_decision(requirement, action=action, actor=self.reviewer)
