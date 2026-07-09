"""Contract Launch Setup — per-contract-type recommended template, review/
approval route, and required fields for the New Contract Request page.

This is configurable workflow *metadata*, not legal advice: playbook names
and review/approval routing are labels describing who should look at a
contract before it moves forward, not a determination of what the contract
should say. Nothing here scores risk or drafts language.

Reuses two things that already exist rather than introducing a new model:
- `ContractTemplate` (contracts/models.py) for "recommended template" — it
  was built for exactly this lookup (pre-approved starting drafts by type).
- `get_required_fields_for_contract_type` (contracts/services/
  contract_policies.py) for "required fields" — the same policy already
  enforced server-side in ContractForm.clean(), so the UI can never drift
  out of sync with what actually blocks contract creation.

`LAUNCH_SETUP_CONFIG` covers every `Contract.ContractType` value so no type
falls through to a broken/empty state; `OTHER` and the blank placeholder
value both explicitly resist recommending a template (see get_launch_setup
docstring) rather than guessing.
"""
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

from contracts.models import Contract, ContractTemplate
from contracts.services.contract_policies import get_required_fields_for_contract_type

# Matches the existing (pre-this-feature) "commercial approval" framing in
# contract_form.html's JS `monetaryReview` check — kept as the single named
# constant for the MSA-specific finance-threshold messaging this feature
# adds, rather than introducing a third, uncoordinated threshold number.
MSA_FINANCE_APPROVAL_THRESHOLD = 100_000

FIELD_LABELS = {
    'counterparty': 'Counterparty',
    'governing_law': 'Governing law',
    'jurisdiction': 'Jurisdiction',
    'start_date': 'Start date',
    'end_date': 'End date',
    'content': 'Content',
}

CommercialCounselCopy = {
    'playbook': 'Commercial playbook',
    'review_route': 'Commercial counsel review',
    'approval_route': 'Standard commercial approval — escalates for high risk or high value.',
}

DisputeCounselCopy = {
    'playbook': None,
    'review_route': 'Dispute counsel review',
    'approval_route': 'Settlement authority and release terms confirmed before signature.',
}

DEFAULT_COPY = {
    'playbook': None,
    'review_route': 'General legal review',
    'approval_route': 'Standard approval process.',
}

# Type-selection card metadata (draft-time estimate + who typically signs
# off) for the New Contract entry screen. Draft-time is an editorial
# estimate of a well-prepared intake, not a measured average — shown as
# "~N min" in the UI so it never reads as a hard guarantee. Approvals text
# is a plain-language summary of the same review_route/approval_route
# copy above, meant to be scannable on a card, not a new source of truth.
CARD_META = {
    Contract.ContractType.MSA: {'draft_minutes': 5, 'typical_approvals': 'Legal, Finance', 'icon': 'file'},
    Contract.ContractType.DPA: {'draft_minutes': 4, 'typical_approvals': 'Legal, DPO', 'icon': 'shield'},
    Contract.ContractType.NDA: {'draft_minutes': 2, 'typical_approvals': 'Legal optional', 'icon': 'document'},
    Contract.ContractType.SOW: {'draft_minutes': 6, 'typical_approvals': 'Legal, Finance', 'icon': 'list'},
    Contract.ContractType.VENDOR: {'draft_minutes': 7, 'typical_approvals': 'Legal, Procurement', 'icon': 'briefcase'},
    Contract.ContractType.AMENDMENT: {'draft_minutes': 3, 'typical_approvals': 'Legal', 'icon': 'edit'},
}
DEFAULT_CARD_META = {'draft_minutes': 5, 'typical_approvals': 'Legal', 'icon': 'file'}

# Cards shown on the New Contract entry screen, in display order — a
# curated subset (not all 19 ContractType values), matching the six
# highest-traffic types. "Other" and the rest stay reachable via the full
# dropdown on the resulting form, same as before this feature existed.
ENTRY_CARD_TYPES = [
    Contract.ContractType.MSA,
    Contract.ContractType.DPA,
    Contract.ContractType.NDA,
    Contract.ContractType.SOW,
    Contract.ContractType.VENDOR,
    Contract.ContractType.AMENDMENT,
]

