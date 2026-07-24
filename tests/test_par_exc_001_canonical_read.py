"""PAR-EXC-001 canonical-read capability — default-off and tenant-safe."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase, override_settings
from django.utils import timezone

from contracts.models import Contract, Organization, OrganizationMembership
from contracts.services.exception_canonical_read import resolve_canonical_applicability
from contracts.services.exception_dual_write import (
    SOURCE_AI_EXCEPTION, SOURCE_KEEP_EXCEPTION, mirror_legacy_exception,
)

User = get_user_model()


@override_settings(
    EXCEPTION_DUAL_WRITE_ENABLED=True,
    EXCEPTION_DUAL_WRITE_ORG_ALLOWLIST='controlled-pilot-org',
    EXCEPTION_CANONICAL_READ_ENABLED=True,
    EXCEPTION_CANONICAL_READ_ORG_ALLOWLIST='controlled-pilot-org',
)
class CanonicalReadTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Controlled pilot', slug='controlled-pilot-org')
        self.other = Organization.objects.create(name='Other', slug='demo-firm')
        self.owner = User.objects.create_user(username='canonical-owner', password='pass12345')
        self.outsider = User.objects.create_user(username='canonical-outsider', password='pass12345')
        OrganizationMembership.objects.create(organization=self.org, user=self.owner, role='OWNER', is_active=True)
        OrganizationMembership.objects.create(organization=self.other, user=self.outsider, role='ADMIN', is_active=True)
        self.contract = Contract.objects.create(
            organization=self.org, title='Canonical read', contract_type='MSA',
            status='IN_PROGRESS', lifecycle_stage='NEGOTIATION', owner=self.owner,
            created_by=self.owner, content='x',
        )

    def _mirror(self, *, source=SOURCE_KEEP_EXCEPTION, outcome='APPROVED', correlation='KEEP_EXCEPTION:RiskSignal:1:kept'):
        return mirror_legacy_exception(
            source=source, organization=self.org, actor=self.owner, owner=self.owner,
            title='Controlled exception', reason='Pilot test', scope_object_model='RiskSignal',
            scope_object_id=1, correlation_id=correlation, outcome=outcome, contract=self.contract,
            granted_privileges=['policy.deviation'] if source != SOURCE_AI_EXCEPTION else [],
            starts_at=timezone.now(), expires_at=timezone.now() + timedelta(days=1),
        )

    def test_correlated_row_is_authoritative_for_applicability(self):
        self._mirror()
        result = resolve_canonical_applicability(
            organization=self.org, source=SOURCE_KEEP_EXCEPTION,
            correlation_id='KEEP_EXCEPTION:RiskSignal:1:kept', legacy_applicable=False,
            privilege_token='policy.deviation', actor=self.owner,
        )
        self.assertTrue(result.canonical_used)
        self.assertTrue(result.applicable)
        self.assertTrue(result.privilege_granted)

    def test_miss_falls_back_to_legacy(self):
        result = resolve_canonical_applicability(
            organization=self.org, source=SOURCE_KEEP_EXCEPTION,
            correlation_id='KEEP_EXCEPTION:RiskSignal:missing', legacy_applicable=True, actor=self.owner,
        )
        self.assertFalse(result.canonical_used)
        self.assertTrue(result.applicable)
        self.assertEqual(result.fallback_reason, 'correlation_miss')

    def test_ai_submitted_remains_not_applicable(self):
        correlation = 'AI_EXCEPTION:ContractReviewFinding:1:submitted'
        self._mirror(source=SOURCE_AI_EXCEPTION, outcome='NONE', correlation=correlation)
        result = resolve_canonical_applicability(
            organization=self.org, source=SOURCE_AI_EXCEPTION, correlation_id=correlation,
            legacy_applicable=True, actor=self.owner,
        )
        self.assertTrue(result.canonical_used)
        self.assertFalse(result.applicable)
        self.assertFalse(result.privilege_granted)

    def test_non_allowlisted_org_does_not_use_canonical(self):
        result = resolve_canonical_applicability(
            organization=self.other, source=SOURCE_KEEP_EXCEPTION,
            correlation_id='KEEP_EXCEPTION:RiskSignal:1:kept', legacy_applicable=True, actor=self.outsider,
        )
        self.assertFalse(result.canonical_used)
        self.assertTrue(result.applicable)

    def test_cross_tenant_read_is_fail_closed(self):
        self._mirror()
        with self.assertRaises(PermissionDenied):
            resolve_canonical_applicability(
                organization=self.org, source=SOURCE_KEEP_EXCEPTION,
                correlation_id='KEEP_EXCEPTION:RiskSignal:1:kept', legacy_applicable=True, actor=self.outsider,
            )
