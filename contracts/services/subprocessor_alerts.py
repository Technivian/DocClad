"""Subprocessor alert service for privacy ops."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from contracts.models import Subprocessor, TransferRecord

_SubprocessorDoesNotExist = Subprocessor.DoesNotExist
_TransferRecordDoesNotExist = TransferRecord.DoesNotExist

EU_COUNTRIES = {
    'AT', 'BE', 'BG', 'CY', 'CZ', 'DE', 'DK', 'EE', 'ES', 'FI', 'FR',
    'GR', 'HR', 'HU', 'IE', 'IT', 'LT', 'LU', 'LV', 'MT', 'NL', 'PL',
    'PT', 'RO', 'SE', 'SI', 'SK',
}


@dataclass
class SubprocessorAlert:
    subprocessor_id: int
    subprocessor_name: str
    country: str
    alert_type: str
    severity: str
    description: str


@dataclass
class TransferRiskFlag:
    transfer_id: int
    title: str
    flag_type: str
    description: str


class SubprocessorAlertService:
    def get_alerts(self, org) -> list[SubprocessorAlert]:
        today = date.today()
        audit_threshold = today - timedelta(days=365)
        alerts: list[SubprocessorAlert] = []

        subprocessors = Subprocessor.objects.filter(organization=org, is_active=True)
        for sp in subprocessors:
            # Expired DPA
            if sp.dpa_in_place and sp.contract_end_date and sp.contract_end_date < today:
                alerts.append(SubprocessorAlert(
                    subprocessor_id=sp.id,
                    subprocessor_name=sp.name,
                    country=sp.country,
                    alert_type='EXPIRED_DPA',
                    severity='HIGH',
                    description=f'DPA expired on {sp.contract_end_date}',
                ))

            # Missing DPA
            if not sp.dpa_in_place:
                severity = 'HIGH' if (sp.risk_level == 'HIGH' or not sp.is_eu_based) else 'MEDIUM'
                alerts.append(SubprocessorAlert(
                    subprocessor_id=sp.id,
                    subprocessor_name=sp.name,
                    country=sp.country,
                    alert_type='MISSING_DPA',
                    severity=severity,
                    description='No DPA in place for this subprocessor',
                ))

            # Overdue audit
            if sp.last_audit_date and sp.last_audit_date < audit_threshold:
                alerts.append(SubprocessorAlert(
                    subprocessor_id=sp.id,
                    subprocessor_name=sp.name,
                    country=sp.country,
                    alert_type='OVERDUE_AUDIT',
                    severity='MEDIUM',
                    description=f'Last audit was on {sp.last_audit_date}, over 365 days ago',
                ))

            # Missing transfer mechanism for non-EU
            if not sp.is_eu_based and not sp.scc_in_place and not sp.dpf_certified:
                alerts.append(SubprocessorAlert(
                    subprocessor_id=sp.id,
                    subprocessor_name=sp.name,
                    country=sp.country,
                    alert_type='MISSING_TRANSFER_MECHANISM',
                    severity='HIGH',
                    description='Non-EU subprocessor lacks SCC or DPF certification',
                ))

        return alerts

    def get_transfer_risk_flags(self, org) -> list[TransferRiskFlag]:
        today = date.today()
        flags: list[TransferRiskFlag] = []

        transfers = TransferRecord.objects.filter(organization=org, is_active=True)
        for tr in transfers:
            if tr.review_date and tr.review_date < today:
                flags.append(TransferRiskFlag(
                    transfer_id=tr.id,
                    title=tr.title,
                    flag_type='EXPIRED_REVIEW',
                    description=f'Transfer review date {tr.review_date} has passed',
                ))

            if not tr.tia_completed:
                flags.append(TransferRiskFlag(
                    transfer_id=tr.id,
                    title=tr.title,
                    flag_type='MISSING_TIA',
                    description='Transfer Impact Assessment not completed',
                ))

        return flags


def get_subprocessor_alert_service() -> SubprocessorAlertService:
    return SubprocessorAlertService()
