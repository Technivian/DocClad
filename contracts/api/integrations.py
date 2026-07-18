
"""
API views for CLM One repository functionality.
"""
import hashlib
import json
import logging
import secrets

from django.contrib.auth import get_user_model
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.utils import timezone
from contracts.services.repository import BulkUpdateValidationError, get_repository_service
from contracts.services.salesforce import (
    CANONICAL_CONTRACT_FIELDS,
    build_salesforce_authorize_url,
    create_salesforce_sync_run,
    decrypt_salesforce_token,
    default_field_map_records,
    encrypt_salesforce_token,
    exchange_salesforce_code_for_tokens,
    get_effective_field_map_records,
    ingest_salesforce_records,
    SalesforceSyncError,
    refresh_salesforce_access_token,
    salesforce_oauth_is_configured,
    sync_salesforce_connection,
)
from contracts.services.webhooks import queue_webhook_event
from contracts.services.esign import ESignReconciliationError, apply_esign_event
from contracts.services.executive_analytics import build_executive_analytics_snapshot
from contracts.services.obligations import get_obligation_service
from contracts.services.netsuite import (
    NetSuiteSyncError,
    fetch_netsuite_records,
    ingest_netsuite_records,
    map_netsuite_record,
    netsuite_is_configured,
)
from contracts.domain.contracts import ListParams
from contracts.middleware import log_action
from contracts.permissions import can_manage_organization
from contracts.tenancy import get_user_organization
from contracts.tenancy import scope_queryset_for_organization
from contracts.models import (
    Contract,
    Document,
    OrganizationAPIToken,
    OrganizationContractFieldMap,
    Organization,
    OrganizationMembership,
    SalesforceOrganizationConnection,
    OrganizationSCIMGroup,
    OrganizationSCIMGroupMembership,
    ExecutiveDashboardPreset,
    WebhookDelivery,
    WebhookEndpoint,
    SalesforceSyncRun,
    UserProfile,
    AuditLog,
    SignatureRequest,
    BackgroundJob,
    OnboardingProgress,
    BillingPlan,
    OrgBillingSubscription,
    UsageRecord,
    ApprovalRequest,
    ClauseTemplate,
    ClausePlaybook,
    ClauseVariant,
    ClauseUsageEvent,
)

logger = logging.getLogger(__name__)
User = get_user_model()



# --- domain-specific imports (originally declared mid-module) ---
from contracts.services.dsar import get_dsar_service
from contracts.services.contract_versions import get_version_service
from contracts.models import ContractVersion
from contracts.services.ai_drafting import get_ai_drafting_service
from contracts.models import ClauseRecommendation
from contracts.services.admin_console import get_admin_console_service
from contracts.models import OrgPolicy
from contracts.services.permissions import get_permission_service
from contracts.services.onboarding import get_onboarding_service
from contracts.services.billing import get_billing_service
from contracts.services.compliance_portal import get_compliance_portal_service
from contracts.services.approval_workflow import get_approval_workflow_service
from contracts.services.clause_analytics import get_clause_analytics_service
from contracts.services.mandatory_clauses import get_mandatory_enforcement_service
from contracts.services.playbook import get_playbook_service
from contracts.services.search_api import (
    get_contract_search_service,
    get_clause_search_service,
)
from contracts.models import SearchTelemetryEvent
from contracts.services.subprocessor_alerts import get_subprocessor_alert_service
from contracts.services.retention_jobs import get_retention_service
from contracts.services.webhook_management import get_webhook_management_service
from contracts.services.inbound_import import get_inbound_import_service
from contracts.services.crm_sync import get_crm_sync_service
from contracts.services.postgres_health import get_postgres_health_service
from contracts.services.cve_gate import get_cve_gate_service
from contracts.services.restore_drill import get_restore_drill_service
from contracts.models import RestoreDrill as _RestoreDrillModel


from contracts.api._helpers import (
    _error_response,
    _scim_response,
    _api_version_response,
    _scim_paginated_list,
    _api_paginated_contracts,
    _resolve_scim_organization,
    _resolve_api_organization,
    _require_org_member_context,
)


