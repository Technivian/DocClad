"""AI clause extraction — uses Google Gemini Flash to identify and locate legal clause spans."""
from __future__ import annotations

import json
import logging
from decimal import Decimal

from google import genai
from google.genai import types
from django.db import transaction
from django.db.models import Q

from contracts.models import AIExtractionSpan, ClauseTemplate, Document, Organization

logger = logging.getLogger(__name__)

_MODEL = "gemini-3.5-flash"  # compatibility alias; runtime value comes from settings
_MAX_TEXT_CHARS = 50_000  # ~12.5 K tokens — covers most contracts

_CLAUSE_LABELS = [
    "indemnity",
    "termination",
    "liability_cap",
    "data_processing",
    "renewal",
    "governing_law",
    "confidentiality",
    "payment_terms",
    "ip_ownership",
]

_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "spans": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string", "enum": _CLAUSE_LABELS},
                    "text": {
                        "type": "string",
                        "description": "Verbatim quote from the document (<=400 chars)",
                    },
                    "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "risk_level": {
                        "type": "string",
                        "enum": ["CLEAR", "REVIEW", "RISK"],
                        "description": "RISK only for language requiring intervention; REVIEW when uncertain",
                    },
                    "rationale": {
                        "type": "string",
                        "description": "Brief evidence-based reason for the risk classification",
                    },
                },
                "required": ["label", "text", "confidence", "risk_level", "rationale"],
            },
        }
    },
    "required": ["spans"],
}

_client: genai.Client | None = None


class AIExtractionError(RuntimeError):
    """Raised when the provider returns an unusable extraction response."""


def get_extraction_model() -> str:
    from django.conf import settings
    return getattr(settings, 'GEMINI_MODEL', 'gemini-3.5-flash')


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        from django.conf import settings
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


_LABEL_TERMS = {
    'indemnity': ('indemnity', 'indemnification'),
    'termination': ('termination', 'exit'),
    'liability_cap': ('liability', 'limitation of liability', 'damages cap'),
    'data_processing': ('data protection', 'data processing', 'privacy', 'gdpr'),
    'renewal': ('renewal', 'auto-renewal', 'extension'),
    'governing_law': ('governing law', 'jurisdiction'),
    'confidentiality': ('confidentiality', 'non-disclosure', 'nda'),
    'payment_terms': ('payment terms', 'fees', 'invoicing'),
    'ip_ownership': ('intellectual property', 'ip ownership', 'ownership'),
}


def _matches_contract_type(template: ClauseTemplate, document: Document) -> bool:
    configured = {
        value.strip().upper()
        for value in (template.applicable_contract_types or '').split(',')
        if value.strip()
    }
    contract_type = getattr(getattr(document, 'contract', None), 'contract_type', '')
    return not configured or not contract_type or contract_type.upper() in configured


def _match_approved_template(
    label: str,
    organization: Organization,
    document: Document,
) -> ClauseTemplate | None:
    """Deterministically ground a citation in this tenant's approved library."""
    if not isinstance(organization, Organization) or not isinstance(document, Document):
        return None
    terms = _LABEL_TERMS.get(label, (label.replace('_', ' '),))
    query = Q()
    for term in terms:
        query |= Q(title__icontains=term) | Q(tags__icontains=term)
        query |= Q(category__name__icontains=term)
    candidates = (
        ClauseTemplate.objects
        .filter(organization=organization, is_approved=True)
        .filter(query)
        .select_related('category')
        .order_by('-version', 'title')[:20]
    )
    return next((item for item in candidates if _matches_contract_type(item, document)), None)


