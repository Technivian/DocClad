"""Hermetic test settings — fast, offline, no external services.

Use with:  DJANGO_SETTINGS_MODULE=config.settings_test python manage.py test
or simply:  make test

Forces an in-memory SQLite database, a local-memory cache, no real AI keys,
and fast password hashing so the full suite runs in seconds without touching
Supabase, Redis, Stripe, Gemini, or the network. This is the gap behind
audit finding C16 (the suite previously migrated against remote Supabase).
"""
import os

# Must be set BEFORE importing base settings: the .env loader uses
# os.environ.setdefault(), so a value present here (even empty) wins and keeps
# the remote DATABASE_URL out of the test run.
os.environ['DATABASE_URL'] = ''
os.environ.setdefault('SQLITE_PATH', ':memory:')
os.environ.setdefault('DJANGO_ENV', 'development')
os.environ.setdefault('DJANGO_DEBUG', 'false')
# Keep all third-party integrations off in tests.
os.environ.setdefault('GEMINI_API_KEY', '')
os.environ.setdefault('STRIPE_SECRET_KEY', '')
os.environ.setdefault('STRIPE_WEBHOOK_SECRET', '')
os.environ['ESIGN_PROVIDER'] = 'null'
os.environ['ESIGN_DOCUMENSO_API_KEY'] = ''
os.environ['ESIGN_DOCUMENSO_WEBHOOK_SECRET'] = ''
# PAR-ID-001 flags must not leak from a staging-equivalent .env into hermetic tests.
os.environ['PROCESS_ROLE_SHADOW_WRITE_ENABLED'] = 'false'
os.environ['PROCESS_ROLE_PARITY_REPORTING_ENABLED'] = 'false'
os.environ['PROCESS_ROLE_RESOLVER_PARITY_ENABLED'] = 'false'
os.environ['PROCESS_ROLE_CANONICAL_RESOLVER_ENABLED'] = 'false'
os.environ['PROCESS_ROLE_CANONICAL_RESOLVER_ORG_ALLOWLIST'] = ''

from .settings_development import *  # noqa: E402,F401,F403

# Remove debug toolbar: it injects POST forms (CSRF check failures) and SQL
# output containing column names (content-not-contains false positives).
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != 'debug_toolbar']  # noqa: F405
MIDDLEWARE = [m for m in MIDDLEWARE if 'debug_toolbar' not in m]  # noqa: F405

# In-memory DB regardless of any inherited config.
DATABASES['default'] = {  # noqa: F405
    'ENGINE': 'django.db.backends.sqlite3',
    'NAME': ':memory:',
}

# Fast + hermetic.
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# Make integrations explicitly inert so no test can reach the network.
GEMINI_AI_ENABLED = False
# Pilot lock must never leak from an operator shell into hermetic tests.
CONTROLLED_PILOT_ENABLED = False
BILLING_SELF_SERVE_ENABLED = True
TRUST_ACCOUNTING_ENABLED = True
# Re-assert PAR-ID-001 defaults after .env load (setdefault cannot override existing .env).
PROCESS_ROLE_SHADOW_WRITE_ENABLED = False
PROCESS_ROLE_PARITY_REPORTING_ENABLED = False
PROCESS_ROLE_RESOLVER_PARITY_ENABLED = False
PROCESS_ROLE_CANONICAL_RESOLVER_ENABLED = False
PROCESS_ROLE_CANONICAL_RESOLVER_ORG_ALLOWLIST = ''

# Run RQ jobs synchronously in tests (no Redis required).
RQ_QUEUES = {
    'default': {
        'URL': 'redis://localhost:6379/0',
        'DEFAULT_TIMEOUT': 360,
        'ASYNC': False,
    },
}
