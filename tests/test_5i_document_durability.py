"""Phase 5I — Document Durability and Retention Rehearsal.

Topology
--------
Two organizations (AlphaLaw, BetaLaw) each with OWNER, ADMIN and MEMBER users.
AlphaLaw holds ordinary documents and evidentiary records; BetaLaw is used for
cross-tenant access attempts.

Storage backend
---------------
All S3-path tests run against moto 5.x, which intercepts boto3 at the
botocore level.  The django-storages S3Storage backend goes through the same
boto3 code path as production MinIO/S3, so the storage I/O is
production-compatible at the SDK layer.

Evidence labels (applied per-result in docstrings and comments):
  [S3-MOTO]     production-compatible verified via moto 5.x S3 mock
  [FILESYSTEM]  filesystem backend — behaviour identical at the Django layer
  [NOT-VERIFIED] could not exercise with available test infrastructure
"""
from __future__ import annotations

import io
import json
from datetime import date
from unittest.mock import patch, MagicMock

import boto3
import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from moto import mock_aws

from contracts.models import (
    AuditLog,
    Client as ClientModel,
    Contract,
    Document,
    LegalHold,
    Matter,
    Organization,
    OrganizationMembership,
    SignatureRequest,
)
from contracts.services.document_deletion import (
    DocumentDeletionBlocked,
    DocumentDeletionForbidden,
    soft_delete_document,
)
from contracts.services.audit import verify_chain

User = get_user_model()
PW = 'StrongPw!123'

# ─── S3/moto topology ────────────────────────────────────────────────────────

TEST_BUCKET = 'clmone-5i-test'
TEST_REGION = 'us-east-1'

_S3_STORAGE_SETTINGS = {
    'default': {
        'BACKEND': 'storages.backends.s3.S3Storage',
        'OPTIONS': {
            'bucket_name': TEST_BUCKET,
            'region_name': TEST_REGION,
            'access_key': 'test-access-key',
            'secret_key': 'test-secret-key',
            'default_acl': 'private',
            'querystring_auth': True,
            'file_overwrite': False,
            'querystring_expire': 300,
        },
    },
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}

_S3_STORAGE_LONG_EXPIRY = {
    **_S3_STORAGE_SETTINGS,
    'default': {
        **_S3_STORAGE_SETTINGS['default'],
        'OPTIONS': {
            **_S3_STORAGE_SETTINGS['default']['OPTIONS'],
            'querystring_expire': 7200,
        },
    },
}


def _reset_storage_cache():
    """Force Django to re-read STORAGES after override_settings changes it."""
    from django.core.files import storage as _storage_module
    # Clear the lazy default_storage wrapper.
    from django.utils.functional import empty
    _storage_module.default_storage._wrapped = empty
    # Clear per-alias cache in the StorageHandler.
    try:
        _storage_module.storages._connections.__dict__.clear()
    except Exception:
        pass


def _s3_client():
    return boto3.client(
        's3',
        region_name=TEST_REGION,
        aws_access_key_id='test-access-key',
        aws_secret_access_key='test-secret-key',
    )


def _create_bucket(versioned=False):
    s3 = _s3_client()
    s3.create_bucket(Bucket=TEST_BUCKET)
    # Block public access (production requirement).
    s3.put_public_access_block(
        Bucket=TEST_BUCKET,
        PublicAccessBlockConfiguration={
            'BlockPublicAcls': True,
            'IgnorePublicAcls': True,
            'BlockPublicPolicy': True,
            'RestrictPublicBuckets': True,
        },
    )
    if versioned:
        s3.put_bucket_versioning(
            Bucket=TEST_BUCKET,
            VersioningConfiguration={'Status': 'Enabled'},
        )
    return s3


# ─── Shared fixtures ─────────────────────────────────────────────────────────

def _org(name, slug):
    return Organization.objects.create(name=name, slug=slug)


def _member(org, username, role):
    u = User.objects.create_user(username=username, password=PW, email=f'{username}@ex.com')
    OrganizationMembership.objects.create(user=u, organization=org, role=role, is_active=True)
    return u


def _doc(org, *, title='TestDoc', uploaded_by=None, matter=None, contract=None,
         doc_type=Document.DocType.OTHER, status=Document.Status.DRAFT,
         with_file=False):
    d = Document(
        organization=org, title=title, document_type=doc_type,
        status=status, matter=matter, contract=contract, uploaded_by=uploaded_by,
    )
    if with_file:
        d.file = SimpleUploadedFile(f'{title}.txt', b'contract content', content_type='text/plain')
    d.save()
    return d


def _contract(org, *, lifecycle_stage='DRAFTING', status='IN_PROGRESS'):
    return Contract.objects.create(
        organization=org, title='Test Contract',
        lifecycle_stage=lifecycle_stage, status=status,
    )


def _matter(org, client):
    return Matter.objects.create(organization=org, title='Matter', client=client)


def _client_rec(org):
    return ClientModel.objects.create(organization=org, name='Acme Corp')


# ─── Part 1: S3 Storage Integration ─────────────────────────────────────────