def _require_org_admin_for_salesforce(request):
    if not getattr(request.user, 'is_authenticated', False):
        return None, _error_response(request, 'Authentication required.', 401)
    organization = get_user_organization(request.user)
    if organization is None:
        return None, _error_response(request, 'No active organization context.', 403)
    if not can_manage_organization(request.user, organization):
        return None, _error_response(request, 'Only organization admins/owners can manage integrations.', 403)
    return organization, None


@login_required
@require_http_methods(["GET"])
def salesforce_connection_status_api(request):
    organization, error = _require_org_admin_for_salesforce(request)
    if error:
        return error

    connection = SalesforceOrganizationConnection.objects.filter(organization=organization).first()
    if connection and connection.refresh_token and connection.token_expired:
        try:
            refreshed = refresh_salesforce_access_token(decrypt_salesforce_token(connection.refresh_token))
            connection.access_token = encrypt_salesforce_token(refreshed.access_token)
            connection.instance_url = refreshed.instance_url or connection.instance_url
            connection.scope = refreshed.scope or connection.scope
            connection.token_expires_at = refreshed.token_expires_at
            if refreshed.refresh_token:
                connection.refresh_token = encrypt_salesforce_token(refreshed.refresh_token)
            connection.save(update_fields=['access_token', 'instance_url', 'scope', 'token_expires_at', 'updated_at'])
        except Exception:
            logger.exception('Salesforce token refresh failed for org_id=%s', organization.id)

    persisted_maps = get_effective_field_map_records(organization)
    return JsonResponse(
        {
            'configured': salesforce_oauth_is_configured(),
            'connected': bool(connection and connection.is_active and connection.access_token),
            'connection': (
                {
                    'instance_url': connection.instance_url,
                    'external_org_id': connection.external_org_id,
                    'scope': connection.scope,
                    'token_expires_at': connection.token_expires_at.isoformat() if connection.token_expires_at else None,
                    'updated_at': connection.updated_at.isoformat() if connection.updated_at else None,
                }
                if connection and connection.is_active
                else None
            ),
            'mapping_count': len(persisted_maps),
        }
    )


@login_required
@require_http_methods(["POST"])
def salesforce_oauth_start_api(request):
    organization, error = _require_org_admin_for_salesforce(request)
    if error:
        return error
    if not salesforce_oauth_is_configured():
        return _error_response(request, 'Salesforce OAuth is not configured.', 400)

    state = secrets.token_urlsafe(24)
    request.session['salesforce_oauth_state'] = state
    request.session['salesforce_oauth_org_id'] = organization.id
    authorize_url = build_salesforce_authorize_url(state)
    return JsonResponse({'authorize_url': authorize_url, 'state': state})


@login_required
@require_http_methods(["GET"])
def salesforce_oauth_callback_api(request):
    organization, error = _require_org_admin_for_salesforce(request)
    if error:
        return error
    if not salesforce_oauth_is_configured():
        return _error_response(request, 'Salesforce OAuth is not configured.', 400)

    state = request.GET.get('state', '').strip()
    code = request.GET.get('code', '').strip()
    expected_state = request.session.get('salesforce_oauth_state')
    expected_org_id = request.session.get('salesforce_oauth_org_id')
    if not state or state != expected_state or expected_org_id != organization.id:
        return _error_response(request, 'Invalid OAuth state.', 400)
    if not code:
        return _error_response(request, 'Missing Salesforce authorization code.', 400)

    try:
        token_data = exchange_salesforce_code_for_tokens(code)
    except Exception:
        logger.exception('Salesforce OAuth callback failed for org_id=%s', organization.id)
        return _error_response(request, 'Salesforce OAuth exchange failed.', 502)

    connection, _ = SalesforceOrganizationConnection.objects.get_or_create(
        organization=organization,
        defaults={'connected_by': request.user},
    )
    connection.connected_by = request.user
    connection.external_org_id = token_data.external_org_id
    connection.instance_url = token_data.instance_url
    connection.access_token = encrypt_salesforce_token(token_data.access_token)
    connection.refresh_token = (
        encrypt_salesforce_token(token_data.refresh_token) if token_data.refresh_token else connection.refresh_token
    )
    connection.scope = token_data.scope
    connection.token_expires_at = token_data.token_expires_at
    connection.is_active = True
    connection.save()

    request.session.pop('salesforce_oauth_state', None)
    request.session.pop('salesforce_oauth_org_id', None)
    return JsonResponse({'connected': True, 'instance_url': connection.instance_url, 'external_org_id': connection.external_org_id})


