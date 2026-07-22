# PAR-DOC-001 — bind SignatureRequest to immutable DocumentVersion.

from django.db import migrations, models
import django.db.models.deletion


def forwards_bind_signature_document_versions(apps, schema_editor):
    SignatureRequest = apps.get_model('contracts', 'SignatureRequest')
    DocumentVersion = apps.get_model('contracts', 'DocumentVersion')
    for request in SignatureRequest.objects.exclude(document_id=None).iterator():
        version = DocumentVersion.objects.filter(document_row_id=request.document_id).first()
        if version is not None:
            SignatureRequest.objects.filter(pk=request.pk).update(document_version_id=version.pk)


def backwards_clear_signature_document_versions(apps, schema_editor):
    SignatureRequest = apps.get_model('contracts', 'SignatureRequest')
    SignatureRequest.objects.all().update(document_version_id=None)


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0108_document_version_entity'),
    ]

    operations = [
        migrations.AddField(
            model_name='signaturerequest',
            name='document_version',
            field=models.ForeignKey(
                blank=True,
                help_text='Exact immutable Document Version bound when the packet was created.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='signature_requests',
                to='contracts.documentversion',
            ),
        ),
        migrations.RunPython(
            forwards_bind_signature_document_versions,
            backwards_clear_signature_document_versions,
        ),
    ]
