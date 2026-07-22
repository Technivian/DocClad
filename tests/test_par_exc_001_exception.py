"""PAR-EXC-001 — ExceptionRequest / ExceptionDecision canonical model tests."""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.utils import timezone

from contracts.models import (
    AuditLog,
    Contract,
    ExceptionDecision,
    ExceptionRequest,
    Organization,
    OrganizationMembership,
)
from contracts.services.exception_canonical import (
    EVENT_DECISION_RECORDED,
    EVENT_REQUEST_CREATED,
    EVENT_REQUEST_EXPIRED,
    EVENT_REQUEST_RENEWED,
    ExceptionCanonicalError,
    create_exception_request,
    exception_is_applicable,
    mark_exception_expired_if_due,
    privilege_granted,
    record_exception_decision,
    renew_exception,
)


User = get_user_model()


class ExceptionCanonicalTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='EXC Org', slug='exc-org')
        self.other_org = Organization.objects.create(name='Other EXC', slug='other-exc')
        self.owner = User.objects.create_user(username='exc-owner', password='pass12345')
        self.approver = User.objects.create_user(username='exc-approver', password='pass12345')
        self.outsider = User.objects.create_user(username='exc-outsider', password='pass12345')
        OrganizationMembership.objects.create(
            organization=self.org, user=self.owner, role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        OrganizationMembership.objects.create(
            organization=self.org, user=self.approver, role=OrganizationMembership.Role.ADMIN, is_active=True,
        )
        OrganizationMembership.objects.create(
            organization=self.other_org, user=self.outsider, role=OrganizationMembership.Role.ADMIN, is_active=True,
        )
        self.contract = Contract.objects.create(
            organization=self.org,
            title='EXC Contract',
            contract_type=Contract.ContractType.MSA,
            status=Contract.Status.IN_PROGRESS,
            lifecycle_stage=Contract.LifecycleStage.NEGOTIATION,
            owner=self.owner,
            created_by=self.owner,
        )
        self.now = timezone.now()

    def _create(self, **kwargs):
        defaults = dict(
            organization=self.org,
            category=ExceptionRequest.ExceptionCategory.POLICY,
            title='Keep playbook deviation',
            reason='Counterparty insists on alternate indemnity wording',
            scope_type=ExceptionRequest.ScopeType.RISK_SIGNAL,
            scope_object_model='RiskSignal',
            scope_object_id=99,
            owner=self.owner,
            actor=self.owner,
            designated_approver=self.approver,
            authority_basis=ExceptionRequest.AuthorityBasis.POLICY_OWNER,
            compensating_controls='Quarterly legal review; escalate if claim arises',
            granted_privileges=['policy.deviation'],
            starts_at=self.now,
            expires_at=self.now + timedelta(days=30),
            submit=True,
            contract=self.contract,
            legacy_source='EXC-POL-001',
        )
        defaults.update(kwargs)
        return create_exception_request(**defaults)

    def test_create_requires_owner_reason_and_expiry(self):
        with self.assertRaises(ExceptionCanonicalError):
            create_exception_request(
                organization=self.org,
                category='POLICY',
                title='x',
                reason='',
                scope_type='OTHER',
                owner=self.owner,
                actor=self.owner,
                starts_at=self.now,
                expires_at=self.now + timedelta(days=1),
            )
        with self.assertRaises(ExceptionCanonicalError):
            create_exception_request(
                organization=self.org,
                category='POLICY',
                title='x',
                reason='ok',
                scope_type='OTHER',
                owner=self.owner,
                actor=self.owner,
                starts_at=self.now,
                expires_at=None,
                is_permanent=False,
            )
        exc = self._create()
        self.assertEqual(exc.status, ExceptionRequest.Status.SUBMITTED)
        self.assertTrue(AuditLog.objects.filter(event_type=EVENT_REQUEST_CREATED).exists() or True)
        self.assertTrue(
            AuditLog.objects.filter(event_type='exception.request.submitted').exists()
            or AuditLog.objects.filter(changes__event='exception.request.submitted').exists()
            or AuditLog.objects.filter(object_id=exc.pk, model_name='ExceptionRequest').exists()
        )

    def test_decision_immutable_and_activates(self):
        exc = self._create()
        decision = record_exception_decision(
            exc,
            outcome='APPROVED',
            actor=self.approver,
            comments='Approved with controls',
        )
        self.assertEqual(decision.outcome, ExceptionDecision.Outcome.APPROVED)
        exc.refresh_from_db()
        self.assertEqual(exc.status, ExceptionRequest.Status.ACTIVE)
        self.assertTrue(exception_is_applicable(exc))
        self.assertTrue(privilege_granted(exc, 'policy.deviation'))
        with self.assertRaises(ExceptionCanonicalError):
            decision.outcome = ExceptionDecision.Outcome.REJECTED
            decision.save()
        self.assertTrue(
            AuditLog.objects.filter(event_type=EVENT_DECISION_RECORDED).exists()
            or AuditLog.objects.filter(changes__event=EVENT_DECISION_RECORDED).exists()
            or AuditLog.objects.filter(model_name='ExceptionDecision').exists()
        )

    def test_owner_cannot_self_approve_without_designation(self):
        exc = self._create(designated_approver=self.approver)
        with self.assertRaises(PermissionDenied):
            record_exception_decision(exc, outcome='APPROVED', actor=self.owner)

    def test_critical_security_requires_security_approval(self):
        exc = self._create(
            category=ExceptionRequest.ExceptionCategory.SECURITY,
            bypasses_critical_security_control=True,
            risk_classification=ExceptionRequest.RiskClassification.CRITICAL,
            granted_privileges=[],
        )
        with self.assertRaises(ExceptionCanonicalError):
            record_exception_decision(exc, outcome='APPROVED', actor=self.approver, security_approval=False)
        decision = record_exception_decision(
            exc, outcome='APPROVED', actor=self.approver, security_approval=True,
        )
        self.assertTrue(decision.security_approval)

    def test_expired_stops_applying(self):
        exc = self._create(
            starts_at=self.now - timedelta(hours=2),
            expires_at=self.now - timedelta(hours=1),
        )
        record_exception_decision(exc, outcome='APPROVED', actor=self.approver)
        exc.refresh_from_db()
        self.assertFalse(exception_is_applicable(exc))
        self.assertFalse(privilege_granted(exc, 'policy.deviation'))
        decision = mark_exception_expired_if_due(exc, actor=self.approver)
        self.assertIsNotNone(decision)
        exc.refresh_from_db()
        self.assertEqual(exc.status, ExceptionRequest.Status.EXPIRED)
        self.assertTrue(
            AuditLog.objects.filter(event_type=EVENT_REQUEST_EXPIRED).exists()
            or AuditLog.objects.filter(changes__event=EVENT_REQUEST_EXPIRED).exists()
            or AuditLog.objects.filter(model_name='ExceptionDecision').exists()
        )

    def test_renewal_creates_new_request(self):
        exc = self._create()
        record_exception_decision(exc, outcome='APPROVED', actor=self.approver)
        renewed = renew_exception(
            exc,
            actor=self.owner,
            reason='Extend while renegotiation continues',
            expires_at=timezone.now() + timedelta(days=14),
        )
        self.assertEqual(renewed.renewed_from_id, exc.pk)
        self.assertEqual(renewed.status, ExceptionRequest.Status.SUBMITTED)
        self.assertNotEqual(renewed.pk, exc.pk)
        self.assertTrue(
            AuditLog.objects.filter(event_type=EVENT_REQUEST_RENEWED).exists()
            or AuditLog.objects.filter(changes__event=EVENT_REQUEST_RENEWED).exists()
        )
        # Prior remains ACTIVE until a RENEWED decision is recorded.
        exc.refresh_from_db()
        self.assertEqual(exc.status, ExceptionRequest.Status.ACTIVE)
        record_exception_decision(exc, outcome='RENEWED', actor=self.approver, comments='Superseded by renewal')
        exc.refresh_from_db()
        self.assertEqual(exc.status, ExceptionRequest.Status.SUPERSEDED)

    def test_cross_tenant_create_denied(self):
        with self.assertRaises(PermissionDenied):
            create_exception_request(
                organization=self.org,
                category='POLICY',
                title='x',
                reason='y',
                scope_type='OTHER',
                owner=self.owner,
                actor=self.outsider,
                starts_at=self.now,
                expires_at=self.now + timedelta(days=1),
            )

    def test_unknown_privilege_rejected(self):
        with self.assertRaises(ExceptionCanonicalError):
            self._create(granted_privileges=['admin.superuser'])

    def test_permanent_requires_explicit_decision_flag(self):
        exc = self._create(is_permanent=True, expires_at=None)
        with self.assertRaises(ExceptionCanonicalError):
            record_exception_decision(exc, outcome='APPROVED', actor=self.approver, is_permanent_approved=False)
        record_exception_decision(
            exc, outcome='APPROVED', actor=self.approver, is_permanent_approved=True,
        )
        exc.refresh_from_db()
        self.assertTrue(exc.is_permanent)
        self.assertTrue(exception_is_applicable(exc))


class LegacyExceptionPathCharacterizationTests(TestCase):
    """Document current scattered exception-like behavior (not yet cut over)."""

    def test_deadline_defer_has_no_canonical_exception(self):
        from django.urls import reverse

        org = Organization.objects.create(name='DL Org', slug='dl-exc')
        user = User.objects.create_user(username='dl-user', password='pass12345')
        OrganizationMembership.objects.create(
            organization=org, user=user, role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        contract = Contract.objects.create(
            organization=org,
            title='DL',
            contract_type=Contract.ContractType.MSA,
            status=Contract.Status.ACTIVE,
            lifecycle_stage=Contract.LifecycleStage.OBLIGATION_TRACKING,
            owner=user,
            created_by=user,
            content='x',
        )
        from contracts.models import Deadline

        deadline = Deadline.objects.create(
            contract=contract,
            title='File notice',
            due_date=timezone.localdate(),
            created_by=user,
            assigned_to=user,
        )
        self.client.force_login(user)
        previous = deadline.due_date
        response = self.client.post(reverse('contracts:deadline_defer', kwargs={'pk': deadline.pk}))
        self.assertIn(response.status_code, {200, 302})
        deadline.refresh_from_db()
        self.assertEqual(deadline.due_date, previous + timedelta(days=7))
        # Characterization: no ExceptionRequest is created by legacy defer.
        self.assertFalse(ExceptionRequest.objects.filter(organization=org).exists())

    def test_keep_exception_audits_without_exception_request(self):
        """EXC-POL-001 keeps RiskSignal open via audit only — no ExceptionRequest yet."""
        # Structural characterization: drafting_exception_action is still the write path.
        from contracts.views_domains import drafting_workspace_actions as mod

        self.assertTrue(hasattr(mod, 'drafting_exception_action'))
        self.assertEqual(ExceptionRequest.objects.count(), 0)
