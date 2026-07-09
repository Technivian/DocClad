"""New Contract → DPA: the first flagship "workflow-first" flow.

A parallel view to ContractCreateView, reached only from the DPA entry
card on Stage 1 — kept separate rather than branching inside
ContractCreateView, since DPA's fields are data-driven (FieldDefinition)
rather than a fixed ModelForm, and creation writes across six tables in one
transaction. ContractCreateView/ContractForm/contract_form.html stay
untouched for every other contract type.
"""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.views import View

from contracts.models import FieldDefinition
from contracts.services.dpa_workflow import (
    create_dpa_workflow_instance,
    get_clause_library_count,
    get_dpa_approval_route,
    get_dpa_contract_template,
    get_dpa_workflow_template,
    get_field_definitions_by_section,
    render_dpa_live_preview,
)
from contracts.tenancy import get_user_organization


def _coerce_field_value(field, raw):
    """Coerce a raw POST string per FieldDefinition.field_type. Returns
    None for a value that couldn't be parsed, so required-field validation
    catches it the same way a blank value would be caught."""
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


def _validate_dpa_submission(post_data, workflow_template):
    """Dynamic-field validation — not a Django Form/ModelForm, since the
    field set is data-driven. Returns (cleaned_values, errors)."""
    field_defs = FieldDefinition.objects.filter(workflow_template=workflow_template)
    cleaned = {}
    errors = {}
    for field in field_defs:
        raw = post_data.get(f'field_{field.id}')
        if field.field_type == FieldDefinition.FieldType.BOOLEAN:
            raw = post_data.get(f'field_{field.id}')  # checkbox: absent when unchecked
        value = _coerce_field_value(field, raw)
        if field.is_required and field.field_type != FieldDefinition.FieldType.BOOLEAN and (value is None or value == ''):
            errors[field.key] = f'{field.label} is required.'
        cleaned[field.key] = value
    return cleaned, errors


class DPAWorkflowBuilderView(LoginRequiredMixin, View):
    template_name = 'contracts/dpa_workflow_builder.html'

    def _context(self, request, *, errors=None, posted=None):
        organization = get_user_organization(request.user)
        workflow_template = get_dpa_workflow_template()
        contract_template = get_dpa_contract_template()
        fields_by_section = get_field_definitions_by_section(workflow_template)
        approval_route = get_dpa_approval_route(workflow_template)
        return {
            'workflow_template': workflow_template,
            'fields_by_section': fields_by_section,
            'template_body': contract_template.body if contract_template else None,
            'approval_route': approval_route,
            'clause_library_count': get_clause_library_count(organization, 'DPA'),
            'gemini_ai_enabled': False,
            'errors': errors or {},
            'posted': posted or {},
        }

    def get(self, request):
        return render(request, self.template_name, self._context(request))

    def post(self, request):
        organization = get_user_organization(request.user)
        workflow_template = get_dpa_workflow_template()
        cleaned_values, errors = _validate_dpa_submission(request.POST, workflow_template)
        if errors:
            messages.error(request, 'Complete the required fields before generating the governed draft.')
            return render(request, self.template_name, self._context(request, errors=errors, posted=cleaned_values))

        workflow = create_dpa_workflow_instance(
            organization=organization, user=request.user, cleaned_values=cleaned_values, request=request,
        )
        messages.success(request, f'"{workflow.title}" generated — it now appears in the Command Center Priority Queue.')
        return redirect(reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))
