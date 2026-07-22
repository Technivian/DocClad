"""PAR-CORE-001 — PDR-0002 remaining drift guards."""

from django.contrib.auth import get_user_model
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from contracts.models import AuditLog, Contract, Organization, OrganizationMembership
from contracts.services.contract_detail_workspace import build_lifecycle_command_label
from contracts.services.repository import BulkUpdateValidationError, get_repository_service


User = get_user_model()


class Pdr0002VocabularyGuardsTests(SimpleTestCase):
    def test_record_status_choices_exclude_draft(self):
        labels = {label for _, label in Contract.Status.choices}
        values = {value for value, _ in Contract.Status.choices}
        self.assertNotIn('Draft', labels)
        self.assertNotIn('DRAFT', values)
        self.assertEqual(
            values,
            {
                Contract.Status.IN_PROGRESS,
                Contract.Status.ACTIVE,
                Contract.Status.EXPIRED,
                Contract.Status.TERMINATED,
                Contract.Status.CANCELLED,
                Contract.Status.ARCHIVED,
            },
        )

    def test_command_label_is_status_dot_stage_only(self):
        class _C:
            status = Contract.Status.IN_PROGRESS
            lifecycle_stage = Contract.LifecycleStage.DRAFTING

            def get_status_display(self):
                return 'In progress'

            def get_lifecycle_stage_display(self):
                return 'Drafting'

        label, _ = build_lifecycle_command_label(_C(), has_documents=False)
        self.assertEqual(label, 'In progress · Drafting')
        self.assertNotIn('Intake incomplete', label)
        self.assertNotIn('Currently in', label)


class Pdr0002BulkAndJobOwnershipTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Core001 Org', slug='core001-org')
        self.user = User.objects.create_user(username='core001', password='pass12345')
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.user,
            role=OrganizationMembership.Role.OWNER,
            is_active=True,
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_bulk_rejects_legacy_draft_record_status(self):
        contract = Contract.objects.create(
            organization=self.org,
            title='Bulk Draft Reject',
            status=Contract.Status.IN_PROGRESS,
            lifecycle_stage=Contract.LifecycleStage.DRAFTING,
            created_by=self.user,
        )
        resp = self.client.post(
            reverse('contracts:contracts_bulk_update_api'),
            data='{"contract_ids": [%d], "updates": {"status": "DRAFT"}}' % contract.pk,
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
        contract.refresh_from_db()
        self.assertEqual(contract.status, Contract.Status.IN_PROGRESS)

    def test_bulk_stage_uses_lifecycle_service_audit(self):
        contract = Contract.objects.create(
            organization=self.org,
            title='Bulk Stage',
            status=Contract.Status.IN_PROGRESS,
            lifecycle_stage=Contract.LifecycleStage.DRAFTING,
            created_by=self.user,
        )
        service = get_repository_service(self.user)
        updated = service.bulk_update(
            [str(contract.pk)],
            {'lifecycle_stage': Contract.LifecycleStage.INTERNAL_REVIEW},
        )
        self.assertEqual(updated, 1)
        contract.refresh_from_db()
        self.assertEqual(contract.lifecycle_stage, Contract.LifecycleStage.INTERNAL_REVIEW)
        event = AuditLog.objects.filter(
            model_name='Contract',
            object_id=contract.pk,
            event_type='contract.lifecycle_stage_changed',
        ).first()
        self.assertIsNotNone(event)

    def test_bulk_illegal_stage_pair_rejected(self):
        contract = Contract.objects.create(
            organization=self.org,
            title='Illegal Stage',
            status=Contract.Status.IN_PROGRESS,
            lifecycle_stage=Contract.LifecycleStage.DRAFTING,
            created_by=self.user,
        )
        service = get_repository_service(self.user)
        with self.assertRaises(BulkUpdateValidationError):
            service.bulk_update(
                [str(contract.pk)],
                {'lifecycle_stage': Contract.LifecycleStage.OBLIGATION_TRACKING},
            )
