"""AI (or deterministic) assistance that changes a work decision comment.

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
    'reassign': 'reassignment',
    'conflict_resolved': 'privacy conflict resolved',
    'conflict_false_positive': 'privacy conflict marked false positive',
    'escalate': 'obligation escalation',
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


def _contract_bits(contract):
    title = (contract.title if contract else '') or 'this contract'
    ctype = ''
    if contract is not None:
        if hasattr(contract, 'get_contract_type_display'):
            ctype = contract.get_contract_type_display() or ''
        ctype = ctype or getattr(contract, 'contract_type', '') or 'agreement'
    return title, ctype or 'agreement'


def _deterministic_suggestion(*, kind: str, contract=None, approval=None, risk_item=None, deadline=None) -> str:
    title, ctype = _contract_bits(contract)
    kind_key = (kind or '').strip().lower()

    if kind_key in ('reject', 'rejection'):
        step = (getattr(approval, 'approval_step', None) or 'approval').replace('_', ' ').strip()
        return (
            f'Rejecting the {step} step on {title} ({ctype}). '
            f'The current draft does not meet our requirements for this stage; '
            f'please revise the governing terms before resubmitting.'
        )
    if kind_key in ('return', 'request_changes', 'changes', 'changes_requested'):
        step = (getattr(approval, 'approval_step', None) or 'approval').replace('_', ' ').strip()
        return (
            f'Returning the {step} step on {title} ({ctype}) for changes. '
            f'Please clarify the commercial terms and update the draft so this approval can proceed.'
        )
    if kind_key == 'reassign':
        step = (getattr(approval, 'approval_step', None) or 'approval').replace('_', ' ').strip()
        return (
            f'Reassigning the {step} step on {title} ({ctype}) to rebalance workload '
            f'and keep this approval moving without delaying the operating loop.'
        )
    if kind_key == 'conflict_resolved':
        risk_title = (getattr(risk_item, 'title', None) or 'cross-document conflict').strip()
        return (
            f'Marking “{risk_title}” on {title} as resolved. '
            f'The conflicting language has been reconciled and no longer blocks privacy review completion.'
        )
    if kind_key == 'conflict_false_positive':
        risk_title = (getattr(risk_item, 'title', None) or 'cross-document conflict').strip()
        return (
            f'Marking “{risk_title}” on {title} as a false positive. '
            f'After review, the flagged conflict does not represent a material privacy risk for this pack.'
        )
    if kind_key == 'escalate':
        obl = (getattr(deadline, 'title', None) or 'this obligation').strip()
        return (
            f'Escalating “{obl}” on {title} ({ctype}) to critical priority. '
            f'The due date or dependency risk requires immediate owner attention.'
        )
    raise ValueError('Unsupported suggestion kind')


def _gemini_suggestion(*, kind: str, contract=None, approval=None, risk_item=None, deadline=None) -> str | None:
    from google import genai
    from google.genai import types

    decision_label = _DECISION_LABELS.get((kind or '').strip().lower(), 'decision')
    title, ctype = _contract_bits(contract)
    extra = []
    if approval is not None:
        extra.append(f'Approval step: {(approval.approval_step or "approval").replace("_", " ")}')
        if approval.comments:
            extra.append(f'Existing approval comments: {approval.comments.strip()[:400]}')
    if risk_item is not None:
        extra.append(f'Risk item: {(risk_item.title or "").strip() or "conflict"}')
        if risk_item.description:
            extra.append(f'Risk description: {risk_item.description.strip()[:400]}')
    if deadline is not None:
        extra.append(f'Obligation: {(deadline.title or "").strip() or "obligation"}')
        if deadline.due_date:
            extra.append(f'Due date: {deadline.due_date}')
    prompt = (
        'You are a legal operations assistant. Draft a concise comment '
        f'for a {decision_label} action. The comment will be submitted as the official reason.\n\n'
        f'Contract: {title}\n'
        f'Contract type: {ctype}\n'
        + ('\n'.join(extra) + '\n' if extra else '')
        + '\nWrite 2-3 sentences, professional tone, no bullet points, no preamble. '
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
    text = re.sub(r'^```(?:\w+)?\s*|\s*```$', '', text).strip()
    text = text.strip('"').strip("'").strip()
    return text[:1200] or None


def suggest_work_action_comment(
    kind: str,
    *,
    organization=None,
    approval=None,
    risk_item=None,
    deadline=None,
    allow_ai: bool = True,
) -> dict:
    """Return `{suggestion, source, decision}` for decision-changing work comments."""
    kind_key = (kind or '').strip().lower()
    if kind_key in ('request_changes', 'changes', 'changes_requested'):
        kind_key = 'return'
    if kind_key in ('rejection',):
        kind_key = 'reject'
    allowed = {
        'reject', 'return', 'reassign',
        'conflict_resolved', 'conflict_false_positive', 'escalate',
    }
    if kind_key not in allowed:
        raise ValueError('Unsupported suggestion kind')

    contract = None
    if approval is not None:
        contract = getattr(approval, 'contract', None)
        organization = organization or getattr(approval, 'organization', None) or (
            contract.organization if contract else None
        )
    if risk_item is not None:
        pack = getattr(risk_item, 'review_pack', None)
        contract = contract or (pack.contract if pack else None)
        organization = organization or (pack.organization if pack else None)
    if deadline is not None:
        contract = contract or getattr(deadline, 'contract', None)
        organization = organization or (contract.organization if contract else None)

    source = 'template'
    suggestion = _deterministic_suggestion(
        kind=kind_key,
        contract=contract,
        approval=approval,
        risk_item=risk_item,
        deadline=deadline,
    )
    if allow_ai and ai_decision_assist_enabled(organization):
        try:
            ai_text = _gemini_suggestion(
                kind=kind_key,
                contract=contract,
                approval=approval,
                risk_item=risk_item,
                deadline=deadline,
            )
            if ai_text:
                suggestion = ai_text
                source = 'ai'
        except Exception:
            logger.exception('AI work-action suggestion failed; using template fallback')

    return {'suggestion': suggestion, 'source': source, 'decision': kind_key}


def suggest_approval_decision_comment(approval, decision: str, *, allow_ai: bool = True) -> dict:
    """Back-compat wrapper for reject/return suggestions."""
    return suggest_work_action_comment(
        decision,
        approval=approval,
        allow_ai=allow_ai,
    )
