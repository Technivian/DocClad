"""New Contract → DPA: the first flagship "workflow-first" flow.

A parallel view to ContractCreateView, reached only from the DPA entry
card on Stage 1 — kept separate rather than branching inside
ContractCreateView, since DPA's fields are data-driven (FieldDefinition)
rather than a fixed ModelForm, and creation writes across six tables in one
transaction. ContractCreateView/ContractForm/contract_form.html stay
untouched for every other contract type.
"""
import os
from uuid import uuid4

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.storage import default_storage
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.utils.text import get_valid_filename
from django.views import View

from contracts.models import Contract, FieldDefinition
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


# The DPA is intentionally collected in product-language steps rather than
# exposing the underlying FieldDefinition sections as a workbench.
DPA_INTAKE_STEPS = (
    {
        'slug': 'agreement-details',
        'title': 'Agreement details',
        'summary': 'Set the parties, owner, and effective date for this DPA.',
        'keys': ('counterparty', 'contract_owner', 'start_date'),
    },
    {
        'slug': 'processing-activities',
        'title': 'Processing activities',
        'summary': 'Describe why the processing is needed and the service in scope.',
        'keys': ('processing_purpose',),
    },
    {
        'slug': 'data-and-transfers',
        'title': 'Data, subjects and transfers',
        'summary': 'Capture data scope, processors, subprocessors, and transfer posture.',
        'keys': (
            'personal_data_categories', 'data_subjects', 'personal_data_involved',
            'subprocessors_used', 'cross_border_transfer', 'special_categories_data',
            'transfer_mechanism', 'include_scc_fallback',
        ),
    },
    {
        'slug': 'security-and-review',
        'title': 'Security and review',
        'summary': 'Capture security evidence and proposed contract positions.',
        'keys': (
            'security_measures_provided', 'security_assurance_available',
            'encryption_confirmed', 'access_controls_mfa_confirmed',
            'privacy_contact_name', 'privacy_contact_role', 'privacy_contact_email',
            'privacy_contact_phone', 'breach_notification_commitment',
            'breach_other_period', 'governing_law', 'audit_rights_position',
            'deletion_return_position', 'dpa_liability_position',
        ),
        # Legacy definitions remain available for direct API callers but are
        # not requester-facing Step 4 controls.
        'hidden_keys': ('breach_notification_hours', 'dpo_contact', 'liability_position'),
    },
)

_DPA_INTAKE_SESSION_KEY = 'dpa_intake_v1'

DPA_DATA_CATEGORIES = (
    'Identity and contact details', 'Employment information', 'Payroll and salary data',
    'Bank details', 'Tax information', 'Absence or health information',
    'Technical or account data', 'Other',
)
DPA_DATA_SUBJECTS = (
    'Employees', 'Contractors', 'Job applicants', 'Former employees',
    'Client contacts', 'Dependants or beneficiaries', 'Other',
)
DPA_COUNTRIES = (
    ('Austria', True), ('Belgium', True), ('Bulgaria', True), ('Croatia', True),
    ('Cyprus', True), ('Czechia', True), ('Denmark', True), ('Estonia', True),
    ('Finland', True), ('France', True), ('Germany', True), ('Greece', True),
    ('Hungary', True), ('Ireland', True), ('Italy', True), ('Latvia', True),
    ('Lithuania', True), ('Luxembourg', True), ('Malta', True), ('Netherlands', True),
    ('Poland', True), ('Portugal', True), ('Romania', True), ('Slovakia', True),
    ('Slovenia', True), ('Spain', True), ('Sweden', True),
    ('United Kingdom', False), ('United States', False), ('Canada', False),
    ('India', False), ('Singapore', False), ('Australia', False), ('Other', False),
)
DPA_TRANSFER_SAFEGUARDS = (
    'Adequacy decision', 'Standard Contractual Clauses', 'Binding Corporate Rules',
    'EU-US Data Privacy Framework', 'Other', 'Not confirmed',
)
_EEA_COUNTRIES = {country for country, is_eea in DPA_COUNTRIES if is_eea}
_TRANSFER_MECHANISM_MAP = {
    'Adequacy decision': 'Adequacy Decision',
    'Standard Contractual Clauses': 'SCC',
    'Binding Corporate Rules': 'BCR',
    'EU-US Data Privacy Framework': 'EU-US Data Privacy Framework',
    'Other': 'Other',
    'Not confirmed': 'None',
}

