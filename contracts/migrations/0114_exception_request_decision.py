# PAR-EXC-001 — ExceptionRequest + ExceptionDecision (additive; no legacy backfill).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contracts', '0113_process_role_assignment'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExceptionRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(choices=[('POLICY', 'Policy exception'), ('APPROVAL', 'Approval override'), ('WORKFLOW', 'Workflow bypass'), ('DEADLINE', 'Deadline extension'), ('SECURITY', 'Security exception'), ('SIGNATURE', 'Signature exception'), ('ADMINISTRATIVE', 'Administrative override'), ('REPAIR', 'Manual repair'), ('FEATURE_FLAG', 'Feature-flag / pilot allowance'), ('RISK_ACCEPTANCE', 'Risk acceptance'), ('AUDIT_FINDING', 'Audit finding accepted or deferred'), ('OTHER', 'Other')], max_length=32)),
                ('title', models.CharField(max_length=255)),
                ('reason', models.TextField()),
                ('scope_type', models.CharField(choices=[('CONTRACT', 'Contract'), ('DOCUMENT', 'Document'), ('DEADLINE', 'Deadline / obligation'), ('RISK_SIGNAL', 'Risk signal'), ('DPA_RISK_ITEM', 'DPA risk item'), ('REVIEW_FINDING', 'Contract review finding'), ('CONFLICT_CHECK', 'Conflict check'), ('WORKFLOW', 'Workflow'), ('ORGANIZATION', 'Organization'), ('PLATFORM', 'Platform / environment'), ('OTHER', 'Other')], max_length=32)),
                ('scope_object_model', models.CharField(blank=True, default='', help_text='Affected model name (e.g. Contract, Deadline). Empty for platform-scoped rows.', max_length=64)),
                ('scope_object_id', models.PositiveIntegerField(blank=True, null=True)),
                ('scope_reference', models.JSONField(blank=True, default=dict, help_text='Explicit scope payload; must not imply privileges beyond granted_privileges.')),
                ('authority_basis', models.CharField(choices=[('policy_owner', 'Policy owner'), ('security', 'Security'), ('workspace_admin', 'Workspace admin'), ('legal', 'Legal'), ('product_governance', 'Product governance'), ('engineering_governance', 'Engineering governance'), ('charter_exception', 'Charter exception record'), ('legacy_unknown', 'Legacy / unknown')], default='legacy_unknown', max_length=40)),
                ('authority_reference', models.JSONField(blank=True, default=dict)),
                ('risk_classification', models.CharField(choices=[('LOW', 'Low'), ('MEDIUM', 'Medium'), ('HIGH', 'High'), ('CRITICAL', 'Critical')], default='MEDIUM', max_length=16)),
                ('bypasses_critical_security_control', models.BooleanField(default=False, help_text='When True, ExceptionDecision APPROVED requires explicit Security authority.')),
                ('compensating_controls', models.TextField(blank=True, default='', help_text='Required compensating controls while the exception is active.')),
                ('granted_privileges', models.JSONField(blank=True, default=list, help_text='Explicit privilege tokens this exception may grant. Empty = deviation only, no privilege grant.')),
                ('is_permanent', models.BooleanField(default=False, help_text='False by default. Permanent exceptions require explicit approval decision metadata.')),
                ('starts_at', models.DateTimeField()),
                ('expires_at', models.DateTimeField(blank=True, help_text='Required unless is_permanent was explicitly approved.', null=True)),
                ('status', models.CharField(choices=[('DRAFT', 'Draft'), ('SUBMITTED', 'Submitted'), ('APPROVED', 'Approved'), ('REJECTED', 'Rejected'), ('ACTIVE', 'Active'), ('EXPIRED', 'Expired'), ('REVOKED', 'Revoked'), ('CLOSED', 'Closed'), ('SUPERSEDED', 'Superseded')], default='DRAFT', max_length=20)),
                ('closed_at', models.DateTimeField(blank=True, null=True)),
                ('closure_notes', models.TextField(blank=True, default='')),
                ('legacy_source', models.CharField(blank=True, default='', help_text='Discovery path id (e.g. EXC-POL-001) when linked from a legacy path.', max_length=64)),
                ('legacy_reference', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('contract', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='exception_requests', to='contracts.contract')),
                ('designated_approver', models.ForeignKey(blank=True, help_text='Named human approver when authority is person-bound.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='exception_requests_to_approve', to=settings.AUTH_USER_MODEL)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='exception_requests', to='contracts.organization')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='exception_requests_owned', to=settings.AUTH_USER_MODEL)),
                ('renewed_from', models.ForeignKey(blank=True, help_text='Prior exception this renewal supersedes.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='renewals', to='contracts.exceptionrequest')),
                ('requester', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='exception_requests_raised', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at', '-pk'],
            },
        ),
        migrations.CreateModel(
            name='ExceptionDecision',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('outcome', models.CharField(choices=[('APPROVED', 'Approved'), ('REJECTED', 'Rejected'), ('RENEWED', 'Renewed (superseding prior)'), ('CLOSED', 'Closed'), ('REVOKED', 'Revoked'), ('EXPIRED_RECORDED', 'Expiry recorded')], max_length=24)),
                ('authority_basis', models.CharField(blank=True, default='', max_length=40)),
                ('authority_holder_id', models.IntegerField(blank=True, null=True)),
                ('security_approval', models.BooleanField(default=False, help_text='True when this decision includes explicit Security approval.')),
                ('comments', models.TextField(blank=True, default='')),
                ('compensating_controls_at_decision', models.TextField(blank=True, default='')),
                ('granted_privileges_at_decision', models.JSONField(blank=True, default=list)),
                ('starts_at', models.DateTimeField(blank=True, null=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('is_permanent_approved', models.BooleanField(default=False)),
                ('decided_at', models.DateTimeField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('decided_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='exception_decisions_made', to=settings.AUTH_USER_MODEL)),
                ('exception_request', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='decisions', to='contracts.exceptionrequest')),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='exception_decisions', to='contracts.organization')),
            ],
            options={
                'ordering': ['-decided_at', '-pk'],
            },
        ),
        migrations.AddIndex(
            model_name='exceptionrequest',
            index=models.Index(fields=['organization', 'status'], name='excreq_org_status_ix'),
        ),
        migrations.AddIndex(
            model_name='exceptionrequest',
            index=models.Index(fields=['organization', 'expires_at'], name='excreq_org_expiry_ix'),
        ),
        migrations.AddIndex(
            model_name='exceptionrequest',
            index=models.Index(fields=['contract', 'status'], name='excreq_contract_status_ix'),
        ),
        migrations.AddIndex(
            model_name='exceptionrequest',
            index=models.Index(fields=['scope_type', 'scope_object_id'], name='excreq_scope_ix'),
        ),
        migrations.AddIndex(
            model_name='exceptiondecision',
            index=models.Index(fields=['exception_request', 'decided_at'], name='excdec_req_decided_ix'),
        ),
        migrations.AddIndex(
            model_name='exceptiondecision',
            index=models.Index(fields=['organization', 'outcome'], name='excdec_org_outcome_ix'),
        ),
    ]
