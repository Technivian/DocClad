from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from contracts.models import CommandCenterWorkItem, Contract, Workflow, WorkflowStep
from contracts.services.dpa_workflow import create_dpa_workflow_instance, sync_command_center_work_item_for_workflow as sync_dpa_item
from contracts.services.msa_workflow import create_msa_workflow_instance, sync_command_center_work_item_for_workflow as sync_msa_item
from contracts.services.nda_workflow import create_nda_workflow_instance, sync_command_center_work_item_for_workflow as sync_nda_item


@dataclass(frozen=True)
class DemoWorkflowSeedResult:
    key: str
    workflow_id: int
    title: str


def _reset_demo_contract(organization, slug: str) -> None:
    Contract.objects.filter(
        organization=organization,
        source_system='demo_seed',
        source_system_id=slug,
    ).delete()


def _set_current_stage(workflow: Workflow, target_step_name: str) -> None:
    now = timezone.now()
    reached_target = False
    for step in workflow.steps.order_by('order', 'pk'):
        if step.name == target_step_name:
            step.status = WorkflowStep.Status.IN_PROGRESS
            step.completed_at = None
            reached_target = True
        elif not reached_target:
            if step.status != WorkflowStep.Status.SKIPPED:
                step.status = WorkflowStep.Status.COMPLETED
                step.completed_at = now
        else:
            if step.status != WorkflowStep.Status.SKIPPED:
                step.status = WorkflowStep.Status.PENDING
                step.completed_at = None
        step.save(update_fields=['status', 'completed_at'])


def _update_work_item(workflow: Workflow, *, stage: str, risk_personality: str, highest_risk_signal: str, next_action: str, approval_route: str, blocking_issue: str, status: str | None = None) -> None:
    item = CommandCenterWorkItem.objects.get(workflow=workflow)
    flags = dict(item.flags or {})
    flags.update({
        'current_stage': stage,
        'risk_personality': risk_personality,
        'highest_risk_signal': highest_risk_signal,
        'next_action': next_action,
        'approval_route': approval_route,
        'blocking_issue': blocking_issue,
        'self_serve_eligible': risk_personality == 'Self-serve eligible',
    })
    item.stage = stage
    item.subtitle = blocking_issue
    item.flags = flags
    item.action_label = 'Open workspace'
    if status:
        item.status = status
    item.last_source_synced_at = timezone.now()
    item.save(update_fields=['stage', 'subtitle', 'flags', 'action_label', 'status', 'last_source_synced_at', 'updated_at'])


