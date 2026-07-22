"""PAR-DOC-001 — Document Version entity hardening."""

from __future__ import annotations

import hashlib
import os
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from contracts.models import (
    AuditLog,
    Contract,
    Document,
    DocumentVersion,
    Organization,
    OrganizationMembership,
    SignatureRequest,
)
from contracts.services.document_version_service import (
    DocumentVersionError,
    EVENT_VERSION_CREATED,
    create_document_version,
)


User = get_user_model()


class DocumentVersionServiceTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='DocVer Org', slug='docver-org')
        self.other_org = Organization.objects.create(name='Other Doc Org', slug='other-docver')
        self.user = User.objects.create_user(username='docver-user', password='pass12345')
        OrganizationMembership.objects.create(
            organization=self.org, user=self.user, role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        self.contract = Contract.objects.create(
            organization=self.org,
            title='Doc Contract',
            contract_type=Contract.ContractType.MSA,
            status=Contract.Status.ACTIVE,
            lifecycle_stage=Contract.LifecycleStage.OBLIGATION_TRACKING,
            created_by=self.user,
        )

    def test_manual_upload_creates_version_record(self):
        content = b'Manual bytes'
        f = SimpleUploadedFile('manual.txt', content, content_type='text/plain')
        doc, ver = create_document_version(
            organization=self.org,
            title='Manual Doc',
            document_type=Document.DocType.CONTRACT,
            status=Document.Status.DRAFT,
            contract=self.contract,
            file=f,
            uploaded_by=self.user,
            source='manual_upload',
        )
        self.assertEqual(ver.version_number, 1)
        self.assertEqual(ver.file_hash, hashlib.sha256(content).hexdigest())
        self.assertFalse(ver.checksum_missing)
        self.assertIsNotNone(doc.version_locked_at)
        self.assertTrue(AuditLog.objects.filter(object_id=doc.pk, event_type=EVENT_VERSION_CREATED).exists())

    def test_supersession_creates_v2_and_supersedes_final(self):
        f1 = SimpleUploadedFile('v1.txt', b'v1', content_type='text/plain')
        d1, _ = create_document_version(
            organization=self.org,
            title='Final Doc',
            document_type=Document.DocType.CONTRACT,
            status=Document.Status.FINAL,
            contract=self.contract,
            file=f1,
            uploaded_by=self.user,
            source='manual_upload',
        )
        f2 = SimpleUploadedFile('v2.txt', b'v2', content_type='text/plain')
        d2, v2 = create_document_version(
            organization=self.org,
            title='Final Doc',
            document_type=Document.DocType.CONTRACT,
            status=Document.Status.FINAL,
            contract=self.contract,
            file=f2,
            uploaded_by=self.user,
            source='document_edit',
            derived_from_document=d1,
            parent_document=d1,
        )
        d1.refresh_from_db()
        self.assertEqual(d1.status, Document.Status.SUPERSEDED)
        self.assertEqual(v2.version_number, 2)
        self.assertTrue(AuditLog.objects.filter(event_type='document.superseded').exists())

    def test_immutable_version_row_rejects_file_hash_mutation(self):
        f = SimpleUploadedFile('lock.txt', b'locked', content_type='text/plain')
        doc, ver = create_document_version(
            organization=self.org,
            title='Locked',
            document_type=Document.DocType.CONTRACT,
            status=Document.Status.DRAFT,
            contract=self.contract,
            file=f,
            uploaded_by=self.user,
            source='manual_upload',
        )
        ver.file_hash = 'deadbeef'
        with self.assertRaises(DocumentVersionError):
            ver.save()

    def test_immutable_document_rejects_file_mutation(self):
        f = SimpleUploadedFile('lock2.txt', b'locked2', content_type='text/plain')
        doc, _ = create_document_version(
            organization=self.org,
            title='Locked2',
            document_type=Document.DocType.CONTRACT,
            status=Document.Status.DRAFT,
            contract=self.contract,
            file=f,
            uploaded_by=self.user,
            source='manual_upload',
        )
        doc.file_hash = 'deadbeef'
        with self.assertRaises(DocumentVersionError):
            doc.save()

    def test_queryset_update_blocked(self):
        f = SimpleUploadedFile('bulk.txt', b'bulk', content_type='text/plain')
        doc, _ = create_document_version(
            organization=self.org,
            title='Bulk',
            document_type=Document.DocType.CONTRACT,
            status=Document.Status.DRAFT,
            contract=self.contract,
            file=f,
            uploaded_by=self.user,
            source='manual_upload',
        )
        with self.assertRaises(DocumentVersionError):
            Document.objects.filter(pk=doc.pk).update(file_hash='bad')

    def test_duplicate_version_numbers_prevented(self):
        f = SimpleUploadedFile('dup.txt', b'dup', content_type='text/plain')
        d1, v1 = create_document_version(
            organization=self.org,
            title='Dup',
            document_type=Document.DocType.CONTRACT,
            status=Document.Status.DRAFT,
            contract=self.contract,
            file=f,
            uploaded_by=self.user,
            source='manual_upload',
        )
        with self.assertRaises(Exception):
            DocumentVersion.objects.create(
                organization=self.org,
                logical_document=d1.logical_document,
                document_row=d1,
                version_number=v1.version_number,
                title='Dup',
                document_type=Document.DocType.CONTRACT,
                status=Document.Status.DRAFT,
                version_locked_at=v1.version_locked_at,
            )

    def test_legacy_document_backfill_on_save(self):
        doc = Document.objects.create(
            organization=self.org,
            title='Legacy',
            document_type=Document.DocType.CONTRACT,
            status=Document.Status.DRAFT,
            contract=self.contract,
            file=SimpleUploadedFile('legacy.txt', b'legacy', content_type='text/plain'),
            uploaded_by=self.user,
        )
        self.assertTrue(hasattr(doc, 'canonical_version'))
        self.assertEqual(doc.canonical_version.source, DocumentVersion.Source.LEGACY_UNKNOWN)

    def test_document_update_view_creates_version(self):
        f = SimpleUploadedFile('base.txt', b'base', content_type='text/plain')
        doc, _ = create_document_version(
            organization=self.org,
            title='Base',
            document_type=Document.DocType.CONTRACT,
            status=Document.Status.FINAL,
            contract=self.contract,
            file=f,
            uploaded_by=self.user,
            source='manual_upload',
        )
        client = Client()
        client.login(username='docver-user', password='pass12345')
        response = client.post(
            reverse('contracts:document_update', kwargs={'pk': doc.pk}),
            data={
                'title': 'Base v2',
                'document_type': Document.DocType.CONTRACT,
                'status': Document.Status.FINAL,
                'description': 'v2',
                'file': SimpleUploadedFile('v2.txt', b'v2content', content_type='text/plain'),
                'contract': self.contract.pk,
                'matter': '',
                'client': '',
                'tags': '',
                'is_privileged': '',
                'is_confidential': '',
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(DocumentVersion.objects.filter(logical_document=doc.logical_document).count(), 2)

    def test_ai_upload_source_recorded(self):
        content = b'AI extracted bytes'
        f = SimpleUploadedFile('ai.txt', content, content_type='text/plain')
        doc, ver = create_document_version(
            organization=self.org,
            title='AI Doc',
            document_type=Document.DocType.CONTRACT,
            status=Document.Status.DRAFT,
            contract=self.contract,
            file=f,
            uploaded_by=self.user,
            source='ai_upload',
        )
        self.assertEqual(ver.source, DocumentVersion.Source.AI_UPLOAD)
        self.assertEqual(doc.version_source, 'ai_upload')

    def test_generated_document_source(self):
        content = b'generated docx bytes'
        f = SimpleUploadedFile('gen.docx', content, content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        doc, ver = create_document_version(
            organization=self.org,
            title='Generated',
            document_type=Document.DocType.CONTRACT,
            status=Document.Status.DRAFT,
            contract=self.contract,
            file=f,
            uploaded_by=self.user,
            source='generated',
        )
        self.assertEqual(ver.source, DocumentVersion.Source.GENERATED)

    def test_signature_request_binds_document_version(self):
        f = SimpleUploadedFile('sign.txt', b'sign me', content_type='text/plain')
        doc, ver = create_document_version(
            organization=self.org,
            title='Sign Doc',
            document_type=Document.DocType.CONTRACT,
            status=Document.Status.FINAL,
            contract=self.contract,
            file=f,
            uploaded_by=self.user,
            source='manual_upload',
        )
        signature = SignatureRequest.objects.create(
            organization=self.org,
            contract=self.contract,
            document=doc,
            signer_name='Signer',
            signer_email='signer@example.com',
            created_by=self.user,
        )
        self.assertEqual(signature.document_version_id, ver.pk)

    def test_cross_tenant_create_forbidden(self):
        other_contract = Contract.objects.create(
            organization=self.other_org,
            title='Other',
            contract_type=Contract.ContractType.MSA,
            status=Contract.Status.ACTIVE,
            lifecycle_stage=Contract.LifecycleStage.OBLIGATION_TRACKING,
        )
        f = SimpleUploadedFile('x.txt', b'x', content_type='text/plain')
        with self.assertRaises(Exception):
            create_document_version(
                organization=self.other_org,
                title='Cross',
                document_type=Document.DocType.CONTRACT,
                status=Document.Status.DRAFT,
                contract=other_contract,
                file=f,
                uploaded_by=self.user,
                actor=self.user,
                source='manual_upload',
            )

    def test_document_version_queryset_update_blocked(self):
        f = SimpleUploadedFile('qv.txt', b'qv', content_type='text/plain')
        _doc, ver = create_document_version(
            organization=self.org,
            title='QV',
            document_type=Document.DocType.CONTRACT,
            status=Document.Status.DRAFT,
            contract=self.contract,
            file=f,
            uploaded_by=self.user,
            source='manual_upload',
        )
        with self.assertRaises(DocumentVersionError):
            DocumentVersion.objects.filter(pk=ver.pk).update(file_hash='bad')


class DocumentVersionMigrationTests(TransactionTestCase):
    def test_migration_rollback_and_reforward(self):
        with tempfile.NamedTemporaryFile(suffix='.sqlite3', delete=False) as tmp:
            db_path = tmp.name
        self.addCleanup(lambda: os.path.exists(db_path) and os.unlink(db_path))
        db_settings = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': db_path,
            }
        }
        with override_settings(DATABASES=db_settings):
            call_command('migrate', 'contracts', '0108', verbosity=0)
            call_command('migrate', 'contracts', '0107', verbosity=0)
            call_command('migrate', 'contracts', '0109', verbosity=0)
            from django.apps import apps

            apps.clear_cache()
            DV = apps.get_model('contracts', 'DocumentVersion')
            self.assertTrue(hasattr(DV, 'objects'))
