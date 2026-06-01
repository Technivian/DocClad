"""Tests for Inbound Import service (Area 3)."""
from unittest import TestCase
from unittest.mock import MagicMock, patch


class TestInboundImportService(TestCase):
    def _make_service(self):
        from contracts.services.inbound_import import InboundImportService
        return InboundImportService()

    def test_csv_import_valid_rows(self):
        svc = self._make_service()
        org = MagicMock()
        user = MagicMock()
        csv_text = 'title,counterparty,contract_type,status\nTest Contract,Acme,NDA,DRAFT\n'

        with patch('contracts.services.inbound_import.Contract') as MockContract:
            MockContract.objects.create.return_value = MagicMock(id=1)
            result = svc.import_contracts_from_csv(org, csv_text, user)

        self.assertEqual(result.imported_count, 1)
        self.assertEqual(result.skipped_count, 0)
        self.assertFalse(result.dry_run)

    def test_csv_import_missing_title_skipped(self):
        svc = self._make_service()
        org = MagicMock()
        user = MagicMock()
        csv_text = 'title,counterparty\n,Acme\n'

        with patch('contracts.services.inbound_import.Contract'):
            result = svc.import_contracts_from_csv(org, csv_text, user)

        self.assertEqual(result.skipped_count, 1)
        self.assertEqual(len(result.errors), 1)
        self.assertIn('title is required', result.errors[0]['message'])

    def test_json_import_valid(self):
        svc = self._make_service()
        org = MagicMock()
        user = MagicMock()
        data = [{'title': 'JSON Contract', 'counterparty': 'Corp', 'contract_type': 'NDA', 'status': 'DRAFT'}]

        with patch('contracts.services.inbound_import.Contract') as MockContract:
            MockContract.objects.create.return_value = MagicMock(id=2)
            result = svc.import_contracts_from_json(org, data, user)

        self.assertEqual(result.imported_count, 1)

    def test_json_import_dry_run(self):
        svc = self._make_service()
        org = MagicMock()
        user = MagicMock()
        data = [{'title': 'Dry Run Contract'}]

        with patch('contracts.services.inbound_import.Contract') as MockContract:
            result = svc.import_contracts_from_json(org, data, user, dry_run=True)

        MockContract.objects.create.assert_not_called()
        self.assertEqual(result.imported_count, 1)
        self.assertTrue(result.dry_run)

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

    def test_multiple_rows_mixed_results(self):
        svc = self._make_service()
        org = MagicMock()
        user = MagicMock()
        data = [
            {'title': 'Good Contract'},
            {'title': '', 'status': 'DRAFT'},  # missing title
        ]

        with patch('contracts.services.inbound_import.Contract') as MockContract:
            MockContract.objects.create.return_value = MagicMock(id=3)
            result = svc.import_contracts_from_json(org, data, user)

        self.assertEqual(result.imported_count, 1)
        self.assertEqual(result.skipped_count, 1)
