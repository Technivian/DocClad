"""PAR-ID-001 — resolver parity comparison tests (legacy always returned)."""

from __future__ import annotations

import json
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from contracts.models import (
    ApprovalRule,
    AuditLog,
    Contract,
    Organization,
    OrganizationMembership,
    ProcessRoleAssignment,
    UserProfile,
    WorkflowTemplate,
    WorkflowTemplateStep,
)
from contracts.services.process_role_assignment import create_process_role_assignment
from contracts.services.process_role_resolver_parity import (
    CLASS_AMBIGUOUS,
    CLASS_CANONICAL_ONLY,
    CLASS_CROSS_TENANT,
    CLASS_DIFFERENT_USER,
    CLASS_ERROR,
    CLASS_INACTIVE,
    CLASS_LEGACY_ONLY,
    CLASS_MATCH,
    EVENT_RESOLVER_CROSS_TENANT,
    EVENT_RESOLVER_PARITY,
    get_staging_counters,
    reset_staging_counters,
)
from contracts.services.role_definition import ensure_canonical_role_definitions
from contracts.services.workflow_routing import resolve_rule_assignee


User = get_user_model()


class ResolverParityTests(TestCase):
    def setUp(self):
        reset_staging_counters()
        self.org = Organization.objects.create(name='Parity Org', slug='parity-org-rp')
        self.org_b = Organization.objects.create(name='Other Org', slug='parity-org-rp-b')
        self.user_a = User.objects.create_user(username='rp-user-a', password='pass12345')
        self.user_b = User.objects.create_user(username='rp-user-b', password='pass12345')
        self.owner = User.objects.create_user(username='rp-owner', password='pass12345')
        OrganizationMembership.objects.create(
            organization=self.org, user=self.user_a, role=OrganizationMembership.Role.MEMBER, is_active=True,
        )
        OrganizationMembership.objects.create(
            organization=self.org, user=self.user_b, role=OrganizationMembership.Role.MEMBER, is_active=True,
        )
        OrganizationMembership.objects.create(
            organization=self.org, user=self.owner, role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        ensure_canonical_role_definitions(self.org)
        self.contract = Contract.objects.create(
            title='RP Contract', organization=self.org, created_by=self.owner, owner=self.owner,
        )
        self.template = WorkflowTemplate.objects.create(
            name='RP Template', organization=self.org, created_by=self.owner,
        )
        self.step = WorkflowTemplateStep.objects.create(
            template=self.template, name='Review', order=1, assignee_role=UserProfile.Role.ASSOCIATE,
        )
        self.rule = ApprovalRule.objects.create(
            organization=self.org,
            name='Legal rule',
            approval_step='LEGAL',
            trigger_type=ApprovalRule.TriggerType.CONTRACT_TYPE,
            trigger_value='MSA',
            approver_role=UserProfile.Role.ASSOCIATE,
            order=1,
            sla_hours=24,
            is_active=True,
        )

    def _profile(self, user, role):
        return UserProfile.objects.update_or_create(user=user, defaults={'role': role})[0]

    def _assign(self, user, code, *, active=True):
        from contracts.models import RoleDefinition

        role_def = RoleDefinition.objects.get(organization=self.org, code=code)
        membership = OrganizationMembership.objects.get(organization=self.org, user=user)
        profile = getattr(user, 'profile', None)
        assignment = create_process_role_assignment(
            organization=self.org,
            user=user,
            membership=membership,
            role_definition=role_def,
            assignment_source='SYSTEM',
            legacy_source_field='profile_role',
            legacy_source_value=getattr(profile, 'role', '') if profile else '',
            mapping_confidence='CERTAIN',
            is_system_managed=True,
            assignment_reason='test',
            skip_authz=True,
        )
        if not active:
            assignment.is_active = False
            assignment.save(update_fields=['is_active'])
        return assignment

    def test_flag_off_leaves_behavior_unchanged(self):
        self._profile(self.user_a, UserProfile.Role.ASSOCIATE)
        result = self.step.resolve_assignee(self.contract)
        self.assertEqual(result, self.user_a)
        self.assertEqual(get_staging_counters()['total_comparisons'], 0)
        self.assertFalse(AuditLog.objects.filter(event_type=EVENT_RESOLVER_PARITY).exists())

    def test_flag_defaults_false_in_settings(self):
        from django.conf import settings

        self.assertFalse(getattr(settings, 'PROCESS_ROLE_RESOLVER_PARITY_ENABLED', True))

    @override_settings(PROCESS_ROLE_RESOLVER_PARITY_ENABLED=True)
    def test_specific_assignee_short_circuit_returns_legacy(self):
        self.step.specific_assignee = self.user_b
        self.step.assignee_role = UserProfile.Role.ASSOCIATE
        self.step.save(update_fields=['specific_assignee', 'assignee_role'])
        self._profile(self.user_a, UserProfile.Role.ASSOCIATE)
        self._assign(self.user_a, 'legal_reviewer')
        result = self.step.resolve_assignee(self.contract)
        self.assertEqual(result.pk if result else None, self.user_b.pk)

    @override_settings(PROCESS_ROLE_RESOLVER_PARITY_ENABLED=True)
    def test_specific_approver_short_circuit_returns_legacy(self):
        self.rule.specific_approver = self.user_b
        self.rule.save(update_fields=['specific_approver'])
        self._profile(self.user_a, UserProfile.Role.ASSOCIATE)
        self._assign(self.user_a, 'legal_reviewer')
        result = resolve_rule_assignee(self.rule, self.contract)
        self.assertEqual(result.pk if result else None, self.user_b.pk)

    @override_settings(PROCESS_ROLE_RESOLVER_PARITY_ENABLED=True)
    def test_match_returns_legacy(self):
        self._profile(self.user_a, UserProfile.Role.ASSOCIATE)
        self._assign(self.user_a, 'legal_reviewer')
        result = self.step.resolve_assignee(self.contract)
        self.assertEqual(result.pk if result else None, self.user_a.pk)
        self.assertEqual(get_staging_counters()[CLASS_MATCH], 1)

    @override_settings(PROCESS_ROLE_RESOLVER_PARITY_ENABLED=True)
    def test_legacy_only_returns_legacy(self):
        self._profile(self.user_a, UserProfile.Role.ASSOCIATE)
        result = resolve_rule_assignee(self.rule, self.contract)
        self.assertEqual(result.pk if result else None, self.user_a.pk)
        self.assertEqual(get_staging_counters()[CLASS_LEGACY_ONLY], 1)

    @override_settings(PROCESS_ROLE_RESOLVER_PARITY_ENABLED=True)
    def test_canonical_only_returns_legacy_none(self):
        self._profile(self.user_a, UserProfile.Role.PARTNER)
        self._assign(self.user_b, 'legal_reviewer')
        result = resolve_rule_assignee(self.rule, self.contract)
        self.assertIsNone(result)
        self.assertEqual(get_staging_counters()[CLASS_CANONICAL_ONLY], 1)

    @override_settings(PROCESS_ROLE_RESOLVER_PARITY_ENABLED=True)
    def test_different_user_returns_legacy(self):
        self._profile(self.user_a, UserProfile.Role.ASSOCIATE)
        self._profile(self.user_b, UserProfile.Role.PARTNER)
        self._assign(self.user_b, 'legal_reviewer')
        result = self.step.resolve_assignee(self.contract)
        self.assertEqual(result.pk if result else None, self.user_a.pk)
        self.assertEqual(get_staging_counters()[CLASS_DIFFERENT_USER], 1)

    @override_settings(PROCESS_ROLE_RESOLVER_PARITY_ENABLED=True)
    def test_different_role_returns_legacy(self):
        self._profile(self.user_a, UserProfile.Role.ASSOCIATE)
        self._assign(self.user_a, 'partner_reviewer')
        result = self.step.resolve_assignee(self.contract)
        self.assertEqual(result.pk if result else None, self.user_a.pk)
        self.assertEqual(get_staging_counters()['DIFFERENT_ROLE'], 1)

    @override_settings(PROCESS_ROLE_RESOLVER_PARITY_ENABLED=True)
    def test_ambiguous_admin_returns_legacy(self):
        self.step.assignee_role = UserProfile.Role.ADMIN
        self.step.save(update_fields=['assignee_role'])
        self._profile(self.user_a, UserProfile.Role.ADMIN)
        self._assign(self.user_a, 'legacy_process_admin')
        result = self.step.resolve_assignee(self.contract)
        self.assertEqual(result.pk if result else None, self.user_a.pk)
        self.assertEqual(get_staging_counters()[CLASS_AMBIGUOUS], 1)

    @override_settings(PROCESS_ROLE_RESOLVER_PARITY_ENABLED=True)
    def test_inactive_assignment_returns_legacy(self):
        self._profile(self.user_a, UserProfile.Role.ASSOCIATE)
        self._assign(self.user_a, 'legal_reviewer', active=False)
        result = self.step.resolve_assignee(self.contract)
        self.assertEqual(result.pk if result else None, self.user_a.pk)
        self.assertEqual(get_staging_counters()[CLASS_INACTIVE], 1)

    @override_settings(PROCESS_ROLE_RESOLVER_PARITY_ENABLED=True)
    def test_delegation_does_not_change_resolver_result(self):
        from contracts.models import ApprovalRequest

        self._profile(self.user_a, UserProfile.Role.ASSOCIATE)
        ApprovalRequest.objects.create(
            organization=self.org,
            contract=self.contract,
            approval_step='LEGAL',
            assigned_to=self.user_a,
            delegated_to=self.user_b,
            status=ApprovalRequest.Status.PENDING,
        )
        result = resolve_rule_assignee(self.rule, self.contract)
        self.assertEqual(result.pk if result else None, self.user_a.pk)

    @override_settings(PROCESS_ROLE_RESOLVER_PARITY_ENABLED=True)
    def test_unresolved_returns_none(self):
        result = self.step.resolve_assignee(self.contract)
        self.assertIsNone(result)
        self.assertGreaterEqual(get_staging_counters()['total_comparisons'], 1)

    @override_settings(PROCESS_ROLE_RESOLVER_PARITY_ENABLED=True)
    def test_resolution_error_returns_legacy(self):
        self._profile(self.user_a, UserProfile.Role.ASSOCIATE)
        with patch(
            'contracts.services.process_role_resolver_parity._canonical_users_for_role',
            side_effect=RuntimeError('canonical boom'),
        ):
            result = self.step.resolve_assignee(self.contract)
        self.assertEqual(result.pk if result else None, self.user_a.pk)
        self.assertEqual(get_staging_counters()[CLASS_ERROR], 1)

    @override_settings(PROCESS_ROLE_RESOLVER_PARITY_ENABLED=True)
    def test_cross_tenant_anomaly_returns_legacy_and_escalates(self):
        self._profile(self.user_a, UserProfile.Role.ASSOCIATE)
        self.rule.organization = self.org_b
        self.rule.save(update_fields=['organization'])
        result = resolve_rule_assignee(self.rule, self.contract)
        self.assertEqual(result.pk if result else None, self.user_a.pk)
        self.assertEqual(get_staging_counters()[CLASS_CROSS_TENANT], 1)
        self.assertTrue(
            AuditLog.objects.filter(event_type=EVENT_RESOLVER_CROSS_TENANT).exists()
        )

    @override_settings(PROCESS_ROLE_RESOLVER_PARITY_ENABLED=True)
    def test_no_automatic_repair(self):
        self._profile(self.user_a, UserProfile.Role.ASSOCIATE)
        before = ProcessRoleAssignment.objects.filter(organization=self.org).count()
        self.step.resolve_assignee(self.contract)
        after = ProcessRoleAssignment.objects.filter(organization=self.org).count()
        self.assertEqual(before, after)

    @override_settings(PROCESS_ROLE_RESOLVER_PARITY_ENABLED=True)
    def test_evidence_hygiene(self):
        self._profile(self.user_a, UserProfile.Role.ASSOCIATE)
        self.step.resolve_assignee(self.contract)
        log = AuditLog.objects.filter(event_type=EVENT_RESOLVER_PARITY).latest('id')
        changes = log.changes or {}
        forbidden = {'password', 'email', 'username', 'contract_title', 'role_dump', 'user_id'}
        self.assertTrue(forbidden.isdisjoint(set(changes.keys())))
        for key in (
            'organization_id', 'resolver_type', 'classification', 'correlation_id',
            'legacy_result_present', 'canonical_result_present', 'criticality', 'timestamp',
        ):
            self.assertIn(key, changes)

    @override_settings(PROCESS_ROLE_RESOLVER_PARITY_ENABLED=True)
    def test_json_reporting_and_critical_drift_counts(self):
        self._profile(self.user_a, UserProfile.Role.ASSOCIATE)
        self._profile(self.user_b, UserProfile.Role.PARTNER)
        self._assign(self.user_b, 'legal_reviewer')
        out = StringIO()
        with self.assertRaises(SystemExit) as ctx:
            call_command(
                'process_role_resolver_parity_report',
                '--organization-id', str(self.org.pk),
                '--json',
                stdout=out,
            )
        self.assertEqual(ctx.exception.code, 1)
        payload = json.loads(out.getvalue())
        self.assertFalse(payload['authoritative_for_runtime'])
        self.assertGreaterEqual(payload['DIFFERENT_USER_count'], 1)
        self.assertGreaterEqual(payload['critical_drift_count'], 1)
        self.assertIn('counts_per_classification', payload)
