"""PAR-APR-002 evidence-only inventory of the DPA approval boundary.

These tests characterize the current model and query boundary.  They must not
be read as a DPA-to-approval mapper or as a read-authority change.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from contracts.models import (
    ApprovalRequest,
    ApprovalRequirement,
    Contract,
    DPAReviewPack,
    Organization,
    OrganizationMembership,
)


User = get_user_model()


def _unlinked_inventory_for_organization(organization):
    """Return evidence counts without inferring a relationship from a contract.

    A common organization, contract, reviewer, or status is not a durable DPA
    to approval linkage.  The production model currently stores no such link,
    so all rows are retained as unlinked evidence.
    """
    dpa_packs = DPAReviewPack.objects.filter(organization=organization)
    approvals = ApprovalRequest.objects.filter(organization=organization)
    return {
        'valid_links': 0,
        'mismatch_counts': {
            'DPA_ONLY': dpa_packs.count(),
            'GENERIC_ONLY': approvals.count(),
            'UNMAPPABLE_STATUS': dpa_packs.count(),
            'STATUS_DIVERGENCE': 0,
            'ACTOR_OR_TIME_DIVERGENCE': 0,
            'CONTRACT_OR_VERSION_DIVERGENCE': 0,
            'TENANT_OR_AUTHORIZATION_VIOLATION': 0,
            'DUPLICATE_OR_AMBIGUOUS_LINKAGE': 0,
        },
    }


class DPAApprovalInventoryTests(TestCase):
    """Evidence for the currently separate DPA and generic approval domains."""

    def setUp(self):
        self.organization = Organization.objects.create(name='APR DPA inventory', slug='apr-dpa-inventory')
        self.reviewer = User.objects.create_user(username='apr-dpa-reviewer', password='pass12345')
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.reviewer,
            role=OrganizationMembership.Role.ADMIN,
            is_active=True,
        )
        self.contract = Contract.objects.create(
            organization=self.organization,
            title='DPA inventory contract',
            contract_type=Contract.ContractType.DPA,
            status=Contract.Status.IN_PROGRESS,
            lifecycle_stage=Contract.LifecycleStage.APPROVAL,
            created_by=self.reviewer,
        )
        self.pack = DPAReviewPack.objects.create(
            organization=self.organization,
            contract=self.contract,
            reviewer=self.reviewer,
            created_by=self.reviewer,
        )
        self.legacy = ApprovalRequest.objects.create(
            organization=self.organization,
            contract=self.contract,
            approval_step='PRIVACY',
            status=ApprovalRequest.Status.PENDING,
            assigned_to=self.reviewer,
        )

    def test_same_contract_is_not_a_valid_dpa_to_approval_link(self):
        field_names = {field.name for field in DPAReviewPack._meta.get_fields()}

        self.assertNotIn('approval_request', field_names)
        self.assertNotIn('approval_requirement', field_names)
        self.assertEqual(ApprovalRequirement.objects.filter(legacy_request=self.legacy).count(), 1)
        self.assertEqual(_unlinked_inventory_for_organization(self.organization)['valid_links'], 0)

    def test_inventory_reports_unlinked_fixture_counts_without_data_repair(self):
        counts = _unlinked_inventory_for_organization(self.organization)['mismatch_counts']

        self.assertEqual(counts['DPA_ONLY'], 1)
        self.assertEqual(counts['GENERIC_ONLY'], 1)
        self.assertEqual(counts['UNMAPPABLE_STATUS'], 1)
        self.assertEqual(sum(value for key, value in counts.items() if key.endswith('VIOLATION')), 0)

    def test_all_dpa_statuses_are_unmappable_without_a_governed_linkage(self):
        dpa_statuses = {choice for choice, _ in DPAReviewPack.ApprovalStatus.choices}
        legacy_statuses = {choice for choice, _ in ApprovalRequest.Status.choices}

        self.assertEqual(dpa_statuses, {'DRAFT', 'UNDER_REVIEW', 'ESCALATED', 'APPROVED', 'REJECTED'})
        self.assertIn('PENDING', legacy_statuses)
        self.assertNotIn('DRAFT', legacy_statuses)
        self.assertNotIn('UNDER_REVIEW', legacy_statuses)
        self.assertEqual(_unlinked_inventory_for_organization(self.organization)['mismatch_counts']['UNMAPPABLE_STATUS'], 1)

    def test_generic_approval_activity_does_not_change_human_controlled_dpa_status(self):
        self.legacy.status = ApprovalRequest.Status.APPROVED
        self.legacy.save(update_fields=['status'])

        self.pack.refresh_from_db()
        self.assertEqual(self.pack.approval_status, DPAReviewPack.ApprovalStatus.DRAFT)

    def test_inventory_is_organization_scoped(self):
        other_org = Organization.objects.create(name='Other APR DPA inventory', slug='other-apr-dpa-inventory')
        other_user = User.objects.create_user(username='other-apr-dpa-reviewer', password='pass12345')
        other_contract = Contract.objects.create(
            organization=other_org,
            title='Other DPA inventory contract',
            contract_type=Contract.ContractType.DPA,
            status=Contract.Status.IN_PROGRESS,
            lifecycle_stage=Contract.LifecycleStage.APPROVAL,
            created_by=other_user,
        )
        DPAReviewPack.objects.create(organization=other_org, contract=other_contract, created_by=other_user)
        ApprovalRequest.objects.create(
            organization=other_org,
            contract=other_contract,
            approval_step='PRIVACY',
            assigned_to=other_user,
        )

        counts = _unlinked_inventory_for_organization(self.organization)['mismatch_counts']
        self.assertEqual(counts['DPA_ONLY'], 1)
        self.assertEqual(counts['GENERIC_ONLY'], 1)
