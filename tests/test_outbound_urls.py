from django.test import SimpleTestCase

from contracts.services.outbound_urls import OutboundURLValidationError, validate_public_https_url


class OutboundURLValidationTests(SimpleTestCase):
    def test_accepts_public_https_url(self):
        self.assertEqual(
            validate_public_https_url('https://hooks.example.com/events', label='Webhook'),
            'https://hooks.example.com/events',
        )

    def test_rejects_insecure_or_internal_targets(self):
        for value in ('http://example.com', 'https://localhost/hook', 'https://127.0.0.1/hook', 'https://10.0.0.8/hook'):
            with self.subTest(value=value):
                with self.assertRaises(OutboundURLValidationError):
                    validate_public_https_url(value, label='Webhook')

    def test_enforces_an_optional_domain_allowlist(self):
        validate_public_https_url(
            'https://api.example.com/events', label='Webhook', allowed_hosts=('example.com',),
        )
        with self.assertRaises(OutboundURLValidationError):
            validate_public_https_url(
                'https://other.example.net/events', label='Webhook', allowed_hosts=('example.com',),
            )