# Shown in the "Selected setup" card's template/playbook rows in place of
# the two separate "no template" / "no playbook" lines whenever a type has
# no entry in LAUNCH_SETUP_CONFIG at all — i.e. genuinely not mapped yet,
# as opposed to OTHER/SETTLEMENT/AMENDMENT, which *are* mapped (they just
# deliberately have no template or no named playbook). One calm, positive
# statement reads as an intentional product decision, not missing config.
CUSTOM_DRAFTING_ROUTE_TITLE = 'Custom drafting route'
CUSTOM_DRAFTING_ROUTE_COPY = (
    'No approved template is mapped yet. DocClad will create a governed '
    'intake record and route it for legal review.'
)

# contract_type -> {playbook, review_route, approval_route}. Template
# recommendation is looked up separately from ContractTemplate, not stored
# here, so this config never goes stale relative to what templates actually
# exist.
LAUNCH_SETUP_CONFIG = {
    Contract.ContractType.NDA: {
        'playbook': 'Standard NDA playbook',
        'review_route': 'Legal review (light-touch)',
        'approval_route': 'Business approval is usually optional for low-risk NDA intake.',
    },
    Contract.ContractType.DPA: {
        'playbook': 'GDPR / DPA playbook',
        'review_route': 'Legal + Privacy review',
        'approval_route': 'Privacy approval confirms the data-transfer posture before signature.',
    },
    Contract.ContractType.MSA: {
        'playbook': 'Commercial playbook',
        'review_route': 'Legal review',
        'approval_route': (
            f'Legal review, plus finance approval if contract value is at or above '
            f'${MSA_FINANCE_APPROVAL_THRESHOLD:,.0f}.'
        ),
    },
    Contract.ContractType.SOW: CommercialCounselCopy,
    Contract.ContractType.SUBCONTRACTOR_SOW: CommercialCounselCopy,
    Contract.ContractType.VENDOR: {
        'playbook': 'Procurement / Commercial playbook',
        'review_route': 'Procurement + Legal review',
        'approval_route': 'Standard commercial approval — escalates for high risk or high value.',
    },
    Contract.ContractType.PURCHASE_ORDER: CommercialCounselCopy,
    Contract.ContractType.RESELLER: CommercialCounselCopy,
    Contract.ContractType.SAAS: {
        'playbook': 'SaaS / Data Security playbook',
        'review_route': 'Legal review, plus Security review when data processing is involved.',
        'approval_route': 'Standard commercial approval — escalates for high risk or high value.',
    },
    Contract.ContractType.SETTLEMENT: DisputeCounselCopy,
    Contract.ContractType.AMENDMENT: {
        'playbook': None,
        'review_route': 'Follows the original agreement’s review route — link the parent contract for full context.',
        'approval_route': 'Mirrors the approval path already used for the agreement being amended.',
    },
    Contract.ContractType.OTHER: {
        'playbook': None,
        'review_route': 'General counsel review — pick a more specific type above for tailored guidance.',
        'approval_route': 'Standard approval process.',
    },
}


@dataclass
class RecommendedTemplate:
    id: int
    name: str
    description: str


@dataclass
class ContractTypeLaunchSetup:
    contract_type: str
    contract_type_label: str
    template: Optional[RecommendedTemplate]
    playbook: Optional[str]
    review_route: str
    approval_route: str
    is_custom_drafting_route: bool = False
    required_fields: List[str] = field(default_factory=list)
    required_field_labels: List[str] = field(default_factory=list)


def _copy_for(contract_type: str) -> dict:
    return LAUNCH_SETUP_CONFIG.get(contract_type, DEFAULT_COPY)


def _is_custom_drafting_route(contract_type: str, template: Optional['RecommendedTemplate']) -> bool:
    """True only when there is genuinely nothing to recommend: no explicit
    workflow-metadata entry AND no approved template either. A type like
    CONSULTING has a seeded template but no bespoke playbook copy yet — that
    still shows its real template, just with generic review/approval
    framing, so it must NOT be flagged as a custom drafting route."""
    return contract_type not in LAUNCH_SETUP_CONFIG and template is None


