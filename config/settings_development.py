from . import settings_base as base
from .settings_base import *  # noqa: F401,F403


DEBUG = base._bool_env('DJANGO_DEBUG', default=True)
DJANGO_E2E = base._bool_env('DJANGO_E2E', default=False)
DJANGO_DEBUG_TOOLBAR = base._bool_env('DJANGO_DEBUG_TOOLBAR', default=False)

if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '0.0.0.0', 'testserver']

CSRF_TRUSTED_ORIGINS.extend([
    'http://localhost:8060',
    'http://127.0.0.1:8060',
    'https://localhost:8060',
    'https://127.0.0.1:8060',
    'https://*.replit.dev',
    'https://*.repl.co',
    'https://*.riker.replit.dev',
    'https://*.riker.replit.dev:8060',
])

# Django 5.2 always wraps template loaders in cached.Loader, so HTML edits stay
# invisible until the worker restarts. In local development, read templates from
# disk on every request so browser reload shows template changes immediately.
if DEBUG:
    TEMPLATES = [
        {
            **TEMPLATES[0],
            'APP_DIRS': False,
            'OPTIONS': {
                **TEMPLATES[0]['OPTIONS'],
                'loaders': [
                    'django.template.loaders.filesystem.Loader',
                    'django.template.loaders.app_directories.Loader',
                ],
            },
        }
    ]

INSTALLED_APPS.append('django_browser_reload')
MIDDLEWARE.append('django_browser_reload.middleware.BrowserReloadMiddleware')
# Catch --noreload workers that outlive a git branch/checkout switch.
MIDDLEWARE.insert(0, 'contracts.middleware.DevServerCodeDriftMiddleware')

# The vertical toolbar changes page width and contaminates visual baselines.
# Keep it opt-in for an explicit debugging session rather than enabling it on
# every local page load or screenshot.
if DJANGO_DEBUG_TOOLBAR and not DJANGO_E2E:
    INSTALLED_APPS.append('debug_toolbar')
    MIDDLEWARE.insert(1, 'debug_toolbar.middleware.DebugToolbarMiddleware')

STORAGES = {
    **STORAGES,
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}
