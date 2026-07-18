"""Replace requester-authored DPA legal positions with operational evidence."""

from django.db import migrations


WORKFLOW_TEMPLATE_NAME = 'DPA Privacy Review Workflow'

STEP4_FIELDS = [
    ('security_measures_provided', 'Technical and organisational measures provided', 'SELECT',
     ['yes', 'no', 'not_sure'], 10),
    ('security_assurance_available', 'Security certification or assurance available', 'SELECT',
     ['yes', 'no', 'not_sure'], 11),
    ('encryption_confirmed', 'Encryption in transit and at rest confirmed', 'SELECT',
     ['yes', 'no', 'not_sure'], 12),
    ('access_controls_mfa_confirmed', 'Access controls and MFA confirmed', 'SELECT',
     ['yes', 'no', 'not_sure'], 13),
    ('privacy_contact_name', 'Counterparty privacy contact name', 'TEXT', [], 20),
    ('privacy_contact_role', 'Counterparty privacy contact role', 'TEXT', [], 21),
    ('privacy_contact_email', 'Counterparty privacy contact email', 'TEXT', [], 22),
    ('privacy_contact_phone', 'Counterparty privacy contact phone', 'TEXT', [], 23),
    ('breach_notification_commitment', 'Breach-notification commitment', 'SELECT',
     ['approved_standard', '24_hours', '48_hours', '72_hours', 'other', 'not_confirmed'], 30),
    ('breach_other_period', 'Other proposed breach-notification period', 'TEXT', [], 31),
    ('related_msa_id', 'Related MSA', 'TEXT', [], 40),
    ('governing_law_changed', 'Governing law changed from related MSA', 'BOOLEAN', [], 41),
    ('security_document_provided', 'Security documentation provided', 'BOOLEAN', [], 42),
    ('audit_rights_position', 'Standard audit rights position', 'SELECT',
     ['accepted', 'deviation', 'not_confirmed'], 50),
    ('audit_rights_proposed_wording', 'Proposed audit-rights wording', 'TEXTAREA', [], 51),
    ('audit_rights_explanation', 'Audit-rights explanation', 'TEXT', [], 52),
    ('deletion_return_position', 'Standard deletion and return position', 'SELECT',
     ['accepted', 'deviation', 'not_confirmed'], 60),
    ('deletion_return_proposed_wording', 'Proposed deletion and return wording', 'TEXTAREA', [], 61),
    ('deletion_return_explanation', 'Deletion and return explanation', 'TEXT', [], 62),
    ('dpa_liability_position', 'Standard DPA liability position', 'SELECT',
     ['accepted', 'deviation', 'not_confirmed'], 70),
    ('dpa_liability_proposed_wording', 'Proposed DPA liability wording', 'TEXTAREA', [], 71),
    ('dpa_liability_explanation', 'DPA liability explanation', 'TEXT', [], 72),
]


def apply_step4_operational_evidence(apps, schema_editor):
    WorkflowTemplate = apps.get_model('contracts', 'WorkflowTemplate')
    FieldDefinition = apps.get_model('contracts', 'FieldDefinition')
    template = WorkflowTemplate.objects.filter(name=WORKFLOW_TEMPLATE_NAME).first()
    if not template:
        return

    FieldDefinition.objects.filter(
        workflow_template=template,
        key__in=['breach_notification_hours', 'dpo_contact', 'liability_position'],
    ).update(is_required=False)

    for key, label, field_type, options, order in STEP4_FIELDS:
        FieldDefinition.objects.update_or_create(
            workflow_template=template,
            key=key,
            defaults={
                'label': label,
                'section': 'PRIVACY_QUESTIONS',
                'field_type': field_type,
                'options': options,
                # Step 4 validates these as a structured group. Keeping the
                # definitions optional preserves existing direct API callers.
                'is_required': False,
                'order': order,
                'maps_to_contract_field': 'governing_law' if key == 'governing_law' else '',
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0085_add_order_confirmation_contract_type'),
    ]

    operations = [
        migrations.RunPython(apply_step4_operational_evidence, migrations.RunPython.noop),
    ]
