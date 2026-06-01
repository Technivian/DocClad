"""Tests for Webhook Management service (Area 3)."""
from unittest import TestCase
from unittest.mock import MagicMock, patch, call


class TestWebhookManagementService(TestCase):
    def _make_service(self):
        from contracts.services.webhook_management import WebhookManagementService
        return WebhookManagementService()

    def test_get_failed_deliveries_returns_list(self):
        svc = self._make_service()
        org = MagicMock()

        delivery = MagicMock()
        delivery.id = 1
        delivery.event_type = 'contract.created'
        delivery.status = 'FAILED'
        delivery.attempt_count = 3
        delivery.max_attempts = 5
        delivery.error_message = 'Timeout'
        delivery.endpoint_id = 10
        delivery.created_at.isoformat.return_value = '2024-01-01T00:00:00'
        delivery.next_attempt_at = None

        with patch('contracts.services.webhook_management.WebhookDelivery') as MockDel:
            mock_qs = MagicMock()
            mock_qs.filter.return_value = mock_qs
            mock_qs.order_by.return_value = mock_qs
            mock_qs.__getitem__ = MagicMock(return_value=[delivery])
            MockDel.objects.filter.return_value = mock_qs
            result = svc.get_failed_deliveries(org)

        self.assertIsInstance(result, list)

    def test_retry_delivery_sets_pending(self):
        svc = self._make_service()
        org = MagicMock()

        delivery = MagicMock()
        delivery.id = 1
        delivery.status = 'FAILED'

        with patch('contracts.services.webhook_management.WebhookDelivery') as MockDel:
            MockDel.objects.get.return_value = delivery
            MockDel.DoesNotExist = Exception
            result = svc.retry_delivery(1, org)

        self.assertEqual(delivery.status, 'PENDING')
        self.assertTrue(result.get('queued'))

    def test_retry_delivery_raises_on_not_found(self):
        svc = self._make_service()
        org = MagicMock()

        with patch('contracts.services.webhook_management.WebhookDelivery') as MockDel:
            from contracts.services.webhook_management import _WebhookDeliveryDoesNotExist
            MockDel.objects.get.side_effect = _WebhookDeliveryDoesNotExist()
            with self.assertRaises(ValueError):
                svc.retry_delivery(999, org)

    def test_get_dead_letter_queue(self):
        svc = self._make_service()
        org = MagicMock()

        with patch('contracts.services.webhook_management.WebhookDelivery') as MockDel:
            mock_qs = MagicMock()
            mock_qs.filter.return_value = mock_qs
            mock_qs.order_by.return_value = mock_qs
            mock_qs.__getitem__ = MagicMock(return_value=[])
            MockDel.objects.filter.return_value = mock_qs
            result = svc.get_dead_letter_queue(org)

        self.assertIsInstance(result, list)

    def test_get_diagnostics_returns_correct_keys(self):
        svc = self._make_service()
        org = MagicMock()

        with patch('contracts.services.webhook_management.WebhookEndpoint') as MockEP:
            with patch('contracts.services.webhook_management.WebhookDelivery') as MockDel:
                MockEP.objects.filter.return_value.count.return_value = 5
                mock_del_qs = MagicMock()
                mock_del_qs.filter.return_value = mock_del_qs
                mock_del_qs.count.return_value = 2
                MockDel.objects.filter.return_value = mock_del_qs
                result = svc.get_diagnostics(org)

        self.assertIn('total_endpoints', result)
        self.assertIn('active_endpoints', result)
        self.assertIn('pending_deliveries', result)
        self.assertIn('failed_deliveries', result)
        self.assertIn('dlq_count', result)
        self.assertIn('success_rate_7d', result)

    def test_requeue_dead_letter_resets_attempts(self):
        svc = self._make_service()
        org = MagicMock()

        delivery = MagicMock()
        delivery.id = 5
        delivery.attempt_count = 8

        with patch('contracts.services.webhook_management.WebhookDelivery') as MockDel:
            MockDel.objects.get.return_value = delivery
            MockDel.DoesNotExist = Exception
            result = svc.requeue_dead_letter(5, org)

        self.assertEqual(delivery.attempt_count, 0)
        self.assertEqual(delivery.status, 'PENDING')
        self.assertTrue(result.get('queued'))

    def test_delivery_to_dict_format(self):
        svc = self._make_service()
        delivery = MagicMock()
        delivery.id = 1
        delivery.event_type = 'test.event'
        delivery.status = 'FAILED'
        delivery.attempt_count = 2
        delivery.max_attempts = 5
        delivery.error_message = 'err'
        delivery.endpoint_id = 3
        delivery.created_at.isoformat.return_value = '2024-01-01T00:00:00'
        delivery.next_attempt_at = None

        d = svc._delivery_to_dict(delivery)

        self.assertEqual(d['id'], 1)
        self.assertEqual(d['status'], 'FAILED')
        self.assertIn('event_type', d)

    def test_retry_saves_delivery(self):
        svc = self._make_service()
        org = MagicMock()
        delivery = MagicMock()

        with patch('contracts.services.webhook_management.WebhookDelivery') as MockDel:
            MockDel.objects.get.return_value = delivery
            MockDel.DoesNotExist = Exception
            svc.retry_delivery(1, org)

        delivery.save.assert_called_once()
