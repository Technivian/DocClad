"""AI (or deterministic) assistance that changes an approval decision comment.

Suggestions never auto-submit. Callers must still require the actor to confirm.
"""

from __future__ import annotations

import logging
import re

from django.conf import settings

from contracts.models import OrgPolicy
from contracts.services.ai_policy import evaluate_prompt

logger = logging.getLogger(__name__)

_DECISION_LABELS = {
    'reject': 'rejection',
    'return': 'return for changes',
    'request_changes': 'return for changes',
}


def ai_decision_assist_enabled(organization) -> bool:
    if organization is None:
        return False
    if not getattr(settings, 'GEMINI_AI_ENABLED', False):
        return False
    if not getattr(settings, 'GEMINI_API_KEY', ''):
        return False
    policy = OrgPolicy.objects.filter(organization=organization).first()
    if policy is not None and not policy.ai_features_enabled:
        return False
    return True


def _deterministic_suggestion(approval, decision: str) -> str:
    """Fallback when Gemini is off — still fills a decision-changing comment."""
    contract = getattr(approval, 'contract', None)
    step = (getattr(approval, 'approval_step', None) or 'approval').replace('_', ' ').strip()
    title = (contract.title if contract else '') or 'this contract'
    ctype = (contract.get_contract_type_display() if contract and hasattr(contract, 'get_contract_type_display') else '') or (
        getattr(contract, 'contract_type', '') if contract else 'agreement'
    )
    decision_key = (decision or 'return').strip().lower()
    if decision_key in ('reject', 'rejection'):
        return (
            f'Rejecting the {step} step on {title} ({ctype}). '
            f'The current draft does not meet our requirements for this stage; '
            f'please revise the governing terms before resubmitting.'
        )
    return (
        f'Returning the {step} step on {title} ({ctype}) for changes. '
        f'Please clarify the commercial terms and update the draft so this approval can proceed.'
    )


def _gemini_suggestion(approval, decision: str) -> str | None:
    from google import genai
    from google.genai import types

    contract = getattr(approval, 'contract', None)
    decision_label = _DECISION_LABELS.get((decision or '').strip().lower(), 'return for changes')
    step = (getattr(approval, 'approval_step', None) or 'approval').replace('_', ' ')
    title = (contract.title if contract else '') or 'Untitled contract'
    ctype = getattr(contract, 'contract_type', '') if contract else ''
    existing = (getattr(approval, 'comments', None) or '').strip()
    prompt = (
        'You are a legal operations assistant. Draft a concise approval decision comment '
        f'for a {decision_label} action. The comment will be submitted as the official reason.\n\n'
        f'Approval step: {step}\n'
        f'Contract: {title}\n'
        f'Contract type: {ctype or "unknown"}\n'
        f'Existing comments: {existing or "(none)"}\n\n'
        'Write 2-3 sentences, professional tone, no bullet points, no preamble. '
        'Do not invent specific clause numbers or party names that are not provided.'
    )
    policy = evaluate_prompt(prompt)
    if not policy.get('allowed', True):
        return None

    model = getattr(settings, 'GEMINI_MODEL', 'gemini-3.5-flash')
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    response = client.models.generate_content(
        model=model,
        contents=policy.get('normalized_prompt') or prompt,
        config=types.GenerateContentConfig(temperature=0.3, max_output_tokens=220),
    )
    text = (getattr(response, 'text', None) or '').strip()
    if not text:
        return None
    # Strip accidental quotes / markdown fences.
    text = re.sub(r'^```(?:\w+)?\s*|\s*```$', '', text).strip()
    text = text.strip('"').strip("'").strip()
    return text[:1200] or None


def suggest_approval_decision_comment(approval, decision: str, *, allow_ai: bool = True) -> dict:
    """Return `{suggestion, source}` for reject/return comments."""
    decision_key = (decision or 'return').strip().lower()
    if decision_key in ('request_changes', 'changes', 'changes_requested'):
        decision_key = 'return'
    if decision_key not in ('reject', 'return'):
        raise ValueError('decision must be reject or return')

    organization = getattr(approval, 'organization', None)
    if organization is None and getattr(approval, 'contract', None) is not None:
        organization = approval.contract.organization

    source = 'template'
    suggestion = _deterministic_suggestion(approval, decision_key)
    if allow_ai and ai_decision_assist_enabled(organization):
        try:
            ai_text = _gemini_suggestion(approval, decision_key)
            if ai_text:
                suggestion = ai_text
                source = 'ai'
        except Exception:
            logger.exception('AI decision suggestion failed; using template fallback')

    return {'suggestion': suggestion, 'source': source, 'decision': decision_key}
