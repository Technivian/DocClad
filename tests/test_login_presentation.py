from pathlib import Path

from django.conf import settings
from django.template import engines
from django.test import TestCase
from django.urls import reverse


class LoginPresentationTests(TestCase):
    def test_login_uses_enterprise_authentication_composition(self):
        response = self.client.get(reverse('login'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'dc-ds-auth-shell')
        self.assertContains(response, 'Governed contract operations')
        self.assertContains(response, 'Control every contract decision.')
        self.assertContains(response, 'Secure enterprise access')
        self.assertContains(response, 'Continue with SSO')
        self.assertContains(response, 'Create workspace')
        self.assertContains(response, reverse('saml_select'))
        self.assertContains(response, reverse('register'))
        self.assertContains(response, reverse('password_reset'))

    def test_login_has_one_logo_and_no_retired_saas_copy(self):
        response = self.client.get(reverse('login'))
        body = response.content.decode()

        self.assertEqual(body.count('alt="CLM One"'), 1)
        for retired_copy in (
            'Protect your portfolio',
            'Empower your team',
            'billable hours',
            'generate invoices',
            'Sign in with SAML',
            'Create one free',
        ):
            self.assertNotIn(retired_copy, body)

    def test_authentication_fields_and_routes_are_preserved(self):
        response = self.client.get(reverse('login') + '?next=/contracts/')
        body = response.content.decode()

        for contract in (
            'method="post"',
            'name="username"',
            'autocomplete="username"',
            'name="password"',
            'autocomplete="current-password"',
            'name="remember"',
            'type="submit"',
        ):
            self.assertIn(contract, body)

    def test_auth_shell_is_shared_and_responsive(self):
        root = Path(settings.BASE_DIR)
        components = (
            root / 'theme' / 'static_src' / 'src' / 'design-system' / 'components.css'
        ).read_text()
        login = (
            root / 'theme' / 'templates' / 'registration' / 'login.html'
        ).read_text()

        for selector in (
            '.dc-ds-auth-shell',
            '.dc-ds-auth-context',
            '.dc-ds-auth-main',
            '.dc-ds-auth-card',
            '.dc-ds-auth-provider',
            '.dc-ds-auth-trust',
        ):
            self.assertIn(selector, components)
        self.assertIn('@media (max-width: 900px)', components)
        self.assertIn('design_system/button.html', login)
        self.assertIn('design_system/icon.html', login)
        self.assertIn('design_system/provider_icon.html', login)
        self.assertNotIn('<style', login)

    def test_google_provider_mark_is_rendered_by_shared_component(self):
        template = engines['django'].from_string(
            '{% include "design_system/provider_icon.html" with provider="google" %}'
        )
        rendered = template.render({})

        self.assertIn('data-provider-icon="google"', rendered)
        self.assertIn('dc-ds-auth-provider__icon', rendered)