@login_required
@require_http_methods(["POST"])
def salesforce_disconnect_api(request):
    organization, error = _require_org_admin_for_salesforce(request)
    if error:
        return error
    connection = SalesforceOrganizationConnection.objects.filter(organization=organization).first()
    if not connection:
        return JsonResponse({'disconnected': True, 'message': 'No active Salesforce connection.'})

    connection.is_active = False
    connection.access_token = ''
    connection.refresh_token = ''
    connection.scope = ''
    connection.token_expires_at = None
    connection.save(update_fields=['is_active', 'access_token', 'refresh_token', 'scope', 'token_expires_at', 'updated_at'])
    return JsonResponse({'disconnected': True})


@login_required
@require_http_methods(["GET", "PUT"])
def salesforce_field_map_api(request):
    organization, error = _require_org_admin_for_salesforce(request)
    if error:
        return error

    if request.method == 'GET':
        persisted = list(
            OrganizationContractFieldMap.objects.filter(organization=organization, is_active=True)
            .values('canonical_field', 'salesforce_object', 'salesforce_field', 'is_required', 'transform_rule')
            .order_by('canonical_field')
        )
        mappings = persisted or default_field_map_records()
        return JsonResponse({'mappings': mappings, 'source': 'database' if persisted else 'default'})

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return _error_response(request, 'Invalid JSON body.', 400)
    mappings = payload.get('mappings')
    if not isinstance(mappings, list) or not mappings:
        return _error_response(request, 'mappings must be a non-empty list.', 400)

    seen_fields = set()
    allowed_fields = set(CANONICAL_CONTRACT_FIELDS)
    normalized = []
    for item in mappings:
        if not isinstance(item, dict):
            return _error_response(request, 'Each mapping must be an object.', 400)
        canonical_field = str(item.get('canonical_field', '')).strip()
        salesforce_field = str(item.get('salesforce_field', '')).strip()
        salesforce_object = str(item.get('salesforce_object', '')).strip() or 'Opportunity'
        transform_rule = str(item.get('transform_rule', '')).strip()
        is_required = bool(item.get('is_required', False))
        if not canonical_field or not salesforce_field:
            return _error_response(request, 'canonical_field and salesforce_field are required.', 400)
        if canonical_field not in allowed_fields:
            return _error_response(request, f'Unsupported canonical_field: {canonical_field}', 400)
        if canonical_field in seen_fields:
            return _error_response(request, f'Duplicate canonical_field: {canonical_field}', 400)
        seen_fields.add(canonical_field)
        normalized.append(
            {
                'canonical_field': canonical_field,
                'salesforce_field': salesforce_field,
                'salesforce_object': salesforce_object,
                'transform_rule': transform_rule,
                'is_required': is_required,
            }
        )

    active_fields = [item['canonical_field'] for item in normalized]
    OrganizationContractFieldMap.objects.filter(organization=organization).exclude(canonical_field__in=active_fields).update(
        is_active=False,
        updated_by=request.user,
    )
    for item in normalized:
        mapping, _ = OrganizationContractFieldMap.objects.get_or_create(
            organization=organization,
            canonical_field=item['canonical_field'],
            defaults={'created_by': request.user},
        )
        mapping.salesforce_field = item['salesforce_field']
        mapping.salesforce_object = item['salesforce_object']
        mapping.transform_rule = item['transform_rule']
        mapping.is_required = item['is_required']
        mapping.is_active = True
        mapping.updated_by = request.user
        mapping.save()

    return JsonResponse({'updated': len(normalized)})


@login_required
@require_http_methods(["POST"])
def salesforce_ingest_preview_api(request):
    organization, error = _require_org_admin_for_salesforce(request)
    if error:
        return error

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return _error_response(request, 'Invalid JSON body.', 400)

    records = payload.get('records')
    dry_run = bool(payload.get('dry_run', True))
    if not isinstance(records, list):
        return _error_response(request, 'records must be a list.', 400)

    summary = ingest_salesforce_records(organization, records, dry_run=dry_run)
    return JsonResponse({'summary': summary, 'dry_run': dry_run})


