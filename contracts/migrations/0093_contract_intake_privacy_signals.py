from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('contracts', '0092_counterparty_collaboration'),
    ]

    operations = [
        migrations.AddField(
            model_name='contract',
            name='personal_data_processing',
            field=models.BooleanField(default=False, help_text='Agreement involves processing personal data'),
        ),
        migrations.AddField(
            model_name='contract',
            name='sensitive_data_flag',
            field=models.BooleanField(default=False, help_text='Sensitive, high-volume, or non-standard personal data is involved'),
        ),
        migrations.AddField(
            model_name='contract',
            name='counterparty_privacy_review_required',
            field=models.BooleanField(default=False, help_text='Counterparty requires privacy review'),
        ),
    ]
