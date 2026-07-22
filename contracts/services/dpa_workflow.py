"""DPA Privacy Review Workflow — the first flagship "workflow-first" flow.

Orchestrates the New Contract → DPA path: a data-driven intake form
(FieldDefinition/FieldValue, not a hardcoded ModelForm), a live draft
preview, rule-based (not AI) risk-signal detection, and creation of a real
Workflow instance (the model that already plays "WorkflowInstance") with
its WorkflowSteps materialized from the DPA WorkflowTemplate.

Kept separate from contracts/services/draft_cockpit.py, which is scoped to
network-free, read-only helpers for the generic (any contract type)
create page — this module does multi-table transactional writes and calls
the workflow execution engine, a different concern.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from django.db import transaction
from django.core.files import File
from django.core.files.storage import default_storage
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
    Document,
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

SECTION_ORDER = [
    FieldDefinition.Section.BASIC_DETAILS,
    FieldDefinition.Section.PRIVACY_DETAILS,
    FieldDefinition.Section.LEGAL_POSITION,
    FieldDefinition.Section.PRIVACY_QUESTIONS,
]

_TOKEN_RE = re.compile(r'\{\{\s*(\w+)\s*\}\}')


def get_dpa_workflow_template() -> Optional[WorkflowTemplate]:
    return (
        WorkflowTemplate.objects
        .filter(contract_type__code='DPA', is_active=True)
        .order_by('-version')
        .first()
    )


def get_dpa_contract_template() -> Optional[ContractTemplate]:
    return (
        ContractTemplate.objects
        .filter(contract_type=Contract.ContractType.DPA, is_active=True)
        .order_by('name')
        .first()
    )


def get_field_definitions_by_section(workflow_template: WorkflowTemplate) -> Dict[str, List[FieldDefinition]]:
    """Grouped, in fixed display order, for left-column rendering."""
    if workflow_template is None:
        return {section: [] for section in SECTION_ORDER}
    definitions = list(
        FieldDefinition.objects.filter(workflow_template=workflow_template).order_by('section', 'order')
    )
    grouped = {section: [] for section in SECTION_ORDER}
    for field in definitions:
        grouped.setdefault(field.section, []).append(field)
    return grouped


def get_dpa_approval_route(workflow_template: WorkflowTemplate) -> List[ApprovalRoute]:
    if workflow_template is None:
        return []
    return list(ApprovalRoute.objects.filter(workflow_template=workflow_template).order_by('order'))


def get_clause_library_count(organization, contract_type: str) -> int:
    """Local copy of draft_cockpit's applicable-clause counter — kept here
    too so this module has no import dependency on draft_cockpit.py."""
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


def render_dpa_live_preview(template_body: Optional[str], field_values_by_key: dict) -> str:
    """Merge-field substitution extended with FieldDefinition-only tokens.

    Checks the basic contract MERGE_FIELDS map first (title/counterparty/
    value/...), then falls back to a submitted FieldDefinition value (e.g.
    {{dpo_contact}}). Unrecognized tokens are left as-is, mirroring
    render_merge_fields's contract.
    """
    if not template_body:
        return ''

    values = dict(field_values_by_key or {})
    if values.get('cross_border_transfer'):
        transfer_positions = {
            'Adequacy Decision': 'Data leaves the EEA under a confirmed adequacy decision; the approved adequacy transfer position applies.',
            'SCC': 'Data leaves the EEA; the parties incorporate the approved Standard Contractual Clauses (SCC) language as the transfer mechanism.',
            'BCR': 'Data leaves the EEA under confirmed Binding Corporate Rules; the approved BCR transfer position applies.',
            'EU-US Data Privacy Framework': 'Data leaves the EEA under the confirmed EU-US Data Privacy Framework; the approved DPF transfer position applies.',
            'Other': 'Data leaves the EEA under a documented alternative safeguard; Privacy must confirm the approved transfer position.',
        }
        transfer_default = transfer_positions.get(
            values.get('transfer_mechanism'),
            'Data leaves the EEA; a confirmed transfer safeguard is required before the DPA can progress.',
        )
    else:
        transfer_default = 'No transfer outside the EEA is currently selected'
    values.setdefault('data_transfer_position', transfer_default)
    values.setdefault(
        'subprocessor_position',
        'Subprocessors are involved; approved flow-down obligations apply'
        if values.get('subprocessors_used')
        else 'No subprocessors are currently selected'
    )

    def _replace(match):
        token = match.group(1)
        if token in values:
            return _format_value(values.get(token))
        if token in MERGE_FIELDS:
            # No Contract instance yet on the builder page — MERGE_FIELDS
            # tokens resolve from field_values_by_key too, since basic
            # details (counterparty, start_date, ...) are also collected
            # as FieldDefinitions with matching keys.
            alias = MERGE_FIELDS[token]
            if alias in values:
                return _format_value(values.get(alias))
            return match.group(0)
        return match.group(0)

    return _TOKEN_RE.sub(_replace, template_body)


@dataclass
class RiskSignalRule:
    code: str
    description: str
    severity: str
    predicate: str  # documentation only; logic lives in detect_dpa_risk_signals


def detect_dpa_risk_signals(workflow: Workflow, field_values_by_key: dict) -> List[RiskSignal]:
    """Rule-based (no AI/LLM call) risk-signal detection from submitted
    field values. Persists RiskSignal rows scoped to the Workflow."""
    signals = []

    # A DPA is itself the governed record for personal-data processing; this
    # baseline must not depend on a redundant user checkbox.
    signals.append(('dpa_review_required', 'DPA baseline: Privacy and Legal review are required.', RiskSignal.Severity.MEDIUM))

    cross_border = bool(field_values_by_key.get('cross_border_transfer'))
    mechanism = field_values_by_key.get('transfer_mechanism')
    if cross_border:
        if mechanism == 'SCC':
            signals.append(('scc_transfer_review', 'Standard Contractual Clauses apply to a non-EEA transfer; DPO approval is required.', RiskSignal.Severity.HIGH))
        elif not mechanism or mechanism == 'None':
            signals.append(('cross_border_no_mechanism', 'Cross-border transfer flagged but no transfer mechanism selected.', RiskSignal.Severity.HIGH))

    if not field_values_by_key.get('dpo_contact'):
        signals.append(('missing_dpo_contact', 'No Data Protection Officer contact provided.', RiskSignal.Severity.MEDIUM))

    if field_values_by_key.get('subprocessors_used'):
        signals.append(('subprocessor_review', 'Subprocessors are involved; approved subprocessor flow-down language must be reviewed.', RiskSignal.Severity.MEDIUM))

    if field_values_by_key.get('special_categories_data'):
        signals.append(('special_categories_risk', 'Special categories of personal data are processed; elevated privacy risk requires Legal and DPO review.', RiskSignal.Severity.HIGH))

    if field_values_by_key.get('include_scc_fallback'):
        signals.append(('scc_fallback_included', 'Approved SCC fallback clause language will be included in the draft.', RiskSignal.Severity.LOW))

    facts = field_values_by_key.get('_dpa_step3', {})
    if facts.get('sensitive_data') == 'not_sure' or facts.get('subprocessors_answer') == 'not_sure':
        signals.append(('privacy_fact_uncertain', 'A privacy intake answer is not confirmed; Privacy and DPO review are required before approval or signature.', RiskSignal.Severity.HIGH))

    step4 = field_values_by_key.get('_dpa_step4', {})
    if step4:
        if any(step4.get(key) in {'no', 'not_sure'} for key in (
            'security_measures_provided', 'security_assurance_available',
            'encryption_confirmed', 'access_controls_mfa_confirmed',
        )):
            signals.append(('security_evidence_missing', 'Security assurance or evidence is missing or not confirmed.', RiskSignal.Severity.MEDIUM))
        if step4.get('breach_notification_commitment') not in {'approved_standard', ''}:
            signals.append(('breach_term_deviation', 'Breach-notification commitment deviates from the approved playbook.', RiskSignal.Severity.MEDIUM))
        if field_values_by_key.get('governing_law_changed'):
            signals.append(('governing_law_deviation', 'Governing law differs from the related MSA.', RiskSignal.Severity.MEDIUM))
        if any(position.get('status') in {'deviation', 'not_confirmed'} for position in step4.get('positions', {}).values()):
            signals.append(('standard_position_deviation', 'A standard DPA position is not accepted or is not confirmed.', RiskSignal.Severity.MEDIUM))

    breach_hours = field_values_by_key.get('breach_notification_hours')
    try:
        breach_hours_val = float(breach_hours) if breach_hours not in (None, '') else None
    except (TypeError, ValueError):
        breach_hours_val = None
    if breach_hours_val is None or breach_hours_val > 72:
        signals.append(('breach_window_too_long', 'Breach notification window is missing or exceeds 72 hours.', RiskSignal.Severity.MEDIUM))

    created = []
    for code, description, severity in signals:
        created.append(RiskSignal.objects.create(workflow=workflow, code=code, description=description, severity=severity))
    return created


def _attach_dpa_intake_evidence(*, workflow, organization, user, cleaned_values):
    """Promote staged Step 4 evidence to contract-scoped Documents."""
    step4 = cleaned_values.get('_dpa_step4', {})
    for evidence_key, evidence in step4.get('evidence', {}).items():
        storage_name = evidence.get('storage_name')
        if not storage_name or not default_storage.exists(storage_name):
            continue
        title = (
            'Security documentation'
            if evidence_key == 'security_document'
            else f'{evidence_key.replace("_document", "").replace("_", " ").title()} proposed wording'
        )
        with default_storage.open(storage_name, 'rb') as source:
            from contracts.services.document_version_service import create_document_version

            create_document_version(
                organization=organization,
                contract=workflow.contract,
                title=title,
                document_type=Document.DocType.EXHIBIT,
                status=Document.Status.DRAFT,
                description='Evidence captured during DPA Step 4 operational intake.',
                uploaded_by=user,
                actor=user,
                source='generated',
                file=File(source, name=evidence.get('original_name') or 'evidence'),
                supersede_prior=False,
            )
        default_storage.delete(storage_name)


def sync_command_center_work_item_for_workflow(workflow: Workflow) -> CommandCenterWorkItem:
    """The single, isolated Command Center integration point — deliberately
    kept out of contracts/services/command_center.py (uncommitted,
    in-progress work from a separate session) to avoid touching its batch
    projection logic. _work_item_href() in that module already checks
    action_path first, so this item resolves correctly without any change
    there; dashboard.html's Kanban "Draft" column already matches
    stage == 'Drafting', so no template change is needed either."""
    contract = workflow.contract
    current_step = (
        workflow.steps.filter(status=WorkflowStep.Status.IN_PROGRESS).order_by('order').first()
        or workflow.steps.filter(status=WorkflowStep.Status.PENDING).order_by('order').first()
    )
    risk_signals = list(workflow.risk_signals.order_by('-severity', 'detected_at'))
    highest_risk = risk_signals[0] if risk_signals else None
    severity_rank = {
        RiskSignal.Severity.CRITICAL: 4,
        RiskSignal.Severity.HIGH: 3,
        RiskSignal.Severity.MEDIUM: 2,
        RiskSignal.Severity.LOW: 1,
    }
    top_signal = max(risk_signals, key=lambda signal: severity_rank.get(signal.severity, 0)) if risk_signals else None
    current_stage = current_step.name if current_step else 'Intake'
    next_action = (
        'Review SCC position and DPO route'
        if top_signal and top_signal.code in {'scc_transfer_review', 'cross_border_no_mechanism'}
        else 'Review DPA risk signals'
        if top_signal
        else 'Open generated DPA workspace'
    )
    blocking_issue = top_signal.description if top_signal else 'Field capture complete; ready for governed review.'
    item, _ = CommandCenterWorkItem.objects.update_or_create(
        organization=workflow.organization,
        source_type=CommandCenterWorkItem.SourceType.WORKFLOW,
        source_model='Workflow',
        source_object_id=workflow.pk,
        defaults={
            'title': workflow.title,
            'subtitle': blocking_issue,
            'item_type': 'DPA workflow',
            'stage': current_stage,
            'status': CommandCenterWorkItem.Status.BLOCKED if top_signal and top_signal.severity in {RiskSignal.Severity.HIGH, RiskSignal.Severity.CRITICAL} else CommandCenterWorkItem.Status.OPEN,
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
                'contract_type': 'DPA',
                'current_stage': current_stage,
                'owner_label': (
                    workflow.created_by.get_full_name() or workflow.created_by.username
                    if workflow.created_by else 'Unassigned'
                ),
                'highest_risk_signal': top_signal.description if top_signal else 'No active risk signal',
                'blocking_issue': blocking_issue,
                'next_action': next_action,
                'self_serve_eligible': contract.risk_level == Contract.RiskLevel.LOW if contract else False,
            },
            'last_source_synced_at': timezone.now(),
        },
    )
    return item


@transaction.atomic
def create_dpa_workflow_instance(*, organization, user, cleaned_values: dict, request=None) -> Workflow:
    """The single orchestration entry point: creates the Contract, the
    Workflow instance, materializes its WorkflowSteps, stores FieldValues,
    renders and saves the DraftDocument, detects RiskSignals, and syncs the
    Command Center Priority Queue row — all in one transaction."""
    workflow_template = get_dpa_workflow_template()
    if workflow_template is None:
        raise ValueError('DPA Privacy Review Workflow template is not seeded.')

    field_defs = list(FieldDefinition.objects.filter(workflow_template=workflow_template))

    contract = Contract(
        title=f"DPA — {cleaned_values.get('counterparty') or 'Untitled counterparty'}",
        contract_type=Contract.ContractType.DPA,
        status=Contract.Status.IN_PROGRESS,
        created_by=user,
        lifecycle_stage=Contract.LifecycleStage.DRAFTING,
        risk_level=Contract.RiskLevel.LOW,
    )
    set_organization_on_instance(contract, organization)
    for field in field_defs:
        if field.maps_to_contract_field and field.key in cleaned_values:
            setattr(contract, field.maps_to_contract_field, cleaned_values[field.key])
    from contracts.services.contract_provenance import OriginKind, apply_provenance_fields, pin_workflow_provenance
    apply_provenance_fields(
        contract,
        origin_kind=OriginKind.WORKFLOW,
        origin_channel='dpa_workflow',
        actor=user,
        lock=False,
        validate=False,
    )
    contract.save()

    related_msa_id = cleaned_values.get('related_msa_id')
    if related_msa_id:
        related_msa = Contract.objects.filter(
            pk=related_msa_id, organization=organization, contract_type=Contract.ContractType.MSA,
        ).first()
        if related_msa:
            contract.parent_contract = related_msa
            contract.save(update_fields=['parent_contract', 'updated_at'])

    workflow = Workflow.objects.create(
        title='DPA Privacy Review Workflow',
        description=f"Privacy review for the DPA with {cleaned_values.get('counterparty') or 'this counterparty'}.",
        organization=organization,
        template=workflow_template,
        contract=contract,
        status=Workflow.Status.ACTIVE,
        created_by=user,
    )
    pin_workflow_provenance(contract, workflow, actor=user, request=request, channel='dpa_workflow')
    materialize_workflow_from_template(workflow)

    FieldValue.objects.bulk_create([
        FieldValue(workflow=workflow, field_definition=field, value=cleaned_values.get(field.key))
        for field in field_defs
    ])

    contract_template = get_dpa_contract_template()
    preview_content = render_dpa_live_preview(contract_template.body if contract_template else None, cleaned_values)
    DraftDocument.objects.create(
        workflow=workflow, contract=contract, content=preview_content, version=1, is_current=True, created_by=user,
    )

    _attach_dpa_intake_evidence(
        workflow=workflow, organization=organization, user=user, cleaned_values=cleaned_values,
    )

    risk_signals = detect_dpa_risk_signals(workflow, cleaned_values)
    if any(signal.severity in {RiskSignal.Severity.HIGH, RiskSignal.Severity.CRITICAL} for signal in risk_signals):
        contract.risk_level = Contract.RiskLevel.HIGH
    elif risk_signals:
        contract.risk_level = Contract.RiskLevel.MEDIUM
    contract.save(update_fields=['risk_level', 'updated_at'])

    sync_command_center_work_item_for_workflow(workflow)

    log_action(
        user, 'CREATE', 'Workflow', workflow.id, str(workflow),
        changes={'event': 'dpa_workflow_created', 'contract_id': contract.id},
        request=request, organization=organization,
    )
    return workflow
