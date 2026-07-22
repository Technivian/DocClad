"""PAR-DOC-001 — canonical Document Version creation, immutability, and audit."""

from __future__ import annotations

import os
import uuid
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

EVENT_VERSION_CREATED = 'document.version.created'
EVENT_VERSION_SUPERSEDED = 'document.superseded'  # existing canonical semantics
EVENT_VERSION_MARKED_FINAL = 'document.version.marked_final'
# Legacy equivalent retained in some paths:
LEGACY_VERSION_CREATED = 'document_version_created'

IMMUTABLE_VERSION_FIELDS = frozenset({
    'file',
    'file_hash',
    'file_size',
    'mime_type',
    'original_filename',
    'version_number',
    'source',
    'uploaded_by_id',
    'derived_from_id',
    'logical_document_id',
    'version_locked_at',
    'checksum_missing',
    'organization_id',
    'contract_id',
})

IMMUTABLE_DOCUMENT_FIELDS = frozenset({
    'file',
    'file_hash',
    'file_size',
    'mime_type',
    'version',
    'parent_document_id',
    'logical_document_id',
    'uploaded_by_id',
    'version_locked_at',
    'version_source',
})


class DocumentVersionError(ValidationError):
    """Raised when version rules are violated."""


def resolve_logical_document(document) -> object:
    """Return the logical Document identity root for a version row."""
    if document is None:
        raise DocumentVersionError('Document is required.')
    if getattr(document, 'logical_document_id', None):
        return document.logical_document
    if getattr(document, 'parent_document_id', None) and document.parent_document_id:
        root = document.parent_document
        while getattr(root, 'parent_document_id', None) and root.parent_document_id:
            root = root.parent_document
        return root
    return document


def _assert_tenant_access(*, actor, organization, contract=None) -> None:
    if actor is None or not getattr(actor, 'is_authenticated', False):
        return
    from contracts.tenancy import get_user_organization

    actor_org = get_user_organization(actor)
    actor_org_id = getattr(actor_org, 'pk', None)
    org_id = getattr(organization, 'pk', None) if organization is not None else None
    if org_id and actor_org_id and org_id != actor_org_id:
        raise PermissionDenied('Cross-tenant document version operations are forbidden.')
    if contract is not None and contract.organization_id and actor_org_id:
        if contract.organization_id != actor_org_id:
            raise PermissionDenied('Cross-tenant contract document attachment is forbidden.')


@transaction.atomic
def allocate_version_number(logical_document) -> int:
    from contracts.models import Document, DocumentVersion

    logical_id = logical_document.pk
    Document.objects.select_for_update().filter(pk=logical_id).first()
    max_doc = (
        Document.objects.filter(logical_document_id=logical_id)
        .order_by('-version')
        .values_list('version', flat=True)
        .first()
    )
    max_ver = (
        DocumentVersion.objects.filter(logical_document_id=logical_id)
        .order_by('-version_number')
        .values_list('version_number', flat=True)
        .first()
    )
    current = max(max_doc or 0, max_ver or 0, logical_document.version or 0)
    return int(current) + 1


def _checksum_for_file(file_field) -> tuple[str, bool]:
    if not file_field:
        return '', True
    try:
        import hashlib

        hasher = hashlib.sha256()
        for chunk in file_field.chunks():
            hasher.update(chunk)
        if hasattr(file_field, 'seek'):
            file_field.seek(0)
        return hasher.hexdigest(), False
    except Exception:
        return '', True


def _emit_version_audit(*, event_type: str, document, version_row, actor, request=None, changes: dict | None = None):
    from contracts.middleware import log_action
    from contracts.models import AuditLog

    log_action(
        actor,
        AuditLog.Action.CREATE,
        'Document',
        document.pk,
        str(document)[:300],
        organization=getattr(document, 'organization', None),
        request=request,
        event_type=event_type,
        actor_type=AuditLog.ActorType.SYSTEM if actor is None else AuditLog.ActorType.HUMAN,
        changes=changes or {},
    )