DPA_OPERATIONAL_ANSWER_CHOICES = (
    ('yes', 'Yes'), ('no', 'No'), ('not_sure', 'Not sure'),
)
DPA_BREACH_COMMITMENTS = (
    ('approved_standard', 'Approved standard'),
    ('24_hours', '24 hours'),
    ('48_hours', '48 hours'),
    ('72_hours', '72 hours'),
    ('other', 'Other proposed period'),
    ('not_confirmed', 'Not confirmed'),
)
DPA_POSITION_CHOICES = (
    ('accepted', 'Accepted'),
    ('deviation', 'Deviation proposed'),
    ('not_confirmed', 'Not confirmed'),
)
DPA_GOVERNING_LAWS = (
    'Netherlands', 'England and Wales', 'Ireland', 'Germany',
    'State of Delaware', 'New York',
)
_DPA_POSITION_KEYS = (
    ('audit_rights', 'Standard audit rights accepted?'),
    ('deletion_return', 'Standard deletion and return terms accepted?'),
    ('dpa_liability', 'Standard DPA liability position accepted?'),
)
_DPA_BREACH_HOURS = {
    'approved_standard': 72, '24_hours': 24, '48_hours': 48, '72_hours': 72,
}


def _stage_dpa_upload(upload, organization):
    """Hold intake evidence in private storage until a DPA Contract exists."""
    if not upload:
        return None
    safe_name = get_valid_filename(os.path.basename(upload.name)) or 'evidence'
    storage_name = default_storage.save(
        f'dpa-intake/{getattr(organization, "pk", "unknown")}/{uuid4().hex}-{safe_name}',
        upload,
    )
    return {
        'storage_name': storage_name,
        'original_name': safe_name,
        'content_type': getattr(upload, 'content_type', ''),
    }


def _step4_facts_from_post(post_data, files, previous=None, organization=None):
    facts = dict(previous or {})
    for key in (
        'security_measures_provided', 'security_assurance_available',
        'encryption_confirmed', 'access_controls_mfa_confirmed',
        'privacy_contact_name', 'privacy_contact_role', 'privacy_contact_email',
        'privacy_contact_phone', 'breach_notification_commitment',
        'breach_other_period', 'related_msa_id', 'governing_law_mode',
        'governing_law',
    ):
        facts[key] = (post_data.get(f'step4_{key}', '') or '').strip()

    positions = {}
    for key, _label in _DPA_POSITION_KEYS:
        positions[key] = {
            'status': (post_data.get(f'step4_{key}_position', '') or '').strip(),
            'wording': (post_data.get(f'step4_{key}_wording', '') or '').strip(),
            'explanation': (post_data.get(f'step4_{key}_explanation', '') or '').strip(),
        }
    facts['positions'] = positions

    evidence = dict(facts.get('evidence', {}))
    for key in ('security_document',) + tuple(f'{position}_document' for position, _ in _DPA_POSITION_KEYS):
        staged = _stage_dpa_upload(files.get(f'step4_{key}'), organization)
        if staged:
            evidence[key] = staged
    facts['evidence'] = evidence
    return facts


def _related_msas(organization):
    if not organization:
        return []
    return list(
        Contract.objects.filter(
            organization=organization,
            contract_type=Contract.ContractType.MSA,
        ).exclude(governing_law='').order_by('title').values('id', 'title', 'governing_law')
    )


def _step4_selected_msa(facts, related_msas):
    try:
        msa_id = int(facts.get('related_msa_id') or 0)
    except (TypeError, ValueError):
        return None
    return next((msa for msa in related_msas if msa['id'] == msa_id), None)


