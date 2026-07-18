from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0087_auditlog_historical_actor_reference'),
    ]

    operations = [
        migrations.CreateModel(
            name='DocumentReviewRun',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('PROCESSING', 'Processing'), ('INFORMATION_REQUIRED', 'Information required'), ('READY', 'AI review ready'), ('FAILED', 'Review unavailable')], default='PROCESSING', max_length=24)),
                ('current_step', models.CharField(default='Uploaded', max_length=64)),
                ('progress_steps', models.JSONField(blank=True, default=list)),
                ('extracted_metadata', models.JSONField(blank=True, default=dict)),
                ('governance_sources', models.JSONField(blank=True, default=dict)),
                ('primary_next_action', models.CharField(blank=True, max_length=300)),
                ('review_objective', models.CharField(blank=True, max_length=300)),
                ('review_model', models.CharField(blank=True, max_length=100)),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('contract', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='document_review_runs', to='contracts.contract')),
                ('document', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='review_run', to='contracts.document')),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='document_review_runs', to='contracts.organization')),
            ],
            options={'ordering': ['-started_at']},
        ),
        migrations.CreateModel(
            name='ContractReviewFinding',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=240)),
                ('severity', models.CharField(choices=[('CRITICAL', 'Critical'), ('HIGH', 'High'), ('MEDIUM', 'Medium'), ('LOW', 'Low'), ('INFORMATION', 'Information')], default='MEDIUM', max_length=12)),
                ('source_clause', models.CharField(blank=True, max_length=120)),
                ('source_page', models.PositiveIntegerField(blank=True, null=True)),
                ('source_excerpt', models.TextField(blank=True)),
                ('explanation', models.TextField(blank=True)),
                ('business_legal_impact', models.TextField(blank=True)),
                ('conflicting_rule', models.TextField(blank=True)),
                ('approved_position', models.TextField(blank=True)),
                ('acceptable_fallback', models.TextField(blank=True)),
                ('suggested_redline', models.TextField(blank=True)),
                ('confidence', models.DecimalField(blank=True, decimal_places=4, max_digits=5, null=True)),
                ('recommended_action', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('OPEN', 'Open'), ('IN_PROGRESS', 'In progress'), ('DISMISSED', 'Dismissed'), ('RESOLVED', 'Resolved'), ('ESCALATED', 'Escalated'), ('INFORMATION_REQUESTED', 'Information requested'), ('EXCEPTION_REQUESTED', 'Exception requested')], default='OPEN', max_length=28)),
                ('assessment', models.TextField(blank=True)),
                ('redline_draft', models.TextField(blank=True)),
                ('comment', models.TextField(blank=True)),
                ('dismissal_reason', models.CharField(blank=True, choices=[('ACCEPTED_BUSINESS_RISK', 'Accepted business risk'), ('FALSE_POSITIVE', 'False positive'), ('COVERED_ELSEWHERE', 'Covered elsewhere'), ('APPROVED_EXCEPTION', 'Approved exception'), ('NOT_APPLICABLE', 'Not applicable'), ('OTHER', 'Other')], max_length=32)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('assigned_reviewer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_review_findings', to=settings.AUTH_USER_MODEL)),
                ('contract', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='review_findings', to='contracts.contract')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_review_findings', to=settings.AUTH_USER_MODEL)),
                ('document', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='review_findings', to='contracts.document')),
                ('resolved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='resolved_review_findings', to=settings.AUTH_USER_MODEL)),
                ('review_run', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='findings', to='contracts.documentreviewrun')),
                ('risk_log', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='review_finding', to='contracts.risklog')),
                ('source_span', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='review_finding', to='contracts.aiextractionspan')),
            ],
            options={'ordering': ['severity', 'created_at']},
        ),
        migrations.AddField(
            model_name='contract',
            name='business_unit',
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AlterField(
            model_name='contract',
            name='status',
            field=models.CharField(
                choices=[
                    ('UPLOADED', 'Uploaded'), ('PROCESSING', 'Processing'), ('CLASSIFICATION_REQUIRED', 'Classification Required'),
                    ('AI_REVIEW_IN_PROGRESS', 'AI Review in Progress'), ('AI_REVIEW_READY', 'AI Review Ready'),
                    ('HUMAN_REVIEW_IN_PROGRESS', 'Human Review in Progress'), ('INFORMATION_REQUIRED', 'Information Required'),
                    ('INTERNAL_APPROVAL_REQUIRED', 'Internal Approval Required'), ('NEGOTIATION_IN_PROGRESS', 'Negotiation in Progress'),
                    ('READY_FOR_SIGNATURE', 'Ready for Signature'), ('SIGNATURE_IN_PROGRESS', 'Signature in Progress'),
                    ('EXECUTED', 'Executed'), ('OBLIGATIONS_ACTIVE', 'Obligations Active'), ('DRAFT', 'Draft'), ('PENDING', 'Pending'),
                    ('IN_REVIEW', 'In Review'), ('APPROVED', 'Approved'), ('ACTIVE', 'Active'), ('EXPIRED', 'Expired'),
                    ('TERMINATED', 'Terminated'), ('COMPLETED', 'Completed'), ('CANCELLED', 'Cancelled'),
                ], default='DRAFT', max_length=30),
        ),
        migrations.AddIndex(model_name='documentreviewrun', index=models.Index(fields=['contract', '-started_at'], name='drr_contract_started_ix')),
        migrations.AddIndex(model_name='documentreviewrun', index=models.Index(fields=['organization', 'status'], name='drr_org_status_ix')),
        migrations.AddIndex(model_name='contractreviewfinding', index=models.Index(fields=['contract', 'status'], name='crf_contract_status_ix')),
        migrations.AddIndex(model_name='contractreviewfinding', index=models.Index(fields=['review_run', 'severity'], name='crf_run_severity_ix')),
    ]
