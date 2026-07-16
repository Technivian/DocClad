import re
from pathlib import Path

from django.conf import settings
from django.template import engines
from django.test import SimpleTestCase


class ExpressiveDesignSystemContractTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.root = Path(settings.BASE_DIR)
        cls.tokens = (
            cls.root / 'theme' / 'static' / 'css' / 'clmone-tokens.css'
        ).read_text()
        cls.components = (
            cls.root / 'theme' / 'static_src' / 'src' / 'design-system' / 'components.css'
        ).read_text()
        cls.dashboard = (
            cls.root / 'theme' / 'templates' / 'dashboard.html'
        ).read_text()
        cls.catalog = (
            cls.root / 'theme' / 'templates' / 'design_system' / 'catalog.html'
        ).read_text()

    def test_expressive_tokens_are_canonical(self):
        for token in (
            '--color-surface-canvas-cool',
            '--color-feature-cyan',
            '--color-state-clear',
            '--gradient-feature',
            '--radius-surface',
            '--radius-feature',
            '--shadow-surface-expressive',
            '--shadow-feature',
            '--shell-sidebar-width-spacious',
            '--context-rail-width-spacious',
            '--feature-surface-min-height',
        ):
            self.assertIn(token, self.tokens)

    def test_shared_expressive_components_exist(self):
        for selector in (
            '.dc-ds-surface--expressive',
            '.dc-ds-surface--feature',
            '.dc-ds-metric--expressive',
            '.dc-ds-metric__value--clear',
            '.dc-ds-empty--activation',
            '.dc-ds-setup-action',
            '.dc-ds-shell-callout',
        ):
            self.assertIn(selector, self.components)

    def test_command_center_consumes_shared_variants(self):
        for class_name in (
            'dc-ds-surface--feature',
            'dc-ds-surface--feature-clear',
            'dc-ds-surface--expressive',
            'dc-ds-metric--expressive',
            'dc-ds-metric__value--clear',
            'dc-ds-setup-list',
            'design_system/setup_action.html',
        ):
            self.assertIn(class_name, self.dashboard)

        self.assertIn('dc-ds-shell-callout', self.catalog)

    def test_reference_layer_uses_tokens_instead_of_page_hex_values(self):
        css = (
            self.root / 'theme' / 'static' / 'css' / 'command-center.css'
        ).read_text()
        reference_layer = css.split('/* Reference-led visual layer for the dashboard work surface.', 1)[1]
        hex_values = set(re.findall(r'#[0-9a-fA-F]{3,8}', reference_layer))
        self.assertEqual(hex_values, {'#000'})

    def test_command_center_alignment_layer_uses_shared_tokens(self):
        css = (
            self.root / 'theme' / 'static' / 'css' / 'command-center.css'
        ).read_text()
        alignment = css.split('/* Shared token alignment.', 1)[1]

        for token in (
            '--page-padding-x',
            '--space-24',
            '--radius-surface',
            '--radius-feature',
            '--radius-subpanel',
            '--color-border-soft',
            '--shadow-surface-expressive',
        ):
            self.assertIn(f'var({token})', alignment)

    def test_setup_action_partial_renders_shared_anatomy(self):
        template = engines['django'].from_string(
            '{% include "design_system/setup_action.html" '
            'with href="/setup/" icon="workflow" label="Configure approvals" '
            'copy="Define the route." %}'
        )
        rendered = template.render({})
        self.assertIn('dc-ds-setup-action', rendered)
        self.assertIn('Configure approvals', rendered)
        self.assertIn('/setup/', rendered)
