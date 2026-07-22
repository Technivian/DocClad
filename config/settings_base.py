import os
import re
import subprocess
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlparse

from django.core.exceptions import ImproperlyConfigured


BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return
    for raw_line in dotenv_path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {'1', 'true', 'yes', 'on'}


def _csv_env(name: str, default: list[str] | None = None) -> list[str]:
    raw = os.getenv(name)
    if raw is None:
        return list(default or [])
    return [item.strip() for item in raw.split(',') if item.strip()]


def _git_short_sha(base_dir: Path) -> str:
    try:
        completed = subprocess.run(
            ['git', '-C', str(base_dir), 'rev-parse', '--short', 'HEAD'],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return ''
    return completed.stdout.strip()


_load_dotenv(BASE_DIR / '.env')

DJANGO_ENV = os.getenv('DJANGO_ENV', 'development').strip().lower()

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', '')
if not SECRET_KEY and DJANGO_ENV == 'production':
    raise ImproperlyConfigured('DJANGO_SECRET_KEY must be set in production.')
if not SECRET_KEY:
    SECRET_KEY = 'django-insecure-dev-only-key-change-me'

ALLOWED_HOSTS = _csv_env('ALLOWED_HOSTS')
CSRF_TRUSTED_ORIGINS = _csv_env('CSRF_TRUSTED_ORIGINS')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'theme',
    'contracts',
    'django_rq',
]

SSO_ENABLED = _bool_env('SSO_ENABLED', default=False)
SAML_ENABLED = _bool_env('SAML_ENABLED', default=False)

try:
    import mozilla_django_oidc  # noqa: F401
    OIDC_PACKAGE_AVAILABLE = True
except Exception:
    OIDC_PACKAGE_AVAILABLE = False

try:
    import onelogin  # noqa: F401
    SAML_PACKAGE_AVAILABLE = True
except Exception:
    SAML_PACKAGE_AVAILABLE = False

if OIDC_PACKAGE_AVAILABLE:
    INSTALLED_APPS.append('mozilla_django_oidc')

if SSO_ENABLED and not OIDC_PACKAGE_AVAILABLE:
    raise ImportError(
        'SSO_ENABLED is true but mozilla-django-oidc is not installed. '
        'Install it with: pip install mozilla-django-oidc'
    )

if SAML_ENABLED and not SAML_PACKAGE_AVAILABLE:
    raise ImportError(
        'SAML_ENABLED is true but python3-saml is not installed. '
        'Install it with: pip install python3-saml'
    )

