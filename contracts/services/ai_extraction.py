"""Rules-engine AI extraction service for clause text-span citations.

Extracts labelled spans from OCR-extracted document text, scoring each match
with a calibrated confidence value. Does not call any external LLM — all
patterns are deterministic regex, making the output auditable and replayable.
"""

from __future__ import annotations

import re
from decimal import Decimal

from contracts.models import AIExtractionSpan, Document, Organization


# Each entry: label -> list of (pattern, base_confidence_increment)
# Patterns are tried in order; first match wins per non-overlapping window.
CLAUSE_PATTERNS: dict[str, list[tuple[re.Pattern, float]]] = {
    'indemnity': [
        (re.compile(r'\bindemnif(?:y|ies|ied|ication)\b', re.IGNORECASE), 0.75),
        (re.compile(r'\bholds?\s+harmless\b', re.IGNORECASE), 0.65),
        (re.compile(r'\bindemnity\b', re.IGNORECASE), 0.70),
    ],
    'termination': [
        (re.compile(r'\btermination\s+(?:for\s+cause|without\s+cause|clause|right)\b', re.IGNORECASE), 0.80),
        (re.compile(r'\bterminat(?:e|ion)\b', re.IGNORECASE), 0.55),
        (re.compile(r'\bright\s+to\s+cancel\b', re.IGNORECASE), 0.60),
    ],
    'liability_cap': [
        (re.compile(r'\blimitation\s+of\s+liability\b', re.IGNORECASE), 0.85),
        (re.compile(r'\bliability\s+(?:shall\s+not\s+exceed|is\s+capped|cap)\b', re.IGNORECASE), 0.80),
        (re.compile(r'\bexclusion\s+of\s+(?:indirect\s+)?damages\b', re.IGNORECASE), 0.70),
        (re.compile(r'\bin\s+no\s+event\s+shall\b', re.IGNORECASE), 0.65),
    ],
    'data_processing': [
        (re.compile(r'\bdata\s+processing\s+agreement\b', re.IGNORECASE), 0.90),
        (re.compile(r'\bDPA\b'), 0.70),
        (re.compile(r'\bpersonal\s+data\b', re.IGNORECASE), 0.60),
        (re.compile(r'\bGDPR\b'), 0.75),
        (re.compile(r'\bdata\s+(?:controller|processor|subject)\b', re.IGNORECASE), 0.65),
    ],
    'renewal': [
        (re.compile(r'\bauto(?:matic(?:ally)?)?\s+renew(?:al|s)?\b', re.IGNORECASE), 0.85),
        (re.compile(r'\brenew(?:al|s|ed|ing)?\b', re.IGNORECASE), 0.55),
        (re.compile(r'\brollover\b', re.IGNORECASE), 0.55),
    ],
    'governing_law': [
        (re.compile(r'\bgoverning\s+law\b', re.IGNORECASE), 0.90),
        (re.compile(r'\bgoverned\s+by\s+the\s+laws?\s+of\b', re.IGNORECASE), 0.85),
        (re.compile(r'\bjurisdiction\s+(?:of|shall\s+be)\b', re.IGNORECASE), 0.70),
        (re.compile(r'\bapplicable\s+law\b', re.IGNORECASE), 0.65),
    ],
    'confidentiality': [
        (re.compile(r'\bconfidentiality\s+(?:obligation|clause|agreement)\b', re.IGNORECASE), 0.85),
        (re.compile(r'\bNDA\b'), 0.75),
        (re.compile(r'\bnon[-\s]disclosure\b', re.IGNORECASE), 0.80),
        (re.compile(r'\bconfidential\s+information\b', re.IGNORECASE), 0.60),
    ],
    'payment_terms': [
        (re.compile(r'\bpayment\s+terms?\b', re.IGNORECASE), 0.80),
        (re.compile(r'\bnet\s+\d+\s*days?\b', re.IGNORECASE), 0.85),
        (re.compile(r'\binvoice\s+(?:date|period|due)\b', re.IGNORECASE), 0.65),
        (re.compile(r'\blate\s+payment\s+(?:fee|interest|penalty)\b', re.IGNORECASE), 0.70),
    ],
    'ip_ownership': [
        (re.compile(r'\bintellectual\s+property\s+(?:rights?|ownership)\b', re.IGNORECASE), 0.85),
        (re.compile(r'\bwork\s+made\s+for\s+hire\b', re.IGNORECASE), 0.80),
        (re.compile(r'\bassignment\s+of\s+(?:intellectual\s+property|IP|rights?)\b', re.IGNORECASE), 0.80),
        (re.compile(r'\bIP\s+(?:ownership|rights?|assignment)\b'), 0.70),
    ],
}

