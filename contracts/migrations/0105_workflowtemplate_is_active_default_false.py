# Generated manually for PAR-WF-003 — unpublished-by-default workflow templates

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0104_myworksavedview'),
    ]

    operations = [
        migrations.AlterField(
            model_name='workflowtemplate',
            name='is_active',
            field=models.BooleanField(default=False),
        ),
    ]
