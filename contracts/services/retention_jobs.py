"""Retention job service for privacy ops."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from contracts.models import Contract, RetentionPolicy, RetentionActionLog

_RetentionActionLogDoesNotExist = RetentionActionLog.DoesNotExist


@dataclass
class RetentionItem:
    contract_id: int
    contract_title: str
    created_at: date
    days_overdue: int
    policy_id: int
    policy_title: str
    auto_delete: bool


class RetentionService:
    def get_overdue_contracts(self, org) -> list[RetentionItem]:
        today = date.today()
        items: list[RetentionItem] = []

        policies = RetentionPolicy.objects.filter(organization=org, category='CONTRACTS', is_active=True)
        for policy in policies:
            contracts = Contract.objects.filter(organization=org)
            for contract in contracts:
                contract_date = contract.created_at.date() if contract.created_at else None
                if contract_date is None:
                    continue
                age_days = (today - contract_date).days
                if age_days > policy.retention_period_days:
                    items.append(RetentionItem(
                        contract_id=contract.id,
                        contract_title=contract.title,
                        created_at=contract_date,
                        days_overdue=age_days - policy.retention_period_days,
                        policy_id=policy.id,
                        policy_title=policy.title,
                        auto_delete=policy.auto_delete,
                    ))

        return items

    def log_retention_action(
        self,
        org,
        contract_id: int,
        action: str,
        performed_by,
        notes: str = '',
    ) -> RetentionActionLog:
        contract = None
        try:
            contract = Contract.objects.get(pk=contract_id, organization=org)
        except Contract.DoesNotExist:
            pass

        return RetentionActionLog.objects.create(
            organization=org,
            contract=contract,
            action=action,
            performed_by=performed_by,
            notes=notes,
        )

    def get_retention_log(self, org, limit: int = 50) -> list[dict]:
        logs = RetentionActionLog.objects.filter(organization=org)[:limit]
        return [
            {
                'id': log.id,
                'contract_id': log.contract_id,
                'action': log.action,
                'performed_by': log.performed_by_id,
                'notes': log.notes,
                'created_at': log.created_at.isoformat(),
            }
            for log in logs
        ]


def get_retention_service() -> RetentionService:
    return RetentionService()
