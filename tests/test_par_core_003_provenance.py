"""PAR-CORE-003 — Contract Record provenance completeness."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase

from contracts.models import (
    AuditLog,
    Contract,
    Organization,
    OrganizationMembership,
    Workflow,
    WorkflowTemplate,
)
from contracts.services.contract_import_lifecycle import persist_contract_with_imported_lifecycle
from contracts.services.contract_provenance import (
    EVENT_PROVENANCE_ASSIGNED,
    EVENT_PROVENANCE_REPAIRED,
    EVENT_RECORD_CREATED,
    OriginKind,
    ProvenanceError,
    apply_provenance_fields,
    pin_workflow_provenance,
    repair_contract_provenance,
    validate_provenance_for_kind,
)
from contracts.services.inbound_import import InboundImportService
from contracts.services.netsuite import upsert_contract_from_netsuite
from contracts.services.salesforce import upsert_contract_from_salesforce


User = get_user_model()


class ProvenanceValidationTests(TestCase):
    def test_missing_origin_kind_rejected(self):
        with self.assertRaises(ProvenanceError):
            validate_provenance_for_kind(origin_kind='')

    def test_manual_requires_actor_and_reason(self):
        with self.assertRaises(ProvenanceError):
            validate_provenance_for_kind(origin_kind=OriginKind.MANUAL, origin_reason='x')
        with self.assertRaises(ProvenanceError):
            validate_provenance_for_kind(origin_kind=OriginKind.MANUAL, actor=object())

    def test_workflow_requires_instance_and_version(self):
        with self.assertRaises(ProvenanceError):
            validate_provenance_for_kind(origin_kind=OriginKind.WORKFLOW)
        with self.assertRaises(ProvenanceError):
            validate_provenance_for_kind(origin_kind=OriginKind.WORKFLOW, origin_workflow_id=1)

    def test_integration_requires_source_identity(self):
        with self.assertRaises(ProvenanceError):
            validate_provenance_for_kind(origin_kind=OriginKind.INTEGRATION, source_system='salesforce')


class ProvenanceCreatePathTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Prov Org', slug='prov-org')
        self.org_b = Organization.objects.create(name='Other Org', slug='prov-other')
        self.user = User.objects.create_user(username='prov-owner', password='pass12345')
        self.member = User.objects.create_user(username='prov-member', password='pass12345')
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.user,
            role=OrganizationMembership.Role.OWNER,
            is_active=True,
        )
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.member,
            role=OrganizationMembership.Role.MEMBER,
            is_active=True,
        )
        self.template = WorkflowTemplate.objects.create(
            name='Prov Template',
            description='t',
            organization=self.org,
            version=3,
            is_active=True,
        )

    def test_unclassified_create_becomes_legacy_unknown_and_locks(self):
        c = Contract.objects.create(organization=self.org, title='Bare')
        c.refresh_from_db()
        self.assertEqual(c.origin_kind, OriginKind.LEGACY_UNKNOWN)
        self.assertIsNotNone(c.provenance_locked_at)

    def test_manual_create_locks_actor_and_reason(self):
        c = Contract(organization=self.org, title='Manual')
        apply_provenance_fields(
            c,
            origin_kind=OriginKind.MANUAL,
            origin_channel='test',
            origin_reason='Operator created manually',
            actor=self.user,
            lock=True,
        )
        c.save()
        c.refresh_from_db()
        self.assertEqual(c.origin_kind, OriginKind.MANUAL)
        self.assertEqual(c.created_by_id, self.user.id)
        self.assertEqual(c.origin_reason, 'Operator created manually')
        self.assertIsNotNone(c.provenance_locked_at)

    def test_workflow_pin_sets_instance_and_version(self):
        c = Contract(organization=self.org, title='WF', created_by=self.user)
        apply_provenance_fields(
            c, origin_kind=OriginKind.WORKFLOW, origin_channel='test_wf', actor=self.user, lock=False, validate=False,
        )
        c.save()
        self.assertIsNone(c.provenance_locked_at)
        wf = Workflow.objects.create(
            title='Inst',
            organization=self.org,
            template=self.template,
            contract=c,
            created_by=self.user,
        )
        pin_workflow_provenance(c, wf, actor=self.user, channel='test_wf')
        c.refresh_from_db()
        self.assertEqual(c.origin_kind, OriginKind.WORKFLOW)
        self.assertEqual(c.origin_workflow_id, wf.id)
        self.assertEqual(c.origin_workflow_template_id, self.template.id)
        self.assertEqual(c.origin_workflow_template_version, 3)
        self.assertIsNotNone(c.provenance_locked_at)
        self.assertTrue(
            AuditLog.objects.filter(object_id=c.pk, event_type=EVENT_PROVENANCE_ASSIGNED).exists()
        )

    def test_salesforce_import_retains_source_identity(self):
        contract, action = upsert_contract_from_salesforce(
            self.org,
            {
                'source_system_id': 'SF-99',
                'contract_title': 'SF Deal',
                'counterparty_name': 'Acme',
                'status': 'ACTIVE',
            },
        )
        self.assertEqual(action, 'created')
        self.assertEqual(contract.origin_kind, OriginKind.INTEGRATION)
        self.assertEqual(contract.source_system, 'salesforce')
        self.assertEqual(contract.source_system_id, 'SF-99')
        self.assertIsNotNone(contract.provenance_locked_at)
        self.assertTrue(
            AuditLog.objects.filter(object_id=contract.pk, event_type=EVENT_RECORD_CREATED).exists()
        )

    def test_netsuite_import_retains_source_identity(self):
        contract, action = upsert_contract_from_netsuite(
            self.org,
            {
                'source_system_id': 'NS-1',
                'contract_title': 'NS Deal',
                'status': 'IN_PROGRESS',
            },
        )
        self.assertEqual(action, 'created')
        self.assertEqual(contract.origin_kind, OriginKind.INTEGRATION)
        self.assertEqual(contract.source_system, 'netsuite')
        self.assertEqual(contract.source_system_id, 'NS-1')

    def test_inbound_import_sets_import_inbound(self):
        result = InboundImportService().import_contracts_from_json(
            self.org,
            [{'title': 'Inbound One', 'status': 'IN_PROGRESS', 'contract_type': 'NDA'}],
            self.user,
        )
        self.assertEqual(result.imported_count, 1)
        c = Contract.objects.get(title='Inbound One')
        self.assertEqual(c.origin_kind, OriginKind.IMPORT_INBOUND)
        self.assertEqual(c.created_by_id, self.user.id)

    def test_csv_import_path_via_persist_helper(self):
        c = Contract(organization=self.org, title='CSV Row')
        persist_contract_with_imported_lifecycle(
            c,
            desired_status='IN_PROGRESS',
            actor=None,
            source='csv_import',
            provenance_correlation_id='batch-abc',
        )
        c.refresh_from_db()
        self.assertEqual(c.origin_kind, OriginKind.IMPORT_CSV)
        self.assertEqual(c.provenance_correlation_id, 'batch-abc')

    def test_immutable_provenance_rejects_silent_edit(self):
        c = Contract.objects.create(organization=self.org, title='Locked')
        c.origin_kind = OriginKind.MANUAL
        with self.assertRaises(ProvenanceError):
            c.save(update_fields=['origin_kind', 'updated_at'])

    def test_queryset_update_cannot_bypass_provenance(self):
        c = Contract.objects.create(organization=self.org, title='BulkGuard')
        with self.assertRaises(ProvenanceError):
            Contract.objects.filter(pk=c.pk).update(origin_kind=OriginKind.MANUAL)

    def test_bulk_create_stamps_legacy_unknown(self):
        objs = [
            Contract(organization=self.org, title='B1'),
            Contract(organization=self.org, title='B2'),
        ]
        Contract.objects.bulk_create(objs)
        kinds = set(Contract.objects.filter(title__in=['B1', 'B2']).values_list('origin_kind', flat=True))
        self.assertEqual(kinds, {OriginKind.LEGACY_UNKNOWN})

    def test_authorized_repair_emits_audit(self):
        c = Contract.objects.create(organization=self.org, title='Repair Me')
        self.assertEqual(c.origin_kind, OriginKind.LEGACY_UNKNOWN)
        repair_contract_provenance(
            c,
            reason='Recovered Salesforce id from ops ticket',
            actor=self.user,
            origin_kind=OriginKind.INTEGRATION,
            origin_channel='salesforce',
            source_system='salesforce',
            source_system_id='SF-REPAIR-1',
        )
        c.refresh_from_db()
        self.assertEqual(c.origin_kind, OriginKind.INTEGRATION)
        self.assertEqual(c.source_system_id, 'SF-REPAIR-1')
        self.assertTrue(
            AuditLog.objects.filter(object_id=c.pk, event_type=EVENT_PROVENANCE_REPAIRED).exists()
        )

    def test_unauthorized_repair_denied(self):
        c = Contract.objects.create(organization=self.org, title='No Repair')
        with self.assertRaises(PermissionDenied):
            repair_contract_provenance(
                c,
                reason='Nope',
                actor=self.member,
                origin_kind=OriginKind.MANUAL,
                created_by=self.member,
                origin_reason='Nope',
            )

    def test_repair_tenant_isolation(self):
        c = Contract.objects.create(organization=self.org, title='Tenant A')
        with self.assertRaises(PermissionDenied):
            repair_contract_provenance(
                c,
                reason='Cross-tenant',
                actor=self.user,
                organization=self.org_b,
                origin_kind=OriginKind.MANUAL,
                created_by=self.user,
                origin_reason='Cross-tenant',
            )

    def test_workflow_org_mismatch_rejected(self):
        c = Contract(organization=self.org, title='Mismatch', created_by=self.user)
        apply_provenance_fields(
            c, origin_kind=OriginKind.WORKFLOW, origin_channel='x', actor=self.user, lock=False, validate=False,
        )
        c.save()
        wf = Workflow.objects.create(
            title='Other',
            organization=self.org_b,
            template=self.template,
            contract=c,
            created_by=self.user,
        )
        with self.assertRaises(ProvenanceError):
            pin_workflow_provenance(c, wf, actor=self.user)


class ProvenanceMigrationTests(TransactionTestCase):
    """Forward / rollback / re-forward evidence for 0106."""

    def test_forward_rollback_reforward(self):
        executor = MigrationExecutor(connection)
        app = 'contracts'
        target = [(app, '0106_contract_record_provenance')]
        before = [(app, '0105_workflowtemplate_is_active_default_false')]

        executor.migrate(before)
        executor.loader.build_graph()

        ProjectState = executor.loader.project_state(before).apps
        Organization = ProjectState.get_model('contracts', 'Organization')
        Contract = ProjectState.get_model('contracts', 'Contract')
        org = Organization.objects.create(name='Mig Org', slug='mig-prov')
        Contract.objects.create(
            organization=org,
            title='Pre-prov',
            status='IN_PROGRESS',
            lifecycle_stage='DRAFTING',
            source_system='salesforce',
            source_system_id='SF-MIG',
        )
        Contract.objects.create(
            organization=org,
            title='No Evidence',
            status='IN_PROGRESS',
            lifecycle_stage='DRAFTING',
        )

        executor.migrate(target)
        executor.loader.build_graph()
        After = executor.loader.project_state(target).apps.get_model('contracts', 'Contract')
        sf = After.objects.get(title='Pre-prov')
        legacy = After.objects.get(title='No Evidence')
        self.assertEqual(sf.origin_kind, 'INTEGRATION')
        self.assertEqual(sf.source_system_id, 'SF-MIG')
        self.assertEqual(legacy.origin_kind, 'LEGACY_UNKNOWN')
        self.assertIsNotNone(sf.provenance_locked_at)

        executor.migrate(before)
        executor.loader.build_graph()
        # Re-forward
        executor.migrate(target)
        executor.loader.build_graph()
        After2 = executor.loader.project_state(target).apps.get_model('contracts', 'Contract')
        self.assertEqual(After2.objects.get(title='Pre-prov').origin_kind, 'INTEGRATION')
        self.assertEqual(After2.objects.get(title='No Evidence').origin_kind, 'LEGACY_UNKNOWN')
