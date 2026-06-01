"""CRM sync service for integrations."""
from __future__ import annotations

from contracts.models import SalesforceOrganizationConnection, SalesforceSyncRun

_SalesforceConnectionDoesNotExist = SalesforceOrganizationConnection.DoesNotExist


class CRMSyncService:
    def get_sync_status(self, org) -> dict:
        try:
            conn = SalesforceOrganizationConnection.objects.get(organization=org, is_active=True)
            last_run = SalesforceSyncRun.objects.filter(organization=org).order_by('-started_at').first()
            total_synced = 0
            if last_run:
                total_synced = (last_run.created_count or 0) + (last_run.updated_count or 0)

            return {
                'provider': 'salesforce',
                'last_sync_at': conn.last_sync_at.isoformat() if conn.last_sync_at else None,
                'total_synced': total_synced,
                'pending': 0,
                'errors': last_run.error_count if last_run else 0,
            }
        except _SalesforceConnectionDoesNotExist:
            return {
                'provider': None,
                'last_sync_at': None,
                'total_synced': 0,
                'pending': 0,
                'errors': 0,
            }

    def list_available_integrations(self, org) -> list[dict]:
        integrations = []

        try:
            conn = SalesforceOrganizationConnection.objects.get(organization=org)
            integrations.append({
                'name': 'salesforce',
                'connected': conn.is_active,
                'last_sync_at': conn.last_sync_at.isoformat() if conn.last_sync_at else None,
            })
        except _SalesforceConnectionDoesNotExist:
            integrations.append({
                'name': 'salesforce',
                'connected': False,
                'last_sync_at': None,
            })

        return integrations

    def trigger_sync(self, org, provider: str, user) -> dict:
        if provider == 'salesforce':
            return {'queued': True, 'provider': 'salesforce'}
        raise ValueError(f'Unknown provider: {provider}')


def get_crm_sync_service() -> CRMSyncService:
    return CRMSyncService()
