"""Tests for the AI clause-span extraction service (Gemini LLM backend).

All tests use unittest.mock to avoid hitting the database or the real Gemini API.
"""
import json
import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch


def _make_mock_client(json_payload):
    mock_response = MagicMock()
    mock_response.text = json.dumps(json_payload)
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    return mock_client


class TestClauseLabels(unittest.TestCase):
    """Verify the _CLAUSE_LABELS list is well-formed."""

    def test_all_nine_labels_present(self):
        from contracts.services.ai_extraction import _CLAUSE_LABELS
        expected = {
            "indemnity", "termination", "liability_cap", "data_processing",
            "renewal", "governing_law", "confidentiality", "payment_terms", "ip_ownership",
        }
        self.assertEqual(set(_CLAUSE_LABELS), expected)

    def test_extraction_schema_has_label_enum(self):
        from contracts.services.ai_extraction import _EXTRACTION_SCHEMA, _CLAUSE_LABELS
        enum = _EXTRACTION_SCHEMA["properties"]["spans"]["items"]["properties"]["label"]["enum"]
        self.assertEqual(set(enum), set(_CLAUSE_LABELS))


class TestExtractClauseSpans(unittest.TestCase):
    """Test extract_clause_spans with mocked DB and mocked Gemini client."""

    def setUp(self):
        # Reset module-level client singleton so patches take effect cleanly
        import contracts.services.ai_extraction as svc
        svc._client = None

    def _run(self, text, api_spans=None, replace_existing=True):
        """Run extraction with DB and API calls mocked out.

        api_spans is the list of span dicts the mock API will return.
        """
        if api_spans is None:
            api_spans = []

        mock_org = MagicMock()
        mock_doc = MagicMock()
        mock_doc.pk = 42
        mock_client = _make_mock_client({"spans": api_spans})

        with patch("contracts.services.ai_extraction._get_client", return_value=mock_client):
            with patch("contracts.services.ai_extraction.AIExtractionSpan") as MockSpan:
                mock_qs = MagicMock()
                MockSpan.objects.filter.return_value = mock_qs
                MockSpan.objects.bulk_create = MagicMock()
                MockSpan.side_effect = lambda **kwargs: MagicMock(**kwargs)

                from contracts.services.ai_extraction import extract_clause_spans
                result = extract_clause_spans(text, mock_org, mock_doc, replace_existing=replace_existing)

        return result, MockSpan, mock_qs

    def test_empty_text_returns_empty(self):
        result, _, _ = self._run("")
        self.assertEqual(result, [])

    def test_whitespace_only_returns_empty(self):
        result, _, _ = self._run("   \n\t  ")
        self.assertEqual(result, [])

    def test_finds_indemnity_span(self):
        text = "The supplier shall indemnify the client against all third-party claims."
        spans = [{"label": "indemnity", "text": "The supplier shall indemnify", "confidence": 0.9}]
        result, MockSpan, _ = self._run(text, api_spans=spans)
        self.assertGreater(len(result), 0)
        MockSpan.objects.bulk_create.assert_called_once()

    def test_finds_governing_law_span(self):
        text = "Governing Law. This agreement is governed by the laws of California."
        spans = [{"label": "governing_law", "text": "This agreement is governed by the laws of California.", "confidence": 0.95}]
        result, MockSpan, _ = self._run(text, api_spans=spans)
        self.assertGreater(len(result), 0)

    def test_replace_existing_true_deletes_prior_spans(self):
        text = "This contract includes governing law and termination rights."
        spans = [{"label": "governing_law", "text": "governing law", "confidence": 0.8}]
        _, MockSpan, mock_qs = self._run(text, api_spans=spans, replace_existing=True)
        MockSpan.objects.filter.assert_called()
        mock_qs.delete.assert_called_once()

    def test_replace_existing_false_skips_delete(self):
        text = "This contract includes governing law."
        spans = [{"label": "governing_law", "text": "governing law", "confidence": 0.8}]
        _, MockSpan, mock_qs = self._run(text, api_spans=spans, replace_existing=False)
        mock_qs.delete.assert_not_called()

    def test_multiple_labels_extracted(self):
        text = (
            "The vendor shall indemnify the client. "
            "This agreement is governed by the laws of New York. "
            "Either party may terminate with 30 days notice. "
            "Confidential Information shall not be disclosed."
        )
        spans = [
            {"label": "indemnity", "text": "The vendor shall indemnify the client.", "confidence": 0.9},
            {"label": "governing_law", "text": "governed by the laws of New York.", "confidence": 0.9},
            {"label": "termination", "text": "Either party may terminate with 30 days notice.", "confidence": 0.85},
            {"label": "confidentiality", "text": "Confidential Information shall not be disclosed.", "confidence": 0.8},
        ]
        result, _, _ = self._run(text, api_spans=spans)
        self.assertGreaterEqual(len(result), 3)

    def test_bulk_create_not_called_on_no_matches(self):
        text = "This is a generic contract with no specific clause language."
        result, MockSpan, _ = self._run(text, api_spans=[])
        if not result:
            MockSpan.objects.bulk_create.assert_not_called()

    def test_span_not_found_in_text_is_skipped(self):
        """A quoted span that cannot be located in the document is silently dropped."""
        text = "This is a contract about something."
        spans = [{"label": "indemnity", "text": "this text does not appear", "confidence": 0.9}]
        result, _, _ = self._run(text, api_spans=spans)
        self.assertEqual(len(result), 0)

    def test_api_calls_generate_content(self):
        """Verify the service calls client.models.generate_content."""
        text = "The vendor shall indemnify the client."
        mock_org = MagicMock()
        mock_doc = MagicMock()
        mock_doc.pk = 1
        mock_client = _make_mock_client({"spans": []})

        import contracts.services.ai_extraction as svc
        svc._client = None

        with patch("contracts.services.ai_extraction._get_client", return_value=mock_client):
            with patch("contracts.services.ai_extraction.AIExtractionSpan") as MockSpan:
                MockSpan.objects.filter.return_value = MagicMock()
                MockSpan.objects.bulk_create = MagicMock()

                from contracts.services.ai_extraction import extract_clause_spans
                extract_clause_spans(text, mock_org, mock_doc)

        mock_client.models.generate_content.assert_called_once()

    def test_uses_current_stable_gemini_flash_model(self):
        from contracts.services.ai_extraction import _MODEL
        self.assertEqual(_MODEL, "gemini-3.5-flash")


