# PAR-EXC-001 — correlation_id for dual-write idempotency.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0114_exception_request_decision'),
    ]

    operations = [
        migrations.AddField(
            model_name='exceptionrequest',
            name='correlation_id',
            field=models.CharField(
                blank=True,
                db_index=True,
                default='',
                help_text='Stable dual-write correlation key shared with the legacy record.',
                max_length=191,
            ),
        ),
        migrations.AddIndex(
            model_name='exceptionrequest',
            index=models.Index(
                fields=['organization', 'legacy_source', 'correlation_id'],
                name='excreq_corr_ix',
            ),
        ),
    ]
