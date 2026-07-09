# Generated manually for the workflow-first New Contract DPA cockpit.

from django.db import migrations, models


WORKFLOW_TEMPLATE_NAME = 'DPA Privacy Review Workflow'
DPA_TEMPLATE_NAME = 'Standard Data Processing Agreement'

DPA_FIELDS = [
    {'key': 'counterparty', 'label': 'Counterparty name', 'section': 'BASIC_DETAILS', 'field_type': 'TEXT',
     'is_required': True, 'order': 1, 'maps_to_contract_field': 'counterparty', 'help_text': '', 'options': []},
    {'key': 'start_date', 'label': 'Effective date', 'section': 'BASIC_DETAILS', 'field_type': 'DATE',
     'is_required': True, 'order': 2, 'maps_to_contract_field': 'start_date', 'help_text': '', 'options': []},
    {'key': 'contract_owner', 'label': 'Contract owner', 'section': 'BASIC_DETAILS', 'field_type': 'TEXT',
     'is_required': True, 'order': 3, 'maps_to_contract_field': '', 'help_text': '', 'options': []},
    {'key': 'processing_purpose', 'label': 'Processing purpose', 'section': 'PRIVACY_DETAILS', 'field_type': 'TEXTAREA',
     'is_required': True, 'order': 1, 'maps_to_contract_field': '', 'help_text': '', 'options': []},
    {'key': 'personal_data_categories', 'label': 'Personal data categories', 'section': 'PRIVACY_DETAILS', 'field_type': 'TEXTAREA',
     'is_required': True, 'order': 2, 'maps_to_contract_field': '', 'help_text': '', 'options': []},
    {'key': 'data_subjects', 'label': 'Data subjects', 'section': 'PRIVACY_DETAILS', 'field_type': 'TEXT',
     'is_required': True, 'order': 3, 'maps_to_contract_field': '', 'help_text': '', 'options': []},
    {'key': 'subprocessors_used', 'label': 'Subprocessors involved', 'section': 'PRIVACY_DETAILS', 'field_type': 'BOOLEAN',
     'is_required': True, 'order': 4, 'maps_to_contract_field': '', 'help_text': 'Yes triggers subprocessor review.', 'options': []},
    {'key': 'cross_border_transfer', 'label': 'Data leaves EEA', 'section': 'PRIVACY_DETAILS', 'field_type': 'BOOLEAN',
     'is_required': True, 'order': 5, 'maps_to_contract_field': 'data_transfer_flag', 'help_text': 'Yes triggers SCC risk and DPO approval.', 'options': []},
    {'key': 'governing_law', 'label': 'Governing law', 'section': 'LEGAL_POSITION', 'field_type': 'TEXT',
     'is_required': True, 'order': 1, 'maps_to_contract_field': 'governing_law', 'help_text': '', 'options': []},
    {'key': 'liability_position', 'label': 'Fallback liability position', 'section': 'LEGAL_POSITION', 'field_type': 'TEXTAREA',
     'is_required': False, 'order': 2, 'maps_to_contract_field': '', 'help_text': 'Fallback liability language, if any deviation from standard position.', 'options': []},
    {'key': 'personal_data_involved', 'label': 'Is personal data involved?', 'section': 'PRIVACY_QUESTIONS', 'field_type': 'BOOLEAN',
     'is_required': True, 'order': 1, 'maps_to_contract_field': '', 'help_text': 'Yes triggers DPA review and Legal review.', 'options': []},
    {'key': 'transfer_mechanism', 'label': 'Cross-border transfer mechanism', 'section': 'PRIVACY_QUESTIONS', 'field_type': 'SELECT',
     'is_required': True, 'order': 2, 'maps_to_contract_field': '', 'help_text': '', 'options': ['SCC', 'BCR', 'Adequacy Decision', 'None']},
    {'key': 'breach_notification_hours', 'label': 'Breach notification window (hours)', 'section': 'PRIVACY_QUESTIONS', 'field_type': 'NUMBER',
     'is_required': True, 'order': 3, 'maps_to_contract_field': '', 'help_text': 'Hours to notify the Controller after becoming aware of a breach.', 'options': []},
    {'key': 'dpo_contact', 'label': 'Data Protection Officer contact', 'section': 'PRIVACY_QUESTIONS', 'field_type': 'TEXT',
     'is_required': False, 'order': 4, 'maps_to_contract_field': '', 'help_text': 'Name/email of the Data Protection Officer or privacy contact.', 'options': []},
]

