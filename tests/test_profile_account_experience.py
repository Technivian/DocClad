"""Account settings information architecture and self-service permission tests."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from contracts.models import Organization, OrganizationMembership, UserProfile


class ProfileAccountExperienceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='profile-member',
            email='member@example.com',
            first_name='Morgan',
            last_name='Lee',
            password='testpass123',
        )
        self.organization = Organization.objects.create(name='Profile Workspace', slug='profile-workspace')
        self.membership = OrganizationMembership.objects.create(
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
            language=UserProfile.Language.EN,
            timezone='UTC',
            date_format=UserProfile.DateFormat.DMY_LONG,
            notify_contract_updates=True,
            notify_workflow_events=True,
            notify_review_approval_requests=True,
            notify_obligation_reminders=False,
            notify_security_alerts=True,
        )
        self.client.login(username='profile-member', password='testpass123')

    def test_account_settings_route_and_title(self):
        response = self.client.get('/settings/profile/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Account settings')
        self.assertContains(response, 'dc-ds-shell__page-title')
        self.assertContains(response, 'Back to settings')
        self.assertContains(response, reverse('settings_hub'))
        self.assertContains(response, 'is-hash-target')
        self.assertContains(response, 'sidebar-padding')
        body = response.content.decode()
        self.assertIn('Account settings', body.split('dc-ds-shell__page-title', 1)[-1][:80])
        self.assertNotIn('>Profile</h1>', body)

    def test_profile_page_hides_legacy_fields_and_prepopulates_identity(self):
        response = self.client.get(reverse('profile'))

        self.assertContains(response, 'Personal details')
        self.assertContains(response, 'Workspace membership')
        self.assertContains(response, 'Account security')
        self.assertContains(response, 'Regional preferences')
        self.assertContains(response, 'Notifications')
        self.assertContains(response, 'value="Morgan"')
        self.assertContains(response, 'value="member@example.com"')
        self.assertNotContains(response, 'name="bar_number"')
        self.assertNotContains(response, 'name="hourly_rate"')
        self.assertNotContains(response, 'name="bio"')
        self.assertNotContains(response, 'name="role"')

    def test_layout_places_notifications_full_width(self):
        response = self.client.get(reverse('profile'))
        body = response.content.decode()
        grid = body.split('profile-page__grid', 1)[-1].split('id="notification-settings"', 1)[0]
        self.assertIn('Personal details', grid)
        self.assertIn('Account security', grid)
        self.assertIn('Workspace membership', grid)
        self.assertIn('Regional preferences', grid)
        self.assertNotIn('id="notification-settings"', grid)
        self.assertIn('profile-page__card--notifications', body)
        self.assertIn('profile-notify-table', body)

    def test_account_settings_grid_stretches_paired_cards(self):
        from pathlib import Path

        css = Path('theme/static/css/profile.css').read_text()
        self.assertIn('align-items: stretch', css)
        self.assertIn('.profile-page__actions', css)
        self.assertIn('margin-top: auto', css)

    def test_profile_header_is_compact_without_eyebrow(self):
        response = self.client.get(reverse('profile'))
        body = response.content.decode()
        main = body.split('<main class="profile-page"', 1)[-1].split('</main>', 1)[0]
        self.assertNotIn('CLM One account', main)
        self.assertNotIn('dc-ds-eyebrow', main)
        self.assertIn('Member since', main)
        self.assertIn('member@example.com', main)
        self.assertIn('Member', main)
        self.assertContains(response, 'sidebar-profile-avatar')
        self.assertContains(response, 'Save changes')
        self.assertContains(response, 'disabled>Save changes</button>')
        self.assertContains(response, 'data-dirty-form')
        self.assertContains(response, 'beforeunload')

    def test_email_editable_badge_for_local_accounts(self):
        response = self.client.get(reverse('profile'))
        self.assertContains(response, 'Editable')
        self.assertContains(response, 'You can update this email for your account.')
        self.assertNotContains(response, 'Managed by organization')

    def test_workspace_membership_uses_read_only_definition_list(self):
        response = self.client.get(reverse('profile'))
        self.assertContains(response, 'Workspace membership')
        self.assertContains(response, 'Workspace role')
        self.assertContains(response, 'Permission set')
        self.assertContains(response, 'Standard member')
        self.assertContains(response, 'profile-info-list')
        self.assertContains(response, 'Your workspace role is managed by a workspace administrator.')
        self.assertNotContains(response, 'Access level')
        self.assertNotContains(response, '>Permissions<')
        self.assertNotContains(response, 'Product role')
        self.assertNotContains(response, 'Manage members and roles')

        self.membership.role = OrganizationMembership.Role.OWNER
        self.membership.save(update_fields=['role'])
        admin_response = self.client.get(reverse('profile'))
        self.assertContains(admin_response, 'Your workspace role grants full administrative access.')
        self.assertContains(admin_response, 'Manage members and roles')
        self.assertContains(admin_response, 'Workspace administrator')

    def test_security_summary_and_session_management(self):
        response = self.client.get(reverse('profile'))
        self.assertContains(response, 'Manage sessions')
        self.assertNotContains(response, 'Manage my sessions')
        self.assertNotContains(response, 'Review workspace sessions')
        self.assertContains(response, 'Active sessions')
        self.assertNotContains(response, 'Personal active sessions')
        self.assertContains(response, 'Sign-in method')
        self.assertContains(response, 'Recovery method')
        self.assertContains(response, 'Multi-factor authentication')
        self.assertContains(response, 'Set up MFA')
        self.assertContains(response, 'Change password')
        self.assertContains(response, reverse('profile_password_change'))
        self.assertContains(response, 'profile-security-list')

    def test_password_change_available_for_local_accounts(self):
        response = self.client.get(reverse('profile_password_change'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Change password')
        self.assertContains(response, 'Back to Account settings')

    def test_regional_and_notification_controls(self):
        response = self.client.get(reverse('profile'))
        self.assertContains(response, 'id="regional-preferences"')
        self.assertContains(response, 'id="notification-settings"')
        self.assertContains(response, 'name="language"')
        self.assertContains(response, 'name="timezone"')
        self.assertContains(response, 'name="date_format"')
        self.assertContains(response, 'Example:')
        self.assertContains(response, 'regional-preview-formats')
        self.assertContains(response, 'name="notify_contract_updates"')
        self.assertContains(response, 'name="notify_workflow_events"')
        self.assertContains(response, 'name="notify_review_approval_requests"')
        self.assertContains(response, 'name="notify_obligation_reminders"')
        self.assertContains(response, 'name="notify_security_alerts"')
        self.assertContains(response, 'Required security notifications cannot be disabled.')
        self.assertContains(response, 'Always on')
        self.assertContains(response, 'profile-switch--locked')
        self.assertContains(response, 'profile-switch')
        self.assertContains(response, 'aria-live="polite"')

    def test_mfa_setup_is_collapsed_until_started(self):
        response = self.client.get(reverse('profile'))
        self.assertContains(response, 'Set up MFA')
        self.assertNotContains(response, 'name="mfa_enrollment_code"')

        started = self.client.post(reverse('profile'), {'action': 'start_mfa_setup'})
        self.assertEqual(started.status_code, 302)
        response = self.client.get(started['Location'])
        self.assertContains(response, 'Send email verification code')
        self.assertContains(response, 'name="mfa_enrollment_code"')
        self.assertContains(response, 'Email verification code')

    def test_role_post_is_ignored_by_self_service_profile_update(self):
        response = self.client.post(reverse('profile'), {
            'action': 'save_identity',
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
        self.assertEqual(self.profile.language, UserProfile.Language.EN)
        self.assertTrue(self.profile.notify_contract_updates)

    def test_section_save_messages_and_saved_query(self):
        identity = self.client.post(reverse('profile'), {
            'action': 'save_identity',
            'first_name': 'Morgan',
            'last_name': 'Lee',
            'email': 'member@example.com',
            'phone': '555-0100',
            'department': 'Legal',
        }, follow=True)
        self.assertContains(identity, 'Personal details saved.')
        self.assertIn('saved=identity', identity.request['QUERY_STRING'])

        regional = self.client.post(reverse('profile'), {
            'action': 'save_regional',
            'language': UserProfile.Language.NL,
            'timezone': 'Europe/Amsterdam',
            'date_format': UserProfile.DateFormat.ISO,
        }, follow=True)
        self.assertContains(regional, 'Regional preferences saved.')
        self.assertIn('saved=regional', regional.request['QUERY_STRING'])

        notifications = self.client.post(reverse('profile'), {
            'action': 'save_notifications',
            'notify_contract_updates': 'on',
            'notify_security_alerts': 'on',
        }, follow=True)
        self.assertContains(notifications, 'Notification preferences saved.')
        self.assertIn('saved=notifications', notifications.request['QUERY_STRING'])

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.language, UserProfile.Language.NL)
        self.assertEqual(self.profile.timezone, 'Europe/Amsterdam')
        self.assertEqual(self.profile.date_format, UserProfile.DateFormat.ISO)
        self.assertTrue(self.profile.notify_contract_updates)
        self.assertFalse(self.profile.notify_workflow_events)
        self.assertTrue(self.profile.notify_security_alerts)

    def test_mandatory_security_alerts_cannot_be_disabled(self):
        response = self.client.post(reverse('profile'), {
            'action': 'save_notifications',
            'notify_contract_updates': 'on',
            # omit notify_security_alerts intentionally
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.notify_security_alerts)

    def test_legacy_save_action_still_works(self):
        response = self.client.post(reverse('profile'), {
            'action': 'save',
            'first_name': 'Morgan',
            'last_name': 'Lee',
            'email': 'member@example.com',
            'phone': '555-0100',
            'department': 'Legal',
            'language': UserProfile.Language.NL,
            'timezone': 'Europe/Amsterdam',
            'date_format': UserProfile.DateFormat.ISO,
            'notify_contract_updates': 'on',
            'notify_security_alerts': 'on',
        }, follow=True)
        self.assertContains(response, 'Account updated successfully.')

    def test_profile_page_hides_authenticated_footer(self):
        response = self.client.get(reverse('profile'))
        self.assertTrue(response.context['hide_app_footer'])
        self.assertNotContains(response, 'All rights reserved.')

    def test_responsive_css_stacks_grid(self):
        css_path = reverse('profile')  # load page that references CSS
        response = self.client.get(css_path)
        self.assertContains(response, 'css/profile.css')
        from pathlib import Path
        from django.conf import settings
        css = (Path(settings.BASE_DIR) / 'theme' / 'static' / 'css' / 'profile.css').read_text()
        self.assertIn('@media (max-width: 1024px)', css)
        self.assertIn('grid-template-columns: 1fr', css)
        self.assertIn('profile-page__card--notifications', css)

    def test_profile_sessions_page(self):
        response = self.client.get(reverse('profile_sessions'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'My sessions')
        self.assertContains(response, reverse('profile'))
        self.assertContains(response, 'Back to Account settings')