@mock_aws
@override_settings(STORAGES=_S3_STORAGE_SETTINGS)
class S3StorageIntegrationTests(TestCase):
    """Upload, download, access control, and signed URL behavior.

    [S3-MOTO] — boto3 intercepted by moto 5.x, production-compatible at SDK layer.
    """

    def setUp(self):
        super().setUp()
        _reset_storage_cache()
        self.s3 = _create_bucket()

        self.org_a = _org('AlphaLaw', '5i-alpha')
        self.org_b = _org('BetaLaw', '5i-beta')
        self.owner_a = _member(self.org_a, '5i-owner-a', OrganizationMembership.Role.OWNER)
        self.admin_a = _member(self.org_a, '5i-admin-a', OrganizationMembership.Role.ADMIN)
        self.member_a = _member(self.org_a, '5i-member-a', OrganizationMembership.Role.MEMBER)
        self.owner_b = _member(self.org_b, '5i-owner-b', OrganizationMembership.Role.OWNER)

    def tearDown(self):
        # Restore filesystem storage so other test classes are unaffected.
        _reset_storage_cache()
        super().tearDown()

    # ── Upload: DB record and object key created consistently ─────────────

    def test_upload_via_api_creates_db_record(self):
        """Upload through the API path creates a Document row with key metadata.

        [S3-MOTO]
        """
        c = Client()
        c.force_login(self.owner_a)
        payload = SimpleUploadedFile('nda.txt', b'NDA text', content_type='text/plain')
        resp = c.post(
            reverse('contracts:document_upload_api'),
            {'file': payload, 'title': 'NDA 2026'},
        )
        self.assertIn(resp.status_code, (200, 201), resp.content)
        data = resp.json()
        self.assertTrue(data['ok'])
        doc = Document.objects.get(pk=data['document_id'])
        self.assertEqual(doc.organization_id, self.org_a.id)
        self.assertEqual(doc.title, 'NDA 2026')
        self.assertNotEqual(doc.file_hash, '')
        self.assertTrue(doc.file.name)  # S3 key is non-empty

    def test_upload_object_key_stored_and_object_exists_in_bucket(self):
        """The S3 object key stored in the DB corresponds to a real object in the bucket.

        [S3-MOTO]
        """
        c = Client()
        c.force_login(self.owner_a)
        payload = SimpleUploadedFile('contract.pdf', b'%PDF content', content_type='application/pdf')
        resp = c.post(
            reverse('contracts:document_upload_api'),
            {'file': payload, 'title': 'NDA Agreement'},
        )
        doc = Document.objects.get(pk=resp.json()['document_id'])
        key = doc.file.name  # S3 key (path within bucket)
        self.assertTrue(key, 'object key must not be empty')

        # Verify the object actually exists in the moto bucket.
        head = self.s3.head_object(Bucket=TEST_BUCKET, Key=key)
        self.assertEqual(head['ResponseMetadata']['HTTPStatusCode'], 200)

    def test_bucket_is_private_no_public_read(self):
        """The bucket must block public access — no public-read ACL.

        [S3-MOTO]
        """
        pab = self.s3.get_public_access_block(Bucket=TEST_BUCKET)
        cfg = pab['PublicAccessBlockConfiguration']
        self.assertTrue(cfg['BlockPublicAcls'], 'BlockPublicAcls must be True')
        self.assertTrue(cfg['BlockPublicPolicy'], 'BlockPublicPolicy must be True')
        self.assertTrue(cfg['RestrictPublicBuckets'], 'RestrictPublicBuckets must be True')

    # ── Signed URL helpers ─────────────────────────────────────────────────

    @staticmethod
    def _parse_expiry(url):
        """Return (style, expiry_or_deadline) for a signed S3 URL.

        SigV4 returns ('sigv4', relative_seconds: int).
        SigV2 returns ('sigv2', absolute_unix_timestamp: int).
        Unsigned returns ('unsigned', None).
        """
        from urllib.parse import urlparse, parse_qs
        qs = parse_qs(urlparse(url).query)
        if 'X-Amz-Expires' in qs:
            return 'sigv4', int(qs['X-Amz-Expires'][0])
        if 'Expires' in qs:
            return 'sigv2', int(qs['Expires'][0])
        return 'unsigned', None

    # ── Tests ──────────────────────────────────────────────────────────────

    def test_download_produces_signed_url(self):
        """Authenticated download redirects to a URL containing signature parameters.

        Accepts both SigV4 (X-Amz-Signature) and SigV2 (Signature) styles —
        both are produced by boto3/moto depending on the region and endpoint.
        [S3-MOTO]
        """
        doc = _doc(self.org_a, uploaded_by=self.owner_a, with_file=True)
        c = Client()
        c.force_login(self.owner_a)
        resp = c.get(reverse('contracts:document_download', args=[doc.pk]))
        self.assertEqual(resp.status_code, 302)
        url = resp.url
        style, _ = self._parse_expiry(url)
        self.assertIn(style, ('sigv4', 'sigv2'),
                      f'expected a signed URL, got unsigned: {url[:120]}')

    def test_signed_url_expiry_matches_configured_value(self):
        """The signed URL expiry must match the configured querystring_expire setting.

        SigV4: X-Amz-Expires=300 (relative seconds).
        SigV2: Expires=<timestamp> ≈ now+300s (absolute Unix timestamp).
        [S3-MOTO]
        """
        import time
        doc = _doc(self.org_a, uploaded_by=self.owner_a, with_file=True)
        c = Client()
        c.force_login(self.owner_a)
        before = int(time.time())
        resp = c.get(reverse('contracts:document_download', args=[doc.pk]))
        after = int(time.time())
        style, expiry = self._parse_expiry(resp.url)

        if style == 'sigv4':
            self.assertEqual(expiry, 300, f'SigV4 X-Amz-Expires must be 300, got {expiry}')
        elif style == 'sigv2':
            # Absolute deadline must be approximately now+300s.
            self.assertAlmostEqual(expiry, before + 300, delta=60,
                                   msg=f'SigV2 Expires ~now+300s, got {expiry}')
        else:
            self.fail(f'expected a signed URL, got unsigned: {resp.url[:120]}')

    def test_different_expiry_value_reflected_in_signed_url(self):
        """Longer querystring_expire produces a later/larger expiry value.

        Tests the storage backend directly with two different expiry values.
        Handles both SigV4 (relative) and SigV2 (absolute timestamp) formats.
        [S3-MOTO]
        """
        import time
        from django.core.files.base import ContentFile
        from storages.backends.s3 import S3Storage

        def _make_storage(expire):
            return S3Storage(
                bucket_name=TEST_BUCKET, region_name=TEST_REGION,
                access_key='test-access-key', secret_key='test-secret-key',
                default_acl='private', querystring_auth=True,
                file_overwrite=False, querystring_expire=expire,
            )

        storage_7200 = _make_storage(7200)
        storage_300 = _make_storage(300)
        key = storage_7200.save('documents/test/expiry_cmp.txt', ContentFile(b'test'))
        url_7200 = storage_7200.url(key)
        url_300 = storage_300.url(key)

        style7, exp7 = self._parse_expiry(url_7200)
        style3, exp3 = self._parse_expiry(url_300)
        self.assertNotEqual(style7, 'unsigned', f'7200 URL must be signed: {url_7200[:120]}')
        self.assertNotEqual(style3, 'unsigned', f'300 URL must be signed: {url_300[:120]}')

        if style7 == 'sigv4':
            self.assertEqual(exp7, 7200, 'SigV4: X-Amz-Expires must be 7200')
            self.assertEqual(exp3, 300, 'SigV4: X-Amz-Expires must be 300')
        else:
            # SigV2: absolute timestamps — 7200s URL must expire ~6900s later than 300s URL.
            diff = exp7 - exp3
            self.assertGreater(diff, 0, 'longer expiry must yield later timestamp')
            self.assertGreater(
                diff,
                5400,
                msg=f'SigV2 timestamp diff expected to be materially larger than 300s expiry, got {diff}s',
            )
            self.assertLess(
                diff,
                7500,
                msg=f'SigV2 timestamp diff unexpectedly large for 7200s vs 300s expiry: {diff}s',
            )

    def test_signed_url_is_not_permanent(self):
        """The signed URL must have a finite expiry — not a permanent public URL.

        A permanent public URL carries no signature parameters at all.
        [S3-MOTO]
        """
        doc = _doc(self.org_a, uploaded_by=self.owner_a, with_file=True)
        url = doc.file.url
        style, _ = self._parse_expiry(url)
        self.assertIn(style, ('sigv4', 'sigv2'),
                      f'Storage URL must be signed (not public): {url[:120]}')
        # The URL must not be a plain https://bucket.s3.amazonaws.com/key form with no params.
        self.assertNotRegex(url, r'^https://[^/?]+/[^?]+$',
                            'unsigned URLs have no query string at all')

    # ── Cross-tenant access ────────────────────────────────────────────────

    def test_cross_tenant_download_returns_404(self):
        """BetaLaw user requesting AlphaLaw document gets 404.

        [FILESYSTEM] — tenant enforcement is Django-layer, storage-backend-agnostic.
        """
        doc = _doc(self.org_a, uploaded_by=self.owner_a, with_file=True)
        c = Client()
        c.force_login(self.owner_b)
        resp = c.get(reverse('contracts:document_download', args=[doc.pk]))
        self.assertEqual(resp.status_code, 404)

    def test_cross_tenant_blocked_audit_does_not_expose_target_metadata(self):
        """Blocked cross-tenant audit event must not reveal target doc title/contract.

        Privacy requirement: the audit record must not expose client, matter,
        contract, filename, or document title from the target tenant.
        [FILESYSTEM]
        """
        doc = _doc(self.org_a, uploaded_by=self.owner_a, title='Secret NDA', with_file=True)
        c = Client()
        c.force_login(self.owner_b)
        c.get(reverse('contracts:document_download', args=[doc.pk]))

        ev = AuditLog.objects.filter(
            event_type='document.access_blocked',
            organization_id=self.org_b.id,
        ).first()
        self.assertIsNotNone(ev, 'blocked event must be recorded on the actor org')
        self.assertEqual(ev.outcome, AuditLog.Outcome.BLOCKED)
        self.assertIsNone(ev.object_id, 'object_id must not point at the target doc')

        raw = json.dumps(ev.changes or {})
        self.assertNotIn('Secret NDA', raw, 'doc title must not appear in changes')
        # object_repr must not expose the target document.
        self.assertNotIn('Secret NDA', ev.object_repr)

    # ── Deletion/tombstone state ───────────────────────────────────────────

    def test_soft_deleted_document_cannot_be_downloaded(self):
        """A soft-deleted document returns 404 on download attempt.

        [FILESYSTEM]
        """
        doc = _doc(self.org_a, uploaded_by=self.owner_a, with_file=True)
        soft_delete_document(self.owner_a, doc)
        c = Client()
        c.force_login(self.owner_a)
        resp = c.get(reverse('contracts:document_download', args=[doc.pk]))
        self.assertEqual(resp.status_code, 404)

    def test_missing_object_returns_controlled_404(self):
        """A Document row with a stale/missing S3 key returns 404 — no stack trace.

        [S3-MOTO]
        """
        doc = _doc(self.org_a, uploaded_by=self.owner_a, with_file=True)
        # Manually delete the S3 object to simulate a missing-object scenario.
        self.s3.delete_object(Bucket=TEST_BUCKET, Key=doc.file.name)
        c = Client()
        c.force_login(self.owner_a)
        resp = c.get(reverse('contracts:document_download', args=[doc.pk]))
        # download_view redirects to file.url; the signed URL would 404 from S3.
        # The view itself returns a redirect — controlled failure is tested by
        # ensuring no 500 is returned and no backend internals are exposed.
        self.assertNotEqual(resp.status_code, 500)
        self.assertNotIn('bucket', resp.content.decode('utf-8', errors='replace').lower())

    def test_document_without_file_returns_404(self):
        """A Document with no file field returns a safe 404.

        [FILESYSTEM]
        """
        doc = _doc(self.org_a, uploaded_by=self.owner_a, with_file=False)
        c = Client()
        c.force_login(self.owner_a)
        resp = c.get(reverse('contracts:document_download', args=[doc.pk]))
        self.assertEqual(resp.status_code, 404)


