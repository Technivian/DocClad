"""MSA Commercial Review Workflow.

Extends the governed drafting loop proven by the DPA workflow path to MSA
without introducing a second architecture. The flow is still:

New Contract cockpit -> governed draft generation -> Workflow/Contract/
DraftDocument/FieldValue/RiskSignal/ApprovalRoute/CommandCenterWorkItem ->
workspace redirect.
"""
from __future__ import annotations

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
    WorkflowTemplate,
)
from contracts.services.contract_templates import MERGE_FIELDS, _format_value
from contracts.services.workflow_execution import materialize_workflow_from_template
from contracts.tenancy import set_organization_on_instance

WORKFLOW_TEMPLATE_NAME = 'MSA Commercial Review Workflow'
TEMPLATE_LABEL = 'Enterprise Services MSA · Netherlands · B2B'
PLAYBOOK_LABEL = 'MSA Commercial Playbook'
FINANCE_APPROVAL_THRESHOLD = 250000

SECTION_ORDER = [
    FieldDefinition.Section.BASIC_DETAILS,
    FieldDefinition.Section.COMMERCIAL_TERMS,
    FieldDefinition.Section.SERVICES_SCOPE,
    FieldDefinition.Section.LEGAL_POSITION,
    FieldDefinition.Section.SMART_QUESTIONS,
]

_TOKEN_RE = re.compile(r'\{\{\s*(\w+)\s*\}\}')


def get_msa_workflow_template() -> Optional[WorkflowTemplate]:
    return (
        WorkflowTemplate.objects
        .filter(contract_type__code='MSA', is_active=True)
        .order_by('-version')
        .first()
    )


