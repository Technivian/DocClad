"""Tests for Inbound Import service (Area 3) — PDR-0002 aware."""
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from contracts.models import Contract, Organization, OrganizationMembership
from contracts.services.inbound_import import InboundImportService


User = get_user_model()


class TestInboundImportValidation(SimpleTestCase):
    def _make_service(self):
        return InboundImportService()

    def test_validate_row_invalid_status(self):
        svc = self._make_service()
        errors = svc.validate_import_row({'title': 'Test', 'status': 'BOGUS'})
        self.assertTrue(any('status' in e for e in errors))

    def test_validate_row_invalid_date(self):
        svc = self._make_service()
        errors = svc.validate_import_row({'title': 'Test', 'start_date': 'not-a-date'})
        self.assertTrue(any('start_date' in e for e in errors))

    def test_validate_row_valid_passes(self):
        svc = self._make_service()
        errors = svc.validate_import_row({
            'title': 'Valid Contract',
            'counterparty': 'Corp',
            'contract_type': 'NDA',
            'status': 'DRAFT',
            'start_date': '2024-01-01',
            'end_date': '2025-01-01',
        })
        self.assertEqual(errors, [])

    def test_validate_row_rejects_illegal_pair(self):
        svc = self._make_service()
        errors = svc.validate_import_row({
            'title': 'Bad Pair',
            'status': 'ACTIVE',
            'lifecycle_stage': 'DRAFTING',
        })
        self.assertTrue(any('Invalid import combination' in e for e in errors))


class TestInboundImportPersistence(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Inbound Org', slug='inbound-org')
        self.user = User.objects.create_user(username='inbound-user', password='pass12345')
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.user,
            role=OrganizationMembership.Role.OWNER,
            is_active=True,
        )
        self.svc = InboundImportService()

    def test_csv_import_valid_rows(self):
        csv_text = 'title,counterparty,contract_type,status\nTest Contract,Acme,NDA,DRAFT\n'
        result = self.svc.import_contracts_from_csv(self.org, csv_text, self.user)
        self.assertEqual(result.imported_count, 1)
        self.assertEqual(result.skipped_count, 0)
        contract = Contract.objects.get(title='Test Contract')
        self.assertEqual(contract.status, Contract.Status.IN_PROGRESS)
        self.assertEqual(contract.lifecycle_stage, Contract.LifecycleStage.DRAFTING)

    def test_csv_import_missing_title_skipped(self):
        csv_text = 'title,counterparty\n,Acme\n'
        result = self.svc.import_contracts_from_csv(self.org, csv_text, self.user)
        self.assertEqual(result.skipped_count, 1)
        self.assertEqual(len(result.errors), 1)
        self.assertIn('title is required', result.errors[0]['message'])

    def test_json_import_valid(self):
        data = [{'title': 'JSON Contract', 'counterparty': 'Corp', 'contract_type': 'NDA', 'status': 'DRAFT'}]
        result = self.svc.import_contracts_from_json(self.org, data, self.user)
        self.assertEqual(result.imported_count, 1)

    def test_json_import_dry_run(self):
        data = [{'title': 'Dry Run Contract'}]
        result = self.svc.import_contracts_from_json(self.org, data, self.user, dry_run=True)
        self.assertEqual(result.imported_count, 1)
        self.assertTrue(result.dry_run)
        self.assertFalse(Contract.objects.filter(title='Dry Run Contract').exists())

    def test_multiple_rows_mixed_results(self):
        data = [
            {'title': 'Good Contract'},
            {'title': '', 'status': 'DRAFT'},
        ]
        result = self.svc.import_contracts_from_json(self.org, data, self.user)
        self.assertEqual(result.imported_count, 1)
        self.assertEqual(result.skipped_count, 1)
