from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class DesignSystemPhaseOneFoundationTests(SimpleTestCase):
    """Guard the non-visual ownership boundary established in Phase 1."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.root = Path(settings.BASE_DIR)
        cls.theme = cls.root / 'theme'

    def test_canonical_ink_compatibility_stops_are_defined(self):
        tokens = (self.theme / 'static' / 'css' / 'clmone-tokens.css').read_text()
        self.assertIn('--ink-200: #D7DCE1', tokens)
        self.assertIn('--ink-800: #252A31', tokens)

    def test_shell_css_is_compiled_and_loaded_after_page_css(self):
        base = (self.theme / 'templates' / 'base.html').read_text()
        shell = self.theme / 'static_src' / 'src' / 'global-shell.css'
        compiled = self.theme / 'static' / 'css' / 'dist' / 'global-shell.css'

        self.assertTrue(shell.exists())
        self.assertTrue(compiled.exists())
        self.assertIn('@import "./global-shell/foundations.css"', shell.read_text())
        self.assertTrue((shell.parent / 'global-shell' / 'foundations.css').exists())
        self.assertTrue((shell.parent / 'global-shell' / 'shared-components.css').exists())
        self.assertTrue((shell.parent / 'global-shell' / 'legacy-layout.css').exists())
        self.assertNotIn('<style', base)
        self.assertLess(base.index('{% block page_css %}'), base.index('css/dist/global-shell.css'))

    def test_tailwind_v4_entry_is_the_only_active_build_path(self):
        package = (self.theme / 'static_src' / 'package.json').read_text()
        entry = (self.theme / 'static_src' / 'src' / 'styles.css').read_text()

        self.assertIn('tailwindcss', entry)
        self.assertNotIn('@config', entry)
        self.assertIn('build:shell', package)
        self.assertFalse((self.theme / 'static_src' / 'tailwind.config.js').exists())
        self.assertFalse((self.theme / 'static_src' / 'src' / 'theme.css').exists())
        self.assertFalse((self.theme / 'package.json').exists())

    def test_phase_one_decision_and_legacy_inventory_exist(self):
        adr = (self.root / 'docs' / 'adr' / '0008-frontend-design-system-phase-1.md').read_text()
        inventory = (self.root / 'docs' / 'design-system' / 'LEGACY_COMPATIBILITY_INVENTORY.md').read_text()

        self.assertIn('clmone-tokens.css', adr)
        self.assertIn('.dc-ds-*', adr)
        self.assertIn('page-local CSS is prohibited by default', adr)
        self.assertIn('--ds-color-shell', inventory)
        self.assertIn('.cform-*', inventory)
