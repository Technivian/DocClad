"""Pilot monitoring helpers and daily health summary (no contract content)."""
from __future__ import annotations

import json
from datetime import datetime, time, timedelta
from typing import Any, Dict

from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone

from contracts.models import (
    AuditLog,
    Contract,
    ExceptionDecision,
    ExceptionRequest,
    Organization,
    OrganizationMembership,
)
from contracts.observability import request_metrics_snapshot
from contracts.services.exception_dual_write import (
    AUTHORIZED_SOURCES,
    EVENT_DUAL_WRITE_FAILED,
    EVENT_SECURITY_GATE_BLOCKED,
)
from contracts.services.exception_canonical_read import (
    EVENT_CANONICAL_READ_DENIED,
    EVENT_CANONICAL_READ_FALLBACK,
    EVENT_CANONICAL_READ_USED,
)


def _day_bounds(day=None):
    day = day or timezone.localdate()
    start = timezone.make_aware(datetime.combine(day, time.min))
    end = start + timedelta(days=1)
    return start, end


def pilot_feature_flag_state() -> Dict[str, Any]:
    return {
        'CONTROLLED_PILOT_ENABLED': bool(getattr(settings, 'CONTROLLED_PILOT_ENABLED', False)),
        'GEMINI_AI_ENABLED': bool(getattr(settings, 'GEMINI_AI_ENABLED', False)),
        'BILLING_SELF_SERVE_ENABLED': bool(getattr(settings, 'BILLING_SELF_SERVE_ENABLED', True)),
        'TRUST_ACCOUNTING_ENABLED': bool(getattr(settings, 'TRUST_ACCOUNTING_ENABLED', True)),
        'FINANCE_APPROVAL_THRESHOLD': str(
            getattr(settings, 'FINANCE_APPROVAL_THRESHOLD', None)
            or '100000'
        ),
        'RATELIMIT_ENABLED': bool(getattr(settings, 'RATELIMIT_ENABLED', True)),
        'LOGIN_RATE_LIMIT_REQUESTS': getattr(settings, 'LOGIN_RATE_LIMIT_REQUESTS', None),
        'EXCEPTION_DUAL_WRITE_ENABLED': bool(
            getattr(settings, 'EXCEPTION_DUAL_WRITE_ENABLED', False)
        ),
        'EXCEPTION_DUAL_WRITE_ORG_ALLOWLIST': getattr(
            settings, 'EXCEPTION_DUAL_WRITE_ORG_ALLOWLIST', ''
        ),
        'EXCEPTION_CANONICAL_READ_ENABLED': bool(
            getattr(settings, 'EXCEPTION_CANONICAL_READ_ENABLED', False)
        ),
        'EXCEPTION_CANONICAL_READ_ORG_ALLOWLIST': getattr(
            settings, 'EXCEPTION_CANONICAL_READ_ORG_ALLOWLIST', ''
        ),
    }


