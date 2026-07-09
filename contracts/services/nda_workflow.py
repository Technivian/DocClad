"""NDA Self-Serve Workflow.

Extends the workflow cockpit reference pattern to a lighter-weight NDA flow:

New Contract cockpit -> governed draft generation -> Workflow/Contract/
DraftDocument/FieldValue/RiskSignal/CommandCenterWorkItem -> workspace
redirect, with Legal review skipped unless a risk trigger appears.
"""
from __future__ import annotations

from importlib import import_module
import re
from typing import Dict, List, Optional

from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from contracts.middleware import log_action
from contracts.models import (
    ApprovalRoute,
    ClauseTemplate,
    CommandCenterWorkItem,
    Contract,
    ContractTemplate,
    DraftDocument,
    FieldDefinition,
    FieldValue,
    RiskSignal,
    Workflow,
    WorkflowStep,
    WorkflowTemplateStep,
    WorkflowTemplate,
)
from contracts.services.contract_templates import MERGE_FIELDS, _format_value
from contracts.services.workflow_execution import materialize_workflow_from_template
from contracts.tenancy import set_organization_on_instance

WORKFLOW_TEMPLATE_NAME = 'NDA Self-Serve Workflow'
TEMPLATE_LABEL = 'Mutual NDA · Netherlands · B2B'
PLAYBOOK_LABEL = 'NDA Self-Serve Playbook'
STANDARD_CONFIDENTIALITY_YEARS = 3

SECTION_ORDER = [
    FieldDefinition.Section.BASIC_DETAILS,
    FieldDefinition.Section.NDA_TERMS,
    FieldDefinition.Section.LEGAL_POSITION,
    FieldDefinition.Section.SMART_QUESTIONS,
]

_TOKEN_RE = re.compile(r'\{\{\s*(\w+)\s*\}\}')


def _ensure_nda_seed_data() -> None:
    seed = import_module('contracts.migrations.0077_seed_nda_workflow')

    contract_type, _ = ContractType.objects.get_or_create(
        code='NDA',
        defaults={
            'name': 'Non-Disclosure Agreement',
            'description': 'Self-serve NDA workflow with governed fallback and conditional legal review.',
            'is_active': True,
        },
    )

    workflow_template, created = WorkflowTemplate.objects.get_or_create(
        name=WORKFLOW_TEMPLATE_NAME,
        contract_type=contract_type,
        defaults={
            'description': 'Lightweight self-serve NDA drafting with conditional legal review.',
            'organization': None,
            'category': 'CONTRACT_REVIEW',
            'version': 1,
            'is_active': True,
        },
    )
    if not workflow_template.is_active:
        workflow_template.is_active = True
        workflow_template.save(update_fields=['is_active'])

    for step in seed.WORKFLOW_STEPS:
        WorkflowTemplateStep.objects.get_or_create(
            template=workflow_template,
            order=step['order'],
            defaults=step,
        )

    for field in seed.FIELD_DEFINITIONS:
        FieldDefinition.objects.get_or_create(
            workflow_template=workflow_template,
            key=field['key'],
            defaults=field,
        )

    for route_step in seed.APPROVAL_ROUTE:
        ApprovalRoute.objects.get_or_create(
            workflow_template=workflow_template,
            order=route_step['order'],
            defaults=route_step,
        )

    template, created_template = ContractTemplate.objects.get_or_create(
        name=seed.NDA_TEMPLATE_NAME,
        contract_type=Contract.ContractType.NDA,
        defaults={
            'description': 'Mutual confidentiality agreement with self-serve routing and governed fallback positions.',
            'body': seed.NDA_TEMPLATE_BODY_ENRICHED,
            'is_active': True,
        },
    )
    if (not created_template and 'confidentiality_purpose' not in template.body) or not template.is_active:
        template.body = seed.NDA_TEMPLATE_BODY_ENRICHED
        template.is_active = True
        template.save(update_fields=['body', 'is_active'])

    for clause in seed.DEMO_CLAUSES:
        ClauseTemplate.objects.get_or_create(
            title=clause['title'],
            organization=None,
            defaults={
                'content': clause['content'],
                'fallback_content': clause['fallback_content'],
                'applicable_contract_types': 'NDA',
                'is_approved': True,
            },
        )


