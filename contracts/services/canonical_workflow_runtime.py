"""Default-off canonical Workflow Definition → Version → Instance runtime.

The service is deliberately an additive execution path.  It does not alter the
legacy ``WorkflowTemplate`` launch path, enable an e-sign provider, or migrate
historic instances.  Every write is tenant-bound and emits a chained audit
event so a controlled, non-production activation can be evidenced separately.
"""

from __future__ import annotations

import hashlib
import json
from typing import Protocol

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from contracts.middleware import log_action


class CanonicalWorkflowError(ValidationError):
    """Raised when a canonical workflow invariant is not met."""


class PublicationPolicy(Protocol):
    def permits(self, *, actor, definition) -> bool:
        ...


class DenyPublicationPolicy:
    """Safe default while an organization-specific publication resolver is unresolved."""

    def permits(self, *, actor, definition) -> bool:
        return False


class ExistingWorkspacePublicationPolicy:
    """Adapter over the existing organization-management access rule.

    It neither creates a role nor changes the process-role resolver.  A future
    resolver may replace this adapter only under its own approval.
    """

    def permits(self, *, actor, definition) -> bool:
        from contracts.permissions import can_manage_organization

        return bool(actor and can_manage_organization(actor, definition.organization))


REQUIRED_NDA_STEP_KINDS = frozenset({'INTAKE', 'DOCUMENT', 'APPROVAL', 'SIGNATURE', 'ARCHIVE'})


def _audit(*, actor, organization, model_name, object_id, event_type, changes=None, outcome='success', request=None):
    from contracts.models import AuditLog

    return log_action(
        actor,
        AuditLog.Action.CREATE if event_type.endswith(('.created', '.launched', '.promoted')) else AuditLog.Action.UPDATE,
        model_name,
        object_id,
        model_name,
        organization=organization,
        request=request,
        event_type=event_type,
        outcome=outcome,
        actor_type=AuditLog.ActorType.HUMAN if actor else AuditLog.ActorType.SYSTEM,
        changes={'event': event_type, **(changes or {})},
    )


def _assert_same_organization(*objects):
    org_ids = set()
    for obj in objects:
        if obj is None:
            continue
        organization_id = getattr(obj, 'organization_id', None)
        if organization_id is None and getattr(obj, 'definition_id', None):
            organization_id = getattr(obj.definition, 'organization_id', None)
        org_ids.add(organization_id)
    if len(org_ids) != 1 or None in org_ids:
        raise CanonicalWorkflowError('Canonical workflow objects must belong to one organization.')


def _assert_member(*, actor, organization):
    from contracts.permissions import get_active_org_membership

    if actor is None or get_active_org_membership(actor, organization) is None:
        raise PermissionDenied('Organization membership is required.')


def _assert_manage(*, actor, organization):
    from contracts.permissions import can_manage_organization

    _assert_member(actor=actor, organization=organization)
    if not can_manage_organization(actor, organization):
        raise PermissionDenied('Organization management access is required.')


def _assert_contract_edit(*, actor, contract, request=None, model_name='Contract', object_id=None):
    """Use the existing object-level contract rule; do not infer a new workflow role."""
    from contracts.permissions import ContractAction, can_access_contract_action

    if can_access_contract_action(actor, contract, ContractAction.EDIT):
        return
    _audit(
        actor=actor,
        organization=contract.organization,
        model_name=model_name,
        object_id=object_id or contract.pk,
        event_type='canonical.authorization.blocked',
        outcome='blocked',
        request=request,
    )
    raise PermissionDenied('Contract edit access is required for this canonical workflow action.')


def _canonical_runtime_enabled(organization) -> bool:
    if not getattr(settings, 'CANONICAL_NDA_RUNTIME_ENABLED', False):
        return False
    raw_allowlist = str(getattr(settings, 'CANONICAL_NDA_RUNTIME_ORG_ALLOWLIST', '') or '')
    allowed = {item.strip() for item in raw_allowlist.split(',') if item.strip()}
    return str(organization.pk) in allowed or str(getattr(organization, 'slug', '')) in allowed


def _assert_runtime_enabled(organization):
    if not _canonical_runtime_enabled(organization):
        raise CanonicalWorkflowError(
            'The canonical NDA runtime is disabled for this workspace. Controlled activation is required.'
        )