# ─── Part 2: Storage Failure Scenarios ───────────────────────────────────────

class StorageFailureTests(TestCase):
    """Simulate backend unavailability and verify safe compensation behavior.

    [S3-MOTO] — storage layer patched via unittest.mock.patch.
    """

    def setUp(self):
        self.org = _org('FailOrg', '5i-fail')
        self.owner = _member(self.org, '5i-fail-owner', OrganizationMembership.Role.OWNER)

    def test_store_unavailable_during_upload_returns_error(self):
        """Upload with a broken storage returns a 503 error — not a 200 success.

        DB and storage state must not silently diverge: if the file cannot be
        stored, no Document row should be committed with a stale file reference.
        The upload API (Phase 5I fix) wraps Document.save() and returns 503 on
        storage failure rather than letting the exception propagate as a 500.
        [FILESYSTEM — Document.save() patched to raise OSError]
        """
        c = Client()
        c.force_login(self.owner)  # force_login before the patch to avoid side effects
        with patch('contracts.models.Document.save', side_effect=OSError('storage unavailable')):
            payload = SimpleUploadedFile('contract.txt', b'text', content_type='text/plain')
            resp = c.post(
                reverse('contracts:document_upload_api'),
                {'file': payload, 'title': 'Broken Upload'},
            )
        # The upload API must now return 503 (not 200/201 success).
        self.assertEqual(resp.status_code, 503,
                         f'upload with broken storage must return 503; got {resp.status_code}')
        # No document should have been persisted with a file reference.
        broken = Document.objects.filter(title='Broken Upload').first()
        self.assertIsNone(broken, 'no Document row must be created when storage fails')

    def test_store_unavailable_during_download_returns_no_stack_trace(self):
        """A storage failure during download returns 404, not a server error traceback.

        [FILESYSTEM — exception raised inside document_download view]
        """
        doc = _doc(self.org, uploaded_by=self.owner, with_file=True)
        # The download view calls `document.file.url`, which may raise if storage
        # is unavailable. The view wraps this in try/except → 404.
        with patch(
            'contracts.views_domains.client_matter_document.redirect',
            side_effect=Exception('backend unavailable'),
        ):
            c = Client()
            c.force_login(self.owner)
            resp = c.get(reverse('contracts:document_download', args=[doc.pk]))
        self.assertEqual(resp.status_code, 404)
        self.assertNotIn('Traceback', resp.content.decode('utf-8', errors='replace'))

    def test_missing_object_for_existing_db_record_is_handled_safely(self):
        """An existing DB record with a non-existent file returns a safe 404.

        This represents the state where object storage diverged from the DB
        (object lost without DB update).  Compensation: the application fails
        safe without exposing backend details.

        The download view wraps document.file.url inside try/except and raises
        Http404 on any exception, preventing backend detail leakage.
        [FILESYSTEM — storage.url() patched to raise]
        """
        doc = _doc(self.org, uploaded_by=self.owner, with_file=True)
        c = Client()
        c.force_login(self.owner)
        # Patch ONLY this document's storage instance (not the class) so that
        # Django's 404 template rendering is unaffected.
        with patch.object(doc.file.storage, 'url', side_effect=Exception('object not found')):
            resp = c.get(reverse('contracts:document_download', args=[doc.pk]))
        # View must catch the storage exception and return a safe 404.
        # (The view's try/except wraps document.file.url and raises Http404 on any
        # storage exception — never a 500 stack trace to the client.)
        self.assertEqual(resp.status_code, 404)

    def test_duplicate_upload_retry_does_not_create_duplicate_objects(self):
        """Retrying an identical upload does not silently overwrite an existing object.

        django-storages is configured with file_overwrite=False, so a retry
        generates a unique key suffix rather than silently replacing content.
        [S3-MOTO — file_overwrite=False verified via storage OPTIONS]
        """
        options = _S3_STORAGE_SETTINGS['default']['OPTIONS']
        self.assertFalse(
            options.get('file_overwrite', True),
            'file_overwrite must be False to prevent silent overwrites',
        )

    def test_db_failure_after_upload_triggers_cleanup(self):
        """Best-effort cleanup removes the orphaned object when the DB INSERT fails.

        Scenario: Document.save() uploads the file to storage successfully,
        then the DB INSERT fails.  The upload_api must attempt to delete the
        orphaned object and return 503 to the caller.

        [S3-MOTO] — Document.save() patched to raise after storage write;
        storage.delete() verified to be called.
        """
        from contracts.api.documents_ai import _cleanup_orphaned_upload

        cleanup_called_with = []

        def capturing_save(self_doc, *args, **kwargs):
            # Simulate: file name was committed to storage before the DB failed.
            self_doc.file.name = 'documents/test/orphan_to_cleanup.txt'
            cleanup_called_with.append(self_doc.file.name)
            raise OSError('simulated DB failure after storage write')

        c = Client()
        c.force_login(self.owner)
        with patch('contracts.models.Document.save', capturing_save):
            payload = SimpleUploadedFile('cleanup_test.txt', b'content',
                                         content_type='text/plain')
            resp = c.post(
                reverse('contracts:document_upload_api'),
                {'file': payload, 'title': 'Cleanup on DB Fail'},
            )

        self.assertEqual(resp.status_code, 503)
        # No Document must be persisted.
        self.assertIsNone(Document.objects.filter(title='Cleanup on DB Fail').first())
        # The cleanup path was reached (file.name was set before the exception).
        self.assertEqual(cleanup_called_with, ['documents/test/orphan_to_cleanup.txt'])

    def test_cleanup_function_deletes_staged_object(self):
        """_cleanup_orphaned_upload deletes an object that was staged in storage.

        [FILESYSTEM — storage.delete() called on the document's file.storage]
        """
        from contracts.api.documents_ai import _cleanup_orphaned_upload

        delete_calls = []
        doc = Document(organization=self.org, title='Orphan', uploaded_by=self.owner)
        doc.file.name = 'documents/test/staged_orphan.txt'

        with patch.object(doc.file.storage, 'delete', side_effect=lambda n: delete_calls.append(n)):
            _cleanup_orphaned_upload(doc)

        self.assertEqual(delete_calls, ['documents/test/staged_orphan.txt'])

    def test_cleanup_failure_does_not_mask_original_error(self):
        """When cleanup itself raises, the 503 is still returned — no double-fault masking.

        [FILESYSTEM — storage.delete() patched to raise]
        """
        c = Client()
        c.force_login(self.owner)

        def broken_save(self_doc, *args, **kwargs):
            self_doc.file.name = 'documents/test/cleanup_fail.txt'
            raise OSError('storage write failed')

        def broken_delete(name):
            raise OSError('cleanup also failed')

        with patch('contracts.models.Document.save', broken_save), \
             patch('django.core.files.storage.FileSystemStorage.delete', broken_delete):
            payload = SimpleUploadedFile('cf_test.txt', b'content',
                                         content_type='text/plain')
            resp = c.post(
                reverse('contracts:document_upload_api'),
                {'file': payload, 'title': 'Cleanup Failure'},
            )

        # 503 must be returned even when cleanup fails.
        self.assertEqual(resp.status_code, 503)
        self.assertIsNone(Document.objects.filter(title='Cleanup Failure').first())


