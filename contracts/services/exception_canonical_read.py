"""PAR-EXC-001 controlled canonical applicability read.

The service is deliberately default-off. It may be authoritative only for one
correlated canonical row in an allowlisted organisation; every miss or normal
operational error returns the caller's legacy result. Cross-tenant attempts do
not fall open.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import PermissionDenied

from contracts.services.exception_canonical import exception_is_applicable, privilege_granted
from contracts.services.exception_dual_write import AUTHORIZED_SOURCES

EVENT_CANONICAL_READ_USED = 'exception.canonical_read.used'
EVENT_CANONICAL_READ_FALLBACK = 'exception.canonical_read.fallback'
EVENT_CANONICAL_READ_DENIED = 'exception.canonical_read.denied'


@dataclass(frozen=True)
class CanonicalReadResolution:
    applicable: bool
    privilege_granted: bool
    canonical_used: bool
    fallback_reason: str = ''


def canonical_read_enabled_for_org(organization) -> bool:
    if not getattr(settings, 'EXCEPTION_CANONICAL_READ_ENABLED', False):
        return False
    allow = {
        slug.strip()
        for slug in (getattr(settings, 'EXCEPTION_CANONICAL_READ_ORG_ALLOWLIST', '') or '').split(',')
        if slug.strip()
    }
    return bool(allow) and (getattr(organization, 'slug', '') or '') in allow


def _audit(*, actor, organization, event: str, source: str, correlation_id: str, reason: str = '') -> None:
    from contracts.middleware import log_action

    log_action(
        actor,
        'VIEW',
        'ExceptionRequest',
        changes={
            'event': event,
            'source': source,
            'correlation_id': correlation_id,
            'reason': reason,
        },
        organization=organization,
        event_type=event,
        outcome='blocked' if event == EVENT_CANONICAL_READ_DENIED else 'success',
    )


def resolve_canonical_applicability(
    *,
    organization,
    source: str,
    correlation_id: str,
    legacy_applicable: bool,
    privilege_token: str = '',
    actor=None,
) -> CanonicalReadResolution:
    """Resolve an approved source without broadening authority.

    A canonical value is authoritative only when the requested source has
    exactly one correlated canonical request. Otherwise return the supplied
    legacy result. AI submitted rows remain non-applicable because no decision
    is synthesized.
    """
    if source not in AUTHORIZED_SOURCES:
        raise ValueError(f'Unauthorized canonical-read source: {source}')

    if not canonical_read_enabled_for_org(organization):
        return CanonicalReadResolution(
            applicable=legacy_applicable,
            privilege_granted=False,
            canonical_used=False,
            fallback_reason='disabled_or_not_allowlisted',
        )

    if actor is not None and getattr(actor, 'is_authenticated', False):
        from contracts.tenancy import get_user_organization

        actor_org = get_user_organization(actor)
        if actor_org is not None and actor_org.pk != organization.pk:
            _audit(
                actor=actor, organization=actor_org, event=EVENT_CANONICAL_READ_DENIED,
                source=source, correlation_id=correlation_id, reason='cross_tenant',
            )
            raise PermissionDenied('Cross-tenant canonical exception reads are prohibited.')

    try:
        from contracts.models import ExceptionRequest

        matches = list(ExceptionRequest.objects.filter(
            organization=organization,
            legacy_source=source,
            correlation_id=correlation_id,
        ).order_by('pk')[:2])
        if len(matches) != 1:
            reason = 'correlation_miss' if not matches else 'duplicate_correlation'
            _audit(
                actor=actor, organization=organization, event=EVENT_CANONICAL_READ_FALLBACK,
                source=source, correlation_id=correlation_id, reason=reason,
            )
            return CanonicalReadResolution(
                applicable=legacy_applicable,
                privilege_granted=False,
                canonical_used=False,
                fallback_reason=reason,
            )
        exception = matches[0]
        applicable = exception_is_applicable(exception)
        granted = bool(privilege_token) and privilege_granted(exception, privilege_token)
        _audit(
            actor=actor, organization=organization, event=EVENT_CANONICAL_READ_USED,
            source=source, correlation_id=correlation_id, reason='correlated',
        )
        return CanonicalReadResolution(
            applicable=applicable,
            privilege_granted=granted,
            canonical_used=True,
        )
    except PermissionDenied:
        raise
    except Exception:  # noqa: BLE001 - preserve the legacy product path
        _audit(
            actor=actor, organization=organization, event=EVENT_CANONICAL_READ_FALLBACK,
            source=source, correlation_id=correlation_id, reason='canonical_error',
        )
        return CanonicalReadResolution(
            applicable=legacy_applicable,
            privilege_granted=False,
            canonical_used=False,
            fallback_reason='canonical_error',
        )
