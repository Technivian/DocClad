from django.db import migrations, models

WORKFLOW_TEMPLATE_NAME = 'NDA Self-Serve Workflow'
NDA_TEMPLATE_NAME = 'Standard Mutual NDA'

WORKFLOW_STEPS = [
    {
        'order': 1, 'name': 'Draft', 'step_kind': 'TASK',
        'description': 'Complete the required NDA fields and self-serve routing questions.',
    },
    {
        'order': 2, 'name': 'Legal Review', 'step_kind': 'REVIEW',
        'description': 'Legal reviews non-standard confidentiality, privacy, residual knowledge, and governing law positions.',
        'condition_expression': 'risk=HIGH',
        'assignee_role': 'ASSOCIATE',
        'sla_hours': 24, 'escalation_after_hours': 48,
    },
    {
        'order': 3, 'name': 'Signature', 'step_kind': 'SIGNATURE',
        'description': 'Send the approved NDA for signature.',
        'sla_hours': 24,
    },
]

FIELD_DEFINITIONS = [
    {'key': 'counterparty', 'label': 'Counterparty name', 'section': 'BASIC_DETAILS', 'field_type': 'TEXT', 'is_required': True, 'order': 1, 'maps_to_contract_field': 'counterparty'},
    {'key': 'start_date', 'label': 'Effective date', 'section': 'BASIC_DETAILS', 'field_type': 'DATE', 'is_required': True, 'order': 2, 'maps_to_contract_field': 'start_date'},
    {'key': 'contract_owner', 'label': 'Contract owner', 'section': 'BASIC_DETAILS', 'field_type': 'TEXT', 'is_required': True, 'order': 3},
    {'key': 'business_unit', 'label': 'Business unit', 'section': 'BASIC_DETAILS', 'field_type': 'TEXT', 'is_required': True, 'order': 4},
    {'key': 'internal_reference', 'label': 'Internal reference', 'section': 'BASIC_DETAILS', 'field_type': 'TEXT', 'is_required': False, 'order': 5},
    {'key': 'nda_type', 'label': 'NDA type', 'section': 'NDA_TERMS', 'field_type': 'SELECT', 'is_required': True, 'order': 1, 'options': ['Mutual', 'One-way']},
    {'key': 'confidentiality_purpose', 'label': 'Confidentiality purpose', 'section': 'NDA_TERMS', 'field_type': 'TEXTAREA', 'is_required': True, 'order': 2},
    {'key': 'confidentiality_period', 'label': 'Confidentiality period (years)', 'section': 'NDA_TERMS', 'field_type': 'NUMBER', 'is_required': True, 'order': 3},
    {'key': 'disclosure_scope', 'label': 'Disclosure scope', 'section': 'NDA_TERMS', 'field_type': 'TEXTAREA', 'is_required': True, 'order': 4},
    {'key': 'permitted_recipients', 'label': 'Permitted recipients', 'section': 'NDA_TERMS', 'field_type': 'TEXT', 'is_required': True, 'order': 5},
    {'key': 'governing_law', 'label': 'Governing law', 'section': 'LEGAL_POSITION', 'field_type': 'TEXT', 'is_required': True, 'order': 1, 'maps_to_contract_field': 'governing_law'},
    {'key': 'jurisdiction', 'label': 'Jurisdiction', 'section': 'LEGAL_POSITION', 'field_type': 'TEXT', 'is_required': True, 'order': 2, 'maps_to_contract_field': 'jurisdiction'},
    {'key': 'residual_knowledge_included', 'label': 'Residual knowledge clause included?', 'section': 'LEGAL_POSITION', 'field_type': 'BOOLEAN', 'is_required': False, 'order': 3, 'help_text': 'Yes means the draft needs a governed fallback for residual knowledge language.'},
    {'key': 'injunctive_relief_included', 'label': 'Injunctive relief included?', 'section': 'LEGAL_POSITION', 'field_type': 'BOOLEAN', 'is_required': False, 'order': 4, 'help_text': 'Yes keeps the standard NDA enforcement position visible in the draft.'},
    {'key': 'personal_data_involved', 'label': 'Personal data involved?', 'section': 'LEGAL_POSITION', 'field_type': 'BOOLEAN', 'is_required': False, 'order': 5, 'help_text': 'Yes means privacy review and a linked DPA may be needed.'},
    {'key': 'confidentiality_period_nonstandard', 'label': 'Is the confidentiality period longer than the standard playbook position?', 'section': 'SMART_QUESTIONS', 'field_type': 'BOOLEAN', 'is_required': False, 'order': 1, 'help_text': 'Triggers Legal review when the term is non-standard.'},
    {'key': 'personal_data_confirmed', 'label': 'Does this NDA involve exchanging personal data?', 'section': 'SMART_QUESTIONS', 'field_type': 'BOOLEAN', 'is_required': False, 'order': 2, 'help_text': 'Confirms whether privacy review and a linked DPA should be suggested.'},
    {'key': 'residual_knowledge_nonstandard', 'label': 'Is the counterparty requesting non-standard residual knowledge language?', 'section': 'SMART_QUESTIONS', 'field_type': 'BOOLEAN', 'is_required': False, 'order': 3, 'help_text': 'Triggers Legal review for non-standard residual knowledge language.'},
    {'key': 'governing_law_nonpreferred', 'label': 'Is the governing law outside the preferred jurisdiction?', 'section': 'SMART_QUESTIONS', 'field_type': 'BOOLEAN', 'is_required': False, 'order': 4, 'help_text': 'Triggers Legal escalation when the jurisdiction is non-preferred.'},
]

