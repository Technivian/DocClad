"""PAR-ID-001 — RoleDefinition catalogue tests (migration 0112 additive slice).

No permission, resolver, or membership-authority changes are covered here —
only catalogue governance.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.test import TestCase

from contracts.models import AuditLog, Organization, OrganizationMembership, RoleDefinition, UserProfile
from contracts.services.role_definition import (
    EVENT_CREATED,
    EVENT_DEACTIVATED,
    EVENT_REPAIRED,
    EVENT_UPDATED,
    RoleDefinitionError,
    create_role_definition,
    deactivate_role_definition,
    ensure_canonical_role_definitions,
    lookup_role_definition,
    repair_role_definition,
    update_role_definition,
)


User = get_user_model()


class RoleDefinitionCatalogueTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='RoleDef Org', slug='roledef-org')
        self.org_b = Organization.objects.create(name='RoleDef Org B', slug='roledef-org-b')
        self.owner = User.objects.create_user(username='rd-owner', password='pass12345')
        self.member = User.objects.create_user(username='rd-member', password='pass12345')
        self.outsider = User.objects.create_user(username='rd-outsider', password='pass12345')
        OrganizationMembership.objects.create(
            organization=self.org, user=self.owner, role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        OrganizationMembership.objects.create(
            organization=self.org, user=self.member, role=OrganizationMembership.Role.MEMBER, is_active=True,
        )
        OrganizationMembership.objects.create(
            organization=self.org_b, user=self.outsider, role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        UserProfile.objects.create(user=self.owner, role=UserProfile.Role.ADMIN)
        UserProfile.objects.create(user=self.member, role=UserProfile.Role.ASSOCIATE)
        # Migration seeds existing orgs; re-seed for test orgs created after migrate.
        ensure_canonical_role_definitions(self.org)
        ensure_canonical_role_definitions(self.org_b)

    def test_organization_isolation_of_catalogue(self):
        codes_a = set(RoleDefinition.objects.filter(organization=self.org).values_list('code', flat=True))
        codes_b = set(RoleDefinition.objects.filter(organization=self.org_b).values_list('code', flat=True))
        self.assertTrue(codes_a)
        self.assertEqual(codes_a, codes_b)
        # Rows are distinct per org
        a_id = RoleDefinition.objects.get(organization=self.org, code='legal_reviewer').pk
        b_id = RoleDefinition.objects.get(organization=self.org_b, code='legal_reviewer').pk
        self.assertNotEqual(a_id, b_id)

    def test_duplicate_code_prevented_per_organization(self):
        with self.assertRaises(RoleDefinitionError):
            create_role_definition(
                organization=self.org,
                code='legal_reviewer',
                name='Dup',
                category=RoleDefinition.Category.APPROVAL,
                actor=self.owner,
            )

    def test_code_immutable_after_creation(self):
        role = RoleDefinition.objects.get(organization=self.org, code='signer')
        role.code = 'mutated'
        with self.assertRaises(RoleDefinitionError):
            role.save()

    def test_authorized_catalogue_management(self):
        role = create_role_definition(
            organization=self.org,
            code='custom_reviewer',
            name='Custom Reviewer',
            category=RoleDefinition.Category.WORKFLOW,
            actor=self.owner,
        )
        self.assertTrue(role.is_active)
        update_role_definition(role, actor=self.owner, name='Custom Reviewer v2')
        role.refresh_from_db()
        self.assertEqual(role.name, 'Custom Reviewer v2')
        deactivate_role_definition(role, actor=self.owner)
        role.refresh_from_db()
        self.assertFalse(role.is_active)

    def test_unauthorized_catalogue_management(self):
        with self.assertRaises(PermissionDenied):
            create_role_definition(
                organization=self.org,
                code='forbidden_role',
                name='Forbidden',
                category=RoleDefinition.Category.WORKFLOW,
                actor=self.member,
            )

    def test_cross_tenant_management_denied(self):
        with self.assertRaises(PermissionDenied):
            create_role_definition(
                organization=self.org,
                code='cross_tenant',
                name='Cross',
                category=RoleDefinition.Category.WORKFLOW,
                actor=self.outsider,
            )

    def test_system_managed_protection(self):
        role = RoleDefinition.objects.get(organization=self.org, code='workspace_admin')
        self.assertTrue(role.is_system_managed)
        with self.assertRaises(RoleDefinitionError):
            deactivate_role_definition(role, actor=self.owner)
        role.category = RoleDefinition.Category.WORKFLOW
        with self.assertRaises(RoleDefinitionError):
            role.save()

    def test_system_managed_repair_reactivates(self):
        role = RoleDefinition.objects.get(organization=self.org, code='workspace_member')
        role.is_active = False
        role.save(skip_role_definition_immutability=True)
        repair_role_definition(role, actor=self.owner, is_active=True)
        role.refresh_from_db()
        self.assertTrue(role.is_active)

    def test_active_inactive_lookup(self):
        custom = create_role_definition(
            organization=self.org,
            code='temp_role',
            name='Temp',
            category=RoleDefinition.Category.WORKFLOW,
            actor=self.owner,
        )
        deactivate_role_definition(custom, actor=self.owner)
        # Compatibility lookup for known legacy labels still finds active system seeds
        found = lookup_role_definition(self.org, source_system='profile_role', source_value='ASSOCIATE')
        self.assertIsNotNone(found)
        self.assertEqual(found.code, 'legal_reviewer')
        self.assertTrue(found.is_active)

    def test_truthful_legacy_mapping(self):
        self.assertEqual(
            lookup_role_definition(self.org, source_system='membership_role', source_value='OWNER').code,
            'workspace_owner',
        )
        self.assertEqual(
            lookup_role_definition(self.org, source_system='membership_role', source_value='ADMIN').code,
            'workspace_admin',
        )
        self.assertEqual(
            lookup_role_definition(self.org, source_system='profile_role', source_value='ASSOCIATE').code,
            'legal_reviewer',
        )
        self.assertEqual(
            lookup_role_definition(self.org, source_system='approval_step', source_value='FINANCE').code,
            'finance_approver',
        )

    def test_ambiguous_admin_not_merged(self):
        workspace = lookup_role_definition(self.org, source_system='membership_role', source_value='ADMIN')
        process = lookup_role_definition(self.org, source_system='profile_role', source_value='ADMIN')
        self.assertEqual(workspace.code, 'workspace_admin')
        self.assertEqual(process.code, 'legacy_process_admin')
        self.assertNotEqual(workspace.pk, process.pk)
        self.assertEqual(process.category, RoleDefinition.Category.LEGACY_UNKNOWN)
        # Profile ADMIN still means UserProfile.Role.ADMIN at runtime — unchanged
        self.assertEqual(UserProfile.objects.get(user=self.owner).role, UserProfile.Role.ADMIN)

    def test_unknown_legacy_maps_to_legacy_unknown(self):
        found = lookup_role_definition(self.org, source_system='profile_role', source_value='WIZARD')
        self.assertEqual(found.code, 'legacy_unknown')

    def test_queryset_update_guards(self):
        with self.assertRaises(RoleDefinitionError):
            RoleDefinition.objects.filter(organization=self.org).update(code='hacked')
        with self.assertRaises(RoleDefinitionError):
            RoleDefinition.objects.filter(organization=self.org, code='signer').update(
                is_system_managed=False,
            )

    def test_audit_events_for_lifecycle(self):
        role = create_role_definition(
            organization=self.org,
            code='audited_role',
            name='Audited',
            category=RoleDefinition.Category.WORKFLOW,
            actor=self.owner,
        )
        update_role_definition(role, actor=self.owner, description='Updated desc')
        deactivate_role_definition(role, actor=self.owner)
        events = list(
            AuditLog.objects.filter(
                organization=self.org,
                model_name='RoleDefinition',
                object_id=role.pk,
            ).values_list('event_type', flat=True)
        )
        self.assertIn(EVENT_CREATED, events)
        self.assertIn(EVENT_UPDATED, events)
        self.assertIn(EVENT_DEACTIVATED, events)

    def test_repair_emits_audit(self):
        role = RoleDefinition.objects.get(organization=self.org, code='archiver')
        repair_role_definition(role, actor=self.owner, description='Repaired description')
        self.assertTrue(
            AuditLog.objects.filter(
                organization=self.org,
                model_name='RoleDefinition',
                object_id=role.pk,
                event_type=EVENT_REPAIRED,
            ).exists()
        )

    def test_lookup_does_not_change_profile_or_membership(self):
        membership = OrganizationMembership.objects.get(user=self.member, organization=self.org)
        profile = UserProfile.objects.get(user=self.member)
        before_m, before_p = membership.role, profile.role
        lookup_role_definition(self.org, source_system='profile_role', source_value=before_p)
        membership.refresh_from_db()
        profile.refresh_from_db()
        self.assertEqual(membership.role, before_m)
        self.assertEqual(profile.role, before_p)

    def test_unique_constraint_at_db_layer(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RoleDefinition.objects.create(
                    organization=self.org,
                    code='legal_reviewer',
                    name='Dup DB',
                    category=RoleDefinition.Category.APPROVAL,
                    is_system_managed=False,
                )