def get_msa_contract_template() -> Optional[ContractTemplate]:
    return (
        ContractTemplate.objects
        .filter(contract_type=Contract.ContractType.MSA, is_active=True)
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


def get_msa_approval_route(workflow_template: WorkflowTemplate) -> List[ApprovalRoute]:
    if workflow_template is None:
        return []
    return list(ApprovalRoute.objects.filter(workflow_template=workflow_template).order_by('order'))


def get_clause_library_count(organization, contract_type: str) -> int:
    from django.db.models import Q

    if not contract_type:
        return 0
    qs = ClauseTemplate.objects.filter(is_approved=True)
    qs = qs.filter(Q(organization=organization) | Q(organization__isnull=True)) if organization else qs.filter(organization__isnull=True)
    matching = 0
    for clause in qs.only('applicable_contract_types'):
        allowed = [t.strip() for t in (clause.applicable_contract_types or '').split(',') if t.strip()]
        if not allowed or contract_type in allowed:
            matching += 1
    return matching


def _as_moneyish(value):
    return _format_value(value) if value not in (None, '') else ''


def render_msa_live_preview(template_body: Optional[str], field_values_by_key: dict) -> str:
    if not template_body:
        return ''

    values = dict(field_values_by_key or {})
    personal_data = bool(values.get('personal_data_involved') or values.get('services_involve_personal_data'))
    values.setdefault(
        'data_protection_clause',
        'Data Protection Addendum review is required because the services involve processing personal data.'
        if personal_data else
        'No personal data processing terms are currently required under this draft.'
    )
    values.setdefault(
        'liability_cap',
        'fees paid under this Agreement in the preceding twelve (12) months'
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


def detect_msa_risk_signals(workflow: Workflow, field_values_by_key: dict) -> List[RiskSignal]:
    signals = []

    contract_value = field_values_by_key.get('value')
    try:
        contract_value_num = float(contract_value) if contract_value not in (None, '') else 0
    except (TypeError, ValueError):
        contract_value_num = 0

    finance_trigger = bool(field_values_by_key.get('value_above_threshold_confirmed')) or contract_value_num >= FINANCE_APPROVAL_THRESHOLD
    if finance_trigger:
        signals.append((
            'finance_approval_required',
            f'Contract value exceeds the finance approval threshold of {FINANCE_APPROVAL_THRESHOLD:,}.',
            RiskSignal.Severity.HIGH,
        ))

    if field_values_by_key.get('liability_cap_nonstandard'):
        signals.append((
            'liability_cap_nonstandard',
            'Liability cap deviates from the standard MSA playbook position.',
            RiskSignal.Severity.HIGH,
        ))

    personal_data = bool(field_values_by_key.get('personal_data_involved') or field_values_by_key.get('services_involve_personal_data'))
    if personal_data:
        signals.append((
            'msa_dpa_review_required',
            'Services involve personal data processing; privacy review and linked DPA assessment are required.',
            RiskSignal.Severity.MEDIUM,
        ))

    auto_renew = bool(field_values_by_key.get('auto_renewal_included')) or str(field_values_by_key.get('renewal_type', '')).lower() == 'auto-renew'
    if auto_renew:
        signals.append((
            'renewal_notice_review',
            'Auto-renewal is included; review notice periods and renewal obligation tracking.',
            RiskSignal.Severity.MEDIUM,
        ))

    if field_values_by_key.get('ip_ownership_nonstandard'):
        signals.append((
            'nonstandard_ip_ownership',
            'IP ownership is non-standard and requires Legal review.',
            RiskSignal.Severity.HIGH,
        ))

    governing_law = str(field_values_by_key.get('governing_law') or '').strip().lower()
    governing_law_nonpreferred = bool(field_values_by_key.get('governing_law_nonpreferred')) or (governing_law and 'netherlands' not in governing_law)
    if governing_law_nonpreferred:
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

    if top_signal and top_signal.code == 'finance_approval_required':
        next_action = 'Review Finance approval route'
    elif top_signal and top_signal.code == 'msa_dpa_review_required':
        next_action = 'Review privacy scope and linked DPA need'
    elif top_signal and top_signal.code == 'renewal_notice_review':
        next_action = 'Review renewal notice obligations'
    elif top_signal:
        next_action = 'Review legal fallback positions'
    else:
        next_action = 'Open generated MSA workspace'

    blocking_issue = top_signal.description if top_signal else 'Field capture complete; ready for governed review.'
    item, _ = CommandCenterWorkItem.objects.update_or_create(
        organization=workflow.organization,
        source_type=CommandCenterWorkItem.SourceType.WORKFLOW,
        source_model='Workflow',
        source_object_id=workflow.pk,
        defaults={
            'title': workflow.title,
            'subtitle': blocking_issue,
            'item_type': 'MSA workflow',
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
                'contract_type': 'MSA',
                'current_stage': current_stage,
                'owner_label': (
                    workflow.created_by.get_full_name() or workflow.created_by.username
                    if workflow.created_by else 'Unassigned'
                ),
                'highest_risk_signal': top_signal.description if top_signal else 'No active risk signal',
                'blocking_issue': blocking_issue,
                'next_action': next_action,
            },
            'last_source_synced_at': timezone.now(),
        },
    )
    return item


@transaction.atomic
def create_msa_workflow_instance(*, organization, user, cleaned_values: dict, request=None) -> Workflow:
    workflow_template = get_msa_workflow_template()
    if workflow_template is None:
        raise ValueError('MSA Commercial Review Workflow template is not seeded.')

    field_defs = list(FieldDefinition.objects.filter(workflow_template=workflow_template))

    contract = Contract(
        title=f"MSA — {cleaned_values.get('counterparty') or 'Untitled counterparty'}",
        contract_type=Contract.ContractType.MSA,
        status=Contract.Status.DRAFT,
        created_by=user,
        lifecycle_stage='DRAFTING',
        risk_level=Contract.RiskLevel.LOW,
    )
    set_organization_on_instance(contract, organization)
    for field in field_defs:
        if field.maps_to_contract_field and field.key in cleaned_values:
            setattr(contract, field.maps_to_contract_field, cleaned_values[field.key])
    contract.auto_renew = bool(cleaned_values.get('auto_renewal_included')) or str(cleaned_values.get('renewal_type', '')).lower() == 'auto-renew'
    contract.save()

    workflow = Workflow.objects.create(
        title=WORKFLOW_TEMPLATE_NAME,
        description=f"Commercial review for the MSA with {cleaned_values.get('counterparty') or 'this counterparty'}.",
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

    contract_template = get_msa_contract_template()
    preview_content = render_msa_live_preview(contract_template.body if contract_template else None, cleaned_values)
    DraftDocument.objects.create(
        workflow=workflow,
        contract=contract,
        content=preview_content,
        version=1,
        is_current=True,
        created_by=user,
    )

    risk_signals = detect_msa_risk_signals(workflow, cleaned_values)
    if any(signal.severity in {RiskSignal.Severity.HIGH, RiskSignal.Severity.CRITICAL} for signal in risk_signals):
        contract.risk_level = Contract.RiskLevel.HIGH
    elif risk_signals:
        contract.risk_level = Contract.RiskLevel.MEDIUM
    contract.save(update_fields=['risk_level', 'auto_renew', 'updated_at'])

    sync_command_center_work_item_for_workflow(workflow)

    log_action(
        user,
        'CREATE',
        'Workflow',
        workflow.id,
        str(workflow),
        changes={'event': 'msa_workflow_created', 'contract_id': contract.id},
        request=request,
        organization=organization,
    )
    return workflow