MIDDLEWARE = [
    'contracts.middleware.PreviewExceptionMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'contracts.middleware.AuthRateLimitMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'contracts.middleware.SessionSecurityMiddleware',
    'contracts.middleware.OrganizationMiddleware',
    'contracts.middleware.RequestContextMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'contracts.middleware.ControlledPilotScopeMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'contracts.middleware.SecurityHeadersMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'theme/templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'contracts.context_processors.feature_flags',
                'contracts.context_processors.asset_version',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

def _database_config_from_env() -> dict:
    database_url = os.getenv('DATABASE_URL', '').strip()
    if not database_url:
        return {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.getenv('SQLITE_PATH', str(BASE_DIR / 'db.sqlite3')),
        }

    # Accept common copy/paste forms from dashboards or docs.
    # Examples:
    # - export DATABASE_URL='postgresql://...'
    # - DATABASE_URL="postgresql://..."
    if database_url.lower().startswith('export '):
        database_url = database_url[7:].strip()
    if database_url.startswith('DATABASE_URL='):
        database_url = database_url.split('=', 1)[1].strip()

    # Deployment providers and dashboards sometimes store pasted DSNs with
    # wrapping quotes; strip one matching pair before parsing the URL.
    if len(database_url) >= 2 and database_url[0] == database_url[-1] and database_url[0] in {'"', "'", '`'}:
        database_url = database_url[1:-1].strip()

    # Some UIs or docs copy text like "External Database URL: postgresql://..."
    # or include markdown wrappers. Pull out the first DSN-looking token.
    if not database_url.lower().startswith(('postgres://', 'postgresql://', 'sqlite:///')):
        dsn_match = re.search(r'(postgres(?:ql)?://\S+|sqlite:///\S+)', database_url, flags=re.IGNORECASE)
        if dsn_match:
            database_url = dsn_match.group(1).rstrip('"\'`>)')

    parsed = urlparse(database_url)
    scheme = (parsed.scheme or '').lower()
    query_options = dict(parse_qsl(parsed.query, keep_blank_values=True))

    if scheme in {'postgres', 'postgresql'}:
        engine = os.getenv('DB_ENGINE', 'django.db.backends.postgresql')
        config = {
            'ENGINE': engine,
            'NAME': unquote(parsed.path.lstrip('/')) if parsed.path else '',
            'USER': unquote(parsed.username) if parsed.username else '',
            'PASSWORD': unquote(parsed.password) if parsed.password else '',
            'HOST': parsed.hostname or '',
            'PORT': str(parsed.port) if parsed.port else '',
            'CONN_MAX_AGE': int(os.getenv('DB_CONN_MAX_AGE', os.getenv('CMS_DB_CONN_MAX_AGE', '60'))),
        }
        ssl_require = _bool_env('DB_SSL_REQUIRE', _bool_env('CMS_DB_SSL_REQUIRE', default=False))
        if ssl_require:
            config['OPTIONS'] = {'sslmode': 'require'}
        if 'sslmode' in query_options:
            config.setdefault('OPTIONS', {})
            config['OPTIONS']['sslmode'] = query_options['sslmode']
        return config

    if scheme == 'sqlite':
        if parsed.path in {'', '/'}:
            sqlite_name = os.getenv('SQLITE_PATH', str(BASE_DIR / 'db.sqlite3'))
        else:
            sqlite_name = unquote(parsed.path)
        return {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': sqlite_name,
        }

    raise ImproperlyConfigured(
        'Unsupported DATABASE_URL scheme. Use postgresql://... or postgres://... for production, '
        'sqlite:///... for local, and remove any surrounding quotes from DATABASE_URL.'
    )


DATABASES = {'default': _database_config_from_env()}

# Sub-block D: `manage.py test` must never touch a database on whatever host
# DATABASE_URL happens to resolve to. This lives here (not in
# settings_development.py) so it applies no matter which of
# settings_development / settings_production ends up loaded — a local
# checkout's .env can set DJANGO_ENV=production (this repo's does, mirroring
# the real Render deployment's config for convenience), which would otherwise
# route test runs through settings_production.py with the real DATABASE_URL.
# Opt out with ALLOW_REMOTE_TEST_DB=true (should not be needed).
import sys as _sys  # noqa: E402
if len(_sys.argv) > 1 and _sys.argv[1] == 'test' and not _bool_env('ALLOW_REMOTE_TEST_DB'):
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'theme' / 'static']
# ---------------------------------------------------------------------------
# Media storage — set MEDIA_STORAGE_BACKEND=s3 in any real deployment.
# Works with AWS S3 and Supabase Storage's S3-compatible endpoint.
# Falls back to local filesystem only for local development.
# ---------------------------------------------------------------------------
MEDIA_STORAGE_BACKEND = os.getenv('MEDIA_STORAGE_BACKEND', 'filesystem').strip().lower()

if MEDIA_STORAGE_BACKEND == 's3':
    _s3_options = {
        'bucket_name': os.getenv('AWS_STORAGE_BUCKET_NAME', '').strip(),
        'region_name': os.getenv('AWS_S3_REGION_NAME', '').strip() or None,
        'access_key': os.getenv('AWS_ACCESS_KEY_ID', '').strip() or None,
        'secret_key': os.getenv('AWS_SECRET_ACCESS_KEY', '').strip() or None,
        'endpoint_url': os.getenv('AWS_S3_ENDPOINT_URL', '').strip() or None,
        'default_acl': os.getenv('AWS_DEFAULT_ACL', 'private').strip() or None,
        'querystring_auth': True,
        'file_overwrite': False,
        'querystring_expire': int(os.getenv('AWS_SIGNED_URL_EXPIRE', '3600')),
    }
    if not _s3_options['bucket_name']:
        raise ImproperlyConfigured(
            'MEDIA_STORAGE_BACKEND=s3 requires AWS_STORAGE_BUCKET_NAME to be set.'
        )
    STORAGES = {
        'default': {
            'BACKEND': 'storages.backends.s3.S3Storage',
            'OPTIONS': {k: v for k, v in _s3_options.items() if v is not None},
        },
        'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
    }
