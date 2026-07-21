"""Guard against template {% url %} names that are not registered.

Prevents NoReverseMatch regressions like missing ``my_work_saved_views_api``
when a My Work (or other) template references a route that was never wired.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.test import SimpleTestCase
from django.urls import get_resolver, reverse

_REPO = Path(__file__).resolve().parent.parent
_CRITICAL_TEMPLATES = (
    _REPO / 'theme' / 'templates' / 'contracts' / 'my_work.html',
    _REPO / 'theme' / 'templates' / 'contracts' / 'workflow_template_detail.html',
    _REPO / 'theme' / 'templates' / 'contracts' / 'privacy_dashboard.html',
)

_URL_TAG_RE = re.compile(
    r"""\{%\s*url\s+(['"])(?P<name>[^'"]+)\1""",
)


def _registered_url_names() -> set[str]:
    names: set[str] = set()

    def _walk(resolver, namespace: str = ''):
        for pattern in resolver.url_patterns:
            pattern_ns = getattr(pattern, 'namespace', None)
            if pattern_ns:
                _walk(pattern, f'{namespace}:{pattern_ns}' if namespace else pattern_ns)
                continue
            pattern_name = getattr(pattern, 'name', None)
            if pattern_name:
                names.add(f'{namespace}:{pattern_name}' if namespace else pattern_name)
            if hasattr(pattern, 'url_patterns'):
                _walk(pattern, namespace)

    _walk(get_resolver())
    return names


class TemplateNamedUrlIntegrityTests(SimpleTestCase):
    def test_critical_templates_named_urls_are_registered(self):
        registered = _registered_url_names()
        failures = []
        for path in _CRITICAL_TEMPLATES:
            if not path.exists():
                continue
            text = path.read_text(encoding='utf-8')
            for match in _URL_TAG_RE.finditer(text):
                url_name = match.group('name')
                if url_name not in registered:
                    failures.append(
                        f"{path.name}: {{% url '{url_name}' %}} is not a registered URL name"
                    )
        self.assertEqual(failures, [], 'Unregistered template URL names:\n' + '\n'.join(failures))

    def test_my_work_saved_views_api_wired_if_template_references_it(self):
        path = _REPO / 'theme' / 'templates' / 'contracts' / 'my_work.html'
        text = path.read_text(encoding='utf-8')
        if 'my_work_saved_views_api' not in text:
            self.skipTest('My Work template does not reference saved views API')
        reverse('contracts:my_work_saved_views_api')
        reverse('contracts:my_work_saved_view_detail_api', kwargs={'view_id': 1})
