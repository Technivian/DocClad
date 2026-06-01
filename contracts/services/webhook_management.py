"""Webhook management service for integrations."""
from __future__ import annotations

from django.utils import timezone

from contracts.models import WebhookDelivery, WebhookEndpoint, SalesforceOrganizationConnection

_WebhookDeliveryDoesNotExist = WebhookDelivery.DoesNotExist


class WebhookManagementService:
    def get_failed_deliveries(self, org, limit: int = 50) -> list[dict]:
        deliveries = WebhookDelivery.objects.filter(
            endpoint__organization=org,
            status='FAILED',
        ).order_by('-created_at')[:limit]
        return [self._delivery_to_dict(d) for d in deliveries]

    def retry_delivery(self, delivery_id: int, org) -> dict:
        try:
            delivery = WebhookDelivery.objects.get(pk=delivery_id, endpoint__organization=org)
        except _WebhookDeliveryDoesNotExist:
            raise ValueError(f'Delivery {delivery_id} not found')

        delivery.status = 'PENDING'
        delivery.next_attempt_at = timezone.now()
        delivery.save(update_fields=['status', 'next_attempt_at', 'updated_at'])
        return {'queued': True}

    def get_dead_letter_queue(self, org, limit: int = 50) -> list[dict]:
        deliveries = WebhookDelivery.objects.filter(
            endpoint__organization=org,
            attempt_count__gt=5,
            status='FAILED',
        ).order_by('-created_at')[:limit]
        return [self._delivery_to_dict(d) for d in deliveries]

    def get_diagnostics(self, org) -> dict:
        total_endpoints = WebhookEndpoint.objects.filter(organization=org).count()
        active_endpoints = WebhookEndpoint.objects.filter(organization=org, status='ACTIVE').count()
        pending = WebhookDelivery.objects.filter(endpoint__organization=org, status='PENDING').count()
        failed = WebhookDelivery.objects.filter(endpoint__organization=org, status='FAILED').count()
        dlq_count = WebhookDelivery.objects.filter(
            endpoint__organization=org,
            attempt_count__gt=5,
            status='FAILED',
        ).count()

        from django.utils import timezone as tz
        from datetime import timedelta
        week_ago = tz.now() - timedelta(days=7)
        recent = WebhookDelivery.objects.filter(endpoint__organization=org, created_at__gte=week_ago)
        total_recent = recent.count()
        sent_recent = recent.filter(status='SENT').count()
        success_rate = round(sent_recent / total_recent * 100, 1) if total_recent else 0.0

        return {
            'total_endpoints': total_endpoints,
            'active_endpoints': active_endpoints,
            'pending_deliveries': pending,
            'failed_deliveries': failed,
            'dlq_count': dlq_count,
            'success_rate_7d': success_rate,
        }

    def requeue_dead_letter(self, delivery_id: int, org) -> dict:
        try:
            delivery = WebhookDelivery.objects.get(pk=delivery_id, endpoint__organization=org)
        except _WebhookDeliveryDoesNotExist:
            raise ValueError(f'Delivery {delivery_id} not found')

        delivery.attempt_count = 0
        delivery.status = 'PENDING'
        delivery.next_attempt_at = timezone.now()
        delivery.save(update_fields=['attempt_count', 'status', 'next_attempt_at', 'updated_at'])
        return {'queued': True}

    @staticmethod
    def _delivery_to_dict(d: WebhookDelivery) -> dict:
        return {
            'id': d.id,
            'event_type': d.event_type,
            'status': d.status,
            'attempt_count': d.attempt_count,
            'max_attempts': d.max_attempts,
            'error_message': d.error_message,
            'endpoint_id': d.endpoint_id,
            'created_at': d.created_at.isoformat(),
            'next_attempt_at': d.next_attempt_at.isoformat() if d.next_attempt_at else None,
        }


def get_webhook_management_service() -> WebhookManagementService:
    return WebhookManagementService()
