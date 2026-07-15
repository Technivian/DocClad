"""Phase 4A — durable storage startup guards + authenticated document download."""
from __future__ import annotations

import os
import subprocess
import sys

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from contracts.models import AuditLog, Contract, Document, Organization, OrganizationMembership

User = get_user_model()
PW = 'StrongPw!123'
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _org(name, slug):
    return Organization.objects.create(name=name, slug=slug)


def _member(org, username, role=OrganizationMembership.Role.OWNER):
    u = User.objects.create_user(username=username, password=PW, email=f'{username}@ex.com')
    OrganizationMembership.objects.create(user=u, organization=org, role=role, is_active=True)
    return u


def _document(org, title='Doc', with_file=True):
    doc = Document(organization=org, title=title)
    if with_file:
        doc.file = SimpleUploadedFile(f'{title}.txt', b'hello world', content_type='text/plain')
    doc.save()
    return doc


class DocumentDownloadTests(TestCase):
    def setUp(self):
        self.org_a = _org('Tenant A', 'dl-a')
        self.org_b = _org('Tenant B', 'dl-b')
        self.user_a = _member(self.org_a, 'alice')
        self.user_b = _member(self.org_b, 'bob')
        self.doc_a = _document(self.org_a, 'AlphaDoc')

    def test_unauthenticated_is_redirected_to_login(self):
        resp = Client().get(reverse('contracts:document_download', args=[self.doc_a.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login', resp.url)

    def test_authorized_download_redirects_to_storage_url(self):
        c = Client()
        c.force_login(self.user_a)
        resp = c.get(reverse('contracts:document_download', args=[self.doc_a.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(self.doc_a.file.url, resp.url)

    def test_download_is_audited_with_correct_attribution(self):
        c = Client()
        c.force_login(self.user_a)
        c.get(reverse('contracts:document_download', args=[self.doc_a.pk]))
        row = AuditLog.objects.filter(event_type='document.downloaded', object_id=self.doc_a.pk).first()
        self.assertIsNotNone(row)
        self.assertEqual(row.organization_id, self.org_a.id)
        self.assertEqual(row.user_id, self.user_a.id)

    def test_cross_tenant_download_blocked_and_audited(self):
        c = Client()
        c.force_login(self.user_b)  # tenant B requesting tenant A's doc
        resp = c.get(reverse('contracts:document_download', args=[self.doc_a.pk]))
        self.assertEqual(resp.status_code, 404)
        blocked = AuditLog.objects.filter(event_type='document.access_blocked').first()
        self.assertIsNotNone(blocked)
        self.assertEqual(blocked.organization_id, self.org_b.id)  # actor's org, not target's
        self.assertEqual(blocked.outcome, AuditLog.Outcome.BLOCKED)

    def test_missing_file_fails_safe(self):
        doc = _document(self.org_a, 'NoFile', with_file=False)
        c = Client()
        c.force_login(self.user_a)
        resp = c.get(reverse('contracts:document_download', args=[doc.pk]))
        self.assertEqual(resp.status_code, 404)


class ProductionStorageGuardTests(TestCase):
    """Production startup must reject ephemeral/incomplete storage config."""

    def _run_setup(self, extra_env):
        env = {
            'PATH': os.environ.get('PATH', ''),
            'DJANGO_SETTINGS_MODULE': 'config.settings_production',
            'DJANGO_DEBUG': 'false',
            'DJANGO_SECRET_KEY': 'x' * 50,
            'ALLOWED_HOSTS': 'example.com',
            'CSRF_TRUSTED_ORIGINS': 'https://example.com',
            'DEFAULT_FROM_EMAIL': 'ops@example.com',
            'APP_BASE_URL': 'https://app.example.com',
            'OPERATOR_ALERT_EMAIL': 'security@example.com',
            'ALLOW_SQLITE_IN_PRODUCTION': 'true',  # isolate the storage check
            'DATABASE_URL': 'sqlite:///tmp/guardtest.sqlite3',
        }
        env.update(extra_env)
        return subprocess.run(
            [sys.executable, '-c', 'import django; django.setup()'],
            cwd=_REPO, env=env, capture_output=True, text=True,
        )

    def test_production_rejects_filesystem_storage(self):
        result = self._run_setup({'MEDIA_STORAGE_BACKEND': 'filesystem'})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('durable object storage', result.stderr)

    def test_production_rejects_s3_without_bucket(self):
        result = self._run_setup({'MEDIA_STORAGE_BACKEND': 's3', 'AWS_STORAGE_BUCKET_NAME': ''})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('AWS_STORAGE_BUCKET_NAME', result.stderr)

    def test_production_accepts_s3_with_bucket(self):
        result = self._run_setup({
            'MEDIA_STORAGE_BACKEND': 's3', 'AWS_STORAGE_BUCKET_NAME': 'clmone-test-bucket',
        })
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_production_rejects_ephemeral_opt_in(self):
        result = self._run_setup({
            'MEDIA_STORAGE_BACKEND': 'filesystem',
            'ALLOW_EPHEMERAL_MEDIA_IN_PRODUCTION': 'true',
        })
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('durable object storage', result.stderr)

    def test_secret_values_not_leaked_in_error(self):
        result = self._run_setup({
            'MEDIA_STORAGE_BACKEND': 's3', 'AWS_STORAGE_BUCKET_NAME': '',
            'AWS_SECRET_ACCESS_KEY': 'super-secret-value-123',
        })
        self.assertNotIn('super-secret-value-123', result.stderr)
