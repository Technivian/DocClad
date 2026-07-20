"""Coverage for the three-dimension contract lifecycle vocabulary."""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from contracts.domain.contracts import ListParams
from contracts.models import Contract, Document, Organization, OrganizationMembership
from contracts.services.contract_lifecycle import activate_contract
from contracts.services.lifecycle_dimensions import (
    RECORD_STATUS_ACTIVE,
    RECORD_STATUS_ARCHIVED,
    RECORD_STATUS_IN_PROGRESS,
    STAGE_APPROVAL,
    STAGE_DRAFTING,
    STAGE_EXECUTED,
    STAGE_INTAKE,
    STAGE_INTERNAL_REVIEW,
    STAGE_OBLIGATION_TRACKING,
    STAGE_SIGNATURE,
    WORKFLOW_STAGES,
    is_valid_document_state_for_contract,
    is_valid_status_stage_pair,
    map_legacy_document_status,
    map_legacy_stage,
    map_legacy_status_to_record,
    validate_document_state_for_contract,
    validate_status_stage_pair,
)
from contracts.services.repository import get_repository_service


User = get_user_model()


class StatusStagePairMatrixTests(SimpleTestCase):
    def test_valid_and_invalid_status_stage_pairs(self):
        valid = [
            (RECORD_STATUS_IN_PROGRESS, STAGE_INTAKE),
            (RECORD_STATUS_IN_PROGRESS, STAGE_DRAFTING),
            (RECORD_STATUS_IN_PROGRESS, STAGE_INTERNAL_REVIEW),
            (RECORD_STATUS_IN_PROGRESS, STAGE_APPROVAL),
            (RECORD_STATUS_IN_PROGRESS, STAGE_SIGNATURE),
            (RECORD_STATUS_IN_PROGRESS, STAGE_EXECUTED),
            (RECORD_STATUS_ACTIVE, STAGE_EXECUTED),
            (RECORD_STATUS_ACTIVE, STAGE_OBLIGATION_TRACKING),
            (RECORD_STATUS_ARCHIVED, STAGE_OBLIGATION_TRACKING),
            (RECORD_STATUS_ARCHIVED, STAGE_DRAFTING),
        ]
        invalid = [
            (RECORD_STATUS_IN_PROGRESS, STAGE_OBLIGATION_TRACKING),
            (RECORD_STATUS_ACTIVE, STAGE_DRAFTING),
            (RECORD_STATUS_ACTIVE, STAGE_APPROVAL),
            (RECORD_STATUS_ACTIVE, STAGE_INTAKE),
            ('DRAFT', STAGE_DRAFTING),
            (RECORD_STATUS_IN_PROGRESS, 'ARCHIVED'),
        ]
        for status, stage in valid:
            with self.subTest(status=status, stage=stage, expected=True):
                self.assertTrue(is_valid_status_stage_pair(status, stage))
                validate_status_stage_pair(status, stage)
        for status, stage in invalid:
            with self.subTest(status=status, stage=stage, expected=False):
                self.assertFalse(is_valid_status_stage_pair(status, stage))
                with self.assertRaises(ValidationError):
                    validate_status_stage_pair(status, stage)

    def test_all_workflow_stages_are_known(self):
        self.assertEqual(
            WORKFLOW_STAGES,
            frozenset(value for value, _ in Contract.LifecycleStage.choices),
        )


class DocumentExecutedValidationTests(SimpleTestCase):
    def test_executed_document_allowed_only_after_activation_or_executed_stage(self):
        self.assertTrue(
            is_valid_document_state_for_contract(
                'EXECUTED',
                contract_status=RECORD_STATUS_ACTIVE,
                contract_stage=STAGE_OBLIGATION_TRACKING,
            )
        )
        self.assertTrue(
            is_valid_document_state_for_contract(
                'EXECUTED',
                contract_status=RECORD_STATUS_IN_PROGRESS,
                contract_stage=STAGE_EXECUTED,
            )
        )
        self.assertFalse(
            is_valid_document_state_for_contract(
                'EXECUTED',
                contract_status=RECORD_STATUS_IN_PROGRESS,
                contract_stage=STAGE_DRAFTING,
            )
        )
        with self.assertRaises(ValidationError):
            validate_document_state_for_contract(
                'EXECUTED',
                contract_status=RECORD_STATUS_IN_PROGRESS,
                contract_stage=STAGE_SIGNATURE,
            )
        for state in ('DRAFT', 'FINAL', 'SUPERSEDED'):
            self.assertTrue(
                is_valid_document_state_for_contract(
                    state,
                    contract_status=RECORD_STATUS_IN_PROGRESS,
                    contract_stage=STAGE_DRAFTING,
                )
            )


class ActivateContractTriadTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Activate Org', slug='activate-org')
        self.user = User.objects.create_user(username='activate-user', password='testpass123')
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.user,
            role=OrganizationMembership.Role.OWNER,
            is_active=True,
        )
        self.contract = Contract.objects.create(
            organization=self.org,
            title='Activation Contract',
            status=Contract.Status.IN_PROGRESS,
            lifecycle_stage=Contract.LifecycleStage.SIGNATURE,
            created_by=self.user,
        )
        self.document = Document.objects.create(
            organization=self.org,
            contract=self.contract,
            title='Primary agreement',
            document_type=Document.DocType.CONTRACT,
            status=Document.Status.FINAL,
            uploaded_by=self.user,
        )

    def test_activate_contract_sets_active_obligation_tracking_and_executed_doc(self):
        activate_contract(self.contract, actor=None, system=True)
        self.contract.refresh_from_db()
        self.document.refresh_from_db()
        self.assertEqual(self.contract.status, Contract.Status.ACTIVE)
        self.assertEqual(self.contract.lifecycle_stage, Contract.LifecycleStage.OBLIGATION_TRACKING)
        self.assertEqual(self.document.status, Document.Status.EXECUTED)


