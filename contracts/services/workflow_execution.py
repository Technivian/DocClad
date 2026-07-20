from __future__ import annotations

import re
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from contracts.models import Notification, OrganizationMembership, WorkflowStep, WorkflowTemplateStep


_CONDITION_PATTERN = re.compile(r'^\s*(?P<field>[a-zA-Z0-9_]+)\s*(?P<op>>=|<=|!=|=|>|<|~)\s*(?P<value>.+?)\s*$')
_BOOL_TRUE = {'1', 'true', 't', 'yes', 'y', 'on'}
_BOOL_FALSE = {'0', 'false', 'f', 'no', 'n', 'off'}
_SUPPORTED_OPS = frozenset({'>=', '<=', '!=', '=', '>', '<', '~'})

_FIELD_ALIASES = {
    'type': 'contract_type',
    'contract_type': 'contract_type',
    'value': 'value',
    'risk': 'risk_level',
    'risk_level': 'risk_level',
    'jurisdiction': 'jurisdiction',
    'governing_law': 'governing_law',
    'data_transfer': 'data_transfer_flag',
    'data_transfer_flag': 'data_transfer_flag',
    'status': 'status',
    'counterparty': 'counterparty',
    'finance_threshold': 'finance_threshold',
}

CONDITION_FIELD_CHOICES = (
    ('value', 'Contract value'),
    ('contract_type', 'Contract type'),
    ('risk_level', 'Risk level'),
    ('jurisdiction', 'Jurisdiction'),
    ('governing_law', 'Governing law'),
    ('data_transfer_flag', 'Cross-border data transfer'),
    ('status', 'Status'),
    ('counterparty', 'Counterparty'),
    ('finance_threshold', 'Finance threshold'),
)

CONDITION_OP_CHOICES = (
    ('=', 'equals'),
    ('!=', 'does not equal'),
    ('>', 'greater than'),
    ('>=', 'at least'),
    ('<', 'less than'),
    ('<=', 'at most'),
    ('~', 'contains'),
)

CANONICAL_STEP_KINDS = (
    'TASK',
    'REVIEW',
    'APPROVAL',
    'SIGNATURE',
    'AUTOMATION',
    'NOTIFICATION',
    'CONDITION',
)

_ASSIGNMENT_REQUIRED_KINDS = frozenset({'APPROVAL', 'REVIEW'})


def is_automation_kind(step_kind: str) -> bool:
    return step_kind in {'AUTOMATION', 'AUTOMATIC'}


def assignment_required_for_kind(step_kind: str) -> bool:
    return step_kind in _ASSIGNMENT_REQUIRED_KINDS


def _normalized_text(value):
    return (value or '').strip().upper()


def _contract_field_value(contract, field_name):
    if contract is None:
        return None
    normalized = _FIELD_ALIASES.get(field_name.strip().lower(), field_name.strip().lower())
    if normalized == 'finance_threshold':
        # Boolean helper: true when value is present and >= 100000 (pilot finance gate).
        raw = getattr(contract, 'value', None)
        if raw in (None, ''):
            explicit = getattr(contract, 'finance_threshold', None)
            if explicit is None and hasattr(contract, '_data'):
                explicit = contract._data.get('finance_threshold')
            return bool(explicit)
        try:
            return Decimal(str(raw)) >= Decimal('100000')
        except (InvalidOperation, ValueError, TypeError):
            return False
    return getattr(contract, normalized, None)


def _coerce_boolean(raw_value):
    normalized = _normalized_text(raw_value).lower()
    if normalized in _BOOL_TRUE:
        return True
    if normalized in _BOOL_FALSE:
        return False
    raise ValueError(f'Unsupported boolean value: {raw_value}')


def _coerce_decimal(raw_value):
    normalized = str(raw_value or '').strip().replace(',', '')
    normalized = normalized.lstrip('$€£')
    return Decimal(normalized)


def _evaluate_clause(contract, field_name: str, operator: str, expected_value: str) -> bool:
    actual_value = _contract_field_value(contract, field_name)
    try:
        if isinstance(actual_value, bool):
            actual_bool = bool(actual_value)
            expected_bool = _coerce_boolean(expected_value)
            if operator == '=':
                return actual_bool == expected_bool
            if operator == '!=':
                return actual_bool != expected_bool
            return False

        if isinstance(actual_value, (int, float, Decimal)):
            actual_decimal = Decimal(str(actual_value))
            expected_decimal = _coerce_decimal(expected_value)
            if operator == '=':
                return actual_decimal == expected_decimal
            if operator == '!=':
                return actual_decimal != expected_decimal
            if operator == '>':
                return actual_decimal > expected_decimal
            if operator == '>=':
                return actual_decimal >= expected_decimal
            if operator == '<':
                return actual_decimal < expected_decimal
            if operator == '<=':
                return actual_decimal <= expected_decimal
            return False

        actual_text = _normalized_text(actual_value)
        expected_text = _normalized_text(expected_value)
        if operator == '=':
            return actual_text == expected_text
        if operator == '!=':
            return actual_text != expected_text
        if operator == '~':
            return expected_text in actual_text
        if operator in {'>', '>=', '<', '<='}:
            return False
        return False
    except (InvalidOperation, ValueError):
        return False