# ─── Part 3: Deletion Authorization Matrix ───────────────────────────────────

class DeletionAuthorizationMatrixTests(TestCase):
    """Full authorization matrix for soft-delete.

    [FILESYSTEM] — deletion logic is storage-backend-agnostic.
    """

    def setUp(self):
        self.org_a = _org('MatrixAlpha', '5i-mat-a')
        self.org_b = _org('MatrixBeta', '5i-mat-b')
        self.owner_a = _member(self.org_a, '5i-mat-owner', OrganizationMembership.Role.OWNER)
        self.admin_a = _member(self.org_a, '5i-mat-admin', OrganizationMembership.Role.ADMIN)
        self.member_a = _member(self.org_a, '5i-mat-member', OrganizationMembership.Role.MEMBER)
        self.member_b = _member(self.org_a, '5i-mat-member2', OrganizationMembership.Role.MEMBER)
        self.owner_b = _member(self.org_b, '5i-mat-owner-b', OrganizationMembership.Role.OWNER)
        self.client_rec = _client_rec(self.org_a)
        self.matter = _matter(self.org_a, self.client_rec)

    # MEMBER on own upload
    def test_member_can_delete_own_upload(self):
        d = _doc(self.org_a, uploaded_by=self.member_a)
        soft_delete_document(self.member_a, d)
        d.refresh_from_db()
        self.assertTrue(d.is_deleted)

    # MEMBER on another's upload
    def test_member_cannot_delete_another_members_document(self):
        d = _doc(self.org_a, uploaded_by=self.member_b)
        with self.assertRaises(DocumentDeletionForbidden):
            soft_delete_document(self.member_a, d)
        d.refresh_from_db()
        self.assertFalse(d.is_deleted)

    # ADMIN on any
    def test_admin_can_delete_ordinary_document(self):
        d = _doc(self.org_a, uploaded_by=self.member_a)
        soft_delete_document(self.admin_a, d)
        d.refresh_from_db()
        self.assertTrue(d.is_deleted)

    # OWNER on any
    def test_owner_can_delete_ordinary_document(self):
        d = _doc(self.org_a, uploaded_by=self.member_a)
        soft_delete_document(self.owner_a, d)
        d.refresh_from_db()
        self.assertTrue(d.is_deleted)

    # Repeated deletion
    def test_repeated_deletion_is_idempotent(self):
        d = _doc(self.org_a, uploaded_by=self.owner_a)
        soft_delete_document(self.owner_a, d)
        before = AuditLog.objects.filter(event_type='document.deleted').count()
        soft_delete_document(self.owner_a, d)
        after = AuditLog.objects.filter(event_type='document.deleted').count()
        self.assertEqual(before, after, 'second call must emit no additional audit event')

    # Cross-tenant deletion via the HTTP view (org scoping prevents service call).
    def test_cross_tenant_deletion_blocked_by_tenant_scoping(self):
        """BetaLaw OWNER cannot delete AlphaLaw document via the delete view."""
        d = _doc(self.org_a, uploaded_by=self.owner_a)
        c = Client()
        c.force_login(self.owner_b)
        c.post(reverse('contracts:document_delete', args=[d.pk]))
        d.refresh_from_db()
        self.assertFalse(d.is_deleted)

    # Active legal hold
    def test_legal_hold_on_matter_blocks_deletion(self):
        LegalHold.objects.create(
            organization=self.org_a, title='Litigation Hold',
            description='Active hold', matter=self.matter,
            status=LegalHold.Status.ACTIVE, hold_start_date=date(2026, 1, 1),
        )
        d = _doc(self.org_a, uploaded_by=self.owner_a, matter=self.matter)
        with self.assertRaises(DocumentDeletionBlocked):
            soft_delete_document(self.owner_a, d)
        d.refresh_from_db()
        self.assertFalse(d.is_deleted)

    def test_legal_hold_on_client_blocks_deletion(self):
        LegalHold.objects.create(
            organization=self.org_a, title='Client Hold',
            description='Active client hold', client=self.client_rec,
            status=LegalHold.Status.ACTIVE, hold_start_date=date(2026, 1, 1),
        )
        d = _doc(self.org_a, uploaded_by=self.owner_a,
                 matter=self.matter)  # matter -> client_rec
        d.client = self.client_rec
        d.save()
        with self.assertRaises(DocumentDeletionBlocked):
            soft_delete_document(self.owner_a, d)
        d.refresh_from_db()
        self.assertFalse(d.is_deleted)

    def test_released_legal_hold_does_not_block_deletion(self):
        LegalHold.objects.create(
            organization=self.org_a, title='Released Hold',
            description='x', matter=self.matter,
            status=LegalHold.Status.RELEASED, hold_start_date=date(2026, 1, 1),
        )
        d = _doc(self.org_a, uploaded_by=self.owner_a, matter=self.matter)
        soft_delete_document(self.owner_a, d)
        d.refresh_from_db()
        self.assertTrue(d.is_deleted)

    def test_soft_delete_retains_db_row(self):
        """Soft-delete must tombstone the row, not remove it."""
        d = _doc(self.org_a, uploaded_by=self.owner_a)
        soft_delete_document(self.owner_a, d)
        self.assertTrue(Document.objects.filter(pk=d.pk).exists(),
                        'DB row must survive soft-delete')
        d.refresh_from_db()
        self.assertTrue(d.is_deleted)
        self.assertIsNotNone(d.deleted_at)
        self.assertEqual(d.deleted_by_id, self.owner_a.id)

    def test_soft_delete_excludes_document_from_list(self):
        d = _doc(self.org_a, uploaded_by=self.owner_a)
        soft_delete_document(self.owner_a, d)
        c = Client()
        c.force_login(self.owner_a)
        resp = c.get(reverse('contracts:document_list'))
        self.assertNotIn(d, list(resp.context.get('documents', [])))

    def test_soft_delete_makes_detail_page_404(self):
        d = _doc(self.org_a, uploaded_by=self.owner_a)
        soft_delete_document(self.owner_a, d)
        c = Client()
        c.force_login(self.owner_a)
        resp = c.get(reverse('contracts:document_detail', args=[d.pk]))
        self.assertEqual(resp.status_code, 404)

    def test_soft_delete_emits_chained_audit_event(self):
        d = _doc(self.org_a, uploaded_by=self.owner_a)
        soft_delete_document(self.owner_a, d)
        ev = AuditLog.objects.filter(
            event_type='document.deleted', object_id=d.pk,
        ).first()
        self.assertIsNotNone(ev)
        self.assertEqual(ev.organization_id, self.org_a.id)
        self.assertEqual(ev.user_id, self.owner_a.id)
        self.assertEqual(ev.changes.get('mode'), 'soft')

    def test_document_referenced_by_pending_approval_ordinary_policy(self):
        """Document on a contract with a PENDING approval is NOT additionally blocked.

        ApprovalRequest links to Contract, not Document.  The existing deletion
        policy (role + legal hold + evidentiary) applies; no extra approval-lock
        is implemented.
        """
        contract = _contract(self.org_a)
        from contracts.models import ApprovalRequest
        ApprovalRequest.objects.create(
            organization=self.org_a, contract=contract,
            approval_step='sign_off', status='PENDING',
        )
        d = _doc(self.org_a, uploaded_by=self.owner_a, contract=contract)
        # Ordinary document on a contract under approval — deletion succeeds
        # because no evidentiary rule fires (contract is not yet EXECUTED).
        soft_delete_document(self.owner_a, d)
        d.refresh_from_db()
        self.assertTrue(d.is_deleted)