APPROVAL_ROUTE = [
    {'order': 1, 'name': 'Contract Owner', 'role_label': 'Completes self-serve intake and business context', 'is_conditional': False},
    {'order': 2, 'name': 'Legal', 'role_label': 'Reviews non-standard NDA positions when triggered', 'is_conditional': True, 'condition_note': 'Only if NDA risk triggers appear'},
]

DEMO_CLAUSES = [
    {
        'title': 'NDA Residual Knowledge Fallback Clause',
        'content': (
            'Residual knowledge language is only allowed where the approved NDA playbook fallback preserves the '
            'confidentiality restrictions and excludes source materials from unrestricted reuse.'
        ),
        'fallback_content': 'Escalate any non-standard residual knowledge request to Legal before signature.',
    },
    {
        'title': 'NDA Privacy Linkage Clause',
        'content': (
            'Where personal data may be exchanged under an NDA, the parties must confirm whether a separate '
            'Data Processing Addendum is required before production use.'
        ),
        'fallback_content': 'Pause personal data exchange until privacy review confirms whether a DPA workflow is required.',
    },
    {
        'title': 'NDA Governing Law Escalation Clause',
        'content': (
            'Non-preferred governing law selections require legal confirmation before the NDA can move to signature.'
        ),
        'fallback_content': 'Default to the preferred Netherlands governing law position unless Legal approves otherwise.',
    },
]

NDA_TEMPLATE_BODY_ENRICHED = (
    'NON-DISCLOSURE AGREEMENT\n\n'
    'This Non-Disclosure Agreement is entered into between CLM One B.V. and {{counterparty}} as of {{effective_date}}.\n\n'
    '1. Purpose\n'
    'The parties wish to exchange confidential information for {{confidentiality_purpose}}.\n\n'
    '2. Confidential Information\n'
    'Confidential Information includes information disclosed in connection with {{disclosure_scope}}.\n\n'
    '3. Confidentiality Obligations\n'
    'Each party shall protect Confidential Information and use it only for the Purpose.\n\n'
    '4. Term\n'
    'The confidentiality obligations continue for {{confidentiality_period}} years.\n\n'
    '5. Permitted Recipients\n'
    'Confidential Information may be shared with {{permitted_recipients}}.\n\n'
    '6. Personal Data\n'
    '{{personal_data_clause}}\n\n'
    '7. Governing Law\n'
    'This Agreement is governed by the laws of {{governing_law}}. Jurisdiction: {{jurisdiction}}.\n\n'
    '8. Residual Knowledge\n'
    '{{residual_knowledge_clause}}\n\n'
    '9. Injunctive Relief\n'
    '{{injunctive_relief_clause}}'
)


