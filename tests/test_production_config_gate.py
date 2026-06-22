"""Phase 5D — executable production configuration gate.

Each test boots `config.settings_production` in a clean subprocess with a
controlled environment and asserts production REFUSES unsafe configuration (or
accepts a valid one). No external service is contacted; settings loading only
inspects configuration values.
"""
from __future__ import annotations

import os
import subprocess
import sys

import yaml
from django.test import SimpleTestCase

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_STRONG_SECRET = 'Zx9' + 'q7W2' * 12  # 51 chars, no insecure markers

_VALID_ENV = {
    'DJANGO_SETTINGS_MODULE': 'config.settings_production',
    'DJANGO_ENV': 'production',
    'DJANGO_DEBUG': 'false',
    'DJANGO_SECRET_KEY': _STRONG_SECRET,
    'ALLOWED_HOSTS': 'docclad.example.com',
    'CSRF_TRUSTED_ORIGINS': 'https://docclad.example.com',
    'DEFAULT_FROM_EMAIL': 'ops@docclad.example.com',
    'DATABASE_URL': 'postgres://u:p@db.example.com:5432/docclad',
    'DB_SSL_REQUIRE': 'false',
    'MEDIA_STORAGE_BACKEND': 's3',
    'AWS_STORAGE_BUCKET_NAME': 'docclad-pilot-bucket',
    'GEMINI_API_KEY': '',
    'STRIPE_SECRET_KEY': '',
}


def _run(env_overrides, code='import django; django.setup()', extra_args=()):
    env = {'PATH': os.environ.get('PATH', '')}
    env.update(_VALID_ENV)
    for k, v in env_overrides.items():
        if v is None:
            env.pop(k, None)
        else:
            env[k] = v
    return subprocess.run(
        [sys.executable, *extra_args, '-c', code],
        cwd=_REPO, env=env, capture_output=True, text=True,
    )


class ProductionRejectsUnsafeConfig(SimpleTestCase):
    def _assert_rejected(self, overrides, needle):
        r = _run(overrides)
        self.assertNotEqual(r.returncode, 0, f'expected rejection; stderr={r.stderr[-400:]}')
        self.assertIn(needle, r.stderr, r.stderr[-600:])

    def test_rejects_sqlite(self):
        self._assert_rejected({'DATABASE_URL': 'sqlite:////tmp/x.db'}, 'Production requires PostgreSQL')

    def test_rejects_debug(self):
        self._assert_rejected({'DJANGO_DEBUG': 'true'}, 'DJANGO_DEBUG must be false')

    def test_rejects_missing_secret(self):
        self._assert_rejected({'DJANGO_SECRET_KEY': ''}, 'DJANGO_SECRET_KEY')

    def test_rejects_weak_marker_secret(self):
        self._assert_rejected({'DJANGO_SECRET_KEY': 'django-insecure-dev-only-key-change-me-please'}, 'too weak')

    def test_rejects_short_secret(self):
        self._assert_rejected({'DJANGO_SECRET_KEY': 'short-key'}, 'too weak')

    def test_rejects_missing_allowed_hosts(self):
        self._assert_rejected({'ALLOWED_HOSTS': ''}, 'ALLOWED_HOSTS must be set')

    def test_rejects_missing_csrf_origins(self):
        self._assert_rejected({'CSRF_TRUSTED_ORIGINS': ''}, 'CSRF_TRUSTED_ORIGINS must be set')

    def test_rejects_default_from_email(self):
        self._assert_rejected({'DEFAULT_FROM_EMAIL': 'noreply@docclad.local'}, 'DEFAULT_FROM_EMAIL must be set')

    def test_rejects_ephemeral_media(self):
        self._assert_rejected({'MEDIA_STORAGE_BACKEND': 'filesystem'}, 'durable object storage')

    def test_rejects_s3_without_bucket(self):
        self._assert_rejected({'AWS_STORAGE_BUCKET_NAME': ''}, 'AWS_STORAGE_BUCKET_NAME')


class ProductionAcceptsValidConfig(SimpleTestCase):
    def test_valid_config_boots_and_cookies_secure(self):
        code = (
            'import django; django.setup(); from django.conf import settings; '
            'print("SESSION", settings.SESSION_COOKIE_SECURE); '
            'print("CSRF", settings.CSRF_COOKIE_SECURE); '
            'print("NOSNIFF", settings.SECURE_CONTENT_TYPE_NOSNIFF)'
        )
        r = _run({}, code=code)
        self.assertEqual(r.returncode, 0, r.stderr[-600:])
        self.assertIn('SESSION True', r.stdout)
        self.assertIn('CSRF True', r.stdout)
        self.assertIn('NOSNIFF True', r.stdout)

    def test_no_secret_leak_in_rejection(self):
        r = _run({'AWS_STORAGE_BUCKET_NAME': '', 'AWS_SECRET_ACCESS_KEY': 'super-secret-xyz'})
        self.assertNotIn('super-secret-xyz', r.stderr)


