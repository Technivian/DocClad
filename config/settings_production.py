import logging
import os
import sys as _sys
import warnings
from ipaddress import ip_address
from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured

from . import settings_base as base
from .settings_base import *  # noqa: F401,F403

_prod_logger = logging.getLogger('clmone.production')


def _emergency_bypass_warning(flag_name):
    """Emit a high-severity warning when an emergency bypass flag is enabled.

    Temporary-exception process (see docs/PHASE5_PRODUCTION_CONFIG_GATE.md):
    a bypass requires a named Technical Owner, written rationale, and an expiry
    date; it must be removed at expiry and is logged here on every boot.
    """
    message = (
        f'HIGH SEVERITY: emergency bypass {flag_name}=true is ENABLED in '
        f'production. This disables a pilot safety guard. Requires Technical '
        f'Owner approval, rationale and an expiry date; remove ASAP.'
    )
    _prod_logger.critical(message)
    warnings.warn(message, RuntimeWarning, stacklevel=2)


DEBUG = base._bool_env('DJANGO_DEBUG', default=False)

if DEBUG:
    raise ImproperlyConfigured('DJANGO_DEBUG must be false in production settings.')

if not ALLOWED_HOSTS:
    raise ImproperlyConfigured('ALLOWED_HOSTS must be set in production.')
if not CSRF_TRUSTED_ORIGINS:
    raise ImproperlyConfigured('CSRF_TRUSTED_ORIGINS must be set in production.')
if DEFAULT_FROM_EMAIL in ('noreply@cms-aegis.local', 'noreply@clmone.local'):
    raise ImproperlyConfigured('DEFAULT_FROM_EMAIL must be set in production.')


def _validate_production_app_base_url():
    """Reject outbound-link bases that would leak localhost or use HTTP."""
    parsed = urlparse(APP_BASE_URL)
    hostname = parsed.hostname or ''
    if (
        parsed.scheme != 'https'
        or not hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ImproperlyConfigured(
            'APP_BASE_URL must be an absolute HTTPS origin without credentials, query, or fragment.'
        )

    if parsed.path not in ('', '/'):
        raise ImproperlyConfigured('APP_BASE_URL must be an HTTPS origin, not a path-based URL.')

    try:
        address = ip_address(hostname)
        is_non_public = (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
            or address.is_unspecified
        )
    except ValueError:
        is_non_public = hostname.lower() == 'localhost' or hostname.lower().endswith('.localhost')
    if is_non_public:
        raise ImproperlyConfigured('APP_BASE_URL must not point to a local or non-public address in production.')


_validate_production_app_base_url()

if not OPERATOR_ALERT_EMAIL:
    raise ImproperlyConfigured(
        'OPERATOR_ALERT_EMAIL must be set in production so scheduled-job failures reach an operator.'
    )

# Reject weak / placeholder secret keys (settings_base only rejects an empty
# key). A short or dev-marker key in production is a security defect.
_INSECURE_SECRET_MARKERS = ('django-insecure-', 'change-me', 'changeme', 'dev-only', 'insecure')
if len(SECRET_KEY) < 32 or any(m in SECRET_KEY.lower() for m in _INSECURE_SECRET_MARKERS):
    raise ImproperlyConfigured(
        'DJANGO_SECRET_KEY is missing or too weak for production. Use a strong, '
        'randomly generated secret of at least 32 characters (50+ recommended).'
    )

ALLOW_SQLITE_IN_PRODUCTION = base._bool_env('ALLOW_SQLITE_IN_PRODUCTION', default=False)
# `manage.py test` forces sqlite in settings_base.py regardless of DATABASE_URL
# (Sub-block D: a local checkout's .env can set DJANGO_ENV=production, which
# routes test runs through this very module) — that is the intended safety
# override, not a misconfiguration, so it must not trip this guard.
_IS_TEST_RUN = len(_sys.argv) > 1 and _sys.argv[1] == 'test'
if not ALLOW_SQLITE_IN_PRODUCTION and not _IS_TEST_RUN:
    db_engine = DATABASES.get('default', {}).get('ENGINE', '')
    if db_engine != 'django.db.backends.postgresql':
        raise ImproperlyConfigured(
            'Production requires PostgreSQL. Set DATABASE_URL=postgresql://... '
            'or explicitly set ALLOW_SQLITE_IN_PRODUCTION=true for temporary emergency use.'
        )
elif ALLOW_SQLITE_IN_PRODUCTION:
    _emergency_bypass_warning('ALLOW_SQLITE_IN_PRODUCTION')

# Contract files must be durable in production. The filesystem is ephemeral on
# Render and must never be accepted through a bypass flag.
if MEDIA_STORAGE_BACKEND != 's3':
    raise ImproperlyConfigured(
        'Production requires durable object storage. Set MEDIA_STORAGE_BACKEND=s3 '
        'with a private AWS_STORAGE_BUCKET_NAME.'
    )

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_SSL_REDIRECT = base._bool_env('SECURE_SSL_REDIRECT', default=True)
SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '3600'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = base._bool_env('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=True)
SECURE_HSTS_PRELOAD = base._bool_env('SECURE_HSTS_PRELOAD', default=True)
SECURE_REFERRER_POLICY = os.getenv('SECURE_REFERRER_POLICY', 'same-origin')