def configuration_checksum(configuration: dict) -> str:
    canonical = json.dumps(configuration or {}, sort_keys=True, separators=(',', ':'), default=str)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def validate_nda_configuration(configuration: dict) -> list[str]:
    if not isinstance(configuration, dict):
        return ['Configuration must be an object.']
    steps = configuration.get('steps')
    if not isinstance(steps, list):
        return ['Configuration must contain a steps list.']
    kinds = {str(item.get('kind', '')).upper() for item in steps if isinstance(item, dict)}
    missing = sorted(REQUIRED_NDA_STEP_KINDS - kinds)
    if missing:
        return [f'NDA configuration is missing required step kinds: {", ".join(missing)}.']
    return []


@transaction.atomic
def create_workflow_definition(*, organization, key: str, name: str, actor, description: str = ''):
    from contracts.models import WorkflowDefinition

    _assert_manage(actor=actor, organization=organization)
    definition = WorkflowDefinition.objects.create(
        organization=organization,
        key=(key or '').strip(),
        name=(name or '').strip(),
        description=description or '',
        contract_type='NDA',
        created_by=actor,
    )
    _audit(actor=actor, organization=organization, model_name='WorkflowDefinition', object_id=definition.pk,
           event_type='workflow.definition.created', changes={'definition_key': definition.key})
    return definition


@transaction.atomic
def create_draft_workflow_version(*, definition, configuration: dict, actor):
    from contracts.models import WorkflowVersion

    _assert_manage(actor=actor, organization=definition.organization)
    latest = (
        WorkflowVersion.objects.select_for_update().filter(definition=definition)
        .order_by('-version_number').values_list('version_number', flat=True).first()
    )
    version = WorkflowVersion.objects.create(
        definition=definition,
        version_number=(latest or 0) + 1,
        configuration=configuration or {},
        configuration_checksum=configuration_checksum(configuration or {}),
        created_by=actor,
    )
    _audit(actor=actor, organization=definition.organization, model_name='WorkflowVersion', object_id=version.pk,
           event_type='workflow.version.draft_created', changes={'version_number': version.version_number})
    return version


@transaction.atomic
def validate_workflow_version(*, version, actor):
    _assert_manage(actor=actor, organization=version.definition.organization)
    if version.state != version.State.DRAFT:
        raise CanonicalWorkflowError('Only draft workflow versions can be validated.')
    errors = validate_nda_configuration(version.configuration)
    version.validation_errors = errors
    version.validated_at = timezone.now()
    version.save(update_fields=['validation_errors', 'validated_at'])
    _audit(actor=actor, organization=version.definition.organization, model_name='WorkflowVersion', object_id=version.pk,
           event_type='workflow.version.validated', changes={'error_count': len(errors)})
    return errors


def publish_workflow_version(*, version, actor, policy: PublicationPolicy | None = None, request=None):
    _assert_member(actor=actor, organization=version.definition.organization)
    policy = policy or DenyPublicationPolicy()
    if not policy.permits(actor=actor, definition=version.definition):
        _audit(actor=actor, organization=version.definition.organization, model_name='WorkflowVersion', object_id=version.pk,
               event_type='workflow.version.publication_blocked', outcome='blocked', request=request)
        raise PermissionDenied('Publication authority is not established for this workflow definition.')
    errors = validate_nda_configuration(version.configuration)
    if errors:
        version.validation_errors = errors
        version.validated_at = timezone.now()
        version.save(update_fields=['validation_errors', 'validated_at'])
        _audit(actor=actor, organization=version.definition.organization, model_name='WorkflowVersion', object_id=version.pk,
               event_type='workflow.version.publication_blocked', outcome='blocked',
               changes={'error_count': len(errors)}, request=request)
        raise CanonicalWorkflowError('Workflow version validation failed.')
    return _publish_workflow_version(version=version, actor=actor, request=request)


@transaction.atomic
def _publish_workflow_version(*, version, actor, request=None):
    from contracts.models import WorkflowVersion

    if version.state != WorkflowVersion.State.DRAFT:
        raise CanonicalWorkflowError('Only a draft workflow version can be published.')
    for current in WorkflowVersion.objects.select_for_update().filter(
        definition=version.definition, state=WorkflowVersion.State.PUBLISHED,
    ):
        current.state = WorkflowVersion.State.SUPERSEDED
        current.save(update_fields=['state'], allow_lifecycle_transition=True)
        _audit(actor=actor, organization=version.definition.organization, model_name='WorkflowVersion', object_id=current.pk,
               event_type='workflow.version.superseded', changes={'superseded_by': version.pk}, request=request)
    version.state = WorkflowVersion.State.PUBLISHED
    version.validation_errors = []
    version.validated_at = timezone.now()
    version.published_at = timezone.now()
    version.published_by = actor
    version.configuration_checksum = configuration_checksum(version.configuration)
    version.save(allow_lifecycle_transition=True)
    _audit(actor=actor, organization=version.definition.organization, model_name='WorkflowVersion', object_id=version.pk,
           event_type='workflow.version.published',
           changes={'version_number': version.version_number, 'configuration_checksum': version.configuration_checksum}, request=request)
    return version