def seed_nda_workflow(apps, schema_editor):
    ContractType = apps.get_model('contracts', 'ContractType')
    WorkflowTemplate = apps.get_model('contracts', 'WorkflowTemplate')
    WorkflowTemplateStep = apps.get_model('contracts', 'WorkflowTemplateStep')
    FieldDefinition = apps.get_model('contracts', 'FieldDefinition')
    ApprovalRoute = apps.get_model('contracts', 'ApprovalRoute')
    ContractTemplate = apps.get_model('contracts', 'ContractTemplate')
    ClauseTemplate = apps.get_model('contracts', 'ClauseTemplate')

    contract_type, _ = ContractType.objects.get_or_create(
        code='NDA',
        defaults={
            'name': 'Non-Disclosure Agreement',
            'description': 'Self-serve NDA workflow with governed fallback and conditional legal review.',
            'is_active': True,
        },
    )

    workflow_template, created = WorkflowTemplate.objects.get_or_create(
        name=WORKFLOW_TEMPLATE_NAME,
        contract_type=contract_type,
        defaults={
            'description': 'Lightweight self-serve NDA drafting with conditional legal review.',
            'organization': None,
            'category': 'CONTRACT_REVIEW',
            'version': 1,
            'is_active': True,
        },
    )
    if created:
        for step in WORKFLOW_STEPS:
            WorkflowTemplateStep.objects.create(template=workflow_template, **step)
        for field in FIELD_DEFINITIONS:
            FieldDefinition.objects.create(workflow_template=workflow_template, **field)
        for route_step in APPROVAL_ROUTE:
            ApprovalRoute.objects.create(workflow_template=workflow_template, **route_step)

    template, tmpl_created = ContractTemplate.objects.get_or_create(
        name=NDA_TEMPLATE_NAME,
        contract_type='NDA',
        defaults={
            'description': 'Mutual confidentiality agreement with self-serve routing and governed fallback positions.',
            'body': NDA_TEMPLATE_BODY_ENRICHED,
            'is_active': True,
        },
    )
    if not tmpl_created and 'confidentiality_purpose' not in template.body:
        template.body = NDA_TEMPLATE_BODY_ENRICHED
        template.save(update_fields=['body'])

    for clause in DEMO_CLAUSES:
        ClauseTemplate.objects.get_or_create(
            title=clause['title'],
            organization=None,
            defaults={
                'content': clause['content'],
                'fallback_content': clause['fallback_content'],
                'applicable_contract_types': 'NDA',
                'is_approved': True,
            },
        )


def unseed_nda_workflow(apps, schema_editor):
    ContractType = apps.get_model('contracts', 'ContractType')
    WorkflowTemplate = apps.get_model('contracts', 'WorkflowTemplate')
    ClauseTemplate = apps.get_model('contracts', 'ClauseTemplate')

    WorkflowTemplate.objects.filter(name=WORKFLOW_TEMPLATE_NAME).delete()
    ClauseTemplate.objects.filter(title__in=[c['title'] for c in DEMO_CLAUSES], organization__isnull=True).delete()
    ContractType.objects.filter(code='NDA').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0076_alter_fielddefinition_section'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fielddefinition',
            name='section',
            field=models.CharField(
                choices=[
                    ('BASIC_DETAILS', 'Basic details'),
                    ('NDA_TERMS', 'NDA terms'),
                    ('COMMERCIAL_TERMS', 'Commercial terms'),
                    ('SERVICES_SCOPE', 'Services & scope'),
                    ('PRIVACY_DETAILS', 'Privacy details'),
                    ('LEGAL_POSITION', 'Legal position'),
                    ('PRIVACY_QUESTIONS', 'Smart privacy questions'),
                    ('SMART_QUESTIONS', 'AI smart questions'),
                ],
                default='BASIC_DETAILS',
                max_length=20,
            ),
        ),
        migrations.RunPython(seed_nda_workflow, unseed_nda_workflow),
    ]