def _apply_step4_facts(values, facts, related_msas):
    """Translate operational facts to persisted DPA field values and rules."""
    values = dict(values)
    selected_msa = _step4_selected_msa(facts, related_msas)
    inherited_law = selected_msa['governing_law'] if selected_msa else ''
    manual_law = facts.get('governing_law', '')
    governing_law = inherited_law if facts.get('governing_law_mode') == 'inherit' and inherited_law else manual_law

    values.update({
        'security_measures_provided': facts.get('security_measures_provided', ''),
        'security_assurance_available': facts.get('security_assurance_available', ''),
        'encryption_confirmed': facts.get('encryption_confirmed', ''),
        'access_controls_mfa_confirmed': facts.get('access_controls_mfa_confirmed', ''),
        'privacy_contact_name': facts.get('privacy_contact_name', ''),
        'privacy_contact_role': facts.get('privacy_contact_role', ''),
        'privacy_contact_email': facts.get('privacy_contact_email', ''),
        'privacy_contact_phone': facts.get('privacy_contact_phone', ''),
        'breach_notification_commitment': facts.get('breach_notification_commitment', ''),
        'breach_other_period': facts.get('breach_other_period', ''),
        'governing_law': governing_law,
        'related_msa_id': selected_msa['id'] if selected_msa else None,
        'governing_law_changed': bool(inherited_law and manual_law and manual_law != inherited_law),
        'security_document_provided': bool(facts.get('evidence', {}).get('security_document')),
        '_dpa_step4': facts,
        # Legacy merge fields are derived, never requester-authored.
        'dpo_contact': facts.get('privacy_contact_email', ''),
        'breach_notification_hours': _DPA_BREACH_HOURS.get(facts.get('breach_notification_commitment')),
        'liability_position': '',
    })
    for key, _label in _DPA_POSITION_KEYS:
        position = facts['positions'][key]
        values[f'{key}_position'] = position['status']
        values[f'{key}_proposed_wording'] = position['wording']
        values[f'{key}_explanation'] = position['explanation']
    return values


def _validate_step4_facts(facts, related_msas):
    errors = {}
    for key in (
        'security_measures_provided', 'security_assurance_available',
        'encryption_confirmed', 'access_controls_mfa_confirmed',
    ):
        if facts.get(key) not in {'yes', 'no', 'not_sure'}:
            errors[key] = 'Choose Yes, No, or Not sure.'
    for key in ('privacy_contact_name', 'privacy_contact_role', 'privacy_contact_email'):
        if not facts.get(key):
            errors[key] = 'This contact detail is required.'
    if facts.get('breach_notification_commitment') not in {value for value, _ in DPA_BREACH_COMMITMENTS}:
        errors['breach_notification_commitment'] = 'Choose a controlled breach-notification commitment.'
    elif facts.get('breach_notification_commitment') == 'other' and not facts.get('breach_other_period'):
        errors['breach_other_period'] = 'Describe the proposed period so Legal can review it.'

    selected_msa = _step4_selected_msa(facts, related_msas)
    if facts.get('related_msa_id') and not selected_msa:
        errors['related_msa_id'] = 'Select a related MSA from this workspace.'
    if facts.get('governing_law_mode') == 'inherit':
        if not selected_msa:
            errors['governing_law_mode'] = 'Select a related MSA before inheriting its governing law.'
    elif facts.get('governing_law') not in DPA_GOVERNING_LAWS:
        errors['governing_law'] = 'Select a governing law from the approved list.'

    for key, label in _DPA_POSITION_KEYS:
        position = facts.get('positions', {}).get(key, {})
        if position.get('status') not in {value for value, _ in DPA_POSITION_CHOICES}:
            errors[f'{key}_position'] = f'Choose a status for {label.lower()}'
        elif position['status'] == 'deviation' and not (
            position.get('wording') or facts.get('evidence', {}).get(f'{key}_document')
        ):
            errors[f'{key}_wording'] = 'Paste proposed wording or upload the proposed language.'
    return errors