def normalize_condition_rules(rules: Any) -> dict | None:
    """Normalize rule-builder JSON; return None when empty/invalid structure."""
    if not rules:
        return None
    if isinstance(rules, str):
        import json
        try:
            rules = json.loads(rules)
        except (TypeError, ValueError):
            return None
    if not isinstance(rules, dict):
        return None
    logic = str(rules.get('logic') or 'AND').strip().upper()
    if logic not in {'AND', 'OR'}:
        logic = 'AND'
    clauses = []
    for raw in rules.get('clauses') or []:
        if not isinstance(raw, dict):
            continue
        field = str(raw.get('field') or '').strip().lower()
        op = str(raw.get('op') or '=').strip()
        value = str(raw.get('value') or '').strip()
        if not field or not value:
            continue
        if field not in _FIELD_ALIASES:
            continue
        if op not in _SUPPORTED_OPS:
            continue
        clauses.append({'field': _FIELD_ALIASES[field], 'op': op, 'value': value})
    if not clauses:
        return None
    return {'logic': logic, 'clauses': clauses}


def validate_condition_rules(rules: Any) -> list[str]:
    """Return human validation errors for structured rules (empty = ok)."""
    if not rules:
        return []
    if isinstance(rules, str):
        import json
        try:
            rules = json.loads(rules)
        except (TypeError, ValueError):
            return ['Condition rules must be valid JSON.']
    if not isinstance(rules, dict):
        return ['Condition rules must be an object.']
    logic = str(rules.get('logic') or 'AND').strip().upper()
    if logic not in {'AND', 'OR'}:
        return ['Condition logic must be AND or OR.']
    raw_clauses = rules.get('clauses') or []
    if not isinstance(raw_clauses, list):
        return ['Condition clauses must be a list.']
    if not raw_clauses:
        return []
    errors = []
    for index, raw in enumerate(raw_clauses, start=1):
        if not isinstance(raw, dict):
            errors.append(f'Clause {index} is invalid.')
            continue
        field = str(raw.get('field') or '').strip().lower()
        op = str(raw.get('op') or '=').strip()
        value = str(raw.get('value') or '').strip()
        if not field:
            errors.append(f'Clause {index} needs a field.')
        elif field not in _FIELD_ALIASES:
            errors.append(f'Clause {index} uses unknown field “{field}”.')
        if op not in _SUPPORTED_OPS:
            errors.append(f'Clause {index} uses an unsupported operator.')
        if not value:
            errors.append(f'Clause {index} needs a value.')
    return errors


def compile_condition_rules(rules: Any) -> str:
    """Compile structured rules into a legacy-compatible expression string."""
    normalized = normalize_condition_rules(rules)
    if not normalized:
        return ''
    joiner = ' and ' if normalized['logic'] == 'AND' else ' or '
    parts = [f"{c['field']}{c['op']}{c['value']}" for c in normalized['clauses']]
    return joiner.join(parts)


def describe_condition_rules(rules: Any) -> str:
    """Human-readable description for the rule builder."""
    normalized = normalize_condition_rules(rules)
    if not normalized:
        return ''
    field_labels = dict(CONDITION_FIELD_CHOICES)
    op_labels = dict(CONDITION_OP_CHOICES)
    joiner = ' and ' if normalized['logic'] == 'AND' else ' or '
    parts = []
    for clause in normalized['clauses']:
        field_key = str(clause.get('field') or '').strip()
        value_raw = str(clause.get('value') or '').strip()
        value_norm = value_raw.lower()
        op = str(clause.get('op') or '=').strip()
        # Prefer natural phrasing for common boolean gates.
        if field_key == 'data_transfer_flag' and op in {'=', '=='} and value_norm in {'true', '1', 'yes'}:
            parts.append('cross-border data transfer is required')
            continue
        if field_key == 'data_transfer_flag' and op in {'=', '=='} and value_norm in {'false', '0', 'no'}:
            parts.append('cross-border data transfer is not required')
            continue
        if field_key == 'finance_threshold' and op in {'=', '=='} and value_norm in {'true', '1', 'yes'}:
            parts.append('the finance approval threshold is met')
            continue
        if field_key == 'finance_threshold' and op in {'=', '=='} and value_norm in {'false', '0', 'no'}:
            parts.append('the finance approval threshold is not met')
            continue
        field = field_labels.get(field_key, field_key.replace('_', ' '))
        op_label = op_labels.get(op, op)
        value = value_raw.replace('_', ' ').strip()
        if value.upper() == value and value.isalpha():
            value = value.title()
        parts.append(f"{field} {op_label} {value}")
    return joiner.join(parts)