_EXCERPT_WINDOW = 200  # characters on each side of match for context
_MIN_CONFIDENCE = Decimal('0.50')


def _extract_excerpt(text: str, start: int, end: int) -> str:
    excerpt_start = max(0, start - _EXCERPT_WINDOW)
    excerpt_end = min(len(text), end + _EXCERPT_WINDOW)
    prefix = '…' if excerpt_start > 0 else ''
    suffix = '…' if excerpt_end < len(text) else ''
    return prefix + text[excerpt_start:excerpt_end].strip() + suffix


def _calibrate_confidence(base: float, match: re.Match, text: str) -> Decimal:
    """Boost confidence if match sits inside a clearly identified clause heading."""
    score = base
    # Bump if the matched word appears to start a sentence/clause heading
    pre_context = text[max(0, match.start() - 50): match.start()].strip()
    if re.search(r'(?:\n|^|\.\s+)[A-Z0-9]+\s*\.?\s*$', pre_context):
        score = min(0.95, score + 0.10)
    return Decimal(str(round(score, 4)))


def extract_clause_spans(
    text: str,
    organization: Organization,
    document: Document,
    *,
    replace_existing: bool = True,
) -> list[AIExtractionSpan]:
    """Scan *text* for labelled clause patterns and persist AIExtractionSpan rows.

    Set *replace_existing=True* (default) to delete prior spans for this
    document before inserting new ones (idempotent re-extraction).
    """
    if not text or not text.strip():
        return []

    if replace_existing:
        AIExtractionSpan.objects.filter(document=document).delete()

    spans: list[AIExtractionSpan] = []

    for label, patterns in CLAUSE_PATTERNS.items():
        seen_ranges: list[tuple[int, int]] = []
        for pattern, base_confidence in patterns:
            for match in pattern.finditer(text):
                start, end = match.start(), match.end()
                # Skip if overlapping with an already-captured span for this label
                if any(s <= start < e or s < end <= e for s, e in seen_ranges):
                    continue
                confidence = _calibrate_confidence(base_confidence, match, text)
                if confidence < _MIN_CONFIDENCE:
                    continue
                excerpt = _extract_excerpt(text, start, end)
                spans.append(
                    AIExtractionSpan(
                        document=document,
                        organization=organization,
                        label=label,
                        span_text=excerpt,
                        start_char=start,
                        end_char=end,
                        confidence=confidence,
                        extraction_model='rules-engine-v1',
                    )
                )
                seen_ranges.append((start, end))

    if spans:
        AIExtractionSpan.objects.bulk_create(spans)

    return spans


def get_spans_for_document(document: Document) -> list[AIExtractionSpan]:
    return list(
        AIExtractionSpan.objects.filter(document=document).order_by('start_char')
    )


def get_spans_summary(document: Document) -> dict:
    """Return a label→[spans] dict suitable for JSON serialisation."""
    by_label: dict[str, list[dict]] = {}
    for span in get_spans_for_document(document):
        by_label.setdefault(span.label, []).append(
            {
                'start_char': span.start_char,
                'end_char': span.end_char,
                'confidence': float(span.confidence),
                'excerpt': span.span_text[:300],
            }
        )
    return {
        'extraction_model': 'rules-engine-v1',
        'label_count': len(by_label),
        'span_count': sum(len(v) for v in by_label.values()),
        'labels': by_label,
    }
