
import os

from django.conf import settings

from config.feature_flags import (
    is_feature_redesign_enabled,
    is_clmone_mode_enabled,
    is_cms_aegis_mode_enabled,
    is_mochadocs_mode_enabled,
    is_test_mode_enabled
)
from .back_navigation import resolve_shell_back
from .models import Notification, OrganizationMembership
from .nav_config import get_nav_for
from .permissions import can_manage_organization

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
    css_paths = [
        os.path.join(settings.BASE_DIR, 'theme', 'static', 'css', 'dist', 'styles.css'),
        os.path.join(settings.BASE_DIR, 'theme', 'static', 'css', 'clmone-tokens.css'),
        os.path.join(settings.BASE_DIR, 'theme', 'static', 'css', 'command-center.css'),
    ]
    try:
        return str(int(max(os.path.getmtime(path) for path in css_paths)))
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


def _sidebar_nav_for_template(request, user, organization):
    """Resolve contracts.nav_config.get_nav_for() into template-ready
    entries: each item's `active` callable is evaluated here (against the
    request's already-resolved url_name) into a plain `is_active` boolean,
    since templates can't invoke a callable with an argument."""
    current_url_name = getattr(getattr(request, 'resolver_match', None), 'url_name', None)
    contract_context = bool(getattr(request, 'sidebar_nav_contract_context', False))
    resolved = []
    for entry in get_nav_for(organization, user):
        if entry['kind'] == 'section':
            resolved.append({'kind': 'section', 'label': entry['label']})
            continue
        if entry['kind'] == 'group':
            children = [{
                'label': child['label'],
                'url_name': child['url_name'],
                'is_active': bool(current_url_name) and child['active'](current_url_name),
            } for child in entry['children']]
            resolved.append({
                'kind': 'group',
                'label': entry['label'],
                'icon': entry['icon'],
                'is_active': any(child['is_active'] for child in children),
                'children': children,
            })
            continue
        is_active = bool(current_url_name) and entry['active'](current_url_name)
        if contract_context:
            if entry['label'] == 'Contracts':
                is_active = True
            elif entry['label'] in ('Workflow Designer', 'New Contract', 'Reviews & Approvals'):
                is_active = False
        resolved.append({
            'kind': 'item',
            'label': entry['label'],
            'url_name': entry['url_name'],
            'icon': entry['icon'],
            'variant': entry.get('variant', ''),
            'is_active': is_active,
        })
    return resolved


def feature_flags(request):
    """Add feature flags to template context"""
    unread_notifications = 0
    can_manage_org = False
    sidebar_nav = []
    organization = getattr(request, 'organization', None)
    is_in_house_clm = bool(
        organization and getattr(organization, 'workspace_mode', None) == 'in_house_clm'
    )
    if getattr(request, 'user', None) and request.user.is_authenticated:
        unread_notifications = Notification.objects.filter(recipient=request.user, is_read=False).count()
        can_manage_org = can_manage_organization(request.user, organization)
        sidebar_nav = _sidebar_nav_for_template(request, request.user, organization)
    return {
        'FEATURE_REDESIGN': is_feature_redesign_enabled(),
        'CLMONE_MODE': is_clmone_mode_enabled(),
        'MOCHADOCS_MODE': is_mochadocs_mode_enabled(),
        'TEST_MODE': is_test_mode_enabled(),
        'SSO_ENABLED': getattr(settings, 'SSO_ENABLED', False),
        'GEMINI_AI_ENABLED': getattr(settings, 'GEMINI_AI_ENABLED', False),
        'BILLING_SELF_SERVE_ENABLED': getattr(settings, 'BILLING_SELF_SERVE_ENABLED', True),
        'TRUST_ACCOUNTING_ENABLED': getattr(settings, 'TRUST_ACCOUNTING_ENABLED', True),
        'CONTROLLED_PILOT_ENABLED': getattr(settings, 'CONTROLLED_PILOT_ENABLED', False),
        'BUILD_SHA': getattr(settings, 'BUILD_SHA', 'unknown'),
        'BUILD_LABEL': getattr(settings, 'BUILD_LABEL', 'commit unknown'),
        'csp_nonce': getattr(request, 'csp_nonce', ''),
        'CURRENT_ORGANIZATION': organization,
        'is_in_house_clm': is_in_house_clm,
        'risk_review_label': (
            'Legal Intelligence Hub' if is_in_house_clm else 'Risk Register'
        ),
        'UNREAD_NOTIFICATIONS': unread_notifications,
        'CAN_MANAGE_ORGANIZATION': can_manage_org,
        'SIDEBAR_NAV': sidebar_nav,
        'PAGE_BACK_LINK': resolve_shell_back(request),
        'USER_ORGANIZATION_MEMBERSHIPS': (
            OrganizationMembership.objects.filter(user=request.user, is_active=True).select_related('organization')
            if getattr(request, 'user', None) and request.user.is_authenticated
            else OrganizationMembership.objects.none()
        ),
    }
