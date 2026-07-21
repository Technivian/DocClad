"""Single source of truth for Finance approval threshold routing.

See docs/governance/decisions/pdr/0001-finance-approval-threshold.md for product authority.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Optional, Tuple

from django.conf import settings

# Approved pilot threshold (USD-equivalent contract value).
DEFAULT_FINANCE_APPROVAL_THRESHOLD = Decimal('100000')
FINANCE_APPROVER_STEP = 'FINANCE'
FINANCE_APPROVER_ROLE_LABEL = 'Finance Director'


def get_finance_approval_threshold(organization=None) -> Decimal:
    """Return the Finance approval threshold for ``organization``.

    Pilot rule: globally fixed at $100,000 unless a future org policy layer
    explicitly overrides this helper. ``organization`` is accepted now so call
    sites remain stable when configurability lands.
    """
    del organization  # reserved for future org-scoped policy
    override = getattr(settings, 'FINANCE_APPROVAL_THRESHOLD', None)
    if override is not None:
        return Decimal(str(override))
    return DEFAULT_FINANCE_APPROVAL_THRESHOLD


def _coerce_decimal(value: Any) -> Optional[Decimal]:
    if value is None or value == '':
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def parse_contract_value(value: Any) -> Optional[Decimal]:
    """Normalize intake / workflow values for threshold comparison."""
    return _coerce_decimal(value)


def requires_finance_approval(
    *,
    value: Any = None,
    currency: str = 'USD',
    confirmed_above_threshold: bool = False,
    organization=None,
    recurring_value: Any = None,
    total_contract_value: Any = None,
) -> Tuple[bool, str, dict]:
    """Decide whether Finance approval is required by the value threshold.

    Returns ``(required, reason, audit_context)``. Other approval rules (for
    example non-standard payment terms) may still require Finance independently.
    """
    threshold = get_finance_approval_threshold(organization)
    audit_context = {
        'finance_approval_threshold': str(threshold),
        'finance_approval_currency_basis': currency or 'USD',
        'finance_approver_step': FINANCE_APPROVER_STEP,
        'finance_approver_role': FINANCE_APPROVER_ROLE_LABEL,
    }

    if confirmed_above_threshold:
        audit_context['finance_routing_reason'] = 'operator_confirmed_above_threshold'
        return (
            True,
            f'Finance approval required because contract value was confirmed above the '
            f'${threshold:,.0f} threshold.',
            audit_context,
        )

    # Prefer explicit total contract value, then recurring, then headline value.
    effective_value = (
        parse_contract_value(total_contract_value)
        or parse_contract_value(recurring_value)
        or parse_contract_value(value)
    )

    if effective_value is None:
        audit_context['finance_routing_reason'] = 'value_unknown'
        return (
            False,
            f'Contract value is unknown; Finance approval is not triggered by the '
            f'${threshold:,.0f} value threshold.',
            audit_context,
        )

    audit_context['finance_value_compared'] = str(effective_value)
    if effective_value >= threshold:
        audit_context['finance_routing_reason'] = 'value_at_or_above_threshold'
        return (
            True,
            f'Finance approval required because contract value {effective_value:,.0f} '
            f'meets or exceeds the ${threshold:,.0f} threshold.',
            audit_context,
        )

    audit_context['finance_routing_reason'] = 'value_below_threshold'
    return (
        False,
        f'Contract value {effective_value:,.0f} is below the ${threshold:,.0f} '
        f'Finance approval threshold.',
        audit_context,
    )


def finance_threshold_display(organization=None) -> str:
    threshold = get_finance_approval_threshold(organization)
    return f'${threshold:,.0f}'


def finance_threshold_from_field_values(field_values: Mapping[str, Any], organization=None) -> Tuple[bool, str, dict]:
    """Evaluate Finance routing from governed workflow/intake field maps."""
    return requires_finance_approval(
        value=field_values.get('value'),
        currency=str(field_values.get('currency') or 'USD'),
        confirmed_above_threshold=bool(field_values.get('value_above_threshold_confirmed')),
        organization=organization,
        recurring_value=field_values.get('recurring_value') or field_values.get('annual_value'),
        total_contract_value=field_values.get('total_contract_value') or field_values.get('tcv'),
    )
