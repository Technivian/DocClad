"""PAR-CORE-002 — canonical Contract Type catalogue (G-DOM-02).

``ContractType`` model rows are the governed catalogue (CANONICAL_DOMAIN_MODEL §2.6).
``Contract.contract_type`` CharField is a transitional denormalized code mirror for
filters, integrations, and legacy readers — always synced from the catalogue FK
on save. New writes must resolve through ``assign_contract_type()`` or
``sync_contract_type_catalogue_fields()`` (invoked from ``Contract.save``).
"""

from __future__ import annotations

from typing import Iterable

from django.core.exceptions import ValidationError
from django.db import transaction

EVENT_TYPE_ASSIGNED = 'contract.type.catalogue.assigned'
EVENT_TYPE_REPAIRED = 'contract.type.catalogue.repaired'
EVENT_CATALOGUE_UPDATED = 'contract_type.catalogue.updated'

# Explicit unmappable bucket — never silently merge distinct legacy strings.
UNMAPPED_LEGACY_CODE = 'OTHER'


class ContractTypeCatalogueError(ValidationError):
    """Raised when a contract type code cannot be resolved or assigned."""


def enum_choices() -> tuple[tuple[str, str], ...]:
    from contracts.models import Contract

    return Contract.ContractType.choices


def valid_codes() -> frozenset[str]:
    return frozenset(code for code, _ in enum_choices())


def normalize_code(raw: str | None) -> str:
    return (raw or '').strip().upper()


def catalogue_label_for_code(code: str) -> str:
    for choice_code, label in enum_choices():
        if choice_code == code:
            return label
    return code.replace('_', ' ').title()


@transaction.atomic
def ensure_catalogue_row(code: str, *, name: str | None = None, description: str = '') -> object:
    """Return the governed catalogue row for ``code``, creating it when missing."""
    from contracts.models import ContractType

    normalized = normalize_code(code)
    if not normalized:
        raise ContractTypeCatalogueError('Contract type code is required.')
    if normalized not in valid_codes():
        raise ContractTypeCatalogueError(f'Unknown contract type code "{normalized}".')

    row, created = ContractType.objects.get_or_create(
        code=normalized,
        defaults={
            'name': name or catalogue_label_for_code(normalized),
            'description': description,
            'is_active': True,
        },
    )
    if not created and name and row.name != name:
        # Keep existing display name unless explicitly repairing via admin.
        pass
    return row


def seed_catalogue_from_enum(*, deactivate_missing: bool = False) -> dict[str, int]:
    """Idempotently seed catalogue rows for every ``Contract.ContractType`` value."""
    from contracts.models import ContractType

    created = updated = 0
    codes = set()
    for code, label in enum_choices():
        codes.add(code)
        row, was_created = ContractType.objects.get_or_create(
            code=code,
            defaults={'name': label, 'is_active': True},
        )
        if was_created:
            created += 1
        elif not row.is_active:
            row.is_active = True
            row.name = label
            row.save(update_fields=['is_active', 'name'])
            updated += 1
    if deactivate_missing:
        ContractType.objects.exclude(code__in=codes).update(is_active=False)
    return {'created': created, 'updated': updated, 'total': len(codes)}


def resolve_catalogue(*, code: str | None = None, catalogue_id: int | None = None):
    from contracts.models import ContractType

    if catalogue_id is not None:
        return ContractType.objects.filter(pk=catalogue_id, is_active=True).first()
    normalized = normalize_code(code)
    if not normalized:
        return None
    if normalized not in valid_codes():
        return None
    return ensure_catalogue_row(normalized)


def resolve_import_code(raw: str | None) -> tuple[str, object]:
    """Map import/integration strings to a governed code + catalogue row.

  Legacy aliases map explicitly; unknown values become ``OTHER`` without
  inventing new codes.
    """
    normalized = normalize_code(raw)
    legacy_aliases = {
        'SERVICE': 'SOW',
        'SERVICES': 'SOW',
        'MASTER_SERVICE_AGREEMENT': 'MSA',
        'MASTER SERVICES AGREEMENT': 'MSA',
        'NON_DISCLOSURE': 'NDA',
        'NON-DISCLOSURE': 'NDA',
        'DATA_PROCESSING': 'DPA',
        'SUPPLIER': 'VENDOR',
        'SUPPLIER_AGREEMENT': 'VENDOR',
        'ADDENDUM': 'AMENDMENT',
    }
    if normalized in legacy_aliases:
        normalized = legacy_aliases[normalized]
    if normalized not in valid_codes():
        normalized = UNMAPPED_LEGACY_CODE
    row = ensure_catalogue_row(normalized)
    return normalized, row


