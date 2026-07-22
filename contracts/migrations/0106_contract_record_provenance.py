# PAR-CORE-003 — Contract Record provenance fields + truthful backfill.
#
# Forward: classify existing rows from recoverable evidence only.
# Never invent creators, reasons, or workflow links without evidence.
# No DB CHECK constraint until production data proves completeness.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


def forwards_backfill_provenance(apps, schema_editor):
    Contract = apps.get_model('contracts', 'Contract')
    Workflow = apps.get_model('contracts', 'Workflow')
    WorkflowTemplate = apps.get_model('contracts', 'WorkflowTemplate')
    now = timezone.now()

    # 1) Workflow-linked records: pin earliest workflow instance + template version.
    workflow_by_contract = {}
    for wf in (
        Workflow.objects.exclude(contract_id=None)
        .order_by('contract_id', 'created_at', 'id')
        .iterator()
    ):
        if wf.contract_id not in workflow_by_contract:
            workflow_by_contract[wf.contract_id] = wf

    template_versions = {
        pk: version
        for pk, version in WorkflowTemplate.objects.values_list('id', 'version')
    }
    for contract_id, wf in workflow_by_contract.items():
        template_id = wf.template_id
        Contract.objects.filter(pk=contract_id).update(
            origin_kind='WORKFLOW',
            origin_channel='backfill_workflow_link',
            origin_workflow_id=wf.id,
            origin_workflow_template_id=template_id,
            origin_workflow_template_version=template_versions.get(template_id),
            provenance_locked_at=now,
        )

    # 2) External integrations with recoverable source identity.
    for row in (
        Contract.objects.filter(origin_kind='')
        .exclude(source_system='')
        .exclude(source_system_id='')
        .iterator()
    ):
        Contract.objects.filter(pk=row.pk).update(
            origin_kind='INTEGRATION',
            origin_channel=(row.source_system or 'integration')[:64],
            provenance_locked_at=now,
        )

    # 3) Everything else: explicit legacy/unknown — do not invent history.
    Contract.objects.filter(origin_kind='').update(
        origin_kind='LEGACY_UNKNOWN',
        origin_channel='backfill_unclassified',
        provenance_locked_at=now,
    )


def backwards_clear_provenance(apps, schema_editor):
    Contract = apps.get_model('contracts', 'Contract')
    Contract.objects.all().update(
        origin_kind='',
        origin_channel='',
        origin_workflow_id=None,
        origin_workflow_template_id=None,
        origin_workflow_template_version=None,
        origin_reason='',
        provenance_correlation_id='',
        provenance_locked_at=None,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0105_workflowtemplate_is_active_default_false'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='contract',
            name='origin_channel',
            field=models.CharField(blank=True, default='', help_text='Narrower channel within origin_kind (e.g. salesforce, dpa_workflow, ui).', max_length=64),
        ),
        migrations.AddField(
            model_name='contract',
            name='origin_kind',
            field=models.CharField(blank=True, choices=[('WORKFLOW', 'Workflow instance'), ('MANUAL', 'Manual creation'), ('UPLOAD', 'Document upload'), ('IMPORT_CSV', 'CSV import'), ('IMPORT_INBOUND', 'Inbound import'), ('INTEGRATION', 'External integration'), ('MIGRATION', 'Data migration'), ('SEED', 'Seed / demo data'), ('ADMIN', 'Admin console'), ('LEGACY_UNKNOWN', 'Legacy / unknown')], default='', help_text='How this Contract Record entered CLM One. Blank only until first save.', max_length=32),
        ),
        migrations.AddField(
            model_name='contract',
            name='origin_reason',
            field=models.CharField(blank=True, default='', help_text='Reason for manual creation or governed provenance repair.', max_length=500),
        ),
        migrations.AddField(
            model_name='contract',
            name='origin_workflow',
            field=models.ForeignKey(blank=True, help_text='Originating Workflow Instance when created via workflow.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='originated_contracts', to='contracts.workflow'),
        ),
        migrations.AddField(
            model_name='contract',
            name='origin_workflow_template',
            field=models.ForeignKey(blank=True, help_text='Immutable Workflow Version (template row) pinned at creation.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='originated_contracts', to='contracts.workflowtemplate'),
        ),
        migrations.AddField(
            model_name='contract',
            name='origin_workflow_template_version',
            field=models.PositiveIntegerField(blank=True, help_text='Denormalized template.version at creation for durable lineage.', null=True),
        ),
        migrations.AddField(
            model_name='contract',
            name='provenance_correlation_id',
            field=models.CharField(blank=True, default='', help_text='Import batch or correlation identifier.', max_length=64),
        ),
        migrations.AddField(
            model_name='contract',
            name='provenance_locked_at',
            field=models.DateTimeField(blank=True, help_text='When provenance was finalized; fields are immutable afterwards.', null=True),
        ),
        migrations.AddIndex(
            model_name='contract',
            index=models.Index(fields=['organization', 'origin_kind'], name='ctr_org_origin_ix'),
        ),
        migrations.AddIndex(
            model_name='contract',
            index=models.Index(fields=['organization', 'provenance_correlation_id'], name='ctr_org_prov_corr_ix'),
        ),
        migrations.RunPython(forwards_backfill_provenance, backwards_clear_provenance),
    ]