def _step4_outcomes(facts, related_msas):
    outcomes = [('Privacy review required', 'A DPA always receives Privacy review.')]
    needs_legal = False
    if any(facts.get(key) in {'no', 'not_sure'} for key in (
        'security_measures_provided', 'security_assurance_available',
        'encryption_confirmed', 'access_controls_mfa_confirmed',
    )):
        outcomes.append(('Security evidence missing', 'One or more security assurances are unavailable or not confirmed.'))
        needs_legal = True
    if facts.get('breach_notification_commitment') not in {'approved_standard', ''}:
        outcomes.append(('Breach-notification term deviates from playbook', 'The proposed commitment requires review.'))
        needs_legal = True
    selected_msa = _step4_selected_msa(facts, related_msas)
    if selected_msa and facts.get('governing_law_mode') == 'inherit':
        outcomes.append(('Governing law matches related MSA', selected_msa['governing_law']))
    elif facts.get('governing_law'):
        needs_legal = True
    positions = facts.get('positions', {})
    if positions and all(position.get('status') == 'accepted' for position in positions.values()):
        outcomes.append(('Standard positions accepted', 'Audit, deletion/return, and liability positions match the playbook.'))
    if any(position.get('status') in {'deviation', 'not_confirmed'} for position in positions.values()):
        needs_legal = True
    if needs_legal:
        outcomes.append(('Legal review required', 'A security, breach, governing-law, or standard-position exception was recorded.'))
    return outcomes


def _step3_facts_from_post(post_data, previous=None):
    """Read operational Step 3 facts without adding a fragile DPA schema."""
    facts = dict(previous or {})
    facts['data_categories'] = post_data.getlist('step3_data_categories')
    facts['data_subjects'] = post_data.getlist('step3_data_subjects')
    facts['sensitive_data'] = post_data.get('step3_sensitive_data', '')
    facts['subprocessors_answer'] = post_data.get('step3_subprocessors', '')
    facts['processing_countries'] = post_data.getlist('step3_processing_countries')
    facts['transfer_safeguard'] = post_data.get('step3_transfer_safeguard', '')

    rows = []
    names = post_data.getlist('step3_subprocessor_name')
    services = post_data.getlist('step3_subprocessor_service')
    locations = post_data.getlist('step3_subprocessor_location')
    data_involved = post_data.getlist('step3_subprocessor_data')
    for index, name in enumerate(names):
        row = {
            'name': (name or '').strip(),
            'service': (services[index] if index < len(services) else '').strip(),
            'location': (locations[index] if index < len(locations) else '').strip(),
            'data': (data_involved[index] if index < len(data_involved) else '').strip(),
        }
        if any(row.values()):
            rows.append(row)
    facts['subprocessors'] = rows if facts['subprocessors_answer'] == 'yes' else []
    return facts


def _step3_has_non_eea_country(facts):
    return any(country not in _EEA_COUNTRIES for country in facts.get('processing_countries', []))


def _apply_step3_facts(values, facts):
    """Map plain-language intake facts onto the established DPA workflow keys."""
    values = dict(values)
    values['personal_data_categories'] = ', '.join(facts.get('data_categories', []))
    values['data_subjects'] = ', '.join(facts.get('data_subjects', []))
    values['personal_data_involved'] = True  # A DPA always concerns personal data.
    values['special_categories_data'] = facts.get('sensitive_data') == 'yes'
    values['subprocessors_used'] = facts.get('subprocessors_answer') == 'yes'
    values['cross_border_transfer'] = _step3_has_non_eea_country(facts)
    values['transfer_mechanism'] = _TRANSFER_MECHANISM_MAP.get(facts.get('transfer_safeguard'), 'None')
    values['include_scc_fallback'] = facts.get('transfer_safeguard') == 'Standard Contractual Clauses'
    values['_dpa_step3'] = facts
    return values


def _validate_step3_facts(facts):
    errors = {}
    if not facts.get('data_categories'):
        errors['step3_data_categories'] = 'Select at least one data category.'
    if not facts.get('data_subjects'):
        errors['step3_data_subjects'] = 'Select at least one data subject group.'
    if facts.get('sensitive_data') not in ('yes', 'no', 'not_sure'):
        errors['step3_sensitive_data'] = 'Choose Yes, No, or Not sure.'
    if facts.get('subprocessors_answer') not in ('yes', 'no', 'not_sure'):
        errors['step3_subprocessors'] = 'Choose Yes, No, or Not sure.'
    if not facts.get('processing_countries'):
        errors['step3_processing_countries'] = 'Select at least one processing location.'
    if facts.get('subprocessors_answer') == 'yes':
        subprocessors = facts.get('subprocessors', [])
        if not subprocessors:
            errors['step3_subprocessor_list'] = 'Add at least one subprocessor, including its name, service, location, and data involved.'
        elif any(not all(row.values()) for row in subprocessors):
            errors['step3_subprocessor_list'] = 'Complete the name, service, processing location, and data involved for every subprocessor.'
    if _step3_has_non_eea_country(facts):
        safeguard = facts.get('transfer_safeguard')
        if not safeguard:
            errors['step3_transfer_safeguard'] = 'Confirm the transfer safeguard before continuing.'
        elif safeguard == 'Not confirmed':
            errors['step3_transfer_safeguard'] = 'A confirmed safeguard is required before this DPA can progress.'
    return errors


