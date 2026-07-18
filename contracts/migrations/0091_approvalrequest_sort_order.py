from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0090_contract_paper_source'),
    ]

    operations = [
        migrations.AddField(
            model_name='approvalrequest',
            name='sort_order',
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AlterModelOptions(
            name='approvalrequest',
            options={'ordering': ['sort_order', 'created_at']},
        ),
        migrations.AddIndex(
            model_name='approvalrequest',
            index=models.Index(fields=['contract', 'sort_order'], name='ar_contract_sort_ix'),
        ),
    ]
