from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0101_workflowtemplate_fallback_signer'),
    ]

    operations = [
        migrations.AddField(
            model_name='approvalrequest',
            name='delegation_reason',
            field=models.TextField(
                blank=True,
                help_text='Why coverage was delegated (absence, workload, specialty).',
            ),
        ),
        migrations.AddField(
            model_name='approvalrequest',
            name='delegation_ends_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text='When delegated coverage ends. Blank means open-ended.',
            ),
        ),
    ]