else:
    STORAGES = {
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
    }

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CLMONE_MODE = False
BUILD_SHA = os.getenv('BUILD_SHA', '').strip() or _git_short_sha(BASE_DIR) or 'unknown'
BUILD_LABEL = f'commit {BUILD_SHA}' if BUILD_SHA != 'unknown' else 'commit unknown'

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'

# Keep default CSRF cookie name for browser compatibility with form posts.
# Session cookie renamed from cms_aegis_sessionid → clmone_sessionid.
# Existing sessions using the old name will require re-login once the env var is
# not overriding this. Production must set SESSION_COOKIE_NAME explicitly during transition.
SESSION_COOKIE_NAME = os.getenv('SESSION_COOKIE_NAME', 'clmone_sessionid')
CSRF_COOKIE_NAME = os.getenv('CSRF_COOKIE_NAME', 'csrftoken')
SESSION_IDLE_TIMEOUT_MINUTES = int(os.getenv('SESSION_IDLE_TIMEOUT_MINUTES', '120'))

AUTHENTICATION_BACKENDS = ['django.contrib.auth.backends.ModelBackend']
if SSO_ENABLED:
    AUTHENTICATION_BACKENDS.insert(0, 'contracts.auth_backends.CLMOneOIDCAuthenticationBackend')

OIDC_RP_CLIENT_ID = os.getenv('OIDC_RP_CLIENT_ID', '')
OIDC_RP_CLIENT_SECRET = os.getenv('OIDC_RP_CLIENT_SECRET', '')
OIDC_RP_SIGN_ALGO = os.getenv('OIDC_RP_SIGN_ALGO', 'RS256')
OIDC_RP_SCOPES = os.getenv('OIDC_RP_SCOPES', 'openid email profile')
SSO_ALLOWED_EMAIL_DOMAINS = [d.strip().lower() for d in os.getenv('SSO_ALLOWED_EMAIL_DOMAINS', '').split(',') if d.strip()]
OIDC_OP_AUTHORIZATION_ENDPOINT = os.getenv('OIDC_OP_AUTHORIZATION_ENDPOINT', '')
OIDC_OP_TOKEN_ENDPOINT = os.getenv('OIDC_OP_TOKEN_ENDPOINT', '')
OIDC_OP_USER_ENDPOINT = os.getenv('OIDC_OP_USER_ENDPOINT', '')
OIDC_OP_JWKS_ENDPOINT = os.getenv('OIDC_OP_JWKS_ENDPOINT', '')
OIDC_OP_LOGOUT_ENDPOINT = os.getenv('OIDC_OP_LOGOUT_ENDPOINT', '')
OIDC_OP_DISCOVERY_ENDPOINT = os.getenv('OIDC_OP_DISCOVERY_ENDPOINT', '')
OIDC_USE_NONCE = True
OIDC_STORE_ACCESS_TOKEN = False
OIDC_VERIFY_SSL = _bool_env('OIDC_VERIFY_SSL', default=True)

SAML_SP_ENTITY_ID = os.getenv('SAML_SP_ENTITY_ID', '')
SAML_SP_X509_CERT = os.getenv('SAML_SP_X509_CERT', '')
SAML_SP_PRIVATE_KEY = os.getenv('SAML_SP_PRIVATE_KEY', '')
SAML_STRICT = _bool_env('SAML_STRICT', default=True)

if SSO_ENABLED:
    has_discovery = bool(OIDC_OP_DISCOVERY_ENDPOINT)
    has_explicit_endpoints = all([
        OIDC_OP_AUTHORIZATION_ENDPOINT,
        OIDC_OP_TOKEN_ENDPOINT,
        OIDC_OP_USER_ENDPOINT,
        OIDC_OP_JWKS_ENDPOINT,
    ])
    if not (OIDC_RP_CLIENT_ID and OIDC_RP_CLIENT_SECRET and (has_discovery or has_explicit_endpoints)):
        raise ImportError(
            'SSO_ENABLED is true but required OIDC settings are missing. '
            'Set OIDC_RP_CLIENT_ID and OIDC_RP_CLIENT_SECRET, plus either '
            'OIDC_OP_DISCOVERY_ENDPOINT or all explicit endpoints '
            '(OIDC_OP_AUTHORIZATION_ENDPOINT, OIDC_OP_TOKEN_ENDPOINT, '
            'OIDC_OP_USER_ENDPOINT, OIDC_OP_JWKS_ENDPOINT).'
        )

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

