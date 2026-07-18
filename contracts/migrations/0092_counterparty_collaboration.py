from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0091_approvalrequest_sort_order'),
    ]

    operations = [
        migrations.AddField(
            model_name='document',
            name='share_with_counterparty',
            field=models.BooleanField(default=False, help_text='Make this document available to approved counterparty collaborators.'),
        ),
        migrations.CreateModel(
            name='CounterpartyCollaborationParticipant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, max_length=200)),
                ('email', models.EmailField(max_length=254)),
                ('token', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('ACTIVE', 'Active'), ('REVOKED', 'Revoked'), ('EXPIRED', 'Expired')], default='PENDING', max_length=12)),
                ('can_view_documents', models.BooleanField(default=True)),
                ('can_comment', models.BooleanField(default=True)),
                ('can_upload_revisions', models.BooleanField(default=False)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('accepted_at', models.DateTimeField(blank=True, null=True)),
                ('last_seen_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('contract', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='counterparty_collaboration_participants', to='contracts.contract')),
                ('invited_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sent_counterparty_collaboration_invites', to=settings.AUTH_USER_MODEL)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='counterparty_collaboration_participants', to='contracts.organization')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='CounterpartyCollaborationItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(choices=[('COMMENT', 'Comment'), ('REVISION', 'Revision'), ('TASK', 'Task')], default='COMMENT', max_length=12)),
                ('status', models.CharField(choices=[('OPEN', 'Open'), ('COMPLETED', 'Completed')], default='OPEN', max_length=12)),
                ('title', models.CharField(blank=True, max_length=200)),
                ('content', models.TextField(blank=True)),
                ('due_date', models.DateField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('completed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='completed_counterparty_collaboration_items', to=settings.AUTH_USER_MODEL)),
                ('contract', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='counterparty_collaboration_items', to='contracts.contract')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='counterparty_collaboration_items', to=settings.AUTH_USER_MODEL)),
                ('document', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='counterparty_collaboration_items', to='contracts.document')),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='counterparty_collaboration_items', to='contracts.organization')),
                ('participant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='items', to='contracts.counterpartycollaborationparticipant')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.AddIndex(
            model_name='counterpartycollaborationparticipant',
            index=models.Index(fields=['contract', 'status'], name='ccp_contract_status_ix'),
        ),
        migrations.AddIndex(
            model_name='counterpartycollaborationparticipant',
            index=models.Index(fields=['organization', 'email'], name='ccp_org_email_ix'),
        ),
        migrations.AddIndex(
            model_name='counterpartycollaborationitem',
            index=models.Index(fields=['contract', 'status', '-created_at'], name='cci_contract_status_ix'),
        ),
    ]
