from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from contracts.models import WorkflowTemplate, WorkflowTemplateStep
from contracts.services.workflow_execution import (
    _CONDITION_PATTERN,
    _FIELD_ALIASES,
    describe_condition_expression,
    describe_condition_rules,
    evaluate_condition_expression,
    evaluate_step_condition,
    is_automation_kind,
    normalize_condition_rules,
)


@dataclass(frozen=True)
class WorkflowTemplateStepPreview:
    step_id: int
    order: int
    name: str
    description: str
    step_kind: str
    condition_expression: str
    would_apply: bool
    reason: str
    assignee_role: str
    resolved_assignee: str
    assignment_resolved: bool
    sla_hours: Optional[int]
    escalation_after_hours: Optional[int]
    preview_status: str


@dataclass(frozen=True)
class WorkflowTemplateSimulationResult:
    template_id: int
    template_name: str
    organization_id: Optional[int]
    preview_steps: list[WorkflowTemplateStepPreview]
    active_step_count: int
    skipped_step_count: int
    matched_conditions: tuple[str, ...] = ()
    resulting_route: tuple[str, ...] = ()
    validation_messages: tuple[str, ...] = ()
    unresolved_assignment_count: int = 0
    simulation_completed: bool = True
    execution_blocked: bool = False
    execution_outcome_label: str = 'Ready to launch'
    result_tone: str = 'pass'  # pass | blocked | fail
    final_outcome_label: str = 'would complete'


class _ContractLikeAdapter:
    def __init__(self, data: dict[str, Any], organization=None):
        self.organization = organization
        self._data = data
        self.contract_type = data.get('contract_type') or ''
        self.value = data.get('value')
        self.jurisdiction = data.get('jurisdiction') or ''
        self.governing_law = data.get('governing_law') or ''
        self.data_transfer_flag = bool(data.get('data_transfer_flag', False))
        self.risk_level = data.get('risk_level') or ''
        self.counterparty = data.get('counterparty_name') or data.get('counterparty') or ''
        self.status = data.get('status') or ''
        self.finance_threshold = data.get('finance_threshold')


def _condition_label(step: WorkflowTemplateStep) -> str:
    rules = normalize_condition_rules(getattr(step, 'condition_rules', None))
    if rules:
        return describe_condition_rules(rules) or ''
    return describe_condition_expression(step.condition_expression or '') or ''


def _expression_field(expression: str) -> str:
    match = _CONDITION_PATTERN.match((expression or '').strip())
    if not match:
        return ''
    return _FIELD_ALIASES.get(match.group('field').strip().lower(), match.group('field').strip().lower())


def _humanize_condition_reason(step: WorkflowTemplateStep, would_apply: bool, *, invalid: bool = False, detail: str = '') -> str:
    """Enterprise-facing condition copy — never expose raw expressions like finance_threshold=true."""
    name = (step.name or 'This step').strip() or 'This step'
    label = _condition_label(step)
    field = ''
    rules = normalize_condition_rules(getattr(step, 'condition_rules', None))
    if rules and rules.get('clauses'):
        field = str(rules['clauses'][0].get('field') or '')
    if not field:
        field = _expression_field(step.condition_expression or '')

    if invalid:
        if detail:
            return f'{name} could not be evaluated: {detail}'
        return f'{name} could not be evaluated because its condition is invalid.'

    if field == 'finance_threshold':
        if would_apply:
            return f'{name} was triggered because the contract met the finance approval threshold.'
        return f'{name} was skipped because the contract did not meet the finance approval threshold.'

    if field == 'data_transfer_flag':
        if would_apply:
            return f'{name} was triggered because cross-border data transfer is required.'
        return f'{name} was skipped because cross-border data transfer is not required.'

    if not label:
        if would_apply:
            return 'No condition specified.'
        return f'{name} was skipped.'

    # Prefer natural "is" wording for equals.
    label = label.replace(' equals ', ' is ')
    if would_apply:
        return f'{name} was triggered because {label}.'
    return f'{name} was skipped because the condition did not match ({label}).'


def _resolve_assignment(step: WorkflowTemplateStep, contract_like) -> tuple[bool, str]:
    """Return (resolved?, display). Role-only fallback is treated as unresolved."""
    assignee = step.resolve_assignee(contract_like)
    if assignee is not None:
        full_name = (assignee.get_full_name() or '').strip()
        return True, full_name or getattr(assignee, 'username', '') or 'Assigned user'
    role = (step.assignee_role or '').strip()
    if role:
        return False, f'{role} (unresolved)'
    return False, 'Unresolved'


def _condition_reason(step: WorkflowTemplateStep, contract_like) -> tuple[bool, str, bool]:
    """Return (would_apply, reason, is_invalid)."""
    rules = normalize_condition_rules(getattr(step, 'condition_rules', None))
    if rules:
        try:
            would_apply = evaluate_step_condition(contract_like, step)
        except Exception:
            return False, _humanize_condition_reason(step, False, invalid=True), True
        return would_apply, _humanize_condition_reason(step, would_apply), False

    expression = (step.condition_expression or '').strip()
    if not expression:
        return True, _humanize_condition_reason(step, True), False

    match = _CONDITION_PATTERN.match(expression)
    compound_ok = ' and ' in expression.lower() or ' or ' in expression.lower()
    if not match and not compound_ok:
        return False, _humanize_condition_reason(step, False, invalid=True, detail='Invalid condition expression.'), True

    if match:
        field_name = match.group('field').strip().lower()
        if field_name not in _FIELD_ALIASES:
            return (
                False,
                _humanize_condition_reason(
                    step,
                    False,
                    invalid=True,
                    detail=f'Unknown condition field “{field_name}”.',
                ),
                True,
            )

    try:
        would_apply = evaluate_condition_expression(contract_like, expression)
    except Exception:
        return False, _humanize_condition_reason(step, False, invalid=True), True

    return would_apply, _humanize_condition_reason(step, would_apply), False


