from django.db import migrations

WORKFLOW_TEMPLATE_NAME = 'MSA Commercial Review Workflow'
MSA_TEMPLATE_NAME = 'Standard Master Service Agreement'

WORKFLOW_STEPS = [
    {
        'order': 1, 'name': 'Draft', 'step_kind': 'TASK',
        'description': 'Complete required fields and smart commercial questions.',
    },
    {
        'order': 2, 'name': 'Legal Review', 'step_kind': 'APPROVAL',
        'description': 'Legal reviews fallback positions, privacy scope, IP, and governing law.',
        'sla_hours': 48, 'escalation_after_hours': 72,
    },
    {
        'order': 3, 'name': 'Finance Review', 'step_kind': 'APPROVAL',
        'description': 'Finance reviews value, payment terms, and revenue posture.',
        'condition_expression': 'finance_threshold=true',
        'sla_hours': 24, 'escalation_after_hours': 48,
    },
    {
        'order': 4, 'name': 'Approval', 'step_kind': 'APPROVAL',
        'description': 'Final sign-off before signature.',
        'sla_hours': 24,
    },
]

FIELD_DEFINITIONS = [
    {'key': 'counterparty', 'label': 'Counterparty name', 'section': 'BASIC_DETAILS', 'field_type': 'TEXT', 'is_required': True, 'order': 1, 'maps_to_contract_field': 'counterparty'},
    {'key': 'start_date', 'label': 'Effective date', 'section': 'BASIC_DETAILS', 'field_type': 'DATE', 'is_required': True, 'order': 2, 'maps_to_contract_field': 'start_date'},
    {'key': 'contract_owner', 'label': 'Contract owner', 'section': 'BASIC_DETAILS', 'field_type': 'TEXT', 'is_required': True, 'order': 3},
    {'key': 'business_unit', 'label': 'Business unit', 'section': 'BASIC_DETAILS', 'field_type': 'TEXT', 'is_required': True, 'order': 4},
    {'key': 'internal_reference', 'label': 'Internal reference', 'section': 'BASIC_DETAILS', 'field_type': 'TEXT', 'is_required': False, 'order': 5},
    {'key': 'value', 'label': 'Contract value', 'section': 'COMMERCIAL_TERMS', 'field_type': 'NUMBER', 'is_required': True, 'order': 1, 'maps_to_contract_field': 'value'},
    {'key': 'currency', 'label': 'Currency', 'section': 'COMMERCIAL_TERMS', 'field_type': 'SELECT', 'is_required': True, 'order': 2, 'maps_to_contract_field': 'currency', 'options': ['EUR', 'USD', 'GBP']},
    {'key': 'payment_terms', 'label': 'Payment terms', 'section': 'COMMERCIAL_TERMS', 'field_type': 'TEXT', 'is_required': True, 'order': 3},
    {'key': 'initial_term', 'label': 'Initial term', 'section': 'COMMERCIAL_TERMS', 'field_type': 'TEXT', 'is_required': True, 'order': 4},
    {'key': 'renewal_type', 'label': 'Renewal type', 'section': 'COMMERCIAL_TERMS', 'field_type': 'SELECT', 'is_required': True, 'order': 5, 'options': ['Fixed term', 'Auto-renew', 'Manual renewal']},
    {'key': 'termination_notice_period', 'label': 'Termination notice period', 'section': 'COMMERCIAL_TERMS', 'field_type': 'NUMBER', 'is_required': True, 'order': 6, 'maps_to_contract_field': 'notice_period_days'},
    {'key': 'services_description', 'label': 'Services description', 'section': 'SERVICES_SCOPE', 'field_type': 'TEXTAREA', 'is_required': True, 'order': 1},
    {'key': 'sow_required', 'label': 'Statement of Work required?', 'section': 'SERVICES_SCOPE', 'field_type': 'BOOLEAN', 'is_required': False, 'order': 2, 'help_text': 'Yes means the draft should anticipate one or more SOWs.'},
    {'key': 'deliverables_defined', 'label': 'Deliverables defined?', 'section': 'SERVICES_SCOPE', 'field_type': 'BOOLEAN', 'is_required': False, 'order': 3, 'help_text': 'Yes signals the scope is concrete enough for review.'},
    {'key': 'acceptance_criteria_required', 'label': 'Acceptance criteria required?', 'section': 'SERVICES_SCOPE', 'field_type': 'BOOLEAN', 'is_required': False, 'order': 4, 'help_text': 'Yes indicates acceptance mechanics must be governed.'},
    {'key': 'governing_law', 'label': 'Governing law', 'section': 'LEGAL_POSITION', 'field_type': 'TEXT', 'is_required': True, 'order': 1, 'maps_to_contract_field': 'governing_law'},
    {'key': 'jurisdiction', 'label': 'Jurisdiction', 'section': 'LEGAL_POSITION', 'field_type': 'TEXT', 'is_required': True, 'order': 2, 'maps_to_contract_field': 'jurisdiction'},
    {'key': 'liability_cap', 'label': 'Liability cap', 'section': 'LEGAL_POSITION', 'field_type': 'TEXT', 'is_required': True, 'order': 3},
    {'key': 'confidentiality_period', 'label': 'Confidentiality period', 'section': 'LEGAL_POSITION', 'field_type': 'TEXT', 'is_required': True, 'order': 4},
    {'key': 'ip_ownership', 'label': 'IP ownership', 'section': 'LEGAL_POSITION', 'field_type': 'SELECT', 'is_required': True, 'order': 5, 'options': ['Provider', 'Customer', 'Joint', 'Custom']},
    {'key': 'personal_data_involved', 'label': 'Personal data involved?', 'section': 'LEGAL_POSITION', 'field_type': 'BOOLEAN', 'is_required': False, 'order': 6, 'help_text': 'Yes means the draft should include governed data protection terms.'},
    {'key': 'value_above_threshold_confirmed', 'label': 'Is the contract value above the finance approval threshold?', 'section': 'SMART_QUESTIONS', 'field_type': 'BOOLEAN', 'is_required': False, 'order': 1, 'help_text': 'Triggers Finance approval.'},
    {'key': 'liability_cap_nonstandard', 'label': 'Does the liability cap deviate from the standard playbook position?', 'section': 'SMART_QUESTIONS', 'field_type': 'BOOLEAN', 'is_required': False, 'order': 2, 'help_text': 'Triggers Legal review.'},
    {'key': 'services_involve_personal_data', 'label': 'Will services involve processing personal data?', 'section': 'SMART_QUESTIONS', 'field_type': 'BOOLEAN', 'is_required': False, 'order': 3, 'help_text': 'Triggers DPA/privacy review.'},
    {'key': 'auto_renewal_included', 'label': 'Is auto-renewal included?', 'section': 'SMART_QUESTIONS', 'field_type': 'BOOLEAN', 'is_required': False, 'order': 4, 'help_text': 'Triggers renewal notice review.'},
    {'key': 'ip_ownership_nonstandard', 'label': 'Is IP ownership non-standard?', 'section': 'SMART_QUESTIONS', 'field_type': 'BOOLEAN', 'is_required': False, 'order': 5, 'help_text': 'Triggers Legal review.'},
    {'key': 'governing_law_nonpreferred', 'label': 'Is the governing law outside the preferred jurisdiction?', 'section': 'SMART_QUESTIONS', 'field_type': 'BOOLEAN', 'is_required': False, 'order': 6, 'help_text': 'Triggers Legal escalation.'},
]

