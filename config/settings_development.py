from . import settings_base as base
from .settings_base import *  # noqa: F401,F403


DEBUG = base._bool_env('DJANGO_DEBUG', default=True)
DJANGO_E2E = base._bool_env('DJANGO_E2E', default=False)
DJANGO_DEBUG_TOOLBAR = base._bool_env('DJANGO_DEBUG_TOOLBAR', default=False)

if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '0.0.0.0', 'testserver']

CSRF_TRUSTED_ORIGINS.extend([
    'https://*.replit.dev',
    'https://*.repl.co',
    'https://*.riker.replit.dev',
    'https://*.riker.replit.dev:8060',
])

INSTALLED_APPS.append('django_browser_reload')
MIDDLEWARE.append('django_browser_reload.middleware.BrowserReloadMiddleware')

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
