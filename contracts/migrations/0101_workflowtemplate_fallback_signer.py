# Generated manually for Workflow Designer fallback signer governance.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contracts', '0100_workflowtemplate_governance_metadata'),
    ]

    operations = [
        migrations.AddField(
            model_name='workflowtemplate',
            name='fallback_signer',
            field=models.ForeignKey(
                blank=True,
                help_text='Optional governed fallback when a Signature step has no signer configuration. When set, new launches may route to this signer instead of being blocked.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='workflow_template_fallback_signers',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
