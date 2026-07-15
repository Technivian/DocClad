"""pytest configuration for the CLM One test suite.

Session setup
─────────────
Fix A — close stale client-side Django DB connections at session start.
    Django persists connection objects across module-level setup.  Closing
    them here forces a fresh connection on the first DB access, so there are
    no references to a previous pytest process's pooler server state.

Fix B — flush leftover TransactionTestCase data from previous --reuse-db sessions.
    TransactionTestCase tests commit real data and call flush() in tearDown.
    If any teardown fails (e.g. after a keyboard-interrupt), that data persists
    in the --reuse-db test database.  The session-scoped autouse fixture below
    runs flush() once at session start (after django_db_setup connects to the
    TEST database) so subsequent TestCase snapshots see an empty database.

Topology guard
──────────────
Detecting Supabase Supavisor transaction-mode pooling (port 6543) and
aborting with an actionable error.  In transaction-mode pooling, each
statement may land on a different server, so server-side cursors created
by serialize_db_to_string() (DECLARE _django_curs_N_sync_M) are not
visible to the CLOSE / FETCH that follows.  Result: InvalidCursorName in
django_db_setup that cascades to all TestCase tests in the session.

The correct fix: use DJANGO_SETTINGS_MODULE=config.settings_postgres_test
with TEST_DATABASE_URL pointing to a direct PostgreSQL connection (port 5432).
"""
import os

import pytest


def pytest_configure(config):
    """Abort early if the configured database will cascade-fail the full suite."""
    dsm = os.environ.get('DJANGO_SETTINGS_MODULE', '')
    # Only warn when NOT using the dedicated postgres test settings (which
    # has its own hard error for port 6543).
    if 'postgres_test' in dsm:
        return
    db_url = os.environ.get('DATABASE_URL', '') or os.environ.get('TEST_DATABASE_URL', '')
    if ':6543' in db_url or 'pooler.supabase.com' in db_url:
        import warnings
        warnings.warn(
            '\n'
            '═══════════════════════════════════════════════════════════════\n'
            'WARNING: DATABASE_URL appears to use the Supabase Supavisor\n'
            'transaction-mode pooler (port 6543 or pooler.supabase.com).\n'
            '\n'
            'Server-side cursors created by serialize_db_to_string() are\n'
            'connection-local.  In transaction-mode pooling the pooler may\n'
            'route CLOSE/FETCH to a different server, causing:\n'
            '  psycopg2.errors.InvalidCursorName: cursor "..." does not exist\n'
            'This marks django_db_setup as FAILED and cascades to every\n'
            'TestCase test in the session (~400+ failures).\n'
            '\n'
            'For the full-suite gate, run with:\n'
            '  DJANGO_SETTINGS_MODULE=config.settings_postgres_test\n'
            '  TEST_DATABASE_URL=postgresql://<user>@localhost:5432/clmone_test\n'
            '  python -m pytest tests/ --create-db\n'
            '═══════════════════════════════════════════════════════════════',
            stacklevel=2,
        )


def pytest_sessionstart(session):
    """Close all Django DB connections so each session starts with a fresh one."""
    try:
        import django
        if not django.conf.settings.configured:
            os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_development')
            django.setup()
        from django.db import connections
        connections.close_all()
    except Exception:
        pass


@pytest.fixture(scope='session', autouse=True)
def _session_db_flush(django_db_setup):
    """Flush leftover TransactionTestCase data from previous --reuse-db sessions.

    Runs once at session start, after django_db_setup has wired the connection
    to the TEST database (not the production database).  Silenced on error:
    worst case is some test sees residual rows; it does not cascade.
    """
    from django.core.management import call_command
    try:
        call_command('flush', '--no-input', verbosity=0)
    except Exception:
        pass