@transaction.atomic
def seed_demo_command_center_workflows(*, organization, user) -> list[DemoWorkflowSeedResult]:
    seeded: list[DemoWorkflowSeedResult] = []

    _reset_demo_contract(organization, 'northwind-dpa')
    dpa_workflow = create_dpa_workflow_instance(
        organization=organization,
        user=user,
        cleaned_values={
            'counterparty': 'Northwind Inc.',
            'source_system': 'demo_seed',
            'source_system_id': 'northwind-dpa',
            'start_date': '2026-09-01',
            'governing_law': 'Netherlands',
            'jurisdiction': 'Amsterdam',
            'contract_owner': 'Avery Brooks',
            'processing_purpose': 'Cloud-hosted support and analytics services.',
            'personal_data_categories': 'Employee account data and customer business contact details.',
            'data_subjects': 'Customer administrators and support users.',
            'liability_position': 'Approved SCC fallback remains required before execution.',
            'personal_data_involved': True,
            'cross_border_transfer': True,
            'subprocessors_used': True,
            'transfer_mechanism': 'SCC',
            'breach_notification_hours': 48,
            'dpo_contact': 'dpo@clmone.example',
            'include_scc_fallback': True,
        },
    )
    dpa_workflow.title = 'Northwind DPA Privacy Review Workflow'
    dpa_workflow.description = 'Demo DPA workflow showing SCC fallback and subprocessor governance.'
    dpa_workflow.save(update_fields=['title', 'description'])
    dpa_workflow.contract.title = 'Northwind DPA'
    dpa_workflow.contract.risk_level = Contract.RiskLevel.HIGH
    dpa_workflow.contract.save(update_fields=['title', 'risk_level'])
    _set_current_stage(dpa_workflow, 'DPO / Privacy Review')
    sync_dpa_item(dpa_workflow)
    _update_work_item(
        dpa_workflow,
        stage='DPO Review',
        risk_personality='Privacy risk',
        highest_risk_signal='EEA transfer + subprocessors',
        next_action='Review SCC fallback',
        approval_route='Contract Owner → Legal → DPO → Signature',
        blocking_issue='SCC fallback must be confirmed before DPO sign-off.',
        status=CommandCenterWorkItem.Status.BLOCKED,
    )
    seeded.append(DemoWorkflowSeedResult('northwind-dpa', dpa_workflow.pk, dpa_workflow.title))

    _reset_demo_contract(organization, 'acme-msa')
    msa_workflow = create_msa_workflow_instance(
        organization=organization,
        user=user,
        cleaned_values={
            'counterparty': 'Acme Corporation',
            'source_system': 'demo_seed',
            'source_system_id': 'acme-msa',
            'start_date': '2026-09-15',
            'contract_owner': 'Avery Brooks',
            'business_unit': 'Revenue Operations',
            'internal_reference': 'DEMO-MSA-001',
            'value': 375000,
            'currency': 'EUR',
            'payment_terms': 'Net 30',
            'initial_term': '24 months',
            'renewal_type': 'Auto-renew',
            'termination_notice_period': 60,
            'services_description': 'Managed implementation and commercial support services.',
            'sow_required': True,
            'deliverables_defined': True,
            'acceptance_criteria_required': True,
            'governing_law': 'Netherlands',
            'jurisdiction': 'Amsterdam',
            'liability_cap': '4x annual fees',
            'confidentiality_period': '5 years',
            'ip_ownership': 'Customer',
            'personal_data_involved': False,
            'value_above_threshold_confirmed': True,
            'liability_cap_nonstandard': True,
            'services_involve_personal_data': False,
            'auto_renewal_included': False,
            'ip_ownership_nonstandard': False,
            'governing_law_nonpreferred': False,
        },
    )
    msa_workflow.title = 'Acme MSA Commercial Review Workflow'
    msa_workflow.description = 'Demo MSA workflow showing liability fallback and finance routing.'
    msa_workflow.save(update_fields=['title', 'description'])
    msa_workflow.contract.title = 'Acme MSA'
    msa_workflow.contract.risk_level = Contract.RiskLevel.HIGH
    msa_workflow.contract.save(update_fields=['title', 'risk_level'])
    _set_current_stage(msa_workflow, 'Legal Review')
    sync_msa_item(msa_workflow)
    _update_work_item(
        msa_workflow,
        stage='Legal Review',
        risk_personality='Commercial risk',
        highest_risk_signal='Liability cap outside playbook + finance threshold',
        next_action='Review fallback clause',
        approval_route='Contract Owner → Legal → Finance → Signature',
        blocking_issue='Fallback liability clause requires Legal review before Finance sign-off.',
        status=CommandCenterWorkItem.Status.BLOCKED,
    )
    seeded.append(DemoWorkflowSeedResult('acme-msa', msa_workflow.pk, msa_workflow.title))

    _reset_demo_contract(organization, 'brightlane-nda')
    nda_workflow = create_nda_workflow_instance(
        organization=organization,
        user=user,
        cleaned_values={
            'counterparty': 'Brightlane Ltd',
            'source_system': 'demo_seed',
            'source_system_id': 'brightlane-nda',
            'start_date': '2026-10-01',
            'contract_owner': 'Avery Brooks',
            'business_unit': 'Business Development',
            'internal_reference': 'DEMO-NDA-001',
            'nda_type': 'Mutual',
            'confidentiality_purpose': 'partnership diligence and product evaluation',
            'confidentiality_period': 2,
            'disclosure_scope': 'commercial roadmap and integration planning information',
            'permitted_recipients': 'employees and external counsel with a need to know',
            'governing_law': 'Netherlands',
            'jurisdiction': 'Amsterdam',
            'residual_knowledge_included': False,
            'injunctive_relief_included': True,
            'personal_data_involved': False,
            'confidentiality_period_nonstandard': False,
            'personal_data_confirmed': False,
            'residual_knowledge_nonstandard': False,
            'governing_law_nonpreferred': False,
        },
    )
    nda_workflow.title = 'Brightlane NDA Self-Serve Workflow'
    nda_workflow.description = 'Demo NDA workflow showing self-serve signature readiness.'
    nda_workflow.save(update_fields=['title', 'description'])
    nda_workflow.contract.title = 'Brightlane NDA'
    nda_workflow.contract.risk_level = Contract.RiskLevel.LOW
    nda_workflow.contract.save(update_fields=['title', 'risk_level'])
    _set_current_stage(nda_workflow, 'Signature')
    sync_nda_item(nda_workflow)
    _update_work_item(
        nda_workflow,
        stage='Ready for Signature',
        risk_personality='Self-serve eligible',
        highest_risk_signal='No legal risk detected',
        next_action='Send for signature',
        approval_route='Contract Owner → Signature',
        blocking_issue='No legal risk detected; governed self-serve NDA can proceed to signature.',
        status=CommandCenterWorkItem.Status.OPEN,
    )
    seeded.append(DemoWorkflowSeedResult('brightlane-nda', nda_workflow.pk, nda_workflow.title))

    return seeded
