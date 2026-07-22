# PAR-DOC-001 — DocumentVersion entity + truthful backfill.

import contracts.models
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def _resolve_logical_id(document, by_id):
    current = document
    seen = set()
    while current.parent_document_id and current.parent_document_id not in seen:
        seen.add(current.id)
        current = by_id.get(current.parent_document_id, current)
    return current.id


def forwards_backfill_document_versions(apps, schema_editor):
    Document = apps.get_model('contracts', 'Document')
    DocumentVersion = apps.get_model('contracts', 'DocumentVersion')
    docs = list(Document.objects.all().order_by('id'))
    by_id = {d.id: d for d in docs}
    for doc in docs:
        logical_id = _resolve_logical_id(doc, by_id)
        locked_at = doc.version_locked_at or doc.created_at
        Document.objects.filter(pk=doc.pk).update(
            logical_document_id=logical_id,
            version_locked_at=locked_at,
            version_source=doc.version_source or 'legacy_unknown',
        )
    for doc in Document.objects.all().order_by('id'):
        if not doc.organization_id:
            continue
        if DocumentVersion.objects.filter(document_row_id=doc.pk).exists():
            continue
        original_filename = ''
        if doc.file:
            original_filename = str(doc.file).split('/')[-1]
        DocumentVersion.objects.create(
            organization_id=doc.organization_id,
            logical_document_id=doc.logical_document_id or doc.pk,
            document_row_id=doc.pk,
            version_number=doc.version or 1,
            title=doc.title,
            document_type=doc.document_type,
            status=doc.status,
            description=doc.description or '',
            file=doc.file,
            file_size=doc.file_size,
            mime_type=doc.mime_type or '',
            file_hash=doc.file_hash or '',
            original_filename=original_filename,
            source='legacy_unknown',
            uploaded_by_id=doc.uploaded_by_id,
            contract_id=doc.contract_id,
            matter_id=doc.matter_id,
            client_id=doc.client_id,
            checksum_missing=not bool(doc.file_hash),
            version_locked_at=doc.version_locked_at or doc.created_at,
        )


def backwards_clear_document_versions(apps, schema_editor):
    Document = apps.get_model('contracts', 'Document')
    DocumentVersion = apps.get_model('contracts', 'DocumentVersion')
    DocumentVersion.objects.all().delete()
    Document.objects.all().update(logical_document_id=None, version_locked_at=None, version_source='')


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0107_contract_type_catalogue_fk'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DocumentVersion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version_number', models.PositiveIntegerField()),
                ('title', models.CharField(max_length=300)),
                ('document_type', models.CharField(choices=[('CONTRACT', 'Contract Document'), ('AMENDMENT', 'Amendment'), ('EXHIBIT', 'Exhibit/Attachment'), ('CORRESPONDENCE', 'Correspondence'), ('COURT_FILING', 'Court Filing'), ('PLEADING', 'Pleading'), ('DISCOVERY', 'Discovery'), ('MEMO', 'Memorandum'), ('RESEARCH', 'Legal Research'), ('INVOICE', 'Invoice'), ('TEMPLATE', 'Template'), ('OTHER', 'Other')], max_length=20)),
                ('status', models.CharField(choices=[('DRAFT', 'Draft'), ('FINAL', 'Final'), ('EXECUTED', 'Executed'), ('SUPERSEDED', 'Superseded')], max_length=20)),
                ('description', models.TextField(blank=True, default='')),
                ('file', models.FileField(blank=True, null=True, upload_to=contracts.models.document_upload_path)),
                ('file_size', models.PositiveIntegerField(blank=True, null=True)),
                ('mime_type', models.CharField(blank=True, default='', max_length=100)),
                ('file_hash', models.CharField(blank=True, default='', max_length=64)),
                ('original_filename', models.CharField(blank=True, default='', max_length=255)),
                ('source', models.CharField(choices=[('manual_upload', 'Manual upload'), ('ai_upload', 'AI-assisted upload'), ('contract_attachment', 'Contract attachment'), ('document_edit', 'Document edit / new version'), ('counterparty_revision', 'Counterparty revision'), ('generated', 'Generated document'), ('import', 'Import'), ('legacy_unknown', 'Legacy / unknown')], default='legacy_unknown', max_length=64)),
                ('checksum_missing', models.BooleanField(default=False, help_text='True when checksum could not be computed from available bytes.')),
                ('version_locked_at', models.DateTimeField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['logical_document_id', '-version_number'],
            },
        ),
        migrations.AddField(
            model_name='document',
            name='logical_document',
            field=models.ForeignKey(blank=True, help_text='Logical document identity root; null until first version is saved.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='logical_versions', to='contracts.document'),
        ),
        migrations.AddField(
            model_name='document',
            name='version_locked_at',
            field=models.DateTimeField(blank=True, help_text='When file/content metadata became immutable for this version row.', null=True),
        ),
        migrations.AddField(
            model_name='document',
            name='version_source',
            field=models.CharField(blank=True, default='', help_text='How this version entered CLM One (manual_upload, ai_upload, …).', max_length=64),
        ),
        migrations.AddIndex(
            model_name='document',
            index=models.Index(fields=['organization', 'logical_document', '-version'], name='doc_org_logical_ver_ix'),
        ),
        migrations.AddField(
            model_name='documentversion',
            name='client',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='contracts.client'),
        ),
        migrations.AddField(
            model_name='documentversion',
            name='contract',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='contracts.contract'),
        ),
        migrations.AddField(
            model_name='documentversion',
            name='derived_from',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='derived_versions', to='contracts.documentversion'),
        ),
        migrations.AddField(
            model_name='documentversion',
            name='document_row',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='canonical_version', to='contracts.document'),
        ),
        migrations.AddField(
            model_name='documentversion',
            name='logical_document',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='version_records', to='contracts.document'),
        ),
        migrations.AddField(
            model_name='documentversion',
            name='matter',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='contracts.matter'),
        ),
        migrations.AddField(
            model_name='documentversion',
            name='organization',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='document_versions', to='contracts.organization'),
        ),
        migrations.AddField(
            model_name='documentversion',
            name='uploaded_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddIndex(
            model_name='documentversion',
            index=models.Index(fields=['organization', 'logical_document'], name='docver_org_logical_ix'),
        ),
        migrations.AddIndex(
            model_name='documentversion',
            index=models.Index(fields=['contract', '-version_number'], name='docver_contract_ver_ix'),
        ),
        migrations.AddConstraint(
            model_name='documentversion',
            constraint=models.UniqueConstraint(fields=('logical_document', 'version_number'), name='docver_logical_version_uniq'),
        ),
        migrations.RunPython(forwards_backfill_document_versions, backwards_clear_document_versions),
    ]