def get_nda_workflow_template() -> Optional[WorkflowTemplate]:
    workflow_template = (
        WorkflowTemplate.objects
        .filter(contract_type__code='NDA', is_active=True, name=WORKFLOW_TEMPLATE_NAME)
        .order_by('-version')
        .first()
    )
    if workflow_template is not None:
        return workflow_template
    _ensure_nda_seed_data()
    return (
        WorkflowTemplate.objects
        .filter(contract_type__code='NDA', is_active=True, name=WORKFLOW_TEMPLATE_NAME)
        .order_by('-version')
        .first()
    )


def get_nda_contract_template() -> Optional[ContractTemplate]:
    return (
        ContractTemplate.objects
        .filter(contract_type=Contract.ContractType.NDA, is_active=True)
        .order_by('name')
        .first()
    )


def get_field_definitions_by_section(workflow_template: WorkflowTemplate) -> Dict[str, List[FieldDefinition]]:
    if workflow_template is None:
        return {section: [] for section in SECTION_ORDER}
    definitions = list(
        FieldDefinition.objects.filter(workflow_template=workflow_template).order_by('section', 'order')
    )
    grouped = {section: [] for section in SECTION_ORDER}
    for field in definitions:
        grouped.setdefault(field.section, []).append(field)
    return grouped


def get_nda_approval_route(workflow_template: WorkflowTemplate) -> List[ApprovalRoute]:
    if workflow_template is None:
        return []
    return list(ApprovalRoute.objects.filter(workflow_template=workflow_template).order_by('order'))


def get_clause_library_count(organization, contract_type: str) -> int:
    from django.db.models import Q

    if not contract_type:
        return 0
    qs = ClauseTemplate.objects.filter(is_approved=True)
    qs = (
        qs.filter(Q(organization=organization) | Q(organization__isnull=True))
        if organization else qs.filter(organization__isnull=True)
    )
    matching = 0
    for clause in qs.only('applicable_contract_types'):
        allowed = [t.strip() for t in (clause.applicable_contract_types or '').split(',') if t.strip()]
        if not allowed or contract_type in allowed:
            matching += 1
    return matching


def render_nda_live_preview(template_body: Optional[str], field_values_by_key: dict) -> str:
    if not template_body:
        return ''

    values = dict(field_values_by_key or {})
    personal_data = bool(values.get('personal_data_involved'))
    residual = bool(values.get('residual_knowledge_included'))
    injunctive_relief = bool(values.get('injunctive_relief_included'))
    values.setdefault(
        'personal_data_clause',
        'Personal data may be exchanged under this NDA; privacy review and, where needed, a linked DPA are required.'
        if personal_data else
        'No personal data processing language is currently required under this NDA draft.'
    )
    values.setdefault(
        'residual_knowledge_clause',
        'Residual knowledge language is included and requires legal confirmation of the approved fallback wording.'
        if residual else
        'Residual knowledge language is not included in this draft.'
    )
    values.setdefault(
        'injunctive_relief_clause',
        'The parties acknowledge that injunctive relief may be available for unauthorized disclosure of Confidential Information.'
        if injunctive_relief else
        'No express injunctive relief clause is included in this draft.'
    )

    def _replace(match):
        token = match.group(1)
        if token in values:
            return _format_value(values.get(token))
        if token in MERGE_FIELDS:
            alias = MERGE_FIELDS[token]
            if alias in values:
                return _format_value(values.get(alias))
            return match.group(0)
        return match.group(0)

    return _TOKEN_RE.sub(_replace, template_body)


