"""Shared drafting-workspace mutation endpoints for MSA/DPA/NDA."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from contracts.middleware import log_action
from contracts.models import (
    ApprovalRule,
    Contract,
    FieldDefinition,
    FieldValue,
    OrganizationMembership,
    RiskSignal,
    Workflow,
    WorkflowStep,
)
from contracts.permissions import ContractAction, can_access_contract_action
from contracts.tenancy import get_user_organization


CONTRACT_TYPE_BY_KIND = {
    'msa': Contract.ContractType.MSA,
    'dpa': Contract.ContractType.DPA,
    'nda': Contract.ContractType.NDA,
}

SUBMIT_STEPS_BY_KIND = {
    'msa': {'LEGAL', 'FINANCE'},
    'dpa': {'LEGAL', 'PRIVACY'},
    'nda': {'LEGAL'},
}


def _workflow_for_actor(request, pk, *, kind, action=ContractAction.EDIT):
    organization = get_user_organization(request.user)
    workflow = get_object_or_404(
        Workflow.objects.select_related('contract', 'organization'),
        pk=pk,
        organization=organization,
        contract__contract_type=CONTRACT_TYPE_BY_KIND[kind],
    )
    if not can_access_contract_action(request.user, workflow.contract, action):
        return None, HttpResponseForbidden(f'You do not have permission to update this {kind.upper()}.')
    return workflow, None


def _review_rule(organization, approval_step, contract_type):
    return (
        ApprovalRule.objects.filter(
            organization=organization,
            is_active=True,
            approval_step=approval_step,
            trigger_type=ApprovalRule.TriggerType.CONTRACT_TYPE,
            trigger_value=contract_type,
        )
        .select_related('specific_approver')
        .order_by('order', 'id')
        .first()
    )


def _open_exception_count(workflow):
    return RiskSignal.objects.filter(workflow=workflow, is_resolved=False).count()


def _needs_review_remaining(workflow, kind):
    from contracts.views_domains.workflow_management import (
        _dpa_workspace_context,
        _msa_workspace_context,
        _nda_workspace_context,
    )

    if kind == 'msa':
        workspace = _msa_workspace_context(workflow)
    elif kind == 'dpa':
        workspace = _dpa_workspace_context(workflow)
    else:
        workspace = _nda_workspace_context(workflow)
    overview = workspace.get('document_overview') or {}
    return int(overview.get('needs_review') or 0), workspace


@login_required
@require_POST
def drafting_submit_for_review(request, pk, approval_step, *, kind):
    label = kind.upper()
    workflow, denied = _workflow_for_actor(request, pk, kind=kind)
    if denied:
        return denied

    open_exceptions = _open_exception_count(workflow)
    if open_exceptions:
        messages.error(
            request,
            f'Resolve {open_exceptions} open exception{"s" if open_exceptions != 1 else ""} '
            f'before submitting this {label} for review.',
        )
        return redirect('contracts:workflow_detail', pk=workflow.pk)

    remaining, workspace = _needs_review_remaining(workflow, kind)
    if remaining:
        messages.error(
            request,
            f'Confirm {remaining} remaining drafting section{"s" if remaining != 1 else ""} '
            f'before submitting this {label} for review.',
        )
        return redirect('contracts:workflow_detail', pk=workflow.pk)

    if kind == 'nda' and not workspace.get('legal_review_triggered'):
        messages.error(request, 'This NDA is self-serve eligible and does not require Legal review submission.')
        return redirect('contracts:workflow_detail', pk=workflow.pk)

    normalized_step = approval_step.upper()
    allowed = SUBMIT_STEPS_BY_KIND[kind]
    if normalized_step not in allowed:
        return HttpResponseForbidden(f'Unsupported {label} review route.')

    if kind == 'msa' and normalized_step == 'FINANCE' and not workspace.get('finance_approval_triggered'):
        messages.error(request, 'Finance review is not required for this MSA.')
        return redirect('contracts:workflow_detail', pk=workflow.pk)
    if kind == 'dpa' and normalized_step == 'PRIVACY' and not workspace.get('dpo_approval_triggered'):
        messages.error(request, 'Privacy / DPO review is not required for this DPA.')
        return redirect('contracts:workflow_detail', pk=workflow.pk)

    organization = workflow.organization
    contract_type = CONTRACT_TYPE_BY_KIND[kind]
    rule = _review_rule(organization, normalized_step, contract_type)
    reviewer = rule.specific_approver if rule else None
    if reviewer is None or reviewer.pk == (workflow.contract.owner_id or workflow.contract.created_by_id):
        step_label = 'Privacy' if normalized_step == 'PRIVACY' else normalized_step.title()
        messages.error(
            request,
            f'Configure a separate {step_label} approver for the {label} approval rule before submitting.',
        )
        return redirect('contracts:workflow_detail', pk=workflow.pk)
    if not OrganizationMembership.objects.filter(
        organization=organization,
        user=reviewer,
        is_active=True,
    ).exists():
        step_label = 'Privacy' if normalized_step == 'PRIVACY' else normalized_step.title()
        messages.error(request, f'The configured {step_label} approver is not an active workspace member.')
        return redirect('contracts:workflow_detail', pk=workflow.pk)

    from contracts.services.approval_workflow import ApprovalAccessDenied, get_approval_workflow_service

    try:
        approval = get_approval_workflow_service().submit_for_review(
            workflow.contract,
            request.user,
            reviewer,
            approval_step=normalized_step,
            rule=rule,
            comment=(request.POST.get('comment') or '').strip(),
            request=request,
            enforce_review_readiness=False,
        )
    except (ApprovalAccessDenied, ValueError) as exc:
        messages.error(request, str(exc))
    else:
        step_name = 'Privacy Review' if normalized_step == 'PRIVACY' else f'{normalized_step.title()} Review'
        WorkflowStep.objects.filter(
            workflow=workflow,
            name=step_name,
            status=WorkflowStep.Status.PENDING,
        ).update(status=WorkflowStep.Status.IN_PROGRESS)
        messages.success(
            request,
            f'{label} submitted to {approval.assigned_to_username or step_name} for review.',
        )
    return redirect('contracts:workflow_detail', pk=workflow.pk)


@login_required
@require_POST
def drafting_exception_action(request, pk, signal_id, *, kind):
    label = kind.upper()
    workflow, denied = _workflow_for_actor(request, pk, kind=kind)
    if denied:
        return denied
    signal = get_object_or_404(RiskSignal, pk=signal_id, workflow=workflow)
    action = (request.POST.get('action') or '').strip()
    reason = (request.POST.get('reason') or '').strip()
    comment = (request.POST.get('comment') or '').strip()
    owner_id = (request.POST.get('owner_id') or '').strip()
    event_prefix = f'{kind}_exception'

    if action in {'use_approved_wording', 'accept_fallback'}:
        signal.is_resolved = True
        signal.resolved_at = timezone.now()
        signal.save(update_fields=['is_resolved', 'resolved_at'])
        log_action(
            request.user,
            f'{event_prefix}_{action}',
            'RiskSignal',
            object_id=signal.pk,
            object_repr=signal.code,
            changes={'workflow_id': workflow.pk, 'decision': action, 'comment': comment},
            request=request,
            organization=workflow.organization,
        )
        messages.success(request, 'Exception resolved and recorded in the audit trail.')
    elif action == 'keep_exception':
        if not reason:
            messages.error(request, 'Keeping an exception requires a reason.')
            return redirect('contracts:workflow_detail', pk=workflow.pk)
        if not owner_id:
            messages.error(request, 'Keeping an exception requires an accountable owner.')
            return redirect('contracts:workflow_detail', pk=workflow.pk)
        owner = OrganizationMembership.objects.filter(
            organization=workflow.organization,
            user_id=owner_id,
            is_active=True,
        ).select_related('user').first()
        if owner is None:
            messages.error(request, 'Select an active workspace member as the accountable owner.')
            return redirect('contracts:workflow_detail', pk=workflow.pk)
        log_action(
            request.user,
            f'{event_prefix}_kept',
            'RiskSignal',
            object_id=signal.pk,
            object_repr=signal.code,
            changes={
                'workflow_id': workflow.pk,
                'reason': reason,
                'owner_id': owner.user_id,
                'owner': owner.user.get_full_name() or owner.user.username,
                'requires_approval_route': True,
                'comment': comment,
            },
            request=request,
            organization=workflow.organization,
        )
        from contracts.services.exception_dual_write import (
            ExceptionDualWriteError,
            SOURCE_KEEP_EXCEPTION,
            build_correlation_id,
            safe_mirror_legacy_exception,
        )
        try:
            safe_mirror_legacy_exception(
                source=SOURCE_KEEP_EXCEPTION,
                organization=workflow.organization,
                actor=request.user,
                owner=owner.user,
                title=f'Keep exception: {signal.code}',
                reason=reason,
                scope_object_model='RiskSignal',
                scope_object_id=signal.pk,
                correlation_id=build_correlation_id(
                    source=SOURCE_KEEP_EXCEPTION,
                    object_model='RiskSignal',
                    object_id=signal.pk,
                    suffix='kept',
                ),
                outcome='APPROVED',
                contract=getattr(workflow, 'contract', None),
                scope_reference={'workflow_id': workflow.pk, 'signal_code': signal.code},
                authority_basis='policy_owner',
                compensating_controls=(comment or 'Playbook deviation retained with accountable owner.'),
                granted_privileges=['policy.deviation'],
                risk_classification='MEDIUM',
                request=request,
            )
        except ExceptionDualWriteError as exc:
            messages.error(request, str(exc))
            return redirect('contracts:workflow_detail', pk=workflow.pk)
        messages.success(
            request,
            'Exception retained with accountable owner. The required approval route remains active.',
        )
    elif action == 'request_approval':
        log_action(
            request.user,
            f'{event_prefix}_approval_requested',
            'RiskSignal',
            object_id=signal.pk,
            object_repr=signal.code,
            changes={'workflow_id': workflow.pk, 'comment': comment or reason},
            request=request,
            organization=workflow.organization,
        )
        messages.success(request, 'Approval requested for this exception.')
    elif action == 'add_comment':
        if not comment:
            messages.error(request, 'Enter a comment before saving.')
            return redirect('contracts:workflow_detail', pk=workflow.pk)
        log_action(
            request.user,
            f'{event_prefix}_comment',
            'RiskSignal',
            object_id=signal.pk,
            object_repr=signal.code,
            changes={'workflow_id': workflow.pk, 'comment': comment},
            request=request,
            organization=workflow.organization,
        )
        messages.success(request, 'Comment added to the exception audit trail.')
    else:
        messages.error(request, 'Unsupported exception action.')
        return redirect('contracts:workflow_detail', pk=workflow.pk)

    if kind == 'msa':
        from contracts.services.msa_workflow import sync_command_center_work_item_for_workflow
        sync_command_center_work_item_for_workflow(workflow)
    elif kind == 'dpa':
        from contracts.services.dpa_workflow import sync_command_center_work_item_for_workflow
        sync_command_center_work_item_for_workflow(workflow)
    else:
        from contracts.services.nda_workflow import sync_command_center_work_item_for_workflow
        sync_command_center_work_item_for_workflow(workflow)
    return redirect('contracts:workflow_detail', pk=workflow.pk)


@login_required
@require_POST
def drafting_confirm_section(request, pk, section_id, *, kind):
    label = kind.upper()
    workflow, denied = _workflow_for_actor(request, pk, kind=kind)
    if denied:
        return denied
    safe_section = ''.join(ch if ch.isalnum() or ch in '-_' else '-' for ch in section_id)[:80]
    key = f'_section_confirmed_{safe_section}'
    definition, _ = FieldDefinition.objects.get_or_create(
        workflow_template=workflow.template,
        key=key,
        defaults={
            'label': f'Confirmed {safe_section}',
            'field_type': FieldDefinition.FieldType.BOOLEAN,
            'section': FieldDefinition.Section.SMART_QUESTIONS,
            'is_required': False,
            'help_text': f'Human confirmation for AI-assisted {label} section.',
            'order': 9000,
        },
    )
    FieldValue.objects.update_or_create(
        workflow=workflow,
        field_definition=definition,
        defaults={'value': True},
    )
    log_action(
        request.user,
        f'{kind}_section_confirmed',
        'DraftDocument',
        object_id=workflow.pk,
        object_repr=safe_section,
        changes={'section_id': safe_section},
        request=request,
        organization=workflow.organization,
    )
    remaining, workspace = _needs_review_remaining(workflow, kind)
    open_exceptions = workspace.get('open_exceptions') or 0
    if remaining:
        messages.success(
            request,
            f'Section confirmed. {remaining} section{"s" if remaining != 1 else ""} still need review.',
        )
    elif open_exceptions:
        messages.success(
            request,
            f'Section confirmed. Resolve {open_exceptions} open exception{"s" if open_exceptions != 1 else ""} '
            'before submitting for review.',
        )
    else:
        messages.success(request, 'Section confirmed. Drafting sections are ready for review submission.')

    if kind == 'msa':
        from contracts.services.msa_workflow import sync_command_center_work_item_for_workflow
        sync_command_center_work_item_for_workflow(workflow)
    elif kind == 'dpa':
        from contracts.services.dpa_workflow import sync_command_center_work_item_for_workflow
        sync_command_center_work_item_for_workflow(workflow)
    else:
        from contracts.services.nda_workflow import sync_command_center_work_item_for_workflow
        sync_command_center_work_item_for_workflow(workflow)
    return redirect('contracts:workflow_detail', pk=workflow.pk)