@transaction.atomic
def create_document_version(
    *,
    organization,
    title: str,
    document_type: str,
    status: str,
    contract=None,
    matter=None,
    client=None,
    description: str = '',
    file=None,
    uploaded_by=None,
    actor=None,
    source: str = 'manual_upload',
    logical_document=None,
    derived_from_document=None,
    parent_document=None,
    tags: str = '',
    is_privileged: bool = False,
    is_confidential: bool = False,
    share_with_counterparty: bool = False,
    request=None,
    supersede_prior: bool = True,
) -> tuple[object, object]:
    """Create a logical Document version row and immutable DocumentVersion record."""
    from contracts.models import Document, DocumentVersion

    actor = actor or uploaded_by
    _assert_tenant_access(actor=actor, organization=organization, contract=contract)

    logical = logical_document or (resolve_logical_document(derived_from_document) if derived_from_document else None)
    derived_from_version = None
    if derived_from_document is not None:
        logical = resolve_logical_document(derived_from_document)
        derived_from_version = getattr(derived_from_document, 'canonical_version', None)

    if logical is None:
        # First version — logical identity will be assigned after create.
        version_number = 1
    else:
        version_number = allocate_version_number(logical)

    parent = parent_document
    if parent is None and derived_from_document is not None:
        parent = derived_from_document.parent_document or derived_from_document

    file_hash, checksum_missing = _checksum_for_file(file) if file else ('', True)
    original_filename = os.path.basename(getattr(file, 'name', '') or '') if file else ''

    document = Document(
        organization=organization,
        title=title,
        document_type=document_type,
        status=status,
        description=description,
        file=file,
        contract=contract,
        matter=matter,
        client=client,
        uploaded_by=uploaded_by,
        tags=tags,
        is_privileged=is_privileged,
        is_confidential=is_confidential,
        share_with_counterparty=share_with_counterparty,
        version=version_number,
        parent_document=parent,
        logical_document=logical,
        version_source=source,
    )
    if file:
        document.file_size = getattr(file, 'size', None)
        document.mime_type = getattr(file, 'content_type', '') or ''
        document.file_hash = file_hash
    document.version_locked_at = timezone.now()
    document.save(skip_version_immutability=True)

    if logical is None:
        document.logical_document = document
        document.save(update_fields=['logical_document', 'updated_at'], skip_version_immutability=True)
        logical = document

    version_row = DocumentVersion.objects.create(
        organization=organization,
        logical_document=logical,
        document_row=document,
        version_number=version_number,
        title=title,
        document_type=document_type,
        status=status,
        description=description,
        file=document.file,
        file_size=document.file_size,
        mime_type=document.mime_type or '',
        file_hash=document.file_hash or '',
        original_filename=original_filename,
        source=source,
        uploaded_by=uploaded_by,
        derived_from=derived_from_version,
        contract=contract,
        matter=matter,
        client=client,
        checksum_missing=checksum_missing,
        version_locked_at=timezone.now(),
    )

    if derived_from_document and supersede_prior and derived_from_document.status in {
        Document.Status.FINAL,
        Document.Status.EXECUTED,
    }:
        from contracts.services.document_supersession import supersede_document

        supersede_document(
            derived_from_document,
            document,
            actor=actor,
            reason='superseded by new document version',
            source=source,
            request=request,
            organization=organization,
        )

    snap = version_snapshot(version_row)
    _emit_version_audit(
        event_type=EVENT_VERSION_CREATED,
        document=document,
        version_row=version_row,
        actor=actor,
        request=request,
        changes={
            'event': EVENT_VERSION_CREATED,
            'equivalent_event': LEGACY_VERSION_CREATED,
            'source': source,
            'version': version_snapshot(version_row),
            'logical_document_id': logical.pk,
        },
    )
    if status in {Document.Status.FINAL, Document.Status.EXECUTED}:
        _emit_version_audit(
            event_type=EVENT_VERSION_MARKED_FINAL,
            document=document,
            version_row=version_row,
            actor=actor,
            request=request,
            changes={'event': EVENT_VERSION_MARKED_FINAL, 'status': status, 'version': snap},
        )
    return document, version_row


