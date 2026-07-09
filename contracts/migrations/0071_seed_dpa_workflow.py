"""Seed data for the DPA Privacy Review Workflow — the first flagship
workflow-first flow. Creates the DPA ContractType, the "DPA Privacy Review
Workflow" WorkflowTemplate with its 4 stages, the intake FieldDefinitions
(basic details / privacy details / legal position / smart privacy
questions), the ApprovalRoute chain, a couple of demo DPA ClauseTemplates,
and enriches the existing seeded "Standard Data Processing Agreement"
ContractTemplate body (from 0067_seed_contract_templates) so the live
preview reflects the new smart-privacy-question tokens instead of leaving
them disconnected from the document.
"""
from django.db import migrations

WORKFLOW_TEMPLATE_NAME = 'DPA Privacy Review Workflow'

WORKFLOW_STEPS = [
    {
        'order': 1, 'name': 'Draft', 'step_kind': 'TASK',
        'description': 'Complete required fields and smart privacy questions.',
    },
    {
        'order': 2, 'name': 'Legal Review', 'step_kind': 'APPROVAL',
        'description': 'Legal reviews terms and clause positions.',
        'sla_hours': 48, 'escalation_after_hours': 72,
    },
    {
        'order': 3, 'name': 'DPO / Privacy Review', 'step_kind': 'APPROVAL',
        'description': 'Privacy review of data-transfer posture, subprocessors, and breach terms.',
        'condition_expression': 'data_transfer=true',
        'sla_hours': 48, 'escalation_after_hours': 72,
    },
    {
        'order': 4, 'name': 'Approval', 'step_kind': 'APPROVAL',
        'description': 'Final sign-off before signature.',
        'sla_hours': 24,
    },
]

FIELD_DEFINITIONS = [
    # Basic details — map onto real Contract fields so one answer drives
    # both the Contract record and the live preview.
    {'key': 'counterparty', 'label': 'Counterparty', 'section': 'BASIC_DETAILS', 'field_type': 'TEXT',
     'is_required': True, 'order': 1, 'maps_to_contract_field': 'counterparty'},
    {'key': 'start_date', 'label': 'Start date', 'section': 'BASIC_DETAILS', 'field_type': 'DATE',
     'is_required': True, 'order': 2, 'maps_to_contract_field': 'start_date'},
    {'key': 'end_date', 'label': 'End date', 'section': 'BASIC_DETAILS', 'field_type': 'DATE',
     'is_required': False, 'order': 3, 'maps_to_contract_field': 'end_date'},
    {'key': 'governing_law', 'label': 'Governing law', 'section': 'BASIC_DETAILS', 'field_type': 'TEXT',
     'is_required': True, 'order': 4, 'maps_to_contract_field': 'governing_law'},
    {'key': 'jurisdiction', 'label': 'Jurisdiction', 'section': 'BASIC_DETAILS', 'field_type': 'TEXT',
     'is_required': False, 'order': 5, 'maps_to_contract_field': 'jurisdiction'},
    {'key': 'contract_owner', 'label': 'Contract owner', 'section': 'BASIC_DETAILS', 'field_type': 'TEXT',
     'is_required': True, 'order': 6},
    # Privacy details
    {'key': 'processing_purpose', 'label': 'Processing purpose', 'section': 'PRIVACY_DETAILS',
     'field_type': 'TEXTAREA', 'is_required': True, 'order': 1},
    {'key': 'personal_data_categories', 'label': 'Personal data categories', 'section': 'PRIVACY_DETAILS',
     'field_type': 'TEXTAREA', 'is_required': True, 'order': 2},
    {'key': 'data_subjects', 'label': 'Data subjects', 'section': 'PRIVACY_DETAILS',
     'field_type': 'TEXT', 'is_required': True, 'order': 3},
    # Legal position
    {'key': 'liability_position', 'label': 'Liability fallback position', 'section': 'LEGAL_POSITION',
     'field_type': 'TEXTAREA', 'is_required': False, 'order': 1,
     'help_text': 'Fallback liability language, if any deviation from standard position.'},
    # Smart privacy questions — DPA-only, no Contract equivalent except
    # cross_border_transfer, which also keeps Contract.data_transfer_flag authoritative.
    {'key': 'personal_data_involved', 'label': 'Is personal data involved?',
     'section': 'PRIVACY_QUESTIONS', 'field_type': 'BOOLEAN', 'is_required': True, 'order': 1,
     'help_text': 'Yes triggers DPA review and Legal review.'},
    {'key': 'cross_border_transfer', 'label': 'Does data leave the EEA?',
     'section': 'PRIVACY_QUESTIONS', 'field_type': 'BOOLEAN', 'is_required': True, 'order': 2,
     'maps_to_contract_field': 'data_transfer_flag', 'help_text': 'Yes triggers SCC risk and DPO approval.'},
    {'key': 'subprocessors_used', 'label': 'Are subprocessors involved?',
     'section': 'PRIVACY_QUESTIONS', 'field_type': 'BOOLEAN', 'is_required': True, 'order': 3,
     'help_text': 'Yes triggers subprocessor review.'},
    {'key': 'transfer_mechanism', 'label': 'Cross-border transfer mechanism', 'section': 'PRIVACY_QUESTIONS',
     'field_type': 'SELECT', 'is_required': True, 'order': 4,
     'options': ['SCC', 'BCR', 'Adequacy Decision', 'None']},
    {'key': 'breach_notification_hours', 'label': 'Breach notification window (hours)',
     'section': 'PRIVACY_QUESTIONS', 'field_type': 'NUMBER', 'is_required': True, 'order': 5,
     'help_text': 'Hours to notify the Controller after becoming aware of a breach.'},
    {'key': 'dpo_contact', 'label': 'Data Protection Officer contact', 'section': 'PRIVACY_QUESTIONS',
     'field_type': 'TEXT', 'is_required': False, 'order': 6,
     'help_text': 'Name/email of the Data Protection Officer or privacy contact.'},
]

