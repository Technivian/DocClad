from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0088_document_review_workspace'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contract',
            name='status',
            field=models.CharField(
                choices=[
                    ('NEEDS_INPUT', 'Needs input'), ('UPLOADED', 'Uploaded'), ('PROCESSING', 'Processing'),
                    ('CLASSIFICATION_REQUIRED', 'Classification Required'), ('AI_REVIEW_IN_PROGRESS', 'AI Review in Progress'),
                    ('AI_REVIEW_READY', 'AI Review Ready'), ('HUMAN_REVIEW_IN_PROGRESS', 'Human Review in Progress'),
                    ('INFORMATION_REQUIRED', 'Information Required'), ('INTERNAL_APPROVAL_REQUIRED', 'Internal Approval Required'),
                    ('NEGOTIATION_IN_PROGRESS', 'Negotiation in Progress'), ('READY_FOR_SIGNATURE', 'Ready for Signature'),
                    ('SIGNATURE_IN_PROGRESS', 'Signature in Progress'), ('EXECUTED', 'Executed'),
                    ('OBLIGATIONS_ACTIVE', 'Obligations Active'), ('DRAFT', 'Draft'), ('PENDING', 'Pending'),
                    ('IN_REVIEW', 'In Review'), ('APPROVED', 'Approved'), ('ACTIVE', 'Active'), ('EXPIRED', 'Expired'),
                    ('TERMINATED', 'Terminated'), ('COMPLETED', 'Completed'), ('CANCELLED', 'Cancelled'),
                ], default='DRAFT', max_length=30,
            ),
        ),
        migrations.AlterField(
            model_name='documentreviewrun',
            name='status',
            field=models.CharField(
                choices=[
                    ('UPLOADED', 'Uploaded'), ('EXTRACTING', 'Extracting'),
                    ('CLASSIFICATION_REQUIRED', 'Classification required'), ('PLAYBOOK_REQUIRED', 'Playbook required'),
                    ('AI_REVIEW_IN_PROGRESS', 'AI review in progress'), ('AI_REVIEW_INCOMPLETE', 'AI review incomplete'),
                    ('READY', 'AI review ready'), ('HUMAN_REVIEW_IN_PROGRESS', 'Human review in progress'),
                    ('REVIEW_COMPLETED', 'Review completed'),
                ], default='UPLOADED', max_length=24,
            ),
        ),
    ]