APPROVAL_ROUTE = [
    {'order': 1, 'name': 'Contract Owner', 'role_label': 'Drafts and completes intake', 'is_conditional': False},
    {'order': 2, 'name': 'Legal', 'role_label': 'Reviews fallback positions and escalations', 'is_conditional': True, 'condition_note': 'Liability, privacy, IP, or jurisdiction risk'},
    {'order': 3, 'name': 'Finance', 'role_label': 'Reviews value and payment posture', 'is_conditional': True, 'condition_note': 'Value above finance threshold'},
]

DEMO_CLAUSES = [
    {
        'title': 'MSA Liability Fallback Clause',
        'content': (
            'Where the liability cap deviates from the standard playbook, the approved fallback limits direct damages '
            'to a negotiated multiplier of fees while preserving excluded claims carve-outs.'
        ),
        'fallback_content': 'Escalate any uncapped liability request to Legal for explicit approval.',
    },
    {
        'title': 'MSA Renewal Notice Clause',
        'content': (
            'Automatic renewals require a documented notice period and an obligation-tracking record before the '
            'agreement is executed.'
        ),
        'fallback_content': 'Default to manual renewal if notice obligations cannot be operationally supported.',
    },
    {
        'title': 'MSA Data Protection Linkage Clause',
        'content': (
            'Where services involve processing personal data, the parties will execute or link an approved Data '
            'Processing Addendum before production processing begins.'
        ),
        'fallback_content': 'Suspend personal data processing until the approved DPA workflow is complete.',
    },
]