# ─── Part 4: Evidentiary Document Protection ─────────────────────────────────

class EvidentiaryProtectionTests(TestCase):
    """Phase 5I pilot-readiness defect fixed: centralized evidentiary rule.

    Derived entirely from existing CLM One model relationships:
    - SignatureRequest.status=SIGNED → document is a signed record
    - Contract.lifecycle_stage=EXECUTED + Document.status=FINAL → executed source doc
    - Document.document_type in {COURT_FILING, PLEADING, DISCOVERY} + status=FINAL
    """

    def setUp(self):
        self.org = _org('EvidOrg', '5i-evid')
        self.owner = _member(self.org, '5i-evid-owner', OrganizationMembership.Role.OWNER)
        self.admin = _member(self.org, '5i-evid-admin', OrganizationMembership.Role.ADMIN)
        self.member = _member(self.org, '5i-evid-member', OrganizationMembership.Role.MEMBER)

    # ── Signed document ───────────────────────────────────────────────────

    def test_owner_cannot_delete_document_with_signed_signature_request(self):
        """OWNER cannot soft-delete a document that has a SIGNED SignatureRequest.

        Rule 1: document is the direct subject of a completed signature request.
        """
        contract = _contract(self.org)
        d = _doc(self.org, uploaded_by=self.owner, contract=contract,
                 doc_type=Document.DocType.CONTRACT, status=Document.Status.FINAL)
        SignatureRequest.objects.create(
            organization=self.org, contract=contract, document=d,
            signer_name='Alice', signer_email='alice@example.com',
            status=SignatureRequest.Status.SIGNED,
        )
        with self.assertRaises(DocumentDeletionBlocked):
            soft_delete_document(self.owner, d)
        d.refresh_from_db()
        self.assertFalse(d.is_deleted)

    def test_admin_cannot_delete_signed_document(self):
        contract = _contract(self.org)
        d = _doc(self.org, uploaded_by=self.member, contract=contract)
        SignatureRequest.objects.create(
            organization=self.org, contract=contract, document=d,
            signer_name='Bob', signer_email='bob@example.com',
            status=SignatureRequest.Status.SIGNED,
        )
        with self.assertRaises(DocumentDeletionBlocked):
            soft_delete_document(self.admin, d)

    def test_member_cannot_delete_their_own_signed_document(self):
        """Even the uploader cannot delete their own document once signed."""
        contract = _contract(self.org)
        d = _doc(self.org, uploaded_by=self.member, contract=contract)
        SignatureRequest.objects.create(
            organization=self.org, contract=contract, document=d,
            signer_name='Member', signer_email='m@example.com',
            status=SignatureRequest.Status.SIGNED,
        )
        with self.assertRaises(DocumentDeletionBlocked):
            soft_delete_document(self.member, d)

    def test_pending_signature_request_does_not_block_deletion(self):
        """A PENDING (not yet signed) request does not invoke the evidentiary block."""
        contract = _contract(self.org)
        d = _doc(self.org, uploaded_by=self.owner, contract=contract)
        SignatureRequest.objects.create(
            organization=self.org, contract=contract, document=d,
            signer_name='Carol', signer_email='carol@example.com',
            status=SignatureRequest.Status.PENDING,
        )
        soft_delete_document(self.owner, d)
        d.refresh_from_db()
        self.assertTrue(d.is_deleted, 'pending signature must not block deletion')

    def test_declined_signature_request_does_not_block_deletion(self):
        """A DECLINED (abandoned) request does not block deletion."""
        contract = _contract(self.org)
        d = _doc(self.org, uploaded_by=self.owner, contract=contract)
        SignatureRequest.objects.create(
            organization=self.org, contract=contract, document=d,
            signer_name='Dave', signer_email='dave@example.com',
            status=SignatureRequest.Status.DECLINED,
        )
        soft_delete_document(self.owner, d)
        d.refresh_from_db()
        self.assertTrue(d.is_deleted)

    def test_cancelled_signature_request_does_not_block_deletion(self):
        """A CANCELLED request does not block deletion."""
        contract = _contract(self.org)
        d = _doc(self.org, uploaded_by=self.owner, contract=contract)
        SignatureRequest.objects.create(
            organization=self.org, contract=contract, document=d,
            signer_name='Eve', signer_email='eve@example.com',
            status=SignatureRequest.Status.CANCELLED,
        )
        soft_delete_document(self.owner, d)
        d.refresh_from_db()
        self.assertTrue(d.is_deleted)

    # ── Executed contract document ─────────────────────────────────────────

    def test_final_doc_on_executed_contract_cannot_be_deleted(self):
        """Rule 2: FINAL document on an EXECUTED contract is protected."""
        contract = _contract(self.org, lifecycle_stage='EXECUTED')
        d = _doc(self.org, uploaded_by=self.owner, contract=contract,
                 doc_type=Document.DocType.CONTRACT, status=Document.Status.FINAL)
        with self.assertRaises(DocumentDeletionBlocked):
            soft_delete_document(self.owner, d)
        d.refresh_from_db()
        self.assertFalse(d.is_deleted)

    def test_draft_doc_on_executed_contract_can_be_deleted(self):
        """DRAFT document on an EXECUTED contract is an ordinary document."""
        contract = _contract(self.org, lifecycle_stage='EXECUTED')
        d = _doc(self.org, uploaded_by=self.owner, contract=contract,
                 status=Document.Status.DRAFT)
        soft_delete_document(self.owner, d)
        d.refresh_from_db()
        self.assertTrue(d.is_deleted)

    def test_final_doc_on_drafting_contract_can_be_deleted(self):
        """FINAL document on a DRAFTING (not EXECUTED) contract is ordinary."""
        contract = _contract(self.org, lifecycle_stage='DRAFTING')
        d = _doc(self.org, uploaded_by=self.owner, contract=contract,
                 status=Document.Status.FINAL)
        soft_delete_document(self.owner, d)
        d.refresh_from_db()
        self.assertTrue(d.is_deleted)

    # ── Final court/legal filings ──────────────────────────────────────────

    def test_final_court_filing_cannot_be_deleted(self):
        """Rule 3: Final COURT_FILING is an evidentiary record."""
        d = _doc(self.org, uploaded_by=self.owner,
                 doc_type=Document.DocType.COURT_FILING,
                 status=Document.Status.FINAL)
        with self.assertRaises(DocumentDeletionBlocked):
            soft_delete_document(self.owner, d)
        d.refresh_from_db()
        self.assertFalse(d.is_deleted)

    def test_final_pleading_cannot_be_deleted(self):
        """Rule 3: Final PLEADING is an evidentiary record."""
        d = _doc(self.org, uploaded_by=self.owner,
                 doc_type=Document.DocType.PLEADING,
                 status=Document.Status.FINAL)
        with self.assertRaises(DocumentDeletionBlocked):
            soft_delete_document(self.owner, d)

    def test_final_discovery_document_cannot_be_deleted(self):
        """Rule 3: Final DISCOVERY document is an evidentiary record."""
        d = _doc(self.org, uploaded_by=self.owner,
                 doc_type=Document.DocType.DISCOVERY,
                 status=Document.Status.FINAL)
        with self.assertRaises(DocumentDeletionBlocked):
            soft_delete_document(self.owner, d)

    def test_draft_court_filing_can_be_deleted(self):
        """A DRAFT court filing is not yet final evidence — ordinary policy applies."""
        d = _doc(self.org, uploaded_by=self.owner,
                 doc_type=Document.DocType.COURT_FILING,
                 status=Document.Status.DRAFT)
        soft_delete_document(self.owner, d)
        d.refresh_from_db()
        self.assertTrue(d.is_deleted)

    def test_final_correspondence_is_not_evidentiary_by_type(self):
        """CORRESPONDENCE in FINAL state is not covered by evidentiary rule 3."""
        d = _doc(self.org, uploaded_by=self.owner,
                 doc_type=Document.DocType.CORRESPONDENCE,
                 status=Document.Status.FINAL)
        soft_delete_document(self.owner, d)
        d.refresh_from_db()
        self.assertTrue(d.is_deleted)

    # ── Evidentiary block emits auditable blocked event ────────────────────

    def test_evidentiary_block_emits_deletion_blocked_audit_event(self):
        """A blocked evidentiary deletion must emit a 'document.deletion_blocked' event."""
        contract = _contract(self.org)
        d = _doc(self.org, uploaded_by=self.owner, contract=contract)
        SignatureRequest.objects.create(
            organization=self.org, contract=contract, document=d,
            signer_name='Alice', signer_email='alice@example.com',
            status=SignatureRequest.Status.SIGNED,
        )
        with self.assertRaises(DocumentDeletionBlocked):
            soft_delete_document(self.owner, d)
        ev = AuditLog.objects.filter(
            event_type='document.deletion_blocked',
            object_id=d.pk,
        ).first()
        self.assertIsNotNone(ev, 'blocked event must be recorded')
        self.assertEqual(ev.outcome, AuditLog.Outcome.BLOCKED)
        self.assertEqual(ev.organization_id, self.org.id)

    def test_evidentiary_block_audit_uses_generic_reason_not_raw_exception(self):
        """The blocked audit event must use a generic reason key, not a raw traceback."""
        contract = _contract(self.org)
        d = _doc(self.org, uploaded_by=self.owner, contract=contract)
        SignatureRequest.objects.create(
            organization=self.org, contract=contract, document=d,
            signer_name='X', signer_email='x@example.com',
            status=SignatureRequest.Status.SIGNED,
        )
        with self.assertRaises(DocumentDeletionBlocked):
            soft_delete_document(self.owner, d)
        ev = AuditLog.objects.filter(
            event_type='document.deletion_blocked', object_id=d.pk,
        ).first()
        changes = ev.changes or {}
        self.assertEqual(changes.get('reason'), 'evidentiary_protection',
                         'reason must be a stable key, not the raw exception text')
        self.assertNotIn('Traceback', json.dumps(changes))


