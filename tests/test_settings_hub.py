"""Settings configuration hub — compact landing page for personal, workspace,
and security destinations with permission-aware Admin-only cards."""
from django.contrib.auth import get_user_model
from django.test import Client as TestClient
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from contracts.models import Organization, OrganizationMembership
from contracts.nav_config import get_nav_for
from pathlib import Path

from django.conf import settings

User = get_user_model()

PERSONAL_LABELS = {
    'Account settings',
    'Notifications',
    'Appearance and language',
}
WORKSPACE_LABELS = {
    'Members and roles',
    'Contract types and intake',
    'Workflow templates',
    'Negotiation playbooks',
    'Approval policies',
    'Integrations',
}
SECURITY_LABELS = {
    'Authentication and access',
    'Workspace sessions',
    'Audit log',
}


class SettingsHubViewTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Settings Hub Org', slug='settings-hub-org')
        self.member = User.objects.create_user(username='settings_member', password='testpass123!')
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.member,
            role=OrganizationMembership.Role.MEMBER,
            is_active=True,
        )
        self.admin = User.objects.create_user(username='settings_admin', password='testpass123!')
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.admin,
            role=OrganizationMembership.Role.ADMIN,
            is_active=True,
        )
        self.member_client = TestClient()
        self.member_client.login(username='settings_member', password='testpass123!')
        self.admin_client = TestClient()
        self.admin_client.login(username='settings_admin', password='testpass123!')

    def _labels(self, response):
        return {
            card['label']
            for group in response.context['settings_groups']
            for card in group['cards']
        }

    def test_hub_renders_compact_groups_and_subtitle(self):
        response = self.admin_client.get(reverse('settings_hub'))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        groups = {group['title'] for group in response.context['settings_groups']}
        labels = self._labels(response)
        self.assertIn('settings-hub-page', body)
        self.assertIn('Configure personal preferences, workspace defaults, and security controls.', body)
        self.assertEqual(groups, {'Personal', 'Workspace', 'Security and governance'})
        self.assertEqual(labels, PERSONAL_LABELS | WORKSPACE_LABELS | SECURITY_LABELS)
        self.assertNotIn('Configuration areas', body)
        self.assertNotIn('Organization Team', body)
        self.assertNotIn('Admin workspace', body)
        self.assertNotIn('Operations Dashboard', body)
        self.assertNotIn('Clause Library', body)
        # Content libraries stay under Templates & Playbooks, not Settings.
        self.assertNotIn('>Templates</', ''.join(f'>{label}</' for label in labels))
        # Operations lives in Admin nav, not as a settings hub card.
        self.assertNotIn('>Operations</', ''.join(f'>{label}</' for label in labels))

    def test_hub_uses_navigation_cards_with_icons_and_arrows(self):
        response = self.admin_client.get(reverse('settings_hub'))
        body = response.content.decode()
        self.assertIn('dc-ds-card-grid dc-ds-card-grid--3', body)
        self.assertIn('dc-ds-setup-action--hub', body)
        self.assertIn('dc-ds-setup-action__icon', body)
        self.assertIn('dc-ds-setup-action__arrow', body)
        self.assertIn('Members and roles', body)
        self.assertIn('Approval policies', body)
        self.assertIn('Workspace sessions', body)
        self.assertIn('Audit log', body)
        self.assertIn('Appearance and language', body)
        self.assertIn('Manage your personal details and account preferences.', body)
        self.assertIn('Review and revoke active user sessions across the workspace.', body)

    def test_hub_cards_point_to_real_destinations(self):
        response = self.admin_client.get(reverse('settings_hub'))
        profile = reverse('profile')
        expected = {
            'Account settings': profile,
            'Notifications': f'{profile}#notification-settings',
            'Appearance and language': f'{profile}#regional-preferences',
            'Members and roles': reverse('contracts:organization_team'),
            'Contract types and intake': reverse('contracts:templates_playbooks_hub'),
            'Workflow templates': reverse('contracts:workflow_template_list'),
            'Negotiation playbooks': reverse('contracts:dpa_playbook_list'),
            'Approval policies': reverse('contracts:approval_rule_list'),
            'Integrations': reverse('organization_identity_settings'),
            'Authentication and access': reverse('organization_security_settings'),
            'Workspace sessions': reverse('organization_session_audit'),
            'Audit log': reverse('contracts:organization_activity'),
        }
        cards = {
            card['label']: card['href']
            for group in response.context['settings_groups']
            for card in group['cards']
        }
        self.assertEqual(cards, expected)
        self.assertNotIn(reverse('contracts:clause_template_list'), cards.values())
        self.assertNotIn(reverse('contracts:notification_list'), cards.values())

    def test_member_sees_personal_without_admin_cards(self):
        response = self.member_client.get(reverse('settings_hub'))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        labels = self._labels(response)
        self.assertEqual(labels, PERSONAL_LABELS)
        self.assertIn('Account settings', body)
        self.assertIn('Notifications', body)
        self.assertIn('Appearance and language', body)
        self.assertNotIn('Members and roles', body)
        self.assertNotIn('Workflow templates', body)
        self.assertNotIn('Authentication and access', body)
        self.assertNotIn('Workspace sessions', body)
        self.assertNotIn('Admin only', body)
        self.assertFalse(response.context['can_manage_settings'])

    def test_personal_cards_are_never_admin_only(self):
        response = self.admin_client.get(reverse('settings_hub'))
        personal = next(group for group in response.context['settings_groups'] if group['id'] == 'personal')
        for card in personal['cards']:
            self.assertFalse(card['admin_only'], card['label'])
            self.assertEqual(card['badge_label'], '')

    def test_admin_sees_admin_only_badges_on_gated_cards(self):
        response = self.admin_client.get(reverse('settings_hub'))
        body = response.content.decode()
        self.assertTrue(response.context['can_manage_settings'])
        self.assertIn('Admin only', body)
        self.assertIn('dc-ds-badge--admin', body)
        self.assertContains(response, reverse('contracts:organization_team'))
        self.assertContains(response, reverse('organization_security_settings'))
        self.assertContains(response, reverse('organization_session_audit'))
        self.assertContains(response, reverse('organization_identity_settings'))
        self.assertContains(response, reverse('contracts:templates_playbooks_hub'))

    def test_hub_sections_are_labelled_for_accessibility(self):
        response = self.admin_client.get(reverse('settings_hub'))
        body = response.content.decode()
        self.assertIn('aria-labelledby="settings-group-personal"', body)
        self.assertIn('id="settings-group-personal"', body)
        self.assertIn('aria-labelledby="settings-group-workspace"', body)
        self.assertIn('aria-labelledby="settings-group-security"', body)
        self.assertIn('aria-label="Account settings. Manage your personal details and account preferences."', body)
        self.assertIn('role="list"', body)
        self.assertIn('role="listitem"', body)

    def test_anonymous_user_is_redirected(self):
        anon = TestClient()
        response = anon.get(reverse('settings_hub'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)


class SettingsHubNavigationTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Settings Nav Org', slug='settings-nav-org')
        self.member = User.objects.create_user(username='settings_nav_member', password='testpass123!')
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.member,
            role=OrganizationMembership.Role.MEMBER,
            is_active=True,
        )
        self.admin = User.objects.create_user(username='settings_nav_admin', password='testpass123!')
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.admin,
            role=OrganizationMembership.Role.ADMIN,
            is_active=True,
        )

    def test_sidebar_no_longer_exposes_admin_group(self):
        for user in (self.admin, self.member):
            nav = get_nav_for(self.org, user)
            labels = [entry.get('label') for entry in nav]
            self.assertNotIn('Admin', labels)
            self.assertNotIn('Settings', labels)
            self.assertNotIn('Operations', labels)

    def test_admin_profile_menu_exposes_settings_and_operations(self):
        client = TestClient()
        client.login(username='settings_nav_admin', password='testpass123!')
        response = client.get(reverse('dashboard'))
        body = response.content.decode()
        self.assertIn('href="' + reverse('profile') + '"', body)
        self.assertIn('profile-menu-header__name', body)
        self.assertNotIn('role="menuitem">Account</a>', body)
        self.assertIn('role="menuitem">Settings</a>', body)
        self.assertIn('role="menuitem">Operations</a>', body)
        self.assertIn('role="menuitem">Notifications</a>', body)
        self.assertIn(reverse('settings_hub'), body)
        self.assertIn(reverse('operations_dashboard'), body)
        self.assertNotIn('class="nav-group"', body)

    def test_member_profile_menu_hides_operations(self):
        client = TestClient()
        client.login(username='settings_nav_member', password='testpass123!')
        response = client.get(reverse('dashboard'))
        body = response.content.decode()
        self.assertIn('href="' + reverse('profile') + '"', body)
        self.assertIn('profile-menu-header__name', body)
        self.assertNotIn('role="menuitem">Account</a>', body)
        self.assertIn('role="menuitem">Settings</a>', body)
        self.assertIn('role="menuitem">Notifications</a>', body)
        self.assertNotIn('role="menuitem">Operations</a>', body)


