from django.db import migrations, models


def remap_legacy_step_kinds(apps, schema_editor):
    WorkflowTemplateStep = apps.get_model('contracts', 'WorkflowTemplateStep')
    WorkflowTemplateStep.objects.filter(step_kind='AUTOMATIC').update(step_kind='AUTOMATION')
    WorkflowTemplateStep.objects.filter(step_kind='BRANCH').update(step_kind='CONDITION')


def reverse_remap_legacy_step_kinds(apps, schema_editor):
    WorkflowTemplateStep = apps.get_model('contracts', 'WorkflowTemplateStep')
    WorkflowTemplateStep.objects.filter(step_kind='AUTOMATION').update(step_kind='AUTOMATIC')
    WorkflowTemplateStep.objects.filter(step_kind='CONDITION').update(step_kind='BRANCH')


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0095_lifecycle_three_dimensions'),
    ]

    operations = [
        migrations.AddField(
            model_name='workflowtemplatestep',
            name='condition_rules',
            field=models.JSONField(blank=True, default=None, null=True),
        ),
        migrations.AlterField(
            model_name='workflowtemplatestep',
            name='condition_expression',
            field=models.CharField(
                blank=True,
                help_text='Compiled condition expression (legacy-compatible). Prefer condition_rules.',
                max_length=512,
            ),
        ),
        migrations.AlterField(
            model_name='workflowtemplatestep',
            name='step_kind',
            field=models.CharField(
                choices=[
                    ('TASK', 'Task'),
                    ('REVIEW', 'Review'),
                    ('APPROVAL', 'Approval'),
                    ('SIGNATURE', 'Signature'),
                    ('AUTOMATION', 'Automation'),
                    ('NOTIFICATION', 'Notification'),
                    ('CONDITION', 'Condition'),
                    ('AUTOMATIC', 'Automatic'),
                    ('BRANCH', 'Branch'),
                ],
                default='TASK',
                max_length=20,
            ),
        ),
        migrations.RunPython(remap_legacy_step_kinds, reverse_remap_legacy_step_kinds),
    ]
