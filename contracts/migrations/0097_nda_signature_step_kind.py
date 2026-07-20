from django.db import migrations


WORKFLOW_TEMPLATE_NAME = 'NDA Self-Serve Workflow'


def remap_nda_step_kinds(apps, schema_editor):
    WorkflowTemplate = apps.get_model('contracts', 'WorkflowTemplate')
    WorkflowTemplateStep = apps.get_model('contracts', 'WorkflowTemplateStep')
    templates = WorkflowTemplate.objects.filter(name=WORKFLOW_TEMPLATE_NAME)
    for template in templates:
        WorkflowTemplateStep.objects.filter(template=template, name='Legal Review').update(
            step_kind='REVIEW',
            assignee_role='ASSOCIATE',
        )
        WorkflowTemplateStep.objects.filter(template=template, name='Signature').update(
            step_kind='SIGNATURE',
            assignee_role='',
            specific_assignee_id=None,
        )


def reverse_remap_nda_step_kinds(apps, schema_editor):
    WorkflowTemplate = apps.get_model('contracts', 'WorkflowTemplate')
    WorkflowTemplateStep = apps.get_model('contracts', 'WorkflowTemplateStep')
    templates = WorkflowTemplate.objects.filter(name=WORKFLOW_TEMPLATE_NAME)
    for template in templates:
        WorkflowTemplateStep.objects.filter(template=template, name='Legal Review').update(
            step_kind='APPROVAL',
        )
        WorkflowTemplateStep.objects.filter(template=template, name='Signature').update(
            step_kind='APPROVAL',
        )


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0096_workflow_designer_step_kinds'),
    ]

    operations = [
        migrations.RunPython(remap_nda_step_kinds, reverse_remap_nda_step_kinds),
    ]