INTERNAL_IPS = _csv_env('INTERNAL_IPS', default=['127.0.0.1'])


def _show_debug_toolbar(request):
    if request.path in ('/', '/login/', '/register/'):
        return False
    return request.META.get('REMOTE_ADDR') in INTERNAL_IPS


DEBUG_TOOLBAR_CONFIG = {
    'SHOW_TOOLBAR_CALLBACK': _show_debug_toolbar,
}

RATELIMIT_ENABLED = _bool_env('RATELIMIT_ENABLED', default=True)
RATELIMIT_PATHS = ('/login/', '/register/')
RATELIMIT_TRUSTED_IPS = tuple(_csv_env('RATELIMIT_TRUSTED_IPS'))
LOGIN_RATE_LIMIT_REQUESTS = int(os.getenv('LOGIN_RATE_LIMIT_REQUESTS', '10'))
LOGIN_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv('LOGIN_RATE_LIMIT_WINDOW_SECONDS', '300'))
REGISTER_RATE_LIMIT_REQUESTS = int(os.getenv('REGISTER_RATE_LIMIT_REQUESTS', '10'))
REGISTER_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv('REGISTER_RATE_LIMIT_WINDOW_SECONDS', '300'))

# Token-authenticated API surfaces (Bearer token). We throttle repeated AUTH
# FAILURES per IP rather than total volume, so legitimate authenticated traffic
# is never rate-limited while credential-stuffing / provisioning abuse is.
API_RATELIMIT_PREFIXES = ('/api/', '/scim/', '/contracts/api/', '/contracts/scim/')
API_AUTH_FAIL_LIMIT = int(os.getenv('API_AUTH_FAIL_LIMIT', '20'))
API_AUTH_FAIL_WINDOW_SECONDS = int(os.getenv('API_AUTH_FAIL_WINDOW_SECONDS', '300'))

SECURITY_HEADERS_ENABLED = _bool_env('SECURITY_HEADERS_ENABLED', default=True)
CONTENT_SECURITY_POLICY = os.getenv(
    'CONTENT_SECURITY_POLICY',
    "default-src 'self'; "
    # script/style use per-request nonces ({nonce} is substituted by
    # SecurityHeadersMiddleware). No 'unsafe-inline': inline <script>/<style>
    # blocks carry the nonce, inline event handlers were moved to delegated
    # listeners (static/js/csp-handlers.js), and inline style="" attributes were
    # removed. Google Fonts CSS is still loaded via a stylesheet <link>.
    "script-src 'self' 'nonce-{nonce}'; "
    "style-src 'self' 'nonce-{nonce}' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "frame-src 'none'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "report-uri /csp-report/"
)
PERMISSIONS_POLICY = os.getenv('PERMISSIONS_POLICY', 'geolocation=(), microphone=(), camera=()')
REMINDER_SCHEDULER_EXPECTED_INTERVAL_MINUTES = int(os.getenv('REMINDER_SCHEDULER_EXPECTED_INTERVAL_MINUTES', '60'))
REMINDER_SCHEDULER_STALE_MULTIPLIER = int(os.getenv('REMINDER_SCHEDULER_STALE_MULTIPLIER', '2'))
REQUEST_METRICS_ENABLED = _bool_env('REQUEST_METRICS_ENABLED', default=True)
HEALTH_DB_LATENCY_WARN_MS = int(os.getenv('HEALTH_DB_LATENCY_WARN_MS', '250'))
HEALTH_DB_LATENCY_FAIL_MS = int(os.getenv('HEALTH_DB_LATENCY_FAIL_MS', '1500'))
SLO_API_P95_MS = int(os.getenv('SLO_API_P95_MS', '500'))
SLO_5XX_RATE_WARN_PCT = float(os.getenv('SLO_5XX_RATE_WARN_PCT', '0.8'))
SLO_5XX_RATE_FAIL_PCT = float(os.getenv('SLO_5XX_RATE_FAIL_PCT', '2.0'))

