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
        self.assertTrue((shell.parent / 'global-shell' / 'shell-primitives.css').exists())
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
        adr = (
            self.root
            / 'docs'
            / 'governance'
            / 'decisions'
            / 'adr'
            / '0008-frontend-design-system-phase-1.md'
        ).read_text()
        inventory = (self.root / 'docs' / 'design-system' / 'LEGACY_COMPATIBILITY_INVENTORY.md').read_text()
        phase1_inventory = (
            self.root / 'docs' / 'design-system' / 'LEGACY_COMPATIBILITY_INVENTORY_PHASE1.md'
        ).read_text()

        self.assertIn('clmone-tokens.css', adr)
        self.assertIn('.dc-ds-*', adr)
        self.assertIn('page-local CSS is prohibited by default', adr)
        self.assertIn('Completed', adr)
        self.assertIn('2026-07-19', adr)
        self.assertIn('--ds-color-shell', inventory)
        self.assertIn('.cform-*', inventory)
        self.assertIn('SUPERSEDED', phase1_inventory)
        self.assertIn('--ds-color-shell', phase1_inventory)

    def test_phase_five_a_shell_uses_canonical_hooks_without_dead_aliases(self):
        base = (self.theme / 'templates' / 'base.html').read_text()
        shell = (self.theme / 'static_src' / 'src' / 'global-shell' / 'shell-primitives.css').read_text()
        foundations = (self.theme / 'static_src' / 'src' / 'global-shell' / 'foundations.css').read_text()
        for selector in (
            'dc-ds-shell', 'dc-ds-shell__sidebar', 'dc-ds-shell__main',
            'dc-ds-shell__topbar', 'dc-ds-shell__content',
            'dc-ds-shell__mobile-toggle', 'dc-ds-shell__scrim',
        ):
            self.assertIn(selector, base)
            self.assertIn(f'.{selector}', shell)
        for alias in ('.sidebar-footer-org', '.sidebar-footer-collapse', '.theme-toggle-btn'):
            self.assertNotIn(alias, foundations)

    def test_phase_five_b_auth_shell_aliases_have_no_remaining_consumers(self):
        sources = (
            (self.theme / 'templates' / 'base.html').read_text(),
            (self.theme / 'static_src' / 'src' / 'global-shell' / 'foundations.css').read_text(),
            (self.theme / 'static_src' / 'src' / 'global-shell' / 'legacy-layout.css').read_text(),
            (self.theme / 'static_src' / 'src' / 'design-system' / 'premium.css').read_text(),
            (self.theme / 'static' / 'css' / 'command-center.css').read_text(),
            (self.theme / 'templates' / 'contracts' / 'repository.html').read_text(),
        )
        for alias in (
            'main-layout', 'sidebar-container', 'main-area', 'main-content-pad',
            'sidebar-scrim', 'mobile-nav-toggle',
        ):
            for source in sources:
                with self.subTest(alias=alias):
                    self.assertNotIn(alias, source)

    def test_phase_five_c_workspace_scaffolds_use_canonical_hooks(self):
        components = (self.theme / 'static_src' / 'src' / 'design-system' / 'components.css').read_text()
        premium = (self.theme / 'static_src' / 'src' / 'design-system' / 'premium.css').read_text()
        workspace_templates = (
            'contracts/contract_detail.html',
            'contracts/dpa_contract_workspace.html',
            'contracts/nda_contract_workspace.html',
            'contracts/msa_contract_workspace.html',
        )
        for hook in (
            'dc-ds-workspace__header', 'dc-ds-workspace__metadata-grid',
            'dc-ds-workspace__timeline', 'dc-ds-workspace__layout',
            'dc-ds-workspace__surface', 'dc-ds-workspace__rail',
        ):
            self.assertIn(f'.{hook}', components)
        for template_name in workspace_templates:
            with self.subTest(template=template_name):
                self.assertIn('dc-ds-workspace', (self.theme / 'templates' / template_name).read_text())
        for retired_adapter in ('dpa-ws-header', 'nda-ws-header', 'dpa-ws-grid', 'nda-ws-grid'):
            self.assertNotIn(retired_adapter, premium)

    def test_phase_five_d_workspace_styles_are_shared_not_template_local(self):
        shell = (self.theme / 'static_src' / 'src' / 'global-shell.css').read_text()
        workspace_source = self.theme / 'static_src' / 'src' / 'global-shell' / 'workspaces.css'
        self.assertIn('@import "./global-shell/workspaces.css"', shell)
        self.assertTrue(workspace_source.exists())
        for template_name in (
            'contracts/dpa_contract_workspace.html',
            'contracts/nda_contract_workspace.html',
            'contracts/msa_contract_workspace.html',
        ):
            with self.subTest(template=template_name):
                self.assertNotIn('<style', (self.theme / 'templates' / template_name).read_text())
        self.assertIn('.dc-ds-workspace--workflow', workspace_source.read_text())
        self.assertIn('.dc-ds-workspace--msa', workspace_source.read_text())

    def test_phase_five_e_workspace_route_prefixes_are_retired(self):
        import re

        workspace_source = (
            self.theme / 'static_src' / 'src' / 'global-shell' / 'workspaces.css'
        ).read_text()
        premium = (self.theme / 'static_src' / 'src' / 'design-system' / 'premium.css').read_text()
        templates = (
            'contracts/dpa_contract_workspace.html',
            'contracts/nda_contract_workspace.html',
            'contracts/msa_contract_workspace.html',
        )
        retired = (
            'dpa-ws-', 'nda-ws-', 'msa-ws-',
            'dpa-clause', 'nda-clause', 'msa-clause',
            'dpa-doc', 'nda-doc', 'msa-doc',
            'dpa-risk-', 'nda-risk-', 'msa-risk-',
            'data-dpa-rail-', 'data-msa-open-governance', 'data-msa-tab', 'data-msa-workspace',
        )
        for template_name in templates:
            content = (self.theme / 'templates' / template_name).read_text()
            with self.subTest(template=template_name):
                for token in retired:
                    self.assertNotIn(token, content)
                self.assertIn('dc-ds-workspace__clause', content)
                self.assertIn('dc-ds-button', content)
                self.assertIn('data-clause-link', content)
        for token in (
            '.dpa-ws-', '.nda-ws-', '.msa-ws-',
            '.dpa-clause', '.nda-clause', '.msa-clause',
            '.dpa-doc', '.nda-doc', '.msa-doc',
        ):
            self.assertNotIn(token, workspace_source)
            self.assertNotIn(token, premium)
        self.assertIn('.dc-ds-workspace__clause', workspace_source)
        self.assertIn('.dc-ds-workspace__drawer', workspace_source)
        # Stable JS hooks remain data-* attributes, not route class selectors.
        self.assertTrue(re.search(r'data-workspace-rail-tab|data-workspace-layout|data-clause-link',
                                  (self.theme / 'templates' / 'contracts' / 'dpa_contract_workspace.html').read_text()))

    def test_phase_five_f_builder_and_record_canvas_are_canonical(self):
        shell = (self.theme / 'static_src' / 'src' / 'global-shell.css').read_text()
        workspace_source = (
            self.theme / 'static_src' / 'src' / 'global-shell' / 'workspaces.css'
        ).read_text()
        builder_source = (
            self.theme / 'static_src' / 'src' / 'global-shell' / 'workflow-builder-cockpit.css'
        )
        detail = (self.theme / 'templates' / 'contracts' / 'contract_detail.html').read_text()
        self.assertIn('@import "./global-shell/workflow-builder-cockpit.css"', shell)
        self.assertTrue(builder_source.exists())
        self.assertIn('.cform-doc-canvas', builder_source.read_text())
        self.assertIn('dc-ds-workspace--record', detail)
        self.assertIn('dc-ds-workspace__tabs', detail)
        self.assertIn('dc-ds-workspace__rail--sticky', detail)
        self.assertNotIn('dc-ds-workspace__metadata-grid', detail)
        self.assertNotIn('<style', detail)
        for retired in (
            'contract-command-strip',
            'contract-workspace-grid',
            'class="contract-surface"',
            'contract-surface-kicker',
            'dc-ds-workspace__cta',
            'dc-ds-workspace__badge',
        ):
            self.assertNotIn(retired, detail)
        for token in (
            'contract-command-strip',
            'contract-workspace-grid',
            '.contract-surface',
            '.dc-ds-workspace__cta',
            '.dc-ds-workspace__badge',
        ):
            self.assertNotIn(token, workspace_source)
        for template_name in (
            'contracts/dpa_contract_workspace.html',
            'contracts/nda_contract_workspace.html',
            'contracts/msa_contract_workspace.html',
        ):
            content = (self.theme / 'templates' / template_name).read_text()
            with self.subTest(template=template_name):
                # All three drafting workspaces now expose real primary CTAs.
                self.assertIn('dc-ds-button--primary', content)
                self.assertIn('dc-ds-badge--sm', content)
                self.assertIn('View contract record', content)
                self.assertNotIn('dc-ds-workspace__cta', content)
                self.assertNotIn('dc-ds-workspace__badge', content)

    def test_phase_five_g_dual_class_and_dpa_intake_are_cleaned(self):
        detail = (self.theme / 'templates' / 'contracts' / 'contract_detail.html').read_text()
        workspace_source = (
            self.theme / 'static_src' / 'src' / 'global-shell' / 'workspaces.css'
        ).read_text()
        builder_source = (
            self.theme / 'static_src' / 'src' / 'global-shell' / 'workflow-builder-cockpit.css'
        ).read_text()
        dpa_builder = (
            self.theme / 'templates' / 'contracts' / 'dpa_workflow_builder.html'
        ).read_text()
        review = (
            self.theme / 'templates' / 'contracts' / 'dpa_review_and_generate.html'
        ).read_text()
        for retired in ('btn-cta', 'btn-quiet', 'btn-soft-primary', 'badge-sm', 'badge-yellow', 'badge-red'):
            self.assertNotIn(retired, detail)
        self.assertIn('legacy_badge_tone', detail)
        self.assertIn('dc-ds-badge--attention', detail)
        for dual in ('.btn-cta', '.btn-quiet', '.badge-sm'):
            self.assertNotIn(dual, workspace_source)
        self.assertIn('.dpa-field-error', builder_source)
        self.assertIn('.dpa-review-card', builder_source)
        self.assertIn('.dpa-intake', builder_source)
        self.assertIn('dpa-multiselect', dpa_builder)
        self.assertIn('dpa-step-nav', dpa_builder)
        self.assertIn('<style', dpa_builder)
        self.assertIn('dpa-option-picker', dpa_builder)
        self.assertNotIn('<style', review)
        # Shared field chrome must not remain duplicated in the route-unique style block.
        unique_css = dpa_builder.split('<style', 1)[1].split('</style>', 1)[0]
        self.assertNotIn('.dpa-field-error', unique_css)
        self.assertNotIn('.dpa-form-actions', unique_css)
        self.assertIn('.dpa-multiselect', unique_css)

    def test_phase_five_h_command_center_uses_canonical_controls(self):
        dashboard = (self.theme / 'templates' / 'dashboard.html').read_text()
        cc_css = (self.theme / 'static' / 'css' / 'command-center.css').read_text()
        self.assertIn('class="command-center cc-v3"', dashboard)
        self.assertIn('dc-ds-button dc-ds-button--primary', dashboard)
        self.assertIn('dc-ds-button dc-ds-button--link', dashboard)
        self.assertIn('dc-ds-setup-list', dashboard)
        self.assertIn('dc-ds-surface--feature', dashboard)
        self.assertIn('dc-ds-metric', dashboard)
        for retired in (
            'is-primary',
            'is-secondary',
            'cc-v3-setup-list',
            'cc-v3-empty-hero',
            'cc-v3-actions-empty',
            'btn-cta',
            'badge-sm',
        ):
            self.assertNotIn(retired, dashboard)
        for retired_css in (
            'cc-v3-empty-hero-',
            'cc-v3-actions-empty',
            'cc-v3-hero--empty',
            'cc-v3-setup-copy',
            'cc-v3-setup-list',
            '.is-primary',
            '.is-secondary',
        ):
            self.assertNotIn(retired_css, cc_css)
        self.assertIn('.cc-v3-portfolio-actions .dc-ds-button--primary', cc_css)
        self.assertIn('.cc-v3-portfolio-actions .dc-ds-button--link', cc_css)
        self.assertIn('.dc-ds-setup-action', cc_css)
        # Expressive hero + operational canvas preserved under route-local namespace.
        self.assertIn('cc-v3-portfolio-hero', dashboard)
        self.assertIn('cc-v3-portfolio-score', dashboard)
        self.assertIn('.cc-v3-portfolio-hero', cc_css)

    def test_phase_six_authenticated_templates_have_no_btn_badge_dual_classes(self):
        import re

        templates = self.theme / 'templates'
        exceptions = {
            'landing.html', 'legal_front_door.html', 'base_fullscreen.html',
            '404.html', '403.html', '500.html',
        }
        offenders = []
        pattern = re.compile(
            r'(?<![\w-])(?:btn-cta|btn-quiet|btn-ghost|btn-primary-grad|btn-soft-primary|'
            r'badge-sm|badge-green|badge-blue|badge-yellow|badge-red|badge-purple|badge-gray)(?![\w-])'
        )
        for html_file in templates.rglob('*.html'):
            rel = html_file.relative_to(templates).as_posix()
            if rel in exceptions or rel.startswith('registration/'):
                continue
            text = html_file.read_text(errors='ignore')
            for match in re.finditer(r'''\bclass=(["'])(.*?)\1''', text, flags=re.S):
                if pattern.search(match.group(2)):
                    offenders.append(rel)
                    break
        self.assertEqual(offenders, [], f'Phase 6 dual-class offenders: {offenders}')

    def test_interaction_hover_polish_is_selective_and_motion_aware(self):
        premium = (self.theme / 'static_src' / 'src' / 'design-system' / 'premium.css').read_text()
        shared = (self.theme / 'static_src' / 'src' / 'global-shell' / 'shared-components.css').read_text()
        legacy = (self.theme / 'static_src' / 'src' / 'global-shell' / 'legacy-layout.css').read_text()

        motion_guard = '@media (hover: hover) and (pointer: fine) and (prefers-reduced-motion: no-preference)'
        self.assertIn(motion_guard, premium)
        self.assertIn('.dc-ds-button--primary', premium)
        self.assertIn('.dc-ds-choice', premium)
        self.assertIn('transform: translateY(-1px)', premium)
        self.assertIn('a.list-row:hover', shared)
        self.assertIn('a.settings-card:hover', legacy)
        self.assertIn('.action-link:hover { box-shadow:', legacy)
