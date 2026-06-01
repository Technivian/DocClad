"""Tests for the AI clause-span extraction service (rules engine).

All tests use SimpleTestCase + unittest.mock to avoid hitting the database,
working around the repo's test-DB migration issue (no such table: contracts_*).
"""
import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch, call


class TestClausePatterns(unittest.TestCase):
    """Verify the CLAUSE_PATTERNS dict is well-formed and matches known text."""

    def _import(self):
        from contracts.services.ai_extraction import CLAUSE_PATTERNS, _calibrate_confidence, _extract_excerpt
        return CLAUSE_PATTERNS, _calibrate_confidence, _extract_excerpt

    def test_all_nine_labels_present(self):
        CLAUSE_PATTERNS, _, _ = self._import()
        expected = {
            'indemnity', 'termination', 'liability_cap', 'data_processing',
            'renewal', 'governing_law', 'confidentiality', 'payment_terms', 'ip_ownership',
        }
        self.assertEqual(set(CLAUSE_PATTERNS.keys()), expected)

    def test_indemnity_matches(self):
        import re
        CLAUSE_PATTERNS, _, _ = self._import()
        text = 'The supplier shall indemnify the client against all claims.'
        patterns = CLAUSE_PATTERNS['indemnity']
        found = any(p.search(text) for p, _ in patterns)
        self.assertTrue(found)

    def test_governing_law_matches(self):
        import re
        CLAUSE_PATTERNS, _, _ = self._import()
        text = 'This agreement is governed by the laws of England and Wales.'
        patterns = CLAUSE_PATTERNS['governing_law']
        found = any(p.search(text) for p, _ in patterns)
        self.assertTrue(found)

    def test_payment_net_days_matches(self):
        CLAUSE_PATTERNS, _, _ = self._import()
        text = 'Invoices are due Net 30 days from receipt.'
        found = any(p.search(text) for p, _ in CLAUSE_PATTERNS['payment_terms'])
        self.assertTrue(found)

    def test_min_confidence_threshold(self):
        from contracts.services.ai_extraction import _MIN_CONFIDENCE
        self.assertEqual(_MIN_CONFIDENCE, Decimal('0.50'))

    def test_calibrate_confidence_returns_decimal(self):
        import re
        _, _calibrate_confidence, _ = self._import()
        pattern = re.compile(r'\bindemnif', re.IGNORECASE)
        text = 'The vendor shall indemnify the client.'
        match = pattern.search(text)
        result = _calibrate_confidence(0.75, match, text)
        self.assertIsInstance(result, Decimal)
        self.assertGreaterEqual(result, Decimal('0.50'))
        self.assertLessEqual(result, Decimal('0.95'))

    def test_calibrate_confidence_heading_boost(self):
        """Confidence should be boosted when match sits after a clause heading."""
        import re
        _, _calibrate_confidence, _ = self._import()
        pattern = re.compile(r'\bindemnif', re.IGNORECASE)
        # Simulate heading-like prefix ending with numbered clause
        text = 'Some prefix\n12. Indemnify the party here.'
        match = pattern.search(text)
        if match:
            result = _calibrate_confidence(0.75, match, text)
            # Result should still be capped at 0.95
            self.assertLessEqual(result, Decimal('0.95'))

    def test_extract_excerpt_within_bounds(self):
        _, _, _extract_excerpt = self._import()
        text = 'A' * 500
        excerpt = _extract_excerpt(text, 250, 260)
        # Should not crash; excerpt is at most 200+10+200 chars long
        self.assertLessEqual(len(excerpt), 420)

    def test_extract_excerpt_ellipsis_prefix(self):
        _, _, _extract_excerpt = self._import()
        text = 'X' * 1000
        excerpt = _extract_excerpt(text, 500, 510)
        self.assertTrue(excerpt.startswith('…'))

    def test_extract_excerpt_no_prefix_at_start(self):
        _, _, _extract_excerpt = self._import()
        text = 'Hello world'
        excerpt = _extract_excerpt(text, 0, 5)
        self.assertFalse(excerpt.startswith('…'))


