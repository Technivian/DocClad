from django.db import migrations


WORKFLOW_TEMPLATE_NAME = 'MSA Commercial Review Workflow'
MSA_TEMPLATE_NAME = 'Standard Master Service Agreement'


PAYROLLMINDS_MSA_FIELDS = [
    {
        'key': 'payrollminds_contracting_entity',
        'label': 'Payrollminds contracting entity',
        'section': 'BASIC_DETAILS',
        'field_type': 'SELECT',
        'is_required': True,
        'order': 0,
        'options': ['Payrollminds B.V.', 'Payrollminds Group B.V.'],
    },
    {
        'key': 'client_contact_name',
        'label': 'Client contact name',
        'section': 'BASIC_DETAILS',
        'field_type': 'TEXT',
        'is_required': True,
        'order': 6,
    },
    {
        'key': 'client_contact_email',
        'label': 'Client contact email',
        'section': 'BASIC_DETAILS',
        'field_type': 'TEXT',
        'is_required': True,
        'order': 7,
    },
    {
        'key': 'end_date',
        'label': 'End date',
        'section': 'COMMERCIAL_TERMS',
        'field_type': 'DATE',
        'is_required': False,
        'order': 7,
        'maps_to_contract_field': 'end_date',
    },
    {
        'key': 'consultant_service_type',
        'label': 'Consultant or service type',
        'section': 'SERVICES_SCOPE',
        'field_type': 'TEXT',
        'is_required': True,
        'order': 0,
    },
    {
        'key': 'rate',
        'label': 'Rate',
        'section': 'COMMERCIAL_TERMS',
        'field_type': 'NUMBER',
        'is_required': False,
        'order': 8,
    },
    {
        'key': 'travel_km_rate',
        'label': 'Travel or kilometre rate',
        'section': 'COMMERCIAL_TERMS',
        'field_type': 'NUMBER',
        'is_required': False,
        'order': 9,
    },
    {
        'key': 'administrative_fee',
        'label': 'Administrative fee',
        'section': 'COMMERCIAL_TERMS',
        'field_type': 'NUMBER',
        'is_required': False,
        'order': 10,
    },
    {
        'key': 'client_paper',
        'label': 'Client paper instead of Payrollminds paper?',
        'section': 'SMART_QUESTIONS',
        'field_type': 'BOOLEAN',
        'is_required': False,
        'order': 7,
        'help_text': 'Triggers Legal review because third-party paper may change fallback positions.',
    },
    {
        'key': 'worker_classification',
        'label': 'Employee or independent contractor',
        'section': 'SERVICES_SCOPE',
        'field_type': 'SELECT',
        'is_required': False,
        'order': 5,
        'options': ['Employee', 'Independent contractor', 'Not applicable'],
    },
    {
        'key': 'payrollminds_professional_involved',
        'label': 'Payrollminds Professional involved?',
        'section': 'SERVICES_SCOPE',
        'field_type': 'BOOLEAN',
        'is_required': False,
        'order': 6,
    },
    {
        'key': 'special_conditions',
        'label': 'Additional comments or special conditions',
        'section': 'LEGAL_POSITION',
        'field_type': 'TEXTAREA',
        'is_required': False,
        'order': 7,
    },
]


PAYROLLMINDS_TEMPLATE_BODY = (
    'MASTER SERVICES AGREEMENT\n\n'
    'This Master Services Agreement is entered into between {{payrollminds_contracting_entity}} and {{counterparty}} '
    'as of {{effective_date}}. Client contact: {{client_contact_name}} ({{client_contact_email}}).\n\n'
    '1. Services\n'
    'Payrollminds shall provide {{consultant_service_type}} services described in {{services_description}} and any applicable Statement of Work. '
    'Worker classification: {{worker_classification}}. Payrollminds Professional involved: {{payrollminds_professional_involved}}.\n\n'
    '2. Fees and Payment\n'
    'The total contract value is {{value}} {{currency}}. Rate: {{rate}}. Payment terms are {{payment_terms}}. '
    'Travel or kilometre rate: {{travel_km_rate}}. Administrative fee: {{administrative_fee}}.\n\n'
    '3. Term and Renewal\n'
    'This Agreement starts on {{effective_date}} and continues for {{initial_term}}. End date: {{end_date}}. '
    'Renewal type: {{renewal_type}}. Termination notice period: {{termination_notice_period}} days.\n\n'
    '4. Liability\n'
    "Supplier's liability is capped at {{liability_cap}}, except for excluded claims.\n\n"
    '5. Intellectual Property\n'
    'IP ownership position: {{ip_ownership}}.\n\n'
    '6. Data Protection\n'
    '{{data_protection_clause}}\n\n'
    '7. Governing Law\n'
    'This Agreement is governed by the laws of {{governing_law}}. Jurisdiction: {{jurisdiction}}.\n\n'
    '8. Special Conditions\n'
    '{{special_conditions}}'
)


def apply_payrollminds_msa_fields(apps, schema_editor):
    WorkflowTemplate = apps.get_model('contracts', 'WorkflowTemplate')
    FieldDefinition = apps.get_model('contracts', 'FieldDefinition')
    ContractTemplate = apps.get_model('contracts', 'ContractTemplate')

    workflow_template = WorkflowTemplate.objects.filter(name=WORKFLOW_TEMPLATE_NAME).first()
    if workflow_template:
        for field in PAYROLLMINDS_MSA_FIELDS:
            FieldDefinition.objects.update_or_create(
                workflow_template=workflow_template,
                key=field['key'],
                defaults=field,
            )

    ContractTemplate.objects.filter(name=MSA_TEMPLATE_NAME, contract_type='MSA').update(
        body=PAYROLLMINDS_TEMPLATE_BODY,
        description='Payrollminds-ready MSA framework with governed commercial controls.',
    )


def unapply_payrollminds_msa_fields(apps, schema_editor):
    WorkflowTemplate = apps.get_model('contracts', 'WorkflowTemplate')
    FieldDefinition = apps.get_model('contracts', 'FieldDefinition')
    workflow_template = WorkflowTemplate.objects.filter(name=WORKFLOW_TEMPLATE_NAME).first()
    if workflow_template:
        FieldDefinition.objects.filter(
            workflow_template=workflow_template,
            key__in=[field['key'] for field in PAYROLLMINDS_MSA_FIELDS],
        ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0081_rebrand_clm_one'),
    ]

    operations = [
        migrations.RunPython(apply_payrollminds_msa_fields, unapply_payrollminds_msa_fields),
    ]
