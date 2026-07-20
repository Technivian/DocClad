from pathlib import Path

from django.conf import settings
from django.template import Context, Template
from django.test import SimpleTestCase

from contracts.models import Contract, Document
from contracts.templatetags.clmone_format import (
    contract_status_badge_tone,
    document_status_badge_tone,
    legacy_badge_tone,
    lifecycle_stage_badge_tone,
)


class DesignSystemPhaseTwoATests(SimpleTestCase):
    """Guard the constrained Phase 2A shared-component contract."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.root = Path(settings.BASE_DIR)
        cls.components = (
            cls.root / 'theme' / 'static_src' / 'src' / 'design-system' / 'components.css'
        ).read_text()
        cls.tokens = (cls.root / 'theme' / 'static' / 'css' / 'clmone-tokens.css').read_text()

    def test_button_api_exposes_required_interaction_states(self):
        for selector in (
            '.dc-ds-button:focus-visible',
            '.dc-ds-button:active',
            '[aria-pressed="true"]',
            '.dc-ds-button:disabled',
            '[aria-busy="true"]',
            '.dc-ds-button__loader',
        ):
            self.assertIn(selector, self.components)

    def test_control_api_covers_focus_disabled_and_validation_error(self):
        for selector in (
            '.dc-ds-control',
            '.dc-ds-control:focus-visible',
            '.dc-ds-control:disabled',
            '.dc-ds-control[aria-invalid="true"]',
            '.dc-ds-form-field--error',
        ):
            self.assertIn(selector, self.components)

    def test_canonical_badge_semantics_cover_the_six_supported_tones(self):
        for tone in ('success', 'progress', 'attention', 'danger', 'special', 'neutral'):
            with self.subTest(tone=tone):
                self.assertIn(f'.dc-ds-badge--{tone}', self.components)

    def test_canonical_badge_tones_use_their_accessible_token_pairs(self):
        pairs = {
            'success': ('--status-positive-bg', '--status-positive-fg'),
            'progress': ('--status-progress-bg', '--status-progress-fg'),
            'attention': ('--status-pending-bg', '--status-pending-fg'),
            'danger': ('--status-danger-bg', '--status-danger-fg'),
            'special': ('--status-special-bg', '--status-special-fg'),
            'neutral': ('--status-neutral-bg', '--status-neutral-fg'),
        }
        for tone, pair in pairs.items():
            with self.subTest(tone=tone):
                for token in pair:
                    self.assertIn(token, self.components)
                    self.assertIn(token, self.tokens)

    def test_legacy_badge_adapter_has_a_closed_semantic_mapping(self):
        expected = {
            'badge-green': 'success',
            'badge-blue': 'progress',
            'badge-yellow': 'attention',
            'badge-red': 'danger',
            'badge-purple': 'special',
            'badge-gray': 'neutral',
            'unknown': 'neutral',
        }
        for legacy, canonical in expected.items():
                with self.subTest(legacy=legacy):
                    self.assertEqual(legacy_badge_tone(legacy), canonical)

    def test_contract_status_adapter_covers_every_model_status_and_fails_safe(self):
        expected = {
            'IN_PROGRESS': 'progress',
            'ACTIVE': 'success',
            'EXPIRED': 'danger',
            'TERMINATED': 'danger',
            'CANCELLED': 'neutral',
            'ARCHIVED': 'neutral',
        }
        self.assertEqual({value for value, _ in Contract.Status.choices}, set(expected))
        for status, tone in expected.items():
            with self.subTest(status=status):
                self.assertEqual(contract_status_badge_tone(status), tone)
        self.assertEqual(contract_status_badge_tone(None), 'neutral')
        self.assertEqual(contract_status_badge_tone('RETIRED_STATUS'), 'neutral')
        # Legacy aliases may still map in templatetags for stale rows.
        self.assertEqual(contract_status_badge_tone('DRAFT'), 'neutral')
        self.assertEqual(contract_status_badge_tone('PENDING'), 'attention')

    def test_document_status_adapter_covers_every_model_status_and_fails_safe(self):
        expected = {
            'DRAFT': 'neutral',
            'FINAL': 'success',
            'EXECUTED': 'success',
            'SUPERSEDED': 'neutral',
        }
        self.assertEqual({value for value, _ in Document.Status.choices}, set(expected))
        for status, tone in expected.items():
            with self.subTest(status=status):
                self.assertEqual(document_status_badge_tone(status), tone)
        self.assertEqual(document_status_badge_tone(None), 'neutral')
        self.assertEqual(document_status_badge_tone('RETIRED_STATUS'), 'neutral')
        self.assertEqual(document_status_badge_tone('REVIEW'), 'attention')
        self.assertEqual(document_status_badge_tone('APPROVED'), 'progress')
        self.assertEqual(document_status_badge_tone('ARCHIVED'), 'neutral')

    def test_lifecycle_stage_adapter_covers_every_stage_and_fails_safe(self):
        expected = {
            'INTAKE': 'neutral',
            'DRAFTING': 'neutral',
            'INTERNAL_REVIEW': 'progress',
            'NEGOTIATION': 'progress',
            'APPROVAL': 'attention',
            'SIGNATURE': 'progress',
            'EXECUTED': 'success',
            'OBLIGATION_TRACKING': 'success',
            'RENEWAL': 'attention',
        }
        choices = Contract._meta.get_field('lifecycle_stage').choices
        self.assertEqual({value for value, _ in choices}, set(expected))
        for stage, tone in expected.items():
            with self.subTest(stage=stage):
                self.assertEqual(lifecycle_stage_badge_tone(stage), tone)
        self.assertEqual(lifecycle_stage_badge_tone(None), 'neutral')
        self.assertEqual(lifecycle_stage_badge_tone('RETIRED_STAGE'), 'neutral')

    def test_button_partial_renders_loading_and_disabled_accessibly(self):
        rendered = Template(
            '{% include "design_system/button.html" with label="Save" loading=True %}'
        ).render(Context())
        self.assertIn('disabled', rendered)
        self.assertIn('aria-busy="true"', rendered)
        self.assertIn('dc-ds-button__loader', rendered)

    def test_badge_partial_keeps_long_status_text_in_canonical_markup(self):
        rendered = Template(
            '{% include "design_system/status_badge.html" with label="Counterparty review awaiting a named approver" tone="attention" %}'
        ).render(Context())
        self.assertIn('dc-ds-badge--attention', rendered)
        self.assertIn('Counterparty review awaiting a named approver', rendered)

    def test_representative_templates_use_the_canonical_api(self):
        templates = self.root / 'theme' / 'templates' / 'contracts'
        expectations = {
            'repository.html': ('dc-ds-control', 'dc-ds-button--quiet'),
            'contract_form.html': ('dc-ds-badge--sm', 'dc-ds-button--primary'),
            'contract_detail.html': ('dc-ds-workspace--record', 'dc-ds-control--textarea'),
        }
        for template_name, required in expectations.items():
            content = (templates / template_name).read_text()
            for value in required:
                with self.subTest(template=template_name, value=value):
                    self.assertIn(value, content)

    def test_phase_two_b_one_standard_page_families_adopt_buttons_and_badges(self):
        templates = self.root / 'theme' / 'templates' / 'contracts'
        expectations = {
            'client_list.html': ('dc-ds-button--primary', 'dc-ds-badge--sm'),
            'client_detail.html': ('dc-ds-button--primary', 'dc-ds-badge--sm'),
            'ai_data_controls.html': ('dc-ds-button--danger', 'dc-ds-button--primary'),
            'contract_detail.html': ('dc-ds-button--primary', 'dc-ds-badge--sm'),
        }
        for template_name, required in expectations.items():
            content = (templates / template_name).read_text()
            for value in required:
                with self.subTest(template=template_name, value=value):
                    self.assertIn(value, content)

    def test_contract_and_document_status_badges_use_the_shared_canonical_adapter(self):
        templates = self.root / 'theme' / 'templates' / 'contracts'
        expectations = {
            'contract_detail.html': 'contract.status|contract_status_badge_tone',
            'contract_form.html': 'form.instance.status|contract_status_badge_tone',
            'matter_detail.html': (
                'c.status|contract_status_badge_tone',
                'doc.status|document_status_badge_tone',
            ),
            'document_list.html': 'doc.status|document_status_badge_tone',
        }
        for template_name, required in expectations.items():
            content = (templates / template_name).read_text()
            for value in (required,) if isinstance(required, str) else required:
                with self.subTest(template=template_name, value=value):
                    self.assertIn(value, content)

    def test_repository_stage_and_shared_form_widgets_use_canonical_api(self):
        repository_js = (self.root / 'theme' / 'static' / 'js' / 'clmone-repository.js').read_text()
        forms = (self.root / 'contracts' / 'forms.py').read_text()
        self.assertIn('contract.stage_badge_tone', repository_js)
        self.assertNotIn('contract.status_badge_class', repository_js)
        self.assertIn("FORM_CONTROL = 'dc-ds-control form-control'", forms)
        self.assertIn("FORM_CHECK = 'dc-ds-check form-check-input'", forms)

    def test_phase_two_b_five_record_and_admin_form_families_use_shared_apis(self):
        templates = self.root / 'theme' / 'templates' / 'contracts'
        partial = (self.root / 'theme' / 'templates' / 'design_system' / 'form_field.html').read_text()
        self.assertIn('preserve_help', partial)
        for template_name in (
            'clause_category_form.html', 'clause_template_form.html',
            'counterparty_form.html', 'data_inventory_form.html', 'dsar_form.html',
            'legal_hold_form.html', 'retention_policy_form.html',
            'signature_request_form.html', 'subprocessor_form.html',
            'transfer_record_form.html', 'approval_request_form.html',
        ):
            with self.subTest(template=template_name):
                content = (templates / template_name).read_text()
                self.assertIn('dc-ds-surface', content)
                self.assertIn('design_system/form_field.html', content)
        for template_name in ('client_form.html', 'matter_form.html', 'deadline_form.html', 'document_form.html'):
            with self.subTest(template=template_name):
                content = (templates / template_name).read_text()
                self.assertIn('dc-ds-surface', content)
                self.assertIn('dc-ds-form-field__control', content)

    def test_phase_three_a_list_families_use_the_canonical_table_api(self):
        templates = self.root / 'theme' / 'templates' / 'contracts'
        components = self.components
        for selector in (
            '.dc-ds-table-toolbar', '.dc-ds-table-selection',
            '.dc-ds-table-pagination', '.dc-ds-table-state',
        ):
            self.assertIn(selector, components)
        expectations = {
            'repository.html': ('dc-ds-filterbar', 'dc-ds-table-selection', 'dc-ds-table-pagination'),
            'document_list.html': ('design_system/filter_search_bar.html', 'dc-ds-table-wrap', 'dc-ds-table'),
            'clause_category_list.html': ('dc-ds-table-wrap', 'dc-ds-table', 'design_system/empty_state.html'),
            'clause_template_list.html': ('dc-ds-table-wrap', 'dc-ds-table', 'design_system/empty_state.html'),
            'approval_request_list.html': ('dc-ds-table-wrap',),
            'approval_rule_list_table.html': ('dc-ds-table-wrap', 'dc-ds-table'),
        }
        for template_name, required in expectations.items():
            content = (templates / template_name).read_text()
            for value in required:
                with self.subTest(template=template_name, value=value):
                    self.assertIn(value, content)
        repository_js = (self.root / 'theme' / 'static' / 'js' / 'clmone-repository.js').read_text()
        self.assertIn('dc-ds-table-state', repository_js)
        self.assertIn('aria-selected', repository_js)
        self.assertIn('aria-label="Previous page"', repository_js)

    def test_phase_three_b_standard_lists_use_the_shell_header_and_scaffold(self):
        templates = self.root / 'theme' / 'templates' / 'contracts'
        for selector in (
            '.dc-ds-list-page', '.dc-ds-list-header', '.dc-ds-list-tabs',
            '.dc-ds-list-toolbar', '.dc-ds-list-meta',
        ):
            self.assertIn(selector, self.components)
        page_scaffold = (self.root / 'theme' / 'templates' / 'design_system' / 'page_scaffold.html').read_text()
        page_hero = (self.root / 'theme' / 'templates' / 'design_system' / 'page_hero.html').read_text()
        self.assertIn('{% if flow %} dc-ds-page-flow{% endif %}', page_scaffold)
        self.assertIn('{% if subtitle %}', page_hero)
        expectations = {
            'repository.html': ('authenticated_page_title', 'dc-ds-list-page', 'dc-ds-list-toolbar', '_workspace_tabs.html'),
            'document_list.html': ('authenticated_page_title', 'dc-ds-list-page', 'dc-ds-list-header', 'dc-ds-actions'),
            'clause_category_list.html': ('authenticated_page_title', 'dc-ds-list-page', 'dc-ds-list-header', 'dc-ds-actions'),
            'clause_template_list.html': ('authenticated_page_title', 'dc-ds-list-page', 'dc-ds-list-header', 'dc-ds-actions'),
            'approval_request_list.html': ('authenticated_page_title', 'dc-ds-list-page', 'dc-ds-list-toolbar', 'dc-ds-workspace-tabs', '_workflow_operations_tabs.html'),
            # Intentional Workflow Ops unification: approval rules use the shared
            # list-page toolbar + workflow ops tabs include (not page_scaffold).
            'approval_rule_list.html': ('authenticated_page_title', 'dc-ds-list-page', 'dc-ds-list-toolbar', '_workflow_designer_tabs.html'),
        }
        for template_name, required in expectations.items():
            content = (templates / template_name).read_text()
            for value in required:
                with self.subTest(template=template_name, value=value):
                    self.assertIn(value, content)
        legacy_runtime = ('page-header', 'arch-header', 'page-title', 'arch-title', 'page-wrap')
        for template_name in ('document_list.html', 'clause_category_list.html', 'clause_template_list.html', 'approval_request_list.html'):
            content = (templates / template_name).read_text()
            for value in legacy_runtime:
                with self.subTest(template=template_name, value=value):
                    self.assertNotIn(value, content)

    def test_phase_four_a_standard_record_pages_use_canonical_scaffolds(self):
        templates = self.root / 'theme' / 'templates' / 'contracts'
        for selector in (
            '.dc-ds-record-page', '.dc-ds-record-content',
            '.dc-ds-record-sections', '.dc-ds-record-layout--with-rail',
            '.dc-ds-record-notice', '.dc-ds-form-actions',
        ):
            self.assertIn(selector, self.components)
        expectations = {
            'client_form.html': ('authenticated_page_title', 'dc-ds-record-page', 'dc-ds-record-content--narrow'),
            'client_detail.html': ('authenticated_page_title', 'authenticated_page_subtitle', 'dc-ds-record-sections'),
            'clause_category_form.html': ('authenticated_page_back', 'dc-ds-record-page', 'dc-ds-record-content--centered'),
            'clause_template_form.html': ('authenticated_page_back', 'dc-ds-record-page', 'dc-ds-record-content--centered'),
            'approval_request_form.html': ('authenticated_page_back', 'dc-ds-record-layout--with-rail', 'dc-ds-record-notice', 'dc-ds-form-actions'),
        }
        for template_name, required in expectations.items():
            content = (templates / template_name).read_text()
            for value in required:
                with self.subTest(template=template_name, value=value):
                    self.assertIn(value, content)
        legacy_runtime = ('page-wrap', 'page-header', 'page-title', 'arch-header', 'arch-title')
        for template_name in expectations:
            content = (templates / template_name).read_text()
            for value in legacy_runtime:
                with self.subTest(template=template_name, value=value):
                    self.assertNotIn(value, content)
        premium = (self.root / 'theme' / 'static_src' / 'src' / 'design-system' / 'premium.css').read_text()
        self.assertNotIn('approval-request-actions', premium)

    def test_phase_four_b_counterparty_and_governance_records_use_shared_scaffolds(self):
        templates = self.root / 'theme' / 'templates' / 'contracts'
        for selector in (
            '.dc-ds-record-metadata', '.dc-ds-record-metadata__row',
            '.dc-ds-record-checklist-item', '.dc-ds-record-checklist-add',
        ):
            self.assertIn(selector, self.components)
        expectations = {
            'counterparty_detail.html': ('authenticated_page_back', 'dc-ds-record-metadata', 'dc-ds-page-hero'),
            'counterparty_form.html': ('authenticated_page_back', 'dc-ds-record-form', 'dc-ds-form-actions'),
            'compliance_checklist_detail.html': ('authenticated_page_back', 'dc-ds-record-checklist-item', 'dc-ds-record-sections'),
            'compliance_checklist_form.html': ('authenticated_page_subtitle', 'dc-ds-record-form', 'dc-ds-form-actions'),
            'data_inventory_detail.html': ('authenticated_page_back', 'dc-ds-record-metadata', 'dc-ds-page-hero'),
            'data_inventory_form.html': ('authenticated_page_back', 'dc-ds-record-form', 'dc-ds-form-actions'),
            'legal_hold_detail.html': ('authenticated_page_back', 'dc-ds-record-metadata', 'dc-ds-page-hero'),
            'legal_hold_form.html': ('authenticated_page_back', 'dc-ds-record-form', 'dc-ds-form-actions'),
            'subprocessor_detail.html': ('authenticated_page_back', 'dc-ds-record-metadata', 'dc-ds-page-hero'),
            'subprocessor_form.html': ('authenticated_page_back', 'dc-ds-record-form', 'dc-ds-form-actions'),
            'transfer_record_form.html': ('authenticated_page_back', 'dc-ds-record-form', 'dc-ds-form-actions'),
            'retention_policy_form.html': ('authenticated_page_back', 'dc-ds-record-form', 'dc-ds-form-actions'),
            'risk_log_form.html': ('authenticated_page_back', 'dc-ds-record-form', 'dc-ds-form-actions'),
            'ethical_wall_form.html': ('authenticated_page_back', 'dc-ds-record-form', 'dc-ds-form-actions'),
        }
        for template_name, required in expectations.items():
            content = (templates / template_name).read_text()
            for value in required:
                with self.subTest(template=template_name, value=value):
                    self.assertIn(value, content)
            for legacy in ('page-wrap', 'page-header', 'page-title', 'page-subtitle'):
                with self.subTest(template=template_name, legacy=legacy):
                    self.assertNotIn(legacy, content)
        for template_name in ('data_inventory_detail.html', 'legal_hold_detail.html', 'compliance_checklist_detail.html'):
            with self.subTest(template=template_name):
                self.assertNotIn('<style', (templates / template_name).read_text())