class EmergencyBypassWarnings(SimpleTestCase):
    """Bypass flags are allowed but must emit a high-severity warning."""

    def test_ephemeral_media_bypass_warns(self):
        r = _run(
            {'MEDIA_STORAGE_BACKEND': 'filesystem', 'ALLOW_EPHEMERAL_MEDIA_IN_PRODUCTION': 'true'},
            extra_args=('-W', 'always'),
        )
        self.assertEqual(r.returncode, 0, r.stderr[-400:])
        self.assertIn('HIGH SEVERITY', r.stderr)
        self.assertIn('ALLOW_EPHEMERAL_MEDIA_IN_PRODUCTION', r.stderr)

    def test_sqlite_bypass_warns(self):
        r = _run(
            {'DATABASE_URL': 'sqlite:////tmp/x.db', 'ALLOW_SQLITE_IN_PRODUCTION': 'true'},
            extra_args=('-W', 'always'),
        )
        self.assertEqual(r.returncode, 0, r.stderr[-400:])
        self.assertIn('HIGH SEVERITY', r.stderr)
        self.assertIn('ALLOW_SQLITE_IN_PRODUCTION', r.stderr)


class S3StorageOptionsValid(SimpleTestCase):
    """Regression: the production s3 STORAGES OPTIONS must be valid django-storages
    settings (the invalid `signed_url_expire` raised only at first file op)."""

    def test_s3_default_storage_instantiates(self):
        probe = subprocess.run([sys.executable, '-c', 'import storages'], capture_output=True)
        if probe.returncode != 0:
            self.skipTest('django-storages not installed in this environment')
        code = (
            'import django; django.setup(); '
            'from django.core.files.storage import storages; '
            's = storages["default"]; print("STORAGE", type(s).__name__)'
        )
        r = _run({}, code=code)  # valid env: MEDIA_STORAGE_BACKEND=s3 + bucket
        self.assertEqual(r.returncode, 0, r.stderr[-600:])
        self.assertIn('S3Storage', r.stdout)


class RenderDeploymentConfig(SimpleTestCase):
    """render.yaml: worker/cron use production settings + shared production DB."""

    def setUp(self):
        with open(os.path.join(_REPO, 'render.yaml')) as fh:
            self.cfg = yaml.safe_load(fh)
        self.groups = {g['name']: g for g in self.cfg.get('envVarGroups', [])}
        self.services = {s['name']: s for s in self.cfg.get('services', [])}

    def _group_kv(self, name):
        return {e.get('key'): e.get('value') for e in self.groups[name]['envVars'] if 'key' in e}

    def test_shared_group_sets_production_env_and_db(self):
        kv = self._group_kv('docclad-shared')
        self.assertEqual(kv.get('DJANGO_ENV'), 'production')
        keys = {e.get('key') for e in self.groups['docclad-shared']['envVars']}
        self.assertIn('DATABASE_URL', keys)

    def test_worker_and_cron_reference_shared_group(self):
        for svc in ('docclad-worker', 'docclad-cron-dispatch', 'docclad-cron-daily'):
            self.assertIn(svc, self.services)
            froms = {e.get('fromGroup') for e in self.services[svc]['envVars'] if 'fromGroup' in e}
            self.assertIn('docclad-shared', froms, f'{svc} must inherit docclad-shared (prod DB+settings)')

    def test_worker_type_and_cron_schedules(self):
        self.assertEqual(self.services['docclad-worker']['type'], 'worker')
        self.assertEqual(self.services['docclad-cron-dispatch']['type'], 'cronjob')
        self.assertEqual(self.services['docclad-cron-daily']['type'], 'cronjob')

    def test_ephemeral_media_bypass_absent_in_pilot_config(self):
        raw = open(os.path.join(_REPO, 'render.yaml')).read()
        self.assertNotIn('ALLOW_EPHEMERAL_MEDIA_IN_PRODUCTION', raw)
        self.assertNotIn('ALLOW_SQLITE_IN_PRODUCTION', raw)
