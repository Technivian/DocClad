"""PAR-CORE-003 — Contract Record provenance assignment, immutability, and repair.

Provenance is mandatory for every Contract Record (canonical domain invariant 3).
Historical rows without recoverable evidence are classified ``LEGACY_UNKNOWN`` —
never invented. Locked provenance fields cannot change without a governed repair
that records a reason and an immutable audit event.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

# Canonical audit event types (reuse equivalents; do not duplicate semantics).
EVENT_RECORD_CREATED = 'contract.record.created'
EVENT_PROVENANCE_ASSIGNED = 'contract.record.provenance_assigned'
EVENT_PROVENANCE_REPAIRED = 'contract.record.provenance_repaired'
# Existing create events kept as equivalents — see evidence matrix.
EQUIVALENT_CREATE_EVENTS = frozenset({
    'contract_created',
    'contract.created',
    'contract.uploaded',
    EVENT_RECORD_CREATED,
})


class OriginKind:
    WORKFLOW = 'WORKFLOW'
    MANUAL = 'MANUAL'
    UPLOAD = 'UPLOAD'
    IMPORT_CSV = 'IMPORT_CSV'
    IMPORT_INBOUND = 'IMPORT_INBOUND'
    INTEGRATION = 'INTEGRATION'
    MIGRATION = 'MIGRATION'
    SEED = 'SEED'
    ADMIN = 'ADMIN'
    LEGACY_UNKNOWN = 'LEGACY_UNKNOWN'

    CHOICES = (
        (WORKFLOW, 'Workflow instance'),
        (MANUAL, 'Manual creation'),
        (UPLOAD, 'Document upload'),
        (IMPORT_CSV, 'CSV import'),
        (IMPORT_INBOUND, 'Inbound import'),
        (INTEGRATION, 'External integration'),
        (MIGRATION, 'Data migration'),
        (SEED, 'Seed / demo data'),
        (ADMIN, 'Admin console'),
        (LEGACY_UNKNOWN, 'Legacy / unknown'),
    )

    VALUES = frozenset(c[0] for c in CHOICES)


# Fields that become immutable once provenance_locked_at is set.
PROVENANCE_LOCK_FIELDS = frozenset({
    'origin_kind',
    'origin_channel',
    'origin_workflow_id',
    'origin_workflow_template_id',
    'origin_workflow_template_version',
    'origin_reason',
    'provenance_correlation_id',
    'provenance_locked_at',
    'source_system',
    'source_system_id',
    'created_by_id',
})

# QuerySet.update / bulk paths — Django uses field names without _id for FKs.
PROVENANCE_UPDATE_BLOCKLIST = frozenset({
    'origin_kind',
    'origin_channel',
    'origin_workflow',
    'origin_workflow_id',
    'origin_workflow_template',
    'origin_workflow_template_id',
    'origin_workflow_template_version',
    'origin_reason',
    'provenance_correlation_id',
    'provenance_locked_at',
    'source_system',
    'source_system_id',
    'created_by',
    'created_by_id',
})


class ProvenanceError(ValidationError):
    """Raised when provenance is missing, incomplete, or illegally mutated."""


def provenance_snapshot(contract) -> dict[str, Any]:
    return {
        'origin_kind': getattr(contract, 'origin_kind', '') or '',
        'origin_channel': getattr(contract, 'origin_channel', '') or '',
        'origin_workflow_id': getattr(contract, 'origin_workflow_id', None),
        'origin_workflow_template_id': getattr(contract, 'origin_workflow_template_id', None),
        'origin_workflow_template_version': getattr(contract, 'origin_workflow_template_version', None),
        'origin_reason': getattr(contract, 'origin_reason', '') or '',
        'provenance_correlation_id': getattr(contract, 'provenance_correlation_id', '') or '',
        'provenance_locked_at': (
            contract.provenance_locked_at.isoformat()
            if getattr(contract, 'provenance_locked_at', None)
            else None
        ),
        'source_system': getattr(contract, 'source_system', '') or '',
        'source_system_id': getattr(contract, 'source_system_id', '') or '',
        'created_by_id': getattr(contract, 'created_by_id', None),
        'parent_contract_id': getattr(contract, 'parent_contract_id', None),
        'organization_id': getattr(contract, 'organization_id', None),
        'created_at': (
            contract.created_at.isoformat()
            if getattr(contract, 'created_at', None)
            else None
        ),
    }


def provenance_is_complete(contract) -> bool:
    kind = (getattr(contract, 'origin_kind', '') or '').strip()
    if not kind or kind not in OriginKind.VALUES:
        return False
    if kind == OriginKind.WORKFLOW:
        return bool(contract.origin_workflow_id and contract.origin_workflow_template_id)
    if kind == OriginKind.MANUAL:
        return bool(contract.created_by_id and (contract.origin_reason or '').strip())
    if kind == OriginKind.UPLOAD:
        return bool(contract.created_by_id)
    if kind in {OriginKind.IMPORT_CSV, OriginKind.IMPORT_INBOUND}:
        return True  # channel + org + correlation optional but kind is enough
    if kind == OriginKind.INTEGRATION:
        return bool((contract.source_system or '').strip() and (contract.source_system_id or '').strip())
    if kind in {OriginKind.MIGRATION, OriginKind.SEED, OriginKind.ADMIN, OriginKind.LEGACY_UNKNOWN}:
        return True
    return False


def validate_provenance_for_kind(**fields) -> None:
    """Reject incomplete provenance payloads for the stated origin kind."""
    kind = (fields.get('origin_kind') or '').strip()
    if not kind:
        raise ProvenanceError('origin_kind is required.')
    if kind not in OriginKind.VALUES:
        raise ProvenanceError(f'Unknown origin_kind "{kind}".')

    if kind == OriginKind.WORKFLOW:
        if not fields.get('origin_workflow') and not fields.get('origin_workflow_id'):
            raise ProvenanceError('WORKFLOW provenance requires originating Workflow Instance.')
        if not fields.get('origin_workflow_template') and not fields.get('origin_workflow_template_id'):
            raise ProvenanceError('WORKFLOW provenance requires immutable Workflow Version (template).')
    elif kind == OriginKind.MANUAL:
        if not fields.get('created_by') and not fields.get('created_by_id') and not fields.get('actor'):
            raise ProvenanceError('MANUAL provenance requires creating actor.')
        if not (fields.get('origin_reason') or '').strip():
            raise ProvenanceError('MANUAL provenance requires a reason.')
    elif kind == OriginKind.INTEGRATION:
        if not (fields.get('source_system') or '').strip():
            raise ProvenanceError('INTEGRATION provenance requires source_system.')
        if not (fields.get('source_system_id') or '').strip():
            raise ProvenanceError('INTEGRATION provenance requires external source identifier.')
    elif kind == OriginKind.UPLOAD:
        if not fields.get('created_by') and not fields.get('created_by_id') and not fields.get('actor'):
            raise ProvenanceError('UPLOAD provenance requires creating actor.')


def _actor_may_repair(*, actor, organization) -> bool:
    if actor is None:
        return False
    if getattr(actor, 'is_superuser', False) or getattr(actor, 'is_staff', False):
        return True
    if organization is None:
        return False
    from contracts.models import OrganizationMembership

    return OrganizationMembership.objects.filter(
        organization=organization,
        user=actor,
        is_active=True,
        role__in=[OrganizationMembership.Role.OWNER, OrganizationMembership.Role.ADMIN],
    ).exists()


def apply_provenance_fields(
    contract,
    *,
    origin_kind: str,
    origin_channel: str = '',
    origin_workflow=None,
    origin_workflow_template=None,
    origin_workflow_template_version: int | None = None,
    origin_reason: str = '',
    provenance_correlation_id: str = '',
    source_system: str | None = None,
    source_system_id: str | None = None,
    created_by=None,
    actor=None,
    lock: bool = True,
    validate: bool = True,
) -> None:
    """Stamp provenance fields onto an unsaved or unlocked contract instance."""
    creator = created_by if created_by is not None else actor
    template = origin_workflow_template
    version = origin_workflow_template_version
    if origin_workflow is not None:
        if template is None and getattr(origin_workflow, 'template_id', None):
            template = origin_workflow.template
        if version is None and template is not None:
            version = getattr(template, 'version', None)

    payload = {
        'origin_kind': origin_kind,
        'origin_channel': origin_channel,
        'origin_workflow': origin_workflow,
        'origin_workflow_template': template,
        'origin_workflow_template_version': version,
        'origin_reason': origin_reason,
        'provenance_correlation_id': provenance_correlation_id,
        'source_system': source_system if source_system is not None else contract.source_system,
        'source_system_id': source_system_id if source_system_id is not None else contract.source_system_id,
        'created_by': creator or contract.created_by,
        'actor': actor or creator,
    }
    if validate:
        validate_provenance_for_kind(**payload)

    contract.origin_kind = origin_kind
    contract.origin_channel = (origin_channel or '')[:64]
    if origin_workflow is not None:
        contract.origin_workflow = origin_workflow
    if template is not None:
        contract.origin_workflow_template = template
    if version is not None:
        contract.origin_workflow_template_version = version
    if origin_reason:
        contract.origin_reason = origin_reason[:500]
    if provenance_correlation_id:
        contract.provenance_correlation_id = provenance_correlation_id[:64]
    if source_system is not None:
        contract.source_system = source_system
    if source_system_id is not None:
        contract.source_system_id = source_system_id
    if creator is not None and not contract.created_by_id:
        contract.created_by = creator
    if lock and provenance_is_complete(contract):
        contract.provenance_locked_at = timezone.now()


def ensure_create_provenance(contract) -> None:
    """Called from Contract.save on create — never invents rich history."""
    kind = (getattr(contract, 'origin_kind', '') or '').strip()
    if not kind:
        contract.origin_kind = OriginKind.LEGACY_UNKNOWN
    if contract.provenance_locked_at is None and provenance_is_complete(contract):
        contract.provenance_locked_at = timezone.now()


def assert_provenance_immutable(contract, *, previous: dict[str, Any] | None) -> None:
    """Raise if locked provenance fields would change."""
    if previous is None:
        return
    if not previous.get('provenance_locked_at') and not contract.provenance_locked_at:
        return
    # Once ever locked (DB had lock OR instance now locked with prior values), protect.
    locked_before = bool(previous.get('provenance_locked_at'))
    if not locked_before:
        return
    for field in (
        'origin_kind',
        'origin_channel',
        'origin_workflow_id',
        'origin_workflow_template_id',
        'origin_workflow_template_version',
        'origin_reason',
        'provenance_correlation_id',
        'source_system',
        'source_system_id',
        'created_by_id',
    ):
        old = previous.get(field)
        new = getattr(contract, field, None)
        if field in {'origin_kind', 'origin_channel', 'origin_reason', 'provenance_correlation_id', 'source_system', 'source_system_id'}:
            old = old or ''
            new = new or ''
        if old != new:
            raise ProvenanceError(
                f'Provenance field "{field}" is immutable after lock. '
                f'Use repair_contract_provenance() with a reason.'
            )
    # provenance_locked_at itself must not clear
    if previous.get('provenance_locked_at') and not contract.provenance_locked_at:
        raise ProvenanceError('provenance_locked_at cannot be cleared.')


def _emit_audit(
    *,
    event_type: str,
    contract,
    actor,
    request=None,
    changes: dict | None = None,
    action=None,
):
    from contracts.middleware import log_action
    from contracts.models import AuditLog

    log_action(
        actor,
        action or AuditLog.Action.CREATE,
        'Contract',
        contract.pk,
        str(contract),
        organization=getattr(contract, 'organization', None),
        request=request,
        event_type=event_type,
        actor_type=(
            AuditLog.ActorType.SYSTEM if actor is None else AuditLog.ActorType.HUMAN
        ),
        changes=changes or {},
    )


def assign_and_lock_provenance(
    contract,
    *,
    origin_kind: str,
    origin_channel: str = '',
    origin_workflow=None,
    origin_workflow_template=None,
    origin_workflow_template_version: int | None = None,
    origin_reason: str = '',
    provenance_correlation_id: str = '',
    source_system: str | None = None,
    source_system_id: str | None = None,
    actor=None,
    request=None,
    emit_created: bool = True,
    emit_assigned: bool = True,
) -> object:
    """Assign provenance on a persisted contract and lock it."""
    if contract.pk is None:
        raise ProvenanceError('Contract must be saved before assign_and_lock_provenance.')
    if contract.provenance_locked_at and provenance_is_complete(contract):
        # Idempotent no-op when already locked with same classification.
        return contract

    apply_provenance_fields(
        contract,
        origin_kind=origin_kind,
        origin_channel=origin_channel,
        origin_workflow=origin_workflow,
        origin_workflow_template=origin_workflow_template,
        origin_workflow_template_version=origin_workflow_template_version,
        origin_reason=origin_reason,
        provenance_correlation_id=provenance_correlation_id,
        source_system=source_system,
        source_system_id=source_system_id,
        actor=actor,
        lock=True,
        validate=True,
    )
    contract.save(
        update_fields=[
            'origin_kind',
            'origin_channel',
            'origin_workflow',
            'origin_workflow_template',
            'origin_workflow_template_version',
            'origin_reason',
            'provenance_correlation_id',
            'provenance_locked_at',
            'source_system',
            'source_system_id',
            'created_by',
            'updated_at',
        ],
        allow_provenance_mutation=True,
    )
    snapshot = provenance_snapshot(contract)
    if emit_created:
        _emit_audit(
            event_type=EVENT_RECORD_CREATED,
            contract=contract,
            actor=actor,
            request=request,
            changes={'event': EVENT_RECORD_CREATED, 'provenance': snapshot},
        )
    if emit_assigned:
        _emit_audit(
            event_type=EVENT_PROVENANCE_ASSIGNED,
            contract=contract,
            actor=actor,
            request=request,
            changes={'event': EVENT_PROVENANCE_ASSIGNED, 'provenance': snapshot},
            action=None,
        )
    return contract


def pin_workflow_provenance(contract, workflow, *, actor=None, request=None, channel: str = '') -> object:
    """Pin originating Workflow Instance + Version after workflow create."""
    if workflow is None:
        raise ProvenanceError('origin_workflow is required.')
    if contract.organization_id and workflow.organization_id and contract.organization_id != workflow.organization_id:
        raise ProvenanceError('Workflow Instance organization must match Contract Record workspace.')
    if workflow.contract_id and workflow.contract_id != contract.pk:
        raise ProvenanceError('Workflow Instance must reference this Contract Record.')

    template = workflow.template
    if template is None:
        raise ProvenanceError('Workflow Instance must reference an immutable Workflow Version (template).')

    was_locked = bool(contract.provenance_locked_at)
    apply_provenance_fields(
        contract,
        origin_kind=OriginKind.WORKFLOW,
        origin_channel=channel or contract.origin_channel or 'workflow',
        origin_workflow=workflow,
        origin_workflow_template=template,
        origin_workflow_template_version=template.version,
        origin_reason=contract.origin_reason or '',
        actor=actor or contract.created_by,
        lock=True,
        validate=True,
    )
    contract.save(
        update_fields=[
            'origin_kind',
            'origin_channel',
            'origin_workflow',
            'origin_workflow_template',
            'origin_workflow_template_version',
            'provenance_locked_at',
            'updated_at',
        ],
        allow_provenance_mutation=True,
    )
    snapshot = provenance_snapshot(contract)
    _emit_audit(
        event_type=EVENT_PROVENANCE_ASSIGNED if was_locked else EVENT_RECORD_CREATED,
        contract=contract,
        actor=actor,
        request=request,
        changes={
            'event': EVENT_PROVENANCE_ASSIGNED if was_locked else EVENT_RECORD_CREATED,
            'provenance': snapshot,
        },
    )
    if not was_locked:
        _emit_audit(
            event_type=EVENT_PROVENANCE_ASSIGNED,
            contract=contract,
            actor=actor,
            request=request,
            changes={'event': EVENT_PROVENANCE_ASSIGNED, 'provenance': snapshot},
        )
    return contract


@transaction.atomic
def repair_contract_provenance(
    contract,
    *,
    reason: str,
    actor,
    request=None,
    organization=None,
    **field_updates,
) -> object:
    """Governed provenance repair — requires reason, authorization, and audit."""
    reason = (reason or '').strip()
    if not reason:
        raise ProvenanceError('Provenance repair requires a reason.')
    org = organization or contract.organization
    if not _actor_may_repair(actor=actor, organization=org):
        raise PermissionDenied('Not authorized to repair contract provenance.')
    if org is not None and contract.organization_id and contract.organization_id != org.id:
        raise PermissionDenied('Cannot repair provenance across workspace boundaries.')

    before = provenance_snapshot(contract)
    allowed = {
        'origin_kind',
        'origin_channel',
        'origin_workflow',
        'origin_workflow_template',
        'origin_workflow_template_version',
        'origin_reason',
        'provenance_correlation_id',
        'source_system',
        'source_system_id',
        'created_by',
    }
    unknown = set(field_updates) - allowed
    if unknown:
        raise ProvenanceError(f'Unsupported provenance repair fields: {sorted(unknown)}')

    for key, value in field_updates.items():
        setattr(contract, key, value)

    if 'origin_workflow' in field_updates and field_updates['origin_workflow'] is not None:
        wf = field_updates['origin_workflow']
        if contract.origin_workflow_template_id is None and wf.template_id:
            contract.origin_workflow_template = wf.template
        if contract.origin_workflow_template_version is None and wf.template_id:
            contract.origin_workflow_template_version = wf.template.version

    if not provenance_is_complete(contract):
        raise ProvenanceError('Repaired provenance is still incomplete for its origin_kind.')

    contract.origin_reason = reason[:500] if 'origin_reason' not in field_updates else contract.origin_reason
    contract.provenance_locked_at = timezone.now()
    update_fields = list(field_updates.keys()) + ['origin_reason', 'provenance_locked_at', 'updated_at']
    # Normalize FK names for update_fields
    normalized = []
    for f in update_fields:
        if f == 'origin_workflow':
            normalized.append('origin_workflow')
        elif f == 'origin_workflow_template':
            normalized.append('origin_workflow_template')
        elif f == 'created_by':
            normalized.append('created_by')
        else:
            normalized.append(f)
    contract.save(update_fields=list(dict.fromkeys(normalized)), allow_provenance_mutation=True)

    after = provenance_snapshot(contract)
    from contracts.models import AuditLog

    _emit_audit(
        event_type=EVENT_PROVENANCE_REPAIRED,
        contract=contract,
        actor=actor,
        request=request,
        action=AuditLog.Action.UPDATE,
        changes={
            'event': EVENT_PROVENANCE_REPAIRED,
            'reason': reason,
            'before': before,
            'after': after,
        },
    )
    return contract


def origin_kind_for_import_source(source: str) -> str:
    mapping = {
        'csv_import': OriginKind.IMPORT_CSV,
        'inbound_import': OriginKind.IMPORT_INBOUND,
        'salesforce': OriginKind.INTEGRATION,
        'netsuite': OriginKind.INTEGRATION,
        'import': OriginKind.IMPORT_INBOUND,
    }
    return mapping.get((source or '').strip().lower(), OriginKind.INTEGRATION)


def stamp_import_provenance(contract, *, source: str, actor=None, correlation_id: str = '') -> None:
    """Stamp import/integration provenance onto a contract before first save."""
    kind = origin_kind_for_import_source(source)
    channel = (source or kind).lower()[:64]
    apply_provenance_fields(
        contract,
        origin_kind=kind,
        origin_channel=channel,
        provenance_correlation_id=correlation_id,
        source_system=contract.source_system or (
            'salesforce' if channel == 'salesforce' else
            'netsuite' if channel == 'netsuite' else
            contract.source_system
        ),
        source_system_id=contract.source_system_id or '',
        actor=actor,
        lock=False,
        validate=kind != OriginKind.INTEGRATION or bool(contract.source_system_id),
    )
    # Integrations without id yet stay unlocked until id is set; imports lock on save via ensure.
    if kind != OriginKind.INTEGRATION or (contract.source_system and contract.source_system_id):
        if provenance_is_complete(contract):
            contract.provenance_locked_at = timezone.now()
