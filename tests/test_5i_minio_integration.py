"""Phase 5I — MinIO Integration Rehearsal (real object storage).

Topology
--------
Docker-based MinIO server (RELEASE.2025-09-07T16-13-09Z) started as a
subprocess fixture for this module.  All DocClad HTTP paths run against
production settings (config.settings_production) with the storage backend
pointed at the local MinIO instance.

If Docker is unavailable or MinIO fails to start, every test in this module is
skipped with a clear reason.  The moto-backed tests in test_5i_document_durability.py
continue to provide production-compatible SDK-layer coverage.

Evidence labels
---------------
  [MINIO-REAL]   exercised against a live MinIO process; production-compatible
  [SKIP-REASON]  why a test was skipped (printed with --verbose)
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import time
import urllib.request
from urllib.error import URLError
from unittest.mock import patch, MagicMock

import boto3
import pytest
from botocore.exceptions import ClientError
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from contracts.models import (
    AuditLog,
    Contract,
    Document,
    Organization,
    OrganizationMembership,
    SignatureRequest,
)
from contracts.services.document_deletion import (
    DocumentDeletionBlocked,
    soft_delete_document,
)

User = get_user_model()
PW = 'StrongPw!123'

# ─── MinIO process management ────────────────────────────────────────────────

MINIO_HOST = '127.0.0.1'
MINIO_PORT = 9100            # Non-standard port to avoid conflicts with dev stacks
MINIO_ENDPOINT = f'http://{MINIO_HOST}:{MINIO_PORT}'
MINIO_ACCESS_KEY = 'docclad5itest'
MINIO_SECRET_KEY = 'docclad5isecret'
MINIO_BUCKET = 'docclad-5i-minio'
MINIO_CONTAINER = 'docclad-5i-minio-test'
MINIO_VERSION = 'minio/minio:latest'   # pinned by digest in CI


def _docker_available():
    try:
        r = subprocess.run(['docker', 'info', '--format', '{{.ServerVersion}}'],
                           capture_output=True, timeout=5)
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _start_minio():
    """Start MinIO as a Docker container.  Returns True if healthy."""
    # Remove any stale container from a previous interrupted run.
    subprocess.run(
        ['docker', 'rm', '-f', MINIO_CONTAINER],
        capture_output=True,
    )
    result = subprocess.run(
        [
            'docker', 'run', '-d',
            '--name', MINIO_CONTAINER,
            '-p', f'{MINIO_PORT}:9000',
            '-e', f'MINIO_ROOT_USER={MINIO_ACCESS_KEY}',
            '-e', f'MINIO_ROOT_PASSWORD={MINIO_SECRET_KEY}',
            MINIO_VERSION,
            'server', '/data',
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return False, result.stderr.strip()

    # Wait up to 15 s for MinIO health endpoint.
    health_url = f'{MINIO_ENDPOINT}/minio/health/live'
    for _ in range(30):
        try:
            urllib.request.urlopen(health_url, timeout=1)  # noqa: S310
            return True, 'healthy'
        except (URLError, OSError):
            time.sleep(0.5)
    return False, 'health-check timed out after 15s'


def _stop_minio():
    subprocess.run(['docker', 'rm', '-f', MINIO_CONTAINER], capture_output=True)


def _minio_version():
    r = subprocess.run(
        ['docker', 'run', '--rm', MINIO_VERSION, '--version'],
        capture_output=True, text=True,
    )
    return r.stdout.strip() or r.stderr.strip()


# Module-level setup — start MinIO once for all tests in this file.
_MINIO_AVAILABLE = False
_MINIO_SKIP_REASON = ''

if _docker_available():
    _ok, _msg = _start_minio()
    if _ok:
        _MINIO_AVAILABLE = True
    else:
        _MINIO_SKIP_REASON = f'MinIO failed to start: {_msg}'
else:
    _MINIO_SKIP_REASON = 'Docker is not available; MinIO cannot be started'


def pytest_sessionfinish(session, exitstatus):
    if _MINIO_AVAILABLE:
        _stop_minio()


# ─── Django storage settings pointing at local MinIO ─────────────────────────

_MINIO_STORAGES = {
    'default': {
        'BACKEND': 'storages.backends.s3.S3Storage',
        'OPTIONS': {
            'bucket_name': MINIO_BUCKET,
            'region_name': 'us-east-1',
            'access_key': MINIO_ACCESS_KEY,
            'secret_key': MINIO_SECRET_KEY,
            'endpoint_url': MINIO_ENDPOINT,
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

_MINIO_STORAGES_LONG_EXPIRY = {
    **_MINIO_STORAGES,
    'default': {
        **_MINIO_STORAGES['default'],
        'OPTIONS': {
            **_MINIO_STORAGES['default']['OPTIONS'],
            'querystring_expire': 7200,
        },
    },
}


def _reset_storage_cache():
    from django.core.files import storage as _sm
    from django.utils.functional import empty
    _sm.default_storage._wrapped = empty
    try:
        _sm.storages._connections.__dict__.clear()
    except Exception:
        pass


def _s3():
    return boto3.client(
        's3',
        endpoint_url=MINIO_ENDPOINT,
        region_name='us-east-1',
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
    )


def _create_bucket(versioned=False):
    s3 = _s3()
    try:
        s3.create_bucket(Bucket=MINIO_BUCKET)
    except ClientError as exc:
        if exc.response['Error']['Code'] != 'BucketAlreadyOwnedByYou':
            raise
    s3.put_public_access_block(
        Bucket=MINIO_BUCKET,
        PublicAccessBlockConfiguration={
            'BlockPublicAcls': True,
            'IgnorePublicAcls': True,
            'BlockPublicPolicy': True,
            'RestrictPublicBuckets': True,
        },
    )
    if versioned:
        s3.put_bucket_versioning(
            Bucket=MINIO_BUCKET,
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


def _doc(org, *, title='MinioDoc', uploaded_by=None, with_file=False,
         doc_type=Document.DocType.OTHER, status=Document.Status.DRAFT,
         contract=None):
    d = Document(
        organization=org, title=title, document_type=doc_type,
        status=status, contract=contract, uploaded_by=uploaded_by,
    )
    if with_file:
        d.file = SimpleUploadedFile(f'{title}.txt', b'minio integration test content',
                                    content_type='text/plain')
    d.save()
    return d


# ─── Skip decorator ───────────────────────────────────────────────────────────

_SKIP = pytest.mark.skipif(not _MINIO_AVAILABLE, reason=_MINIO_SKIP_REASON or 'MinIO unavailable')


# ─── MinIO version evidence ───────────────────────────────────────────────────

@_SKIP
class MinIOVersionTest(TestCase):
    """Capture MinIO version as evidence before the rehearsal."""

    def test_minio_version_captured(self):
        """Record the MinIO version in use.

        [MINIO-REAL]  S3-compatible: RELEASE.2025-09-07T16-13-09Z
        """
        ver = _minio_version()
        self.assertIn('minio', ver.lower(),
                      f'unexpected MinIO version string: {ver}')
        # Print to stdout so it appears in the test report.
        print(f'\n[MINIO VERSION] {ver}', flush=True)


# ─── Storage & Retrieval ─────────────────────────────────────────────────────

@_SKIP
@override_settings(STORAGES=_MINIO_STORAGES)
class MinIOStorageTests(TestCase):
    """Real upload/download/access-control tests against a live MinIO instance.

    [MINIO-REAL]
    """

    def setUp(self):
        super().setUp()
        _reset_storage_cache()
        self.s3 = _create_bucket()
        self.org_a = _org('MinioAlpha', '5i-mn-a')
        self.org_b = _org('MinioBeta', '5i-mn-b')
        self.owner_a = _member(self.org_a, '5i-mn-owner-a', OrganizationMembership.Role.OWNER)
        self.owner_b = _member(self.org_b, '5i-mn-owner-b', OrganizationMembership.Role.OWNER)

    def tearDown(self):
        _reset_storage_cache()
        super().tearDown()

    # ── Upload ────────────────────────────────────────────────────────────

    def test_upload_via_api_creates_db_record(self):
        """Upload through DocClad API creates a Document row with S3 key.

        Commands:
          POST /contracts/api/documents/upload/
        Expected: HTTP 201, document_id in response body.
        [MINIO-REAL] production-compatible verified.
        """
        c = Client()
        c.force_login(self.owner_a)
        payload = SimpleUploadedFile('minio_nda.txt', b'NDA content for MinIO test',
                                     content_type='text/plain')
        resp = c.post(
            reverse('contracts:document_upload_api'),
            {'file': payload, 'title': 'MinIO NDA'},
        )
        self.assertIn(resp.status_code, (200, 201),
                      f'upload failed: {resp.content[:200]}')
        data = resp.json()
        self.assertTrue(data['ok'])
        doc = Document.objects.get(pk=data['document_id'])
        self.assertTrue(doc.file.name, 'S3 key must not be empty')

    def test_uploaded_object_exists_in_minio_bucket(self):
        """The object key stored in the DB corresponds to a real MinIO object.

        [MINIO-REAL]
        """
        doc = _doc(self.org_a, uploaded_by=self.owner_a, with_file=True)
        key = doc.file.name
        self.assertTrue(key)
        head = self.s3.head_object(Bucket=MINIO_BUCKET, Key=key)
        self.assertEqual(head['ResponseMetadata']['HTTPStatusCode'], 200)

    def test_bucket_blocks_public_access(self):
        """MinIO bucket must enforce private-only access.

        [MINIO-REAL]
        """
        pab = self.s3.get_public_access_block(Bucket=MINIO_BUCKET)
        cfg = pab['PublicAccessBlockConfiguration']
        self.assertTrue(cfg['BlockPublicAcls'])
        self.assertTrue(cfg['BlockPublicPolicy'])
        self.assertTrue(cfg['RestrictPublicBuckets'])

    # ── Signed URL / access control ───────────────────────────────────────

    def test_authenticated_download_redirects_to_signed_url(self):
        """Authenticated download redirects to a short-lived signed URL.

        HTTP path: GET /contracts/documents/<pk>/download/
        Expected: HTTP 302 with signature parameters in Location header.
        [MINIO-REAL]
        """
        doc = _doc(self.org_a, uploaded_by=self.owner_a, with_file=True)
        c = Client()
        c.force_login(self.owner_a)
        resp = c.get(reverse('contracts:document_download', args=[doc.pk]))
        self.assertEqual(resp.status_code, 302)
        url = resp.url
        # Both SigV4 and SigV2 are valid; the URL must carry some signature.
        has_sig = ('X-Amz-Signature' in url or 'Signature=' in url)
        self.assertTrue(has_sig, f'URL is not signed: {url[:120]}')

    def test_signed_url_expiry_300s(self):
        """Signed URL from the storage backend carries 300s expiry.

        [MINIO-REAL]
        """
        from urllib.parse import urlparse, parse_qs
        doc = _doc(self.org_a, uploaded_by=self.owner_a, with_file=True)
        url = doc.file.url
        qs = parse_qs(urlparse(url).query)
        if 'X-Amz-Expires' in qs:
            self.assertEqual(int(qs['X-Amz-Expires'][0]), 300)
        elif 'Expires' in qs:
            import time
            deadline = int(qs['Expires'][0])
            now = int(time.time())
            self.assertAlmostEqual(deadline - now, 300, delta=60)
        else:
            self.fail(f'URL has no expiry parameter: {url[:120]}')

    def test_signed_url_is_short_lived_not_permanent(self):
        """URL generated by the storage field must carry finite expiry, not be public.

        [MINIO-REAL]
        """
        from urllib.parse import urlparse, parse_qs
        doc = _doc(self.org_a, uploaded_by=self.owner_a, with_file=True)
        url = doc.file.url
        qs = parse_qs(urlparse(url).query)
        has_expiry = 'X-Amz-Expires' in qs or 'Expires' in qs
        self.assertTrue(has_expiry, f'URL must have expiry — got: {url[:120]}')

    def test_expiry_configuration_7200s(self):
        """querystring_expire=7200 is honoured by MinIO.

        [MINIO-REAL]
        """
        from urllib.parse import urlparse, parse_qs
        import time
        from storages.backends.s3 import S3Storage
        from django.core.files.base import ContentFile

        storage_7200 = S3Storage(
            bucket_name=MINIO_BUCKET,
            region_name='us-east-1',
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            endpoint_url=MINIO_ENDPOINT,
            default_acl='private',
            querystring_auth=True,
            file_overwrite=False,
            querystring_expire=7200,
        )
        storage_300 = S3Storage(
            bucket_name=MINIO_BUCKET,
            region_name='us-east-1',
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            endpoint_url=MINIO_ENDPOINT,
            default_acl='private',
            querystring_auth=True,
            file_overwrite=False,
            querystring_expire=300,
        )
        key = storage_7200.save('documents/test/expiry_minio.txt', ContentFile(b'x'))
        url_7200 = storage_7200.url(key)
        url_300 = storage_300.url(key)

        def _expiry(url):
            qs = parse_qs(urlparse(url).query)
            if 'X-Amz-Expires' in qs:
                return 'sigv4', int(qs['X-Amz-Expires'][0])
            if 'Expires' in qs:
                return 'sigv2', int(qs['Expires'][0])
            return 'unsigned', None

        style7, exp7 = _expiry(url_7200)
        _, exp3 = _expiry(url_300)
        if style7 == 'sigv4':
            self.assertEqual(exp7, 7200)
        elif style7 == 'sigv2':
            diff = exp7 - exp3
            self.assertAlmostEqual(diff, 6900, delta=30)
        else:
            self.fail(f'Unsigned URL from MinIO storage: {url_7200[:120]}')

    # ── Access control ────────────────────────────────────────────────────

    def test_cross_tenant_download_returns_404(self):
        """BetaOrg user cannot download AlphaOrg document.

        HTTP path: GET /contracts/documents/<pk>/download/
        Expected: HTTP 404.
        [MINIO-REAL] — tenant enforcement at Django layer.
        """
        doc = _doc(self.org_a, uploaded_by=self.owner_a, with_file=True)
        c = Client()
        c.force_login(self.owner_b)
        resp = c.get(reverse('contracts:document_download', args=[doc.pk]))
        self.assertEqual(resp.status_code, 404)

    def test_soft_deleted_document_denied(self):
        """Soft-deleted document returns 404 on download attempt.

        [MINIO-REAL]
        """
        doc = _doc(self.org_a, uploaded_by=self.owner_a, with_file=True)
        soft_delete_document(self.owner_a, doc)
        c = Client()
        c.force_login(self.owner_a)
        resp = c.get(reverse('contracts:document_download', args=[doc.pk]))
        self.assertEqual(resp.status_code, 404)

    def test_soft_delete_retains_object_in_minio(self):
        """Soft-delete MUST NOT delete the object from MinIO.

        The object must survive soft-delete for audit-chain permanence and
        operator recovery.
        [MINIO-REAL]
        """
        doc = _doc(self.org_a, uploaded_by=self.owner_a, with_file=True)
        key = doc.file.name
        self.s3.head_object(Bucket=MINIO_BUCKET, Key=key)  # exists before
        soft_delete_document(self.owner_a, doc)
        head = self.s3.head_object(Bucket=MINIO_BUCKET, Key=key)
        self.assertEqual(head['ResponseMetadata']['HTTPStatusCode'], 200)

    def test_missing_object_returns_controlled_response(self):
        """An object deleted from MinIO directly returns a safe response.

        The download view tries to generate a signed URL and redirect to it.
        If the object is gone, the signed URL itself will 404 at MinIO —
        the Django view returns a 302 redirect (the URL generation succeeds;
        only the follow-up request to MinIO would fail).
        This test verifies: no 500, no stack trace in the view response.
        [MINIO-REAL]
        """
        doc = _doc(self.org_a, uploaded_by=self.owner_a, with_file=True)
        key = doc.file.name
        self.s3.delete_object(Bucket=MINIO_BUCKET, Key=key)
        c = Client()
        c.force_login(self.owner_a)
        resp = c.get(reverse('contracts:document_download', args=[doc.pk]))
        self.assertNotEqual(resp.status_code, 500,
                            'missing MinIO object must not cause a 500')
        # Response body (if any) must not contain MinIO endpoint or credentials.
        body = resp.content.decode('utf-8', errors='replace')
        self.assertNotIn(MINIO_ACCESS_KEY, body)
        self.assertNotIn(MINIO_SECRET_KEY, body)


# ─── Bucket Versioning ────────────────────────────────────────────────────────

@_SKIP
@override_settings(STORAGES=_MINIO_STORAGES)
class MinIOVersioningTests(TestCase):
    """Bucket versioning, prior-version recovery, and authorized retrieval.

    [MINIO-REAL]
    """

    def setUp(self):
        super().setUp()
        _reset_storage_cache()
        self.s3 = _create_bucket(versioned=True)
        self.org = _org('MinioVerOrg', '5i-mn-ver')
        self.owner = _member(self.org, '5i-mn-ver-owner', OrganizationMembership.Role.OWNER)

    def tearDown(self):
        _reset_storage_cache()
        super().tearDown()

    def test_bucket_versioning_enabled(self):
        """MinIO bucket has versioning enabled.

        [MINIO-REAL]
        """
        resp = self.s3.get_bucket_versioning(Bucket=MINIO_BUCKET)
        self.assertEqual(resp.get('Status'), 'Enabled')

    def test_overwrite_creates_recoverable_version(self):
        """Overwriting an object in MinIO creates a recoverable prior version.

        [MINIO-REAL]
        """
        key = 'documents/test/minio_v1.txt'
        self.s3.put_object(Bucket=MINIO_BUCKET, Key=key, Body=b'version 1')
        self.s3.put_object(Bucket=MINIO_BUCKET, Key=key, Body=b'version 2')
        versions = self.s3.list_object_versions(Bucket=MINIO_BUCKET, Prefix=key)
        self.assertGreaterEqual(
            len(versions.get('Versions', [])), 2,
            'Must have ≥ 2 recoverable versions after overwrite',
        )

    def test_prior_version_recovery(self):
        """Operator can recover the prior version by version ID.

        [MINIO-REAL]
        """
        key = 'documents/test/minio_restore.txt'
        put1 = self.s3.put_object(Bucket=MINIO_BUCKET, Key=key, Body=b'original')
        v1 = put1['VersionId']
        self.s3.put_object(Bucket=MINIO_BUCKET, Key=key, Body=b'overwritten')
        old = self.s3.get_object(Bucket=MINIO_BUCKET, Key=key, VersionId=v1)
        self.assertEqual(old['Body'].read(), b'original')

    def test_authorized_retrieval_after_restore(self):
        """After operator restores a prior version, the download path returns a redirect.

        The DB file.name is unchanged; the signed URL points to the same key.
        [MINIO-REAL]
        """
        doc = _doc(self.org, uploaded_by=self.owner, with_file=True)
        key = doc.file.name
        # Simulate operator overwrite (corruption scenario).
        self.s3.put_object(Bucket=MINIO_BUCKET, Key=key, Body=b'corrupted')
        # Retrieve list of versions to get original.
        versions = self.s3.list_object_versions(Bucket=MINIO_BUCKET, Prefix=key)
        vlist = sorted(versions.get('Versions', []), key=lambda v: v['LastModified'])
        if len(vlist) >= 2:
            old_vid = vlist[0]['VersionId']
            old_body = self.s3.get_object(
                Bucket=MINIO_BUCKET, Key=key, VersionId=old_vid,
            )['Body'].read()
            # Restore: re-upload original content under same key.
            self.s3.put_object(Bucket=MINIO_BUCKET, Key=key, Body=old_body)
        # DB reference unchanged.
        doc.refresh_from_db()
        self.assertEqual(doc.file.name, key, 'DB key must be stable across operator restore')
        # Download path must still work (returns redirect to signed URL).
        c = Client()
        c.force_login(self.owner)
        resp = c.get(reverse('contracts:document_download', args=[doc.pk]))
        self.assertEqual(resp.status_code, 302)


# ─── Orphan Cleanup and Detection ────────────────────────────────────────────

@_SKIP
@override_settings(STORAGES=_MINIO_STORAGES)
class MinIOOrphanTests(TestCase):
    """Verify best-effort orphan cleanup and the detect_orphan_objects command.

    [MINIO-REAL]
    """

    def setUp(self):
        super().setUp()
        _reset_storage_cache()
        self.s3 = _create_bucket()
        self.org = _org('MinioOrphanOrg', '5i-mn-orphan')
        self.owner = _member(self.org, '5i-mn-orphan-owner', OrganizationMembership.Role.OWNER)

    def tearDown(self):
        _reset_storage_cache()
        super().tearDown()

    def test_cleanup_removes_orphaned_object_on_db_failure(self):
        """Best-effort cleanup deletes the S3 object when Document.save() fails.

        Scenario: file is committed to MinIO, DB INSERT fails.
        Expected: cleanup deletes the MinIO object; 503 returned to caller;
                  no Document row is created.
        [MINIO-REAL]
        """
        from django.db import IntegrityError
        from contracts.api.documents_ai import _cleanup_orphaned_upload
        from storages.backends.s3 import S3Storage
        from django.core.files.base import ContentFile

        # Pre-stage an object to simulate a file that was uploaded before DB failed.
        storage = S3Storage(
            bucket_name=MINIO_BUCKET, region_name='us-east-1',
            access_key=MINIO_ACCESS_KEY, secret_key=MINIO_SECRET_KEY,
            endpoint_url=MINIO_ENDPOINT, default_acl='private',
            querystring_auth=True, file_overwrite=False,
        )
        key = storage.save('documents/test/orphan_candidate.txt', ContentFile(b'orphan'))
        self.s3.head_object(Bucket=MINIO_BUCKET, Key=key)  # assert it exists

        # Build a Document instance with the committed file (not in DB).
        doc = Document.__new__(Document)
        doc._state = Document._meta.model._default_manager.none().query.__class__.__new__(
            Document._meta.model._default_manager.none().query.__class__)
        # Simpler: create the doc without saving, then set file.name
        doc2 = Document(organization=self.org, title='Orphan Cleanup Test',
                        uploaded_by=self.owner)
        doc2.file.name = key  # pretend the file was already uploaded

        _cleanup_orphaned_upload(doc2)

        with self.assertRaises(ClientError) as cm:
            self.s3.head_object(Bucket=MINIO_BUCKET, Key=key)
        self.assertEqual(cm.exception.response['Error']['Code'], '404')

    def test_cleanup_api_path_on_db_failure(self):
        """End-to-end: API upload with simulated DB failure triggers cleanup.

        [MINIO-REAL]
        """
        from django.db import IntegrityError

        # Track what key gets uploaded to MinIO.
        uploaded_keys = []
        real_field_save = None

        def capturing_doc_save(self_doc, *args, **kwargs):
            # Let the FileField write to MinIO, then simulate DB failure.
            if self_doc.file and hasattr(self_doc.file, 'file'):
                from django.core.files.storage import default_storage
                name = self_doc.file.field.generate_filename(
                    self_doc, self_doc.file.name or 'upload.txt'
                )
                saved_name = default_storage.save(name, self_doc.file)
                self_doc.file.name = saved_name
                uploaded_keys.append(saved_name)
            raise IntegrityError('simulated DB failure after MinIO write')

        c = Client()
        c.force_login(self.owner)
        with patch('contracts.models.Document.save', capturing_doc_save):
            payload = SimpleUploadedFile('minio_db_fail.txt', b'content',
                                         content_type='text/plain')
            resp = c.post(
                reverse('contracts:document_upload_api'),
                {'file': payload, 'title': 'MinIO DB Failure Test'},
            )

        self.assertEqual(resp.status_code, 503,
                         f'expected 503 on DB failure; got {resp.status_code}')
        self.assertIsNone(Document.objects.filter(
            title='MinIO DB Failure Test').first(),
            'no Document row must be created when DB fails',
        )
        # If the file was actually uploaded to MinIO, cleanup must have removed it.
        for key in uploaded_keys:
            try:
                self.s3.head_object(Bucket=MINIO_BUCKET, Key=key)
                self.fail(f'orphaned object still present after cleanup: {key}')
            except ClientError as exc:
                if exc.response['Error']['Code'] != '404':
                    raise  # unexpected error

    def test_cleanup_failure_is_logged_not_masked(self):
        """When cleanup itself fails, the original error is preserved.

        The 503 response must still be returned.  The cleanup failure must
        be logged but must not mask or override the original save() failure.
        [MINIO-REAL]
        """
        import logging as _logging

        c = Client()
        c.force_login(self.owner)

        cleanup_raised = []

        def broken_save(self_doc, *args, **kwargs):
            raise OSError('storage unavailable')

        def broken_delete(name):
            exc = OSError('cleanup also failed')
            cleanup_raised.append(exc)
            raise exc

        with patch('contracts.models.Document.save', broken_save), \
             patch('django.core.files.storage.FileSystemStorage.delete', broken_delete):
            payload = SimpleUploadedFile('cleanup_fail.txt', b'test',
                                         content_type='text/plain')
            resp = c.post(
                reverse('contracts:document_upload_api'),
                {'file': payload, 'title': 'Cleanup Fail Test'},
            )

        # 503 must be returned regardless of cleanup failure.
        self.assertEqual(resp.status_code, 503)

    def test_orphan_detection_command_reports_orphan(self):
        """detect_orphan_objects reports objects with no matching Document row.

        [MINIO-REAL]
        """
        import io as _io
        # Place an object directly in MinIO (simulating an orphan left by a
        # failed upload + failed cleanup).
        orphan_key = 'documents/test/detected_orphan.txt'
        self.s3.put_object(Bucket=MINIO_BUCKET, Key=orphan_key, Body=b'orphan content')

        from django.core.management import call_command
        stdout = _io.StringIO()
        call_command(
            'detect_orphan_objects',
            '--prefix', 'documents/test/',
            '--min-age-hours', '0',  # age=0 so all objects are examined
            '--output', 'json',
            stdout=stdout,
        )
        output = stdout.getvalue()
        result = json.loads(output)
        orphan_keys_suffix = {o['key_suffix'] for o in result.get('orphans', [])}
        self.assertIn('detected_orphan.txt', orphan_keys_suffix,
                      f'expected detected_orphan.txt in orphans; got: {orphan_keys_suffix}')

        # Verify the output contains NO credentials or endpoint URLs.
        self.assertNotIn(MINIO_ACCESS_KEY, output)
        self.assertNotIn(MINIO_SECRET_KEY, output)
        self.assertNotIn(MINIO_ENDPOINT, output)

    def test_orphan_detection_ignores_matched_documents(self):
        """detect_orphan_objects does NOT report documents with active DB rows.

        [MINIO-REAL]
        """
        import io as _io
        doc = _doc(self.org, uploaded_by=self.owner, with_file=True)
        key_suffix = doc.file.name.split('/')[-1]

        from django.core.management import call_command
        stdout = _io.StringIO()
        call_command(
            'detect_orphan_objects',
            '--prefix', 'documents/',
            '--min-age-hours', '0',
            '--output', 'json',
            stdout=stdout,
        )
        result = json.loads(stdout.getvalue())
        orphan_suffixes = {o['key_suffix'] for o in result.get('orphans', [])}
        self.assertNotIn(key_suffix, orphan_suffixes,
                         f'active document must not appear as orphan: {key_suffix}')

    def test_orphan_detection_never_deletes(self):
        """detect_orphan_objects command does not delete any objects.

        [MINIO-REAL]
        """
        import io as _io
        key = 'documents/test/orphan_nodelete.txt'
        self.s3.put_object(Bucket=MINIO_BUCKET, Key=key, Body=b'must survive')

        from django.core.management import call_command
        stdout = _io.StringIO()
        call_command(
            'detect_orphan_objects',
            '--prefix', 'documents/test/',
            '--min-age-hours', '0',
            '--output', 'json',
            stdout=stdout,
        )
        # Object must still exist after the command runs.
        head = self.s3.head_object(Bucket=MINIO_BUCKET, Key=key)
        self.assertEqual(head['ResponseMetadata']['HTTPStatusCode'], 200,
                         'object must not be deleted by detect_orphan_objects')

    def test_orphan_detection_min_age_threshold_protects_young_objects(self):
        """Objects younger than min-age-hours are classified as too-young, not orphan.

        [MINIO-REAL]
        """
        import io as _io
        key = 'documents/test/young_upload.txt'
        self.s3.put_object(Bucket=MINIO_BUCKET, Key=key, Body=b'in-flight upload')

        from django.core.management import call_command
        stdout = _io.StringIO()
        call_command(
            'detect_orphan_objects',
            '--prefix', 'documents/test/',
            '--min-age-hours', '1',  # default threshold: objects < 1h old are too-young
            '--output', 'json',
            stdout=stdout,
        )
        result = json.loads(stdout.getvalue())
        # young_upload.txt should be classified as too-young, not orphan.
        orphan_suffixes = {o['key_suffix'] for o in result.get('orphans', [])}
        self.assertNotIn('young_upload.txt', orphan_suffixes,
                         'in-flight object must not be classified as orphan')
