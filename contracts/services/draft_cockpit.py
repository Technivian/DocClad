"""Governance data for the New Contract drafting cockpit — everything the
right-hand "AI Governance Panel" and the live draft preview need, all read
from persisted rows. No network calls, no fabricated risk scores: a new
draft has no RiskLog/DPARiskItem rows yet, so the risk panel says that
plainly rather than inventing a score for a contract that doesn't exist.

Real generative AI (clause drafting/explanation) lives in
contracts/services/ai_drafting.py, gated by settings.GEMINI_AI_ENABLED —
this module never calls it and never emulates its output. See
CLAUSE_ACTION_AVAILABILITY below for how the UI represents that gate.
"""
from dataclasses import asdict, dataclass
from typing import List, Optional

from django.conf import settings

from contracts.models import ClauseTemplate, Contract, ContractTemplate
from contracts.services.clause_policy import normalize_clause_type_list
from contracts.services.contract_templates import MERGE_FIELDS
from contracts.services.workflow_routing import HIGH_RISK_TYPES, HIGH_VALUE_THRESHOLD


def get_preview_template_body(contract_type: str, selected_template: Optional[ContractTemplate] = None) -> Optional[str]:
    """Body text to render in the live draft preview.

    Prefers an explicitly chosen template (?template=<id>), then the type's
    recommended template, then None — the preview then shows an honest
    "no approved template yet" state rather than fabricated contract text.
    """
    if selected_template is not None:
        return selected_template.body or None
    if not contract_type or contract_type == Contract.ContractType.OTHER:
        return None
    template = ContractTemplate.objects.filter(contract_type=contract_type, is_active=True).order_by('name').first()
    return template.body if template else None


def get_clause_library_count(organization, contract_type: str) -> int:
    """How many approved clauses in this org's library apply to this type —
    a blank `applicable_contract_types` means "applies to all types"."""
    if not contract_type:
        return 0
    from django.db.models import Q
    qs = ClauseTemplate.objects.filter(is_approved=True)
    if organization is not None:
        qs = qs.filter(Q(organization=organization) | Q(organization__isnull=True))
    else:
        qs = qs.filter(organization__isnull=True)
    matching = 0
    for clause in qs.only('applicable_contract_types'):
        allowed = normalize_clause_type_list(clause.applicable_contract_types)
        if not allowed or contract_type in allowed:
            matching += 1
    return matching


@dataclass
class ApprovalRouteStep:
    name: str
    note: str
    is_conditional: bool = False


def get_approval_route_preview(contract_type: str) -> List[ApprovalRouteStep]:
    """A real, if simplified, approval route derived from the same
    high-risk-type set and value threshold already used to route contracts
    to due-diligence review elsewhere (contracts/services/workflow_routing.py)
    — not a separate, invented threshold."""
    steps = [
        ApprovalRouteStep(name='Contract Owner', note='Drafts and completes intake'),
        ApprovalRouteStep(name='Legal', note='Reviews terms and clause positions'),
    ]
    if contract_type in HIGH_RISK_TYPES:
        steps.append(ApprovalRouteStep(
            name='Finance', note=f'Value ≥ ${HIGH_VALUE_THRESHOLD:,.0f} or high-risk type', is_conditional=True,
        ))
    if contract_type == Contract.ContractType.DPA:
        steps.append(ApprovalRouteStep(name='DPO', note='Personal data processing involved', is_conditional=True))
    return steps


# Which AI action-bar buttons are backed by real, persisted data today
# (playbook/clause-library lookups) versus generative text that requires
# the gated Gemini integration (contracts/services/ai_drafting.py). Keeps
# the UI honest about which buttons do something right now.
CLAUSE_ACTION_AVAILABILITY = {
    'suggest_fallback': 'persisted',   # real: ClauseTemplate.fallback_content / playbook_notes
    'compare_playbook': 'persisted',   # real: ClausePlaybook / ClauseVariant lookups
    'explain_clause': 'generative',    # requires GEMINI_AI_ENABLED
    'generate_summary': 'generative',  # requires GEMINI_AI_ENABLED
}


def get_risk_summary(contract: Optional[Contract]) -> dict:
    """Real risk signals for an already-saved contract — a brand-new draft
    has no RiskLog/DPARiskItem rows yet, so it says exactly that rather
    than inventing a risk score for a contract that doesn't exist."""
    if contract is None or contract.pk is None:
        return {'has_data': False, 'open_count': 0, 'high_or_critical_count': 0}
    from contracts.models import RiskLog
    open_risks = RiskLog.objects.filter(contract=contract).exclude(status=RiskLog.Status.RESOLVED)
    return {
        'has_data': True,
        'open_count': open_risks.count(),
        'high_or_critical_count': open_risks.filter(risk_level__in=['HIGH', 'CRITICAL']).count(),
    }


def get_governance_panel(
    organization, contract_type: str, selected_template: Optional[ContractTemplate], contract: Optional[Contract] = None,
) -> dict:
    template = selected_template or (
        ContractTemplate.objects.filter(contract_type=contract_type, is_active=True).order_by('name').first()
        if contract_type else None
    )
    return {
        'template': {'id': template.pk, 'name': template.name} if template else None,
        'clause_library_count': get_clause_library_count(organization, contract_type),
        'gemini_ai_enabled': bool(getattr(settings, 'GEMINI_AI_ENABLED', False)),
        'approval_route': [asdict(step) for step in get_approval_route_preview(contract_type)],
        'merge_fields': MERGE_FIELDS,
        'risk_summary': get_risk_summary(contract),
    }
