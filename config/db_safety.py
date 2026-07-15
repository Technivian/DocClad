"""Shared helpers for the local-database safety guard.

Kept dependency-free (no Django settings imports) so they can be used both
from a settings module (before Django is configured) and from
contracts/apps.py's AppConfig.ready() (after apps are loaded).
"""
import os

# Render (clmone's deployment platform per render.yaml) sets these on every
# real deployed service. None of them can be present on a developer's laptop
# by accident, which is what makes this a meaningfully different signal from
# DJANGO_ENV — this repo's local .env sets DJANGO_ENV=production (mirroring
# the deployed config so production-flavored commands can be run locally when
# genuinely intended), so DJANGO_ENV alone cannot tell a real deployment
# apart from a local checkout.
_DEPLOYED_PLATFORM_MARKERS = ('RENDER', 'RENDER_SERVICE_ID', 'RENDER_INSTANCE_ID')


def is_local_database_host(database_config: dict) -> bool:
    """True if this DB config points at sqlite or a host on this machine."""
    if 'sqlite' in database_config.get('ENGINE', ''):
        return True
    host = (database_config.get('HOST') or '').strip().lower()
    return host in ('', 'localhost', '127.0.0.1', '::1')


def is_running_on_deployed_platform() -> bool:
    """True only on the actual Render deployment, never on a local checkout."""
    return any(os.environ.get(marker) for marker in _DEPLOYED_PLATFORM_MARKERS)
