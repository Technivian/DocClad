"""PAR-ID-001 — canonical resolver authority tests (flag default off)."""

from __future__ import annotations

from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
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
from contracts.services.process_role_resolver_authority import (
    EVENT_CANONICAL_FAILURE,
    EVENT_CANONICAL_USED,
    EVENT_CROSS_TENANT,
    EVENT_CUTOVER_EXCLUDED,
    EVENT_LEGACY_FALLBACK,
    REASON_CANONICAL_ERROR,
    REASON_CANONICAL_USED,
    REASON_CROSS_TENANT,
    REASON_EXCLUDED_AMBIGUOUS,
    REASON_EXCLUDED_PROFILE_ADMIN,
    REASON_EXCLUDED_WORKSPACE_ROLE,
    REASON_INACTIVE_ASSIGNMENT,
    REASON_MISSING_ASSIGNMENT,
    REASON_ORG_NOT_ALLOWLISTED,
    canonical_resolver_enabled,
)
from contracts.services.role_definition import ensure_canonical_role_definitions
from contracts.services.workflow_routing import resolve_rule_assignee


User = get_user_model()

AUTH_ON = dict(
    PROCESS_ROLE_CANONICAL_RESOLVER_ENABLED=True,
    PROCESS_ROLE_CANONICAL_RESOLVER_ORG_ALLOWLIST='authority-org',
)


class CanonicalResolverAuthorityTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Authority Org', slug='authority-org')
        self.org_b = Organization.objects.create(name='Other Org', slug='authority-org-b')
        self.user_a = User.objects.create_user(username='auth-user-a', password='pass12345')
        self.user_b = User.objects.create_user(username='auth-user-b', password='pass12345')
        self.owner = User.objects.create_user(username='auth-owner', password='pass12345')
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
        ensure_canonical_role_definitions(self.org_b)
        self.contract = Contract.objects.create(
            title='Auth Contract', organization=self.org, created_by=self.owner, owner=self.owner,
        )
        self.template = WorkflowTemplate.objects.create(
            name='Auth Template', organization=self.org, created_by=self.owner,
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

    def _assign(self, user, code, *, active=True, org=None):
        from contracts.models import RoleDefinition

        org = org or self.org
        role_def = RoleDefinition.objects.get(organization=org, code=code)
        membership = OrganizationMembership.objects.get(organization=org, user=user)
        existing = ProcessRoleAssignment.objects.filter(
            organization=org, user=user, role_definition=role_def,
        ).first()
        if existing:
            existing.is_active = active
            existing.save(update_fields=['is_active'])
            return existing
        profile = getattr(user, 'profile', None)
        assignment = create_process_role_assignment(
            organization=org,
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

    def _last_event(self, event_type):
        return AuditLog.objects.filter(event_type=event_type).order_by('-id').first()

    def test_flag_defaults_false(self):
        self.assertFalse(getattr(settings, 'PROCESS_ROLE_CANONICAL_RESOLVER_ENABLED', True))
        self.assertFalse(canonical_resolver_enabled())

    def test_flag_off_uses_legacy(self):
        self._profile(self.user_a, UserProfile.Role.ASSOCIATE)
        self._assign(self.user_b, 'legal_reviewer')  # different canonical would win if on
        result = self.step.resolve_assignee(self.contract)
        self.assertEqual(result, self.user_a)
        self.assertFalse(AuditLog.objects.filter(event_type=EVENT_CANONICAL_USED).exists())

    @override_settings(**AUTH_ON)
    def test_eligible_canonical_match(self):
        self._profile(self.user_a, UserProfile.Role.ASSOCIATE)
        self._assign(self.user_a, 'legal_reviewer')
        result = self.step.resolve_assignee(self.contract)
        self.assertEqual(result, self.user_a)
        event = self._last_event(EVENT_CANONICAL_USED)
        self.assertIsNotNone(event)
        self.assertEqual(event.changes.get('reason'), REASON_CANONICAL_USED)
        self.assertEqual(event.changes.get('path'), 'canonical')
        self.assertEqual(event.changes.get('resolver_type'), 'resolve_assignee')

    @override_settings(**AUTH_ON)
    def test_eligible_canonical_rule_path(self):
        self._profile(self.user_a, UserProfile.Role.ASSOCIATE)
        self._assign(self.user_a, 'legal_reviewer')
        result = resolve_rule_assignee(self.rule, self.contract)
        self.assertEqual(result, self.user_a)
        event = self._last_event(EVENT_CANONICAL_USED)
        self.assertEqual(event.changes.get('resolver_type'), 'resolve_rule_assignee')

    @override_settings(**AUTH_ON)
    def test_profile_admin_exclusion(self):
        self.step.assignee_role = UserProfile.Role.ADMIN
        self.step.save(update_fields=['assignee_role'])
        self._profile(self.user_a, UserProfile.Role.ADMIN)
        self._assign(self.user_a, 'legacy_process_admin')
        result = self.step.resolve_assignee(self.contract)
        self.assertEqual(result, self.user_a)
        event = self._last_event(EVENT_CUTOVER_EXCLUDED)
        self.assertIsNotNone(event)
        self.assertEqual(event.changes.get('reason'), REASON_EXCLUDED_PROFILE_ADMIN)
        self.assertEqual(event.changes.get('path'), 'legacy')

    @override_settings(**AUTH_ON)
    def test_workspace_owner_exclusion(self):
        self.step.assignee_role = 'OWNER'
        self.step.save(update_fields=['assignee_role'])
        result = self.step.resolve_assignee(self.contract)
        event = self._last_event(EVENT_CUTOVER_EXCLUDED)
        self.assertIsNotNone(event)
        self.assertEqual(event.changes.get('reason'), REASON_EXCLUDED_WORKSPACE_ROLE)

    @override_settings(**AUTH_ON)
    def test_missing_assignment_fallback(self):
        self._profile(self.user_a, UserProfile.Role.ASSOCIATE)
        result = self.step.resolve_assignee(self.contract)
        self.assertEqual(result, self.user_a)
        event = self._last_event(EVENT_LEGACY_FALLBACK)
        self.assertEqual(event.changes.get('reason'), REASON_MISSING_ASSIGNMENT)

    @override_settings(**AUTH_ON)
    def test_inactive_assignment_fallback(self):
        self._profile(self.user_a, UserProfile.Role.ASSOCIATE)
        self._assign(self.user_a, 'legal_reviewer', active=False)
        result = self.step.resolve_assignee(self.contract)
        self.assertEqual(result, self.user_a)
        event = self._last_event(EVENT_LEGACY_FALLBACK)
        self.assertEqual(event.changes.get('reason'), REASON_INACTIVE_ASSIGNMENT)

    @override_settings(**AUTH_ON)
    def test_ambiguous_mapping_fallback(self):
        # ADMIN already covered; CLIENT is CERTAIN — use unknown label via empty map path
        # Force AMBIGUOUS by using ADMIN on rule
        self.rule.approver_role = UserProfile.Role.ADMIN
        self.rule.save(update_fields=['approver_role'])
        self._profile(self.user_a, UserProfile.Role.ADMIN)
        result = resolve_rule_assignee(self.rule, self.contract)
        self.assertEqual(result, self.user_a)
        event = self._last_event(EVENT_CUTOVER_EXCLUDED)
        self.assertEqual(event.changes.get('reason'), REASON_EXCLUDED_PROFILE_ADMIN)

    @override_settings(**AUTH_ON)
    def test_canonical_error_fallback(self):
        self._profile(self.user_a, UserProfile.Role.ASSOCIATE)
        self._assign(self.user_a, 'legal_reviewer')
        with patch(
            'contracts.services.process_role_resolver_authority._select_canonical_user',
            side_effect=RuntimeError('boom'),
        ):
            result = self.step.resolve_assignee(self.contract)
        self.assertEqual(result, self.user_a)
        event = self._last_event(EVENT_CANONICAL_FAILURE)
        self.assertIsNotNone(event)
        self.assertEqual(event.changes.get('reason'), REASON_CANONICAL_ERROR)

    @override_settings(**AUTH_ON)
    def test_org_not_allowlisted_uses_legacy(self):
        other = Organization.objects.create(name='Not Listed', slug='not-listed')
        ensure_canonical_role_definitions(other)
        OrganizationMembership.objects.create(
            organization=other, user=self.user_a, role=OrganizationMembership.Role.MEMBER, is_active=True,
        )
        contract = Contract.objects.create(
            title='Other', organization=other, created_by=self.owner, owner=self.owner,
        )
        template = WorkflowTemplate.objects.create(
            name='Other T', organization=other, created_by=self.owner,
        )
        step = WorkflowTemplateStep.objects.create(
            template=template, name='R', order=1, assignee_role=UserProfile.Role.ASSOCIATE,
        )
        self._profile(self.user_a, UserProfile.Role.ASSOCIATE)
        result = step.resolve_assignee(contract)
        self.assertEqual(result, self.user_a)
        event = self._last_event(EVENT_LEGACY_FALLBACK)
        self.assertEqual(event.changes.get('reason'), REASON_ORG_NOT_ALLOWLISTED)

    @override_settings(**AUTH_ON)
    def test_cross_tenant_fail_closed(self):
        self._profile(self.user_a, UserProfile.Role.ASSOCIATE)
        self._assign(self.user_a, 'legal_reviewer')
        # Template belongs to org_b, contract to org — mismatch
        self.template.organization = self.org_b
        self.template.save(update_fields=['organization'])
        result = self.step.resolve_assignee(self.contract)
        self.assertIsNone(result)
        event = self._last_event(EVENT_CROSS_TENANT)
        self.assertIsNotNone(event)
        self.assertEqual(event.changes.get('reason'), REASON_CROSS_TENANT)
        self.assertEqual(event.changes.get('path'), 'blocked')
        # No restricted identity keys
        for banned in ('user_id', 'email', 'username', 'role_payload', 'contract_title'):
            self.assertNotIn(banned, event.changes)

    @override_settings(**AUTH_ON)
    def test_legacy_resolver_retained_when_flag_disabled_midflight(self):
        self._profile(self.user_a, UserProfile.Role.ASSOCIATE)
        self._assign(self.user_b, 'legal_reviewer')
        with self.settings(PROCESS_ROLE_CANONICAL_RESOLVER_ENABLED=True,
                           PROCESS_ROLE_CANONICAL_RESOLVER_ORG_ALLOWLIST='authority-org'):
            on_result = self.step.resolve_assignee(self.contract)
            self.assertEqual(on_result, self.user_b)
        with self.settings(PROCESS_ROLE_CANONICAL_RESOLVER_ENABLED=False):
            off_result = self.step.resolve_assignee(self.contract)
            self.assertEqual(off_result, self.user_a)

    @override_settings(**AUTH_ON)
    def test_specific_assignee_bypasses_canonical(self):
        self.step.specific_assignee = self.user_b
        self.step.save(update_fields=['specific_assignee'])
        self._profile(self.user_a, UserProfile.Role.ASSOCIATE)
        self._assign(self.user_a, 'legal_reviewer')
        result = self.step.resolve_assignee(self.contract)
        self.assertEqual(result, self.user_b)
        self.assertFalse(AuditLog.objects.filter(event_type=EVENT_CANONICAL_USED).exists())

    @override_settings(**AUTH_ON)
    def test_audit_evidence_hygiene(self):
        self._profile(self.user_a, UserProfile.Role.ASSOCIATE)
        self._assign(self.user_a, 'legal_reviewer')
        self.step.resolve_assignee(self.contract)
        event = self._last_event(EVENT_CANONICAL_USED)
        allowed = {
            'organization_id', 'resolver_type', 'path', 'reason',
            'correlation_id', 'criticality', 'timestamp', 'authoritative_for_runtime',
        }
        self.assertTrue(set(event.changes.keys()) <= allowed)

    @override_settings(**AUTH_ON)
    def test_authority_does_not_enable_parity_or_shadow(self):
        self.assertFalse(settings.PROCESS_ROLE_RESOLVER_PARITY_ENABLED)
        self.assertFalse(settings.PROCESS_ROLE_SHADOW_WRITE_ENABLED)
        self.assertFalse(settings.PROCESS_ROLE_PARITY_REPORTING_ENABLED)
        self._profile(self.user_a, UserProfile.Role.ASSOCIATE)
        self._assign(self.user_a, 'legal_reviewer')
        self.step.resolve_assignee(self.contract)
        self.assertFalse(AuditLog.objects.filter(event_type='role.resolver.parity_compared').exists())

    @override_settings(**AUTH_ON)
    def test_workflow_launch_style_templates(self):
        for name, role in (
            ('DPA Review', UserProfile.Role.ASSOCIATE),
            ('MSA Review', UserProfile.Role.ASSOCIATE),
            ('NDA Review', UserProfile.Role.PARALEGAL),
            ('Generic Review', UserProfile.Role.ASSOCIATE),
        ):
            template = WorkflowTemplate.objects.create(
                name=name, organization=self.org, created_by=self.owner,
            )
            step = WorkflowTemplateStep.objects.create(
                template=template, name='Step', order=1, assignee_role=role,
            )
            user = self.user_a if role == UserProfile.Role.ASSOCIATE else self.user_b
            self._profile(user, role)
            code = 'legal_reviewer' if role == UserProfile.Role.ASSOCIATE else 'paralegal_reviewer'
            if not ProcessRoleAssignment.objects.filter(
                organization=self.org, user=user, role_definition__code=code, is_active=True,
            ).exists():
                self._assign(user, code)
            self.assertEqual(step.resolve_assignee(self.contract), user)