@login_required
@require_http_methods(["POST"])
def salesforce_sync_api(request):
    organization, error = _require_org_admin_for_salesforce(request)
    if error:
        return error

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return _error_response(request, 'Invalid JSON body.', 400)

    connection = SalesforceOrganizationConnection.objects.filter(organization=organization, is_active=True).first()
    if connection is None:
        return _error_response(request, 'No active Salesforce connection.', 400)

    dry_run = bool(payload.get('dry_run', False))
    limit = payload.get('limit', getattr(settings, 'SALESFORCE_SYNC_DEFAULT_LIMIT', 200))
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        return _error_response(request, 'limit must be an integer.', 400)
    if limit <= 0 or limit > 2000:
        return _error_response(request, 'limit must be between 1 and 2000.', 400)

    try:
        run = create_salesforce_sync_run(
            organization=organization,
            connection=connection,
            trigger_source=SalesforceSyncRun.TriggerSource.API,
            dry_run=dry_run,
            limit=limit,
            triggered_by=request.user,
        )
    except SalesforceSyncError as exc:
        return _error_response(request, str(exc), 409)

    try:
        summary = sync_salesforce_connection(connection, dry_run=dry_run, limit=limit)
    except Exception:
        logger.exception('Salesforce sync failed for org_id=%s', organization.id)
        run.status = SalesforceSyncRun.Status.FAILED
        run.error_message = 'Salesforce sync failed.'
        run.completed_at = timezone.now()
        run.save(update_fields=['status', 'error_message', 'completed_at'])
        queue_webhook_event(
            organization=organization,
            event_type='salesforce.sync.failed',
            payload={
                'run_id': run.id,
                'status': run.status,
                'error_message': run.error_message,
                'dry_run': dry_run,
                'limit': limit,
            },
        )
        return _error_response(request, 'Salesforce sync failed.', 502)

    run.status = SalesforceSyncRun.Status.SUCCESS
    run.source_object = str(summary.get('source_object', '') or '')
    run.fetched_records = int(summary.get('fetched_records', 0) or 0)
    run.created_count = int(summary.get('created', 0) or 0)
    run.updated_count = int(summary.get('updated', 0) or 0)
    run.skipped_count = int(summary.get('skipped', 0) or 0)
    run.error_count = len(summary.get('errors') or [])
    run.summary = summary
    run.completed_at = timezone.now()
    run.save(
        update_fields=[
            'status',
            'source_object',
            'fetched_records',
            'created_count',
            'updated_count',
            'skipped_count',
            'error_count',
            'summary',
            'completed_at',
        ]
    )
    queue_webhook_event(
        organization=organization,
        event_type='salesforce.sync.completed',
        payload={
            'run_id': run.id,
            'status': run.status,
            'dry_run': dry_run,
            'summary': summary,
        },
    )
    return JsonResponse({'summary': summary, 'dry_run': dry_run})


@login_required
@require_http_methods(["GET"])
def salesforce_sync_runs_api(request):
    organization, error = _require_org_admin_for_salesforce(request)
    if error:
        return error

    limit = request.GET.get('limit', 20)
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        return _error_response(request, 'limit must be an integer.', 400)
    limit = max(1, min(limit, 100))

    runs = (
        SalesforceSyncRun.objects.filter(organization=organization)
        .select_related('triggered_by')
        .order_by('-started_at')[:limit]
    )
    payload = []
    for run in runs:
        payload.append(
            {
                'id': run.id,
                'status': run.status,
                'trigger_source': run.trigger_source,
                'dry_run': run.dry_run,
                'limit_applied': run.limit_applied,
                'source_object': run.source_object,
                'fetched_records': run.fetched_records,
                'created_count': run.created_count,
                'updated_count': run.updated_count,
                'skipped_count': run.skipped_count,
                'error_count': run.error_count,
                'error_message': run.error_message,
                'started_at': run.started_at.isoformat() if run.started_at else None,
                'completed_at': run.completed_at.isoformat() if run.completed_at else None,
                'triggered_by': run.triggered_by.username if run.triggered_by else None,
            }
        )
    return JsonResponse({'runs': payload})


