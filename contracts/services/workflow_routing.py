from datetime import timedelta
from decimal import Decimal

from django.db import models
from django.db.models import Case, IntegerField, Value, When
from django.utils import timezone

from contracts.models import ApprovalRequest, ApprovalRule, Contract, OrganizationMembership, UserProfile, WorkflowTemplate


EU_JURISDICTION_KEYWORDS = {
    'EU',
    'EEA',
    'EUROPEAN UNION',
    'UK',
    'UNITED KINGDOM',
    'GERMANY',
    'FRANCE',
    'NETHERLANDS',
    'IRELAND',
    'BELGIUM',
    'SPAIN',
    'ITALY',
    'SWEDEN',
    'DENMARK',
    'FINLAND',
    'AUSTRIA',
}

from contracts.services.finance_approval_policy import get_finance_approval_threshold

# Workflow category routing uses the same high-value threshold as Finance approval.
def _high_value_threshold(organization=None):
    return get_finance_approval_threshold(organization)


HIGH_VALUE_THRESHOLD = int(get_finance_approval_threshold())
HIGH_RISK_TYPES = {
    Contract.ContractType.EMPLOYMENT,
    Contract.ContractType.LEASE,
    Contract.ContractType.LICENSE,
    Contract.ContractType.PARTNERSHIP,
    Contract.ContractType.SETTLEMENT,
    Contract.ContractType.VENDOR,
}


def _normalized_text(value):
    return (value or '').strip().upper()


def _template_queryset_for_contract(contract, *, category):
    if not contract:
        return WorkflowTemplate.objects.filter(
            is_active=True,
            category=category,
            organization__isnull=True,
        )

    return WorkflowTemplate.objects.filter(
        is_active=True,
        category=category,
    ).filter(
        models.Q(organization=contract.organization) | models.Q(organization__isnull=True)
    ).annotate(
        organization_sort=Case(
            When(organization__isnull=True, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        )
    ).order_by('organization_sort', '-version', '-created_at', '-pk')


def suggest_workflow_category_for_contract(contract):
    if not contract:
        return WorkflowTemplate.Category.GENERAL

    jurisdiction_text = ' '.join(
        part for part in [
            _normalized_text(contract.jurisdiction),
            _normalized_text(contract.governing_law),
        ] if part
    )
    if contract.data_transfer_flag or any(keyword in jurisdiction_text for keyword in EU_JURISDICTION_KEYWORDS):
        return WorkflowTemplate.Category.COMPLIANCE

    if contract.contract_type in HIGH_RISK_TYPES:
        return WorkflowTemplate.Category.DUE_DILIGENCE

    if contract.value and contract.value >= _high_value_threshold(getattr(contract, 'organization', None)):
        return WorkflowTemplate.Category.DUE_DILIGENCE

    return WorkflowTemplate.Category.CONTRACT_REVIEW


def suggest_workflow_template_for_contract(contract):
    from contracts.services.workflow_designer import template_launch_block_reason

    category = suggest_workflow_category_for_contract(contract)
    candidates = list(_template_queryset_for_contract(contract, category=category)[:12])
    if category != WorkflowTemplate.Category.GENERAL:
        candidates.extend(
            list(_template_queryset_for_contract(contract, category=WorkflowTemplate.Category.GENERAL)[:6])
        )

    seen = set()
    for template in candidates:
        if template.pk in seen:
            continue
        seen.add(template.pk)
        if template_launch_block_reason(template):
            continue
        return template
    return None


def _keyword_matches(value, keywords):
    normalized_value = _normalized_text(value)
    return any(keyword in normalized_value for keyword in keywords)


def _parse_decimal_trigger_value(raw_value):
    normalized = (raw_value or '').strip().replace(',', '')
    normalized = normalized.lstrip('$€£')
    if not normalized:
        raise ValueError('empty trigger value')
    return Decimal(normalized)


def _rule_matches_contract(rule, contract):
    if not rule or not contract:
        return False

    trigger_value = _normalized_text(rule.trigger_value)
    if rule.trigger_type == ApprovalRule.TriggerType.CONTRACT_TYPE:
        return contract.contract_type == trigger_value
    if rule.trigger_type == ApprovalRule.TriggerType.JURISDICTION:
        return _keyword_matches(contract.jurisdiction, {trigger_value}) or _keyword_matches(contract.governing_law, {trigger_value})
    if rule.trigger_type == ApprovalRule.TriggerType.VALUE_ABOVE:
        try:
            return contract.value is not None and contract.value >= _parse_decimal_trigger_value(trigger_value)
        except (TypeError, ValueError):
            return False
    if rule.trigger_type == ApprovalRule.TriggerType.RISK_LEVEL:
        return _normalized_text(contract.risk_level) == trigger_value
    if rule.trigger_type == ApprovalRule.TriggerType.DATA_TRANSFER:
        return contract.data_transfer_flag
    return False


def select_approval_rules_for_contract(contract):
    if not contract or not contract.organization_id:
        return ApprovalRule.objects.none()
    return ApprovalRule.objects.filter(
        organization=contract.organization,
        is_active=True,
    ).select_related('specific_approver').order_by('order', 'sla_hours', 'id')


def resolve_rule_assignee(rule, contract):
    # Legacy resolution by default; optional canonical authority when authorized flag is on.
    if rule.specific_approver_id:
        legacy_user = rule.specific_approver
    elif not contract or not contract.organization_id:
        legacy_user = None
    else:
        legacy_user = None
        matching_profiles = {rule.approver_role}
        memberships = (
            OrganizationMembership.objects
            .filter(organization=contract.organization, is_active=True)
            .select_related('user')
            .prefetch_related('user__profile')
        )
        for membership in memberships:
            profile_role = getattr(getattr(membership.user, 'profile', None), 'role', None)
            if profile_role in matching_profiles:
                legacy_user = membership.user
                break
    try:
        from contracts.services.process_role_resolver_parity import after_resolve_rule_assignee
        from contracts.services.process_role_resolver_authority import (
            after_resolve_rule_assignee as apply_authority_after_resolve_rule_assignee,
        )

        # Parity is diagnostic-only (always returns legacy). Authority may
        # replace the return value when separately authorized and enabled.
        compared = after_resolve_rule_assignee(legacy_user=legacy_user, rule=rule, contract=contract)
        return apply_authority_after_resolve_rule_assignee(
            legacy_user=compared, rule=rule, contract=contract,
        )
    except Exception:
        return legacy_user


def build_approval_request_plan_for_contract(contract):
    if not contract:
        return []

    matching_rules = [
        rule for rule in select_approval_rules_for_contract(contract)
        if _rule_matches_contract(rule, contract)
    ]
    if not matching_rules:
        return []

    now = timezone.now()
    plan = []
    for rule in matching_rules:
        plan.append({
            'organization': contract.organization,
            'contract': contract,
            'rule': rule,
            'approval_step': rule.approval_step,
            'assigned_to': resolve_rule_assignee(rule, contract),
            'due_date': now + timedelta(hours=rule.sla_hours),
            'status': ApprovalRequest.Status.PENDING,
        })
    return plan
