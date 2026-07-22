"""Backfill assignee_role on flagship workflow templates so governed launch
policy (PAR-WF-003) can materialize demo and production instances.

Seeded DPA/MSA approval steps and the NDA Signature step were created before
launch blocking required explicit assignee configuration.
"""

from django.db import migrations

DPA_TEMPLATE = 'DPA Privacy Review Workflow'
MSA_TEMPLATE = 'MSA Commercial Review Workflow'
NDA_TEMPLATE = 'NDA Self-Serve Workflow'

DPA_STEP_ROLES = {
    'Legal Review': 'ASSOCIATE',
    'DPO / Privacy Review': 'SENIOR_ASSOCIATE',
    'Approval': 'PARTNER',
}

MSA_STEP_ROLES = {
    'Legal Review': 'ASSOCIATE',
    'Finance Review': 'ADMIN',
    'Approval': 'PARTNER',
}

NDA_STEP_ROLES = {
    'Signature': 'ASSOCIATE',
}


def _apply_step_roles(apps, template_name, step_roles):
    WorkflowTemplate = apps.get_model('contracts', 'WorkflowTemplate')
    WorkflowTemplateStep = apps.get_model('contracts', 'WorkflowTemplateStep')
    for template in WorkflowTemplate.objects.filter(name=template_name):
        for step_name, role in step_roles.items():
            WorkflowTemplateStep.objects.filter(
                template=template,
                name=step_name,
            ).exclude(assignee_role=role).update(assignee_role=role)


def forwards_assign_flagship_template_roles(apps, schema_editor):
    _apply_step_roles(apps, DPA_TEMPLATE, DPA_STEP_ROLES)
    _apply_step_roles(apps, MSA_TEMPLATE, MSA_STEP_ROLES)
    _apply_step_roles(apps, NDA_TEMPLATE, NDA_STEP_ROLES)


def backwards_clear_flagship_template_roles(apps, schema_editor):
    WorkflowTemplate = apps.get_model('contracts', 'WorkflowTemplate')
    WorkflowTemplateStep = apps.get_model('contracts', 'WorkflowTemplateStep')
    for template_name, step_roles in (
        (DPA_TEMPLATE, DPA_STEP_ROLES),
        (MSA_TEMPLATE, MSA_STEP_ROLES),
        (NDA_TEMPLATE, NDA_STEP_ROLES),
    ):
        for template in WorkflowTemplate.objects.filter(name=template_name):
            for step_name in step_roles:
                WorkflowTemplateStep.objects.filter(
                    template=template,
                    name=step_name,
                ).update(assignee_role='')


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0109_signature_request_document_version'),
    ]

    operations = [
        migrations.RunPython(
            forwards_assign_flagship_template_roles,
            backwards_clear_flagship_template_roles,
        ),
    ]