def _coerce_confidentiality_period_years(value) -> float:
    if value in (None, ''):
        return 0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0


def detect_nda_risk_signals(workflow: Workflow, field_values_by_key: dict) -> List[RiskSignal]:
    signals = []

    confidentiality_years = _coerce_confidentiality_period_years(field_values_by_key.get('confidentiality_period'))
    if (
        bool(field_values_by_key.get('confidentiality_period_nonstandard'))
        or confidentiality_years > STANDARD_CONFIDENTIALITY_YEARS
    ):
        signals.append((
            'confidentiality_period_nonstandard',
            'Confidentiality period exceeds the standard NDA playbook position.',
            RiskSignal.Severity.HIGH,
        ))

    if field_values_by_key.get('personal_data_involved'):
        signals.append((
            'nda_privacy_review_required',
            'Personal data may be exchanged under this NDA; privacy review and linked DPA assessment are required.',
            RiskSignal.Severity.MEDIUM,
        ))

    if field_values_by_key.get('residual_knowledge_included') or field_values_by_key.get('residual_knowledge_nonstandard'):
        signals.append((
            'residual_knowledge_risk',
            'Residual knowledge language is included or non-standard and requires Legal review.',
            RiskSignal.Severity.HIGH,
        ))

    governing_law = str(field_values_by_key.get('governing_law') or '').strip().lower()
    if bool(field_values_by_key.get('governing_law_nonpreferred')) or (governing_law and 'netherlands' not in governing_law):
        signals.append((
            'nonpreferred_governing_law',
            'Governing law falls outside the preferred jurisdiction and requires Legal escalation.',
            RiskSignal.Severity.MEDIUM,
        ))

    created = []
    for code, description, severity in signals:
        created.append(RiskSignal.objects.create(workflow=workflow, code=code, description=description, severity=severity))
    return created


def sync_command_center_work_item_for_workflow(workflow: Workflow) -> CommandCenterWorkItem:
    contract = workflow.contract
    current_step = (
        workflow.steps.filter(status=WorkflowStep.Status.IN_PROGRESS).order_by('order').first()
        or workflow.steps.filter(status=WorkflowStep.Status.PENDING).order_by('order').first()
    )
    risk_signals = list(workflow.risk_signals.order_by('-severity', 'detected_at'))
    severity_rank = {
        RiskSignal.Severity.CRITICAL: 4,
        RiskSignal.Severity.HIGH: 3,
        RiskSignal.Severity.MEDIUM: 2,
        RiskSignal.Severity.LOW: 1,
    }
    top_signal = max(risk_signals, key=lambda signal: severity_rank.get(signal.severity, 0)) if risk_signals else None
    current_stage = current_step.name if current_step else 'Intake'

    if top_signal and top_signal.code == 'nda_privacy_review_required':
        next_action = 'Review privacy scope and linked DPA need'
    elif top_signal:
        next_action = 'Review NDA legal risk signals'
    else:
        next_action = 'Send for signature'

    highest_risk_signal = top_signal.description if top_signal else 'Self-serve eligible'
    blocking_issue = top_signal.description if top_signal else 'No active risk signals; NDA can remain self-serve.'
    item, _ = CommandCenterWorkItem.objects.update_or_create(
        organization=workflow.organization,
        source_type=CommandCenterWorkItem.SourceType.WORKFLOW,
        source_model='Workflow',
        source_object_id=workflow.pk,
        defaults={
            'title': workflow.title,
            'subtitle': blocking_issue,
            'item_type': 'NDA workflow',
            'stage': current_stage,
            'status': (
                CommandCenterWorkItem.Status.BLOCKED
                if top_signal and top_signal.severity in {RiskSignal.Severity.HIGH, RiskSignal.Severity.CRITICAL}
                else CommandCenterWorkItem.Status.OPEN
            ),
            'risk_level': top_signal.severity if top_signal else (contract.risk_level if contract else Contract.RiskLevel.LOW),
            'priority': (
                CommandCenterWorkItem.Priority.HIGH
                if top_signal and top_signal.severity in {RiskSignal.Severity.HIGH, RiskSignal.Severity.CRITICAL}
                else CommandCenterWorkItem.Priority.MEDIUM
            ),
            'owner': workflow.created_by,
            'contract': contract,
            'workflow': workflow,
            'due_at': current_step.due_date if current_step else None,
            'action_label': 'Open workspace',
            'action_path': reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}),
            'flags': {
                'contract_type': 'NDA',
                'current_stage': current_stage,
                'owner_label': (
                    workflow.created_by.get_full_name() or workflow.created_by.username
                    if workflow.created_by else 'Unassigned'
                ),
                'highest_risk_signal': highest_risk_signal,
                'blocking_issue': blocking_issue,
                'next_action': next_action,
            },
            'last_source_synced_at': timezone.now(),
        },
    )
    return item