SALESFORCE_CLIENT_ID = os.getenv('SALESFORCE_CLIENT_ID', '').strip()
SALESFORCE_CLIENT_SECRET = os.getenv('SALESFORCE_CLIENT_SECRET', '').strip()
SALESFORCE_AUTHORIZATION_URL = os.getenv(
    'SALESFORCE_AUTHORIZATION_URL',
    'https://login.salesforce.com/services/oauth2/authorize',
).strip()
SALESFORCE_TOKEN_URL = os.getenv(
    'SALESFORCE_TOKEN_URL',
    'https://login.salesforce.com/services/oauth2/token',
).strip()
SALESFORCE_REDIRECT_URI = os.getenv('SALESFORCE_REDIRECT_URI', '').strip()
SALESFORCE_SCOPES = os.getenv('SALESFORCE_SCOPES', 'api refresh_token offline_access').strip()
SALESFORCE_TOKEN_ENCRYPTION_SALT = os.getenv('SALESFORCE_TOKEN_ENCRYPTION_SALT', 'salesforce-tokens-v1').strip()
SALESFORCE_API_VERSION = os.getenv('SALESFORCE_API_VERSION', '61.0').strip()
SALESFORCE_SYNC_DEFAULT_LIMIT = int(os.getenv('SALESFORCE_SYNC_DEFAULT_LIMIT', '200'))

# Optional comma-separated deployment allowlist for customer webhook hosts.
# The runtime always rejects localhost and non-public IP targets.
OUTBOUND_WEBHOOK_ALLOWED_HOSTS = os.getenv('OUTBOUND_WEBHOOK_ALLOWED_HOSTS', '').strip()

NETSUITE_CLIENT_ID = os.getenv('NETSUITE_CLIENT_ID', '').strip()
NETSUITE_CLIENT_SECRET = os.getenv('NETSUITE_CLIENT_SECRET', '').strip()
NETSUITE_TOKEN_URL = os.getenv('NETSUITE_TOKEN_URL', '').strip()
NETSUITE_API_URL = os.getenv('NETSUITE_API_URL', '').strip()
NETSUITE_TIMEOUT_SECONDS = int(os.getenv('NETSUITE_TIMEOUT_SECONDS', '30'))
ESIGN_WEBHOOK_SECRET = os.getenv('ESIGN_WEBHOOK_SECRET', '').strip()
# Outbound e-signature dispatch. 'null' simulates a send (no network) so the
# flow works without credentials; 'http' posts to a configured e-sign gateway;
# 'docusign' uses the DocuSign eSignature REST API; 'documenso' uses the
# Documenso REST API. Free personal accounts support limited API sends; team
# accounts can additionally configure lifecycle webhooks.
ESIGN_PROVIDER = os.getenv('ESIGN_PROVIDER', 'null').strip().lower()
ESIGN_API_BASE = os.getenv('ESIGN_API_BASE', '').strip()
ESIGN_API_KEY = os.getenv('ESIGN_API_KEY', '').strip()
ESIGN_API_TIMEOUT_SECONDS = int(os.getenv('ESIGN_API_TIMEOUT_SECONDS', '10'))
# DocuSign provider (ESIGN_PROVIDER=docusign). Access token is obtained via
# JWT/auth-code OAuth and refreshed out of band (~8h lifetime).
ESIGN_DOCUSIGN_BASE_URI = os.getenv('ESIGN_DOCUSIGN_BASE_URI', '').strip()
ESIGN_DOCUSIGN_ACCOUNT_ID = os.getenv('ESIGN_DOCUSIGN_ACCOUNT_ID', '').strip()
ESIGN_DOCUSIGN_ACCESS_TOKEN = os.getenv('ESIGN_DOCUSIGN_ACCESS_TOKEN', '').strip()
ESIGN_DOCUMENSO_API_KEY = os.getenv('ESIGN_DOCUMENSO_API_KEY', '').strip()
ESIGN_DOCUMENSO_WEBHOOK_SECRET = os.getenv('ESIGN_DOCUMENSO_WEBHOOK_SECRET', '').strip()
ESIGN_DOCUMENSO_BASE_URL = os.getenv('ESIGN_DOCUMENSO_BASE_URL', 'https://app.documenso.com').strip()

