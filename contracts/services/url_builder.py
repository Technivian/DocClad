"""Centralized URL builder for outbound emails.

All email-generated links (invitations, password resets, etc.) must use the
canonical APP_BASE_URL from settings, never request.build_absolute_uri().
This prevents Host-header injection attacks and ensures production links
never use localhost or http.
"""
from urllib.parse import urljoin, urlparse

from django.conf import settings
from django.urls import reverse


def build_canonical_url(path: str) -> str:
    """Build an absolute URL using the canonical APP_BASE_URL.

    Args:
        path: The path or reverse() result to append (e.g., '/invite/abc123' or
              from reverse('contracts:accept_organization_invite', kwargs={...}))

    Returns:
        Absolute URL using APP_BASE_URL as the base.

    Raises:
        ImproperlyConfigured: if APP_BASE_URL is missing or malformed.

    Example:
        url = build_canonical_url(reverse('contracts:accept_organization_invite',
                                          kwargs={'token': invitation.token}))
        # Returns: 'https://clmone.com/invite/abc123' (in production)
    """
    base_url = getattr(settings, 'APP_BASE_URL', None)
    if not base_url:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured(
            'APP_BASE_URL is not configured. Set APP_BASE_URL in environment or settings.'
        )

    # Ensure path starts with /
    if not path.startswith('/'):
        path = '/' + path

    # Use urljoin to safely combine base URL with path
    # (handles trailing slashes correctly)
    return urljoin(base_url.rstrip('/') + '/', path.lstrip('/'))


def build_invitation_url(token: str) -> str:
    """Build the invitation acceptance URL.

    Args:
        token: The invitation token (e.g., from OrganizationInvitation.token)

    Returns:
        Absolute URL for accepting the invitation.
    """
    from django.urls import reverse
    path = reverse('contracts:accept_organization_invite', kwargs={'token': token})
    return build_canonical_url(path)