@transaction.atomic
def launch_nda_workflow_instance(*, version, actor, title: str, launch_rationale: str, request=None):
    """Launch only a published version; the instance never follows later publications."""
    from contracts.models import Contract, WorkflowInstance
    from contracts.services.contract_provenance import OriginKind, apply_provenance_fields

    organization = version.definition.organization
    _assert_member(actor=actor, organization=organization)
    _assert_runtime_enabled(organization)
    if version.state != version.State.PUBLISHED:
        raise CanonicalWorkflowError('Only a published workflow version can be launched.')
    contract = Contract(
        organization=organization,
        title=(title or '').strip(),
        contract_type=Contract.ContractType.NDA,
        status=Contract.Status.IN_PROGRESS,
        lifecycle_stage=Contract.LifecycleStage.INTAKE,
        created_by=actor,
        owner=actor,
    )
    # The legacy Contract provenance schema has no canonical instance column.
    # Keep it explicitly unlocked; ContractRecord below is the authoritative
    # immutable execution provenance and is created only at completion.
    apply_provenance_fields(
        contract, origin_kind=OriginKind.WORKFLOW, origin_channel='canonical_nda_runtime',
        actor=actor, lock=False, validate=False,
    )
    contract.save()
    instance = WorkflowInstance.objects.create(
        organization=organization,
        definition=version.definition,
        workflow_version=version,
        contract=contract,
        launch_rationale=(launch_rationale or '').strip(),
        launched_by=actor,
    )
    _audit(actor=actor, organization=organization, model_name='WorkflowInstance', object_id=instance.pk,
           event_type='workflow.instance.launched',
           changes={'workflow_version_id': version.pk, 'workflow_version_number': version.version_number,
                    'contract_id': contract.pk, 'correlation_id': str(instance.correlation_id)}, request=request)
    return instance


def _latest_final_document_version(instance):
    from contracts.models import DocumentVersion

    return DocumentVersion.objects.filter(
        contract=instance.contract, organization=instance.organization,
        status__in=['FINAL', 'EXECUTED'],
    ).order_by('-created_at', '-pk').first()


@transaction.atomic
def create_final_nda_document_version(*, instance, actor, title: str, file, request=None, derived_from=None):
    from contracts.models import Document
    from contracts.services.document_version_service import create_document_version

    _assert_member(actor=actor, organization=instance.organization)
    _assert_contract_edit(
        actor=actor, contract=instance.contract, request=request,
        model_name='WorkflowInstance', object_id=instance.pk,
    )
    _assert_same_organization(instance, instance.workflow_version, instance.definition, instance.contract)
    if instance.status != instance.Status.ACTIVE:
        raise CanonicalWorkflowError('Final document creation requires an active workflow instance.')
    if derived_from is None:
        derived_from = _latest_final_document_version(instance)
    derived_from_document = getattr(derived_from, 'document_row', None)
    document, version = create_document_version(
        organization=instance.organization,
        title=title,
        document_type=Document.DocType.CONTRACT,
        status=Document.Status.FINAL,
        contract=instance.contract,
        file=file,
        uploaded_by=actor,
        actor=actor,
        source='generated',
        derived_from_document=derived_from_document,
        request=request,
    )
    if derived_from is not None:
        _reset_after_material_change(instance=instance, superseding_version=version, actor=actor, request=request)
    _audit(actor=actor, organization=instance.organization, model_name='DocumentVersion', object_id=version.pk,
           event_type='document.version.created',
           changes={'workflow_instance_id': instance.pk, 'document_id': document.pk,
                    'derived_from_id': getattr(derived_from, 'pk', None)}, request=request)
    _audit(actor=actor, organization=instance.organization, model_name='DocumentVersion', object_id=version.pk,
           event_type='document.locked',
           changes={'workflow_instance_id': instance.pk, 'document_id': document.pk}, request=request)
    return version


