from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0098_workflow_template_scenario'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='notify_obligation_reminders',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='notify_review_approval_requests',
            field=models.BooleanField(default=True),
        ),
    ]
