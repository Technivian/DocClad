# Generated manually for the "New DPA Draft" cockpit polish pass.
#
# Consolidates the yes/no privacy-routing toggles (previously split across
# PRIVACY_DETAILS and PRIVACY_QUESTIONS) into a single PRIVACY_QUESTIONS
# "AI Smart Questions" section, adds the two missing toggles (special
# categories of data, SCC fallback language), and rewrites help_text into
# short "why it matters" copy shown under each question in the cockpit UI.

from django.db import migrations

WORKFLOW_TEMPLATE_NAME = 'DPA Privacy Review Workflow'

DPA_FIELDS = [
    {'key': 'personal_data_involved', 'label': 'Will the counterparty process personal data?',
     'section': 'PRIVACY_QUESTIONS', 'field_type': 'BOOLEAN', 'is_required': True, 'order': 1,
     'maps_to_contract_field': '', 'help_text': 'Required for GDPR routing and DPO approval.', 'options': []},
    {'key': 'cross_border_transfer', 'label': 'Will data leave the EEA?',
     'section': 'PRIVACY_QUESTIONS', 'field_type': 'BOOLEAN', 'is_required': True, 'order': 2,
     'maps_to_contract_field': 'data_transfer_flag', 'help_text': 'Triggers SCC review and international transfer language.', 'options': []},
    {'key': 'subprocessors_used', 'label': 'Are subprocessors involved?',
     'section': 'PRIVACY_QUESTIONS', 'field_type': 'BOOLEAN', 'is_required': True, 'order': 3,
     'maps_to_contract_field': '', 'help_text': 'Adds subprocessor review and approval checks.', 'options': []},
    {'key': 'special_categories_data', 'label': 'Are special categories of personal data processed?',
     'section': 'PRIVACY_QUESTIONS', 'field_type': 'BOOLEAN', 'is_required': False, 'order': 4,
     'maps_to_contract_field': '', 'help_text': 'Elevates privacy risk — triggers Legal and DPO review.', 'options': []},
    {'key': 'include_scc_fallback', 'label': 'Should SCC fallback language be included?',
     'section': 'PRIVACY_QUESTIONS', 'field_type': 'BOOLEAN', 'is_required': False, 'order': 5,
     'maps_to_contract_field': '', 'help_text': 'Adds the approved SCC fallback clause to the draft for DPO sign-off.', 'options': []},
    {'key': 'transfer_mechanism', 'label': 'Cross-border transfer mechanism', 'section': 'PRIVACY_QUESTIONS',
     'field_type': 'SELECT', 'is_required': True, 'order': 6, 'maps_to_contract_field': '',
     'help_text': '', 'options': ['SCC', 'BCR', 'Adequacy Decision', 'None']},
    {'key': 'breach_notification_hours', 'label': 'Breach notification window (hours)', 'section': 'PRIVACY_QUESTIONS',
     'field_type': 'NUMBER', 'is_required': True, 'order': 7, 'maps_to_contract_field': '',
     'help_text': 'Hours to notify the Controller after becoming aware of a breach.', 'options': []},
    {'key': 'dpo_contact', 'label': 'Data Protection Officer contact', 'section': 'PRIVACY_QUESTIONS',
     'field_type': 'TEXT', 'is_required': False, 'order': 8, 'maps_to_contract_field': '',
     'help_text': 'Name/email of the Data Protection Officer or privacy contact.', 'options': []},
]


def apply_dpa_smart_questions_expansion(apps, schema_editor):
    WorkflowTemplate = apps.get_model('contracts', 'WorkflowTemplate')
    FieldDefinition = apps.get_model('contracts', 'FieldDefinition')

    workflow_template = WorkflowTemplate.objects.filter(name=WORKFLOW_TEMPLATE_NAME).first()
    if not workflow_template:
        return
    for field in DPA_FIELDS:
        FieldDefinition.objects.update_or_create(
            workflow_template=workflow_template,
            key=field['key'],
            defaults=field,
        )


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0073_update_dpa_governed_drafting_fields'),
    ]

    operations = [
        migrations.RunPython(apply_dpa_smart_questions_expansion, reverse_noop),
    ]
