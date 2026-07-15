"""Sub-block D1: local development and test runs must never silently touch a
shared/remote database.

Uses subprocess.run with a tightly controlled env dict (not the real ambient
environment, so this never risks reading the real .env / real DATABASE_URL)
to exercise config/settings_base.py's test-command guard and
contracts/apps.py's deployed-platform guard exactly as a real invocation of
manage.py would trigger them. Follows the same pattern as
tests/test_document_storage_download.py::ProductionStorageGuardTests.
"""
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

from config.db_safety import is_local_database_host, is_running_on_deployed_platform

_REPO = Path(__file__).resolve().parent.parent

# A syntactically valid but non-resolvable host — using this (never a real
# credential) means even a bug in the guard could not reach a real database:
# DNS resolution for this host fails, so any accidental connection attempt
# would error out immediately rather than reaching a live server.
_FAKE_REMOTE_HOST = 'db.this-host-does-not-exist.invalid'


class DatabaseHostClassificationTests(SimpleTestCase):
    def test_sqlite_engine_is_always_local(self):
        self.assertTrue(is_local_database_host({'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}))

    def test_localhost_postgres_is_local(self):
        for host in ('localhost', '127.0.0.1', '::1', ''):
            with self.subTest(host=host):
                self.assertTrue(is_local_database_host({'ENGINE': 'django.db.backends.postgresql', 'HOST': host}))

    def test_remote_host_is_not_local(self):
        self.assertFalse(is_local_database_host({
            'ENGINE': 'django.db.backends.postgresql',
            'HOST': 'aws-0-eu-west-1.pooler.supabase.com',
        }))

    def test_no_deployed_platform_markers_in_test_process(self):
        # This test itself must be running on a developer/CI machine, not Render.
        self.assertFalse(is_running_on_deployed_platform())


class ManageDotPyDatabaseGuardTests(SimpleTestCase):
    """Exercises the actual guard via subprocess, exactly as manage.py would."""

    def _base_env(self):
        return {
            'PATH': __import__('os').environ.get('PATH', ''),
            'DJANGO_SETTINGS_MODULE': 'config.settings',
            'DJANGO_SECRET_KEY': 'x' * 50,
            'ALLOWED_HOSTS': '127.0.0.1,localhost',
            'APP_BASE_URL': 'https://app.example.com',
            'OPERATOR_ALERT_EMAIL': 'security@example.com',
            'MEDIA_STORAGE_BACKEND': 's3',
            'AWS_STORAGE_BUCKET_NAME': 'clmone-test-bucket',
        }

    def _run(self, code, extra_env):
        env = self._base_env()
        env.update(extra_env)
        return subprocess.run(
            [sys.executable, '-c', code],
            cwd=_REPO, env=env, capture_output=True, text=True, timeout=30,
        )

    def test_development_with_remote_database_url_refuses_to_start(self):
        result = self._run(
            'import django; django.setup()',
            {
                'DJANGO_ENV': 'development',
                'DATABASE_URL': f'postgresql://user:pass@{_FAKE_REMOTE_HOST}:5432/postgres',
            },
        )
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('REFUSING TO START', result.stdout)
        self.assertIn(_FAKE_REMOTE_HOST, result.stdout)

    def test_production_env_with_remote_database_url_also_refuses_to_start(self):
        # This is the actual local misconfiguration this guard exists for:
        # this repo's own .env sets DJANGO_ENV=production (mirroring the real
        # deployment's config) alongside a real DATABASE_URL. DJANGO_ENV alone
        # must not be trusted to distinguish "the real deployment" from "a
        # local checkout with production-flavored settings".
        result = self._run(
            'import django; django.setup()',
            {
                'DJANGO_ENV': 'production',
                'DATABASE_URL': f'postgresql://user:pass@{_FAKE_REMOTE_HOST}:5432/postgres',
                'CSRF_TRUSTED_ORIGINS': 'https://example.com',
                'DEFAULT_FROM_EMAIL': 'ops@example.com',
            },
        )
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('REFUSING TO START', result.stdout)

    def test_explicit_opt_in_allows_remote_database_url(self):
        result = self._run(
            'import django; django.setup()',
            {
                'DJANGO_ENV': 'development',
                'DATABASE_URL': f'postgresql://user:pass@{_FAKE_REMOTE_HOST}:5432/postgres',
                'ALLOW_REMOTE_DATABASE': 'true',
            },
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('explicitly allowed', result.stdout)

    def test_deployed_platform_marker_allows_remote_database_url(self):
        result = self._run(
            'import django; django.setup()',
            {
                'DJANGO_ENV': 'production',
                'DATABASE_URL': f'postgresql://user:pass@{_FAKE_REMOTE_HOST}:5432/postgres',
                'CSRF_TRUSTED_ORIGINS': 'https://example.com',
                'DEFAULT_FROM_EMAIL': 'ops@example.com',
                'RENDER': 'true',
            },
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('deployed platform', result.stdout)

    def test_local_sqlite_database_url_is_always_allowed(self):
        result = self._run(
            'import django; django.setup()',
            {'DJANGO_ENV': 'development', 'DATABASE_URL': 'sqlite:///:memory:'},
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('[CLM One] Database:', result.stdout)
        self.assertIn('(local', result.stdout)

    def test_empty_database_url_defaults_to_local_sqlite_and_is_allowed(self):
        # An explicitly empty DATABASE_URL (distinct from an absent one, which
        # would let the real repo .env's DATABASE_URL leak into this
        # subprocess's environment via _load_dotenv's setdefault) must
        # resolve to the local sqlite default, per _database_config_from_env.
        result = self._run(
            'import django; django.setup()',
            {'DJANGO_ENV': 'development', 'DATABASE_URL': ''},
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('(local', result.stdout)

    def test_manage_dot_py_test_forces_sqlite_even_with_remote_database_url(self):
        # Simulates `manage.py test` specifically: sys.argv[1] == 'test' must
        # force an in-memory sqlite database regardless of DATABASE_URL,
        # regardless of DJANGO_ENV, and regardless of ALLOW_REMOTE_DATABASE.
        code = (
            'import sys; sys.argv = ["manage.py", "test"]\n'
            'import django; django.setup()\n'
            'from django.conf import settings\n'
            'print("ENGINE=" + settings.DATABASES["default"]["ENGINE"])\n'
            'print("NAME=" + str(settings.DATABASES["default"]["NAME"]))\n'
        )
        result = self._run(
            code,
            {
                'DJANGO_ENV': 'production',
                'DATABASE_URL': f'postgresql://user:pass@{_FAKE_REMOTE_HOST}:5432/postgres',
                'CSRF_TRUSTED_ORIGINS': 'https://example.com',
                'DEFAULT_FROM_EMAIL': 'ops@example.com',
                'ALLOW_REMOTE_DATABASE': 'true',  # even with this set, test runs must stay local
            },
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('ENGINE=django.db.backends.sqlite3', result.stdout)
        self.assertIn('NAME=:memory:', result.stdout)

    def test_secret_password_not_leaked_in_refusal_message(self):
        result = self._run(
            'import django; django.setup()',
            {
                'DJANGO_ENV': 'development',
                'DATABASE_URL': f'postgresql://someuser:super-secret-password-123@{_FAKE_REMOTE_HOST}:5432/postgres',
            },
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('super-secret-password-123', result.stdout)
        self.assertNotIn('super-secret-password-123', result.stderr)
