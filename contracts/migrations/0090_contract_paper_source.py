from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0089_document_review_truthful_states'),
    ]

    operations = [
        migrations.AddField(
            model_name='contract',
            name='paper_source',
            field=models.CharField(
                blank=True,
                choices=[
                    ('OUR_PAPER', 'Our paper'),
                    ('COUNTERPARTY_PAPER', 'Counterparty paper'),
                ],
                default='',
                max_length=24,
            ),
        ),
    ]
