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

SECTION_DISPLAY = {
    FieldDefinition.Section.BASIC_DETAILS: {
        'number': '1',
        'eyebrow': 'Basic details',
        'title': 'Counterparty and dates',
        'summary': 'Capture the contract anchor points before governance kicks in.',
        'slug': 'basic-details',
    },
    FieldDefinition.Section.PRIVACY_DETAILS: {
        'number': '2',
        'eyebrow': 'Privacy details',
        'title': 'Processing scope',
        'summary': 'Define what data is in scope and who it relates to.',
        'slug': 'privacy-details',
    },
    FieldDefinition.Section.LEGAL_POSITION: {
        'number': '3',
        'eyebrow': 'Legal position',
        'title': 'Governing law and fallback language',
        'summary': 'Set the legal default position and fallback language.',
        'slug': 'legal-position',
    },
    FieldDefinition.Section.PRIVACY_QUESTIONS: {
        'number': '4',
        'eyebrow': 'AI smart questions',
        'title': 'Risk and routing triggers',
        'summary': 'Surface the privacy and transfer questions that affect review routing.',
        'slug': 'privacy-questions',
    },
}


def _field_has_value(field, value):
    if field.field_type == FieldDefinition.FieldType.BOOLEAN:
        return value is not None
    if value in (None, ''):
        return False
    return True


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
        clause_library_count = get_clause_library_count(organization, 'DPA')
        posted_values = posted or {}
        errors = errors or {}

        section_cards = []
        total_required = 0
        completed_required = 0
        missing_required_labels = []
        active_section_slug = None
        for section in (
            FieldDefinition.Section.BASIC_DETAILS,
            FieldDefinition.Section.PRIVACY_DETAILS,
            FieldDefinition.Section.LEGAL_POSITION,
            FieldDefinition.Section.PRIVACY_QUESTIONS,
        ):
            fields = list(fields_by_section.get(section, []))
            required_fields = [field for field in fields if field.is_required and field.field_type != FieldDefinition.FieldType.BOOLEAN]
            missing_fields = [field for field in required_fields if not _field_has_value(field, posted_values.get(field.key))]
            total_required += len(required_fields)
            completed_required += len(required_fields) - len(missing_fields)
            missing_required_labels.extend(field.label for field in missing_fields)
            has_errors = any(field.key in errors for field in fields)
            if active_section_slug is None and (missing_fields or has_errors):
                active_section_slug = SECTION_DISPLAY[section]['slug']
            section_cards.append({
                'section': section,
                'slug': SECTION_DISPLAY[section]['slug'],
                'number': SECTION_DISPLAY[section]['number'],
                'eyebrow': SECTION_DISPLAY[section]['eyebrow'],
                'title': SECTION_DISPLAY[section]['title'],
                'summary': SECTION_DISPLAY[section]['summary'],
                'fields': fields,
                'required_count': len(required_fields),
                'completed_count': len(required_fields) - len(missing_fields),
                'missing_count': len(missing_fields),
                'missing_labels': [field.label for field in missing_fields],
                'has_errors': has_errors,
                'is_open': False,
                'status_label': (
                    'Complete' if not missing_fields and required_fields else
                    'Optional' if not required_fields else
                    f'{len(missing_fields)} missing'
                ),
                'status_tone': (
                    'clear' if not missing_fields and required_fields else
                    'neutral' if not required_fields else
                    'attention'
                ),
            })

        if active_section_slug is None and section_cards:
            active_section_slug = section_cards[0]['slug']
        for section in section_cards:
            section['is_open'] = section['slug'] == active_section_slug

        total_completed = completed_required
        missing_total = total_required - completed_required
        completion_percent = round((total_completed / total_required) * 100) if total_required else 100
        approval_route_label = ' → '.join(step.name for step in approval_route) if approval_route else 'Not configured'
        governance_badges = [
            {
                'label': 'Template selected',
                'value': 'GDPR Processor DPA',
                'target': 'dpa-gov-template',
                'tab': 'governance',
                'tone': 'clear',
            },
            {
                'label': 'Playbook applied',
                'value': 'GDPR Processor DPA playbook',
                'target': 'dpa-gov-template',
                'tab': 'governance',
                'tone': 'clear',
            },
            {
                'label': 'Clause library',
                'value': f'{clause_library_count} approved clause' + ('s' if clause_library_count != 1 else ''),
                'target': 'dpa-gov-template',
                'tab': 'governance',
                'tone': 'neutral',
            },
            {
                'label': 'Risk checks',
                'value': 'Privacy, SCC, and subprocessor rules',
                'target': 'dpa-gov-risk',
                'tab': 'governance',
                'tone': 'warn',
            },
            {
                'label': 'Approval route',
                'value': approval_route_label,
                'target': 'dpa-gov-approval',
                'tab': 'governance',
                'tone': 'neutral',
            },
            {
                'label': 'Audit trail',
                'value': 'Activates on generate',
                'target': 'dpa-audit-trail',
                'tab': 'audit',
                'tone': 'neutral',
            },
        ]

        audit_preview = [
            {'event': 'Template selected', 'meta': 'Approved GDPR Processor DPA template loaded.'},
            {'event': 'Field values captured', 'meta': 'Mapped to contract, workflow, and field-value rows.'},
            {'event': 'Risk checks run', 'meta': 'SCC, DPO, and subprocessor rules are ready to persist.'},
            {'event': 'Approval route generated', 'meta': approval_route_label},
        ]
        return {
            'workflow_template': workflow_template,
            'fields_by_section': fields_by_section,
            'section_cards': section_cards,
            'template_body': contract_template.body if contract_template else None,
            'approval_route': approval_route,
            'governance_badges': governance_badges,
            'audit_preview': audit_preview,
            'total_required_fields': total_required,
            'completed_required_fields': total_completed,
            'completion_percent': completion_percent,
            'missing_required_fields': missing_total,
            'missing_required_labels': missing_required_labels,
            'active_section_slug': active_section_slug,
            'clause_library_count': clause_library_count,
            'gemini_ai_enabled': False,
            'errors': errors,
            'posted': posted_values,
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
