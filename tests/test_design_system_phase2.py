import re
from pathlib import Path

from django.conf import settings
from django.template import engines
from django.test import SimpleTestCase

from contracts.templatetags.clmone_format import (
    CANONICAL_BADGE_TONE,
    LEGACY_BADGE_CLASS,
    semantic_badge_tone,
)

CANONICAL_SEMANTIC_NAMES = {
    'success',
    'information',
    'warning',
    'danger',
    'neutral',
    'pending',
    'inactive',
    'not_applicable',
}


class DesignSystemPhaseTwoTests(SimpleTestCase):
    """Badges, semantic status, and empty states (design-system Phase 2)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.root = Path(settings.BASE_DIR)
        cls.theme = cls.root / 'theme'
        cls.base_html = (cls.theme / 'templates' / 'base.html').read_text()
        cls.global_shell_css = '\n'.join(
            source.read_text()
            for source in sorted(
                (cls.theme / 'static_src' / 'src' / 'global-shell').glob('*.css')
            )
        )
        cls.components_css = (
            cls.theme / 'static_src' / 'src' / 'components.css'
        ).read_text()
        cls.ds_components_css = (
            cls.theme / 'static_src' / 'src' / 'design-system' / 'components.css'
        ).read_text()

    # -- semantic vocabulary -------------------------------------------------

    def test_canonical_semantic_vocabulary_is_exactly_eight_names(self):
        self.assertEqual(set(LEGACY_BADGE_CLASS), CANONICAL_SEMANTIC_NAMES)
        self.assertEqual(set(CANONICAL_BADGE_TONE), CANONICAL_SEMANTIC_NAMES)

    def test_every_semantic_name_maps_to_a_defined_badge_tone(self):
        defined_tones = set(
            re.findall(r'\.dc-ds-badge--([a-z]+)', self.ds_components_css)
        )
        for semantic, tone_class in CANONICAL_BADGE_TONE.items():
            tone = tone_class.removeprefix('dc-ds-badge--')
            self.assertIn(
                tone, defined_tones,
                f'{semantic} maps to undefined tone {tone_class!r}',
            )

    def test_every_semantic_name_maps_to_a_defined_legacy_class(self):
        defined_legacy = set(re.findall(r'\.(badge-[a-z]+)\s*\{', self.global_shell_css))
        for semantic, legacy_class in LEGACY_BADGE_CLASS.items():
            self.assertIn(
                legacy_class, defined_legacy,
                f'{semantic} maps to undefined legacy class {legacy_class!r}',
            )

    def test_semantic_badge_tone_filter_resolves_known_and_unknown_input(self):
        self.assertEqual(semantic_badge_tone('success'), 'success')
        self.assertEqual(semantic_badge_tone('not_applicable'), 'neutral')
        # Unknown semantic never renders unstyled — falls back to neutral.
        self.assertEqual(semantic_badge_tone('totally-unknown'), 'neutral')

    # -- canonical token usage (no hardcoded status hex) ---------------------

    def test_legacy_badge_colours_resolve_through_canonical_status_tokens(self):
        for legacy_class in ('badge-green', 'badge-blue', 'badge-yellow', 'badge-red', 'badge-purple', 'badge-gray'):
            match = re.search(r'\.' + legacy_class + r'\s*\{([^}]*)\}', self.global_shell_css)
            self.assertIsNotNone(match, f'{legacy_class} not found in global shell CSS')
            rule_body = match.group(1)
            self.assertIn('var(--status-', rule_body, f'{legacy_class} is not token-backed: {rule_body!r}')
            self.assertNotRegex(rule_body, r'#[0-9A-Fa-f]{3,6}', f'{legacy_class} still hardcodes a hex colour')

    def test_badge_neutral_second_system_is_token_backed(self):
        match = re.search(r'\.badge-neutral\s*\{([^}]*)\}', self.components_css)
        self.assertIsNotNone(match)
        self.assertIn('var(--status-neutral', match.group(1))

    def test_dc_ds_badge_neutral_tone_exists_and_is_token_backed(self):
        match = re.search(r'\.dc-ds-badge--neutral\s*\{([^}]*)\}', self.ds_components_css)
        self.assertIsNotNone(match, 'canonical .dc-ds-badge--neutral tone is missing')
        self.assertIn('var(--status-neutral', match.group(1))

    def test_no_orphaned_selectorless_declaration_block_in_base_html(self):
        # Regression guard for the malformed selector-less declaration block
        # removed from the legacy shell compatibility source.
        self.assertNotIn('background: rgba(196,145,51,0.14);', self.global_shell_css)

    # -- compatibility: legacy classes still present, still used ------------

    def test_legacy_badge_classes_still_defined(self):
        for legacy_class in ('badge-sm', 'badge-green', 'badge-blue', 'badge-yellow', 'badge-red', 'badge-purple', 'badge-gray'):
            self.assertIn(f'.{legacy_class}', self.global_shell_css, f'{legacy_class} was removed from global shell CSS')

    def test_legacy_badge_classes_still_have_repository_consumers(self):
        # Guardrail: do not let a legacy class quietly reach zero usage and
        # then get "cleaned up" without anyone noticing — that decision needs
        # to be explicit, not accidental.
        consumers = 0
        for html_file in self.theme.rglob('*.html'):
            text = html_file.read_text(errors='ignore')
            if re.search(r'\bbadge-(green|blue|yellow|red|purple|gray)\b', text):
                consumers += 1
        self.assertGreater(consumers, 0, 'legacy .badge-* classes have zero remaining consumers')

    def test_empty_state_and_wq_empty_still_defined(self):
        self.assertIn('.empty-state {', self.global_shell_css)
        self.assertIn('.wq-empty {', self.global_shell_css)

    def test_wq_empty_is_token_backed(self):
        match = re.search(r'\.wq-empty\s*\{([^}]*)\}', self.global_shell_css)
        self.assertIsNotNone(match)
        self.assertIn('var(--text-muted)', match.group(1))

    # -- canonical empty-state component -------------------------------------

    def test_dc_ds_empty_component_still_defined(self):
        self.assertIn('.dc-ds-empty {', self.ds_components_css)

    def test_empty_state_partial_renders_title_and_copy(self):
        django_engine = engines['django']
        template = django_engine.from_string(
            '{% include "design_system/empty_state.html" with title="No records found." copy="Try again later." %}'
        )
        rendered = template.render({})
        self.assertIn('dc-ds-empty', rendered)
        self.assertIn('No records found.', rendered)
        self.assertIn('Try again later.', rendered)

    def test_empty_state_partial_supports_reason_how_and_primary_action(self):
        django_engine = engines['django']
        template = django_engine.from_string(
            '{% include "design_system/empty_state.html" with '
            'title="No contracts" reason="Nothing has been uploaded." '
            'how="Uploaded agreements appear here automatically." '
            'action_url="/contracts/documents/new/" action_label="Upload contract" %}'
        )
        rendered = template.render({})
        self.assertIn('Nothing has been uploaded.', rendered)
        self.assertIn('Uploaded agreements appear here automatically.', rendered)
        self.assertIn('href="/contracts/documents/new/"', rendered)
        self.assertIn('Upload contract', rendered)

    def test_second_empty_state_css_system_is_token_consistent_with_base_html(self):
        # theme/static_src/src/components.css's .empty-state is shadowed by
        # base.html's inline copy today (source order), but must not silently
        # diverge if load order is ever refactored.
        for selector in ('.empty-state', '.empty-state-icon', '.empty-state-title', '.empty-state-description'):
            match = re.search(re.escape(selector) + r'\s*\{([^}]*)\}', self.components_css)
            self.assertIsNotNone(match, f'{selector} missing from components.css')
            self.assertNotRegex(match.group(1), r'#[0-9A-Fa-f]{3,6}', f'{selector} hardcodes a hex colour')

    # -- accessible status labels ---------------------------------------------

    def test_status_badge_partial_requires_visible_label_text(self):
        django_engine = engines['django']
        template = django_engine.from_string(
            '{% include "design_system/status_badge.html" with label="Escalated" tone="danger" %}'
        )
        rendered = template.render({})
        # Colour must never be the only signal — the status word itself has
        # to be present in the rendered markup, not just a coloured swatch.
        self.assertIn('Escalated', rendered)
        self.assertIn('dc-ds-badge--danger', rendered)

    def test_cc_v3_namespace_stays_command_center_scoped(self):
        # .cc-v3-* is the Command Center's own namespace (integrated after
        # this phase landed) — it must stay confined to the dashboard route
        # and must not leak into any other page or shared component.
        allowed = {
            'theme/static/css/command-center.css',
            'theme/templates/dashboard.html',
        }
        offenders = []
        for path in self.theme.rglob('*'):
            if not path.is_file() or path.suffix not in {'.css', '.html', '.js'}:
                continue
            if 'cc-v3-' not in path.read_text(errors='ignore'):
                continue
            rel = str(path.relative_to(self.root))
            if rel not in allowed:
                offenders.append(rel)
        self.assertEqual(offenders, [])