def _step3_outcomes(facts):
    outcomes = []
    if facts.get('sensitive_data') == 'yes':
        outcomes.append(('DPO approval required', 'Sensitive or criminal-offence data requires elevated privacy review.'))
    elif facts.get('sensitive_data') == 'not_sure':
        outcomes.append(('Privacy review required', 'Sensitive-data scope is not yet confirmed.'))
    if facts.get('subprocessors_answer') == 'yes':
        outcomes.append(('Subprocessor review required', 'The disclosed subprocessor list will be reviewed.'))
    elif facts.get('subprocessors_answer') == 'not_sure':
        outcomes.append(('Privacy review required', 'Subprocessor involvement is not yet confirmed.'))
    if _step3_has_non_eea_country(facts):
        safeguard = facts.get('transfer_safeguard')
        outcomes.append(('International transfer identified', 'A non-EEA processing location was selected.'))
        if safeguard == 'Standard Contractual Clauses':
            outcomes.extend((
                ('SCC review required', 'Approved SCC language will be included automatically.'),
                ('DPO approval required', 'SCC processing requires DPO review before signature.'),
            ))
        elif safeguard == 'Not confirmed':
            outcomes.append(('Transfer safeguard unresolved', 'Generation is blocked until a safeguard is confirmed.'))
        elif safeguard:
            outcomes.append(('Transfer clause selected', f'{safeguard} will be reflected in the governed draft.'))
    elif facts.get('processing_countries'):
        outcomes.append(('No transfer review required', 'All selected processing locations are within the EEA.'))
    return outcomes


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


def _validate_dpa_values(values, fields):
    errors = {}
    for field in fields:
        value = values.get(field.key)
        if field.is_required and field.field_type != FieldDefinition.FieldType.BOOLEAN and not _field_has_value(field, value):
            errors[field.key] = f'{field.label} is required.'
    return errors


def _dpa_governance_results(values):
    """Return review findings derived solely from captured DPA answers.

    These mirror the persisted risk rules that run during generation, without
    creating pre-generation risk records or presenting speculative results.
    """
    results = []

    def add(title, status, trigger, rule, approval, tone='attention'):
        results.append({
            'title': title, 'status': status, 'trigger': trigger,
            'rule': rule, 'approval': approval, 'tone': tone,
        })

    facts = values.get('_dpa_step3', {})
    add('Privacy and Legal review required', 'Required', 'A DPA governs personal-data processing.',
        'DPA baseline review rule', 'Privacy and Legal review')
    if values.get('cross_border_transfer'):
        mechanism = values.get('transfer_mechanism')
        if mechanism == 'SCC':
            add('SCC review required', 'Required', 'A non-EEA location uses Standard Contractual Clauses.',
                'International transfer rule', 'DPO approval before signature')
        elif mechanism in ('', 'None', None):
            add('Transfer safeguard unresolved', 'Blocked', 'A non-EEA location has no confirmed safeguard.',
                'International transfer rule', 'Privacy and DPO review')
        else:
            add('International transfer identified', 'Required', f'{mechanism} was selected for a non-EEA location.',
                'International transfer rule', 'Privacy review')
    if values.get('subprocessors_used'):
        add('Subprocessor review required', 'Required', 'Subprocessors involved was selected.',
            'Subprocessor flow-down rule', 'Legal review')
    if values.get('special_categories_data'):
        add('Elevated privacy review required', 'Required', 'Special-category data was selected.',
            'Special-category safeguard rule', 'Privacy, Legal, and DPO review')
    if facts.get('sensitive_data') == 'not_sure' or facts.get('subprocessors_answer') == 'not_sure':
        add('Privacy review required', 'Blocked', 'An operational privacy fact was marked Not sure.',
            'Uncertain-answer review rule', 'Privacy and DPO review before approval or signature')
    if values.get('liability_position'):
        add('Non-standard position detected', 'Review', 'A fallback liability position was entered.',
            'Non-standard clause review rule', 'Legal review')
    step4 = values.get('_dpa_step4', {})
    if step4:
        related_msas = []
        related_msa_id = values.get('related_msa_id')
        if related_msa_id:
            related_msas = [{'id': related_msa_id, 'governing_law': values.get('governing_law', '')}]
        for title, detail in _step4_outcomes(step4, related_msas):
            if title == 'Privacy review required':
                continue  # The baseline rule above already records this.
            add(
                title,
                'Required' if 'required' in title.lower() else 'Review',
                detail,
                'Step 4 operational evidence rule',
                'Legal review' if title in {'Legal review required', 'Security evidence missing'} else 'Privacy review',
                tone='attention',
            )
    if not results:
        add('No exception detected', 'Clear', 'No conditional review trigger was selected.',
            'Approved DPA baseline', 'Standard workflow route', tone='clear')
    return results