MSA_TEMPLATE_BODY_ENRICHED = (
    'MASTER SERVICES AGREEMENT\n\n'
    'This Master Services Agreement is entered into between DocClad B.V. and {{counterparty}} as of {{effective_date}}.\n\n'
    '1. Services\n'
    'Supplier shall provide the services described in {{services_description}} and any applicable Statement of Work.\n\n'
    '2. Fees and Payment\n'
    'The total contract value is {{value}} {{currency}}. Payment terms are {{payment_terms}}.\n\n'
    '3. Term and Renewal\n'
    'This Agreement starts on {{effective_date}} and continues for {{initial_term}}. Renewal type: {{renewal_type}}. '
    'Termination notice period: {{termination_notice_period}} days.\n\n'
    '4. Liability\n'
    'Supplier’s liability is capped at {{liability_cap}}, except for excluded claims.\n\n'
    '5. Intellectual Property\n'
    'IP ownership position: {{ip_ownership}}.\n\n'
    '6. Data Protection\n'
    '{{data_protection_clause}}\n\n'
    '7. Governing Law\n'
    'This Agreement is governed by the laws of {{governing_law}}. Jurisdiction: {{jurisdiction}}.'
)


def seed_msa_workflow(apps, schema_editor):
    ContractType = apps.get_model('contracts', 'ContractType')
    WorkflowTemplate = apps.get_model('contracts', 'WorkflowTemplate')
    WorkflowTemplateStep = apps.get_model('contracts', 'WorkflowTemplateStep')
    FieldDefinition = apps.get_model('contracts', 'FieldDefinition')
    ApprovalRoute = apps.get_model('contracts', 'ApprovalRoute')
    ContractTemplate = apps.get_model('contracts', 'ContractTemplate')
    ClauseTemplate = apps.get_model('contracts', 'ClauseTemplate')

    contract_type, _ = ContractType.objects.get_or_create(
        code='MSA',
        defaults={
            'name': 'Master Service Agreement',
            'description': 'Governed commercial agreement workflow with finance, liability, privacy, and renewal controls.',
            'is_active': True,
        },
    )

    workflow_template, created = WorkflowTemplate.objects.get_or_create(
        name=WORKFLOW_TEMPLATE_NAME,
        contract_type=contract_type,
        defaults={
            'description': 'Governed intake, legal review, finance review, and approval for Master Services Agreements.',
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
        name=MSA_TEMPLATE_NAME,
        contract_type='MSA',
        defaults={
            'description': 'Baseline MSA framework for ongoing services engagements, with governed commercial controls.',
            'body': MSA_TEMPLATE_BODY_ENRICHED,
            'is_active': True,
        },
    )
    if not tmpl_created and 'services_description' not in template.body:
        template.body = MSA_TEMPLATE_BODY_ENRICHED
        template.save(update_fields=['body'])

    for clause in DEMO_CLAUSES:
        ClauseTemplate.objects.get_or_create(
            title=clause['title'],
            organization=None,
            defaults={
                'content': clause['content'],
                'fallback_content': clause['fallback_content'],
                'applicable_contract_types': 'MSA',
                'is_approved': True,
            },
        )


def unseed_msa_workflow(apps, schema_editor):
    ContractType = apps.get_model('contracts', 'ContractType')
    WorkflowTemplate = apps.get_model('contracts', 'WorkflowTemplate')
    ClauseTemplate = apps.get_model('contracts', 'ClauseTemplate')

    WorkflowTemplate.objects.filter(name=WORKFLOW_TEMPLATE_NAME).delete()
    ClauseTemplate.objects.filter(title__in=[c['title'] for c in DEMO_CLAUSES], organization__isnull=True).delete()
    ContractType.objects.filter(code='MSA').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0074_dpa_smart_questions_expansion'),
    ]

    operations = [
        migrations.RunPython(seed_msa_workflow, unseed_msa_workflow),
    ]