class SettingsHubResponsiveContractTests(SimpleTestCase):
    def test_card_grid_collapses_on_narrow_viewports(self):
        components = (
            Path(settings.BASE_DIR) / 'theme' / 'static_src' / 'src' / 'design-system' / 'components.css'
        ).read_text()
        self.assertIn('.dc-ds-card-grid--3', components)
        self.assertIn('@media (max-width: 1024px)', components)
        self.assertIn('@media (max-width: 640px)', components)
        # Compact cards remain single-column on small screens.
        self.assertIn(
            '.dc-ds-card-grid--3,\n  .dc-ds-summary { grid-template-columns: 1fr; }',
            components,
        )

    def test_setup_action_supports_admin_badge_markup(self):
        partial = (
            Path(settings.BASE_DIR) / 'theme' / 'templates' / 'design_system' / 'setup_action.html'
        ).read_text()
        self.assertIn('badge_label', partial)
        self.assertIn('badge_class', partial)
        self.assertIn('aria-label', partial)
        self.assertIn('dc-ds-setup-action__arrow', partial)

    def test_hub_template_enforces_card_interaction_contract(self):
        template = (
            Path(settings.BASE_DIR) / 'theme' / 'templates' / 'settings_hub.html'
        ).read_text()
        self.assertIn('dc-ds-setup-action--hub', template)
        self.assertIn('translateX(2px)', template)
        self.assertIn('dc-ds-badge--admin', template)
        self.assertIn('-webkit-line-clamp: 2', template)
        self.assertIn('min-height: 112px', template)
