"""Deterministic, explainable risk assessment for a new contract intake.

This is deliberately an *initial* assessment: it does not claim to be a
legal review and it never upgrades a draft to a reviewed result.  The same
policy is serialized to the request page so its live route preview and the
server-side save use the same inputs and thresholds.
"""
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from typing import Mapping, Optional

from contracts.models import Contract
from contracts.services.contract_launch_setup import get_launch_setup_for_type


RISK_INPUT_FIELDS = (
    'contract_type', 'governing_law', 'jurisdiction', 'start_date', 'end_date',
    'paper_source',
)
HIGH_VALUE_THRESHOLD = Decimal('100000')
HIGH_VALUE_CRITICAL_THRESHOLD = Decimal('500000')
LONG_DURATION_DAYS = 365 * 3
STANDARD_LAW_TERMS = ('delaware', 'new york', 'england', 'wales')
ELEVATED_BASE_TYPES = {
    Contract.ContractType.DPA,
    Contract.ContractType.MSA,
    Contract.ContractType.SAAS,
    Contract.ContractType.VENDOR,
}


@dataclass(frozen=True)
class IntakeRiskAssessment:
    state: str
    level: Optional[str]
    label: str
    reasons: tuple[str, ...]
    blocking_fields: tuple[str, ...]
    review_route: str
    approval_route: str
    template_applied: bool
    playbook_applied: bool
    playbook_name: Optional[str]

    @property
    def is_assessed(self) -> bool:
        return self.state == 'PRELIMINARY'

    def as_dict(self) -> dict:
        result = asdict(self)
        result['reasons'] = list(self.reasons)
        result['blocking_fields'] = list(self.blocking_fields)
        return result


def _has_standard_legal_posture(value: object) -> bool:
    text = str(value or '').casefold()
    return any(term in text for term in STANDARD_LAW_TERMS)


def _duration_days(start_date: object, end_date: object) -> Optional[int]:
    if isinstance(start_date, date) and isinstance(end_date, date):
        return (end_date - start_date).days
    return None


def assess_intake_risk(
    values: Mapping[str, object],
    *,
    template_applied: bool = False,
) -> IntakeRiskAssessment:
    """Return the only risk state a new request is allowed to claim.

    Missing risk inputs result in ``Not assessed`` rather than a misleading
    low result.  Once those inputs are present, this returns a preliminary
    score; reviewed and overridden states belong to the governed review path,
    not the intake form.
    """
    missing = tuple(name for name in RISK_INPUT_FIELDS if not values.get(name))
    contract_type = str(values.get('contract_type') or '')
    setup = get_launch_setup_for_type(contract_type) if contract_type else None
    review_route = setup.review_route if setup else 'Select a contract type to determine review routing.'
    approval_route = setup.approval_route if setup else 'Select a contract type to determine approval routing.'
    playbook_applied = bool(setup and setup.playbook)

    if missing:
        return IntakeRiskAssessment(
            state='NOT_ASSESSED',
            level=None,
            label='Risk not assessed',
            reasons=('Complete the risk inputs before relying on a preliminary risk result.',),
            blocking_fields=missing,
            review_route=review_route,
            approval_route=approval_route,
            template_applied=template_applied,
            playbook_applied=playbook_applied,
            playbook_name=setup.playbook if setup else None,
        )

    score = 0
    reasons: list[str] = []
    value = values.get('value')
    if value not in (None, ''):
        value_decimal = Decimal(str(value))
        if value_decimal >= HIGH_VALUE_CRITICAL_THRESHOLD:
            score += 5
            reasons.append('Contract value is at least $500,000.')
        elif value_decimal >= HIGH_VALUE_THRESHOLD:
            score += 4
            reasons.append('Contract value is at least $100,000.')
    if contract_type in ELEVATED_BASE_TYPES:
        score += 1
        reasons.append('Contract type has an elevated review baseline.')
    if not _has_standard_legal_posture(values.get('governing_law')):
        score += 1
        reasons.append('Governing law is outside the standard intake posture.')
    if not _has_standard_legal_posture(values.get('jurisdiction')):
        score += 1
        reasons.append('Jurisdiction is outside the standard intake posture.')
    if values.get('data_transfer_flag'):
        score += 2
        reasons.append('Cross-border personal-data transfer is involved.')
    elif values.get('personal_data_processing') and not values.get('dpa_attached'):
        score += 2
        reasons.append('Personal-data processing has no approved DPA.')
    elif values.get('personal_data_processing'):
        reasons.append('Personal-data processing is covered by an approved DPA.')
    if values.get('sensitive_data_flag'):
        score += 2
        reasons.append('Sensitive, high-volume, or non-standard data is involved.')
    if values.get('counterparty_privacy_review_required'):
        score += 2
        reasons.append('The counterparty requires privacy review.')
    if (_duration_days(values.get('start_date'), values.get('end_date')) or 0) > LONG_DURATION_DAYS:
        score += 1
        reasons.append('Contract duration exceeds three years.')
    if values.get('auto_renew'):
        score += 1
        reasons.append('Contract renews automatically.')
    if values.get('paper_source') == Contract.PaperSource.COUNTERPARTY_PAPER:
        score += 2
        reasons.append('Counterparty paper needs non-standard terms review.')
    if not template_applied:
        score += 1
        reasons.append('No approved starting template is applied.')
    if not playbook_applied:
        score += 1
        reasons.append('No matching review playbook is available.')

    if score >= 4:
        level = Contract.RiskLevel.HIGH
    elif score >= 2:
        level = Contract.RiskLevel.MEDIUM
    else:
        level = Contract.RiskLevel.LOW
    return IntakeRiskAssessment(
        state='PRELIMINARY',
        level=level,
        label=f'Preliminary {dict(Contract.RiskLevel.choices)[level]} risk',
        reasons=tuple(reasons) or ('No elevated intake signals were identified.',),
        blocking_fields=(),
        review_route=review_route,
        approval_route=approval_route,
        template_applied=template_applied,
        playbook_applied=playbook_applied,
        playbook_name=setup.playbook if setup else None,
    )


def intake_risk_client_policy() -> dict:
    """Small JSON-safe policy used by the existing live route preview."""
    return {
        'risk_input_fields': list(RISK_INPUT_FIELDS),
        'high_value_threshold': str(HIGH_VALUE_THRESHOLD),
        'critical_value_threshold': str(HIGH_VALUE_CRITICAL_THRESHOLD),
        'long_duration_days': LONG_DURATION_DAYS,
        'standard_law_terms': list(STANDARD_LAW_TERMS),
        'elevated_base_types': sorted(ELEVATED_BASE_TYPES),
    }
