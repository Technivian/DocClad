"""New Contract -> MSA governed drafting cockpit."""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST
from django.views import View

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
from contracts.middleware import log_action
from contracts.permissions import ContractAction, can_access_contract_action
from contracts.services.finance_approval_policy import get_finance_approval_threshold
from contracts.services.msa_workflow import (
    create_msa_document_artifact,
    create_msa_workflow_instance,
    get_clause_library_count,
    get_field_definitions_by_section,
    get_msa_approval_route,
    get_msa_contract_template,
    get_msa_workflow_template,
    sync_command_center_work_item_for_workflow,
)
from contracts.tenancy import get_user_organization
from django.utils import timezone


def _coerce_field_value(field, raw):
    if field.field_type == FieldDefinition.FieldType.BOOLEAN:
        return raw in ('true', 'on', '1', 'True')
    if field.field_type == FieldDefinition.FieldType.DATE:
        if not raw:
            return None
        return parse_date(raw)
    if field.field_type == FieldDefinition.FieldType.NUMBER:
        if raw in (None, ''):
            return None
        try:
            return float(raw) if '.' in raw else int(raw)
        except (TypeError, ValueError):
            return None
    return (raw or '').strip()


def _validate_msa_submission(post_data, workflow_template):
    field_defs = FieldDefinition.objects.filter(workflow_template=workflow_template)
    cleaned = {}
    errors = {}
    for field in field_defs:
        raw = post_data.get(f'field_{field.id}')
        if field.field_type == FieldDefinition.FieldType.BOOLEAN:
            raw = post_data.get(f'field_{field.id}')
        value = _coerce_field_value(field, raw)
        if field.is_required and field.field_type != FieldDefinition.FieldType.BOOLEAN and (value is None or value == ''):
            errors[field.key] = f'{field.label} is required.'
        if value and field.key.endswith('email'):
            try:
                validate_email(value)
            except ValidationError:
                errors[field.key] = f'Enter a valid email address for {field.label.lower()}.'
        cleaned[field.key] = value
    return cleaned, errors


class MSAWorkflowBuilderView(LoginRequiredMixin, View):
    template_name = 'contracts/msa_workflow_builder.html'

    def _context(self, request, *, errors=None, posted=None):
        organization = get_user_organization(request.user)
        workflow_template = get_msa_workflow_template()
        contract_template = get_msa_contract_template()
        fields_by_section = get_field_definitions_by_section(workflow_template)
        approval_route = get_msa_approval_route(workflow_template)
        return {
            'workflow_template': workflow_template,
            'fields_by_section': fields_by_section,
            'template_body': contract_template.body if contract_template else None,
            'approval_route': approval_route,
            'clause_library_count': get_clause_library_count(organization, 'MSA'),
            'gemini_ai_enabled': False,
            'finance_approval_threshold': int(get_finance_approval_threshold()),
            'errors': errors or {},
            'posted': posted or {},
        }

    def get(self, request):
        return render(request, self.template_name, self._context(request))

    def post(self, request):
        organization = get_user_organization(request.user)
        workflow_template = get_msa_workflow_template()
        cleaned_values, errors = _validate_msa_submission(request.POST, workflow_template)
        if errors:
            messages.error(request, 'Complete the required fields before generating the governed draft.')
            return render(request, self.template_name, self._context(request, errors=errors, posted=cleaned_values))

        workflow = create_msa_workflow_instance(
            organization=organization,
            user=request.user,
            cleaned_values=cleaned_values,
            request=request,
        )
        messages.success(request, f'"{workflow.title}" generated — it now appears in the Command Center Priority Queue.')
        return redirect(reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))


def _msa_review_rule(organization, approval_step):
    """Return the explicitly configured MSA reviewer rule for this workspace."""
    return (
        ApprovalRule.objects.filter(
            organization=organization,
            is_active=True,
            approval_step=approval_step,
            trigger_type=ApprovalRule.TriggerType.CONTRACT_TYPE,
            trigger_value__iexact=Contract.ContractType.MSA,
        )
        .select_related('specific_approver')
        .order_by('order', 'id')
        .first()
    )


@login_required
@require_POST
def msa_submit_for_review(request, pk, approval_step):
    """Submit the generated MSA to its configured Legal or Finance reviewer."""
    from contracts.views_domains.drafting_workspace_actions import drafting_submit_for_review

    return drafting_submit_for_review(request, pk, approval_step, kind='msa')


@login_required
@require_POST
def msa_export_document(request, pk, artifact_type):
    """Create and download an auditable DOCX artifact from the current MSA draft."""
    organization = get_user_organization(request.user)
    workflow = get_object_or_404(
        Workflow.objects.select_related('contract', 'organization'),
        pk=pk,
        organization=organization,
        contract__contract_type=Contract.ContractType.MSA,
    )
    if not can_access_contract_action(request.user, workflow.contract, ContractAction.VIEW):
        return HttpResponseForbidden('You do not have permission to export this MSA.')
    try:
        document = create_msa_document_artifact(
            workflow=workflow,
            user=request.user,
            artifact_type=artifact_type,
            request=request,
        )
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect('contracts:workflow_detail', pk=workflow.pk)
    return redirect('contracts:document_download', pk=document.pk)


def _msa_workflow_for_actor(request, pk, action=ContractAction.EDIT):
    organization = get_user_organization(request.user)
    workflow = get_object_or_404(
        Workflow.objects.select_related('contract', 'organization'),
        pk=pk,
        organization=organization,
        contract__contract_type=Contract.ContractType.MSA,
    )
    if not can_access_contract_action(request.user, workflow.contract, action):
        return None, HttpResponseForbidden('You do not have permission to update this MSA.')
    return workflow, None


@login_required
@require_POST
def msa_exception_action(request, pk, signal_id):
    """Resolve, keep, or route an MSA drafting exception with audit."""
    from contracts.views_domains.drafting_workspace_actions import drafting_exception_action

    return drafting_exception_action(request, pk, signal_id, kind='msa')


@login_required
@require_POST
def msa_confirm_section(request, pk, section_id):
    """Record human confirmation for an AI-assisted drafting section."""
    from contracts.views_domains.drafting_workspace_actions import drafting_confirm_section

    return drafting_confirm_section(request, pk, section_id, kind='msa')