def assign_contract_type(contract, *, code: str | None = None, catalogue=None) -> None:
    """Canonical write: set catalogue FK and denormalized code together."""
    if catalogue is not None:
        contract.contract_type_catalogue = catalogue
        contract.contract_type = catalogue.code
        return
    normalized, row = resolve_import_code(code or contract.contract_type)
    contract.contract_type_catalogue = row
    contract.contract_type = normalized


def sync_contract_type_catalogue_fields(contract) -> None:
    """Keep FK and CharField aligned before persistence."""
    if getattr(contract, 'contract_type_catalogue_id', None):
        cat = contract.contract_type_catalogue
        if cat and contract.contract_type != cat.code:
            contract.contract_type = cat.code
        return
    if contract.contract_type:
        normalized, row = resolve_import_code(contract.contract_type)
        contract.contract_type = normalized
        contract.contract_type_catalogue = row
        return
    # Default empty creates to OTHER catalogue for mandatory type pairing.
    from contracts.models import Contract

    row = ensure_catalogue_row(Contract.ContractType.OTHER)
    contract.contract_type = row.code
    contract.contract_type_catalogue = row


def get_contract_type_code(contract) -> str:
    if getattr(contract, 'contract_type_catalogue_id', None) and contract.contract_type_catalogue_id:
        return contract.contract_type_catalogue.code
    return normalize_code(contract.contract_type) or UNMAPPED_LEGACY_CODE


def active_catalogue_queryset():
    from contracts.models import ContractType

    return ContractType.objects.filter(is_active=True).order_by('name')


def form_choices(*, include_blank: bool = True) -> list[tuple[str, str]]:
    rows = list(active_catalogue_queryset().values_list('code', 'name'))
    if include_blank:
        return [('', 'Select contract type')] + rows
    return rows


def validate_import_contract_type(raw: str | None) -> list[str]:
    if not (raw or '').strip():
        return []
    normalized = normalize_code(raw)
    legacy_ok = normalized in {
        'SERVICE', 'SERVICES', 'MASTER_SERVICE_AGREEMENT', 'SUPPLIER', 'SUPPLIER_AGREEMENT', 'ADDENDUM',
    }
    if normalized in valid_codes() or legacy_ok:
        return []
    return [f'invalid contract_type "{raw}"']


def emit_catalogue_assigned_audit(contract, *, actor=None, request=None, source: str = ''):
    from contracts.middleware import log_action
    from contracts.models import AuditLog

    log_action(
        actor,
        AuditLog.Action.UPDATE if contract.pk else AuditLog.Action.CREATE,
        'Contract',
        contract.pk,
        str(contract),
        organization=getattr(contract, 'organization', None),
        request=request,
        event_type=EVENT_TYPE_ASSIGNED,
        changes={
            'event': EVENT_TYPE_ASSIGNED,
            'source': source,
            'contract_type_code': get_contract_type_code(contract),
            'contract_type_catalogue_id': contract.contract_type_catalogue_id,
        },
    )


@transaction.atomic
def repair_contract_type_catalogue(
    contract,
    *,
    code: str,
    reason: str,
    actor,
    request=None,
    organization=None,
) -> object:
    """Governed repair when historical type evidence is recovered."""
    from contracts.services.contract_provenance import _actor_may_repair

    reason = (reason or '').strip()
    if not reason:
        raise ContractTypeCatalogueError('Type repair requires a reason.')
    org = organization or contract.organization
    if not _actor_may_repair(actor=actor, organization=org):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied('Not authorized to repair contract type catalogue binding.')
    if org is not None and contract.organization_id and contract.organization_id != org.id:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied('Cannot repair contract type across workspace boundaries.')

    before = {
        'contract_type': contract.contract_type,
        'contract_type_catalogue_id': contract.contract_type_catalogue_id,
    }
    assign_contract_type(contract, code=code)
    contract.save(update_fields=['contract_type', 'contract_type_catalogue', 'updated_at'])

    from contracts.middleware import log_action
    from contracts.models import AuditLog

    log_action(
        actor,
        AuditLog.Action.UPDATE,
        'Contract',
        contract.pk,
        str(contract),
        organization=org,
        request=request,
        event_type=EVENT_TYPE_REPAIRED,
        changes={
            'event': EVENT_TYPE_REPAIRED,
            'reason': reason,
            'before': before,
            'after': {
                'contract_type': contract.contract_type,
                'contract_type_catalogue_id': contract.contract_type_catalogue_id,
            },
        },
    )
    return contract


def audit_catalogue_mutation(*, actor, catalogue, action: str, changes: dict | None = None, request=None):
    from contracts.middleware import log_action
    from contracts.models import AuditLog

    log_action(
        actor,
        AuditLog.Action.UPDATE if action == 'update' else AuditLog.Action.CREATE,
        'ContractType',
        catalogue.pk,
        str(catalogue),
        request=request,
        event_type=EVENT_CATALOGUE_UPDATED,
        changes={'event': EVENT_CATALOGUE_UPDATED, 'action': action, **(changes or {})},
    )
