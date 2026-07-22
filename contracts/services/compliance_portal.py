"""Compliance portal service — exportable trust report and compliance bundle."""
from __future__ import annotations

from dataclasses import dataclass, field

from django.utils import timezone

from contracts.models import (
    AuditLog,
    Contract,
    DSARRequest,
    Organization,
    OrganizationMembership,
    OrgPolicy,
)


@dataclass
class TrustReport:
    org_id: int
    org_name: str
    generated_at: str
    policy_summary: dict
    dsar_stats: dict
    retention_config: dict
    ai_governance: dict
    audit_counts: dict
    contract_stats: dict


class CompliancePortalService:
    def generate_trust_report(self, org: Organization) -> TrustReport:
        policy = self._get_policy(org)
        dsar_stats = self._dsar_stats(org)
        audit_counts = self._audit_counts(org)
        contract_stats = self._contract_stats(org)

        return TrustReport(
            org_id=org.pk,
            org_name=org.name,
            generated_at=timezone.now().isoformat(),
            policy_summary={
                'mfa_required': policy.mfa_required,
                'data_transfer_review_required': policy.data_transfer_review_required,
                'ai_features_enabled': policy.ai_features_enabled,
                'allow_public_sharing': policy.allow_public_sharing,
            },
            dsar_stats=dsar_stats,
            retention_config={
                'retention_period_days': policy.retention_period_days,
                'retention_period_years': round(policy.retention_period_days / 365, 1),
            },
            ai_governance={
                'ai_features_enabled': policy.ai_features_enabled,
                'extraction_model': 'deterministic-rule-based',
                'drafting_model': 'deterministic-template-library',
                'audit_trail': True,
            },
            audit_counts=audit_counts,
            contract_stats=contract_stats,
        )

    def export_compliance_bundle(self, org: Organization) -> dict:
        report = self.generate_trust_report(org)
        member_count = OrganizationMembership.objects.filter(organization=org).count()
        return {
            'export_version': '1.0',
            'generated_at': report.generated_at,
            'organization': {'id': report.org_id, 'name': report.org_name},
            'policy_summary': report.policy_summary,
            'dsar_stats': report.dsar_stats,
            'retention_config': report.retention_config,
            'ai_governance': report.ai_governance,
            'audit_counts': report.audit_counts,
            'contract_stats': report.contract_stats,
            'member_count': member_count,
        }

    def _get_policy(self, org: Organization) -> OrgPolicy:
        policy, _ = OrgPolicy.objects.get_or_create(organization=org)
        return policy

    def _dsar_stats(self, org: Organization) -> dict:
        qs = DSARRequest.objects.filter(organization=org)
        total = qs.count()
        completed = qs.filter(status='COMPLETED').count()
        denied = qs.filter(status='DENIED').count()
        pending = qs.exclude(status__in=['COMPLETED', 'DENIED']).count()
        overdue = sum(1 for r in qs.exclude(status__in=['COMPLETED', 'DENIED']) if r.is_overdue)
        return {
            'total': total,
            'completed': completed,
            'denied': denied,
            'pending': pending,
            'overdue': overdue,
            'completion_rate_pct': round(completed / total * 100, 1) if total else 0,
        }

    def _audit_counts(self, org: Organization) -> dict:
        member_ids = list(
            OrganizationMembership.objects.filter(organization=org).values_list('user_id', flat=True)
        )
        total = AuditLog.objects.filter(user_id__in=member_ids).count()
        by_action = {}
        for action in ['CREATE', 'UPDATE', 'DELETE', 'VIEW', 'EXPORT', 'APPROVE']:
            by_action[action.lower()] = AuditLog.objects.filter(
                user_id__in=member_ids, action=action
            ).count()
        return {'total': total, 'by_action': by_action}

    def _contract_stats(self, org: Organization) -> dict:
        qs = Contract.objects.filter(organization=org)
        total = qs.count()
        # PDR-0002 record statuses only (no Draft/APPROVED as record status).
        by_status = {}
        for status in [
            'IN_PROGRESS',
            'ACTIVE',
            'EXPIRED',
            'TERMINATED',
            'CANCELLED',
            'ARCHIVED',
        ]:
            by_status[status.lower()] = qs.filter(status=status).count()
        data_transfer = qs.filter(data_transfer_flag=True).count()
        dpa_attached = qs.filter(dpa_attached=True).count()
        return {
            'total': total,
            'by_status': by_status,
            'data_transfer_contracts': data_transfer,
            'dpa_attached': dpa_attached,
        }


def get_compliance_portal_service() -> CompliancePortalService:
    return CompliancePortalService()
