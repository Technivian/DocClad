"""Enterprise admin console service — org settings, policy, integrations, audit."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from contracts.models import (
    AuditLog,
    Organization,
    OrganizationAPIToken,
    OrganizationMembership,
    OrgPolicy,
    SalesforceOrganizationConnection,
    WebhookEndpoint,
)


@dataclass
class OrgSettings:
    org_id: int
    name: str
    slug: str
    member_count: int
    token_count: int
    policy: dict


@dataclass
class IntegrationStatus:
    name: str
    enabled: bool
    details: dict


class AdminConsoleService:
    def get_settings(self, org: Organization) -> OrgSettings:
        policy, _ = OrgPolicy.objects.get_or_create(organization=org)
        member_count = OrganizationMembership.objects.filter(organization=org).count()
        token_count = OrganizationAPIToken.objects.filter(organization=org).count()
        return OrgSettings(
            org_id=org.pk,
            name=org.name,
            slug=org.slug,
            member_count=member_count,
            token_count=token_count,
            policy=_policy_to_dict(policy),
        )

    def update_policy(self, org: Organization, user, **kwargs) -> OrgPolicy:
        policy, _ = OrgPolicy.objects.get_or_create(organization=org)
        allowed_fields = {
            'mfa_required', 'require_approval_above_value',
            'data_transfer_review_required', 'retention_period_days',
            'max_api_tokens_per_user', 'allow_public_sharing', 'ai_features_enabled',
        }
        for field, value in kwargs.items():
            if field in allowed_fields:
                setattr(policy, field, value)
        policy.updated_by = user
        policy.save()
        return policy

    def list_integrations(self, org: Organization) -> list[IntegrationStatus]:
        integrations = []

        sf = SalesforceOrganizationConnection.objects.filter(organization=org).first()
        integrations.append(IntegrationStatus(
            name='salesforce',
            enabled=sf is not None and getattr(sf, 'is_active', False),
            details={'instance_url': sf.instance_url if sf else None},
        ))

        webhook_count = WebhookEndpoint.objects.filter(organization=org).count()
        integrations.append(IntegrationStatus(
            name='webhooks',
            enabled=webhook_count > 0,
            details={'endpoint_count': webhook_count},
        ))

        scim_provisioned = OrganizationMembership.objects.filter(
            organization=org
        ).exclude(scim_external_id='').count()
        integrations.append(IntegrationStatus(
            name='scim',
            enabled=scim_provisioned > 0,
            details={'provisioned_members': scim_provisioned},
        ))

        return integrations

    def get_audit_summary(self, org: Organization, limit: int = 50) -> list[dict]:
        # AuditLog is not directly org-scoped; filter by org members
        member_ids = list(
            OrganizationMembership.objects.filter(organization=org).values_list('user_id', flat=True)
        )
        logs = AuditLog.objects.filter(user_id__in=member_ids).order_by('-timestamp')[:limit]
        return [
            {
                'id': log.pk,
                'action': log.action,
                'actor': log.user.username if log.user else None,
                'model_name': log.model_name,
                'object_repr': log.object_repr,
                'timestamp': log.timestamp.isoformat(),
            }
            for log in logs
        ]


def _policy_to_dict(policy: OrgPolicy) -> dict:
    return {
        'mfa_required': policy.mfa_required,
        'require_approval_above_value': (
            float(policy.require_approval_above_value)
            if policy.require_approval_above_value is not None else None
        ),
        'data_transfer_review_required': policy.data_transfer_review_required,
        'retention_period_days': policy.retention_period_days,
        'max_api_tokens_per_user': policy.max_api_tokens_per_user,
        'allow_public_sharing': policy.allow_public_sharing,
        'ai_features_enabled': policy.ai_features_enabled,
        'updated_at': policy.updated_at.isoformat() if policy.updated_at else None,
    }


def get_admin_console_service() -> AdminConsoleService:
    return AdminConsoleService()