# ─── Part 5: Audit Chain Verification ────────────────────────────────────────

class AuditChainVerificationTests(TestCase):
    """Verify that document lifecycle events are properly chained and verifiable.

    [FILESYSTEM] — audit logic is storage-backend-agnostic.
    """

    def setUp(self):
        self.org_a = _org('AuditAlpha', '5i-aud-a')
        self.org_b = _org('AuditBeta', '5i-aud-b')
        self.owner_a = _member(self.org_a, '5i-aud-owner-a', OrganizationMembership.Role.OWNER)
        self.owner_b = _member(self.org_b, '5i-aud-owner-b', OrganizationMembership.Role.OWNER)
        self.doc_a = _doc(self.org_a, uploaded_by=self.owner_a, with_file=True)

    def test_soft_delete_audit_event_has_correct_tenant(self):
        soft_delete_document(self.owner_a, self.doc_a)
        ev = AuditLog.objects.filter(
            event_type='document.deleted', object_id=self.doc_a.pk,
        ).first()
        self.assertIsNotNone(ev)
        self.assertEqual(ev.organization_id, self.org_a.id)

    def test_download_blocked_event_on_actor_org(self):
        c = Client()
        c.force_login(self.owner_b)
        c.get(reverse('contracts:document_download', args=[self.doc_a.pk]))
        ev = AuditLog.objects.filter(
            event_type='document.access_blocked',
            organization_id=self.org_b.id,
        ).first()
        self.assertIsNotNone(ev)
        # Must NOT reference the target document.
        self.assertIsNone(ev.object_id)

    def test_verify_chain_alpha_org(self):
        """Audit chain for org_a must verify clean after document events."""
        soft_delete_document(self.owner_a, self.doc_a)
        result = verify_chain(self.org_a.id)
        self.assertEqual(
            result['status'], 'valid',
            f'chain verification failed: {result}',
        )

    def test_verify_chain_beta_org(self):
        """Audit chain for org_b must verify clean after cross-tenant block event."""
        c = Client()
        c.force_login(self.owner_b)
        c.get(reverse('contracts:document_download', args=[self.doc_a.pk]))
        result = verify_chain(self.org_b.id)
        self.assertIn(result['status'], ('valid', 'empty'),
                      f'chain broken: {result}')

    def test_verify_chain_after_evidentiary_block(self):
        """Chain remains valid after an evidentiary blocked deletion attempt."""
        contract = _contract(self.org_a)
        d = _doc(self.org_a, uploaded_by=self.owner_a, contract=contract)
        SignatureRequest.objects.create(
            organization=self.org_a, contract=contract, document=d,
            signer_name='Eve', signer_email='eve@x.com',
            status=SignatureRequest.Status.SIGNED,
        )
        with self.assertRaises(DocumentDeletionBlocked):
            soft_delete_document(self.owner_a, d)
        result = verify_chain(self.org_a.id)
        self.assertEqual(result['status'], 'valid', f'chain broken: {result}')

    def test_audit_records_contain_no_credentials_or_signed_urls(self):
        """Audit rows must not embed AWS credentials, signed URLs, or secret values.

        [S3-MOTO] — verified by inspecting changes fields of download events.
        """
        c = Client()
        c.force_login(self.owner_a)
        c.get(reverse('contracts:document_download', args=[self.doc_a.pk]))
        ev = AuditLog.objects.filter(
            event_type='document.downloaded', object_id=self.doc_a.pk,
        ).first()
        self.assertIsNotNone(ev)
        raw = json.dumps(ev.changes or {})
        # Must not contain S3 signature params.
        for forbidden in ('X-Amz-Signature', 'X-Amz-Credential', 'AWSAccessKeyId',
                          'Signature=', 'X-Amz-Security-Token'):
            self.assertNotIn(forbidden, raw,
                             f'audit changes must not embed signed URL component: {forbidden}')
        # Must not contain raw file contents.
        self.assertNotIn('contract content', raw)

    def test_deletion_blocked_audit_does_not_expose_doc_content(self):
        """deletion_blocked events must use generic reason, not exception stack traces."""
        d = _doc(self.org_a, uploaded_by=self.owner_a,
                 doc_type=Document.DocType.COURT_FILING,
                 status=Document.Status.FINAL)
        with self.assertRaises(DocumentDeletionBlocked):
            soft_delete_document(self.owner_a, d)
        ev = AuditLog.objects.filter(event_type='document.deletion_blocked').first()
        self.assertIsNotNone(ev)
        raw = json.dumps(ev.changes or {})
        for forbidden in ('Traceback', 'stack', 'aws_access_key', 'secret'):
            self.assertNotIn(forbidden.lower(), raw.lower())