def _execution_labels(*, blocked: bool, unresolved: int, has_route: bool, has_invalid: bool) -> tuple[str, str, str]:
    """Return (result_tone, execution_outcome_label, final_outcome_label)."""
    if has_invalid:
        return (
            'fail',
            'Blocked — invalid configuration',
            'execution would be blocked by invalid configuration',
        )
    if not has_route:
        return (
            'blocked',
            'Blocked before launch',
            'execution would be blocked — no actionable route',
        )
    if unresolved:
        return (
            'blocked',
            'Blocked before launch',
            'execution would be blocked by unresolved assignments',
        )
    if blocked:
        return (
            'blocked',
            'Blocked before launch',
            'execution would be blocked by unresolved issues',
        )
    return (
        'pass',
        'Ready to launch',
        'would complete',
    )


def simulate_workflow_template(template: WorkflowTemplate, contract_data: dict[str, Any], organization=None, user=None):
    """
    Build a dry-run preview of how a template would materialize for contract-like data.

    This function does not create or mutate Workflow / WorkflowStep records.
    Simulation success (the dry-run completed) is separate from executability
    (whether the workflow could safely launch for these inputs).
    """
    if template is None:
        return WorkflowTemplateSimulationResult(
            template_id=0,
            template_name='',
            organization_id=getattr(organization, 'id', None),
            preview_steps=[],
            active_step_count=0,
            skipped_step_count=0,
            simulation_completed=True,
            execution_blocked=True,
            execution_outcome_label='Blocked before launch',
            result_tone='fail',
            final_outcome_label='execution would be blocked by invalid configuration',
        )

    contract_like = _ContractLikeAdapter(contract_data or {}, organization=organization)
    preview_steps: list[WorkflowTemplateStepPreview] = []
    first_actionable = True
    matched_conditions: list[str] = []
    resulting_route: list[str] = []
    validation_messages: list[str] = []
    unresolved_assignment_count = 0
    has_invalid = False

    for step in template.steps.order_by('order', 'pk'):
        would_apply, reason, is_invalid = _condition_reason(step, contract_like)
        preview_status = 'WOULD_SKIP'
        assignment_resolved = True
        resolved_assignee = ''

        if is_invalid:
            has_invalid = True
            validation_messages.append(reason)
            preview_status = 'WOULD_SKIP'
            would_apply = False
        elif would_apply:
            if is_automation_kind(step.step_kind):
                preview_status = 'WOULD_COMPLETE_AUTOMATICALLY'
                reason = reason if reason and reason != 'No condition specified.' else 'Automation step would complete immediately.'
            elif first_actionable:
                preview_status = 'WOULD_START'
                first_actionable = False
                if reason == 'No condition specified.':
                    reason = 'First applicable actionable step.'
            else:
                preview_status = 'WOULD_WAIT'
                if reason == 'No condition specified.':
                    reason = 'Applicable but waiting for an earlier actionable step.'
            if step.condition_expression or step.condition_rules:
                matched_conditions.append(reason)
            resulting_route.append(step.name)

            if not is_automation_kind(step.step_kind):
                assignment_resolved, resolved_assignee = _resolve_assignment(step, contract_like)
                if not assignment_resolved:
                    unresolved_assignment_count += 1
                    role_hint = f' ({step.assignee_role})' if step.assignee_role else ''
                    validation_messages.append(
                        f'{step.name}: Assignment unresolved{role_hint}. No matching workspace member could be resolved for this scenario.'
                    )
        else:
            preview_status = 'WOULD_SKIP'

        preview_steps.append(
            WorkflowTemplateStepPreview(
                step_id=step.pk,
                order=step.order,
                name=step.name,
                description=step.description,
                step_kind=step.step_kind,
                condition_expression=step.condition_expression,
                would_apply=would_apply,
                reason=reason,
                assignee_role=step.assignee_role,
                resolved_assignee=resolved_assignee,
                assignment_resolved=assignment_resolved,
                sla_hours=step.sla_hours,
                escalation_after_hours=step.escalation_after_hours,
                preview_status=preview_status,
            )
        )

    active_step_count = sum(1 for preview in preview_steps if preview.preview_status != 'WOULD_SKIP')
    skipped_step_count = len(preview_steps) - active_step_count
    if not resulting_route:
        validation_messages.append('No steps would run for these inputs.')

    execution_blocked = bool(validation_messages) or unresolved_assignment_count > 0 or not resulting_route or has_invalid
    result_tone, execution_outcome_label, final_outcome_label = _execution_labels(
        blocked=execution_blocked,
        unresolved=unresolved_assignment_count,
        has_route=bool(resulting_route),
        has_invalid=has_invalid,
    )

    return WorkflowTemplateSimulationResult(
        template_id=template.pk,
        template_name=template.name,
        organization_id=getattr(template, 'organization_id', None),
        preview_steps=preview_steps,
        active_step_count=active_step_count,
        skipped_step_count=skipped_step_count,
        matched_conditions=tuple(matched_conditions),
        resulting_route=tuple(resulting_route),
        validation_messages=tuple(validation_messages),
        unresolved_assignment_count=unresolved_assignment_count,
        simulation_completed=True,
        execution_blocked=execution_blocked,
        execution_outcome_label=execution_outcome_label,
        result_tone=result_tone,
        final_outcome_label=final_outcome_label,
    )