def extract_clause_spans(
    text: str,
    organization: Organization,
    document: Document,
    *,
    replace_existing: bool = True,
) -> list[AIExtractionSpan]:
    """Extract labelled clause spans from *text* using Gemini and persist AIExtractionSpan rows.

    Set *replace_existing=True* (default) to atomically replace prior spans for
    this document after the provider response has been fully validated.
    """
    if not text or not text.strip():
        return []

    label_list = ", ".join(_CLAUSE_LABELS)
    prompt = (
        "Extract all legal clause spans from the contract text below.\n\n"
        f"For each clause found return:\n"
        f"  label      - one of: {label_list}\n"
        "  text       - a VERBATIM quote (<=400 chars) capturing the key sentence(s)."
        " The text MUST appear in the document exactly as written.\n"
        "  confidence - 0.0-1.0 (omit spans below 0.5)\n\n"
        "Multiple spans per label are allowed when the clause appears more than once.\n\n"
        f"CONTRACT TEXT:\n{text[:_MAX_TEXT_CHARS]}"
    )

    model = get_extraction_model()
    response = _get_client().models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type='application/json',
            response_schema=_EXTRACTION_SCHEMA,
            temperature=0,
        ),
    )

    try:
        data = json.loads(response.text or '')
    except (TypeError, ValueError) as exc:
        raise AIExtractionError('The AI provider returned an unreadable result.') from exc
    if not isinstance(data, dict) or not isinstance(data.get('spans'), list):
        raise AIExtractionError('The AI provider returned an invalid extraction result.')

    spans: list[AIExtractionSpan] = []
    for item in data.get("spans", []):
        if not isinstance(item, dict) or item.get('label') not in _CLAUSE_LABELS:
            continue
        span_text = (item.get("text") or "").strip()
        if not span_text:
            continue
        pos = text.find(span_text)
        if pos == -1:
            pos = text.lower().find(span_text.lower())
        if pos == -1:
            logger.debug(
                "ai_extraction: quoted span not located in document %s, skipping: %.80s",
                document.pk,
                span_text,
            )
            continue
        try:
            confidence_value = min(1.0, max(0.0, float(item.get('confidence', 0))))
        except (TypeError, ValueError):
            continue
        if confidence_value < 0.5:
            continue
        confidence = Decimal(str(round(confidence_value, 4)))
        source_template = _match_approved_template(item['label'], organization, document)
        risk_level = str(item.get('risk_level') or AIExtractionSpan.RiskLevel.REVIEW).upper()
        if risk_level not in AIExtractionSpan.RiskLevel.values:
            risk_level = AIExtractionSpan.RiskLevel.REVIEW
        if risk_level == AIExtractionSpan.RiskLevel.CLEAR and source_template is None:
            risk_level = AIExtractionSpan.RiskLevel.REVIEW
        spans.append(
            AIExtractionSpan(
                document=document,
                organization=organization,
                label=item["label"],
                span_text=span_text,
                start_char=pos,
                end_char=pos + len(span_text),
                confidence=confidence,
                extraction_model=model,
                rationale=str(item.get('rationale') or '')[:500],
                risk_level=risk_level,
                source_template=source_template,
            )
        )

    with transaction.atomic():
        if replace_existing:
            AIExtractionSpan.objects.filter(
                document=document,
                organization=organization,
            ).delete()
        if spans:
            AIExtractionSpan.objects.bulk_create(spans)

    return spans


def get_spans_for_document(document: Document) -> list[AIExtractionSpan]:
    return list(
        AIExtractionSpan.objects.filter(document=document).order_by("start_char")
    )


def get_spans_summary(document: Document) -> dict:
    """Return a label->spans dict suitable for JSON serialisation."""
    by_label: dict[str, list[dict]] = {}
    extraction_model = ''
    for span in get_spans_for_document(document):
        extraction_model = extraction_model or span.extraction_model
        by_label.setdefault(span.label, []).append(
            {
                "id": span.pk,
                "start_char": span.start_char,
                "end_char": span.end_char,
                "confidence": float(span.confidence),
                "excerpt": span.span_text[:300],
                "risk_level": span.risk_level,
                "rationale": span.rationale,
                "review_status": span.review_status,
                "reviewed_by": span.reviewed_by.get_full_name() or span.reviewed_by.username if span.reviewed_by else None,
                "source_template": ({
                    "id": span.source_template_id,
                    "title": span.source_template.title,
                    "version": span.source_template.version,
                    "playbook_notes": span.source_template.playbook_notes,
                    "fallback_content": span.source_template.fallback_content,
                } if span.source_template_id else None),
            }
        )
    return {
        "extraction_model": extraction_model or get_extraction_model(),
        "label_count": len(by_label),
        "span_count": sum(len(v) for v in by_label.values()),
        "labels": by_label,
    }
