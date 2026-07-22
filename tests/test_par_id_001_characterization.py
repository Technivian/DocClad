"""PAR-ID-001 characterization tests — lock interim dual-role semantics before reconciliation.

These tests document current behavior that MUST remain truthful during discovery
and MUST be preserved or explicitly migrated during Role Definition reconciliation.
No schema changes; no privilege model changes.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from contracts.models import Organization, OrganizationMembership, UserProfile


User = get_user_model()


class RoleDefinitionInterimCharacterizationTests(TestCase):
    """Baseline semantics while OrganizationMembership.Role and UserProfile.Role coexist."""

    def setUp(self):
        self.org = Organization.objects.create(name='Role Char Org', slug='role-char-org')
        self.owner_user = User.objects.create_user(username='role-owner', password='pass12345')
        self.member_user = User.objects.create_user(username='role-member', password='pass12345')

        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.owner_user,
            role=OrganizationMembership.Role.OWNER,
            is_active=True,
        )
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.member_user,
            role=OrganizationMembership.Role.MEMBER,
            is_active=True,
        )
        UserProfile.objects.create(user=self.owner_user, role=UserProfile.Role.ADMIN)
        UserProfile.objects.create(user=self.member_user, role=UserProfile.Role.ASSOCIATE)

    def test_organization_membership_role_is_independent_of_user_profile_role(self):
        """Pilot pattern: MEMBER org role + ASSOCIATE process role is valid."""
        membership = OrganizationMembership.objects.get(user=self.member_user, organization=self.org)
        profile = UserProfile.objects.get(user=self.member_user)
        self.assertEqual(membership.role, OrganizationMembership.Role.MEMBER)
        self.assertEqual(profile.role, UserProfile.Role.ASSOCIATE)
        self.assertNotEqual(membership.role, profile.role)

    def test_admin_exists_in_both_enums_with_different_meaning(self):
        """ADMIN in org membership vs profile are distinct concepts — must not be conflated."""
        owner_membership = OrganizationMembership.objects.get(user=self.owner_user, organization=self.org)
        owner_profile = UserProfile.objects.get(user=self.owner_user)
        self.assertEqual(owner_membership.role, OrganizationMembership.Role.OWNER)
        self.assertEqual(owner_profile.role, UserProfile.Role.ADMIN)
        self.assertIn('ADMIN', OrganizationMembership.Role.values)
        self.assertIn('ADMIN', UserProfile.Role.values)

    def test_organization_membership_role_choices_are_workspace_scoped(self):
        self.assertEqual(
            set(OrganizationMembership.Role.values),
            {'OWNER', 'ADMIN', 'MEMBER'},
        )

    def test_user_profile_role_choices_are_process_scoped(self):
        self.assertEqual(
            set(UserProfile.Role.values),
            {
                'PARTNER',
                'SENIOR_ASSOCIATE',
                'ASSOCIATE',
                'PARALEGAL',
                'LEGAL_ASSISTANT',
                'ADMIN',
                'CLIENT',
            },
        )

    def test_membership_role_does_not_auto_sync_to_profile_role(self):
        """No automatic sync — profile is created separately with its own default."""
        new_user = User.objects.create_user(username='role-new', password='pass12345')
        OrganizationMembership.objects.create(
            organization=self.org,
            user=new_user,
            role=OrganizationMembership.Role.ADMIN,
            is_active=True,
        )
        self.assertFalse(UserProfile.objects.filter(user=new_user).exists())
        profile, _ = UserProfile.objects.get_or_create(user=new_user)
        self.assertEqual(profile.role, UserProfile.Role.ASSOCIATE)  # model default
        membership = OrganizationMembership.objects.get(user=new_user, organization=self.org)
        self.assertEqual(membership.role, OrganizationMembership.Role.ADMIN)
        self.assertNotEqual(membership.role, profile.role)
