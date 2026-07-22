"""PAR-EXC-001 — priority dual-write adapters (legacy authoritative)."""

from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from contracts.models import (
    AuditLog,
    Client,
    ConflictCheck,
    Contract,
    Deadline,
    ExceptionDecision,
    ExceptionRequest,
    Organization,
    OrganizationMembership,
)
from contracts.services.exception_canonical import (
    exception_is_applicable,
    mark_exception_expired_if_due,
    renew_exception,
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


@override_settings(
    EXCEPTION_DUAL_WRITE_ENABLED=True,
    EXCEPTION_DUAL_WRITE_ORG_ALLOWLIST='exc-dual-org',
)
class ExceptionDualWriteTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='EXC Dual', slug='exc-dual-org')
        self.other = Organization.objects.create(name='Other Dual', slug='other-dual')
        self.owner = User.objects.create_user(username='dual-owner', password='pass12345')
        self.outsider = User.objects.create_user(username='dual-out', password='pass12345')
        OrganizationMembership.objects.create(
            organization=self.org, user=self.owner, role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        OrganizationMembership.objects.create(
            organization=self.other, user=self.outsider, role=OrganizationMembership.Role.ADMIN, is_active=True,
        )
        self.contract = Contract.objects.create(
            organization=self.org,
            title='Dual Contract',
            contract_type=Contract.ContractType.MSA,
            status=Contract.Status.IN_PROGRESS,
            lifecycle_stage=Contract.LifecycleStage.NEGOTIATION,
            owner=self.owner,
            created_by=self.owner,
            content='x',
        )
        self.now = timezone.now()

    def _mirror(self, **kwargs):
        defaults = dict(
            source=SOURCE_KEEP_EXCEPTION,
            organization=self.org,
            actor=self.owner,
            owner=self.owner,
            title='Keep exception',
            reason='Counterparty insists',
            scope_object_model='RiskSignal',
            scope_object_id=1,
            correlation_id='KEEP_EXCEPTION:RiskSignal:1:kept',
            outcome='APPROVED',
            contract=self.contract,
            granted_privileges=['policy.deviation'],
            starts_at=self.now,
            expires_at=self.now + timedelta(days=30),
        )
        defaults.update(kwargs)
        return mirror_legacy_exception(**defaults)

    def test_flag_and_allowlist_gate(self):
        self.assertTrue(dual_write_enabled_for_org(self.org))
        with override_settings(EXCEPTION_DUAL_WRITE_ENABLED=False):
            self.assertFalse(dual_write_enabled_for_org(self.org))
        with override_settings(EXCEPTION_DUAL_WRITE_ORG_ALLOWLIST='someone-else'):
            self.assertFalse(dual_write_enabled_for_org(self.org))

    def test_create_approved_decision_and_idempotent(self):
        req1, dec1 = self._mirror()
        self.assertIsNotNone(req1)
        self.assertEqual(dec1.outcome, ExceptionDecision.Outcome.APPROVED)
        self.assertEqual(req1.status, ExceptionRequest.Status.ACTIVE)
        self.assertEqual(req1.correlation_id, 'KEEP_EXCEPTION:RiskSignal:1:kept')
        self.assertTrue(exception_is_applicable(req1))
        req2, dec2 = self._mirror()
        self.assertEqual(req1.pk, req2.pk)
        self.assertEqual(dec1.pk, dec2.pk)
        self.assertEqual(ExceptionRequest.objects.filter(organization=self.org).count(), 1)

    def test_owner_expiry_compensating_controls(self):
        req, _ = self._mirror(compensating_controls='Quarterly legal review')
        self.assertEqual(req.owner_id, self.owner.pk)
        self.assertIsNotNone(req.expires_at)
        self.assertIn('Quarterly', req.compensating_controls)

    def test_cross_tenant_fail_closed(self):
        with self.assertRaises(ExceptionDualWriteError):
            self._mirror(actor=self.outsider)
        self.assertFalse(
            ExceptionRequest.objects.filter(
                organization=self.org,
                correlation_id='KEEP_EXCEPTION:RiskSignal:1:kept',
            ).exists()
        )

    def test_critical_without_security_fail_closed(self):
        with self.assertRaises(ExceptionDualWriteError):
            self._mirror(
                bypasses_critical_security_control=True,
                security_approval=False,
                risk_classification='CRITICAL',
                correlation_id='KEEP_EXCEPTION:RiskSignal:7:crit',
                scope_object_id=7,
            )
        self.assertFalse(
            ExceptionRequest.objects.filter(
                correlation_id='KEEP_EXCEPTION:RiskSignal:7:crit',
            ).exists()
        )

    def test_critical_with_security_approval(self):
        req, dec = self._mirror(
            bypasses_critical_security_control=True,
            security_approval=True,
            risk_classification='CRITICAL',
            source=SOURCE_DPA_APPROVE_WITH_BLOCKERS,
            correlation_id='DPA_APPROVE_WITH_BLOCKERS:DPAReviewPack:9:x',
            granted_privileges=['approval.defer_blocker'],
        )
        self.assertTrue(dec.security_approval)
        self.assertEqual(req.risk_classification, ExceptionRequest.RiskClassification.CRITICAL)

    def test_malformed_privilege_fail_closed(self):
        with self.assertRaises(ExceptionDualWriteError):
            self._mirror(granted_privileges=['admin.superuser'])

    def test_ai_exception_request_without_approval_decision(self):
        req, dec = self._mirror(
            source=SOURCE_AI_EXCEPTION,
            outcome='NONE',
            correlation_id='AI_EXCEPTION:ContractReviewFinding:5:requested',
            scope_object_model='ContractReviewFinding',
            scope_object_id=5,
            granted_privileges=[],
        )
        self.assertEqual(req.status, ExceptionRequest.Status.SUBMITTED)
        self.assertIsNone(dec)

    def test_rejected_and_revoked_outcomes(self):
        req, dec = self._mirror(
            outcome='REJECTED',
            correlation_id='KEEP_EXCEPTION:RiskSignal:2:rej',
            scope_object_id=2,
        )
        self.assertEqual(dec.outcome, ExceptionDecision.Outcome.REJECTED)
        self.assertEqual(req.status, ExceptionRequest.Status.REJECTED)
        req2, dec2 = self._mirror(
            outcome='REVOKED',
            correlation_id='KEEP_EXCEPTION:RiskSignal:3:rev',
            scope_object_id=3,
        )
        self.assertEqual(dec2.outcome, ExceptionDecision.Outcome.REVOKED)
        self.assertEqual(req2.status, ExceptionRequest.Status.REVOKED)

    def test_expiry_stops_applying_and_renewal(self):
        req, _ = self._mirror(
            starts_at=self.now - timedelta(days=10),
            expires_at=self.now - timedelta(days=1),
            correlation_id='KEEP_EXCEPTION:RiskSignal:4:exp',
            scope_object_id=4,
        )
        self.assertFalse(exception_is_applicable(req))
        mark_exception_expired_if_due(req, actor=self.owner)
        req.refresh_from_db()
        self.assertEqual(req.status, ExceptionRequest.Status.EXPIRED)
        # Historical decision unchanged
        self.assertEqual(req.decisions.filter(outcome='APPROVED').count(), 1)
        renewed = renew_exception(
            req, actor=self.owner, expires_at=timezone.now() + timedelta(days=14),
        )
        self.assertEqual(renewed.renewed_from_id, req.pk)
        self.assertNotEqual(renewed.pk, req.pk)

    def test_decision_immutable(self):
        _, dec = self._mirror(correlation_id='KEEP_EXCEPTION:RiskSignal:6:imm', scope_object_id=6)
        from contracts.services.exception_canonical import ExceptionCanonicalError
        with self.assertRaises(ExceptionCanonicalError):
            dec.outcome = ExceptionDecision.Outcome.REJECTED
            dec.save()

    def test_ordinary_failure_preserves_no_raise_via_safe(self):
        with mock.patch(
            'contracts.models.ExceptionRequest.objects.create',
            side_effect=RuntimeError('boom'),
        ):
            req, dec = safe_mirror_legacy_exception(
                source=SOURCE_KEEP_EXCEPTION,
                organization=self.org,
                actor=self.owner,
                owner=self.owner,
                title='x',
                reason='y',
                scope_object_model='RiskSignal',
                scope_object_id=99,
                correlation_id='KEEP_EXCEPTION:RiskSignal:99:fail',
                outcome='APPROVED',
            )
        self.assertIsNone(req)
        self.assertIsNone(dec)
        self.assertTrue(
            AuditLog.objects.filter(event_type=EVENT_DUAL_WRITE_FAILED).exists()
            or AuditLog.objects.filter(model_name='ExceptionRequest').exists()
        )

    def test_deadline_defer_dual_write_path(self):
        deadline = Deadline.objects.create(
            contract=self.contract,
            title='Notice',
            due_date=timezone.localdate(),
            created_by=self.owner,
            assigned_to=self.owner,
        )
        self.client.force_login(self.owner)
        previous = deadline.due_date
        response = self.client.post(reverse('contracts:deadline_defer', kwargs={'pk': deadline.pk}))
        self.assertEqual(response.status_code, 302)
        deadline.refresh_from_db()
        self.assertEqual(deadline.due_date, previous + timedelta(days=7))
        self.assertTrue(
            ExceptionRequest.objects.filter(
                organization=self.org, legacy_source=SOURCE_DEADLINE_DEFER,
            ).exists()
        )

    def test_legacy_authoritative_when_flag_off(self):
        with override_settings(EXCEPTION_DUAL_WRITE_ENABLED=False):
            deadline = Deadline.objects.create(
                contract=self.contract,
                title='Notice2',
                due_date=timezone.localdate(),
                created_by=self.owner,
                assigned_to=self.owner,
            )
            self.client.force_login(self.owner)
            previous = deadline.due_date
            response = self.client.post(reverse('contracts:deadline_defer', kwargs={'pk': deadline.pk}))
            self.assertEqual(response.status_code, 302)
            deadline.refresh_from_db()
            self.assertEqual(deadline.due_date, previous + timedelta(days=7))
            self.assertFalse(
                ExceptionRequest.objects.filter(legacy_source=SOURCE_DEADLINE_DEFER).exists()
            )

    def test_source_classifications_cover_six_paths(self):
        sources = [
            SOURCE_KEEP_EXCEPTION,
            SOURCE_ACCEPTED_RISK,
            SOURCE_AI_EXCEPTION,
            SOURCE_CONFLICT_CHECK_WAIVER,
            SOURCE_DEADLINE_DEFER,
            SOURCE_DPA_APPROVE_WITH_BLOCKERS,
        ]
        for i, source in enumerate(sources):
            outcome = 'NONE' if source == SOURCE_AI_EXCEPTION else 'APPROVED'
            privileges = []
            if source == SOURCE_KEEP_EXCEPTION:
                privileges = ['policy.deviation']
            elif source == SOURCE_ACCEPTED_RISK:
                privileges = ['risk.accept']
            elif source == SOURCE_DEADLINE_DEFER:
                privileges = ['deadline.extend']
            elif source == SOURCE_DPA_APPROVE_WITH_BLOCKERS:
                privileges = ['approval.defer_blocker']
            elif source == SOURCE_CONFLICT_CHECK_WAIVER:
                privileges = ['policy.deviation']
            req, _ = self._mirror(
                source=source,
                outcome=outcome,
                correlation_id=build_correlation_id(
                    source=source, object_model='X', object_id=i, suffix='t',
                ),
                scope_object_id=100 + i,
                granted_privileges=privileges,
                security_approval=(source == SOURCE_DPA_APPROVE_WITH_BLOCKERS),
                bypasses_critical_security_control=(source == SOURCE_DPA_APPROVE_WITH_BLOCKERS),
            )
            self.assertEqual(req.legacy_source, source)

    def test_conflict_check_waiver_dual_write(self):
        client = Client.objects.create(organization=self.org, name='ACME')
        check = ConflictCheck.objects.create(
            client=client,
            checked_party='Rival Co',
            status=ConflictCheck.Status.PENDING,
            notes='Client approved waiver',
            checked_by=self.owner,
        )
        self.client.force_login(self.owner)
        url = reverse('contracts:conflict_check_update', kwargs={'pk': check.pk})
        response = self.client.post(url, {
            'client': client.pk,
            'checked_party': 'Rival Co',
            'status': ConflictCheck.Status.WAIVED,
            'notes': 'Client approved waiver',
            'conflicts_found': '',
            'checked_party_type': '',
        })
        self.assertIn(response.status_code, {200, 302})
        check.refresh_from_db()
        self.assertEqual(check.status, ConflictCheck.Status.WAIVED)
        self.assertTrue(
            ExceptionRequest.objects.filter(
                organization=self.org, legacy_source=SOURCE_CONFLICT_CHECK_WAIVER,
            ).exists()
        )
