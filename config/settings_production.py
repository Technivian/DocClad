import logging
import os
import warnings

from django.core.exceptions import ImproperlyConfigured

from . import settings_base as base
from .settings_base import *  # noqa: F401,F403

_prod_logger = logging.getLogger('docclad.production')


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
if DEFAULT_FROM_EMAIL in ('noreply@cms-aegis.local', 'noreply@docclad.local'):
    raise ImproperlyConfigured('DEFAULT_FROM_EMAIL must be set in production.')

# Reject weak / placeholder secret keys (settings_base only rejects an empty
# key). A short or dev-marker key in production is a security defect.
_INSECURE_SECRET_MARKERS = ('django-insecure-', 'change-me', 'changeme', 'dev-only', 'insecure')
if len(SECRET_KEY) < 32 or any(m in SECRET_KEY.lower() for m in _INSECURE_SECRET_MARKERS):
    raise ImproperlyConfigured(
        'DJANGO_SECRET_KEY is missing or too weak for production. Use a strong, '
        'randomly generated secret of at least 32 characters (50+ recommended).'
    )

ALLOW_SQLITE_IN_PRODUCTION = base._bool_env('ALLOW_SQLITE_IN_PRODUCTION', default=False)
if not ALLOW_SQLITE_IN_PRODUCTION:
    db_engine = DATABASES.get('default', {}).get('ENGINE', '')
    if db_engine != 'django.db.backends.postgresql':
        raise ImproperlyConfigured(
            'Production requires PostgreSQL. Set DATABASE_URL=postgresql://... '
            'or explicitly set ALLOW_SQLITE_IN_PRODUCTION=true for temporary emergency use.'
        )
else:
    _emergency_bypass_warning('ALLOW_SQLITE_IN_PRODUCTION')

# Media storage: warn if using filesystem in production (files lost on redeploy)
# but don't hard-block it — set MEDIA_STORAGE_BACKEND=s3 when object storage is available.
if MEDIA_STORAGE_BACKEND not in ('s3', 'filesystem'):
    raise ImproperlyConfigured(
        f'Unsupported MEDIA_STORAGE_BACKEND={MEDIA_STORAGE_BACKEND!r}. Use "s3" or "filesystem".'
    )

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_SSL_REDIRECT = base._bool_env('SECURE_SSL_REDIRECT', default=True)
SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '3600'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = base._bool_env('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=True)
SECURE_HSTS_PRELOAD = base._bool_env('SECURE_HSTS_PRELOAD', default=True)
SECURE_REFERRER_POLICY = os.getenv('SECURE_REFERRER_POLICY', 'same-origin')