class DPAWorkflowBuilderView(LoginRequiredMixin, View):
    template_name = 'contracts/dpa_workflow_builder.html'

    def _load_intake(self, request):
        intake = request.session.get(_DPA_INTAKE_SESSION_KEY, {})
        organization = get_user_organization(request.user)
        if intake.get('organization_id') != getattr(organization, 'pk', None):
            return {}, 1
        return intake.get('values', {}), intake.get('step', 1)

    def _save_intake(self, request, values, step):
        organization = get_user_organization(request.user)
        request.session[_DPA_INTAKE_SESSION_KEY] = {
            'organization_id': getattr(organization, 'pk', None),
            'values': values,
            'step': step,
        }
        request.session.modified = True

    @staticmethod
    def _merge_posted_values(post_data, values, fields):
        merged = dict(values)
        for field in fields:
            input_name = f'field_{field.id}'
            if field.field_type == FieldDefinition.FieldType.BOOLEAN:
                # A rendered checkbox answers the question even when unchecked.
                merged[field.key] = input_name in post_data
            elif input_name in post_data:
                value = _coerce_field_value(field, post_data.get(input_name))
                # Django's JSON session serializer cannot store date objects.
                merged[field.key] = value.isoformat() if hasattr(value, 'isoformat') else value
        return merged

    def _steps(self, workflow_template, values, errors, active_step):
        fields = list(FieldDefinition.objects.filter(workflow_template=workflow_template).order_by('section', 'order'))
        by_key = {field.key: field for field in fields}
        assigned = set()
        steps = []
        for number, config in enumerate(DPA_INTAKE_STEPS, start=1):
            step_fields = [by_key[key] for key in config['keys'] if key in by_key]
            assigned.update(field.key for field in step_fields)
            assigned.update(config.get('hidden_keys', ()))
            required = [field for field in step_fields if field.is_required and field.field_type != FieldDefinition.FieldType.BOOLEAN]
            completed = sum(1 for field in required if _field_has_value(field, values.get(field.key)))
            steps.append({
                **config, 'number': number, 'fields': step_fields,
                'required_count': len(required), 'completed_count': completed,
                'is_active': number == active_step,
                'has_errors': any(field.key in errors for field in step_fields),
            })
        # Preserve any newly configured DPA field without silently dropping it.
        extras = [field for field in fields if field.key not in assigned]
        if extras:
            steps[-1]['fields'].extend(extras)
        return steps, fields

    def _context(self, request, *, errors=None, posted=None, active_step=None):
        workflow_template = get_dpa_workflow_template()
        saved_values, saved_step = self._load_intake(request)
        posted_values = posted if posted is not None else saved_values
        errors = errors or {}
        active_step = max(1, min(active_step or saved_step, len(DPA_INTAKE_STEPS)))
        steps, fields = self._steps(workflow_template, posted_values, errors, active_step)
        required = [field for field in fields if field.is_required and field.field_type != FieldDefinition.FieldType.BOOLEAN]
        completed = sum(1 for field in required if _field_has_value(field, posted_values.get(field.key)))
        step3_facts = posted_values.get('_dpa_step3', {})
        step4_facts = posted_values.get('_dpa_step4', {})
        related_msas = _related_msas(get_user_organization(request.user))
        saved_rows = list(step3_facts.get('subprocessors', []))
        subprocessor_rows = saved_rows or [{}]
        return {
            'workflow_template': workflow_template,
            'steps': steps,
            'active_step': active_step,
            'total_required_fields': len(required),
            'completed_required_fields': completed,
            'missing_required_fields': len(required) - completed,
            'completion_percent': round((completed / len(required)) * 100) if required else 100,
            'errors': errors,
            'posted': posted_values,
            'step3_facts': step3_facts,
            'step3_outcomes': _step3_outcomes(step3_facts),
            'step3_has_non_eea': _step3_has_non_eea_country(step3_facts),
            'step3_subprocessor_rows': subprocessor_rows,
            'step4_facts': step4_facts,
            'step4_outcomes': _step4_outcomes(step4_facts, related_msas),
            'related_msas': related_msas,
            'governing_law_options': DPA_GOVERNING_LAWS,
            'breach_commitments': DPA_BREACH_COMMITMENTS,
            'position_choices': DPA_POSITION_CHOICES,
            'position_fields': _DPA_POSITION_KEYS,
            'security_assurance_fields': (
                ('security_measures_provided', 'Have technical and organisational measures been provided?'),
                ('security_assurance_available', 'Security certification or assurance available?'),
                ('encryption_confirmed', 'Encryption in transit and at rest confirmed?'),
                ('access_controls_mfa_confirmed', 'Access controls and MFA confirmed?'),
            ),
            'data_category_options': DPA_DATA_CATEGORIES,
            'data_subject_options': DPA_DATA_SUBJECTS,
            'country_options': DPA_COUNTRIES,
            'transfer_safeguards': DPA_TRANSFER_SAFEGUARDS,
            'yes_no_not_sure_choices': (('yes', 'Yes'), ('no', 'No'), ('not_sure', 'Not sure')),
        }

    def get(self, request):
        requested_step = request.GET.get('step')
        try:
            requested_step = int(requested_step) if requested_step else None
        except (TypeError, ValueError):
            requested_step = None
        return render(request, self.template_name, self._context(request, active_step=requested_step))

    def post(self, request):
        organization = get_user_organization(request.user)
        workflow_template = get_dpa_workflow_template()
        action = request.POST.get('action', 'generate')
        saved_values, saved_step = self._load_intake(request)

        # Preserve direct generation for API and existing callers that submit
        # the complete field set without moving through the UI wizard.
        if action == 'generate':
            cleaned_values, errors = _validate_dpa_submission(request.POST, workflow_template)
        else:
            active_step = max(1, min(int(request.POST.get('step', saved_step) or 1), len(DPA_INTAKE_STEPS)))
            steps, _fields = self._steps(workflow_template, saved_values, {}, active_step)
            current_fields = steps[active_step - 1]['fields']
            if active_step == 3:
                facts = _step3_facts_from_post(request.POST, saved_values.get('_dpa_step3'))
                cleaned_values = _apply_step3_facts(saved_values, facts)
                errors = _validate_step3_facts(facts) if action == 'continue' else {}
            elif active_step == 4:
                related_msas = _related_msas(organization)
                facts = _step4_facts_from_post(
                    request.POST, request.FILES, saved_values.get('_dpa_step4'), organization,
                )
                cleaned_values = _apply_step4_facts(saved_values, facts, related_msas)
                errors = _validate_step4_facts(facts, related_msas) if action == 'continue' else {}
            else:
                cleaned_values = self._merge_posted_values(request.POST, saved_values, current_fields)
                errors = _validate_dpa_values(cleaned_values, current_fields) if action == 'continue' else {}

            if action == 'previous':
                self._save_intake(request, cleaned_values, active_step - 1)
                return redirect(f"{reverse('contracts:dpa_workflow_builder')}?step={max(1, active_step - 1)}")
            if action == 'save_exit':
                self._save_intake(request, cleaned_values, active_step)
                messages.success(request, 'DPA intake saved. You can resume it from New Contract.')
                return redirect('contracts:contract_template_picker')
            if errors:
                return render(request, self.template_name, self._context(request, errors=errors, posted=cleaned_values, active_step=active_step))
            if active_step < len(DPA_INTAKE_STEPS):
                self._save_intake(request, cleaned_values, active_step + 1)
                return redirect(f"{reverse('contracts:dpa_workflow_builder')}?step={active_step + 1}")
            all_fields = list(FieldDefinition.objects.filter(workflow_template=workflow_template))
            errors = _validate_dpa_values(cleaned_values, all_fields)
            if errors:
                return render(request, self.template_name, self._context(request, errors=errors, posted=cleaned_values, active_step=active_step))
            self._save_intake(request, cleaned_values, active_step)
            return redirect('contracts:dpa_workflow_review')

        if errors:
            messages.error(request, 'Complete the required fields before generating the governed draft.')
            return render(request, self.template_name, self._context(request, errors=errors, posted=cleaned_values))

        workflow = create_dpa_workflow_instance(
            organization=organization, user=request.user, cleaned_values=cleaned_values, request=request,
        )
        messages.success(request, f'"{workflow.title}" generated — it now appears in the Command Center Priority Queue.')
        return redirect(reverse('contracts:workflow_detail', kwargs={'pk': workflow.pk}))


