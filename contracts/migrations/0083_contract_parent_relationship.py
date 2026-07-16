from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0082_payrollminds_msa_mvp_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='contract',
            name='parent_contract',
            field=models.ForeignKey(
                blank=True,
                help_text='Master or governing agreement that this contract belongs to.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='linked_contracts',
                to='contracts.contract',
            ),
        ),
    ]
