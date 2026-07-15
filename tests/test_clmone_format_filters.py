"""Sub-block C: shared formatting helpers (contracts/templatetags/clmone_format.py)."""
from django.test import SimpleTestCase

from contracts.templatetags.clmone_format import (
    event_label,
    humanduration,
    iso_datetime,
    money,
    object_type_label,
    sort_label,
)


class MoneyFilterTests(SimpleTestCase):
    def test_formats_integer_with_thousands_separator(self):
        self.assertEqual(money(125000), '$125,000.00')

    def test_formats_string_decimal(self):
        self.assertEqual(money('125000.5'), '$125,000.50')

    def test_respects_currency_code(self):
        self.assertEqual(money(50, 'EUR'), '€50.00')
        self.assertEqual(money(50, 'GBP'), '£50.00')

    def test_unknown_currency_falls_back_to_code_prefix(self):
        self.assertEqual(money(50, 'JPY'), 'JPY 50.00')

    def test_empty_value_renders_em_dash(self):
        self.assertEqual(money(None), '—')
        self.assertEqual(money(''), '—')

    def test_unparsable_value_passes_through(self):
        self.assertEqual(money('not-a-number'), 'not-a-number')


class IsoDatetimeFilterTests(SimpleTestCase):
    def test_parses_iso_string_with_microseconds_and_offset(self):
        result = iso_datetime('2026-06-01T09:15:38.135815+00:00')
        self.assertNotIn('T', result)
        self.assertNotIn('+00:00', result)
        self.assertIn('2026', result)

    def test_parses_bare_date_string(self):
        result = iso_datetime('2026-06-11', fmt='M d, Y')
        self.assertEqual(result, 'Jun 11, 2026')

    def test_empty_value_renders_empty_string(self):
        self.assertEqual(iso_datetime(''), '')
        self.assertEqual(iso_datetime(None), '')

    def test_unparsable_string_passes_through(self):
        self.assertEqual(iso_datetime('not-a-date'), 'not-a-date')


class ObjectTypeLabelFilterTests(SimpleTestCase):
    def test_known_model_names_use_curated_labels(self):
        self.assertEqual(object_type_label('OrganizationMembership'), 'team membership')
        self.assertEqual(object_type_label('ContractAI'), 'AI review')
        self.assertEqual(object_type_label('DSARRequest'), 'data subject request')

    def test_unmapped_pascal_case_falls_back_to_word_split(self):
        self.assertEqual(object_type_label('SomeFutureModel'), 'some future model')

    def test_empty_value(self):
        self.assertEqual(object_type_label(''), '')
        self.assertEqual(object_type_label(None), '')


class EventLabelFilterTests(SimpleTestCase):
    def test_snake_case_event(self):
        self.assertEqual(event_label('contract_ai_assistant_invoked'), 'Contract AI Assistant Invoked')

    def test_dot_notation_event(self):
        self.assertEqual(event_label('approval.delegated'), 'Approval Delegated')

    def test_acronyms_are_uppercased(self):
        self.assertEqual(event_label('mfa_recovery_codes_generated'), 'MFA Recovery Codes Generated')
        self.assertEqual(event_label('scim_user_provisioned'), 'SCIM User Provisioned')

    def test_empty_value(self):
        self.assertEqual(event_label(''), '')
        self.assertEqual(event_label(None), '')


class SortLabelFilterTests(SimpleTestCase):
    def test_descending_field(self):
        self.assertEqual(sort_label('-created_at'), 'Created at ↓')

    def test_ascending_field(self):
        self.assertEqual(sort_label('value'), 'Value ↑')

    def test_no_raw_dash_or_underscore_leaks_through(self):
        result = sort_label('-created_at')
        self.assertNotIn('-created_at', result)
        self.assertNotIn('_', result)

    def test_empty_value(self):
        self.assertEqual(sort_label(''), '')
        self.assertEqual(sort_label(None), '')


class HumanDurationFilterTests(SimpleTestCase):
    def test_seconds_only(self):
        self.assertEqual(humanduration(45), '45s')

    def test_minutes(self):
        self.assertEqual(humanduration(125), '2m')

    def test_hours_and_minutes(self):
        self.assertEqual(humanduration(3725), '1h 2m')

    def test_hours_exact(self):
        self.assertEqual(humanduration(7200), '2h')

    def test_days_and_hours_matches_audit_finding(self):
        # The audit found "Heartbeat: 787296s" on the operations dashboard.
        self.assertEqual(humanduration(787296), '9d 2h')

    def test_non_numeric_passes_through(self):
        self.assertEqual(humanduration('unknown'), 'unknown')
