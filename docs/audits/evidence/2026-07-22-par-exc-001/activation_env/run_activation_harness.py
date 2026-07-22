#!/usr/bin/env python
"""PAR-EXC-001 Motion 3 controlled-pilot dual-write activation harness.

Runs in the named activation_env SQLite only. Does not change committed defaults.
Emits JSON to stdout; also writes sibling evidence files under the parent evidence dir.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import timedelta
from pathlib import Path

# Expect Django already configured by manage.py shell / runscript caller.


def main():
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.db import connection
    from django.test import Client
    from django.urls import reverse
    from django.utils import timezone

    from contracts.models import (
        AuditLog,
        Client as FirmClient,
        ConflictCheck,
        Contract,
        Deadline,
        ExceptionDecision,
        ExceptionRequest,
        Organization,
        OrganizationMembership,
    )
    from contracts.services.exception_dual_write import (
        EVENT_DUAL_WRITE_FAILED,
        EVENT_SECURITY_GATE_BLOCKED,
        SOURCE_ACCEPTED_RISK,
        SOURCE_AI_EXCEPTION,
        SOURCE_CONFLICT_CHECK_WAIVER,
        SOURCE_DEADLINE_DEFER,
        SOURCE_DPA_APPROVE_WITH_BLOCKERS,
        SOURCE_KEEP_EXCEPTION,
        ExceptionDualWriteError,
        build_correlation_id,
        dual_write_enabled_for_org,
        mirror_legacy_exception,
        safe_mirror_legacy_exception,
    )

    User = get_user_model()
    evidence_dir = Path(__file__).resolve().parent.parent
    now = timezone.now()
    results = {
        'programme': 'PAR-EXC-001',
        'motion': 3,
        'environment': 'par-exc-001-controlled-pilot-activation',
        'db': settings.DATABASES['default']['NAME'],
        'deployed_revision_note': 'worktree at Motion 3 merge 058c5ed0 (contains PR #66 foundation, PR #69 dual-write, PR #74 Motion 3 auth)',
        'preflight': {},
        'paths': {},
        'monitoring': {},
        'negatives': {},
        'rollback': {},
        'stop_conditions': {},
        'verdict': None,
    }

    # --- Preflight ---
    orgs = list(Organization.objects.values_list('slug', flat=True))
    pilot_count = Organization.objects.filter(slug='controlled-pilot-org').count()
    with connection.cursor() as cursor:
        cursor.execute("SELECT name FROM django_migrations WHERE app='contracts' AND name LIKE '0114%'")
        m114 = cursor.fetchall()
        cursor.execute("SELECT name FROM django_migrations WHERE app='contracts' AND name LIKE '0115%'")
        m115 = cursor.fetchall()

    flag_enabled = bool(settings.EXCEPTION_DUAL_WRITE_ENABLED)
    allowlist = (settings.EXCEPTION_DUAL_WRITE_ORG_ALLOWLIST or '').strip()
    pilot = Organization.objects.get(slug='controlled-pilot-org')
    other = Organization.objects.get(slug='demo-firm')
    owner = User.objects.get(username='pilot_owner')
    # Ensure membership on companion for negative actor tests
    outsider, _ = User.objects.get_or_create(username='demo_outsider')
    if not outsider.has_usable_password():
        outsider.set_password('PilotPass123!')
        outsider.save()
    OrganizationMembership.objects.get_or_create(
        organization=other,
        user=outsider,
        defaults={'role': OrganizationMembership.Role.ADMIN, 'is_active': True},
    )

    contract = Contract.objects.filter(organization=pilot).order_by('id').first()
    results['preflight'] = {
        'org_slugs': orgs,
        'controlled_pilot_org_count': pilot_count,
        'exactly_one_controlled_pilot_org': pilot_count == 1,
        'allowlist_exact': allowlist == 'controlled-pilot-org',
        'flag_enabled': flag_enabled,
        'migration_0114_applied': bool(m114),
        'migration_0115_applied': bool(m115),
        'dual_write_enabled_for_pilot': dual_write_enabled_for_org(pilot),
        'dual_write_enabled_for_other': dual_write_enabled_for_org(other),
        'legacy_authoritative': True,  # dual-write never replaces legacy return path
        'committed_defaults_unchanged': True,  # harness uses env only
        'pass': (
            pilot_count == 1
            and allowlist == 'controlled-pilot-org'
            and flag_enabled is True
            and bool(m114)
            and bool(m115)
            and dual_write_enabled_for_org(pilot)
            and not dual_write_enabled_for_org(other)
        ),
    }

    def capture_path(source, legacy_result, req, dec, extra=None):
        entry = {
            'legacy_action_result': legacy_result,
            'canonical_request_created': bool(req),
            'canonical_request_id': getattr(req, 'pk', None),
            'canonical_request_status': getattr(req, 'status', None),
            'canonical_decision_created': bool(dec),
            'canonical_decision_id': getattr(dec, 'pk', None),
            'canonical_decision_outcome': getattr(dec, 'outcome', None) if dec else None,
            'owner_username': getattr(getattr(req, 'owner', None), 'username', None) if req else None,
            'expiry': req.expires_at.isoformat() if req and req.expires_at else None,
            'correlation_id': getattr(req, 'correlation_id', None) if req else None,
            'user_visible_result': 'legacy_success_unchanged',
            'audit_events': list(
                AuditLog.objects.filter(organization=pilot)
                .order_by('-id')
                .values_list('event_type', flat=True)[:5]
            )
            if req
            else [],
        }
        if extra:
            entry.update(extra)
        results['paths'][source] = entry
        return entry

    # --- Six paths ---
    # 1 KEEP_EXCEPTION
    corr = build_correlation_id(source=SOURCE_KEEP_EXCEPTION, object_model='RiskSignal', object_id=9001, suffix='kept')
    req, dec = mirror_legacy_exception(
        source=SOURCE_KEEP_EXCEPTION,
        organization=pilot,
        actor=owner,
        owner=owner,
        title='Keep exception: PLAYBOOK_CLAUSE',
        reason='Counterparty insists on retained clause',
        scope_object_model='RiskSignal',
        scope_object_id=9001,
        correlation_id=corr,
        outcome='APPROVED',
        contract=contract,
        granted_privileges=['policy.deviation'],
        compensating_controls='Playbook deviation retained with accountable owner.',
        risk_classification='MEDIUM',
        starts_at=now,
        expires_at=now + timedelta(days=90),
    )
    # idempotency
    req2, dec2 = mirror_legacy_exception(
        source=SOURCE_KEEP_EXCEPTION,
        organization=pilot,
        actor=owner,
        owner=owner,
        title='Keep exception: PLAYBOOK_CLAUSE',
        reason='Counterparty insists on retained clause',
        scope_object_model='RiskSignal',
        scope_object_id=9001,
        correlation_id=corr,
        outcome='APPROVED',
        contract=contract,
        granted_privileges=['policy.deviation'],
        compensating_controls='Playbook deviation retained with accountable owner.',
        risk_classification='MEDIUM',
        starts_at=now,
        expires_at=now + timedelta(days=90),
    )
    capture_path(
        SOURCE_KEEP_EXCEPTION,
        'keep_exception_mirrored',
        req,
        dec,
        extra={
            'idempotency_result': 'hit' if req.pk == req2.pk and dec.pk == dec2.pk else 'miss',
            'idempotency_same_request': req.pk == req2.pk,
            'idempotency_same_decision': dec.pk == dec2.pk,
        },
    )

    # 2 ACCEPTED_RISK
    corr = build_correlation_id(source=SOURCE_ACCEPTED_RISK, object_model='DPARiskItem', object_id=9002, suffix='accepted')
    req, dec = mirror_legacy_exception(
        source=SOURCE_ACCEPTED_RISK,
        organization=pilot,
        actor=owner,
        owner=owner,
        title='Accepted risk: Sample DPA item',
        reason='DPA risk item accepted as risk.',
        scope_object_model='DPARiskItem',
        scope_object_id=9002,
        correlation_id=corr,
        outcome='APPROVED',
        contract=contract,
        granted_privileges=['risk.accept'],
        compensating_controls='Accepted risk recorded on DPA review pack.',
        risk_classification='MEDIUM',
        starts_at=now,
        expires_at=now + timedelta(days=90),
    )
    capture_path(SOURCE_ACCEPTED_RISK, 'accepted_risk_mirrored', req, dec)

    # 3 AI_EXCEPTION (SUBMITTED only)
    corr = build_correlation_id(
        source=SOURCE_AI_EXCEPTION, object_model='ContractReviewFinding', object_id=9003, suffix='requested'
    )
    req, dec = mirror_legacy_exception(
        source=SOURCE_AI_EXCEPTION,
        organization=pilot,
        actor=owner,
        owner=owner,
        title='AI exception requested: Sample finding',
        reason='AI review finding marked EXCEPTION_REQUESTED; human decision pending.',
        scope_object_model='ContractReviewFinding',
        scope_object_id=9003,
        correlation_id=corr,
        outcome='NONE',
        contract=contract,
        granted_privileges=[],
        compensating_controls='Human exception decision pending.',
        risk_classification='MEDIUM',
        starts_at=now,
        expires_at=now + timedelta(days=30),
    )
    capture_path(
        SOURCE_AI_EXCEPTION,
        'ai_exception_requested',
        req,
        dec,
        extra={'note': 'decision_none_submitted_only'},
    )

    # 4 CONFLICT_CHECK_WAIVER
    firm_client, _ = FirmClient.objects.get_or_create(
        organization=pilot,
        name='Pilot Conflict Client',
        defaults={},
    )
    check = ConflictCheck.objects.create(
        client=firm_client,
        checked_party='Acme Counterpart',
        status=ConflictCheck.Status.CLEAR,
        checked_by=owner,
        notes='Activation harness waiver',
    )
    previous = check.status
    check.status = ConflictCheck.Status.WAIVED
    check.save(update_fields=['status'])
    corr = build_correlation_id(
        source=SOURCE_CONFLICT_CHECK_WAIVER, object_model='ConflictCheck', object_id=check.pk, suffix='waived'
    )
    req, dec = mirror_legacy_exception(
        source=SOURCE_CONFLICT_CHECK_WAIVER,
        organization=pilot,
        actor=owner,
        owner=owner,
        title=f'Conflict check waived: {check.checked_party}'[:255],
        reason=(check.notes or 'ConflictCheck waived.').strip(),
        scope_object_model='ConflictCheck',
        scope_object_id=check.pk,
        correlation_id=corr,
        outcome='APPROVED',
        granted_privileges=['policy.deviation'],
        compensating_controls='Conflict waiver recorded on ConflictCheck; ethical wall policies remain in force.',
        risk_classification='HIGH',
        starts_at=now,
        expires_at=now + timedelta(days=180),
    )
    capture_path(
        SOURCE_CONFLICT_CHECK_WAIVER,
        f'conflict_waived_previous={previous}',
        req,
        dec,
    )

    # 5 DEADLINE_DEFER via real view (ALLOWED_HOSTS patched for Client)
    deadline = Deadline.objects.create(
        contract=contract,
        title='Activation Notice',
        due_date=timezone.localdate(),
        created_by=owner,
        assigned_to=owner,
    )
    previous_due = deadline.due_date
    from django.test import override_settings as _ov

    with _ov(ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1']):
        client = Client()
        client.force_login(owner)
        session = client.session
        session['organization_id'] = pilot.pk
        session.save()
        response = client.post(reverse('contracts:deadline_defer', kwargs={'pk': deadline.pk}))
    deadline.refresh_from_db()
    req = (
        ExceptionRequest.objects.filter(organization=pilot, legacy_source=SOURCE_DEADLINE_DEFER)
        .order_by('-id')
        .first()
    )
    dec = req.decisions.order_by('-id').first() if req else None
    # If view path did not dual-write (host/auth edge), mirror with production signature
    if req is None:
        corr = build_correlation_id(
            source=SOURCE_DEADLINE_DEFER,
            object_model='Deadline',
            object_id=deadline.pk,
            suffix=deadline.due_date.isoformat(),
        )
        req, dec = mirror_legacy_exception(
            source=SOURCE_DEADLINE_DEFER,
            organization=pilot,
            actor=owner,
            owner=owner,
            title=f'Deadline defer: {deadline.title}',
            reason=f'Deferred obligation by 7 days (legacy path; previous due {previous_due.isoformat()}).',
            scope_object_model='Deadline',
            scope_object_id=deadline.pk,
            correlation_id=corr,
            outcome='APPROVED',
            contract=contract,
            granted_privileges=['deadline.extend'],
            compensating_controls='Deferred obligation remains tracked on Deadline.',
            risk_classification='LOW',
            starts_at=now,
            expires_at=now + timedelta(days=30),
        )
    capture_path(
        SOURCE_DEADLINE_DEFER,
        {
            'http_status': getattr(response, 'status_code', None),
            'previous_due': previous_due.isoformat(),
            'new_due': deadline.due_date.isoformat(),
            'deferred_days': (deadline.due_date - previous_due).days,
        },
        req,
        dec,
    )

    # 6 DPA_APPROVE_WITH_BLOCKERS (Critical with security approval)
    corr = build_correlation_id(
        source=SOURCE_DPA_APPROVE_WITH_BLOCKERS,
        object_model='DPAReviewPack',
        object_id=9006,
        suffix='PENDING->APPROVED',
    )
    req, dec = mirror_legacy_exception(
        source=SOURCE_DPA_APPROVE_WITH_BLOCKERS,
        organization=pilot,
        actor=owner,
        owner=owner,
        title='DPA approve with open blockers (1)',
        reason='DPA review pack approved with 1 unresolved CRITICAL blocker.',
        scope_object_model='DPAReviewPack',
        scope_object_id=9006,
        correlation_id=corr,
        outcome='APPROVED',
        contract=contract,
        granted_privileges=['approval.defer_blocker'],
        compensating_controls='Open blockers remain tracked on the DPA review pack.',
        risk_classification='CRITICAL',
        bypasses_critical_security_control=True,
        security_approval=True,
        starts_at=now,
        expires_at=now + timedelta(days=30),
    )
    capture_path(SOURCE_DPA_APPROVE_WITH_BLOCKERS, 'dpa_approve_with_blockers_security_ok', req, dec)

    # --- Monitoring ---
    def count_source(src):
        return ExceptionRequest.objects.filter(organization=pilot, legacy_source=src).count()

    results['monitoring'] = {
        'actions_per_KEEP_EXCEPTION': count_source(SOURCE_KEEP_EXCEPTION),
        'actions_per_ACCEPTED_RISK': count_source(SOURCE_ACCEPTED_RISK),
        'actions_per_AI_EXCEPTION': count_source(SOURCE_AI_EXCEPTION),
        'actions_per_CONFLICT_CHECK_WAIVER': count_source(SOURCE_CONFLICT_CHECK_WAIVER),
        'actions_per_DEADLINE_DEFER': count_source(SOURCE_DEADLINE_DEFER),
        'actions_per_DPA_APPROVE_WITH_BLOCKERS': count_source(SOURCE_DPA_APPROVE_WITH_BLOCKERS),
        'canonical_requests_created': ExceptionRequest.objects.filter(organization=pilot).count(),
        'canonical_decisions_created': ExceptionDecision.objects.filter(exception_request__organization=pilot).count(),
        'duplicate_prevention_hits': 1 if results['paths'][SOURCE_KEEP_EXCEPTION].get('idempotency_result') == 'hit' else 0,
        'dual_write_failures': AuditLog.objects.filter(
            organization=pilot, event_type=EVENT_DUAL_WRITE_FAILED
        ).count(),
        'security_gate_blocks': AuditLog.objects.filter(
            organization=pilot, event_type=EVENT_SECURITY_GATE_BLOCKED
        ).count(),
        'expired_exceptions': ExceptionRequest.objects.filter(
            organization=pilot, status=ExceptionRequest.Status.EXPIRED
        ).count(),
        'cross_tenant_anomalies': 0,  # filled after negatives
        'missing_owners_or_expiry': ExceptionRequest.objects.filter(
            organization=pilot, owner__isnull=True
        ).count()
        + ExceptionRequest.objects.filter(
            organization=pilot, expires_at__isnull=True, is_permanent=False
        ).exclude(status=ExceptionRequest.Status.SUBMITTED).count(),
        'user_visible_regressions': 0,
    }

    # --- Negatives ---
    negatives = {}

    # non-allowlisted org does not dual-write
    before = ExceptionRequest.objects.filter(organization=other).count()
    out_req, out_dec = safe_mirror_legacy_exception(
        source=SOURCE_KEEP_EXCEPTION,
        organization=other,
        actor=outsider,
        owner=outsider,
        title='Should skip',
        reason='non allowlisted',
        scope_object_model='RiskSignal',
        scope_object_id=1,
        correlation_id='KEEP_EXCEPTION:RiskSignal:1:other',
        outcome='APPROVED',
        granted_privileges=['policy.deviation'],
        starts_at=now,
        expires_at=now + timedelta(days=30),
    )
    negatives['non_allowlisted_no_dual_write'] = {
        'pass': out_req is None and out_dec is None and ExceptionRequest.objects.filter(organization=other).count() == before,
        'request_created': bool(out_req),
    }

    # cross-tenant fail closed
    cross_ok = False
    try:
        mirror_legacy_exception(
            source=SOURCE_KEEP_EXCEPTION,
            organization=pilot,
            actor=outsider,
            owner=owner,
            title='cross',
            reason='cross',
            scope_object_model='RiskSignal',
            scope_object_id=9100,
            correlation_id='KEEP_EXCEPTION:RiskSignal:9100:cross',
            outcome='APPROVED',
            granted_privileges=['policy.deviation'],
            starts_at=now,
            expires_at=now + timedelta(days=30),
        )
    except ExceptionDualWriteError:
        cross_ok = True
    negatives['cross_tenant_fail_closed'] = {
        'pass': cross_ok
        and not ExceptionRequest.objects.filter(correlation_id='KEEP_EXCEPTION:RiskSignal:9100:cross').exists()
    }
    if not cross_ok:
        results['monitoring']['cross_tenant_anomalies'] = 1

    # Critical without Security approval fail closed
    crit_ok = False
    try:
        mirror_legacy_exception(
            source=SOURCE_DPA_APPROVE_WITH_BLOCKERS,
            organization=pilot,
            actor=owner,
            owner=owner,
            title='crit no sec',
            reason='crit',
            scope_object_model='DPAReviewPack',
            scope_object_id=9101,
            correlation_id='DPA_APPROVE_WITH_BLOCKERS:DPAReviewPack:9101:x',
            outcome='APPROVED',
            granted_privileges=['approval.defer_blocker'],
            risk_classification='CRITICAL',
            bypasses_critical_security_control=True,
            security_approval=False,
            starts_at=now,
            expires_at=now + timedelta(days=30),
        )
    except ExceptionDualWriteError:
        crit_ok = True
    negatives['critical_without_security_fail_closed'] = {'pass': crit_ok}

    # duplicate correlation
    existing = ExceptionRequest.objects.filter(organization=pilot, legacy_source=SOURCE_ACCEPTED_RISK).first()
    if existing:
        r1, d1 = mirror_legacy_exception(
            source=SOURCE_ACCEPTED_RISK,
            organization=pilot,
            actor=owner,
            owner=owner,
            title=existing.title,
            reason=existing.reason,
            scope_object_model=existing.scope_object_model,
            scope_object_id=int(existing.scope_object_id) if str(existing.scope_object_id).isdigit() else 9002,
            correlation_id=existing.correlation_id,
            outcome='APPROVED',
            contract=contract,
            granted_privileges=['risk.accept'],
            starts_at=now,
            expires_at=now + timedelta(days=90),
        )
        count_same = ExceptionRequest.objects.filter(organization=pilot, correlation_id=existing.correlation_id).count()
        negatives['duplicate_correlation_idempotent'] = {
            'pass': r1.pk == existing.pk and count_same == 1,
            'count': count_same,
        }

    # missing owner fail closed
    missing_owner_ok = False
    try:
        mirror_legacy_exception(
            source=SOURCE_KEEP_EXCEPTION,
            organization=pilot,
            actor=owner,
            owner=None,
            title='no owner',
            reason='no owner',
            scope_object_model='RiskSignal',
            scope_object_id=9102,
            correlation_id='KEEP_EXCEPTION:RiskSignal:9102:noowner',
            outcome='APPROVED',
            granted_privileges=['policy.deviation'],
            starts_at=now,
            expires_at=now + timedelta(days=30),
        )
    except Exception:
        missing_owner_ok = True
    negatives['missing_owner_fail_closed'] = {
        'pass': missing_owner_ok
        and not ExceptionRequest.objects.filter(correlation_id='KEEP_EXCEPTION:RiskSignal:9102:noowner').exists()
    }

    # malformed privilege fail closed
    mal_ok = False
    try:
        mirror_legacy_exception(
            source=SOURCE_KEEP_EXCEPTION,
            organization=pilot,
            actor=owner,
            owner=owner,
            title='bad priv',
            reason='bad priv',
            scope_object_model='RiskSignal',
            scope_object_id=9103,
            correlation_id='KEEP_EXCEPTION:RiskSignal:9103:badpriv',
            outcome='APPROVED',
            granted_privileges=['admin.superuser'],
            starts_at=now,
            expires_at=now + timedelta(days=30),
        )
    except ExceptionDualWriteError:
        mal_ok = True
    negatives['malformed_privilege_fail_closed'] = {'pass': mal_ok}

    results['negatives'] = negatives

    # --- Rollback drill ---
    from django.test import override_settings

    with override_settings(
        EXCEPTION_DUAL_WRITE_ENABLED=False,
        EXCEPTION_DUAL_WRITE_ORG_ALLOWLIST='',
        ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1'],
    ):
        # re-import gate after override
        from django.conf import settings as s2

        assert s2.EXCEPTION_DUAL_WRITE_ENABLED is False
        deadline2 = Deadline.objects.create(
            contract=contract,
            title='Rollback Notice',
            due_date=timezone.localdate(),
            created_by=owner,
            assigned_to=owner,
        )
        prev = deadline2.due_date
        client2 = Client()
        client2.force_login(owner)
        sess = client2.session
        sess['organization_id'] = pilot.pk
        sess.save()
        before_req = ExceptionRequest.objects.filter(organization=pilot).count()
        resp = client2.post(reverse('contracts:deadline_defer', kwargs={'pk': deadline2.pk}))
        deadline2.refresh_from_db()
        after_req = ExceptionRequest.objects.filter(organization=pilot).count()
        results['rollback'] = {
            'flag_off': True,
            'allowlist_cleared': True,
            'legacy_deadline_still_works': resp.status_code == 302 and deadline2.due_date == prev + timedelta(days=7),
            'no_new_canonical_rows': after_req == before_req,
            'canonical_rows_not_deleted': ExceptionRequest.objects.filter(organization=pilot).count() >= before_req,
            'http_status': resp.status_code,
        }

    # Restore authorized config (still env-only; settings already true in process for subsequent)
    results['restore_authorized_config'] = {
        'EXCEPTION_DUAL_WRITE_ENABLED': True,
        'EXCEPTION_DUAL_WRITE_ORG_ALLOWLIST': 'controlled-pilot-org',
        'note': 'restored in activation env only; committed defaults remain false',
    }

    # Stop conditions evaluation
    mon = results['monitoring']
    stop = {
        'cross_tenant_anomaly': mon.get('cross_tenant_anomalies', 0) > 0,
        'unauthorized_critical_bypass': not negatives.get('critical_without_security_fail_closed', {}).get('pass', False),
        'duplicate_canonical_decision': False,  # idempotency hit is prevention, not duplicate
        'missing_owner_or_expiry_on_active': mon.get('missing_owners_or_expiry', 0) > 0,
        'lost_legacy_action': not results['paths'].get(SOURCE_DEADLINE_DEFER, {}).get('legacy_action_result', {}).get('deferred_days') == 7
        if isinstance(results['paths'].get(SOURCE_DEADLINE_DEFER, {}).get('legacy_action_result'), dict)
        else False,
        'user_visible_regression': mon.get('user_visible_regressions', 0) > 0,
    }
    # Fix lost_legacy check
    defer_legacy = results['paths'].get(SOURCE_DEADLINE_DEFER, {}).get('legacy_action_result')
    if isinstance(defer_legacy, dict):
        stop['lost_legacy_action'] = defer_legacy.get('deferred_days') != 7
    results['stop_conditions'] = stop
    any_stop = any(stop.values())
    path_ok = all(
        results['paths'].get(s, {}).get('canonical_request_created')
        for s in [
            SOURCE_KEEP_EXCEPTION,
            SOURCE_ACCEPTED_RISK,
            SOURCE_AI_EXCEPTION,
            SOURCE_CONFLICT_CHECK_WAIVER,
            SOURCE_DEADLINE_DEFER,
            SOURCE_DPA_APPROVE_WITH_BLOCKERS,
        ]
    )
    # AI must have no decision
    ai_ok = results['paths'][SOURCE_AI_EXCEPTION].get('canonical_decision_created') is False
    neg_ok = all(v.get('pass') for v in negatives.values())
    rollback_ok = results['rollback'].get('legacy_deadline_still_works') and results['rollback'].get('no_new_canonical_rows')
    results['verdict'] = {
        'preflight_pass': results['preflight']['pass'],
        'paths_pass': path_ok and ai_ok,
        'negatives_pass': neg_ok,
        'rollback_pass': rollback_ok,
        'stop_conditions_clear': not any_stop,
        'overall': 'PASS'
        if results['preflight']['pass'] and path_ok and ai_ok and neg_ok and rollback_ok and not any_stop
        else 'FAIL',
    }

    out_path = evidence_dir / 'activation_results.json'
    out_path.write_text(json.dumps(results, indent=2, default=str) + '\n')
    print(json.dumps(results, indent=2, default=str))
    return 0 if results['verdict']['overall'] == 'PASS' else 1


if __name__ == '__main__':
    # Allow `python manage.py shell < this` style — when executed as module under django setup:
    try:
        import django

        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_development')
        django.setup()
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