class DPAReviewAndGenerateView(DPAWorkflowBuilderView):
    template_name = 'contracts/dpa_review_and_generate.html'

    def _review_context(self, request, *, errors=None):
        workflow_template = get_dpa_workflow_template()
        values, _step = self._load_intake(request)
        fields = list(FieldDefinition.objects.filter(workflow_template=workflow_template).order_by('section', 'order'))
        summaries = []
        for field in fields:
            value = values.get(field.key)
            if field.field_type == FieldDefinition.FieldType.BOOLEAN:
                value = 'Yes' if value else 'No'
            summaries.append({'label': field.label, 'value': value or 'Not provided'})
        return {
            'values': values, 'summaries': summaries,
            'governance_results': _dpa_governance_results(values),
            'errors': errors or {},
        }

    def get(self, request):
        values, _step = self._load_intake(request)
        if not values:
            messages.info(request, 'Start the DPA intake before reviewing it.')
            return redirect('contracts:dpa_workflow_builder')
        return render(request, self.template_name, self._review_context(request))

    def post(self, request):
        action = request.POST.get('action')
        if action == 'edit':
            return redirect('contracts:dpa_workflow_builder')
        if action == 'save_draft':
            messages.success(request, 'DPA intake saved.')
            return redirect('contracts:dpa_workflow_review')

        workflow_template = get_dpa_workflow_template()
        values, _step = self._load_intake(request)
        fields = list(FieldDefinition.objects.filter(workflow_template=workflow_template))
        errors = _validate_dpa_values(values, fields)
        if errors:
            return redirect('contracts:dpa_workflow_builder')
        cleaned_values = dict(values)
        for field in fields:
            if field.field_type == FieldDefinition.FieldType.DATE and isinstance(cleaned_values.get(field.key), str):
                cleaned_values[field.key] = parse_date(cleaned_values[field.key])
        workflow = create_dpa_workflow_instance(
            organization=get_user_organization(request.user), user=request.user,
            cleaned_values=cleaned_values, request=request,
        )
        request.session.pop(_DPA_INTAKE_SESSION_KEY, None)
        messages.success(request, f'“{workflow.title}” generated and ready for review.')
        return redirect('contracts:workflow_detail', pk=workflow.pk)


def dpa_submit_for_review(request, pk, approval_step):
    from contracts.views_domains.drafting_workspace_actions import drafting_submit_for_review

    return drafting_submit_for_review(request, pk, approval_step, kind='dpa')


def dpa_exception_action(request, pk, signal_id):
    from contracts.views_domains.drafting_workspace_actions import drafting_exception_action

    return drafting_exception_action(request, pk, signal_id, kind='dpa')


def dpa_confirm_section(request, pk, section_id):
    from contracts.views_domains.drafting_workspace_actions import drafting_confirm_section

    return drafting_confirm_section(request, pk, section_id, kind='dpa')
