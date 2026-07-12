
import os
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
            status='PENDING',
            created_by=self.user,
        )
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'DocClad')
        self.assertContains(response, 'High-Risk Deviations')
        self.assertContains(response, 'css/command-center.css')

    def test_dashboard_loads_with_feature_flag_disabled(self):
        os.environ['FEATURE_REDESIGN'] = 'false'
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dashboard')

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
        self.assertContains(response, 'js/docclad-ui.js')
        self.assertContains(response, 'id="docclad-command-palette"')
        self.assertContains(response, 'data-command-input')
        self.assertContains(response, 'data-command-trigger')
        self.assertContains(response, 'id="docclad-toast-region"')

    def test_casefile_catalogue_is_authenticated_and_renders_primitives(self):
        url = reverse('contracts:design_system_catalog')
        anonymous = self.client.get(url)
        self.assertEqual(anonymous.status_code, 302)

        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'DocClad Design System')
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

        tokens = (root / 'theme' / 'static' / 'css' / 'docclad-tokens.css').read_text()
        runtime = (root / 'theme' / 'static' / 'js' / 'docclad-ui.js').read_text()
        for token in ('--casefile-forest-600', '--status-progress-fg', '--grid-columns', '--radius-card'):
            self.assertIn(token, tokens)
        self.assertIn('DocClad.toast', runtime)
        self.assertIn('commandPalette', runtime)

    def test_casefile_is_the_light_only_shell_standard(self):
        root = Path(settings.BASE_DIR)
        core_assets = (
            root / 'theme' / 'templates' / 'base.html',
            root / 'theme' / 'templates' / 'base_fullscreen.html',
            root / 'theme' / 'static' / 'css' / 'docclad-tokens.css',
        )
        for asset in core_assets:
            content = asset.read_text()
            self.assertNotIn('[data-theme="dark"]', content, asset)

        for shell in core_assets[:2]:
            self.assertIn('data-design-system="casefile"', shell.read_text())

    def test_casefile_runtime_exposes_motion_chart_table_and_server_feedback(self):
        root = Path(settings.BASE_DIR)
        runtime = (root / 'theme' / 'static' / 'js' / 'docclad-ui.js').read_text()
        for contract in (
            'DocClad.motion',
            'DocClad.chartTheme',
            'DocClad.dataTable',
            'data-server-toast',
            'data-table-core',
            'prefers-reduced-motion: reduce',
        ):
            self.assertIn(contract, runtime)

    def test_casefile_spacing_scale_uses_distinct_four_pixel_steps(self):
        root = Path(settings.BASE_DIR)
        tokens = (root / 'theme' / 'static' / 'css' / 'docclad-tokens.css').read_text()
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
        tokens = (root / 'theme' / 'static' / 'css' / 'docclad-tokens.css').read_text()
        picker = (
            root / 'theme' / 'templates' / 'contracts' / 'contract_template_picker.html'
        ).read_text()

        self.assertIn('@import "./premium.css"', index)
        self.assertIn('--page-padding-x: var(--space-32)', tokens)
        self.assertIn('--page-padding-top: var(--space-32)', tokens)
        self.assertIn('--ds-page-x: var(--page-padding-x)', tokens)
        self.assertIn('.page-wrap', premium)
        self.assertIn('.dc-ds-page', premium)
        self.assertIn('ctp-page', picker)

    def test_core_operational_surfaces_use_central_icons_and_table_contracts(self):
        root = Path(settings.BASE_DIR)
        template_root = root / 'theme' / 'templates'
        for relative_path in (
            'base.html',
            'dashboard.html',
            'contracts/repository.html',
            'contracts/approval_request_list.html',
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

    def test_clause_library_uses_shared_toast_implementation(self):
        root = Path(settings.BASE_DIR)
        clause_library = (
            root / 'theme' / 'templates' / 'contracts' / 'clause_library.html'
        ).read_text()
        self.assertIn('window.DocClad.toast', clause_library)
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
        self.assertContains(response, 'main-layout')
        self.assertContains(response, 'sidebar-container')
        self.assertContains(response, '@media (max-width: 1024px)')

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