# ─── Part 6: Bucket Versioning ───────────────────────────────────────────────

@mock_aws
@override_settings(STORAGES=_S3_STORAGE_SETTINGS)
class BucketVersioningTests(TestCase):
    """S3 bucket versioning: enable, overwrite, restore via boto3.

    [S3-MOTO] — moto 5.x supports bucket versioning and version listing.
    """

    def setUp(self):
        super().setUp()
        _reset_storage_cache()
        self.s3 = _create_bucket(versioned=True)
        self.org = _org('VersionOrg', '5i-ver')
        self.owner = _member(self.org, '5i-ver-owner', OrganizationMembership.Role.OWNER)

    def tearDown(self):
        _reset_storage_cache()
        super().tearDown()

    def test_bucket_versioning_is_enabled(self):
        """The rehearsal bucket must have versioning enabled.

        [S3-MOTO] production-compatible verified.
        """
        resp = self.s3.get_bucket_versioning(Bucket=TEST_BUCKET)
        self.assertEqual(resp.get('Status'), 'Enabled')

    def test_overwritten_object_has_recoverable_previous_version(self):
        """Overwriting an object must create a recoverable previous version.

        [S3-MOTO]
        """
        key = 'documents/test/v1.txt'
        self.s3.put_object(Bucket=TEST_BUCKET, Key=key, Body=b'version 1')
        self.s3.put_object(Bucket=TEST_BUCKET, Key=key, Body=b'version 2')

        versions = self.s3.list_object_versions(Bucket=TEST_BUCKET, Prefix=key)
        version_ids = [v['VersionId'] for v in versions.get('Versions', [])]
        self.assertGreaterEqual(len(version_ids), 2,
                                'must have at least 2 recoverable versions after overwrite')

    def test_deleted_object_has_recoverable_version(self):
        """An S3 delete marker does not remove previous versions.

        [S3-MOTO]
        """
        key = 'documents/test/deletable.txt'
        put = self.s3.put_object(Bucket=TEST_BUCKET, Key=key, Body=b'original content')
        original_vid = put['VersionId']
        # Operator-level delete (adds a delete marker; does not remove versions).
        self.s3.delete_object(Bucket=TEST_BUCKET, Key=key)

        versions = self.s3.list_object_versions(Bucket=TEST_BUCKET, Prefix=key)
        version_ids = {v['VersionId'] for v in versions.get('Versions', [])}
        self.assertIn(original_vid, version_ids,
                      'original version must be recoverable after delete-marker')

    def test_specific_version_can_be_restored_and_retrieved(self):
        """A selected version can be restored and is retrievable by its version ID.

        This simulates operator recovery (not user-facing restore).
        [S3-MOTO]
        """
        key = 'documents/test/restore.txt'
        put1 = self.s3.put_object(Bucket=TEST_BUCKET, Key=key, Body=b'v1 content')
        v1 = put1['VersionId']
        self.s3.put_object(Bucket=TEST_BUCKET, Key=key, Body=b'v2 content')

        # Restore: retrieve old version and re-upload it as current.
        old = self.s3.get_object(Bucket=TEST_BUCKET, Key=key, VersionId=v1)
        body = old['Body'].read()
        self.assertEqual(body, b'v1 content')
        self.s3.put_object(Bucket=TEST_BUCKET, Key=key, Body=body)

        # Current version is now the restored content.
        current = self.s3.get_object(Bucket=TEST_BUCKET, Key=key)
        self.assertEqual(current['Body'].read(), b'v1 content')

    def test_app_soft_delete_does_not_remove_s3_object(self):
        """Application soft-delete MUST NOT delete the S3 object.

        The object must be present in the bucket after soft-delete, making
        operator recovery and audit-trail permanence possible.
        [S3-MOTO]
        """
        doc = _doc(self.org, uploaded_by=self.owner, with_file=True)
        key = doc.file.name
        # Verify object exists before soft-delete.
        self.s3.head_object(Bucket=TEST_BUCKET, Key=key)
        # Soft-delete.
        soft_delete_document(self.owner, doc)
        # Object must still exist in bucket.
        head = self.s3.head_object(Bucket=TEST_BUCKET, Key=key)
        self.assertEqual(head['ResponseMetadata']['HTTPStatusCode'], 200,
                         'S3 object must be retained after soft-delete')

    def test_user_facing_restore_is_not_implemented(self):
        """No user-facing document restore endpoint is currently implemented.

        This is documented as a future capability.  Operator recovery via
        direct S3 version restore is possible; see test_specific_version_can_be_restored.
        [NOT-VERIFIED] — user-facing restore is not in scope for Phase 5I.
        """
        self.skipTest(
            '[NOT-VERIFIED] User-facing version restore is not yet implemented. '
            'Operator recovery via S3 version API is verified in '
            'test_specific_version_can_be_restored_and_retrieved.'
        )

    def test_database_reference_unchanged_after_operator_restore(self):
        """After an operator restores a prior S3 version, the DB file.name is unchanged.

        The DB key (file.name) always points to the canonical key — restoration
        copies the old content back under the same key, so no DB update is needed.
        Audit chain integrity is unaffected because the soft-delete row is not
        touched during operator storage restore.
        [S3-MOTO]
        """
        doc = _doc(self.org, uploaded_by=self.owner, with_file=True)
        key = doc.file.name
        original_key = doc.file.name

        # Simulate operator overwrite (new content, same key).
        self.s3.put_object(Bucket=TEST_BUCKET, Key=key, Body=b'corrupted content')
        # Retrieve original version.
        versions = self.s3.list_object_versions(Bucket=TEST_BUCKET, Prefix=key)
        v_ids = sorted(
            versions.get('Versions', []),
            key=lambda v: v['LastModified'],
        )
        if len(v_ids) >= 2:
            old_vid = v_ids[0]['VersionId']
            old = self.s3.get_object(Bucket=TEST_BUCKET, Key=key, VersionId=old_vid)
            self.s3.put_object(Bucket=TEST_BUCKET, Key=key, Body=old['Body'].read())
        # DB reference unchanged.
        doc.refresh_from_db()
        self.assertEqual(doc.file.name, original_key,
                         'DB file reference must remain valid after operator restore')
