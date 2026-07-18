"""Preserve immutable audit actors when an application account is removed."""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0086_dpa_step4_operational_evidence'),
    ]

    operations = [
        migrations.AlterField(
            model_name='auditlog',
            name='user',
            field=models.ForeignKey(
                blank=True,
                db_constraint=False,
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name='audit_logs',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