class LegacyMigrationMappingTests(SimpleTestCase):
    def test_map_legacy_status_to_record_samples(self):
        samples = {
            'DRAFT': RECORD_STATUS_IN_PROGRESS,
            'PENDING': RECORD_STATUS_IN_PROGRESS,
            'IN_REVIEW': RECORD_STATUS_IN_PROGRESS,
            'APPROVED': RECORD_STATUS_IN_PROGRESS,
            'AI_REVIEW_READY': RECORD_STATUS_IN_PROGRESS,
            'INTERNAL_APPROVAL_REQUIRED': RECORD_STATUS_IN_PROGRESS,
            'EXECUTED': RECORD_STATUS_IN_PROGRESS,
            'OBLIGATIONS_ACTIVE': RECORD_STATUS_ACTIVE,
            'COMPLETED': RECORD_STATUS_ACTIVE,
            'ACTIVE': RECORD_STATUS_ACTIVE,
            'CANCELLED': 'CANCELLED',
            'EXPIRED': 'EXPIRED',
        }
        for legacy, expected in samples.items():
            with self.subTest(legacy=legacy):
                self.assertEqual(map_legacy_status_to_record(legacy), expected)
        self.assertEqual(
            map_legacy_status_to_record('ACTIVE', lifecycle_stage='ARCHIVED'),
            RECORD_STATUS_ARCHIVED,
        )

    def test_map_legacy_stage_samples(self):
        self.assertEqual(map_legacy_stage('ARCHIVED'), STAGE_OBLIGATION_TRACKING)
        self.assertEqual(map_legacy_stage('DRAFTING'), STAGE_DRAFTING)
        self.assertEqual(map_legacy_stage(None), STAGE_DRAFTING)
        self.assertEqual(map_legacy_stage('UNKNOWN_STAGE'), STAGE_DRAFTING)

    def test_map_legacy_document_status_samples(self):
        self.assertEqual(map_legacy_document_status('REVIEW'), 'DRAFT')
        self.assertEqual(map_legacy_document_status('APPROVED'), 'FINAL')
        self.assertEqual(map_legacy_document_status('ARCHIVED'), 'SUPERSEDED')
        self.assertEqual(map_legacy_document_status('EXECUTED'), 'EXECUTED')
        self.assertEqual(map_legacy_document_status(None), 'DRAFT')


class LabelAndCompactHeaderGuardTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Label Org', slug='label-org')
        self.user = User.objects.create_user(username='label-user', password='testpass123')
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.user,
            role=OrganizationMembership.Role.MEMBER,
            is_active=True,
        )
        self.client.login(username='label-user', password='testpass123')

    def test_contract_status_labels_exclude_draft_and_stage_is_drafting(self):
        status_labels = {label for _, label in Contract.Status.choices}
        self.assertNotIn('Draft', status_labels)
        self.assertIn('In progress', status_labels)
        self.assertEqual(Contract.LifecycleStage.DRAFTING.label, 'Drafting')

    def test_compact_header_uses_status_display_dot_stage_display(self):
        contract = Contract.objects.create(
            organization=self.org,
            title='Header Contract',
            status=Contract.Status.IN_PROGRESS,
            lifecycle_stage=Contract.LifecycleStage.DRAFTING,
            created_by=self.user,
        )
        response = self.client.get(reverse('contracts:contract_detail', args=[contract.pk]))
        self.assertEqual(response.status_code, 200)
        expected = f'{contract.get_status_display()} · {contract.get_lifecycle_stage_display()}'
        self.assertContains(response, expected)
        self.assertContains(response, 'In progress · Drafting')


class RepositoryLifecycleStageFilterTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Repo Org', slug='repo-lifecycle-org')
        self.user = User.objects.create_user(username='repo-lifecycle-user', password='testpass123')
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.user,
            role=OrganizationMembership.Role.OWNER,
            is_active=True,
        )
        self.drafting = Contract.objects.create(
            organization=self.org,
            title='Drafting Contract',
            status=Contract.Status.IN_PROGRESS,
            lifecycle_stage=Contract.LifecycleStage.DRAFTING,
            created_by=self.user,
        )
        self.approval = Contract.objects.create(
            organization=self.org,
            title='Approval Contract',
            status=Contract.Status.IN_PROGRESS,
            lifecycle_stage=Contract.LifecycleStage.APPROVAL,
            created_by=self.user,
        )
        self.service = get_repository_service(self.user)

    def test_list_params_filters_lifecycle_stage(self):
        result = self.service.list(ListParams(lifecycle_stage=[Contract.LifecycleStage.APPROVAL]))
        ids = {row.id for row in result.contracts}
        self.assertIn(str(self.approval.pk), ids)
        self.assertNotIn(str(self.drafting.pk), ids)
        self.assertEqual(result.total_count, 1)
