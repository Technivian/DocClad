"""Validation for application-initiated outbound HTTP requests.

Outbound integrations must never be able to target a loopback, private, or
otherwise non-public address. Host allowlists are optional in development but
can be supplied per integration through settings when a deployment needs a
tighter egress policy.
"""
from __future__ import annotations

from ipaddress import ip_address
from urllib.parse import urlparse

from django.conf import settings


class OutboundURLValidationError(ValueError):
    """Raised before an outbound request is constructed."""


def validate_public_https_url(url: str, *, label: str, allowed_hosts: tuple[str, ...] = ()) -> str:
    """Return a validated HTTPS URL suitable for an external integration.

    This intentionally rejects credentials in URLs and direct access to
    localhost or non-public IP ranges. Deployments may pass exact domains or
    parent domains (``example.com`` also allows ``api.example.com``).
    """
    value = str(url or '').strip()
    parsed = urlparse(value)
    hostname = (parsed.hostname or '').lower().rstrip('.')
    if (
        parsed.scheme != 'https'
        or not hostname
        or parsed.username
        or parsed.password
    ):
        raise OutboundURLValidationError(f'{label} must be an absolute HTTPS URL without credentials.')

    if hostname == 'localhost' or hostname.endswith('.localhost'):
        raise OutboundURLValidationError(f'{label} must not target localhost.')

    try:
        address = ip_address(hostname)
    except ValueError:
        address = None
    if address and (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    ):
        raise OutboundURLValidationError(f'{label} must not target a non-public IP address.')

    hosts = tuple(host.lower().strip().lstrip('.') for host in allowed_hosts if host and host.strip())
    if hosts and not any(hostname == host or hostname.endswith(f'.{host}') for host in hosts):
        raise OutboundURLValidationError(f'{label} host is not approved by the outbound allowlist.')
    return value


def setting_host_allowlist(name: str) -> tuple[str, ...]:
    """Read a comma-separated host allowlist without exposing it to callers."""
    raw = str(getattr(settings, name, '') or '')
    return tuple(item.strip() for item in raw.split(',') if item.strip())
