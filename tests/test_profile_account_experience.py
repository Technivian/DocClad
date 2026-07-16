"""Account-page information architecture and self-service permission tests."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from contracts.models import Organization, OrganizationMembership, UserProfile


class ProfileAccountExperienceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='account-member',
            email='member@example.com',
            first_name='Morgan',
            last_name='Lee',
            password='testpass123',
        )
        self.organization = Organization.objects.create(name='Account Workspace', slug='account-workspace')
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.user,
            role=OrganizationMembership.Role.MEMBER,
            is_active=True,
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            role=UserProfile.Role.ASSOCIATE,
            phone='555-0100',
            department='Legal',
            bar_number='BAR-100',
            hourly_rate='300.00',
            bio='Legacy professional profile data.',
        )
        self.client.login(username='account-member', password='testpass123')

    def test_account_page_hides_legacy_fields_and_prepopulates_identity(self):
        response = self.client.get(reverse('profile'))

        self.assertContains(response, 'Workspace access')
        self.assertContains(response, 'Security')
        self.assertContains(response, 'Preferences')
        self.assertContains(response, 'value="Morgan"')
        self.assertContains(response, 'value="member@example.com"')
        self.assertNotContains(response, 'name="bar_number"')
        self.assertNotContains(response, 'name="hourly_rate"')
        self.assertNotContains(response, 'name="bio"')
        self.assertNotContains(response, 'name="role"')

    def test_role_post_is_ignored_by_self_service_account_update(self):
        response = self.client.post(reverse('profile'), {
            'first_name': 'Morgan',
            'last_name': 'Lee',
            'email': 'member@example.com',
            'phone': '555-0200',
            'department': 'Legal Operations',
            'role': UserProfile.Role.ADMIN,
        })

        self.assertEqual(response.status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.role, UserProfile.Role.ASSOCIATE)
        self.assertEqual(self.profile.department, 'Legal Operations')