# Cache — uses Redis when REDIS_URL is set, falls back to LocMem for local dev.
# LocMem is per-process and breaks rate limiting across gunicorn workers; always
# set REDIS_URL in production.
_redis_url = os.getenv('REDIS_URL', '').strip()
if _redis_url:
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': _redis_url,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'SOCKET_CONNECT_TIMEOUT': 5,
                'SOCKET_TIMEOUT': 5,
                'IGNORE_EXCEPTIONS': True,
            },
            'KEY_PREFIX': 'cms',
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }

# RQ job queue — backed by Redis when available, synchronous fallback otherwise.
# The worker runs via: manage.py rqworker default
RQ_QUEUES = {
    'default': {
        'URL': _redis_url or 'redis://localhost:6379/0',
        'DEFAULT_TIMEOUT': 360,
    },
}
if not _redis_url:
    RQ_QUEUES['default']['ASYNC'] = False

DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@clmone.local')
SERVER_EMAIL = os.getenv('SERVER_EMAIL', DEFAULT_FROM_EMAIL)

# Canonical base URL used by all outbound email links. Must be set in
# production via the APP_BASE_URL environment variable (https, no trailing
# slash). Defaults to localhost for development/test — url_builder.py and
# CLMOnePasswordResetForm both read this.
APP_BASE_URL = os.getenv('APP_BASE_URL', 'http://localhost:8000').strip()

# Operator alert email — if set, send_operator_job_failure_alert() sends a
# failure notification to this address when a scheduled job run fails.
OPERATOR_ALERT_EMAIL = os.getenv('OPERATOR_ALERT_EMAIL', '').strip()

# SMTP — defaults to console backend in dev; set EMAIL_HOST to enable real sending.
_email_host = os.getenv('EMAIL_HOST', '').strip()
if _email_host:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = _email_host
    EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
    EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '').strip()
    EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '').strip()
    EMAIL_USE_TLS = _bool_env('EMAIL_USE_TLS', default=True)
    EMAIL_USE_SSL = _bool_env('EMAIL_USE_SSL', default=False)
    EMAIL_TIMEOUT = int(os.getenv('EMAIL_TIMEOUT', '10'))
else:
    EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')

# Sentry — enabled when SENTRY_DSN is set; silent no-op otherwise.
_sentry_dsn = os.getenv('SENTRY_DSN', '').strip()
if _sentry_dsn:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.redis import RedisIntegration
    sentry_sdk.init(
        dsn=_sentry_dsn,
        integrations=[DjangoIntegration(), RedisIntegration()],
        traces_sample_rate=float(os.getenv('SENTRY_TRACES_SAMPLE_RATE', '0.1')),
        send_default_pii=False,
        environment=os.getenv('DJANGO_ENV', 'development'),
    )

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '').strip()
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-3.5-flash').strip()
# An explicit GEMINI_AI_ENABLED env override always wins; otherwise AI is on
# only when a key is present. A pilot deployment sets GEMINI_AI_ENABLED=false
# to keep confidential contract text off the LLM until the AI-controls work
# (redaction / opt-in / audit / DPA — roadmap B6) lands.
GEMINI_AI_ENABLED = _bool_env('GEMINI_AI_ENABLED', default=bool(GEMINI_API_KEY))

# ---------------------------------------------------------------------------
# Pilot scope flags (roadmap item 0.2)
# ---------------------------------------------------------------------------
# Default to current behaviour (enabled) so existing environments/tests are
# unaffected. A contained pilot deployment sets these to ``false`` to descope
# self-serve billing (invoice manually) and trust accounting (until its ledger
# is made atomic — roadmap B8), shrinking the critical path to pilot.
BILLING_SELF_SERVE_ENABLED = _bool_env('BILLING_SELF_SERVE_ENABLED', default=True)
TRUST_ACCOUNTING_ENABLED = _bool_env('TRUST_ACCOUNTING_ENABLED', default=True)
# Controlled internal pilot lock: when true, middleware + nav hide/block
# excluded surfaces (billing, law-firm modules, freeform create, signatures,
# unrestricted AI entry points, unfinished integrations). Default false so
# hermetic tests and general development remain unaffected.
CONTROLLED_PILOT_ENABLED = _bool_env('CONTROLLED_PILOT_ENABLED', default=False)