def _reset_after_material_change(*, instance, superseding_version, actor, request=None):
    """Append revocations/cancellations; never rewrite prior decisions or evidence."""
    from contracts.models import ApprovalDecision, ApprovalRequirement, SignaturePacket

    requirements = ApprovalRequirement.objects.select_for_update().filter(
        workflow_instance=instance,
        status__in=[ApprovalRequirement.Status.OPEN, ApprovalRequirement.Status.SATISFIED],
    )
    for requirement in requirements:
        requirement.status = ApprovalRequirement.Status.INVALIDATED
        requirement.invalidation_reason = 'Material final NDA version change requires a new approval.'
        requirement.invalidated_at = timezone.now()
        requirement.closed_at = timezone.now()
        requirement.save(update_fields=['status', 'invalidation_reason', 'invalidated_at', 'closed_at', 'updated_at'])
        ApprovalDecision.objects.create(
            organization=instance.organization,
            requirement=requirement,
            outcome=ApprovalDecision.Outcome.REVOKED,
            decided_by=actor,
            authority_holder_id=requirement.assigned_to_id,
            comments=requirement.invalidation_reason,
            contract_status=requirement.contract_status_at_open,
            contract_lifecycle_stage=requirement.contract_lifecycle_stage_at_open,
            document_version=superseding_version,
            document_version_missing=False,
            decided_at=timezone.now(),
        )
        _audit(actor=actor, organization=instance.organization, model_name='ApprovalRequirement', object_id=requirement.pk,
               event_type='approval.requirement.invalidated',
               changes={'workflow_instance_id': instance.pk, 'document_version_id': superseding_version.pk}, request=request)
        _audit(actor=actor, organization=instance.organization, model_name='ApprovalRequirement', object_id=requirement.pk,
               event_type='approval.reset',
               changes={'workflow_instance_id': instance.pk, 'document_version_id': superseding_version.pk}, request=request)
    for packet in SignaturePacket.objects.select_for_update().filter(
        workflow_instance=instance,
        status__in=[SignaturePacket.Status.PENDING, SignaturePacket.Status.SENT],
    ):
        packet.status = SignaturePacket.Status.CANCELLED
        packet.invalidated_at = timezone.now()
        packet.invalidation_reason = 'Material final NDA version change invalidated this packet.'
        packet.save(update_fields=['status', 'invalidated_at', 'invalidation_reason'])
        _audit(actor=actor, organization=instance.organization, model_name='SignaturePacket', object_id=packet.pk,
               event_type='signature.packet.invalidated',
               changes={'workflow_instance_id': instance.pk, 'document_version_id': superseding_version.pk}, request=request)
    _audit(actor=actor, organization=instance.organization, model_name='DocumentVersion', object_id=superseding_version.pk,
           event_type='document.version.material_change_recorded', changes={'workflow_instance_id': instance.pk}, request=request)


@transaction.atomic
def open_nda_approval_requirement(*, instance, actor, approval_step: str, assigned_to, authority_basis='workflow_submit', request=None):
    from contracts.services.approval_canonical import create_approval_requirement

    _assert_member(actor=actor, organization=instance.organization)
    _assert_contract_edit(
        actor=actor, contract=instance.contract, request=request,
        model_name='WorkflowInstance', object_id=instance.pk,
    )
    document_version = _latest_final_document_version(instance)
    if document_version is None:
        raise CanonicalWorkflowError('Approval requires an immutable final NDA DocumentVersion.')
    requirement = create_approval_requirement(
        organization=instance.organization,
        contract=instance.contract,
        workflow_instance=instance,
        document_version=document_version,
        approval_step=approval_step,
        assigned_to=assigned_to,
        authority_basis=authority_basis,
        authority_reference={
            'workflow_instance_id': instance.pk,
            'workflow_version_id': instance.workflow_version_id,
            'document_version_id': document_version.pk,
        },
        actor=actor,
        request=request,
    )
    _audit(actor=actor, organization=instance.organization, model_name='ApprovalRequirement', object_id=requirement.pk,
           event_type='approval.requirement.opened',
           changes={'workflow_instance_id': instance.pk, 'document_version_id': document_version.pk}, request=request)
    return requirement


