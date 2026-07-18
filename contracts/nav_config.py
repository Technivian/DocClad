"""Centralized sidebar nav registry for the standard CLM One shell.

This module is the single source of truth for what the sidebar renders. It
maps to existing URL names ONLY — it introduces zero new routes and changes
zero permission checks. Older layout pages intentionally stay reachable by
direct URL while they are being rebuilt, but they are no longer exposed as
primary shell navigation. That keeps the product on a single clean standard
surface instead of mixing migrated and legacy pages in the sidebar.
"""
from django.utils.safestring import mark_safe

from .permissions import can_manage_organization


def _nav_icon(name, body):
    return mark_safe(
        f'<svg class="nav-icon-svg nav-icon-svg--{name}" fill="none" stroke="currentColor" '
        f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24" '
        f'aria-hidden="true">{body}</svg>'
    )


_ICON_DASHBOARD = _nav_icon(
    'dashboard',
    '<path d="M4 6.5A2.5 2.5 0 0 1 6.5 4H9v6H4V6.5ZM11 4h3.5A2.5 2.5 0 0 1 17 6.5V10h-6V4ZM4 14h5v6H6.5A2.5 2.5 0 0 1 4 17.5V14ZM11 14h6v3.5A2.5 2.5 0 0 1 14.5 20H11v-6Z"/>'
    '<circle cx="12" cy="12" r="1.2"/>'
)
_ICON_PLUS = _nav_icon(
    'new-contract',
    '<path d="M6 3.8h8l4.2 4.2V20.2H6z"/><path d="M14 3.8V8h4.2"/><path d="M9.5 13h5M12 10.5v5.5"/>'
)
_ICON_UPLOAD = _nav_icon(
    'upload-review',
    '<path d="M12 4v8"/><path d="M8.5 8.5 12 5l3.5 3.5"/><path d="M5 14v5h14v-5"/><path d="M8 14h8"/>'
)
_ICON_FOLDER = _nav_icon(
    'contracts',
    '<path d="M4 7.2A2.2 2.2 0 0 1 6.2 5h4.1l1.4 1.8H20v10.7A2.5 2.5 0 0 1 17.5 20h-11A2.5 2.5 0 0 1 4 17.5z"/>'
    '<path d="M8 11h8M8 15h5"/>'
)
_ICON_TASK = _nav_icon(
    'obligations',
    '<rect x="4" y="5" width="16" height="15" rx="2"/><path d="M8 3v4M16 3v4M4 10h16"/><path d="m8.5 14.5 2 2 4-4"/>'
)
_ICON_SETTINGS = _nav_icon(
    'admin',
    '<rect x="5" y="5" width="14" height="14" rx="3"/>'
    '<path d="M9 9h6M9 12h6M9 15h6"/>'
)
_ICON_DPA_REVIEWS = _nav_icon(
    'dpa-reviews',
    '<path d="M12 3.5 6 6.2v4.1c0 4.2 2.6 7.7 6 9.5 3.4-1.8 6-5.3 6-9.5V6.2z"/><path d="m9.5 12.1 1.7 1.7 3.4-3.7"/><path d="M8.8 8.8h6.4"/>'
)


def _always(user, organization):
    return True


def _can_manage(user, organization):
    return can_manage_organization(user, organization)


_STANDARD_NAV = [
    {'kind': 'item', 'label': 'Command Center', 'url_name': 'dashboard', 'icon': _ICON_DASHBOARD,
     'active': lambda n: n == 'dashboard', 'visible': _always},
    {'kind': 'item', 'label': 'New Contract', 'url_name': 'contracts:contract_template_picker', 'icon': _ICON_PLUS,
     'variant': 'action',
     'active': lambda n: n in ('contract_template_picker', 'contract_create', 'dpa_workflow_builder', 'msa_workflow_builder', 'nda_workflow_builder'), 'visible': _always},
    {'kind': 'item', 'label': 'Upload & Review', 'url_name': 'contracts:upload_signed_contract', 'icon': _ICON_UPLOAD,
     'active': lambda n: n == 'upload_signed_contract', 'visible': _always},
    # Repository is the canonical contract list. The former Contract
    # Workspace remains available by direct URL for active legacy work, but
    # primary navigation must not send people back into that screen family.
    {'kind': 'item', 'label': 'Contracts', 'url_name': 'contracts:repository', 'icon': _ICON_FOLDER,
     'active': lambda n: n in ('repository', 'contract_list', 'contract_detail', 'contract_update'), 'visible': _always},
    {'kind': 'item', 'label': 'DPA Reviews', 'url_name': 'contracts:dpa_review_pack_list', 'icon': _ICON_DPA_REVIEWS,
     'active': lambda n: bool(n) and 'dpa_review' in n, 'visible': _always},
    {'kind': 'item', 'label': 'Obligations', 'url_name': 'contracts:obligations_workspace', 'icon': _ICON_TASK,
     'active': lambda n: bool(n) and ('obligations' in n or 'deadline' in n), 'visible': _always},
    {'kind': 'group', 'label': 'Admin', 'icon': _ICON_SETTINGS, 'visible': _always, 'children': [
        {'label': 'Settings', 'url_name': 'settings_hub',
         'active': lambda n: n == 'settings_hub', 'visible': _always},
        {'label': 'Team', 'url_name': 'contracts:organization_team',
         'active': lambda n: n == 'organization_team', 'visible': _always},
        {'label': 'Security', 'url_name': 'organization_security_settings',
         'active': lambda n: n in ('organization_security_settings', 'organization_identity_settings'), 'visible': _can_manage},
        {'label': 'Session Audit', 'url_name': 'organization_session_audit',
         'active': lambda n: n == 'organization_session_audit', 'visible': _can_manage},
    ]},
]


def get_nav_for(organization, user):
    """Return the sidebar entries for this organization/user.

    Each entry is either `{'kind': 'section', 'label': ...}` or
    `{'kind': 'item', 'label', 'url_name', 'icon', 'is_active'}` — permission
    filtering (`visible`) is already applied, so the template only needs to
    render what it's given. Consecutive section headers with no visible
    items between them are dropped so hiding a gated item never leaves a
    dangling empty section.
    """
    resolved = []
    for entry in _STANDARD_NAV:
        if entry['kind'] == 'section':
            resolved.append({'kind': 'section', 'label': entry['label']})
            continue
        if not entry['visible'](user, organization):
            continue
        if entry['kind'] == 'group':
            children = [
                child for child in entry['children']
                if child['visible'](user, organization)
            ]
            if children:
                resolved.append({**entry, 'children': children})
            continue
        resolved.append(entry)

    # Drop section headers with no following item (either trailing, or
    # immediately followed by another section header).
    cleaned = []
    for i, entry in enumerate(resolved):
        if entry['kind'] == 'section':
            has_item_after = any(
                e['kind'] == 'item' for e in resolved[i + 1:i + 1 + _next_section_span(resolved, i + 1)]
            )
            if not has_item_after:
                continue
        cleaned.append(entry)
    return cleaned


def _next_section_span(entries, start):
    """How many entries from `start` until the next section header (or end)."""
    for offset, entry in enumerate(entries[start:]):
        if entry['kind'] == 'section':
            return offset
    return len(entries) - start