def describe_condition_expression(expression: str) -> str:
    """Best-effort human label for a legacy expression string."""
    expression = (expression or '').strip()
    if not expression:
        return ''
    rules = None
    compound = _split_compound_expression(expression)
    if compound:
        logic, parts = compound
        clauses = []
        for part in parts:
            match = _CONDITION_PATTERN.match(part)
            if not match:
                return expression
            clauses.append({
                'field': match.group('field'),
                'op': match.group('op'),
                'value': match.group('value').strip(),
            })
        rules = {'logic': logic, 'clauses': clauses}
    else:
        match = _CONDITION_PATTERN.match(expression)
        if match:
            rules = {
                'logic': 'AND',
                'clauses': [{
                    'field': match.group('field'),
                    'op': match.group('op'),
                    'value': match.group('value').strip(),
                }],
            }
    label = describe_condition_rules(rules)
    return label or expression


def step_condition_summary(step) -> str:
    """Card-facing condition copy, e.g. 'Runs when Risk level is High'."""
    rules = getattr(step, 'condition_rules', None)
    label = describe_condition_rules(rules)
    if not label:
        label = describe_condition_expression(getattr(step, 'condition_expression', '') or '')
    if not label:
        return ''
    # Prefer "is" wording for equals.
    label = label.replace(' equals ', ' is ')
    return f'Runs when {label}'


def evaluate_condition_rules(contract, rules: Any) -> bool:
    normalized = normalize_condition_rules(rules)
    if not normalized:
        return True
    results = [
        _evaluate_clause(contract, clause['field'], clause['op'], clause['value'])
        for clause in normalized['clauses']
    ]
    if normalized['logic'] == 'OR':
        return any(results)
    return all(results)


def _split_compound_expression(expression: str) -> tuple[str, list[str]] | None:
    """Split legacy compound expressions joined by and/or (case-insensitive)."""
    text = (expression or '').strip()
    if not text:
        return None
    lower = text.lower()
    if ' and ' in lower and ' or ' not in lower:
        parts = re.split(r'\s+and\s+', text, flags=re.IGNORECASE)
        return 'AND', [p.strip() for p in parts if p.strip()]
    if ' or ' in lower and ' and ' not in lower:
        parts = re.split(r'\s+or\s+', text, flags=re.IGNORECASE)
        return 'OR', [p.strip() for p in parts if p.strip()]
    return None


def evaluate_condition_expression(contract, expression):
    expression = (expression or '').strip()
    if not expression:
        return True

    compound = _split_compound_expression(expression)
    if compound:
        logic, parts = compound
        results = [evaluate_condition_expression(contract, part) for part in parts]
        return any(results) if logic == 'OR' else all(results)

    match = _CONDITION_PATTERN.match(expression)
    if not match:
        return False

    return _evaluate_clause(
        contract,
        match.group('field'),
        match.group('op'),
        match.group('value').strip(),
    )


def evaluate_step_condition(contract, step) -> bool:
    """Evaluate structured rules when present; fall back to expression."""
    rules = getattr(step, 'condition_rules', None)
    if rules:
        return evaluate_condition_rules(contract, rules)
    return evaluate_condition_expression(contract, getattr(step, 'condition_expression', '') or '')