APPROVAL_ROUTE = [
    {'order': 1, 'name': 'Contract Owner', 'role_label': 'Drafts and completes intake', 'is_conditional': False},
    {'order': 2, 'name': 'Legal', 'role_label': 'Reviews terms and clause positions', 'is_conditional': False},
    {'order': 3, 'name': 'DPO', 'role_label': 'Personal data processing involved', 'is_conditional': True,
     'condition_note': 'Cross-border transfer flagged'},
    {'order': 4, 'name': 'Finance', 'role_label': 'Value ≥ $250,000', 'is_conditional': True,
     'condition_note': 'High contract value'},
]

DEMO_CLAUSES = [
    {
        'title': 'Standard SCC Incorporation Clause',
        'content': (
            'Where personal data is transferred outside the jurisdiction of the Controller, the parties '
            'incorporate the applicable Standard Contractual Clauses by reference, which shall take '
            'precedence over any conflicting term of the underlying agreement.'
        ),
        'fallback_content': 'The parties will negotiate an alternative transfer mechanism in good faith.',
    },
    {
        'title': 'Subprocessor Flow-Down Clause',
        'content': (
            'Processor shall ensure that any subprocessor is bound by data protection obligations no less '
            'protective than those set out in this DPA, and shall remain fully liable for the subprocessor\'s '
            'performance.'
        ),
        'fallback_content': 'Processor will provide 30 days\' notice before engaging a new subprocessor.',
    },
]

DPA_TEMPLATE_NAME = 'Standard Data Processing Agreement'

DPA_TEMPLATE_BODY_ENRICHED = (
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
    '4. Sub-processors. Subprocessor position: {{subprocessor_position}}. Processor will not engage a '
    'sub-processor without Controller\'s prior written authorization.\n\n'
    '5. International Transfers. Data transfer position: {{data_transfer_position}}. Where personal data '
    'is transferred outside the EEA, the parties will rely on {{transfer_mechanism}} as the transfer mechanism.\n\n'
    '6. Breach Notification. Processor will notify Controller without undue delay, and in any event '
    'within {{breach_notification_hours}} hours, after becoming aware of a personal data breach.\n\n'
    '7. Data Protection Officer. Processor\'s data protection contact for matters arising under this '
    'DPA is {{dpo_contact}}.\n\n'
    '8. Governing Law. This DPA is governed by the laws of {{governing_law}}.'
)


def seed_dpa_workflow(apps, schema_editor):
    ContractType = apps.get_model('contracts', 'ContractType')
    WorkflowTemplate = apps.get_model('contracts', 'WorkflowTemplate')
    WorkflowTemplateStep = apps.get_model('contracts', 'WorkflowTemplateStep')
    FieldDefinition = apps.get_model('contracts', 'FieldDefinition')
    ApprovalRoute = apps.get_model('contracts', 'ApprovalRoute')
    ContractTemplate = apps.get_model('contracts', 'ContractTemplate')
    ClauseTemplate = apps.get_model('contracts', 'ClauseTemplate')

    contract_type, _ = ContractType.objects.get_or_create(
        code='DPA',
        defaults={
            'name': 'Data Processing Agreement',
            'description': 'GDPR-aligned processor terms with privacy, SCC, and subprocessor review.',
            'is_active': True,
        },
    )

    workflow_template, created = WorkflowTemplate.objects.get_or_create(
        name=WORKFLOW_TEMPLATE_NAME,
        contract_type=contract_type,
        defaults={
            'description': 'Governed intake, legal review, DPO/privacy review, and approval for Data Processing Agreements.',
            'organization': None,
            'category': 'COMPLIANCE',
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
        name=DPA_TEMPLATE_NAME,
        contract_type='DPA',
        defaults={
            'description': 'GDPR-aligned processor terms to attach to a primary services agreement.',
            'body': DPA_TEMPLATE_BODY_ENRICHED,
            'is_active': True,
        },
    )
    if not tmpl_created and 'transfer_mechanism' not in template.body:
        template.body = DPA_TEMPLATE_BODY_ENRICHED
        template.save(update_fields=['body'])

    for clause in DEMO_CLAUSES:
        ClauseTemplate.objects.get_or_create(
            title=clause['title'],
            organization=None,
            defaults={
                'content': clause['content'],
                'fallback_content': clause['fallback_content'],
                'applicable_contract_types': 'DPA',
                'is_approved': True,
            },
        )


def unseed_dpa_workflow(apps, schema_editor):
    ContractType = apps.get_model('contracts', 'ContractType')
    WorkflowTemplate = apps.get_model('contracts', 'WorkflowTemplate')
    ClauseTemplate = apps.get_model('contracts', 'ClauseTemplate')

    # WorkflowTemplateStep/FieldDefinition/ApprovalRoute all CASCADE from
    # WorkflowTemplate, so deleting the template is enough. ContractType's
    # FK from WorkflowTemplate is SET_NULL, not CASCADE, so delete both
    # explicitly. The pre-existing "Standard Data Processing Agreement"
    # ContractTemplate (owned by 0067) is intentionally left alone — only
    # its body may have been enriched, which is not undone here.
    WorkflowTemplate.objects.filter(name=WORKFLOW_TEMPLATE_NAME).delete()
    ContractType.objects.filter(code='DPA').delete()
    ClauseTemplate.objects.filter(title__in=[c['title'] for c in DEMO_CLAUSES], organization__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0070_dpa_workflow_models'),
    ]

    operations = [
        migrations.RunPython(seed_dpa_workflow, unseed_dpa_workflow),
    ]
