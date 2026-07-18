"""Explainable reviewer and approver routing for the existing draft intake."""
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Mapping

from contracts.models import Contract
from contracts.services.contract_launch_setup import MSA_FINANCE_APPROVAL_THRESHOLD, get_launch_setup_for_type
from contracts.services.intake_risk import STANDARD_LAW_TERMS


def _standard_posture(value: object) -> bool:
    text = str(value or '').casefold()
    return any(term in text for term in STANDARD_LAW_TERMS)


@dataclass(frozen=True)
class IntakeRouteDecision:
    template_status: str
    comparison_baseline: str
    playbook: str
    review_mode: str
    reviewers: tuple[dict, ...]
    approvers: tuple[dict, ...]

    def as_dict(self) -> dict:
        result = asdict(self)
        result['reviewers'] = list(self.reviewers)
        result['approvers'] = list(self.approvers)
        return result


def derive_intake_route(values: Mapping[str, object], *, template_applied: bool = False) -> IntakeRouteDecision:
    contract_type = str(values.get('contract_type') or '')
    setup = get_launch_setup_for_type(contract_type) if contract_type else None
    baseline = setup.template.name if setup and setup.template else 'No approved template available'
    playbook = setup.playbook if setup and setup.playbook else 'No approved playbook matched'
    third_party_paper = values.get('paper_source') == Contract.PaperSource.COUNTERPARTY_PAPER
    reviewers: list[dict] = []
    approvers: list[dict] = []

    def add_reviewer(role: str, reason: str):
        if not any(item['role'] == role for item in reviewers):
            reviewers.append({'role': role, 'reason': reason})

    if not contract_type:
        add_reviewer('Legal', 'Legal review will be determined after a contract type is selected.')
    elif third_party_paper:
        add_reviewer('Legal', 'Legal added because the counterparty supplied the paper.')
    if values.get('governing_law') and not _standard_posture(values.get('governing_law')):
        add_reviewer('Legal', f"Legal added because governing law is non-standard: {values.get('governing_law')}.")
    if values.get('jurisdiction') and not _standard_posture(values.get('jurisdiction')):
        add_reviewer('Legal', f"Legal added because jurisdiction is non-standard: {values.get('jurisdiction')}.")
    if not setup or not setup.playbook:
        add_reviewer('Legal', 'Full legal review required because no approved playbook matched.')
    if not reviewers and contract_type:
        add_reviewer('Legal', setup.review_route if setup else 'Standard legal review is required for this contract type.')

    personal_data_without_dpa = values.get('personal_data_processing') and not values.get('dpa_attached')
    privacy_reason = None
    if personal_data_without_dpa:
        privacy_reason = 'Privacy added because personal data is processed without an approved DPA.'
    elif values.get('sensitive_data_flag'):
        privacy_reason = 'Privacy added because sensitive, high-volume, or non-standard data is involved.'
    elif values.get('counterparty_privacy_review_required'):
        privacy_reason = 'Privacy added because the counterparty requires privacy review.'
    elif values.get('data_transfer_flag') and not values.get('scc_attached'):
        privacy_reason = 'Privacy added because personal data leaves the EEA without confirmed approved safeguards.'
    if privacy_reason:
        add_reviewer('Privacy', privacy_reason)

    value = Decimal(str(values.get('value') or 0))
    if value >= Decimal(str(MSA_FINANCE_APPROVAL_THRESHOLD)):
        approvers.append({
            'role': 'Finance Director',
            'reason': f'Finance Director added because contract value meets the ${MSA_FINANCE_APPROVAL_THRESHOLD:,.0f} approval threshold.',
        })
    if contract_type:
        approvers.append({
            'role': 'Business Owner',
            'reason': 'Business Owner added because every draft requires the configured business approval before signature.',
        })
    if setup and contract_type == Contract.ContractType.DPA and privacy_reason:
        approvers.append({'role': 'Privacy Officer', 'reason': 'Privacy Officer added because the DPA requires privacy escalation.'})

    return IntakeRouteDecision(
        template_status=(
            'Not applicable' if third_party_paper else 'Applied' if template_applied else 'Not applied'
        ),
        comparison_baseline=baseline,
        playbook=playbook,
        review_mode='Deviation review' if third_party_paper else 'Standard review',
        reviewers=tuple(reviewers),
        approvers=tuple(approvers),
    )


def intake_routing_client_policy() -> dict:
    return {'finance_approval_threshold': str(MSA_FINANCE_APPROVAL_THRESHOLD)}
