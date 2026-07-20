from datetime import datetime, timezone as datetime_timezone

from django.db import transaction
from django.utils import timezone
from django.contrib.sessions.models import Session

from .models import OrganizationMembership, UserProfile


def revoke_user_sessions(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.session_revocation_counter += 1
    profile.save(update_fields=['session_revocation_counter', 'updated_at'])
    return profile.session_revocation_counter


def revoke_organization_sessions(organization):
    affected_users = []
    memberships = (
        OrganizationMembership.objects
        .filter(organization=organization, is_active=True)
        .select_related('user')
    )
    with transaction.atomic():
        for membership in memberships:
            profile, _ = UserProfile.objects.get_or_create(user=membership.user)
            profile.session_revocation_counter += 1
            profile.save(update_fields=['session_revocation_counter', 'updated_at'])
            affected_users.append(membership.user_id)
    return affected_users


def revoke_session_by_key(session_key):
    if not session_key:
        return False
    deleted, _ = Session.objects.filter(session_key=session_key).delete()
    return bool(deleted)


def get_organization_session_audit(organization):
    memberships = (
        OrganizationMembership.objects
        .filter(organization=organization, is_active=True)
        .select_related('user')
    )
    members_by_id = {membership.user_id: membership for membership in memberships}
    sessions = []
    for session in Session.objects.all():
        try:
            data = session.get_decoded()
        except Exception:
            continue
        user_id = data.get('_auth_user_id')
        if user_id is None:
            continue
        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            continue
        membership = members_by_id.get(user_id)
        if membership is None:
            continue
        last_activity = data.get('session_last_activity_at')
        if last_activity is not None:
            try:
                last_activity = int(last_activity)
            except (TypeError, ValueError):
                last_activity = None
        if last_activity is not None:
            last_activity = datetime.fromtimestamp(last_activity, tz=datetime_timezone.utc)
        sessions.append({
            'session_key': session.session_key,
            'user_id': user_id,
            'username': membership.user.username,
            'email': membership.user.email,
            'role': membership.role,
            'last_activity_at': last_activity,
            'expire_date': session.expire_date,
            'is_expired': session.expire_date <= timezone.now(),
        })
    sessions.sort(key=lambda item: (item['username'] or '', item['expire_date']))
    return sessions


def get_user_sessions(user, *, current_session_key=None):
    """Return active Django sessions that belong to the given user only."""
    sessions = []
    if not user or not getattr(user, 'pk', None):
        return sessions
    user_id = int(user.pk)
    for session in Session.objects.all():
        try:
            data = session.get_decoded()
        except Exception:
            continue
        raw_user_id = data.get('_auth_user_id')
        if raw_user_id is None:
            continue
        try:
            if int(raw_user_id) != user_id:
                continue
        except (TypeError, ValueError):
            continue
        last_activity = data.get('session_last_activity_at')
        if last_activity is not None:
            try:
                last_activity = int(last_activity)
            except (TypeError, ValueError):
                last_activity = None
        if last_activity is not None:
            last_activity = datetime.fromtimestamp(last_activity, tz=datetime_timezone.utc)
        user_agent = (data.get('session_user_agent') or data.get('user_agent') or '').strip()
        sessions.append({
            'session_key': session.session_key,
            'last_activity_at': last_activity,
            'expire_date': session.expire_date,
            'is_expired': session.expire_date <= timezone.now(),
            'is_current': bool(current_session_key and session.session_key == current_session_key),
            'user_agent': user_agent or 'Browser session',
        })
    sessions.sort(
        key=lambda item: (
            0 if item['is_current'] else 1,
            item['last_activity_at'] or item['expire_date'],
        ),
        reverse=True,
    )
    return sessions


def current_session_timestamp():
    return int(timezone.now().timestamp())
