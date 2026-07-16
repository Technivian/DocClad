"""Governed AI review for uploaded, previously signed agreements.

The review deliberately creates *review items*, never an automatic legal
decision.  Every item is grounded in a verbatim clause citation persisted by
``ai_extraction`` so a contract owner can inspect and resolve it in the normal
risk workflow.
"""
from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

from contracts.models import AIExtractionSpan, CommandCenterWorkItem, Document, Organization, RiskLog
from contracts.services.ai_extraction import AIExtractionError, extract_clause_spans, get_extraction_model


class AIContractReviewUnavailable(RuntimeError):
    """Raised when a workspace cannot run a provider-backed contract review."""


@dataclass(frozen=True)
class ContractReviewResult:
    spans_reviewed: int
    flags_created: int
    model: str


def provider_is_configured() -> bool:
    """Whether this deployment has explicitly enabled the Gemini provider."""
    return bool(
        getattr(settings, 'GEMINI_AI_ENABLED', False)
        and getattr(settings, 'GEMINI_API_KEY', '')
    )


def _risk_level_for_span(span: AIExtractionSpan) -> str:
    if span.risk_level == AIExtractionSpan.RiskLevel.RISK:
        return RiskLog.RiskLevel.HIGH
    return RiskLog.RiskLevel.MEDIUM


def _flag_title(span: AIExtractionSpan) -> str:
    return f'AI review — {span.label_display} needs review'


def _create_flags(document: Document, spans: list[AIExtractionSpan], user) -> int:
    """Persist only non-clear, evidence-backed suggestions as open risk items."""
    if not document.contract_id:
        return 0

    flags_created = 0
    for span in spans:
        if span.risk_level == AIExtractionSpan.RiskLevel.CLEAR:
            continue
        quote = span.span_text.strip()
        rationale = span.rationale.strip() or 'Review this clause against the approved playbook.'
        risk_level = _risk_level_for_span(span)
        flag = RiskLog.objects.create(
            contract=document.contract,
            title=_flag_title(span),
            description=(
                f'AI review evidence from “{document.title}” ({span.label_display}, '
                f'{int(float(span.confidence) * 100)}% confidence):\n“{quote}”'
            ),
            risk_level=risk_level,
            signal_type=RiskLog.SignalType.ESCALATION,
            status=RiskLog.Status.OPEN,
            assigned_to=document.contract.owner,
            follow_up='Validate the cited language and either resolve or update this review item.',
            mitigation_plan=rationale,
            created_by=user,
        )
        priority = (
            CommandCenterWorkItem.Priority.HIGH
            if risk_level == RiskLog.RiskLevel.HIGH
            else CommandCenterWorkItem.Priority.MEDIUM
        )
        CommandCenterWorkItem.objects.create(
            organization=document.organization,
            source_type=CommandCenterWorkItem.SourceType.RISK,
            source_model='RiskLog',
            source_object_id=flag.pk,
            title=flag.title,
            subtitle=f'AI review of {document.title}: {span.label_display} needs human review.',
            item_type='AI contract review',
            stage='Review',
            status=CommandCenterWorkItem.Status.OPEN,
            risk_level=risk_level,
            priority=priority,
            owner=flag.assigned_to,
            contract=document.contract,
            risk_log=flag,
            action_label='Review flag',
            flags={
                'risk_personality': 'AI-identified clause risk',
                'highest_risk_signal': flag.title,
                'blocking_issue': span.rationale or 'AI identified a clause that needs review.',
                'next_action': 'Review the cited clause and record a decision.',
            },
        )
        flags_created += 1
    return flags_created


def review_uploaded_contract(
    *,
    document: Document,
    organization: Organization,
    text: str,
    user,
) -> ContractReviewResult:
    """Run Gemini extraction and create human-owned flags for one upload.

    A usable text layer is required.  Provider errors propagate as a controlled
    review failure; callers must retain the uploaded contract regardless.
    """
    if not provider_is_configured():
        raise AIContractReviewUnavailable('AI review is not configured for this workspace.')
    if not text or not text.strip():
        raise AIContractReviewUnavailable('No readable text was found in this document.')

    try:
        spans = extract_clause_spans(text, organization, document, replace_existing=True)
    except AIExtractionError:
        raise
    flags_created = _create_flags(document, spans, user)
    return ContractReviewResult(
        spans_reviewed=len(spans),
        flags_created=flags_created,
        model=get_extraction_model(),
    )