@login_required
@require_http_methods(["POST"])
def netsuite_sync_api(request):
    organization, error = _require_org_admin_for_salesforce(request)
    if error:
        return error

    if not netsuite_is_configured():
        return _error_response(request, 'NetSuite integration is not configured.', 400)

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return _error_response(request, 'Invalid JSON body.', 400)

    dry_run = bool(payload.get('dry_run', False))
    limit = payload.get('limit', 200)
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        return _error_response(request, 'limit must be an integer.', 400)
    if limit <= 0 or limit > 2000:
        return _error_response(request, 'limit must be between 1 and 2000.', 400)

    try:
        records = fetch_netsuite_records(limit=limit)
    except NetSuiteSyncError as exc:
        return _error_response(request, str(exc), 502)

    if dry_run:
        summary = {'total_records': len(records), 'created': 0, 'updated': 0, 'skipped': 0, 'errors': []}
        for index, record in enumerate(records):
            try:
                mapped = map_netsuite_record(record)
                source_id = str(mapped.get('source_system_id', '') or '').strip()
                title = str(mapped.get('contract_title', '') or '').strip()
                if not source_id or not title:
                    summary['skipped'] += 1
                    continue
                exists = Contract.objects.filter(
                    organization=organization,
                    source_system='netsuite',
                    source_system_id=source_id,
                ).exists()
                if exists:
                    summary['updated'] += 1
                else:
                    summary['created'] += 1
            except Exception as exc:
                summary['errors'].append({'index': index, 'error': str(exc)})
    else:
        summary = ingest_netsuite_records(organization, records)

    summary['fetched_records'] = len(records)
    summary['dry_run'] = dry_run
    summary['source'] = 'netsuite_api'
    return JsonResponse({'summary': summary, 'dry_run': dry_run})


@login_required
@require_http_methods(["GET"])
def webhook_deliveries_api(request):
    organization, error = _require_org_admin_for_salesforce(request)
    if error:
        return error

    limit = request.GET.get('limit', 50)
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        return _error_response(request, 'limit must be an integer.', 400)
    limit = max(1, min(limit, 200))

    deliveries = (
        WebhookDelivery.objects.filter(organization=organization)
        .select_related('endpoint')
        .order_by('-created_at')[:limit]
    )
    payload = []
    for item in deliveries:
        payload.append(
            {
                'id': item.id,
                'endpoint_id': item.endpoint_id,
                'endpoint_name': item.endpoint.name if item.endpoint else '',
                'event_type': item.event_type,
                'status': item.status,
                'attempt_count': item.attempt_count,
                'max_attempts': item.max_attempts,
                'response_status': item.response_status,
                'error_message': item.error_message,
                'next_attempt_at': item.next_attempt_at.isoformat() if item.next_attempt_at else None,
                'dead_lettered_at': item.dead_lettered_at.isoformat() if item.dead_lettered_at else None,
                'created_at': item.created_at.isoformat() if item.created_at else None,
            }
        )
    return JsonResponse({'deliveries': payload})


@csrf_exempt
@require_http_methods(["POST"])
def esign_webhook_api(request):
    secret = str(getattr(settings, 'ESIGN_WEBHOOK_SECRET', '') or '').strip()
    if not secret:
        return _error_response(request, 'E-sign webhook secret is not configured.', 503)
    provided_secret = str(request.headers.get('X-Esign-Webhook-Secret', '') or '').strip()
    if not provided_secret or not secrets.compare_digest(secret, provided_secret):
        return _error_response(request, 'Invalid webhook secret.', 403)

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return _error_response(request, 'Invalid JSON body.', 400)
    events = payload if isinstance(payload, list) else [payload]
    if not all(isinstance(event, dict) for event in events):
        return _error_response(request, 'Events payload must be an object or list of objects.', 400)

    summary = {
        'total_events': len(events),
        'applied': 0,
        'duplicate': 0,
        'stale': 0,
        'errors': [],
    }
    for index, event in enumerate(events):
        signature_request = None
        signature_request_id = event.get('signature_request_id')
        external_id = str(event.get('external_id') or '').strip()
        if signature_request_id:
            signature_request = SignatureRequest.objects.filter(id=signature_request_id).first()
        if signature_request is None and external_id:
            signature_request = SignatureRequest.objects.filter(external_id=external_id).order_by('-id').first()
        if signature_request is None:
            summary['errors'].append({'index': index, 'error': 'Signature request not found.'})
            continue

        try:
            result = apply_esign_event(signature_request, event, dry_run=False)
        except ESignReconciliationError as exc:
            summary['errors'].append({'index': index, 'error': str(exc)})
            continue

        result_key = str(result.get('result') or '')
        if result_key in summary:
            summary[result_key] += 1
        else:
            summary['errors'].append({'index': index, 'error': f'Unknown reconciliation result: {result_key}'})

    return JsonResponse({'summary': summary})


