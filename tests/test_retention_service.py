"""Tests for Retention Service (Area 2) - SimpleTestCase with mocks."""
from datetime import date, timedelta
from unittest import TestCase
from unittest.mock import MagicMock, patch


class TestRetentionServiceMocked(TestCase):
    def _make_service(self):
        from contracts.services.retention_jobs import RetentionService
        return RetentionService()

    def test_overdue_contracts_detected(self):
        svc = self._make_service()
        org = MagicMock()

        policy = MagicMock()
        policy.id = 1
        policy.title = 'Contract Policy'
        policy.category = 'CONTRACTS'
        policy.retention_period_days = 365
        policy.auto_delete = False

        old_date = date.today() - timedelta(days=400)
        contract = MagicMock()
        contract.id = 10
        contract.title = 'Old Contract'
        contract.created_at = MagicMock()
        contract.created_at.date.return_value = old_date

        with patch('contracts.services.retention_jobs.RetentionPolicy') as MockPolicy:
            with patch('contracts.services.retention_jobs.Contract') as MockContract:
                MockPolicy.objects.filter.return_value = [policy]
                MockContract.objects.filter.return_value = [contract]
                items = svc.get_overdue_contracts(org)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].contract_id, 10)
        self.assertGreater(items[0].days_overdue, 0)

    def test_recent_contracts_not_overdue(self):
        svc = self._make_service()
        org = MagicMock()

        policy = MagicMock()
        policy.id = 1
        policy.title = 'Contract Policy'
        policy.category = 'CONTRACTS'
        policy.retention_period_days = 365
        policy.auto_delete = False

        recent_date = date.today() - timedelta(days=100)
        contract = MagicMock()
        contract.id = 11
        contract.title = 'Recent Contract'
        contract.created_at = MagicMock()
        contract.created_at.date.return_value = recent_date

        with patch('contracts.services.retention_jobs.RetentionPolicy') as MockPolicy:
            with patch('contracts.services.retention_jobs.Contract') as MockContract:
                MockPolicy.objects.filter.return_value = [policy]
                MockContract.objects.filter.return_value = [contract]
                items = svc.get_overdue_contracts(org)

        self.assertEqual(len(items), 0)

    def test_no_policies_returns_empty(self):
        svc = self._make_service()
        org = MagicMock()

        with patch('contracts.services.retention_jobs.RetentionPolicy') as MockPolicy:
            MockPolicy.objects.filter.return_value = []
            items = svc.get_overdue_contracts(org)

        self.assertEqual(items, [])

    def test_log_retention_action_creates_log(self):
        svc = self._make_service()
        org = MagicMock()
        user = MagicMock()

        mock_contract = MagicMock()
        mock_log = MagicMock()
        mock_log.id = 99
        mock_log.action = 'FLAGGED'

        with patch('contracts.services.retention_jobs.Contract') as MockContract:
            with patch('contracts.services.retention_jobs.RetentionActionLog') as MockLog:
                MockContract.objects.get.return_value = mock_contract
                MockContract.DoesNotExist = Exception
                MockLog.objects.create.return_value = mock_log
                result = svc.log_retention_action(org, 10, 'FLAGGED', user, notes='Test note')

        self.assertEqual(result.action, 'FLAGGED')
        MockLog.objects.create.assert_called_once()

    def test_log_action_handles_missing_contract(self):
        svc = self._make_service()
        org = MagicMock()
        user = MagicMock()
        mock_log = MagicMock()
        mock_log.id = 98
        mock_log.action = 'ARCHIVED'

        with patch('contracts.services.retention_jobs.Contract') as MockContract:
            with patch('contracts.services.retention_jobs.RetentionActionLog') as MockLog:
                MockContract.DoesNotExist = Exception
                MockContract.objects.get.side_effect = Exception('not found')
                MockLog.objects.create.return_value = mock_log
                result = svc.log_retention_action(org, 999, 'ARCHIVED', user)

        MockLog.objects.create.assert_called_once()

    def test_get_retention_log_returns_list(self):
        svc = self._make_service()
        org = MagicMock()

        mock_log = MagicMock()
        mock_log.id = 1
        mock_log.contract_id = 10
        mock_log.action = 'FLAGGED'
        mock_log.performed_by_id = 5
        mock_log.notes = ''
        mock_log.created_at.isoformat.return_value = '2024-01-01T00:00:00'

        with patch('contracts.services.retention_jobs.RetentionActionLog') as MockLog:
            mock_qs = MagicMock()
            mock_qs.__getitem__ = MagicMock(return_value=[mock_log])
            MockLog.objects.filter.return_value = mock_qs
            logs = svc.get_retention_log(org)

        self.assertIsInstance(logs, list)

    def test_retention_item_has_auto_delete_flag(self):
        svc = self._make_service()
        org = MagicMock()

        policy = MagicMock()
        policy.id = 1
        policy.title = 'Contract Policy'
        policy.category = 'CONTRACTS'
        policy.retention_period_days = 100
        policy.auto_delete = True

        old_date = date.today() - timedelta(days=200)
        contract = MagicMock()
        contract.id = 20
        contract.title = 'Auto Delete Contract'
        contract.created_at = MagicMock()
        contract.created_at.date.return_value = old_date

        with patch('contracts.services.retention_jobs.RetentionPolicy') as MockPolicy:
            with patch('contracts.services.retention_jobs.Contract') as MockContract:
                MockPolicy.objects.filter.return_value = [policy]
                MockContract.objects.filter.return_value = [contract]
                items = svc.get_overdue_contracts(org)

        self.assertTrue(items[0].auto_delete)

    def test_days_overdue_calculated_correctly(self):
        svc = self._make_service()
        org = MagicMock()

        policy = MagicMock()
        policy.id = 1
        policy.title = 'Test Policy'
        policy.category = 'CONTRACTS'
        policy.retention_period_days = 100
        policy.auto_delete = False

        old_date = date.today() - timedelta(days=150)
        contract = MagicMock()
        contract.id = 30
        contract.title = 'Test'
        contract.created_at = MagicMock()
        contract.created_at.date.return_value = old_date

        with patch('contracts.services.retention_jobs.RetentionPolicy') as MockPolicy:
            with patch('contracts.services.retention_jobs.Contract') as MockContract:
                MockPolicy.objects.filter.return_value = [policy]
                MockContract.objects.filter.return_value = [contract]
                items = svc.get_overdue_contracts(org)

        self.assertEqual(items[0].days_overdue, 50)