# PAR-ID-001 Slice 3 — feature-flagged shadow sync / parity (default OFF).
# When enabled, selected UserProfile.role writes mirror into org-scoped
# ProcessRoleAssignment. Legacy profile role remains authoritative for runtime.
PROCESS_ROLE_SHADOW_WRITE_ENABLED = _bool_env('PROCESS_ROLE_SHADOW_WRITE_ENABLED', default=False)
PROCESS_ROLE_PARITY_REPORTING_ENABLED = _bool_env('PROCESS_ROLE_PARITY_REPORTING_ENABLED', default=False)
# When enabled, selected legacy assignee resolvers also run canonical comparison
# diagnostics. Legacy return values remain authoritative for all callers.
PROCESS_ROLE_RESOLVER_PARITY_ENABLED = _bool_env('PROCESS_ROLE_RESOLVER_PARITY_ENABLED', default=False)
# PAR-ID-001 — canonical resolver authority (default OFF). Independent of the
# diagnostic flags above. When on, eligible CERTAIN non-ADMIN process roles on
# approved resolver paths may return canonical ProcessRoleAssignment users for
# organizations listed in PROCESS_ROLE_CANONICAL_RESOLVER_ORG_ALLOWLIST
# (comma-separated slugs). Empty allowlist = no organizations (fail-safe).
# Activation requires a separate governance vote; do not enable by default.
PROCESS_ROLE_CANONICAL_RESOLVER_ENABLED = _bool_env(
    'PROCESS_ROLE_CANONICAL_RESOLVER_ENABLED', default=False,
)
PROCESS_ROLE_CANONICAL_RESOLVER_ORG_ALLOWLIST = os.getenv(
    'PROCESS_ROLE_CANONICAL_RESOLVER_ORG_ALLOWLIST', '',
).strip()

# PAR-EXC-001 — priority-path dual-write (default OFF). Legacy remains
# authoritative. Empty allowlist = no organizations (fail-safe). Enablement
# requires Motion 2 authorization + controlled-pilot activation.
EXCEPTION_DUAL_WRITE_ENABLED = _bool_env('EXCEPTION_DUAL_WRITE_ENABLED', default=False)
EXCEPTION_DUAL_WRITE_ORG_ALLOWLIST = os.getenv(
    'EXCEPTION_DUAL_WRITE_ORG_ALLOWLIST', '',
).strip()

STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY', '').strip()
STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY', '').strip()
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '').strip()
STRIPE_PRICE_STARTER = os.getenv('STRIPE_PRICE_STARTER', '').strip()
STRIPE_PRICE_PROFESSIONAL = os.getenv('STRIPE_PRICE_PROFESSIONAL', '').strip()
STRIPE_ENABLED = bool(STRIPE_SECRET_KEY)

DJANGO_LOG_LEVEL = os.getenv('DJANGO_LOG_LEVEL', 'INFO').upper()
LOG_SINK_ENABLED = _bool_env('LOG_SINK_ENABLED', default=False)
LOG_SINK_URL = os.getenv('LOG_SINK_URL', '').strip()
LOG_SINK_TIMEOUT_SECONDS = float(os.getenv('LOG_SINK_TIMEOUT_SECONDS', '2.0'))

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'request_context': {
            '()': 'contracts.logging_context.RequestContextLogFilter',
        },
    },
    'formatters': {
        'structured': {
            'format': (
                '%(asctime)s %(levelname)s %(name)s '
                'request_id=%(request_id)s user_id=%(request_user_id)s '
                'org_id=%(request_org_id)s path=%(request_path)s %(message)s'
            ),
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'filters': ['request_context'],
            'formatter': 'structured',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': DJANGO_LOG_LEVEL,
    },
}

if LOG_SINK_ENABLED and LOG_SINK_URL:
    LOGGING['handlers']['http_sink'] = {
        'class': 'contracts.log_sinks.HttpJsonLogHandler',
        'sink_url': LOG_SINK_URL,
        'timeout_seconds': LOG_SINK_TIMEOUT_SECONDS,
        'filters': ['request_context'],
    }
    LOGGING['root']['handlers'].append('http_sink')