DPA_TEMPLATE_BODY = (
    'DATA PROCESSING AGREEMENT\n\n'
    'This Data Processing Agreement ("DPA") is entered into between DocClad B.V. '
    '("Controller") and {{counterparty}} ("Processor"), effective {{effective_date}}.\n\n'
    '1. Subject Matter. Processor will process personal data solely on behalf of Controller and only '
    'for the following purposes: {{processing_purpose}}.\n\n'
    '2. Categories of Data. The personal data categories are {{personal_data_categories}}. '
    'The affected data subjects are {{data_subjects}}.\n\n'
    '3. Security. Processor will implement appropriate technical and organizational measures to '
    'protect personal data against unauthorized or unlawful processing and against accidental loss, '
    'destruction, or damage.\n\n'
    "4. Sub-processors. Subprocessor position: {{subprocessor_position}}. Processor will not engage a "
    "sub-processor without Controller's prior written authorization.\n\n"
    '5. International Transfers. Data transfer position: {{data_transfer_position}}. Where personal data '
    'is transferred outside the EEA, the parties will rely on {{transfer_mechanism}} as the transfer mechanism.\n\n'
    '6. Breach Notification. Processor will notify Controller without undue delay, and in any event '
    'within {{breach_notification_hours}} hours, after becoming aware of a personal data breach.\n\n'
    "7. Data Protection Officer. Processor's data protection contact for matters arising under this DPA is {{dpo_contact}}.\n\n"
    '8. Governing Law. This DPA is governed by the laws of {{governing_law}}.'
)


def apply_dpa_cockpit_fields(apps, schema_editor):
    WorkflowTemplate = apps.get_model('contracts', 'WorkflowTemplate')
    FieldDefinition = apps.get_model('contracts', 'FieldDefinition')
    ContractTemplate = apps.get_model('contracts', 'ContractTemplate')
    ApprovalRoute = apps.get_model('contracts', 'ApprovalRoute')

    workflow_template = WorkflowTemplate.objects.filter(name=WORKFLOW_TEMPLATE_NAME).first()
    if workflow_template:
        FieldDefinition.objects.filter(workflow_template=workflow_template, key__in=['end_date', 'jurisdiction', 'value']).delete()
        FieldDefinition.objects.filter(workflow_template=workflow_template, section='COMMERCIAL_TERMS').update(section='PRIVACY_DETAILS')
        for field in DPA_FIELDS:
            FieldDefinition.objects.update_or_create(
                workflow_template=workflow_template,
                key=field['key'],
                defaults=field,
            )
        ApprovalRoute.objects.update_or_create(
            workflow_template=workflow_template,
            name='DPO',
            defaults={'order': 3, 'role_label': 'Data leaves the EEA', 'is_conditional': True, 'condition_note': 'EEA transfer selected'},
        )

    ContractTemplate.objects.filter(name=DPA_TEMPLATE_NAME, contract_type='DPA').update(
        description='GDPR Processor DPA · Netherlands · B2B',
        body=DPA_TEMPLATE_BODY,
        is_active=True,
    )


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0072_fieldvalue_json_encoder'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fielddefinition',
            name='section',
            field=models.CharField(
                choices=[
                    ('BASIC_DETAILS', 'Basic details'),
                    ('PRIVACY_DETAILS', 'Privacy details'),
                    ('LEGAL_POSITION', 'Legal position'),
                    ('PRIVACY_QUESTIONS', 'Smart privacy questions'),
                ],
                default='BASIC_DETAILS',
                max_length=20,
            ),
        ),
        migrations.RunPython(apply_dpa_cockpit_fields, reverse_noop),
    ]