def _exception_dual_write_health(*, organization, start, end, audits) -> Dict[str, Any]:
    """Return metadata-only PAR-EXC-001 counters and stop-condition indicators."""
    source_counts = {source: 0 for source in sorted(AUTHORIZED_SOURCES)}
    empty = {
        'actions_by_source': source_counts,
        'canonical_requests_created': 0,
        'canonical_decisions_created': 0,
        'submitted_without_decision': 0,
        'dual_write_failures': 0,
        'security_gate_blocks': 0,
        'cross_tenant_denials': 0,
        'duplicate_correlation_groups': 0,
        'requests_with_multiple_decisions': 0,
        'active_missing_owner_or_expiry': 0,
        'canonical_read_used': 0,
        'canonical_read_fallbacks': 0,
        'canonical_read_denials': 0,
        'stop_required': False,
        'stop_reasons': [],
    }
    if organization is None:
        return empty

    requests = ExceptionRequest.objects.filter(
        organization=organization,
        created_at__gte=start,
        created_at__lt=end,
        legacy_source__in=AUTHORIZED_SOURCES,
    )
    decisions = ExceptionDecision.objects.filter(
        organization=organization,
        created_at__gte=start,
        created_at__lt=end,
        exception_request__legacy_source__in=AUTHORIZED_SOURCES,
    )

    for row in requests.values('legacy_source').annotate(count=Count('id')):
        source_counts[row['legacy_source']] = row['count']

    duplicate_correlation_groups = (
        requests.exclude(correlation_id='')
        .values('legacy_source', 'correlation_id')
        .annotate(count=Count('id'))
        .filter(count__gt=1)
        .count()
    )
    requests_with_multiple_decisions = (
        requests.annotate(decision_count=Count('decisions'))
        .filter(decision_count__gt=1)
        .count()
    )
    active_missing_owner_or_expiry = requests.filter(
        status__in=[ExceptionRequest.Status.APPROVED, ExceptionRequest.Status.ACTIVE],
        is_permanent=False,
    ).filter(Q(owner__isnull=True) | Q(expires_at__isnull=True)).count()

    dual_write_failures = audits.filter(event_type=EVENT_DUAL_WRITE_FAILED).count()
    security_gate_blocks = audits.filter(event_type=EVENT_SECURITY_GATE_BLOCKED).count()
    cross_tenant_denials = audits.filter(event_type='exception.cross_tenant.denied').count()
    canonical_read_used = audits.filter(event_type=EVENT_CANONICAL_READ_USED).count()
    canonical_read_fallbacks = audits.filter(event_type=EVENT_CANONICAL_READ_FALLBACK).count()
    canonical_read_denials = audits.filter(event_type=EVENT_CANONICAL_READ_DENIED).count()
    submitted_without_decision = requests.filter(
        status=ExceptionRequest.Status.SUBMITTED,
        decisions__isnull=True,
    ).count()

    stop_reasons = []
    if dual_write_failures:
        stop_reasons.append('dual_write_failure')
    if security_gate_blocks:
        stop_reasons.append('unauthorized_critical_bypass_blocked')
    if cross_tenant_denials:
        stop_reasons.append('cross_tenant_anomaly')
    if canonical_read_denials:
        stop_reasons.append('canonical_read_cross_tenant_denial')
    if duplicate_correlation_groups:
        stop_reasons.append('duplicate_correlation')
    if requests_with_multiple_decisions:
        stop_reasons.append('duplicate_canonical_decision')
    if active_missing_owner_or_expiry:
        stop_reasons.append('active_missing_owner_or_expiry')

    return {
        'actions_by_source': source_counts,
        'canonical_requests_created': requests.count(),
        'canonical_decisions_created': decisions.count(),
        'submitted_without_decision': submitted_without_decision,
        'dual_write_failures': dual_write_failures,
        'security_gate_blocks': security_gate_blocks,
        'cross_tenant_denials': cross_tenant_denials,
        'duplicate_correlation_groups': duplicate_correlation_groups,
        'requests_with_multiple_decisions': requests_with_multiple_decisions,
        'active_missing_owner_or_expiry': active_missing_owner_or_expiry,
        'canonical_read_used': canonical_read_used,
        'canonical_read_fallbacks': canonical_read_fallbacks,
        'canonical_read_denials': canonical_read_denials,
        'stop_required': bool(stop_reasons),
        'stop_reasons': stop_reasons,
    }


