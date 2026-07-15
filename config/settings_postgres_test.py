"""PostgreSQL test settings — full-stack against a direct connection.

Use INSTEAD of config.settings_development when running the complete backend
suite.  Requires TEST_DATABASE_URL to point to a direct PostgreSQL connection
on port 5432 (local or Supabase direct — not the Supavisor pooler).

Why a separate settings file
─────────────────────────────
The application DATABASE_URL points to Supabase Supavisor's transaction-mode
pooler (port 6543).  In that topology each statement can land on a different
server connection.  Django's test runner calls serialize_db_to_string() which
creates named server-side cursors (DECLARE _django_curs_N_sync_M).  Those
cursors are connection-local: if the pooler hands the next statement to a
different server the cursor is gone and Django raises InvalidCursorName,
causing the session-scoped django_db_setup fixture to fail and cascading to
every TestCase in the session.

A direct connection on port 5432 (or a session-mode pooler that preserves
connection affinity) keeps the server connection stable for the lifetime of
the test session.

Usage
─────
Add TEST_DATABASE_URL to .env (see .env.example for format), then:

    DJANGO_SETTINGS_MODULE=config.settings_postgres_test \\
        python -m pytest tests/ --create-db

Or as a one-liner (without storing credentials in .env):

    DJANGO_SETTINGS_MODULE=config.settings_postgres_test \\
    TEST_DATABASE_URL=postgresql://<user>@localhost:5432/clmone_test \\
        python -m pytest tests/ --create-db

NEVER point TEST_DATABASE_URL at production or pilot data.
"""
import os
from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured

# ── Pre-load .env so TEST_DATABASE_URL is available before settings_base ──────
#
# settings_base._load_dotenv() uses os.environ.setdefault (env wins over .env).
# We replicate the same logic here early so that TEST_DATABASE_URL can be read
# from .env without requiring it to be exported in the shell beforehand.

from pathlib import Path as _Path  # noqa: E402

_DOTENV = _Path(__file__).resolve().parent.parent / '.env'
if _DOTENV.exists():
    for _raw_line in _DOTENV.read_text(encoding='utf-8').splitlines():
        _dotenv_line = _raw_line.strip()
        if not _dotenv_line or _dotenv_line.startswith('#') or '=' not in _dotenv_line:
            continue
        _dk, _dv = _dotenv_line.split('=', 1)
        os.environ.setdefault(_dk.strip(), _dv.strip().strip('"').strip("'"))

# ── Validate TEST_DATABASE_URL before any other settings are imported ─────────
#
# Values already present in os.environ WIN over .env file values (setdefault).
# We set DATABASE_URL here (from TEST_DATABASE_URL) before the base import so
# the application's Supabase URL never reaches the test runner's connection.

_TEST_DATABASE_URL = os.environ.get('TEST_DATABASE_URL', '').strip()

if not _TEST_DATABASE_URL:
    raise ImproperlyConfigured(
        'TEST_DATABASE_URL is required when using config.settings_postgres_test.\n'
        '\n'
        'Set it in .env or export it before running pytest:\n'
        '  TEST_DATABASE_URL=postgresql://<user>@localhost:5432/clmone_test\n'
        '\n'
        'See .env.example (section "Test database") for the full topology guide.\n'
        'Never point TEST_DATABASE_URL at production or pilot data.'
    )

_parsed = urlparse(_TEST_DATABASE_URL)
if _parsed.port == 6543:
    raise ImproperlyConfigured(
        'TEST_DATABASE_URL uses the Supabase Supavisor transaction-mode pooler '
        '(port 6543).\n'
        '\n'
        'Transaction-mode pooling is incompatible with parts of the Django test\n'
        'suite.  Server-side cursors (DECLARE cursor) are connection-local: if the\n'
        'pooler routes the next statement to a different server the cursor is gone\n'
        'and Django raises InvalidCursorName.  This marks the session-scoped\n'
        'django_db_setup fixture as FAILED and cascades to every TestCase test.\n'
        '\n'
        'Use a direct PostgreSQL connection (port 5432) or a session-mode pooler\n'
        'that preserves server affinity for the connection lifetime.\n'
        'See .env.example (section "Test database") for options.'
    )

# Override DATABASE_URL so that settings_base picks up the test DSN, not the
# Supabase production URL from .env.
os.environ['DATABASE_URL'] = _TEST_DATABASE_URL

# ── Override DJANGO_ENV to 'development' so production validation doesn't fire ──
# (allows localhost HTTP URLs in test environment)
os.environ['DJANGO_ENV'] = 'development'

# ── Inherit all application settings from development ─────────────────────────

from .settings_development import *  # noqa: E402,F401,F403

# Remove interactive development middleware that interferes with the test
# client (debug toolbar injects POST forms → CSRF failures; browser-reload
# injects JavaScript that confuses content-not-contains assertions).
INSTALLED_APPS = [
    app for app in INSTALLED_APPS  # noqa: F405
    if app not in ('debug_toolbar', 'django_browser_reload')
]
MIDDLEWARE = [
    m for m in MIDDLEWARE  # noqa: F405
    if 'debug_toolbar' not in m and 'browser_reload' not in m
]

# Fast password hashing — tests don't need PBKDF2 security.
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

# Local caches and mail so no external services are required for CI.
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# Run RQ jobs synchronously (no Redis worker needed).
RQ_QUEUES = {
    'default': {
        'URL': 'redis://localhost:6379/0',
        'DEFAULT_TIMEOUT': 360,
        'ASYNC': False,
    },
}
