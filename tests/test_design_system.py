
import os
import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.template import Context, Template
from django.test import Client, TestCase
from django.urls import reverse

from contracts.models import Contract, Organization, OrganizationMembership


class DesignSystemTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
        )

    def _enable_clm_dashboard(self, organization):
        organization.workspace_mode = Organization.WorkspaceMode.IN_HOUSE_CLM
        organization.save(update_fields=['workspace_mode'])

    def test_dashboard_loads_with_feature_flag_enabled(self):
        os.environ['FEATURE_REDESIGN'] = 'true'
        # The KPI strip only renders on a populated dashboard; empty
        # workspaces get the onboarding checklist instead.
        organization = Organization.objects.create(name='DS Firm', slug='ds-firm')
        OrganizationMembership.objects.create(
            organization=organization,
            user=self.user,
            role=OrganizationMembership.Role.OWNER,
            is_active=True,
        )
        self._enable_clm_dashboard(organization)
        Contract.objects.create(
            organization=organization,
            title='DS Contract',
            content='Seed so the dashboard renders its normal state.',
            status='ACTIVE',
            created_by=self.user,
        )
        # Legal Pulse shows a meaningful zero-state instead of a bare "0" —
        # a PENDING contract is needed for "Needs Legal Review" itself
        # (not its empty-state copy) to render.
        Contract.objects.create(
            organization=organization,
            title='DS Contract Needing Review',
            content='Seed so the Legal Pulse metric has a nonzero value.',
            status='IN_PROGRESS',
            created_by=self.user,
        )
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'CLM One')
        self.assertContains(response, 'Risk findings')
        self.assertContains(response, 'css/command-center.css')

    def test_dashboard_loads_with_feature_flag_disabled(self):
        os.environ['FEATURE_REDESIGN'] = 'false'
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Command Center')

    def test_button_component_snippet(self):
        template = Template(
            '<button class="btn-primary">Primary Button</button>'
            '<button class="btn-secondary">Secondary Button</button>'
        )
        rendered = template.render(Context({}))
        self.assertIn('btn-primary', rendered)
        self.assertIn('btn-secondary', rendered)

    def test_card_component_snippet(self):
        template = Template(
            '<div class="card"><div class="card-header"></div><div class="card-content"></div></div>'
        )
        rendered = template.render(Context({}))
        self.assertIn('card-header', rendered)
        self.assertIn('card-content', rendered)

    def test_dense_admin_row_adapter_renders_core_slots(self):
        template = Template(
            '{% include "design_system/dense_admin_row.html" with '
            'title="Session owner" metadata="owner@example.com · Admin" '
            'timestamp="Last activity: 2026-07-09" badge_label="Active" badge_tone="success" %}'
        )
        rendered = template.render(Context({}))
        self.assertIn('dc-ds-dense-row', rendered)
        self.assertIn('Session owner', rendered)
        self.assertIn('owner@example.com · Admin', rendered)
        self.assertIn('Last activity: 2026-07-09', rendered)
        self.assertIn('Active', rendered)

    def test_casefile_button_renders_central_icon_and_toast_hooks(self):
        template = Template(
            '{% include "design_system/button.html" with label="Saved" '
            'tone="primary" icon="check" toast_message="Draft saved" toast_tone="success" %}'
        )
        rendered = template.render(Context({}))
        self.assertIn('dc-ds-button--primary', rendered)
        self.assertIn('dc-ds-icon', rendered)
        self.assertIn('data-toast-message="Draft saved"', rendered)
        self.assertIn('data-toast-tone="success"', rendered)

    def test_authenticated_shell_exposes_casefile_interaction_contracts(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'js/clmone-ui.js')
        self.assertContains(response, 'id="clmone-command-palette"')
        self.assertContains(response, 'data-command-input')
        self.assertContains(response, 'id="clmone-toast-region"')

    def test_casefile_catalogue_is_authenticated_and_renders_primitives(self):
        url = reverse('contracts:design_system_catalog')
        anonymous = self.client.get(url)
        self.assertEqual(anonymous.status_code, 302)

        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'CLM One Design System')
        self.assertContains(response, 'Semantic color and type')
        self.assertContains(response, 'dc-ds-table')
        self.assertContains(response, 'data-toast-message')

    def test_casefile_documentation_and_runtime_contract_exist(self):
        root = Path(settings.BASE_DIR)
        required_docs = {
            'README.md',
            'FOUNDATIONS.md',
            'COMPONENTS.md',
            'DOMAIN_PATTERNS.md',
            'INTERACTIONS.md',
            'PAGE_ARCHETYPES.md',
            'CONTENT_STANDARDS.md',
            'ENGINEERING.md',
            'MIGRATION.md',
        }
        docs_dir = root / 'docs' / 'design-system'
        self.assertTrue(required_docs.issubset({path.name for path in docs_dir.iterdir()}))

        tokens = (root / 'theme' / 'static' / 'css' / 'clmone-tokens.css').read_text()
        runtime = (root / 'theme' / 'static' / 'js' / 'clmone-ui.js').read_text()
        for token in ('--casefile-forest-600', '--status-progress-fg', '--grid-columns', '--radius-card'):
            self.assertIn(token, tokens)
        self.assertIn('CLMOne.toast', runtime)
        self.assertIn('commandPalette', runtime)

    def test_casefile_is_the_light_only_shell_standard(self):
        root = Path(settings.BASE_DIR)
        core_assets = (
            root / 'theme' / 'templates' / 'base.html',
            root / 'theme' / 'templates' / 'base_fullscreen.html',
            root / 'theme' / 'static' / 'css' / 'clmone-tokens.css',
        )
        for asset in core_assets:
            content = asset.read_text()
            self.assertNotIn('[data-theme="dark"]', content, asset)

        for shell in core_assets[:2]:
            self.assertIn('data-design-system="casefile"', shell.read_text())

    def test_casefile_runtime_exposes_motion_chart_table_and_server_feedback(self):
        root = Path(settings.BASE_DIR)
        runtime = (root / 'theme' / 'static' / 'js' / 'clmone-ui.js').read_text()
        for contract in (
            'CLMOne.motion',
            'CLMOne.chartTheme',
            'CLMOne.dataTable',
            'data-server-toast',
            'data-table-core',
            'prefers-reduced-motion: reduce',
        ):
            self.assertIn(contract, runtime)

    def test_casefile_spacing_scale_uses_distinct_four_pixel_steps(self):
        root = Path(settings.BASE_DIR)
        tokens = (root / 'theme' / 'static' / 'css' / 'clmone-tokens.css').read_text()
        for token in (
            '--space-12: 12px',
            '--space-16: 16px',
            '--space-20: 20px',
            '--space-24: 24px',
            '--ds-space-3: var(--space-12)',
        ):
            self.assertIn(token, tokens)

    def test_casefile_premium_layer_owns_application_page_spacing(self):
        root = Path(settings.BASE_DIR)
        index = (
            root / 'theme' / 'static_src' / 'src' / 'design-system' / 'index.css'
        ).read_text()
        premium = (
            root / 'theme' / 'static_src' / 'src' / 'design-system' / 'premium.css'
        ).read_text()
        tokens = (root / 'theme' / 'static' / 'css' / 'clmone-tokens.css').read_text()
        picker = (
            root / 'theme' / 'templates' / 'contracts' / 'contract_template_picker.html'
        ).read_text()

        self.assertIn('@import "./premium.css"', index)
        self.assertIn('--page-padding-x: var(--space-24)', tokens)
        self.assertIn('--page-padding-top: var(--space-16)', tokens)
        self.assertIn('--ds-page-x: var(--page-padding-x)', tokens)
        self.assertIn('.page-wrap', premium)
        self.assertIn('.dc-ds-page', premium)
        self.assertIn('ctp-page', picker)

    def test_command_center_rules_are_canonical_across_legacy_and_shared_pages(self):
        root = Path(settings.BASE_DIR)
        tokens = (root / 'theme' / 'static' / 'css' / 'clmone-tokens.css').read_text()
        premium = (
            root / 'theme' / 'static_src' / 'src' / 'design-system' / 'premium.css'
        ).read_text()
        components = (
            root / 'theme' / 'static_src' / 'src' / 'design-system' / 'components.css'
        ).read_text()

        for contract in (
            '--color-surface-page: #F7F9FC',
            '--color-status-success-border',
            '--color-status-warning-border',
            '--color-status-error-border',
            '--radius-subpanel: 10px',
            '--radius-card: 8px',
            '--shadow-card:',
        ):
            self.assertIn(contract, tokens)

        for legacy_family in (
            '.page-wrap',
            '.panel, .card, .card-l1, .summary-card, .kpi-card, .ad-card',
            '.btn, .btn-cta, .btn-soft, .btn-quiet, .btn-primary-grad',
            '.table-container, .table-wrap, .panel-table, .dc-ds-table-wrap',
            '.badge-success, .badge-green, .status-success, .status-clear',
        ):
            self.assertIn(legacy_family, premium)

        self.assertIn('border-radius: var(--radius-subpanel)', components)
        self.assertIn('background: var(--color-surface-table-head)', components)

    def test_global_search_selected_controls_and_debug_ui_have_one_contract(self):
        root = Path(settings.BASE_DIR)
        base = (root / 'theme' / 'templates' / 'base.html').read_text()
        tokens = (root / 'theme' / 'static' / 'css' / 'clmone-tokens.css').read_text()
        premium = (
            root / 'theme' / 'static_src' / 'src' / 'design-system' / 'premium.css'
        ).read_text()
        development = (root / 'config' / 'settings_development.py').read_text()

        self.assertEqual(base.count('placeholder="Search CLM One"'), 2)
        for token in (
            '--color-control-selected-bg',
            '--color-control-selected-border',
            '--color-control-selected-text',
        ):
            self.assertIn(token, tokens)
            self.assertIn(token, premium)
        self.assertIn("DJANGO_DEBUG_TOOLBAR', default=False", development)
        self.assertIn('if DJANGO_DEBUG_TOOLBAR and not DJANGO_E2E:', development)

    def test_primary_contract_empty_states_explain_cause_population_and_action(self):
        template_root = Path(settings.BASE_DIR) / 'theme' / 'templates' / 'contracts'
        for relative_path in (
            'document_list.html',
            'matter_list.html',
            'client_list.html',
            'counterparty_list.html',
            'deadline_list.html',
            'signature_request_list.html',
            'dsar_list.html',
            'risk_log_list.html',
            'workflow_template_list.html',
            'legal_hold_list.html',
            'invoice_list.html',
            'data_inventory_list.html',
            'transfer_record_list.html',
        ):
            template = (template_root / relative_path).read_text()
            with self.subTest(template=relative_path):
                self.assertIn('design_system/empty_state.html', template)
                self.assertIn('reason=', template)
                self.assertIn('how=', template)
                self.assertIn('action_label=', template)

    def test_primary_pages_share_command_center_header_and_scaffold(self):
        root = Path(settings.BASE_DIR)
        template_root = root / 'theme' / 'templates'
        base = (template_root / 'base.html').read_text()
        shell = '\n'.join(
            source.read_text()
            for source in sorted(
                (root / 'theme' / 'static_src' / 'src' / 'global-shell').glob('*.css')
            )
        )
        premium = (
            root / 'theme' / 'static_src' / 'src' / 'design-system' / 'premium.css'
        ).read_text()

        self.assertIn('topbar-page-context', base)
        self.assertIn('block authenticated_page_title', base)
        self.assertIn('dc-ds-header-promoted', base)
        self.assertIn('css/dist/global-shell.css', base)
        self.assertIn('.workspace-main-head', shell)
        self.assertIn('.workspace-title', shell)
        self.assertIn('.topbar-page-context', premium)
        self.assertIn('height: var(--shell-topbar-height)', premium)

        for relative_path in (
            'dashboard.html',
            'contracts/contract_template_picker.html',
            'contracts/repository.html',
            'contracts/dpa_review_pack_list.html',
            'contracts/obligations_workspace.html',
            'settings_hub.html',
        ):
            content = (template_root / relative_path).read_text()
            self.assertIn('block authenticated_page_title', content, relative_path)

        repository = (template_root / 'contracts' / 'repository.html').read_text()
        components = (
            root / 'theme' / 'static_src' / 'src' / 'design-system' / 'components.css'
        ).read_text()
        self.assertNotIn('dc-ds-scaffold--with-rail', repository)
        self.assertIn('grid-template-columns: minmax(0, 1fr) 296px', components)
        self.assertIn('.dc-ds-scaffold__rail { min-width: 0; order: 2; }', components)
        self.assertNotIn('Repository Control Center', repository)

    def test_primary_pages_use_shared_rhythm_summary_and_selected_controls(self):
        root = Path(settings.BASE_DIR)
        template_root = root / 'theme' / 'templates' / 'contracts'
        components = (
            root / 'theme' / 'static_src' / 'src' / 'design-system' / 'components.css'
        ).read_text()

        for selector in (
            '.dc-ds-page-flow',
            '.dc-ds-page-actions',
            '.dc-ds-summary',
            '.dc-ds-choice',
        ):
            self.assertIn(selector, components)

        for relative_path in (
            'contract_template_picker.html',
            'repository.html',
            'dpa_review_pack_list.html',
            'obligations_workspace.html',
        ):
            content = (template_root / relative_path).read_text()
            self.assertIn('dc-ds-page-flow', content, relative_path)

        repository = (template_root / 'repository.html').read_text()
        self.assertIn('repo-filter-drawer', repository)
        self.assertNotIn('dc-ds-summary', repository)

        obligations = (template_root / 'obligations_workspace.html').read_text()
        self.assertNotIn('dc-ds-scaffold--with-rail', obligations)
        self.assertNotIn('dc-ds-summary--vertical', obligations)
        self.assertIn('dc-ds-summary', obligations)
        self.assertIn('obligations-summary', obligations)
        self.assertIn('clm-list-shell', obligations)
        self.assertIn('clm-list-filter-drawer', obligations)
        self.assertNotIn('dc-ds-surface__title', obligations)

        dpa_list = (template_root / 'dpa_review_pack_list.html').read_text()
        self.assertNotIn('dc-ds-scaffold--with-rail', dpa_list)
        self.assertIn('dc-ds-summary', dpa_list)
        self.assertIn('dpa-review-summary', dpa_list)
        self.assertIn('clm-list-shell', dpa_list)
        self.assertIn('clm-list-filter-drawer', dpa_list)
        self.assertNotIn('dc-ds-summary--vertical', dpa_list)
        self.assertNotIn('Active reviews', dpa_list)

    def test_workspace_and_document_views_inherit_shared_layout_rules(self):
        root = Path(settings.BASE_DIR)
        templates = root / 'theme' / 'templates' / 'contracts'
        workspaces = (
            root / 'theme' / 'static_src' / 'src' / 'global-shell' / 'workspaces.css'
        ).read_text()

        # These routes retain specialised workflow content, but their shared
        # structure is governed by canonical workspace source.
        for selector in (
            '.dc-ds-workspace--workflow',
            '.dc-ds-workspace__header',
            '.dc-ds-workspace__timeline',
            '.dc-ds-workspace__surface',
            '.dc-ds-workspace__layout',
            'grid-template-columns:repeat(7, 84px)',
        ):
            self.assertIn(selector, workspaces)

        for relative_path in (
            'document_detail.html',
            'document_compare.html',
            'document_ocr_review.html',
            'reports_dashboard.html',
        ):
            content = (templates / relative_path).read_text()
            with self.subTest(template=relative_path):
                self.assertIn('block authenticated_page_title', content)
                self.assertIn('block authenticated_page_subtitle', content)

    def test_command_center_styles_do_not_override_shared_navigation_shell(self):
        root = Path(settings.BASE_DIR)
        command_center = (
            root / 'theme' / 'static' / 'css' / 'command-center.css'
        ).read_text()
        shell = '\n'.join(
            source.read_text()
            for source in sorted(
                (root / 'theme' / 'static_src' / 'src' / 'global-shell').glob('*.css')
            )
        )

        for route_scoped_shell_selector in (
            'body:has(.cc-v3) .sidebar-container',
            'body:has(.cc-v3) .sidebar-brand',
            'body:has(.cc-v3) .sidebar-padding',
            'body:has(.cc-v3) .sidebar-footer',
            'body:has(.cc-v3) .sidebar-profile',
            'body:has(.cc-v3) .nav-link',
            'body:has(.cc-v3) .nav-group',
            'body:has(.cc-v3) .nav-sub-link',
        ):
            self.assertNotIn(route_scoped_shell_selector, command_center)

        self.assertIn('navigation is product chrome, never page chrome', shell)
        self.assertIn('width: 225px', shell)
        self.assertIn('min-height: 54px', shell)

    def test_core_operational_surfaces_use_central_icons_and_table_contracts(self):
        root = Path(settings.BASE_DIR)
        template_root = root / 'theme' / 'templates'
        for relative_path in (
            'base.html',
            'dashboard.html',
            'contracts/repository.html',
        ):
            content = (template_root / relative_path).read_text()
            self.assertNotIn('<svg', content, relative_path)

        repository = (template_root / 'contracts' / 'repository.html').read_text()
        self.assertIn('data-table-core="server"', repository)
        for name in (
            '_work_queue_table.html',
            '_approval_queue_table.html',
            '_obligations_matrix_table.html',
            '_task_queue_table.html',
        ):
            content = (template_root / 'components' / name).read_text()
            self.assertIn('dc-ds-table', content)
            self.assertIn('data-table-core="server"', content)

    def test_authenticated_tables_share_compact_interaction_contract(self):
        root = Path(settings.BASE_DIR)
        components = (
            root / 'theme' / 'static_src' / 'src' / 'design-system' / 'components.css'
        ).read_text()
        premium = (
            root / 'theme' / 'static_src' / 'src' / 'design-system' / 'premium.css'
        ).read_text()
        legacy = (
            root / 'theme' / 'static_src' / 'src' / 'global-shell' / 'legacy-layout.css'
        ).read_text()
        repository_runtime = (
            root / 'theme' / 'static' / 'js' / 'clmone-repository.js'
        ).read_text()
        my_work = (
            root / 'theme' / 'templates' / 'contracts' / 'my_work.html'
        ).read_text()
        approval_queue = (
            root / 'theme' / 'templates' / 'components' / '_approval_queue_table.html'
        ).read_text()
        task_queue = (
            root / 'theme' / 'templates' / 'components' / '_task_queue_table.html'
        ).read_text()

        self.assertGreaterEqual(
            components.count('padding: var(--space-8) var(--space-12)'),
            2,
        )
        self.assertIn('table > tbody > tr:hover > td', premium)
        self.assertIn('tr:is([data-href], .cursor-pointer):focus-visible', premium)
        self.assertIn('.wq-table td', legacy)
        self.assertIn('padding: 8px 12px', legacy)
        self.assertIn('data-href="/contracts/${contract.id}/"', repository_runtime)
        self.assertIn("e.key === 'Enter' || e.key === ' '", repository_runtime)
        self.assertIn('renderStatusIndicator(contract)', repository_runtime)
        self.assertIn('repo-status-badge', repository_runtime)
        self.assertIn('vertical-align: middle; padding: 8px 12px', my_work)
        self.assertNotIn('#my-work-table td { vertical-align: top', my_work)
        self.assertIn('class="my-work-row-actions"', my_work)
        self.assertNotIn('show_detail=1', my_work)
        self.assertIn('<div class="wq-approval-actions"', approval_queue)
        self.assertIn('<div class="wq-approval-actions">', task_queue)

    def test_operational_table_hierarchy_and_selection_exceptions(self):
        root = Path(settings.BASE_DIR)
        templates = root / 'theme' / 'templates'

        def assert_header_order(relative_path, ordered_tokens):
            content = (templates / relative_path).read_text()
            header_match = re.search(r'<thead[^>]*>(.*?)</thead>', content, re.DOTALL)
            self.assertIsNotNone(header_match, relative_path)
            header = header_match.group(1)
            positions = [header.index(token) for token in ordered_tokens]
            self.assertEqual(positions, sorted(positions), relative_path)

        # The primary record stays first. Context precedes state, ownership,
        # timing, activity/value, and row actions when those columns exist.
        assert_header_order(
            'components/_approval_queue_table.html',
            ('data-col="title"', 'data-col="stage"', 'data-col="status"',
             'data-col="assignee"', 'data-col="due"', 'data-col="activity"',
             'data-col="actions"'),
        )
        assert_header_order(
            'components/_obligations_matrix_table.html',
            ('data-col="obligation"', 'data-col="contract"', 'data-col="status"',
             'data-col="owner"', 'data-col="due"', 'data-col="actions"'),
        )
        assert_header_order(
            'contracts/repository.html',
            ('data-col="select"', 'data-col="title"', 'data-col="type"',
             'data-col="stage"', 'data-col="status"', 'data-col="owner"', 'data-col="key_date"',
             'data-col="activity"', 'data-col="value"', 'data-col="actions"'),
        )
        assert_header_order(
            'contracts/workflow_dashboard.html',
            ('data-col="workflow"', 'data-col="type"', 'data-col="business_unit"',
             'data-col="stage"', 'data-col="owner"', 'data-col="key_date"',
             'data-col="progress"', 'data-col="value"', 'data-col="actions"'),
        )
        assert_header_order(
            'contracts/legal_intelligence_hub.html',
            ('data-col="severity"', 'data-col="signal"', 'data-col="source"',
             'data-col="status"', 'data-col="owner"', 'data-col="due"',
             'data-col="actions"'),
        )

        my_work = (templates / 'contracts' / 'my_work.html').read_text()
        my_work_header = re.search(r'<thead[^>]*>(.*?)</thead>', my_work, re.DOTALL).group(1)
        self.assertIn('data-col="assigned">Assigned on</th>', my_work_header)
        self.assertLess(my_work_header.index('data-col="priority"'), my_work_header.index('data-col="title"'))
        self.assertLess(my_work_header.index('data-col="type"'), my_work_header.index('data-col="status"'))
        self.assertLess(my_work_header.index('data-col="status"'), my_work_header.index('data-col="due"'))

        repository = (templates / 'contracts' / 'repository.html').read_text()
        repository_table = re.search(r'<table id="contracts-table".*?</table>', repository, re.DOTALL).group(0)
        self.assertIn('id="select-all"', repository_table)
        self.assertIn('dc-ds-table-selection', repository)

        # No other normalized operational table advertises unsupported bulk selection.
        for relative_path in (
            'contracts/my_work.html',
            'components/_approval_queue_table.html',
            'components/_task_queue_table.html',
            'components/_obligations_matrix_table.html',
            'contracts/dpa_review_pack_list.html',
            'contracts/legal_intelligence_hub.html',
        ):
            content = (templates / relative_path).read_text()
            with self.subTest(table=relative_path):
                self.assertNotIn('data-col="select"', content)
                self.assertNotIn('dc-ds-table-selection', content)

        repository_runtime = (root / 'theme' / 'static' / 'js' / 'clmone-repository.js').read_text()
        self.assertIn('/contracts/api/contracts/bulk-update/', repository_runtime)
        self.assertIn('repo-bulk-export', repository_runtime)
        self.assertIn('renderRowActions(contract)', repository_runtime)
        self.assertIn('data-approval-action="approve"', (templates / 'components' / '_approval_queue_table.html').read_text())
        self.assertIn('data-task-action="complete"', (templates / 'components' / '_task_queue_table.html').read_text())

    def test_table_hierarchy_documents_exceptions_and_legacy_follow_up(self):
        root = Path(settings.BASE_DIR)
        documentation = (root / 'docs' / 'design-system' / 'COMPONENTS.md').read_text()
        self.assertIn('Record → context/type → stage/status → owner → due/key date', documentation)
        for exception in ('**My Work**', '**Legal Intelligence**', '**Contracts Repository**'):
            self.assertIn(exception, documentation)
        for legacy_template in (
            'audit_log_list.html',
            'contract_list.html',
            'privacy_dashboard.html',
            'workflow_template_detail.html',
        ):
            self.assertIn(legacy_template, documentation)

    def test_clause_library_uses_shared_toast_implementation(self):
        root = Path(settings.BASE_DIR)
        clause_library = (
            root / 'theme' / 'templates' / 'contracts' / 'clause_library.html'
        ).read_text()
        self.assertIn('window.CLMOne.toast', clause_library)
        self.assertNotIn('.toast-base', clause_library)

    def test_public_pages_expose_build_metadata(self):
        landing = self.client.get(reverse('index'))
        login_page = self.client.get(reverse('login'))

        self.assertEqual(landing.status_code, 200)
        self.assertEqual(login_page.status_code, 200)
        self.assertContains(landing, 'name="build-sha"')
        self.assertContains(landing, 'name="build-label"')
        self.assertContains(login_page, 'name="build-sha"')
        self.assertContains(login_page, 'name="build-label"')

    def test_stat_component_snippet(self):
        template = Template(
            '<div class="stat"><div class="stat-label">Total Contracts</div>'
            '<div class="stat-value">142</div></div>'
        )
        rendered = template.render(Context({}))
        self.assertIn('stat-label', rendered)
        self.assertIn('stat-value', rendered)

    def test_responsive_shell_markers(self):
        os.environ['FEATURE_REDESIGN'] = 'true'
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'dc-ds-shell')
        self.assertContains(response, 'dc-ds-shell__sidebar')
        self.assertContains(response, 'css/dist/global-shell.css')
        shell = '\n'.join(
            source.read_text()
            for source in sorted(
                (Path(settings.BASE_DIR) / 'theme' / 'static_src' / 'src' / 'global-shell').glob('*.css')
            )
        )
        self.assertIn('@media (max-width: 1024px)', shell)

    def test_search_and_notifications_links_exist(self):
        os.environ['FEATURE_REDESIGN'] = 'true'
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'title="Search"')
        self.assertContains(response, '/contracts/search/')
        self.assertContains(response, 'title="Notifications"')

    def tearDown(self):
        if 'FEATURE_REDESIGN' in os.environ:
            del os.environ['FEATURE_REDESIGN']
