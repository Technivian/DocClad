
import os

from django.conf import settings

from config.feature_flags import (
    is_feature_redesign_enabled,
    is_docclad_mode_enabled,
    is_cms_aegis_mode_enabled,
    is_mochadocs_mode_enabled,
    is_test_mode_enabled
)
from .models import Notification, OrganizationMembership

_ASSET_VERSION_CACHE = None


def _compute_asset_version():
    """mtime of the built stylesheet, used to cache-bust in development.

    Production serves hashed filenames via CompressedManifestStaticFilesStorage,
    so this returns '' there (no redundant query string). In DEBUG the dev server
    serves unhashed static files, so a per-build version query ensures rebuilt CSS
    is picked up without a manual hard refresh.
    """
    if not getattr(settings, 'DEBUG', False):
        return ''
    css_path = os.path.join(settings.BASE_DIR, 'theme', 'static', 'css', 'dist', 'styles.css')
    try:
        return str(int(os.path.getmtime(css_path)))
    except OSError:
        return ''


def asset_version(request):
    """Expose ASSET_VERSION for cache-busting static asset URLs in templates."""
    global _ASSET_VERSION_CACHE
    # Recompute every request in DEBUG (cheap stat); cache once otherwise.
    if getattr(settings, 'DEBUG', False):
        return {'ASSET_VERSION': _compute_asset_version()}
    if _ASSET_VERSION_CACHE is None:
        _ASSET_VERSION_CACHE = _compute_asset_version()
    return {'ASSET_VERSION': _ASSET_VERSION_CACHE}


def feature_flags(request):
    """Add feature flags to template context"""
    unread_notifications = 0
    if getattr(request, 'user', None) and request.user.is_authenticated:
        unread_notifications = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return {
        'FEATURE_REDESIGN': is_feature_redesign_enabled(),
        'DOCCLAD_MODE': is_docclad_mode_enabled(),
        'CMS_AEGIS_MODE': is_docclad_mode_enabled(),  # deprecated alias — remove after template migration
        'MOCHADOCS_MODE': is_mochadocs_mode_enabled(),
        'TEST_MODE': is_test_mode_enabled(),
        'SSO_ENABLED': getattr(settings, 'SSO_ENABLED', False),
        'GEMINI_AI_ENABLED': getattr(settings, 'GEMINI_AI_ENABLED', False),
        'BILLING_SELF_SERVE_ENABLED': getattr(settings, 'BILLING_SELF_SERVE_ENABLED', True),
        'TRUST_ACCOUNTING_ENABLED': getattr(settings, 'TRUST_ACCOUNTING_ENABLED', True),
        'BUILD_SHA': getattr(settings, 'BUILD_SHA', 'unknown'),
        'BUILD_LABEL': getattr(settings, 'BUILD_LABEL', 'commit unknown'),
        'csp_nonce': getattr(request, 'csp_nonce', ''),
        'CURRENT_ORGANIZATION': getattr(request, 'organization', None),
        'UNREAD_NOTIFICATIONS': unread_notifications,
        'USER_ORGANIZATION_MEMBERSHIPS': (
            OrganizationMembership.objects.filter(user=request.user, is_active=True).select_related('organization')
            if getattr(request, 'user', None) and request.user.is_authenticated
            else OrganizationMembership.objects.none()
        ),
    }