@transaction.atomic
def record_nda_approval(*, requirement, actor, action='approve', comments='', request=None):
    from contracts.services.approval_canonical import record_approval_decision

    if requirement.workflow_instance_id is None:
        raise CanonicalWorkflowError('This is not a canonical workflow approval requirement.')
    _assert_member(actor=actor, organization=requirement.organization)
    if actor.pk not in {requirement.assigned_to_id, requirement.delegated_to_id}:
        raise PermissionDenied('This approval is assigned to another actor.')
    accountable_user_id = requirement.contract.owner_id or requirement.contract.created_by_id
    if accountable_user_id == actor.pk:
        raise PermissionDenied('A contract owner cannot decide their own approval.')
    current = _latest_final_document_version(requirement.workflow_instance)
    if current is None or requirement.document_version_id != current.pk:
        raise CanonicalWorkflowError('Approval cannot be recorded against a superseded final document version.')
    return record_approval_decision(requirement, action=action, actor=actor, comments=comments, request=request)


@transaction.atomic
def create_signature_packet(*, instance, actor, provider_name='', request=None):
    from contracts.models import ApprovalRequirement, SignaturePacket

    _assert_member(actor=actor, organization=instance.organization)
    _assert_contract_edit(
        actor=actor, contract=instance.contract, request=request,
        model_name='WorkflowInstance', object_id=instance.pk,
    )
    document_version = _latest_final_document_version(instance)
    if document_version is None:
        raise CanonicalWorkflowError('Signature packet requires a final NDA DocumentVersion.')
    requirements = ApprovalRequirement.objects.filter(workflow_instance=instance)
    if not requirements.exists() or requirements.exclude(
        status=ApprovalRequirement.Status.SATISFIED, document_version=document_version,
    ).exists():
        raise CanonicalWorkflowError('All canonical approvals for this final document version must be satisfied.')
    packet = SignaturePacket.objects.create(
        organization=instance.organization,
        workflow_instance=instance,
        contract=instance.contract,
        document_version=document_version,
        provider_name=(provider_name or '').strip(),
        created_by=actor,
    )
    _audit(actor=actor, organization=instance.organization, model_name='SignaturePacket', object_id=packet.pk,
           event_type='signature.packet.created',
           changes={'workflow_instance_id': instance.pk, 'document_version_id': document_version.pk}, request=request)
    return packet


@transaction.atomic
def dispatch_signature_packet(*, packet, actor, provider_reference='', request=None):
    """Record dispatch intent only; no provider is selected or contacted here."""
    _assert_member(actor=actor, organization=packet.organization)
    _assert_contract_edit(
        actor=actor, contract=packet.contract, request=request,
        model_name='SignaturePacket', object_id=packet.pk,
    )
    if packet.status != packet.Status.PENDING:
        raise CanonicalWorkflowError('Only a pending signature packet can be dispatched.')
    if _latest_final_document_version(packet.workflow_instance).pk != packet.document_version_id:
        raise CanonicalWorkflowError('Cannot dispatch a packet for a superseded document version.')
    packet.status = packet.Status.SENT
    packet.provider_reference = (provider_reference or '').strip()
    packet.sent_at = timezone.now()
    packet.save(update_fields=['status', 'provider_reference', 'sent_at'])
    _audit(actor=actor, organization=packet.organization, model_name='SignaturePacket', object_id=packet.pk,
           event_type='signature.dispatch.succeeded',
           changes={'document_version_id': packet.document_version_id}, request=request)
    return packet


@transaction.atomic
def record_signature_evidence(*, packet, actor, event_id: str, event_type: str, evidence_payload=None, request=None):
    from contracts.models import SignatureEvidence

    _assert_member(actor=actor, organization=packet.organization)
    _assert_contract_edit(
        actor=actor, contract=packet.contract, request=request,
        model_name='SignaturePacket', object_id=packet.pk,
    )
    existing = SignatureEvidence.objects.filter(packet=packet, event_id=(event_id or '').strip()).first()
    if existing is not None:
        return existing
    if packet.status not in {packet.Status.SENT, packet.Status.PENDING}:
        raise CanonicalWorkflowError('Signature evidence cannot be appended to a terminal packet.')
    if _latest_final_document_version(packet.workflow_instance).pk != packet.document_version_id:
        raise CanonicalWorkflowError('Signature evidence cannot be bound to a superseded document version.')
    payload = evidence_payload or {}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode('utf-8')).hexdigest()
    evidence = SignatureEvidence.objects.create(
        packet=packet, organization=packet.organization, event_id=(event_id or '').strip(),
        event_type=(event_type or '').strip(), provider_name=packet.provider_name,
        payload_hash=digest, evidence_payload=payload, recorded_by=actor,
    )
    if evidence.event_type.lower() in {'signed', 'completed'}:
        packet.status = packet.Status.SIGNED
        packet.save(update_fields=['status'])
    _audit(actor=actor, organization=packet.organization, model_name='SignatureEvidence', object_id=evidence.pk,
           event_type='signature.evidence.recorded',
           changes={'packet_id': packet.pk, 'document_version_id': packet.document_version_id,
                    'evidence_event_type': evidence.event_type}, request=request)
    return evidence


