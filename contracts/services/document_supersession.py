"""Governed document supersession with immutable audit evidence."""

from __future__ import annotations

import uuid

from django.core.exceptions import PermissionDenied, ValidationError


class DocumentSupersessionError(ValidationError):
    """Raised when a document cannot be superseded."""


def supersede_document(
    previous,
    replacement,
    *,
    actor=None,
    reason: str = '',
    source: str = '',
    request=None,
    correlation_id: str = '',
    organization=None,
):
    """Mark ``previous`` as SUPERSEDED after ``replacement`` exists.

    Emits ``document.superseded`` (immutable audit) with actor, contract,
    previous/replacement ids, statuses, reason/source, and correlation context.
    Filename or upload alone is not treated as supersession evidence — callers
    must invoke this only when a real replacement document row exists.
    """
    from contracts.middleware import log_action
    from contracts.models import AuditLog, Document
    from contracts.tenancy import get_user_organization

    if previous is None or replacement is None:
        raise DocumentSupersessionError('Previous and replacement documents are required.')
    if not getattr(previous, 'pk', None) or not getattr(replacement, 'pk', None):
        raise DocumentSupersessionError('Both documents must be persisted before supersession.')
    if previous.pk == replacement.pk:
        raise DocumentSupersessionError('A document cannot supersede itself.')

    prev_org_id = getattr(previous, 'organization_id', None)
    repl_org_id = getattr(replacement, 'organization_id', None)
    if prev_org_id and repl_org_id and prev_org_id != repl_org_id:
        raise DocumentSupersessionError('Documents must belong to the same organization.')

    if actor is not None and getattr(actor, 'is_authenticated', False):
        actor_org = organization or get_user_organization(actor)
        actor_org_id = getattr(actor_org, 'pk', None)
        if actor_org_id and prev_org_id and actor_org_id != prev_org_id:
            raise PermissionDenied('Cross-tenant document supersession is forbidden.')

    if previous.status == Document.Status.SUPERSEDED:
        return previous  # idempotent

    if previous.status not in {
        Document.Status.FINAL,
        Document.Status.EXECUTED,
        Document.Status.DRAFT,
    }:
        raise DocumentSupersessionError(
            f'Cannot supersede document in status {previous.status}.'
        )

    old_status = previous.status
    previous.status = Document.Status.SUPERSEDED
    previous.save(update_fields=['status', 'updated_at'])

    corr = (correlation_id or '').strip()
    if not corr and request is not None:
        corr = str(getattr(request, 'request_id', '') or '')
    if not corr:
        corr = str(uuid.uuid4())

    org = organization or getattr(previous, 'organization', None) or getattr(replacement, 'organization', None)
    resolved_actor_type = (
        AuditLog.ActorType.SYSTEM if actor is None else AuditLog.ActorType.HUMAN
    )
    log_action(
        actor,
        AuditLog.Action.UPDATE,
        'Document',
        object_id=previous.pk,
        object_repr=str(previous)[:300],
        organization=org,
        request=request,
        event_type='document.superseded',
        actor_type=resolved_actor_type,
        changes={
            'event': 'document.superseded',
            'contract_id': previous.contract_id or replacement.contract_id,
            'previous_document_id': previous.pk,
            'replacement_document_id': replacement.pk,
            'previous_document_status': old_status,
            'replacement_document_status': replacement.status,
            'previous_version': previous.version,
            'replacement_version': replacement.version,
            'from': old_status,
            'to': Document.Status.SUPERSEDED,
            'reason': (reason or '')[:300],
            'source': (source or '')[:120],
            'correlation_id': corr[:64],
        },
    )
    return previous
