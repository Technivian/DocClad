# PAR-APR-001 — ApprovalRequirement + ApprovalDecision with truthful backfill.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def _outcome_for_status(status):
    mapping = {
        'APPROVED': 'APPROVED',
        'REJECTED': 'REJECTED',
        'CHANGES_REQUESTED': 'RETURNED',
    }
    return mapping.get(status)


def _requirement_status_for_legacy(status):
    mapping = {
        'PENDING': 'OPEN',
        'ESCALATED': 'OPEN',
        'APPROVED': 'SATISFIED',
        'REJECTED': 'REJECTED',
        'CHANGES_REQUESTED': 'RETURNED',
    }
    return mapping.get(status, 'OPEN')


def forwards_backfill_approval_canonical(apps, schema_editor):
    ApprovalRequest = apps.get_model('contracts', 'ApprovalRequest')
    ApprovalRequirement = apps.get_model('contracts', 'ApprovalRequirement')
    ApprovalDecision = apps.get_model('contracts', 'ApprovalDecision')
    DocumentVersion = apps.get_model('contracts', 'DocumentVersion')
    Document = apps.get_model('contracts', 'Document')

    for ar in ApprovalRequest.objects.select_related('contract').order_by('id'):
        org_id = ar.organization_id or (ar.contract.organization_id if ar.contract_id else None)
        if not org_id:
            continue
        if ApprovalRequirement.objects.filter(legacy_request_id=ar.pk).exists():
            continue

        document_version_id = None
        document_version_missing = True
        if ar.contract_id:
            doc = (
                Document.objects.filter(contract_id=ar.contract_id)
                .order_by('-version', '-created_at')
                .first()
            )
            if doc:
                dv = DocumentVersion.objects.filter(document_row_id=doc.pk).first()
                if dv:
                    document_version_id = dv.pk
                    document_version_missing = False

        contract = ar.contract
        requirement = ApprovalRequirement.objects.create(
            organization_id=org_id,
            contract_id=ar.contract_id,
            legacy_request_id=ar.pk,
            rule_id=ar.rule_id,
            approval_step=ar.approval_step,
            sort_order=ar.sort_order or 0,
            authority_basis='legacy_unknown',
            authority_reference={'legacy_backfill': True},
            contract_status_at_open=getattr(contract, 'status', '') or '',
            contract_lifecycle_stage_at_open=getattr(contract, 'lifecycle_stage', '') or '',
            document_version_id=document_version_id,
            document_version_missing=document_version_missing,
            assigned_to_id=ar.assigned_to_id,
            delegated_to_id=ar.delegated_to_id,
            delegated_at=ar.delegated_at,
            delegation_reason=ar.delegation_reason or '',
            delegation_ends_at=ar.delegation_ends_at,
            status=_requirement_status_for_legacy(ar.status),
            due_date=ar.due_date,
            opened_at=ar.created_at,
            opened_by_id=ar.decided_by_id,
            closed_at=ar.decided_at,
        )

        outcome = _outcome_for_status(ar.status)
        if outcome and ar.decided_at:
            ApprovalDecision.objects.create(
                organization_id=org_id,
                requirement_id=requirement.pk,
                outcome=outcome,
                decided_by_id=ar.decided_by_id,
                authority_holder_id=ar.assigned_to_id,
                acting_under_delegation=bool(
                    ar.delegated_to_id and ar.decided_by_id and ar.delegated_to_id == ar.decided_by_id
                ),
                delegation_holder_id=ar.delegated_to_id if ar.delegated_to_id else None,
                comments=ar.comments or '',
                contract_status=getattr(contract, 'status', '') or '',
                contract_lifecycle_stage=getattr(contract, 'lifecycle_stage', '') or '',
                document_version_id=document_version_id,
                document_version_missing=document_version_missing,
                decided_at=ar.decided_at,
            )