def resolve_canonical_version(document) -> object | None:
    """Return the immutable DocumentVersion for a Document row when present."""
    if document is None or not getattr(document, 'pk', None):
        return None
    try:
        return document.canonical_version
    except Exception:
        from contracts.models import DocumentVersion

        return DocumentVersion.objects.filter(document_row_id=document.pk).first()


def bind_signature_document_version(signature_request) -> None:
    """Pin SignatureRequest to the exact DocumentVersion for its document row."""
    document = getattr(signature_request, 'document', None)
    if document is None:
        return
    version = resolve_canonical_version(document)
    if version is None:
        version = ensure_canonical_version_for_document(document)
    if version is not None and signature_request.document_version_id != version.pk:
        signature_request.document_version = version


def version_snapshot(version_row) -> dict[str, Any]:
    return {
        'id': version_row.pk,
        'logical_document_id': version_row.logical_document_id,
        'document_row_id': version_row.document_row_id,
        'version_number': version_row.version_number,
        'file_hash': version_row.file_hash or '',
        'checksum_missing': version_row.checksum_missing,
        'source': version_row.source or '',
        'uploaded_by_id': version_row.uploaded_by_id,
        'created_at': version_row.created_at.isoformat() if version_row.created_at else None,
        'original_filename': version_row.original_filename or '',
    }


def ensure_canonical_version_for_document(document) -> object | None:
    """Create a DocumentVersion row for legacy direct Document saves (idempotent)."""
    from contracts.models import DocumentVersion

    if not document.pk:
        return None
    if hasattr(document, 'canonical_version'):
        try:
            existing = document.canonical_version
            if existing is not None:
                return existing
        except DocumentVersion.DoesNotExist:
            pass
    if DocumentVersion.objects.filter(document_row_id=document.pk).exists():
        return DocumentVersion.objects.get(document_row_id=document.pk)

    logical = resolve_logical_document(document)
    if document.logical_document_id is None:
        document.logical_document = logical
        document.save(update_fields=['logical_document', 'updated_at'], skip_version_immutability=True)

    import os
    original_filename = os.path.basename(document.file.name) if document.file else ''
    checksum_missing = not bool(document.file_hash)
    source = document.version_source or DocumentVersion.Source.LEGACY_UNKNOWN
    if not document.version_locked_at:
        document.version_locked_at = timezone.now()
        document.save(update_fields=['version_locked_at', 'updated_at'], skip_version_immutability=True)

    return DocumentVersion.objects.create(
        organization=document.organization,
        logical_document=logical,
        document_row=document,
        version_number=document.version or 1,
        title=document.title,
        document_type=document.document_type,
        status=document.status,
        description=document.description or '',
        file=document.file,
        file_size=document.file_size,
        mime_type=document.mime_type or '',
        file_hash=document.file_hash or '',
        original_filename=original_filename,
        source=source,
        uploaded_by=document.uploaded_by,
        contract=document.contract,
        matter=document.matter,
        client=document.client,
        checksum_missing=checksum_missing,
        version_locked_at=document.version_locked_at or timezone.now(),
        skip_version_immutability=True,
    )


def assert_document_version_immutable(instance, *, previous: dict | None) -> None:
    if previous is None or not previous.get('version_locked_at'):
        return
    for field in IMMUTABLE_DOCUMENT_FIELDS:
        old = previous.get(field)
        new = getattr(instance, field, None)
        if field.endswith('_id'):
            new = getattr(instance, field.replace('_id', '') + '_id', None) if hasattr(instance, field) else new
        if old != new:
            raise DocumentVersionError(
                f'Document field "{field}" is immutable after version lock. Create a new version instead.'
            )


def assert_document_version_row_immutable(instance, *, previous: dict | None) -> None:
    if previous is None or not previous.get('version_locked_at'):
        return
    for field in IMMUTABLE_VERSION_FIELDS:
        old = previous.get(field)
        new = getattr(instance, field, None)
        if old != new:
            raise DocumentVersionError(
                f'DocumentVersion field "{field}" is immutable after lock.'
            )
