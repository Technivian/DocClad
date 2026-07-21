"""Workflow Designer list helpers: cards, publish validation, duplication."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from django.db.models import Count, Q
from django.urls import reverse

from contracts.models import AuditLog, OrganizationMembership, Workflow, WorkflowTemplate, WorkflowTemplateStep
from contracts.services.workflow_templates import clone_template_version, compare_template_versions, list_template_versions


OPEN_WORKFLOW_STATUSES = frozenset({
    Workflow.Status.ACTIVE,
})

WORKFLOW_TEMPLATE_AUDIT_EVENT_CHOICES = (
    ('workflow_template_created', 'Created'),
    ('workflow_template_updated', 'Updated'),
    ('workflow_template_cloned', 'Cloned'),
    ('workflow_template_restored', 'Restored'),
    ('workflow_template_step_added', 'Step added'),
    ('workflow_template_step_updated', 'Step updated'),
    ('workflow_template_step_deleted', 'Step deleted'),
    ('workflow_template_reordered', 'Reordered'),
    ('workflow_template_publish_toggled', 'Publish changed'),
    ('workflow_template_scenario_saved', 'Scenario saved'),
    ('workflow_template_audit_exported', 'Audit exported'),
    ('workflow_preview_run', 'Test run'),
)


@dataclass(frozen=True)
class PublishValidationResult:
    ok: bool
    errors: tuple[str, ...]
    step_issues: tuple[dict, ...] = ()
    warnings: tuple[dict, ...] = ()
    infos: tuple[dict, ...] = ()

    @property
    def message(self) -> str:
        if self.ok and not self.warnings:
            return ''
        return ' '.join(self.errors) or ' '.join(item.get('message', '') for item in self.warnings)

    @property
    def blocking_count(self) -> int:
        return len(self.step_issues) or len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)


def can_edit_workflow_template(user, organization, template: WorkflowTemplate | None = None) -> bool:
    """Authoring requires an active org membership and a template in the org scope."""
    if not user or not getattr(user, 'is_authenticated', False) or not organization:
        return False
    if template is not None and template.organization_id not in (None, organization.pk):
        return False
    return OrganizationMembership.objects.filter(
        organization=organization,
        user=user,
        is_active=True,
    ).exists()


class WorkflowLaunchBlocked(Exception):
    """Raised when a template must not be used for new workflow launches."""

    def __init__(self, message: str, *, template: WorkflowTemplate | None = None):
        super().__init__(message)
        self.template = template
        self.message = message


def _step_has_assignee(step: WorkflowTemplateStep) -> bool:
    return bool((step.assignee_role or '').strip() or step.specific_assignee_id)


def unassigned_required_steps(template: WorkflowTemplate) -> list[WorkflowTemplateStep]:
    """Required actionable steps that have no role or user assignee."""
    from contracts.services.workflow_execution import assignment_required_for_kind

    gaps = []
    for step in template.steps.order_by('order', 'pk'):
        needs_assignment = (
            assignment_required_for_kind(step.step_kind)
            or step.step_kind == WorkflowTemplateStep.StepKind.SIGNATURE
        )
        if needs_assignment and not _step_has_assignee(step):
            gaps.append(step)
    return gaps


def template_launch_policy(template: WorkflowTemplate | None) -> dict:
    """
    Governed new-launch outcome for a published template.

    Returns:
      blocked (bool), uses_fallback (bool), label (str), reason (str|None)
    """
    if template is None:
        return {
            'blocked': False,
            'uses_fallback': False,
            'label': 'Allowed',
            'reason': None,
        }

    gaps = unassigned_required_steps(template)
    if not gaps:
        return {
            'blocked': False,
            'uses_fallback': False,
            'label': 'Allowed',
            'reason': None,
        }

    signature_gaps = [
        step for step in gaps if step.step_kind == WorkflowTemplateStep.StepKind.SIGNATURE
    ]
    other_gaps = [
        step for step in gaps if step.step_kind != WorkflowTemplateStep.StepKind.SIGNATURE
    ]
    has_fallback = bool(getattr(template, 'fallback_signer_id', None))

    # Signature-only gaps may route to an explicitly configured fallback signer.
    if signature_gaps and not other_gaps and has_fallback:
        return {
            'blocked': False,
            'uses_fallback': True,
            'label': 'Route to configured fallback signer',
            'reason': None,
        }

    names = ', '.join(step.name for step in gaps[:3])
    more = f' (+{len(gaps) - 3} more)' if len(gaps) > 3 else ''
    if signature_gaps and not other_gaps:
        reason = (
            f'New launches are blocked for “{template.name}” because required Signature '
            f'step{"s" if len(signature_gaps) != 1 else ""} lack signer configuration: '
            f'{names}{more}. Configure a signer on the step, set a fallback signer, '
            f'or create a corrected version before launching.'
        )
        label = 'Blocked — Signature step lacks signer configuration'
    else:
        reason = (
            f'New launches are blocked for “{template.name}” because required steps '
            f'have no assignee: {names}{more}. Create a corrected version before launching.'
        )
        label = 'Blocked — required steps lack assignees'

    return {
        'blocked': True,
        'uses_fallback': False,
        'label': label,
        'reason': reason,
    }


def template_launch_block_reason(template: WorkflowTemplate | None) -> str | None:
    """
    Governed launch rule: block new launches when a required step has no assignee
    unless an explicit fallback signer covers Signature-only gaps.
    """
    return template_launch_policy(template).get('reason')


def assert_template_safe_to_launch(template: WorkflowTemplate | None) -> None:
    reason = template_launch_block_reason(template)
    if reason:
        raise WorkflowLaunchBlocked(reason, template=template)


def can_mutate_workflow_template(user, organization, template: WorkflowTemplate | None = None) -> bool:
    """Published versions are read-only; mutate only draft versions the user can edit."""
    if not can_edit_workflow_template(user, organization, template):
        return False
    if template is not None and template.is_active:
        return False
    return True


def workflow_template_canvas_tabs(*, template_pk: int, active: str) -> list[dict]:
    """Detail-page tabs: Design / Test / Versions / Audit trail."""
    base = reverse('contracts:workflow_template_detail', kwargs={'pk': template_pk})
    # Canonical tab key is activity; accept legacy ?tab=audit.
    if active == 'audit':
        active = 'activity'
    items = (
        ('design', 'Design'),
        ('test', 'Test'),
        ('versions', 'Versions'),
        ('activity', 'Audit trail'),
    )
    return [
        {
            'key': key,
            'label': label,
            'url': f'{base}?tab={key}',
            'active': key == active,
        }
        for key, label in items
    ]


def template_uses_status_condition(template: WorkflowTemplate) -> bool:
    """Show Status in Test only when routing conditions reference record status."""
    for step in template.steps.all():
        rules = getattr(step, 'condition_rules', None) or {}
        for clause in rules.get('clauses') or []:
            if str(clause.get('field') or '').strip().lower() == 'status':
                return True
        expression = (getattr(step, 'condition_expression', '') or '').lower()
        if 'status' in expression:
            return True
    return False


def _humanize_version_change_summary(
    *,
    description: str,
    previous: WorkflowTemplate | None,
    version: WorkflowTemplate,
) -> str:
    text = (description or '').strip()
    if text:
        return text
    if not previous:
        return 'Initial version'
    comparison = compare_template_versions(previous, version)
    bits: list[str] = []
    for diff in comparison.step_diffs:
        lower = diff.lower()
        if 'added' in lower:
            name = diff.split('added', 1)[-1].strip(' :.')
            # "Step 2: added 2. Finance Review" → Finance Review
            if '. ' in name:
                name = name.split('. ', 1)[-1]
            bits.append(f'Added {name}')
        elif 'removed' in lower:
            name = diff.split('removed', 1)[-1].strip(' :.')
            if '. ' in name:
                name = name.split('. ', 1)[-1]
            bits.append(f'Removed {name}')
        elif 'changed' in lower or '→' in diff or '->' in diff:
            bits.append(diff.replace('Step ', '').strip())
        else:
            bits.append(diff)
    for field_name, old, new in comparison.field_diffs:
        if field_name == 'description':
            continue
        label = field_name.replace('_', ' ')
        bits.append(f'Changed {label} from {old} to {new}')
    # Prefer SLA-oriented phrasing when step diffs mention sla.
    refined = []
    for bit in bits:
        if 'sla' in bit.lower() and 'from' in bit.lower():
            refined.append(bit.replace('sla_hours', 'SLA').replace('sla', 'SLA'))
        else:
            refined.append(bit)
    return '; '.join(refined[:4]) if refined else 'No structural differences from prior version'


def build_template_version_rows(template: WorkflowTemplate, *, current_pk: int | None = None) -> list[dict]:
    """Governed Versions-tab rows with usage and provenance metadata."""
    from contracts.services.workflow_audit import _display_user, template_version_provenance

    versions = list(
        list_template_versions(template)
    )
    # Prefer select_related when queryset-backed; list_template_versions returns list.
    current_pk = current_pk or template.pk
    usage_map = {
        row['template_id']: row['c']
        for row in Workflow.objects.filter(template_id__in=[v.pk for v in versions])
        .values('template_id')
        .annotate(c=Count('id'))
    }
    active_usage_map = {
        row['template_id']: row['c']
        for row in Workflow.objects.filter(
            template_id__in=[v.pk for v in versions],
            status=Workflow.Status.ACTIVE,
        )
        .values('template_id')
        .annotate(c=Count('id'))
    }
    rows = []
    for index, version in enumerate(versions):
        previous = versions[index + 1] if index + 1 < len(versions) else None
        provenance = template_version_provenance(version)
        validation = validate_template_for_publish(version)
        change_summary = _humanize_version_change_summary(
            description=version.description or '',
            previous=previous,
            version=version,
        )
        is_current = version.pk == current_pk
        is_live = bool(version.is_active)
        if is_live and is_current:
            status_label = 'Live published'
            status_tone = 'success'
        elif is_live:
            status_label = 'Published'
            status_tone = 'success'
        elif is_current:
            status_label = 'Current draft'
            status_tone = 'attention'
        else:
            status_label = 'Draft'
            status_tone = 'neutral'
            if any(v.is_active for v in versions):
                status_label = 'Superseded draft'

        created_by_user = getattr(version, 'created_by', None)
        published_by_user = getattr(version, 'published_by', None)
        created_by = (
            _display_user(created_by_user)
            if created_by_user
            else (provenance.get('created_by') or 'System')
        )
        published_at = getattr(version, 'published_at', None) or provenance.get('published_at')
        if is_live and not published_at:
            published_at = version.created_at
        published_by = (
            _display_user(published_by_user)
            if published_by_user
            else (provenance.get('published_by') or ('System' if is_live else '—'))
        )
        source_version = previous.version if previous else None
        rows.append({
            'template': version,
            'version_number': version.version,
            'status_label': status_label,
            'status_tone': status_tone,
            'is_current': is_current,
            'is_published': is_live,
            'created_by': created_by,
            'created_at': version.created_at,
            'published_by': published_by,
            'published_at': published_at,
            'source_version': source_version,
            'change_summary': change_summary,
            'validation_ok': validation.ok,
            'blocking_count': validation.blocking_count,
            'warning_count': validation.warning_count,
            'active_workflow_count': int(active_usage_map.get(version.pk, 0)),
            'total_workflow_count': int(usage_map.get(version.pk, 0)),
            'view_url': f"{reverse('contracts:workflow_template_detail', kwargs={'pk': version.pk})}?tab=design",
            'compare_url': (
                reverse('contracts:workflow_template_compare', kwargs={'pk': current_pk, 'other_pk': version.pk})
                if version.pk != current_pk
                else ''
            ),
            'restore_url': reverse('contracts:workflow_template_restore_version', kwargs={'pk': version.pk}),
            'validation_url': f"{reverse('contracts:workflow_template_detail', kwargs={'pk': version.pk})}?tab=design",
        })
    return rows


DEFAULT_TEST_SCENARIOS = (
    {
        'key': 'standard_nda',
        'name': 'Standard NDA',
        'payload': {
            'contract_type': 'NDA',
            'value': '0',
            'jurisdiction': 'Netherlands',
            'governing_law': 'Netherlands',
            'data_transfer_flag': False,
            'risk_level': 'LOW',
            'counterparty_name': 'Acme BV',
        },
    },
    {
        'key': 'high_risk_international',
        'name': 'High-risk international transfer',
        'payload': {
            'contract_type': 'DPA',
            'value': '250000',
            'jurisdiction': 'United States',
            'governing_law': 'England and Wales',
            'data_transfer_flag': True,
            'risk_level': 'HIGH',
            'counterparty_name': 'Global Processor Inc',
        },
    },
)


def workflow_hub_tabs(*, active: str) -> list[dict]:
    """Unified tab strip for the Workflow Designer hub (ops + authoring)."""
    items = (
        ('active', 'Active workflows', 'contracts:workflow_dashboard'),
        ('approvals', 'Approval requests', 'contracts:approval_request_list'),
        ('templates', 'Templates', 'contracts:workflow_template_list'),
        ('routing', 'Routing rules', 'contracts:approval_rule_list'),
        ('approval_rules', 'Approval rules', 'contracts:workflow_approval_route_list'),
        ('history', 'Change history', 'contracts:workflow_designer_history'),
    )
    return [
        {
            'key': key,
            'label': label,
            'url': reverse(url_name),
            'active': key == active,
        }
        for key, label, url_name in items
    ]


def workflow_designer_tabs(*, active: str) -> list[dict]:
    """Backward-compatible alias for the unified Workflow Designer hub tabs."""
    return workflow_hub_tabs(active=active)


def template_stage_count(template: WorkflowTemplate) -> int:
    cached = getattr(template, 'step_count', None)
    if cached is not None:
        return int(cached)
    return template.steps.count()


def is_incomplete_template(template: WorkflowTemplate) -> bool:
    """Zero-stage templates are never publishable — surface as Setup required."""
    return template_stage_count(template) == 0


def is_standard_incomplete_template(template: WorkflowTemplate) -> bool:
    name = (template.name or '').strip().lower()
    return is_incomplete_template(template) and (
        name == 'standard' or name.startswith('standard ') or 'standard workflow' in name
    )


def ensure_stepless_templates_unpublished(queryset) -> int:
    """Force any published zero-stage templates back to draft (data integrity)."""
    stepless = list(
        queryset.annotate(step_count=Count('steps')).filter(is_active=True, step_count=0)
    )
    if not stepless:
        return 0
    WorkflowTemplate.objects.filter(pk__in=[t.pk for t in stepless]).update(is_active=False)
    for template in stepless:
        template.is_active = False
    return len(stepless)


def validate_template_for_publish(template: WorkflowTemplate) -> PublishValidationResult:
    """Gate publish on stages, routing, owners, and configuration integrity."""
    from contracts.services.workflow_execution import (
        assignment_required_for_kind,
        validate_condition_rules,
    )

    errors: list[str] = []
    step_issues: list[dict] = []
    warnings: list[dict] = []
    infos: list[dict] = []
    steps = list(template.steps.order_by('order', 'pk'))
    if not steps:
        errors.append('Add at least one stage before publishing this template.')
        return PublishValidationResult(
            ok=False,
            errors=tuple(errors),
            step_issues=(),
            warnings=(),
            infos=(),
        )

    orders = [step.order for step in steps]
    if len(orders) != len(set(orders)):
        errors.append('Stage order must be unique — resolve disconnected or duplicate stages.')

    actionable = [
        step for step in steps
        if step.step_kind not in {
            WorkflowTemplateStep.StepKind.CONDITION,
            WorkflowTemplateStep.StepKind.BRANCH,
        }
    ]
    if not actionable:
        errors.append('Add at least one actionable step so the workflow can reach Completed.')

    def _append_blocking(step, message: str, *, field: str = '') -> None:
        errors.append(message)
        payload = {
            'step_id': step.pk,
            'step_name': step.name,
            'message': message,
            'severity': 'blocking',
        }
        if field:
            payload['field'] = field
        step_issues.append(payload)

    def _append_warning(step, message: str, *, field: str = '') -> None:
        payload = {
            'step_id': step.pk,
            'step_name': step.name,
            'message': message,
            'severity': 'warning',
        }
        if field:
            payload['field'] = field
        warnings.append(payload)

    for step in steps:
        has_assignee = bool((step.assignee_role or '').strip() or step.specific_assignee_id)
        if assignment_required_for_kind(step.step_kind) and not has_assignee:
            _append_blocking(step, 'Assignment required', field='assignment')
        elif step.step_kind == WorkflowTemplateStep.StepKind.SIGNATURE and not has_assignee:
            _append_blocking(step, 'Signer configuration missing', field='assignment')
        elif step.step_kind == WorkflowTemplateStep.StepKind.TASK and not has_assignee:
            _append_warning(step, 'Assignment recommended', field='assignment')

        if step.step_kind in {
            WorkflowTemplateStep.StepKind.REVIEW,
            WorkflowTemplateStep.StepKind.APPROVAL,
        } and not step.sla_hours:
            _append_blocking(step, 'SLA is required', field='sla_hours')
        elif step.step_kind == WorkflowTemplateStep.StepKind.TASK and not step.sla_hours:
            _append_warning(step, 'SLA not configured', field='sla_hours')

        if step.escalation_after_hours and not step.sla_hours:
            _append_blocking(step, 'Configure SLA before escalation timing', field='sla_hours')
        elif (
            step.sla_hours
            and step.escalation_after_hours
            and step.escalation_after_hours <= step.sla_hours
        ):
            _append_blocking(step, 'Escalation must be after the SLA', field='escalation_after_hours')

        for rule_error in validate_condition_rules(step.condition_rules):
            _append_blocking(step, f'Invalid condition: {rule_error}', field='conditions')
        expression = (step.condition_expression or '').strip()
        if expression:
            if expression.count('(') != expression.count(')'):
                _append_blocking(step, 'Condition has unbalanced parentheses', field='conditions')
            if any(token in expression for token in (';;', '===')):
                _append_blocking(step, 'Condition expression is invalid', field='conditions')

    if not errors and not warnings:
        infos.append({'message': 'Configuration is ready to publish.', 'severity': 'info'})

    return PublishValidationResult(
        ok=not errors,
        errors=tuple(errors),
        step_issues=tuple(step_issues),
        warnings=tuple(warnings),
        infos=tuple(infos),
    )


def _status_presentation(template: WorkflowTemplate) -> dict:
    """Card/list status. Section headers own Published vs Drafts grouping."""
    if is_incomplete_template(template):
        return {
            'label': 'Setup required',
            'catalog_label': 'Drafts',
            'badge': 'Setup required',
            'tone': 'attention',
            'dot': 'draft',
            'is_published': False,
            'is_incomplete': True,
        }
    if template.is_active:
        has_blocking = not validate_template_for_publish(template).ok
        return {
            'label': 'Published',
            'catalog_label': 'Published',
            'badge': 'Configuration issue' if has_blocking else '',
            'tone': 'attention' if has_blocking else 'success',
            'dot': 'live',
            'is_published': True,
            'is_incomplete': False,
            'has_configuration_issue': has_blocking,
        }
    return {
        'label': 'Draft',
        'catalog_label': 'Drafts',
        'badge': 'Draft',
        'tone': 'attention',
        'dot': 'draft',
        'is_published': False,
        'is_incomplete': False,
    }


def _contract_type_label(template: WorkflowTemplate) -> str:
    if template.contract_type_id and getattr(template, 'contract_type', None):
        return template.contract_type.name
    return template.get_category_display()


def _template_steps(template: WorkflowTemplate) -> list[WorkflowTemplateStep]:
    if (
        hasattr(template, '_prefetched_objects_cache')
        and 'steps' in getattr(template, '_prefetched_objects_cache', {})
    ):
        return sorted(template.steps.all(), key=lambda step: (step.order, step.pk))
    return list(template.steps.order_by('order', 'pk'))


def _stage_names(template: WorkflowTemplate, *, visible_limit: int = 3) -> dict:
    steps = _template_steps(template)
    names = [step.name for step in steps]
    visible = names[:visible_limit]
    more_count = max(0, len(names) - visible_limit)
    return {
        'visible': visible,
        'more_count': more_count,
        'empty': not names,
    }


def _stage_path(template: WorkflowTemplate, *, limit: int = 3) -> str:
    stages = _stage_names(template, visible_limit=limit)
    if stages['empty']:
        return 'No stages yet'
    path = ' → '.join(stages['visible'])
    if stages['more_count']:
        path = f'{path} → +{stages["more_count"]} more'
    return path


def _template_icon_key(template: WorkflowTemplate) -> str:
    """Compact identity icon for NDA / MSA / DPA / generic review tiles."""
    type_code = ''
    type_name = ''
    if template.contract_type_id and getattr(template, 'contract_type', None):
        type_code = (getattr(template.contract_type, 'code', None) or '').upper()
        type_name = (template.contract_type.name or '').upper()
    blob = ' '.join(
        part for part in (
            type_code,
            type_name,
            (template.name or '').upper(),
            (template.category or '').upper(),
            (template.get_category_display() or '').upper(),
        ) if part
    )
    if any(token in blob for token in ('NDA', 'NON-DISCLOSURE', 'NON DISCLOSURE', 'CONFIDENTIAL')):
        return 'shield'
    if any(token in blob for token in ('MSA', 'MASTER SERVICE', 'MASTER SERVICES')):
        return 'briefcase'
    if any(token in blob for token in ('DPA', 'DATA PROCESS', 'PRIVACY', 'GDPR')):
        return 'lock'
    return 'workflow'


def _incomplete_reason(template: WorkflowTemplate) -> str:
    if not is_incomplete_template(template):
        return ''
    return 'Add at least one stage to continue.'


def _normalize_duplicate_base_name(name: str) -> str:
    """Strip nested Copy-of / Copy-N suffixes so duplicates stay readable."""
    base = (name or '').strip() or 'Workflow'
    changed = True
    while changed:
        changed = False
        stripped = re.sub(r'^(?:Copy of\s+)+', '', base, flags=re.IGNORECASE).strip()
        if stripped != base:
            base = stripped or 'Workflow'
            changed = True
            continue
        stripped = re.sub(r'\s+Copy(?:\s+\d+)?$', '', base, flags=re.IGNORECASE).strip()
        if stripped != base:
            base = stripped or 'Workflow'
            changed = True
    return base


def next_duplicate_template_name(template: WorkflowTemplate, *, explicit_name: Optional[str] = None) -> str:
    """
    Prefer ``{Name} Copy 2`` over ``Copy of Copy of {Name}``.

    The original keeps its name; the first duplicate becomes ``Copy 2``, then ``Copy 3``.
    """
    if explicit_name and explicit_name.strip():
        return explicit_name.strip()

    base = _normalize_duplicate_base_name(template.name)
    qs = WorkflowTemplate.objects.all()
    if template.organization_id:
        qs = qs.filter(organization_id=template.organization_id)
    else:
        qs = qs.filter(organization__isnull=True)

    existing = set(qs.values_list('name', flat=True))
    copy_re = re.compile(rf'^{re.escape(base)} Copy (\d+)$', re.IGNORECASE)
    used_numbers = set()
    for name in existing:
        match = copy_re.match(name or '')
        if match:
            used_numbers.add(int(match.group(1)))
    if base in existing:
        used_numbers.add(1)

    next_number = 2
    while next_number in used_numbers:
        next_number += 1
    return f'{base} Copy {next_number}'


def _owner_is_meaningful(owner_label: str) -> bool:
    normalized = (owner_label or '').strip().lower()
    return bool(normalized) and normalized not in {
        'system',
        'workspace',
        'unassigned',
        '—',
        '-',
    }


def _latest_audit(template: WorkflowTemplate) -> Optional[AuditLog]:
    return (
        AuditLog.objects.filter(
            Q(model_name='WorkflowTemplate', object_id=template.pk)
            | Q(changes__template_id=template.pk)
        )
        .select_related('user')
        .order_by('-timestamp', '-pk')
        .first()
    )


def _owner_label(template: WorkflowTemplate, latest_audit: Optional[AuditLog]) -> str:
    for step in template.steps.all()[:8]:
        if step.specific_assignee_id:
            user = step.specific_assignee
            return (user.get_full_name() or user.username).strip() or 'Assigned'
        if (step.assignee_role or '').strip():
            return step.get_assignee_role_display() if hasattr(step, 'get_assignee_role_display') else step.assignee_role
    if latest_audit and latest_audit.user_id:
        user = latest_audit.user
        return (user.get_full_name() or user.username).strip() or 'Workspace'
    if template.organization_id:
        return 'Workspace'
    return 'System'


def _has_unpublished_changes(template: WorkflowTemplate) -> bool:
    versions = list_template_versions(template)
    if len(versions) < 2:
        return is_incomplete_template(template) is False and not template.is_active and template_stage_count(template) > 0
    newest = versions[0]
    published = next((v for v in versions if v.is_active and not is_incomplete_template(v)), None)
    if published and newest.pk != published.pk and not newest.is_active:
        return True
    return (not template.is_active) and template_stage_count(template) > 0


def active_workflow_count_for_template(template: WorkflowTemplate) -> int:
    cached = getattr(template, 'active_workflow_count', None)
    if cached is not None:
        return int(cached)
    return Workflow.objects.filter(
        template=template,
        status=Workflow.Status.ACTIVE,
    ).count()


def _card_description(template: WorkflowTemplate, contract_type_label: str) -> str:
    description = (template.description or '').strip()
    if description:
        if len(description) > 120:
            return description[:117].rstrip() + '…'
        return description
    if contract_type_label:
        return f'Governed {contract_type_label} workflow template.'
    return 'Reusable approval and review blueprint.'


def _card_badge(status: dict, *, has_unpublished_changes: bool) -> str:
    """Only surface badges that add meaning beyond the section header / Live status."""
    if status.get('is_incomplete'):
        return 'Setup required'
    if status.get('has_configuration_issue'):
        return 'Configuration issue'
    if has_unpublished_changes and status.get('is_published'):
        return 'Changes pending'
    # Drafts: keep a Draft badge; “Changes pending” lives on the secondary line.
    if status.get('badge') == 'Draft':
        return 'Draft'
    return status.get('badge') or ''


def _card_secondary_line(
    template: WorkflowTemplate,
    *,
    status: dict,
    contract_type_label: str,
    stage_count: int,
    active_count: int,
    updated_at,
    has_unpublished_changes: bool,
) -> str:
    """One concise secondary line — never dump owner/version/dates/usage together."""
    from django.utils.formats import date_format

    if status.get('is_incomplete'):
        return 'No workflow stages configured'

    if status.get('is_published'):
        type_part = contract_type_label or 'Workflow'
        usage = f'Used by {active_count}' if active_count else 'Not used yet'
        return f'{type_part} · {usage}'

    stage_part = '1 stage' if stage_count == 1 else f'{stage_count} stages'
    if has_unpublished_changes:
        return f'{stage_part} · Changes pending'
    if updated_at:
        return f'{stage_part} · Updated {date_format(updated_at, "j M Y")}'
    return stage_part


def build_template_card(template: WorkflowTemplate) -> dict:
    status = _status_presentation(template)
    latest_audit = _latest_audit(template)
    editor = '—'
    updated_at = template.created_at
    if latest_audit:
        updated_at = latest_audit.timestamp
        if latest_audit.user_id:
            editor = (latest_audit.user.get_full_name() or latest_audit.user.username).strip() or '—'
    owner_label = _owner_label(template, latest_audit)
    stages = _stage_names(template, visible_limit=3)
    incomplete_reason = _incomplete_reason(template)
    selectable = bool(status['is_published'] and not status['is_incomplete'])
    if status['is_incomplete']:
        select_disabled_reason = incomplete_reason
    elif not status['is_published']:
        select_disabled_reason = 'Publish this template before it can be selected.'
    else:
        select_disabled_reason = ''
    contract_type_label = _contract_type_label(template)
    active_count = active_workflow_count_for_template(template)
    stage_count = template_stage_count(template)
    has_unpublished_changes = _has_unpublished_changes(template)
    badge = _card_badge(status, has_unpublished_changes=has_unpublished_changes)
    secondary_line = _card_secondary_line(
        template,
        status=status,
        contract_type_label=contract_type_label,
        stage_count=stage_count,
        active_count=active_count,
        updated_at=updated_at,
        has_unpublished_changes=has_unpublished_changes,
    )
    return {
        'template': template,
        'name': template.name,
        'contract_type_label': contract_type_label,
        'description': _card_description(template, contract_type_label),
        'icon_key': _template_icon_key(template),
        'status_label': status['label'],
        'catalog_status_label': status['catalog_label'],
        'status_badge': badge,
        'show_status_badge': bool(badge),
        # Published templates always show green Live; issue badges sit beside it.
        'show_live_status': bool(status['is_published']),
        'live_status_label': 'Live',
        'status_tone': status['tone'],
        'status_dot': status['dot'],
        'is_published': status['is_published'],
        'is_incomplete': status['is_incomplete'],
        'incomplete_reason': incomplete_reason,
        'secondary_line': secondary_line,
        'version_label': f'v{template.version}',
        'stage_path': _stage_path(template),
        'stage_names': stages['visible'],
        'stage_more_count': stages['more_count'],
        'stages_empty': stages['empty'],
        'stage_count': stage_count,
        'owner_label': owner_label,
        'show_owner': _owner_is_meaningful(owner_label),
        'updated_at': updated_at,
        'editor_label': editor,
        'active_workflow_count': active_count,
        'active_workflow_label': (
            f'{active_count} active workflow'
            if active_count == 1
            else f'{active_count} active workflows'
        ),
        'has_unpublished_changes': has_unpublished_changes,
        'designer_url': reverse('contracts:workflow_template_detail', kwargs={'pk': template.pk}),
        'can_delete': bool(template.organization_id),
        'can_publish': validate_template_for_publish(template).ok and not template.is_active,
        'selectable': selectable,
        'select_disabled_reason': select_disabled_reason,
    }


def duplicate_workflow_template(template: WorkflowTemplate, *, name: Optional[str] = None) -> WorkflowTemplate:
    """Create an independent unpublished copy (not a version bump)."""
    copy_name = next_duplicate_template_name(template, explicit_name=name)
    clone = WorkflowTemplate.objects.create(
        name=copy_name,
        description=template.description,
        organization=template.organization,
        category=template.category,
        contract_type=template.contract_type,
        version=1,
        parent_template=None,
        is_active=False,
    )
    for step in template.steps.order_by('order', 'pk'):
        WorkflowTemplateStep.objects.create(
            template=clone,
            name=step.name,
            description=step.description,
            order=step.order,
            estimated_duration=step.estimated_duration,
            step_kind=step.step_kind,
            condition_expression=step.condition_expression,
            assignee_role=step.assignee_role,
            specific_assignee=step.specific_assignee,
            sla_hours=step.sla_hours,
            escalation_after_hours=step.escalation_after_hours,
        )
    return clone


def filter_workflow_templates(queryset, *, q='', contract_type='', status='', owner='', sort='updated'):
    q = (q or '').strip()
    if q:
        queryset = queryset.filter(
            Q(name__icontains=q)
            | Q(description__icontains=q)
            | Q(category__icontains=q)
            | Q(contract_type__name__icontains=q)
        )
    contract_type = (contract_type or '').strip()
    if contract_type:
        if contract_type.isdigit():
            queryset = queryset.filter(contract_type_id=int(contract_type))
        else:
            queryset = queryset.filter(category=contract_type)

    status = (status or '').strip().lower()
    queryset = queryset.annotate(step_count=Count('steps', distinct=True))
    if status == 'published':
        queryset = queryset.filter(is_active=True).exclude(step_count=0)
    elif status == 'draft':
        queryset = queryset.filter(Q(is_active=False) | Q(step_count=0))
    elif status == 'incomplete':
        queryset = queryset.filter(step_count=0)

    owner = (owner or '').strip()
    if owner == 'unassigned':
        queryset = queryset.exclude(
            steps__specific_assignee__isnull=False
        ).exclude(
            steps__assignee_role__gt=''
        ).distinct()
    elif owner == 'system':
        queryset = queryset.filter(organization__isnull=True)
    elif owner == 'workspace':
        queryset = queryset.filter(organization__isnull=False)

    sort = (sort or 'updated').strip().lower()
    if sort == 'name':
        queryset = queryset.order_by('name', '-version')
    elif sort == 'status':
        queryset = queryset.order_by('-is_active', 'name')
    elif sort == 'version':
        queryset = queryset.order_by('-version', 'name')
    else:
        queryset = queryset.order_by('-created_at', 'name')
    return queryset