def backwards_clear_approval_canonical(apps, schema_editor):
    ApprovalDecision = apps.get_model('contracts', 'ApprovalDecision')
    ApprovalRequirement = apps.get_model('contracts', 'ApprovalRequirement')
    ApprovalDecision.objects.all().delete()
    ApprovalRequirement.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0110_flagship_workflow_template_assignees'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ApprovalRequirement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('approval_step', models.CharField(max_length=50)),
                ('sort_order', models.PositiveSmallIntegerField(default=0)),
                ('authority_basis', models.CharField(choices=[('rule', 'Approval rule'), ('manual', 'Manual submission'), ('workflow_submit', 'Workflow submit'), ('ai_ad_hoc', 'AI-assisted ad hoc'), ('legacy_unknown', 'Legacy / unknown')], default='legacy_unknown', max_length=32)),
                ('authority_reference', models.JSONField(blank=True, default=dict)),
                ('contract_status_at_open', models.CharField(blank=True, default='', max_length=32)),
                ('contract_lifecycle_stage_at_open', models.CharField(blank=True, default='', max_length=32)),
                ('document_version_missing', models.BooleanField(default=False, help_text='True when no Document Version could be bound at requirement open.')),
                ('delegated_at', models.DateTimeField(blank=True, null=True)),
                ('delegation_reason', models.TextField(blank=True, default='')),
                ('delegation_ends_at', models.DateTimeField(blank=True, null=True)),
                ('status', models.CharField(choices=[('OPEN', 'Open'), ('SATISFIED', 'Satisfied'), ('REJECTED', 'Rejected'), ('RETURNED', 'Returned'), ('INVALIDATED', 'Invalidated'), ('CANCELLED', 'Cancelled')], default='OPEN', max_length=20)),
                ('due_date', models.DateTimeField(blank=True, null=True)),
                ('invalidation_reason', models.TextField(blank=True, default='')),
                ('invalidated_at', models.DateTimeField(blank=True, null=True)),
                ('opened_at', models.DateTimeField(auto_now_add=True)),
                ('closed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['sort_order', 'opened_at'],
            },
        ),
        migrations.CreateModel(
            name='ApprovalDecision',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('outcome', models.CharField(choices=[('APPROVED', 'Approved'), ('REJECTED', 'Rejected'), ('RETURNED', 'Returned'), ('REVOKED', 'Revoked'), ('ABSTAINED', 'Abstained')], max_length=20)),
                ('authority_holder_id', models.IntegerField(blank=True, null=True)),
                ('acting_under_delegation', models.BooleanField(default=False)),
                ('delegation_holder_id', models.IntegerField(blank=True, null=True)),
                ('comments', models.TextField(blank=True, default='')),
                ('contract_status', models.CharField(blank=True, default='', max_length=32)),
                ('contract_lifecycle_stage', models.CharField(blank=True, default='', max_length=32)),
                ('document_version_missing', models.BooleanField(default=False)),
                ('decided_at', models.DateTimeField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-decided_at', '-pk'],
            },
        ),
        migrations.AddField(
            model_name='approvalrequirement',
            name='assigned_to',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='approval_requirements', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='approvalrequirement',
            name='contract',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='approval_requirements', to='contracts.contract'),
        ),
        migrations.AddField(
            model_name='approvalrequirement',
            name='delegated_to',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='delegated_approval_requirements', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='approvalrequirement',
            name='document_version',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='approval_requirements', to='contracts.documentversion'),
        ),
        migrations.AddField(
            model_name='approvalrequirement',
            name='legacy_request',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='canonical_requirement', to='contracts.approvalrequest'),
        ),
        migrations.AddField(
            model_name='approvalrequirement',
            name='opened_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='opened_approval_requirements', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='approvalrequirement',
            name='organization',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='approval_requirements', to='contracts.organization'),
        ),
        migrations.AddField(
            model_name='approvalrequirement',
            name='rule',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='contracts.approvalrule'),
        ),
        migrations.AddField(
            model_name='approvaldecision',
            name='decided_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='approval_decisions_made', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='approvaldecision',
            name='document_version',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='approval_decisions', to='contracts.documentversion'),
        ),
        migrations.AddField(
            model_name='approvaldecision',
            name='organization',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='approval_decisions', to='contracts.organization'),
        ),
        migrations.AddField(
            model_name='approvaldecision',
            name='requirement',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='decisions', to='contracts.approvalrequirement'),
        ),
        migrations.AddIndex(
            model_name='approvalrequirement',
            index=models.Index(fields=['contract', 'status'], name='apreq_contract_status_ix'),
        ),
        migrations.AddIndex(
            model_name='approvalrequirement',
            index=models.Index(fields=['organization', 'status'], name='apreq_org_status_ix'),
        ),
        migrations.RunPython(forwards_backfill_approval_canonical, backwards_clear_approval_canonical),
    ]
