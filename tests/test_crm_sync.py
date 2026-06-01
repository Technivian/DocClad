"""Tests for CRM Sync service (Area 3)."""
from unittest import TestCase
from unittest.mock import MagicMock, patch


class TestCRMSyncService(TestCase):
    def _make_service(self):
        from contracts.services.crm_sync import CRMSyncService
        return CRMSyncService()

    def test_sync_status_with_active_salesforce(self):
        svc = self._make_service()
        org = MagicMock()
        conn = MagicMock()
        conn.is_active = True
        conn.last_sync_at.isoformat.return_value = '2024-06-01T10:00:00'

        mock_run = MagicMock()
        mock_run.created_count = 10
        mock_run.updated_count = 5
        mock_run.error_count = 0

        with patch('contracts.services.crm_sync.SalesforceOrganizationConnection') as MockConn:
            with patch('contracts.services.crm_sync.SalesforceSyncRun') as MockRun:
                MockConn.objects.get.return_value = conn
                MockConn.DoesNotExist = Exception
                MockRun.objects.filter.return_value.order_by.return_value.first.return_value = mock_run
                result = svc.get_sync_status(org)

        self.assertEqual(result['provider'], 'salesforce')
        self.assertIsNotNone(result['last_sync_at'])
        self.assertEqual(result['total_synced'], 15)

    def test_sync_status_no_connection(self):
        svc = self._make_service()
        org = MagicMock()

        with patch('contracts.services.crm_sync.SalesforceOrganizationConnection') as MockConn:
            from contracts.services.crm_sync import _SalesforceConnectionDoesNotExist
            MockConn.objects.get.side_effect = _SalesforceConnectionDoesNotExist()
            result = svc.get_sync_status(org)

        self.assertIsNone(result['provider'])
        self.assertIsNone(result['last_sync_at'])

    def test_list_integrations_returns_list(self):
        svc = self._make_service()
        org = MagicMock()
        conn = MagicMock()
        conn.is_active = True
        conn.last_sync_at = None

        with patch('contracts.services.crm_sync.SalesforceOrganizationConnection') as MockConn:
            MockConn.objects.get.return_value = conn
            MockConn.DoesNotExist = Exception
            integrations = svc.list_available_integrations(org)

        self.assertIsInstance(integrations, list)
        self.assertTrue(any(i['name'] == 'salesforce' for i in integrations))

    def test_trigger_sync_salesforce(self):
        svc = self._make_service()
        org = MagicMock()
        user = MagicMock()
        result = svc.trigger_sync(org, 'salesforce', user)
        self.assertTrue(result.get('queued'))
        self.assertEqual(result['provider'], 'salesforce')

    def test_trigger_sync_unknown_provider_raises(self):
        svc = self._make_service()
        org = MagicMock()
        user = MagicMock()
        with self.assertRaises(ValueError):
            svc.trigger_sync(org, 'unknown_crm', user)