class TestGetSpansSummary(unittest.TestCase):
    """Test the get_spans_summary utility."""

    def test_empty_spans_returns_correct_shape(self):
        mock_doc = MagicMock()
        with patch("contracts.services.ai_extraction.AIExtractionSpan") as MockSpan:
            MockSpan.objects.filter.return_value.order_by.return_value = []
            from contracts.services.ai_extraction import get_spans_summary
            result = get_spans_summary(mock_doc)

        self.assertIn("extraction_model", result)
        self.assertIn("label_count", result)
        self.assertIn("span_count", result)
        self.assertIn("labels", result)
        self.assertEqual(result["label_count"], 0)
        self.assertEqual(result["span_count"], 0)
        self.assertIsInstance(result["labels"], dict)

    def test_span_is_serialised_correctly(self):
        mock_doc = MagicMock()
        mock_span = MagicMock()
        mock_span.label = "indemnity"
        mock_span.start_char = 10
        mock_span.end_char = 20
        mock_span.confidence = Decimal("0.75")
        mock_span.span_text = "The vendor shall indemnify..."

        with patch("contracts.services.ai_extraction.AIExtractionSpan") as MockSpan:
            MockSpan.objects.filter.return_value.order_by.return_value = [mock_span]
            from contracts.services.ai_extraction import get_spans_summary
            result = get_spans_summary(mock_doc)

        self.assertEqual(result["label_count"], 1)
        self.assertEqual(result["span_count"], 1)
        self.assertIn("indemnity", result["labels"])
        span_entry = result["labels"]["indemnity"][0]
        self.assertEqual(span_entry["start_char"], 10)
        self.assertEqual(span_entry["confidence"], 0.75)
        self.assertIn("excerpt", span_entry)

    def test_multiple_spans_same_label_grouped(self):
        mock_doc = MagicMock()
        spans = []
        for i in range(3):
            s = MagicMock()
            s.label = "termination"
            s.start_char = i * 100
            s.end_char = i * 100 + 10
            s.confidence = Decimal("0.60")
            s.span_text = f"termination text {i}"
            spans.append(s)

        with patch("contracts.services.ai_extraction.AIExtractionSpan") as MockSpan:
            MockSpan.objects.filter.return_value.order_by.return_value = spans
            from contracts.services.ai_extraction import get_spans_summary
            result = get_spans_summary(mock_doc)

        self.assertEqual(result["label_count"], 1)
        self.assertEqual(result["span_count"], 3)
        self.assertEqual(len(result["labels"]["termination"]), 3)


if __name__ == "__main__":
    unittest.main()