# Documenso event type → internal status string (matches PROVIDER_STATUS_MAP in esign.py)
_DOCUMENSO_EVENT_STATUS = {
    'DOCUMENT_SENT': 'sent',
    'DOCUMENT_OPENED': 'opened',
    'DOCUMENT_SIGNED': 'signed',
    'DOCUMENT_RECIPIENT_COMPLETED': 'signed',
    'DOCUMENT_COMPLETED': 'completed',
    'DOCUMENT_REJECTED': 'declined',
    'DOCUMENT_CANCELLED': 'cancelled',
    # Legacy V1 event names retained for in-flight envelopes.
    'document.sent': 'sent',
    'document.opened': 'opened',
    'document.signed': 'signed',
    'document.completed': 'completed',
    'document.declined': 'declined',
    'document.cancelled': 'cancelled',
    'document.expired': 'expired',
}


@csrf_exempt
@require_http_methods(["POST"])
def documenso_esign_webhook_api(request):
    """Receive Documenso webhook events and reconcile signature request status.

    Documenso sends an X-Documenso-Secret header containing the webhook secret
    configured in the Documenso dashboard. We verify it with constant-time
    comparison to prevent timing attacks.

    The externalId on the Documenso document is set to
    'clmone-{org_id}-{sig_req_id}' by DocumensoSignatureProvider.send().
    Legacy records created before the rename use 'cms-aegis-{org_id}-{sig_req_id}'.
    Both formats are accepted here for backwards compatibility with in-flight signatures.
    """
    secret = str(getattr(settings, 'ESIGN_DOCUMENSO_WEBHOOK_SECRET', '') or '').strip()
    if not secret:
        return HttpResponse('Webhook not configured', status=400)

    provided = str(request.headers.get('X-Documenso-Secret', '') or '').strip()
    if not provided or not secrets.compare_digest(secret, provided):
        return HttpResponse('Invalid webhook secret', status=401)

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return HttpResponse('Invalid JSON', status=400)

    event_type = str(payload.get('event') or '').strip()
    internal_status = _DOCUMENSO_EVENT_STATUS.get(event_type)
    if not internal_status:
        # Unknown event type — acknowledge but don't process
        logger.debug('documenso_webhook: unhandled event type %s', event_type)
        return JsonResponse({'received': True, 'processed': False})

    data = payload.get('payload') or payload.get('data') or {}
    doc_id = str(data.get('id') or '').strip()
    external_id = str(data.get('externalId') or '').strip()
    created_at = str(payload.get('createdAt') or '').strip()

    # Look up SignatureRequest: first by our externalId pattern, then by doc id
    sig_req = None
    # Accept both new 'clmone-' prefix and legacy 'cms-aegis-' prefix for in-flight signatures
    if external_id.startswith('clmone-') or external_id.startswith('cms-aegis-'):
        parts = external_id.split('-')
        # clmone-{org}-{id} → 3 parts; cms-aegis-{org}-{id} → 4 parts
        if len(parts) in (3, 4):
            try:
                sig_req = SignatureRequest.objects.filter(id=int(parts[-1])).first()
            except (ValueError, TypeError):
                pass
    if sig_req is None and doc_id:
        sig_req = SignatureRequest.objects.filter(external_id=doc_id).order_by('-id').first()

    if sig_req is None:
        logger.warning('documenso_webhook: no SignatureRequest found for doc_id=%s externalId=%s', doc_id, external_id)
        return JsonResponse({'received': True, 'processed': False, 'reason': 'signature_request_not_found'})

    event = {
        'event_id': f'documenso-{event_type}-{doc_id}-{created_at}',
        'provider': 'documenso',
        'external_id': doc_id,
        'status': internal_status,
        'event_at': created_at or None,
    }

    # For declined events, pull reason from recipient if available
    recipients = data.get('recipients') or []
    declined = next((r for r in recipients if r.get('signingStatus', '').upper() == 'REJECTED'), None)
    if declined:
        event['decline_reason'] = declined.get('rejectionReason', '')

    try:
        result = apply_esign_event(sig_req, event, dry_run=False)
    except ESignReconciliationError as exc:
        logger.warning('documenso_webhook: reconciliation error: %s', exc)
        return JsonResponse({'received': True, 'processed': False, 'error': str(exc)})

    return JsonResponse({'received': True, 'processed': True, 'result': result.get('result')})