@transaction.atomic
def materialize_workflow_from_template(workflow, *, refresh: bool = False):
    if not workflow or not workflow.template_id:
        return []

    existing_steps = list(workflow.steps.all())
    if existing_steps and not refresh:
        return existing_steps

    # Only gate new launches / full rematerialization — existing active steps continue.
    from contracts.services.workflow_designer import assert_template_safe_to_launch

    assert_template_safe_to_launch(workflow.template)

    if refresh and existing_steps:
        workflow.steps.all().delete()

    now = timezone.now()
    created_steps = []
    first_actionable = True
    for template_step in workflow.template.steps.order_by('order', 'pk'):
        applies = template_step.applies_to_contract(workflow.contract)
        due_date = None
        if template_step.sla_hours:
            due_date = now + timedelta(hours=int(template_step.sla_hours))

        status = WorkflowStep.Status.PENDING
        blocked_reason = ''
        completed_at = None
        if not applies:
            status = WorkflowStep.Status.SKIPPED
            blocked_reason = (
                f"Condition '{template_step.condition_expression}' was not met for this contract."
                if template_step.condition_expression
                else 'Step skipped for this contract.'
            )
            due_date = None
        elif is_automation_kind(template_step.step_kind):
            status = WorkflowStep.Status.COMPLETED
            completed_at = now
        elif first_actionable:
            status = WorkflowStep.Status.IN_PROGRESS
            first_actionable = False
        else:
            first_actionable = False

        assignee = template_step.resolve_assignee(workflow.contract)
        if (
            assignee is None
            and template_step.step_kind == WorkflowTemplateStep.StepKind.SIGNATURE
            and getattr(workflow.template, 'fallback_signer_id', None)
        ):
            assignee = workflow.template.fallback_signer

        created_steps.append(
            WorkflowStep.objects.create(
                workflow=workflow,
                template_step=template_step,
                name=template_step.name,
                description=template_step.description,
                status=status,
                assigned_to=assignee,
                due_date=due_date,
                completed_at=completed_at,
                order=template_step.order,
                blocked_reason=blocked_reason,
            )
        )

    if created_steps and all(step.status in {WorkflowStep.Status.COMPLETED, WorkflowStep.Status.SKIPPED} for step in created_steps):
        workflow.status = workflow.Status.COMPLETED
        workflow.save(update_fields=['status'])
    return created_steps


@transaction.atomic
def advance_workflow_after_completion(step):
    workflow = step.workflow
    next_step = (
        workflow.steps
        .filter(order__gt=step.order)
        .exclude(status__in=[WorkflowStep.Status.COMPLETED, WorkflowStep.Status.SKIPPED])
        .order_by('order', 'pk')
        .first()
    )
    if next_step and next_step.status == WorkflowStep.Status.PENDING:
        next_step.status = WorkflowStep.Status.IN_PROGRESS
        if next_step.due_date is None and next_step.template_step and next_step.template_step.sla_hours:
            next_step.due_date = timezone.now() + timedelta(hours=int(next_step.template_step.sla_hours))
        next_step.save(update_fields=['status', 'due_date'])
        return next_step

    if not workflow.steps.exclude(status__in=[WorkflowStep.Status.COMPLETED, WorkflowStep.Status.SKIPPED]).exists():
        workflow.status = workflow.Status.COMPLETED
        workflow.save(update_fields=['status'])
    return None


def _workflow_reminder_recipients(step):
    recipients = set()
    if step.assigned_to_id:
        recipients.add(step.assigned_to)
    if step.workflow and step.workflow.created_by_id:
        recipients.add(step.workflow.created_by)
    organization = step.workflow.organization
    if organization:
        for membership in OrganizationMembership.objects.filter(
            organization=organization,
            is_active=True,
            role__in=[OrganizationMembership.Role.OWNER, OrganizationMembership.Role.ADMIN],
        ).select_related('user'):
            recipients.add(membership.user)
    return recipients


@transaction.atomic
def escalate_overdue_workflow_steps(now=None):
    now = now or timezone.now()
    overdue_steps = WorkflowStep.objects.select_related('workflow', 'workflow__organization', 'workflow__created_by', 'assigned_to').filter(
        status__in=[WorkflowStep.Status.PENDING, WorkflowStep.Status.IN_PROGRESS],
        due_date__isnull=False,
        due_date__lt=now,
        escalated_at__isnull=True,
    )
    notifications = 0
    for step in overdue_steps:
        recipients = _workflow_reminder_recipients(step)
        link = reverse('contracts:workflow_detail', kwargs={'pk': step.workflow_id})
        title = f'Workflow overdue: {step.workflow.title} ({step.name})'
        for recipient in recipients:
            if Notification.objects.filter(
                recipient=recipient,
                notification_type=Notification.NotificationType.TASK,
                title=title,
                link=link,
                created_at__date=timezone.localdate(now),
            ).exists():
                continue
            Notification.objects.create(
                recipient=recipient,
                notification_type=Notification.NotificationType.TASK,
                title=title,
                message=(
                    f'{step.workflow.title} is waiting on "{step.name}" and it was due '
                    f'on {step.due_date.isoformat()}.'
                ),
                link=link,
            )
            notifications += 1

        step.status = WorkflowStep.Status.ESCALATED
        step.escalated_at = now
        step.save(update_fields=['status', 'escalated_at'])

    return {
        'escalated_count': overdue_steps.count(),
        'notification_count': notifications,
    }
