from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill_contract_owners(apps, schema_editor):
    Contract = apps.get_model('contracts', 'Contract')
    Contract.objects.filter(owner__isnull=True, created_by__isnull=False).update(
        owner=models.F('created_by')
    )


class Migration(migrations.Migration):
    dependencies = [
        ('contracts', '0078_alter_organization_workspace_mode_default'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='contract',
            name='owner',
            field=models.ForeignKey(
                blank=True,
                help_text='Active workspace member accountable for this contract.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='owned_contracts',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(backfill_contract_owners, migrations.RunPython.noop),
        migrations.AddField(
            model_name='dpareviewpack',
            name='reviewer',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='assigned_dpa_review_packs',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name='approvalrequest',
            name='status',
            field=models.CharField(
                choices=[
                    ('PENDING', 'Pending'),
                    ('CHANGES_REQUESTED', 'Changes Requested'),
                    ('APPROVED', 'Approved'),
                    ('REJECTED', 'Rejected'),
                    ('ESCALATED', 'Escalated'),
                ],
                default='PENDING',
                max_length=20,
            ),
        ),
    ]
