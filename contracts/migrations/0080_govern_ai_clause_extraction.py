from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0079_mvp_contract_owner_dpa_reviewer_and_changes_requested'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='aiextractionspan',
            name='rationale',
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name='aiextractionspan',
            name='risk_level',
            field=models.CharField(
                choices=[('CLEAR', 'Clear'), ('REVIEW', 'Review needed'), ('RISK', 'Active risk')],
                default='REVIEW',
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='aiextractionspan',
            name='source_template',
            field=models.ForeignKey(
                blank=True,
                help_text='Approved clause-library source matched to this citation.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='ai_extraction_spans',
                to='contracts.clausetemplate',
            ),
        ),
        migrations.AddField(
            model_name='aiextractionspan',
            name='review_status',
            field=models.CharField(
                choices=[('PENDING', 'Needs review'), ('CONFIRMED', 'Confirmed'), ('DISMISSED', 'Dismissed')],
                default='PENDING',
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name='aiextractionspan',
            name='reviewed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='aiextractionspan',
            name='reviewed_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='reviewed_ai_extraction_spans',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddIndex(
            model_name='aiextractionspan',
            index=models.Index(fields=['organization', 'review_status'], name='contracts_a_organiz_b07e7a_idx'),
        ),
    ]