@transaction.atomic
def promote_contract_record(*, instance, packet, actor, request=None):
    from contracts.models import ApprovalRequirement, ContractRecord, SignatureEvidence

    _assert_member(actor=actor, organization=instance.organization)
    _assert_contract_edit(
        actor=actor, contract=instance.contract, request=request,
        model_name='WorkflowInstance', object_id=instance.pk,
    )
    _assert_same_organization(instance, packet, instance.contract)
    if packet.workflow_instance_id != instance.pk or packet.status != packet.Status.SIGNED:
        raise CanonicalWorkflowError('Contract Record promotion requires a completed signature packet for this instance.')
    if not SignatureEvidence.objects.filter(packet=packet).exists():
        raise CanonicalWorkflowError('Contract Record promotion requires retained signature evidence.')
    requirements = ApprovalRequirement.objects.filter(workflow_instance=instance)
    if not requirements.exists() or requirements.exclude(
        status=ApprovalRequirement.Status.SATISFIED, document_version=packet.document_version,
    ).exists():
        raise CanonicalWorkflowError('Contract Record promotion requires approvals bound to the signed document version.')
    record, created = ContractRecord.objects.get_or_create(
        contract=instance.contract,
        defaults={
            'organization': instance.organization,
            'workflow_instance': instance,
            'workflow_version': instance.workflow_version,
            'document_version': packet.document_version,
            'signature_packet': packet,
            'provenance_snapshot': {
                'workflow_definition_id': instance.definition_id,
                'workflow_version_id': instance.workflow_version_id,
                'workflow_version_checksum': instance.workflow_version.configuration_checksum,
                'workflow_instance_id': instance.pk,
                'document_version_id': packet.document_version_id,
                'signature_packet_id': packet.pk,
                'approval_requirement_ids': list(requirements.values_list('pk', flat=True)),
            },
            'created_by': actor,
        },
    )
    if not created:
        return record
    instance.status = instance.Status.COMPLETED
    instance.completed_at = timezone.now()
    instance.save(update_fields=['status', 'completed_at'])
    _audit(actor=actor, organization=instance.organization, model_name='ContractRecord', object_id=record.pk,
           event_type='contract.record.promoted', changes={'workflow_instance_id': instance.pk,
                                                           'document_version_id': packet.document_version_id}, request=request)
    _audit(actor=actor, organization=instance.organization, model_name='ContractRecord', object_id=record.pk,
           event_type='contract.record.created', changes={'workflow_instance_id': instance.pk,
                                                          'document_version_id': packet.document_version_id}, request=request)
    return record


@transaction.atomic
def archive_contract_record(*, record, actor, request=None):
    _assert_manage(actor=actor, organization=record.organization)
    if record.archived_at:
        return record
    record.archived_at = timezone.now()
    record.archived_by = actor
    record.save(update_fields=['archived_at', 'archived_by'], allow_archive=True)
    _audit(actor=actor, organization=record.organization, model_name='ContractRecord', object_id=record.pk,
           event_type='contract.record.archived', changes={'workflow_instance_id': record.workflow_instance_id}, request=request)
    return record


def export_contract_record(*, record, actor, request=None) -> dict:
    from contracts.permissions import ContractAction, can_access_contract_action

    if not can_access_contract_action(actor, record.contract, ContractAction.VIEW):
        _audit(actor=actor, organization=record.organization, model_name='ContractRecord', object_id=record.pk,
               event_type='contract.record.export_blocked', outcome='blocked', request=request)
        raise PermissionDenied('You do not have access to this contract record.')
    _audit(actor=actor, organization=record.organization, model_name='ContractRecord', object_id=record.pk,
           event_type='contract.record.exported', changes={'document_version_id': record.document_version_id}, request=request)
    return {
        'record_id': record.pk,
        'contract_id': record.contract_id,
        'workflow_instance_id': record.workflow_instance_id,
        'workflow_version_id': record.workflow_version_id,
        'document_version_id': record.document_version_id,
        'signature_packet_id': record.signature_packet_id,
        'provenance': record.provenance_snapshot,
    }