@login_required
@require_http_methods(['GET'])
def api_webhook_failed(request):
    org = get_user_organization(request.user)
    svc = get_webhook_management_service()
    return JsonResponse({'deliveries': svc.get_failed_deliveries(org)})


@login_required
@require_http_methods(['POST'])
def api_webhook_retry(request, delivery_id):
    org = get_user_organization(request.user)
    svc = get_webhook_management_service()
    try:
        result = svc.retry_delivery(delivery_id, org)
        return JsonResponse(result)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=404)


@login_required
@require_http_methods(['GET'])
def api_webhook_dlq(request):
    org = get_user_organization(request.user)
    svc = get_webhook_management_service()
    return JsonResponse({'deliveries': svc.get_dead_letter_queue(org)})


@login_required
@require_http_methods(['GET'])
def api_webhook_diagnostics(request):
    org = get_user_organization(request.user)
    svc = get_webhook_management_service()
    return JsonResponse(svc.get_diagnostics(org))


@login_required
@require_http_methods(['POST'])
def api_webhook_requeue(request, delivery_id):
    org = get_user_organization(request.user)
    svc = get_webhook_management_service()
    try:
        result = svc.requeue_dead_letter(delivery_id, org)
        return JsonResponse(result)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=404)


@login_required
@require_http_methods(['POST'])
def api_import_contracts_csv(request):
    org = get_user_organization(request.user)
    svc = get_inbound_import_service()
    csv_text = request.body.decode('utf-8', errors='replace')
    dry_run = request.GET.get('dry_run', '').lower() in ('true', '1', 'yes')
    result = svc.import_contracts_from_csv(org, csv_text, request.user, dry_run=dry_run)
    return JsonResponse({
        'imported_count': result.imported_count,
        'skipped_count': result.skipped_count,
        'errors': result.errors,
        'dry_run': result.dry_run,
    })


@login_required
@require_http_methods(['POST'])
def api_import_contracts_json(request):
    org = get_user_organization(request.user)
    svc = get_inbound_import_service()
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, Exception):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    if not isinstance(data, list):
        return JsonResponse({'error': 'Expected a JSON array'}, status=400)
    dry_run = request.GET.get('dry_run', '').lower() in ('true', '1', 'yes')
    result = svc.import_contracts_from_json(org, data, request.user, dry_run=dry_run)
    return JsonResponse({
        'imported_count': result.imported_count,
        'skipped_count': result.skipped_count,
        'errors': result.errors,
        'dry_run': result.dry_run,
    })


@login_required
@require_http_methods(['GET'])
def api_crm_sync_status(request):
    org = get_user_organization(request.user)
    svc = get_crm_sync_service()
    return JsonResponse(svc.get_sync_status(org))


@login_required
@require_http_methods(['GET'])
def api_crm_list_integrations(request):
    org = get_user_organization(request.user)
    svc = get_crm_sync_service()
    return JsonResponse({'integrations': svc.list_available_integrations(org)})


@login_required
@require_http_methods(['POST'])
def api_crm_trigger_sync(request):
    org = get_user_organization(request.user)
    svc = get_crm_sync_service()
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, Exception):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    provider = data.get('provider', 'salesforce')
    try:
        result = svc.trigger_sync(org, provider, request.user)
        return JsonResponse(result)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)