def _recommended_template_for(contract_type: str) -> Optional[RecommendedTemplate]:
    """No template for OTHER, ever — see module docstring: don't guess."""
    if not contract_type or contract_type == Contract.ContractType.OTHER:
        return None
    template = (
        ContractTemplate.objects.filter(contract_type=contract_type, is_active=True)
        .order_by('name')
        .first()
    )
    if not template:
        return None
    return RecommendedTemplate(id=template.pk, name=template.name, description=template.description)


def get_launch_setup_for_type(contract_type: str) -> ContractTypeLaunchSetup:
    """Build the launch-setup card contents for one contract type."""
    copy = _copy_for(contract_type)
    required_fields = list(get_required_fields_for_contract_type(contract_type))
    label = dict(Contract.ContractType.choices).get(contract_type, contract_type)
    template = _recommended_template_for(contract_type)
    return ContractTypeLaunchSetup(
        contract_type=contract_type,
        contract_type_label=label,
        template=template,
        playbook=copy.get('playbook'),
        review_route=copy['review_route'],
        approval_route=copy['approval_route'],
        is_custom_drafting_route=_is_custom_drafting_route(contract_type, template),
        required_fields=required_fields,
        required_field_labels=[FIELD_LABELS.get(f, f.replace('_', ' ').capitalize()) for f in required_fields],
    )


def get_launch_setup_map() -> Dict[str, dict]:
    """Every contract type's launch setup, JSON-serializable, for the New
    Contract Request page to dump once via `json_script` and read client-side
    on every `contract_type` change — no per-keystroke request needed."""
    return {
        contract_type: asdict(get_launch_setup_for_type(contract_type))
        for contract_type, _ in Contract.ContractType.choices
    }


CARD_DESCRIPTIONS = {
    Contract.ContractType.MSA: 'Create a governed commercial agreement for long-term services.',
    Contract.ContractType.DPA: 'Generate processor terms with privacy, SCC, and subprocessor checks.',
    Contract.ContractType.NDA: 'Create mutual or one-way confidentiality agreements from approved language.',
    Contract.ContractType.SOW: 'Draft scope, deliverables, milestones, pricing, and acceptance terms.',
    Contract.ContractType.VENDOR: 'Generate supplier terms with liability, renewal, and compliance controls.',
    Contract.ContractType.AMENDMENT: 'Amend an existing agreement with controlled clause changes.',
}

CARD_TITLES = {
    Contract.ContractType.MSA: 'MSA',
    Contract.ContractType.DPA: 'DPA',
    Contract.ContractType.NDA: 'NDA',
    Contract.ContractType.SOW: 'SOW',
    Contract.ContractType.VENDOR: 'Supplier Agreement',
    Contract.ContractType.AMENDMENT: 'Addendum',
}


@dataclass
class ContractTypeEntryCard:
    contract_type: str
    title: str
    description: str
    icon: str
    template_name: Optional[str]
    draft_minutes: int
    typical_approvals: str
    start_url: str


def get_entry_cards(start_url_for=None) -> List[ContractTypeEntryCard]:
    """The New Contract entry screen's type cards, in display order.

    `start_url_for(contract_type)` builds the "Start draft" href for a card
    — injected rather than reversed here so this stays a plain service
    function with no `django.urls` dependency. Falls back to a bare query
    string if the caller doesn't supply one (e.g. for tests).
    """
    cards = []
    for contract_type in ENTRY_CARD_TYPES:
        setup = get_launch_setup_for_type(contract_type)
        meta = CARD_META.get(contract_type, DEFAULT_CARD_META)
        href = start_url_for(contract_type) if start_url_for else f'?type={contract_type}'
        cards.append(ContractTypeEntryCard(
            contract_type=contract_type,
            title=CARD_TITLES.get(contract_type, setup.contract_type_label),
            description=CARD_DESCRIPTIONS.get(contract_type, ''),
            icon=meta['icon'],
            template_name=setup.template.name if setup.template else None,
            draft_minutes=meta['draft_minutes'],
            typical_approvals=meta['typical_approvals'],
            start_url=href,
        ))
    return cards