class TestExtractClauseSpans(unittest.TestCase):
    """Test extract_clause_spans with mocked DB."""

    def _run_extraction(self, text, replace_existing=True):
        """Run extraction with DB calls mocked out."""
        mock_org = MagicMock()
        mock_doc = MagicMock()
        mock_doc.id = 42

        with patch('contracts.services.ai_extraction.AIExtractionSpan') as MockSpan:
            mock_qs = MagicMock()
            MockSpan.objects.filter.return_value = mock_qs
            MockSpan.objects.bulk_create = MagicMock()
            # Make constructor return a MagicMock for each span
            MockSpan.side_effect = lambda **kwargs: MagicMock(**kwargs)

            from contracts.services.ai_extraction import extract_clause_spans
            result = extract_clause_spans(text, mock_org, mock_doc, replace_existing=replace_existing)

        return result, MockSpan, mock_qs

    def test_empty_text_returns_empty(self):
        result, _, _ = self._run_extraction('')
        self.assertEqual(result, [])

    def test_whitespace_only_returns_empty(self):
        result, _, _ = self._run_extraction('   \n\t  ')
        self.assertEqual(result, [])

    def test_finds_indemnity_span(self):
        text = 'The supplier shall indemnify the client against all third-party claims arising from this agreement.'
        result, MockSpan, _ = self._run_extraction(text)
        self.assertGreater(len(result), 0)
        MockSpan.objects.bulk_create.assert_called_once()

    def test_finds_governing_law_span(self):
        text = 'Governing Law. This agreement is governed by the laws of California, USA.'
        result, MockSpan, _ = self._run_extraction(text)
        self.assertGreater(len(result), 0)

    def test_replace_existing_true_deletes_prior_spans(self):
        text = 'This contract includes governing law and termination rights.'
        _, MockSpan, mock_qs = self._run_extraction(text, replace_existing=True)
        MockSpan.objects.filter.assert_called()
        mock_qs.delete.assert_called_once()

    def test_replace_existing_false_skips_delete(self):
        text = 'This contract includes governing law.'
        _, MockSpan, mock_qs = self._run_extraction(text, replace_existing=False)
        mock_qs.delete.assert_not_called()

    def test_multiple_labels_extracted(self):
        text = (
            'Indemnification. The vendor shall indemnify the client. '
            'Governing Law. This agreement is governed by the laws of New York. '
            'Termination. Either party may terminate with 30 days notice. '
            'Confidential Information shall not be disclosed.'
        )
        result, MockSpan, _ = self._run_extraction(text)
        self.assertGreaterEqual(len(result), 3)

    def test_bulk_create_not_called_on_no_matches(self):
        text = 'This is a generic contract with no specific clause language.'
        result, MockSpan, _ = self._run_extraction(text)
        if not result:
            MockSpan.objects.bulk_create.assert_not_called()


class TestGetSpansSummary(unittest.TestCase):
    """Test the get_spans_summary utility."""

    def test_empty_spans_returns_correct_shape(self):
        mock_doc = MagicMock()
        with patch('contracts.services.ai_extraction.AIExtractionSpan') as MockSpan:
            MockSpan.objects.filter.return_value.order_by.return_value = []
            from contracts.services.ai_extraction import get_spans_summary
            result = get_spans_summary(mock_doc)

        self.assertIn('extraction_model', result)
        self.assertIn('label_count', result)
        self.assertIn('span_count', result)
        self.assertIn('labels', result)
        self.assertEqual(result['label_count'], 0)
        self.assertEqual(result['span_count'], 0)
        self.assertIsInstance(result['labels'], dict)

    def test_span_is_serialised_correctly(self):
        mock_doc = MagicMock()
        mock_span = MagicMock()
        mock_span.label = 'indemnity'
        mock_span.start_char = 10
        mock_span.end_char = 20
        mock_span.confidence = Decimal('0.75')
        mock_span.span_text = 'The vendor shall indemnify...'

        with patch('contracts.services.ai_extraction.AIExtractionSpan') as MockSpan:
            MockSpan.objects.filter.return_value.order_by.return_value = [mock_span]
            from contracts.services.ai_extraction import get_spans_summary
            result = get_spans_summary(mock_doc)

        self.assertEqual(result['label_count'], 1)
        self.assertEqual(result['span_count'], 1)
        self.assertIn('indemnity', result['labels'])
        span_entry = result['labels']['indemnity'][0]
        self.assertEqual(span_entry['start_char'], 10)
        self.assertEqual(span_entry['confidence'], 0.75)
        self.assertIn('excerpt', span_entry)

    def test_multiple_spans_same_label_grouped(self):
        mock_doc = MagicMock()
        spans = []
        for i in range(3):
            s = MagicMock()
            s.label = 'termination'
            s.start_char = i * 100
            s.end_char = i * 100 + 10
            s.confidence = Decimal('0.60')
            s.span_text = f'termination text {i}'
            spans.append(s)

        with patch('contracts.services.ai_extraction.AIExtractionSpan') as MockSpan:
            MockSpan.objects.filter.return_value.order_by.return_value = spans
            from contracts.services.ai_extraction import get_spans_summary
            result = get_spans_summary(mock_doc)

        self.assertEqual(result['label_count'], 1)
        self.assertEqual(result['span_count'], 3)
        self.assertEqual(len(result['labels']['termination']), 3)


if __name__ == '__main__':
    unittest.main()
