"""Branded error pages + no-traceback-leak (audit findings B4 / C11).

Verifies:
  - Custom 404/500/403/400 templates exist, render, and carry CLM One branding.
  - A 404 served by the app uses the branded template (not Django's default).
  - PreviewExceptionMiddleware does NOT leak a traceback when DEBUG is off.

Run: DJANGO_SETTINGS_MODULE=config.settings_test python manage.py test \
        tests.test_error_pages
"""
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase, override_settings

from contracts.middleware import PreviewExceptionMiddleware


class ErrorTemplateTests(TestCase):
    def test_all_error_templates_render_with_branding(self):
        for name in ('400.html', '403.html', '404.html', '500.html'):
            html = render_to_string(name)
            self.assertIn('CLM One', html, f'{name} missing branding')
            # No Django technical-500 markers should ever appear.
            self.assertNotIn('Traceback', html)

    def test_app_404_uses_branded_template(self):
        resp = self.client.get('/this-path-does-not-exist-xyz/')
        self.assertEqual(resp.status_code, 404)
        self.assertContains(resp, 'Page not found', status_code=404)


class PreviewExceptionLeakTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _boom(self, request):
        raise RuntimeError('secret-internal-detail-12345')

    @override_settings(DEBUG=False)
    def test_no_traceback_leak_in_production(self):
        mw = PreviewExceptionMiddleware(self._boom)
        request = self.factory.get('/anything/')
        # In production the middleware must re-raise (Django then renders the
        # branded handler500) rather than return the exception text.
        with self.assertRaises(RuntimeError):
            mw(request)

    @override_settings(DEBUG=True)
    def test_verbose_only_in_debug(self):
        mw = PreviewExceptionMiddleware(self._boom)
        request = self.factory.get('/anything/')
        resp = mw(request)
        self.assertEqual(resp.status_code, 500)
        self.assertIn('secret-internal-detail-12345', resp.content.decode())
