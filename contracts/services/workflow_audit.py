from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable, Optional

from django.db.models import Q

from contracts.middleware import log_action
from contracts.models import AuditLog, Workflow, WorkflowStep, WorkflowTemplate, WorkflowTemplateStep


def _display_user(user) -> str:
    if not user:
        return 'System'
    full_name = (getattr(user, 'get_full_name', lambda: '')() or '').strip()
    return full_name or getattr(user, 'username', None) or str(user)


def _display_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, 'isoformat'):
        try:
            return value.isoformat()
        except TypeError:
            pass
    if hasattr(value, 'get_full_name') and hasattr(value, 'username'):
        full_name = (value.get_full_name() or '').strip()
        return full_name or value.username
    return value


def build_field_changes(before: Any, after: Any, fields: Iterable[str]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    for field_name in fields:
        before_value = _display_value(getattr(before, field_name, None) if before is not None else None)
        after_value = _display_value(getattr(after, field_name, None) if after is not None else None)
        if before_value != after_value:
            changes.append({
                'field': field_name,
                'from': before_value,
                'to': after_value,
            })
    return changes


def _build_payload(event: str, *, organization_id: Optional[int] = None, **extra: Any) -> dict[str, Any]:
    payload = {'event': event}
    if organization_id is not None:
        payload['organization_id'] = organization_id
    payload.update(extra)
    return payload


def _log(
    user,
    action: str,
    model_name: str,
    object_id: Optional[int],
    object_repr: str,
    *,
    changes: Optional[dict[str, Any]] = None,
    request=None,
):
    log_action(
        user,
        action,
        model_name,
        object_id=object_id,
        object_repr=object_repr,
        changes=changes,
        request=request,
    )


def log_workflow_created(workflow: Workflow, user, request=None):
    _log(
        user,
        AuditLog.Action.CREATE,
        'Workflow',
        workflow.pk,
        workflow.title,
        changes=_build_payload(
            'workflow_created',
            organization_id=workflow.organization_id,
            workflow_id=workflow.pk,
            workflow_title=workflow.title,
            contract_id=workflow.contract_id,
            contract_title=getattr(workflow.contract, 'title', None),
            template_id=workflow.template_id,
            template_name=getattr(workflow.template, 'name', None),
            status=workflow.status,
        ),
        request=request,
    )


def log_workflow_step_added(step: WorkflowStep, user, request=None):
    _log(
        user,
        AuditLog.Action.CREATE,
        'WorkflowStep',
        step.pk,
        step.name,
        changes=_build_payload(
            'workflow_step_added',
            organization_id=step.workflow.organization_id,
            workflow_id=step.workflow_id,
            workflow_title=step.workflow.title,
            step_name=step.name,
            status=step.status,
            order=step.order,
            assigned_to=_display_user(step.assigned_to),
            due_date=_display_value(step.due_date),
        ),
        request=request,
    )


def log_workflow_step_completed(
    step: WorkflowStep,
    user,
    request=None,
    previous_status: Optional[str] = None,
    extra_changes: Optional[list[dict[str, Any]]] = None,
):
    _log(
        user,
        AuditLog.Action.UPDATE,
        'WorkflowStep',
        step.pk,
        step.name,
        changes=_build_payload(
            'workflow_step_completed',
            organization_id=step.workflow.organization_id,
            workflow_id=step.workflow_id,
            workflow_title=step.workflow.title,
            step_name=step.name,
            status_from=previous_status,
            status_to=step.status,
            completed_at=_display_value(step.completed_at),
            field_changes=extra_changes or [],
        ),
        request=request,
    )


def log_workflow_step_updated(step: WorkflowStep, user, changes, request=None):
    _log(
        user,
        AuditLog.Action.UPDATE,
        'WorkflowStep',
        step.pk,
        step.name,
        changes=_build_payload(
            'workflow_step_updated',
            organization_id=step.workflow.organization_id,
            workflow_id=step.workflow_id,
            workflow_title=step.workflow.title,
            step_name=step.name,
            field_changes=changes or [],
        ),
        request=request,
    )


def log_workflow_step_escalated(
    step: WorkflowStep,
    user=None,
    request=None,
    extra_changes: Optional[list[dict[str, Any]]] = None,
):
    _log(
        user,
        AuditLog.Action.UPDATE,
        'WorkflowStep',
        step.pk,
        step.name,
        changes=_build_payload(
            'workflow_step_escalated',
            organization_id=step.workflow.organization_id,
            workflow_id=step.workflow_id,
            workflow_title=step.workflow.title,
            step_name=step.name,
            status_to=step.status,
            escalated_at=_display_value(step.escalated_at),
            field_changes=extra_changes or [],
        ),
        request=request,
    )


def log_workflow_template_created(template: WorkflowTemplate, user, request=None):
    _log(
        user,
        AuditLog.Action.CREATE,
        'WorkflowTemplate',
        template.pk,
        template.name,
        changes=_build_payload(
            'workflow_template_created',
            organization_id=template.organization_id,
            template_id=template.pk,
            template_name=template.name,
            version=template.version,
            category=template.category,
            is_active=template.is_active,
        ),
        request=request,
    )


def log_workflow_template_updated(template: WorkflowTemplate, user, changes, request=None):
    _log(
        user,
        AuditLog.Action.UPDATE,
        'WorkflowTemplate',
        template.pk,
        template.name,
        changes=_build_payload(
            'workflow_template_updated',
            organization_id=template.organization_id,
            template_id=template.pk,
            template_name=template.name,
            field_changes=changes or [],
        ),
        request=request,
    )


def log_workflow_template_cloned(source_template: WorkflowTemplate, new_template: WorkflowTemplate, user, request=None):
    _log(
        user,
        AuditLog.Action.CREATE,
        'WorkflowTemplate',
        new_template.pk,
        new_template.name,
        changes=_build_payload(
            'workflow_template_cloned',
            organization_id=new_template.organization_id,
            source_template_id=source_template.pk,
            source_template_name=source_template.name,
            source_template_version=source_template.version,
            new_template_id=new_template.pk,
            new_template_name=new_template.name,
            new_template_version=new_template.version,
        ),
        request=request,
    )


def log_workflow_template_restored(source_template: WorkflowTemplate, restored_template: WorkflowTemplate, user, request=None):
    _log(
        user,
        AuditLog.Action.CREATE,
        'WorkflowTemplate',
        restored_template.pk,
        restored_template.name,
        changes=_build_payload(
            'workflow_template_restored',
            organization_id=restored_template.organization_id,
            restored_from_template_id=source_template.pk,
            restored_from_template_name=source_template.name,
            restored_from_template_version=source_template.version,
            restored_template_id=restored_template.pk,
            restored_template_name=restored_template.name,
            restored_template_version=restored_template.version,
        ),
        request=request,
    )


def log_workflow_template_step_added(template_step: WorkflowTemplateStep, user, request=None):
    _log(
        user,
        AuditLog.Action.CREATE,
        'WorkflowTemplateStep',
        template_step.pk,
        template_step.name,
        changes=_build_payload(
            'workflow_template_step_added',
            organization_id=template_step.template.organization_id,
            template_id=template_step.template_id,
            template_name=template_step.template.name,
            step_name=template_step.name,
            step_kind=template_step.step_kind,
            order=template_step.order,
            assignee_role=template_step.assignee_role or None,
            specific_assignee_id=template_step.specific_assignee_id,
            sla_hours=template_step.sla_hours,
            escalation_after_hours=template_step.escalation_after_hours,
        ),
        request=request,
    )


def log_workflow_template_step_updated(template_step: WorkflowTemplateStep, user, changes=None, request=None):
    _log(
        user,
        AuditLog.Action.UPDATE,
        'WorkflowTemplateStep',
        template_step.pk,
        template_step.name,
        changes=_build_payload(
            'workflow_template_step_updated',
            organization_id=template_step.template.organization_id,
            template_id=template_step.template_id,
            template_name=template_step.template.name,
            step_name=template_step.name,
            step_kind=template_step.step_kind,
            order=template_step.order,
            changes=changes or {},
        ),
        request=request,
    )


def log_workflow_template_step_deleted(template_step_data: dict[str, Any], template: WorkflowTemplate, user, request=None):
    _log(
        user,
        AuditLog.Action.DELETE,
        'WorkflowTemplateStep',
        template_step_data.get('step_id'),
        template_step_data.get('step_name', ''),
        changes=_build_payload(
            'workflow_template_step_deleted',
            organization_id=template.organization_id,
            template_id=template.pk,
            template_name=template.name,
            **template_step_data,
        ),
        request=request,
    )


def log_workflow_template_reordered(template: WorkflowTemplate, user, changes, request=None):
    _log(
        user,
        AuditLog.Action.UPDATE,
        'WorkflowTemplate',
        template.pk,
        template.name,
        changes=_build_payload(
            'workflow_template_reordered',
            organization_id=template.organization_id,
            template_id=template.pk,
            template_name=template.name,
            field_changes=changes or [],
        ),
        request=request,
    )


def log_workflow_template_publish_toggled(template: WorkflowTemplate, user, old_status, new_status, request=None):
    _log(
        user,
        AuditLog.Action.UPDATE,
        'WorkflowTemplate',
        template.pk,
        template.name,
        changes=_build_payload(
            'workflow_template_publish_toggled',
            organization_id=template.organization_id,
            template_id=template.pk,
            template_name=template.name,
            old_status=old_status,
            new_status=new_status,
            field_changes=[{
                'field': 'is_active',
                'from': old_status,
                'to': new_status,
            }],
        ),
        request=request,
    )


def log_workflow_preview_run(template: WorkflowTemplate, user, preview_data, request=None):
    _log(
        user,
        AuditLog.Action.VIEW,
        'WorkflowTemplatePreview',
        template.pk,
        template.name,
        changes=_build_payload(
            'workflow_preview_run',
            organization_id=template.organization_id,
            template_id=template.pk,
            template_name=template.name,
            **(preview_data or {}),
        ),
        request=request,
    )


def _workflow_audit_queryset(workflow: Workflow):
    step_ids = list(WorkflowStep.objects.filter(workflow=workflow).values_list('pk', flat=True))
    queryset = AuditLog.objects.select_related('user').filter(
        Q(model_name='Workflow', object_id=workflow.pk)
        | Q(model_name='WorkflowStep', object_id__in=step_ids)
        | Q(model_name='WorkflowStep', changes__workflow_id=workflow.pk)
        | Q(model_name='WorkflowStep', changes__workflow_title=workflow.title)
    )
    return queryset


def _workflow_template_audit_queryset(template: WorkflowTemplate):
    step_ids = list(WorkflowTemplateStep.objects.filter(template=template).values_list('pk', flat=True))
    queryset = AuditLog.objects.select_related('user').filter(
        Q(model_name='WorkflowTemplate', object_id=template.pk)
        | Q(model_name='WorkflowTemplate', changes__template_id=template.pk)
        | Q(model_name='WorkflowTemplate', changes__source_template_id=template.pk)
        | Q(model_name='WorkflowTemplate', changes__restored_from_template_id=template.pk)
        | Q(model_name='WorkflowTemplateStep', object_id__in=step_ids)
        | Q(model_name='WorkflowTemplateStep', changes__template_id=template.pk)
        | Q(model_name='WorkflowTemplatePreview', object_id=template.pk)
        | Q(model_name='WorkflowTemplatePreview', changes__template_id=template.pk)
    )
    return queryset


def _action_badge_class(action: str) -> str:
    return {
        AuditLog.Action.CREATE: 'badge-green',
        AuditLog.Action.UPDATE: 'badge-blue',
        AuditLog.Action.DELETE: 'badge-red',
        AuditLog.Action.VIEW: 'badge-gray',
        AuditLog.Action.APPROVE: 'badge-green',
        AuditLog.Action.REJECT: 'badge-red',
    }.get(action, 'badge-gray')


def _summarize_changes(log: AuditLog) -> str:
    changes = log.changes or {}
    event = changes.get('event')
    if event == 'workflow_created':
        return 'Workflow created'
    if event == 'workflow_step_added':
        return f"Step added to {changes.get('workflow_title') or log.object_repr}"
    if event == 'workflow_step_completed':
        return f"Step completed: {changes.get('step_name') or log.object_repr}"
    if event == 'workflow_step_updated':
        return f"Step updated: {changes.get('step_name') or log.object_repr}"
    if event == 'workflow_step_escalated':
        return f"Step escalated: {changes.get('step_name') or log.object_repr}"
    if event == 'workflow_template_created':
        return 'Template created'
    if event == 'workflow_template_updated':
        return 'Template updated'
    if event == 'workflow_template_cloned':
        return f"Cloned to v{changes.get('new_template_version')}"
    if event == 'workflow_template_restored':
        return f"Restored as v{changes.get('restored_template_version')}"
    if event == 'workflow_template_step_added':
        return f"Template step added: {changes.get('step_name') or log.object_repr}"
    if event == 'workflow_template_step_deleted':
        return f"Template step deleted: {changes.get('step_name') or log.object_repr}"
    if event == 'workflow_template_reordered':
        return 'Template steps reordered'
    if event == 'workflow_template_publish_toggled':
        return 'Published template' if changes.get('new_status') else 'Unpublished template'
    if event == 'workflow_preview_run':
        return 'Template preview run'
    if event == 'workflow_template_step_updated':
        return f"Template step updated: {changes.get('step_name') or log.object_repr}"
    if event == 'workflow_template_scenario_saved':
        return f"Saved scenario: {changes.get('scenario_name') or log.object_repr}"
    if event == 'workflow_template_audit_exported':
        return 'Audit log exported'
    return log.object_repr or log.model_name


def _changed_field_texts(log: AuditLog) -> list[str]:
    changes = log.changes or {}
    field_changes = changes.get('field_changes') or []
    rendered = []
    for item in field_changes:
        field = item.get('field')
        before = item.get('from')
        after = item.get('to')
        if field:
            rendered.append(f"{field}: {before} → {after}")
    return rendered


def build_audit_feed(logs: Iterable[AuditLog]) -> list[dict[str, Any]]:
    feed = []
    for log in logs:
        feed.append({
            'log': log,
            'timestamp': log.timestamp,
            'actor': _display_user(log.user),
            'action': log.get_action_display(),
            'action_class': _action_badge_class(log.action),
            'summary': _summarize_changes(log),
            'changed_fields': _changed_field_texts(log),
        })
    return feed


def get_workflow_audit_feed(workflow: Workflow, limit: Optional[int] = 8) -> list[dict[str, Any]]:
    queryset = _workflow_audit_queryset(workflow).order_by('-timestamp', '-pk')
    if limit is not None:
        queryset = queryset[:limit]
    return build_audit_feed(queryset)


def get_workflow_template_audit_feed(template: WorkflowTemplate, limit: Optional[int] = 8) -> list[dict[str, Any]]:
    queryset = _workflow_template_audit_queryset(template).order_by('-timestamp', '-pk')
    if limit is not None:
        queryset = queryset[:limit]
    return build_audit_feed(queryset)


def template_version_provenance(template: WorkflowTemplate) -> dict[str, Any]:
    """Best-effort created-by / published-at from the template audit trail."""
    created_by = None
    published_by = None
    published_at = None
    logs = list(
        _workflow_template_audit_queryset(template)
        .select_related('user')
        .order_by('timestamp', 'pk')[:80]
    )
    for log in logs:
        changes = log.changes or {}
        event = changes.get('event')
        if created_by is None and log.user_id and event in {
            'workflow_template_created',
            'workflow_template_cloned',
            'workflow_template_restored',
        }:
            created_by = _display_user(log.user)
        if event == 'workflow_template_publish_toggled' and changes.get('new_status'):
            published_at = log.timestamp
            if log.user_id:
                published_by = _display_user(log.user)
    if created_by is None:
        for log in logs:
            if log.user_id:
                created_by = _display_user(log.user)
                break
    return {
        'created_by': created_by,
        'published_by': published_by,
        'published_at': published_at,
    }


def build_workflow_template_audit_rows(
    template: WorkflowTemplate,
    *,
    actor: str = '',
    event_type: str = '',
    version: str = '',
    date_from=None,
    date_to=None,
    limit: Optional[int] = 200,
) -> list[dict[str, Any]]:
    """Audit-trail workspace rows with previous/new values and filters."""
    queryset = _workflow_template_audit_queryset(template).select_related('user').order_by('-timestamp', '-pk')
    if actor:
        queryset = queryset.filter(
            Q(user__username__icontains=actor)
            | Q(user__first_name__icontains=actor)
            | Q(user__last_name__icontains=actor)
            | Q(user__email__icontains=actor)
        )
    if event_type:
        event_needles = [part.strip() for part in str(event_type).split(',') if part.strip()]
        event_q = Q()
        for needle in event_needles:
            event_q |= (
                Q(event_type__icontains=needle)
                | Q(action__iexact=needle)
                | Q(changes__event__icontains=needle)
            )
        queryset = queryset.filter(event_q)
    if date_from:
        queryset = queryset.filter(timestamp__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(timestamp__date__lte=date_to)
    if limit is not None:
        queryset = queryset[:limit]

    rows = []
    version_needle = (version or '').strip().lstrip('vV')
    for log in queryset:
        changes = log.changes or {}
        field_changes = changes.get('field_changes') or changes.get('changes') or []
        if isinstance(field_changes, dict):
            # Nested "changes" payload from step updates.
            nested = field_changes.get('field_changes') if isinstance(field_changes, dict) else None
            field_changes = nested or [
                {'field': key, 'from': value.get('from') if isinstance(value, dict) else None, 'to': value.get('to') if isinstance(value, dict) else value}
                for key, value in (field_changes.items() if isinstance(field_changes, dict) else [])
            ]
        previous_parts = []
        new_parts = []
        for item in field_changes if isinstance(field_changes, list) else []:
            field = item.get('field') or item.get('name') or ''
            before = item.get('from', item.get('before', '—'))
            after = item.get('to', item.get('after', '—'))
            if field:
                previous_parts.append(f'{field}: {before}')
                new_parts.append(f'{field}: {after}')
        if not previous_parts and changes.get('old_status') is not None:
            previous_parts.append(f"published: {changes.get('old_status')}")
            new_parts.append(f"published: {changes.get('new_status')}")
        version_label = (
            changes.get('new_template_version')
            or changes.get('restored_template_version')
            or changes.get('source_template_version')
            or template.version
        )
        if version_needle and str(version_label) != version_needle:
            continue
        rows.append({
            'timestamp': log.timestamp,
            'actor': _display_user(log.user),
            'action': log.get_action_display(),
            'event': changes.get('event') or log.event_type or log.action,
            'summary': _summarize_changes(log),
            'affected': (
                changes.get('step_name')
                or changes.get('field')
                or log.object_repr
                or log.model_name
            ),
            'previous_value': '; '.join(previous_parts) if previous_parts else '—',
            'new_value': '; '.join(new_parts) if new_parts else (_summarize_changes(log) or '—'),
            'version': f'v{version_label}' if version_label is not None else '—',
            'source': changes.get('source') or log.actor_type or 'app',
            'event_id': str(log.pk),
            'details': changes,
            'log': log,
        })
    return rows


def log_workflow_template_scenario_saved(template: WorkflowTemplate, scenario_name: str, user, request=None):
    _log(
        user,
        AuditLog.Action.CREATE,
        'WorkflowTemplateScenario',
        template.pk,
        scenario_name,
        changes=_build_payload(
            'workflow_template_scenario_saved',
            organization_id=template.organization_id,
            template_id=template.pk,
            template_name=template.name,
            scenario_name=scenario_name,
        ),
        request=request,
    )


def log_workflow_template_audit_exported(template: WorkflowTemplate, user, request=None, row_count: int = 0):
    _log(
        user,
        AuditLog.Action.EXPORT,
        'WorkflowTemplate',
        template.pk,
        template.name,
        changes=_build_payload(
            'workflow_template_audit_exported',
            organization_id=template.organization_id,
            template_id=template.pk,
            template_name=template.name,
            row_count=row_count,
        ),
        request=request,
    )
