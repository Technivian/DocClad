import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class DesignSystemPhaseOneTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.root = Path(settings.BASE_DIR)
        cls.theme = cls.root / 'theme'
        cls.canonical = (
            cls.theme / 'static' / 'css' / 'clmone-tokens.css'
        ).read_text()

    def test_all_ds_consumers_resolve_through_canonical_aliases(self):
        consumers = set()
        for css_file in (self.theme / 'static_src' / 'src').rglob('*.css'):
            consumers.update(re.findall(r'var\((--ds-[a-z0-9-]+)', css_file.read_text()))

        canonical_aliases = set(
            re.findall(r'^\s*(--ds-[a-z0-9-]+)\s*:', self.canonical, re.MULTILINE)
        )
        # Component-local chart swatches are instance state, not foundation tokens.
        unresolved = consumers - canonical_aliases - {'--ds-chart-color'}
        self.assertEqual(unresolved, set())

    def test_ds_aliases_are_deprecated_and_defined_only_in_canonical_file(self):
        alias_lines = [
            line for line in self.canonical.splitlines()
            if re.match(r'^\s*--ds-[a-z0-9-]+\s*:', line)
        ]
        self.assertEqual(len(alias_lines), 76)
        self.assertTrue(all('deprecated:' in line for line in alias_lines))

        adapter = (
            self.theme / 'static_src' / 'src' / 'design-system' / 'tokens.css'
        ).read_text()
        self.assertIsNone(re.search(r'^\s*--ds-[a-z0-9-]+\s*:', adapter, re.MULTILINE))
        self.assertIn('clmone-tokens.css', adapter)

    def test_aliases_load_before_every_compiled_consumer(self):
        for template_name in ('base.html', 'base_fullscreen.html'):
            template = (self.theme / 'templates' / template_name).read_text()
            self.assertLess(
                template.index("css/clmone-tokens.css"),
                template.index("css/dist/styles.css"),
                template_name,
            )

        styles = (self.theme / 'static_src' / 'src' / 'styles.css').read_text()
        index = (
            self.theme / 'static_src' / 'src' / 'design-system' / 'index.css'
        ).read_text()
        self.assertIn('@import "./design-system/index.css"', styles)
        self.assertLess(index.index('@import "./tokens.css"'), index.index('@import "./components.css"'))
        self.assertLess(index.index('@import "./tokens.css"'), index.index('@import "./premium.css"'))

    def test_authentication_shell_uses_canonical_brand_and_focus_tokens(self):
        auth_shell = (self.theme / 'templates' / 'base_fullscreen.html').read_text()
        for retired_literal in ('#315EF6', '#1B7F5A', '#176B4D'):
            self.assertNotIn(retired_literal, auth_shell)
        self.assertIn('--primary: var(--seal)', auth_shell)
        self.assertIn('--cta: var(--seal)', auth_shell)
        self.assertIn('.login-input:focus-visible', auth_shell)
        self.assertIn('var(--focus-ring)', auth_shell)

    def test_shared_focus_rule_covers_keyboard_interactions(self):
        base_css = (self.theme / 'static_src' / 'src' / 'base.css').read_text()
        self.assertIn('[role="button"]', base_css)
        self.assertIn('[tabindex]:not([tabindex="-1"])', base_css)
        self.assertGreaterEqual(base_css.count(':not(:disabled)'), 4)
        self.assertGreaterEqual(base_css.count(':not([aria-disabled="true"])'), 7)
        self.assertIn('):focus-visible', base_css)
        self.assertIn('outline: 3px solid var(--focus-ring)', base_css)

    def test_compatibility_and_command_center_namespaces_remain_bounded(self):
        for namespace in ('.arch-', '.cw-', '.cform-', '.crs-'):
            self.assertTrue(
                any(
                    namespace in path.read_text(errors='ignore')
                    for path in self.theme.rglob('*')
                    if path.is_file() and path.suffix in {'.css', '.html'}
                ),
                namespace,
            )

        cc_files = []
        for path in self.theme.rglob('*'):
            if not path.is_file() or path.suffix not in {'.css', '.html', '.js'}:
                continue
            if 'cc-v3-' in path.read_text(errors='ignore'):
                cc_files.append(str(path.relative_to(self.root)))
        allowed_cc_files = {
            'theme/static/css/command-center.css',
            'theme/templates/dashboard.html',
        }
        self.assertTrue(set(cc_files).issubset(allowed_cc_files), cc_files)

    def test_architecture_document_records_the_phase_boundary(self):
        architecture = (
            self.root / 'docs' / 'design-system' / 'ARCHITECTURE.md'
        ).read_text()
        self.assertIn('clmone-tokens.css', architecture)
        self.assertIn('.dc-ds-*', architecture)
        self.assertIn('premium.css', architecture)
        self.assertIn('Phase 1 — foundation', architecture)
        self.assertIn('production Command Center is the visual and layout reference', architecture)
        self.assertIn('source of truth for visual quality', architecture)
        self.assertIn('layout rules', architecture)