def build_pilot_daily_health(organization: Organization | None = None, day=None) -> Dict[str, Any]:
    """Aggregate operational health without contract text or credentials."""
    start, end = _day_bounds(day)
    org = organization
    if org is None:
        org = Organization.objects.filter(slug='controlled-pilot-org').first()

    audits = AuditLog.objects.filter(timestamp__gte=start, timestamp__lt=end)
    contracts = Contract.objects.filter(created_at__gte=start, created_at__lt=end)
    if org is not None:
        audits = audits.filter(organization=org)
        contracts = contracts.filter(organization=org)

    # Event-type heuristics from existing AuditLog payloads (no content fields).
    legal_submits = audits.filter(
        Q(changes__event__icontains='legal')
        | Q(object_repr__icontains='Legal')
        | Q(action__icontains='submit')
    ).filter(Q(changes__approval_step='LEGAL') | Q(changes__event__icontains='msa') | Q(model_name='ApprovalRequest')).count()

    finance_submits = audits.filter(
        Q(changes__approval_step='FINANCE')
        | Q(changes__event__icontains='finance')
    ).count()

    exports = audits.filter(
        Q(changes__event__icontains='export')
        | Q(action__icontains='export')
        | Q(object_repr__icontains='export')
    ).count()

    lifecycle_failures = audits.filter(
        Q(outcome=AuditLog.Outcome.FAILURE)
        & (
            Q(changes__event__icontains='lifecycle')
            | Q(event_type__icontains='lifecycle')
        )
    ).count()

    authz_failures = audits.filter(
        Q(outcome=AuditLog.Outcome.FAILURE)
        & (
            Q(action__icontains='denied')
            | Q(changes__event__icontains='forbidden')
            | Q(changes__event__icontains='unauthorized')
        )
    ).count()

    audit_write_failures = audits.filter(
        Q(changes__event__icontains='audit') & Q(outcome=AuditLog.Outcome.FAILURE)
    ).count()

    ai_denials = audits.filter(
        Q(changes__event__icontains='ai')
        & (
            Q(outcome=AuditLog.Outcome.FAILURE)
            | Q(changes__event__icontains='denied')
            | Q(changes__event__icontains='disabled')
        )
    ).count()

    failed_actions = audits.filter(outcome=AuditLog.Outcome.FAILURE).count()
    login_failures = audits.filter(
        Q(action__icontains='login') & Q(outcome=AuditLog.Outcome.FAILURE)
    ).count()

    active_users = 0
    if org is not None:
        active_users = (
            OrganizationMembership.objects.filter(organization=org, is_active=True)
            .values('user_id')
            .distinct()
            .count()
        )

    metrics = request_metrics_snapshot()
    summary = {
        'date': str(start.date()),
        'organization': org.slug if org else None,
        'feature_flags': pilot_feature_flag_state(),
        'active_users': active_users,
        'contracts_created': contracts.count(),
        'contracts_created_by_type': list(
            contracts.values('contract_type').annotate(count=Count('id')).order_by('contract_type')
        ),
        'workflow_completions_approx': audits.filter(
            Q(changes__event__icontains='completed')
            | Q(action='UPDATE', changes__event__icontains='workflow')
        ).count(),
        'failed_actions': failed_actions,
        'login_failures': login_failures,
        'http_status_counts': metrics.get('status_counts', {}),
        'msa_legal_submissions_approx': legal_submits,
        'msa_finance_submissions_approx': finance_submits,
        'exports_approx': exports,
        'lifecycle_transition_failures': lifecycle_failures,
        'authorization_failures': authz_failures,
        'audit_event_creation_failures': audit_write_failures,
        'ai_usage_and_policy_denials_approx': ai_denials,
        'exception_dual_write': _exception_dual_write_health(
            organization=org,
            start=start,
            end=end,
            audits=audits,
        ),
        'unresolved_incidents': None,  # operator-maintained in ops log
        'support_requests': None,  # operator-maintained in ops log
        'routing_anomalies': None,  # compare Finance submits vs threshold matrix in review
        'audit_anomalies': audit_write_failures,
        'notes': (
            'Counts are derived from AuditLog metadata and request metrics. '
            'Contract content, credentials, and secrets are never included.'
        ),
    }
    return summary


def format_pilot_daily_health(summary: Dict[str, Any]) -> str:
    return json.dumps(summary, indent=2, sort_keys=True, default=str)