@transaction.atomic
def create_nda_workflow_instance(*, organization, user, cleaned_values: dict, request=None) -> Workflow:
    workflow_template = get_nda_workflow_template()
    if workflow_template is None:
        raise ValueError('NDA Self-Serve Workflow template is not seeded.')

    field_defs = list(FieldDefinition.objects.filter(workflow_template=workflow_template))
    has_risk = (
        bool(cleaned_values.get('confidentiality_period_nonstandard'))
        or _coerce_confidentiality_period_years(cleaned_values.get('confidentiality_period')) > STANDARD_CONFIDENTIALITY_YEARS
        or bool(cleaned_values.get('personal_data_involved'))
        or bool(cleaned_values.get('residual_knowledge_included'))
        or bool(cleaned_values.get('residual_knowledge_nonstandard'))
        or bool(cleaned_values.get('governing_law_nonpreferred'))
        or ('netherlands' not in str(cleaned_values.get('governing_law') or '').strip().lower() and cleaned_values.get('governing_law'))
    )

    contract = Contract(
        title=f"NDA — {cleaned_values.get('counterparty') or 'Untitled counterparty'}",
        contract_type=Contract.ContractType.NDA,
        status=Contract.Status.DRAFT,
        created_by=user,
        lifecycle_stage='DRAFTING',
        risk_level=Contract.RiskLevel.HIGH if has_risk else Contract.RiskLevel.LOW,
    )
    set_organization_on_instance(contract, organization)
    for field in field_defs:
        if field.maps_to_contract_field and field.key in cleaned_values:
            setattr(contract, field.maps_to_contract_field, cleaned_values[field.key])
    contract.save()

    workflow = Workflow.objects.create(
        title=WORKFLOW_TEMPLATE_NAME,
        description=f"NDA drafting for {cleaned_values.get('counterparty') or 'this counterparty'}.",
        organization=organization,
        template=workflow_template,
        contract=contract,
        status=Workflow.Status.ACTIVE,
        created_by=user,
    )
    materialize_workflow_from_template(workflow)

    FieldValue.objects.bulk_create([
        FieldValue(workflow=workflow, field_definition=field, value=cleaned_values.get(field.key))
        for field in field_defs
    ])

    contract_template = get_nda_contract_template()
    preview_content = render_nda_live_preview(contract_template.body if contract_template else None, cleaned_values)
    DraftDocument.objects.create(
        workflow=workflow,
        contract=contract,
        content=preview_content,
        version=1,
        is_current=True,
        created_by=user,
    )

    detect_nda_risk_signals(workflow, cleaned_values)
    sync_command_center_work_item_for_workflow(workflow)

    log_action(
        user,
        'CREATE',
        'Workflow',
        workflow.id,
        str(workflow),
        changes={'event': 'nda_workflow_created', 'contract_id': contract.id},
        request=request,
        organization=organization,
    )
    return workflow
