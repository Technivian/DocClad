"""PAR-CORE-002 — dual ContractType reconciliation (G-DOM-02)."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase

from contracts.models import Contract, ContractType, Organization, OrganizationMembership
from contracts.services.contract_import_lifecycle import persist_contract_with_imported_lifecycle
from contracts.services.contract_type_catalogue import (
    assign_contract_type,
    ensure_catalogue_row,
    form_choices,
    repair_contract_type_catalogue,
    seed_catalogue_from_enum,
    sync_contract_type_catalogue_fields,
    valid_codes,
    validate_import_contract_type,
)
from contracts.services.inbound_import import InboundImportService


User = get_user_model()


class ContractTypeCatalogueTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_catalogue_from_enum()

    def test_seed_covers_all_enum_codes(self):
        codes = set(ContractType.objects.values_list('code', flat=True))
        self.assertEqual(codes, set(valid_codes()))
        self.assertEqual(codes.__len__(), 21)

    def test_assign_sets_fk_and_denormalized_code(self):
        org = Organization.objects.create(name='Type Org', slug='type-org')
        contract = Contract(organization=org, title='Typed')
        assign_contract_type(contract, code='MSA')
        contract.save()
        contract.refresh_from_db()
        self.assertEqual(contract.contract_type, 'MSA')
        self.assertEqual(contract.contract_type_catalogue.code, 'MSA')

    def test_save_syncs_fk_from_legacy_char_field(self):
        org = Organization.objects.create(name='Legacy Org', slug='legacy-org')
        contract = Contract.objects.create(organization=org, title='Legacy', contract_type='DPA')
        self.assertEqual(contract.contract_type_catalogue.code, 'DPA')

    def test_import_alias_service_maps_to_sow(self):
        org = Organization.objects.create(name='Alias Org', slug='alias-org')
        contract = Contract(organization=org, title='Alias')
        assign_contract_type(contract, code='SERVICE')
        self.assertEqual(contract.contract_type, 'SOW')
        self.assertEqual(contract.contract_type_catalogue.code, 'SOW')

    def test_unknown_import_maps_to_other_not_invented_code(self):
        org = Organization.objects.create(name='Unknown Org', slug='unknown-org')
        contract = Contract(organization=org, title='Unknown')
        assign_contract_type(contract, code='NOT_A_REAL_TYPE')
        self.assertEqual(contract.contract_type, 'OTHER')
        self.assertEqual(contract.contract_type_catalogue.code, 'OTHER')

    def test_inbound_import_accepts_msa_and_sets_catalogue(self):
        org = Organization.objects.create(name='Inbound Org', slug='inbound-type')
        user = User.objects.create_user(username='inbound-type', password='pass12345')
        OrganizationMembership.objects.create(
            organization=org, user=user, role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        result = InboundImportService().import_contracts_from_json(
            org,
            [{'title': 'Inbound MSA', 'status': 'IN_PROGRESS', 'contract_type': 'MSA'}],
            user,
        )
        self.assertEqual(result.imported_count, 1)
        c = Contract.objects.get(title='Inbound MSA')
        self.assertEqual(c.contract_type_catalogue.code, 'MSA')

    def test_inbound_rejects_invalid_type(self):
        errors = validate_import_contract_type('NOT_VALID')
        self.assertTrue(errors)

    def test_duplicate_catalogue_code_prevented(self):
        ensure_catalogue_row('NDA')
        with self.assertRaises(Exception):
            ContractType.objects.create(code='NDA', name='Duplicate NDA')

    def test_form_choices_from_catalogue(self):
        codes = {c[0] for c in form_choices(include_blank=False)}
        self.assertIn('MSA', codes)
        self.assertIn('ORDER_CONFIRMATION', codes)

    def test_repository_filter_by_type_still_works(self):
        org = Organization.objects.create(name='Repo Org', slug='repo-type')
        Contract.objects.create(organization=org, title='Filter Me', contract_type='NDA')
        self.assertTrue(
            Contract.objects.filter(organization=org, contract_type='NDA').exists()
        )
        self.assertTrue(
            Contract.objects.filter(organization=org, contract_type_catalogue__code='NDA').exists()
        )

    def test_authorized_type_repair(self):
        org = Organization.objects.create(name='Repair Org', slug='repair-type')
        owner = User.objects.create_user(username='type-owner', password='pass12345')
        OrganizationMembership.objects.create(
            organization=org, user=owner, role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        contract = Contract.objects.create(organization=org, title='Repair', contract_type='OTHER')
        repair_contract_type_catalogue(
            contract, code='VENDOR', reason='Recovered from archive metadata', actor=owner,
        )
        contract.refresh_from_db()
        self.assertEqual(contract.contract_type, 'VENDOR')
        self.assertEqual(contract.contract_type_catalogue.code, 'VENDOR')

    def test_unauthorized_type_repair_denied(self):
        org = Organization.objects.create(name='Deny Org', slug='deny-type')
        member = User.objects.create_user(username='type-member', password='pass12345')
        OrganizationMembership.objects.create(
            organization=org, user=member, role=OrganizationMembership.Role.MEMBER, is_active=True,
        )
        contract = Contract.objects.create(organization=org, title='No Repair', contract_type='OTHER')
        with self.assertRaises(PermissionDenied):
            repair_contract_type_catalogue(
                contract, code='MSA', reason='Nope', actor=member,
            )

    def test_persist_import_helper_assigns_catalogue(self):
        org = Organization.objects.create(name='Persist Org', slug='persist-type')
        contract = Contract(organization=org, title='CSV Type', contract_type='SAAS')
        persist_contract_with_imported_lifecycle(
            contract, desired_status='IN_PROGRESS', source='csv_import',
        )
        contract.refresh_from_db()
        self.assertEqual(contract.contract_type_catalogue.code, 'SAAS')


class ContractTypeMigrationTests(TransactionTestCase):
    def test_forward_rollback_reforward(self):
        executor = MigrationExecutor(connection)
        app = 'contracts'
        before = [(app, '0106_contract_record_provenance')]
        target = [(app, '0107_contract_type_catalogue_fk')]

        executor.migrate(before)
        executor.loader.build_graph()
        State = executor.loader.project_state(before).apps
        Organization = State.get_model('contracts', 'Organization')
        Contract = State.get_model('contracts', 'Contract')
        org = Organization.objects.create(name='Mig Type', slug='mig-type')
        Contract.objects.create(organization=org, title='Legacy SERVICE', contract_type='SERVICE', status='IN_PROGRESS', lifecycle_stage='DRAFTING')
        Contract.objects.create(organization=org, title='Valid NDA', contract_type='NDA', status='IN_PROGRESS', lifecycle_stage='DRAFTING')

        executor.migrate(target)
        executor.loader.build_graph()
        After = executor.loader.project_state(target).apps
        ContractAfter = After.get_model('contracts', 'Contract')
        ContractTypeAfter = After.get_model('contracts', 'ContractType')
        self.assertEqual(ContractTypeAfter.objects.count(), 21)
        svc = ContractAfter.objects.get(title='Legacy SERVICE')
        self.assertEqual(svc.contract_type, 'SOW')
        self.assertIsNotNone(svc.contract_type_catalogue_id)

        executor.migrate(before)
        executor.loader.build_graph()
        executor.migrate(target)
        executor.loader.build_graph()
        After2 = executor.loader.project_state(target).apps.get_model('contracts', 'Contract')
        row = After2.objects.filter(title='Legacy SERVICE').values('contract_type').first()
        self.assertEqual(row['contract_type'], 'SOW')
