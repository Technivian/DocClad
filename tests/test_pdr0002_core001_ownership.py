"""PAR-CORE-001 remaining ownership: imports, supersession audit, Model.save."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from contracts.models import AuditLog, Contract, Document, Organization, OrganizationMembership
from contracts.services.contract_import_lifecycle import (
    ImportLifecycleError,
    persist_contract_with_imported_lifecycle,
    resolve_import_status_stage,
)
from contracts.services.document_supersession import supersede_document
from contracts.services.inbound_import import InboundImportService
from contracts.services.netsuite import upsert_contract_from_netsuite
from contracts.services.salesforce import upsert_contract_from_salesforce


User = get_user_model()


class ImportLifecycleResolveTests(SimpleTestCase):
    def test_status_only_picks_compatible_default_stage(self):
        self.assertEqual(resolve_import_status_stage(status='ACTIVE'), ('ACTIVE', 'OBLIGATION_TRACKING'))
        self.assertEqual(resolve_import_status_stage(status='DRAFT'), ('IN_PROGRESS', 'DRAFTING'))

    def test_explicit_invalid_pair_rejected(self):
        with self.assertRaises(ImportLifecycleError):
            resolve_import_status_stage(status='ACTIVE', lifecycle_stage='DRAFTING')
        with self.assertRaises(ImportLifecycleError):
            resolve_import_status_stage(status='IN_PROGRESS', lifecycle_stage='OBLIGATION_TRACKING')


class ImportPathOwnershipTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Import Org', slug='import-core001')
        self.user = User.objects.create_user(username='import-user', password='pass12345')
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.user,
            role=OrganizationMembership.Role.OWNER,
            is_active=True,
        )

    def test_inbound_rejects_invalid_status_stage_pair(self):
        svc = InboundImportService()
        result = svc.import_contracts_from_json(
            self.org,
            [{
                'title': 'Bad Pair',
                'status': 'ACTIVE',
                'lifecycle_stage': 'DRAFTING',
                'contract_type': 'NDA',
            }],
            self.user,
        )
        self.assertEqual(result.imported_count, 0)
        self.assertEqual(result.skipped_count, 1)
        self.assertTrue(any('Invalid import combination' in e['message'] for e in result.errors))
        self.assertFalse(Contract.objects.filter(title='Bad Pair').exists())

    def test_inbound_import_routes_lifecycle_through_service_audit(self):
        svc = InboundImportService()
        result = svc.import_contracts_from_json(
            self.org,
            [{'title': 'Imported Active', 'status': 'ACTIVE', 'contract_type': 'NDA'}],
            self.user,
        )
        self.assertEqual(result.imported_count, 1)
        contract = Contract.objects.get(title='Imported Active')
        self.assertEqual(contract.status, Contract.Status.ACTIVE)
        self.assertEqual(contract.lifecycle_stage, Contract.LifecycleStage.OBLIGATION_TRACKING)
        self.assertTrue(
            AuditLog.objects.filter(
                model_name='Contract',
                object_id=contract.pk,
                event_type='contract.operational_position_changed',
            ).exists()
        )

    def test_salesforce_upsert_invalid_pair_cannot_enter(self):
        with self.assertRaises(ImportLifecycleError):
            # Force invalid by resolving before persist — upsert only takes status,
            # so exercise the helper used by CSV/inbound with both fields.
            persist_contract_with_imported_lifecycle(
                Contract(organization=self.org, title='SF Bad', source_system='salesforce', source_system_id='x1'),
                desired_status='ACTIVE',
                desired_lifecycle_stage='DRAFTING',
                source='salesforce',
            )
        self.assertFalse(Contract.objects.filter(title='SF Bad').exists())

    def test_salesforce_upsert_applies_compatible_lifecycle(self):
        contract, action = upsert_contract_from_salesforce(
            self.org,
            {
                'source_system_id': 'sf-100',
                'contract_title': 'SF Contract',
                'counterparty_name': 'Acme',
                'status': 'SIGNED',
                'contract_type': 'MSA',
            },
        )
        self.assertEqual(action, 'created')
        self.assertEqual(contract.status, Contract.Status.ACTIVE)
        self.assertEqual(contract.lifecycle_stage, Contract.LifecycleStage.OBLIGATION_TRACKING)

    def test_netsuite_upsert_applies_compatible_lifecycle(self):
        contract, action = upsert_contract_from_netsuite(
            self.org,
            {
                'source_system_id': 'ns-100',
                'contract_title': 'NS Contract',
                'counterparty_name': 'Beta',
                'status': 'ACTIVE',
                'contract_type': 'OTHER',
            },
        )
        self.assertEqual(action, 'created')
        self.assertEqual(contract.status, Contract.Status.ACTIVE)
        self.assertEqual(contract.lifecycle_stage, Contract.LifecycleStage.OBLIGATION_TRACKING)


class DocumentSupersessionAuditTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Supersede Org', slug='supersede-org')
        self.org_b = Organization.objects.create(name='Other Org', slug='other-supersede')
        self.user = User.objects.create_user(username='super-user', password='pass12345')
        self.user_b = User.objects.create_user(username='other-super', password='pass12345')
        OrganizationMembership.objects.create(
            organization=self.org, user=self.user, role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        OrganizationMembership.objects.create(
            organization=self.org_b, user=self.user_b, role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        self.contract = Contract.objects.create(
            organization=self.org,
            title='Supersede Contract',
            status=Contract.Status.ACTIVE,
            lifecycle_stage=Contract.LifecycleStage.OBLIGATION_TRACKING,
            created_by=self.user,
        )
        self.previous = Document.objects.create(
            organization=self.org,
            title='Final Doc',
            status=Document.Status.FINAL,
            contract=self.contract,
            version=1,
            uploaded_by=self.user,
            file=SimpleUploadedFile('a.txt', b'aaa', content_type='text/plain'),
        )
        self.replacement = Document.objects.create(
            organization=self.org,
            title='Replacement Doc',
            status=Document.Status.DRAFT,
            contract=self.contract,
            version=2,
            parent_document=self.previous,
            uploaded_by=self.user,
            file=SimpleUploadedFile('b.txt', b'bbb', content_type='text/plain'),
        )

    def test_supersede_emits_immutable_audit_with_context(self):
        supersede_document(
            self.previous,
            self.replacement,
            actor=self.user,
            reason='version replace',
            source='test',
            correlation_id='corr-123',
            organization=self.org,
        )
        self.previous.refresh_from_db()
        self.assertEqual(self.previous.status, Document.Status.SUPERSEDED)
        event = AuditLog.objects.filter(event_type='document.superseded', object_id=self.previous.pk).first()
        self.assertIsNotNone(event)
        changes = event.changes or {}
        self.assertEqual(changes.get('event'), 'document.superseded')
        self.assertEqual(changes.get('previous_document_id'), self.previous.pk)
        self.assertEqual(changes.get('replacement_document_id'), self.replacement.pk)
        self.assertEqual(changes.get('contract_id'), self.contract.pk)
        self.assertEqual(changes.get('reason'), 'version replace')
        self.assertEqual(changes.get('source'), 'test')
        self.assertEqual(changes.get('correlation_id'), 'corr-123')
        self.assertEqual(changes.get('from'), Document.Status.FINAL)
        self.assertEqual(changes.get('to'), Document.Status.SUPERSEDED)

    def test_cross_tenant_actor_denied(self):
        with self.assertRaises(PermissionDenied):
            supersede_document(
                self.previous,
                self.replacement,
                actor=self.user_b,
                reason='attack',
                source='test',
            )
        self.previous.refresh_from_db()
        self.assertEqual(self.previous.status, Document.Status.FINAL)

    def test_document_update_view_writes_supersession_audit(self):
        client = Client()
        client.force_login(self.user)
        response = client.post(
            reverse('contracts:document_update', kwargs={'pk': self.previous.pk}),
            data={
                'title': 'Updated Document',
                'document_type': Document.DocType.CONTRACT,
                'status': Document.Status.FINAL,
                'description': 'Updated version',
                'file': SimpleUploadedFile('updated.txt', b'Updated content', content_type='text/plain'),
                'contract': self.contract.pk,
                'matter': '',
                'client': '',
                'tags': '',
                'is_privileged': '',
                'is_confidential': '',
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.previous.refresh_from_db()
        self.assertEqual(self.previous.status, Document.Status.SUPERSEDED)
        self.assertTrue(
            AuditLog.objects.filter(
                event_type='document.superseded',
                object_id=self.previous.pk,
            ).exists()
        )


class ContractSavePairProtectionTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Save Org', slug='save-core001')
        self.user = User.objects.create_user(username='save-user', password='pass12345')

    def test_valid_pair_saves(self):
        contract = Contract(
            organization=self.org,
            title='Valid',
            status=Contract.Status.IN_PROGRESS,
            lifecycle_stage=Contract.LifecycleStage.DRAFTING,
            created_by=self.user,
        )
        contract.save()
        self.assertTrue(contract.pk)

    def test_invalid_pair_rejected_on_explicit_update(self):
        contract = Contract.objects.create(
            organization=self.org,
            title='Will Flip',
            status=Contract.Status.IN_PROGRESS,
            lifecycle_stage=Contract.LifecycleStage.DRAFTING,
            created_by=self.user,
        )
        contract.status = Contract.Status.ACTIVE
        # Keep DRAFTING explicitly — must raise on update.
        with self.assertRaises(ValidationError):
            contract.save(update_fields=['status', 'updated_at'])

    def test_create_active_with_default_stage_coerces_resting_stage(self):
        contract = Contract.objects.create(
            organization=self.org,
            title='Active Default Stage',
            status=Contract.Status.ACTIVE,
            created_by=self.user,
        )
        self.assertEqual(contract.lifecycle_stage, Contract.LifecycleStage.OBLIGATION_TRACKING)

    def test_partial_update_without_lifecycle_fields_allows_historical_pair(self):
        contract = Contract.objects.create(
            organization=self.org,
            title='Historical',
            status=Contract.Status.IN_PROGRESS,
            lifecycle_stage=Contract.LifecycleStage.DRAFTING,
            created_by=self.user,
        )
        contract.status = Contract.Status.ACTIVE
        contract.lifecycle_stage = Contract.LifecycleStage.DRAFTING
        contract.save(skip_lifecycle_validation=True)
        contract.title = 'Renamed Only'
        contract.save(update_fields=['title', 'updated_at'])
        contract.refresh_from_db()
        self.assertEqual(contract.title, 'Renamed Only')
        self.assertEqual(contract.status, Contract.Status.ACTIVE)
        self.assertEqual(contract.lifecycle_stage, Contract.LifecycleStage.DRAFTING)

    def test_explicit_illegal_create_pair_without_default_stage_rejected(self):
        contract = Contract(
            organization=self.org,
            title='Illegal Create',
            status=Contract.Status.IN_PROGRESS,
            lifecycle_stage=Contract.LifecycleStage.OBLIGATION_TRACKING,
            created_by=self.user,
        )
        with self.assertRaises(ValidationError):
            contract.save()
