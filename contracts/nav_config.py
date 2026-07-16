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

_ICON_DASHBOARD = mark_safe('<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"></path></svg>')
_ICON_PLUS = mark_safe('<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path></svg>')
_ICON_UPLOAD = mark_safe('<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 16V4m0 0L8 8m4-4 4 4M5 14v5a1 1 0 001 1h12a1 1 0 001-1v-5"></path></svg>')
_ICON_FOLDER = mark_safe('<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>')
_ICON_TASK = mark_safe('<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"></path></svg>')
_ICON_SETTINGS = mark_safe('<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317a1 1 0 011.35-.936l.478.239a1 1 0 00.894 0l.478-.239a1 1 0 011.35.936l.067.53a1 1 0 00.611.822l.49.198a1 1 0 01.554 1.266l-.18.52a1 1 0 00.174.952l.325.44a1 1 0 010 1.19l-.325.44a1 1 0 00-.174.952l.18.52a1 1 0 01-.554 1.266l-.49.198a1 1 0 00-.611.822l-.067.53a1 1 0 01-1.35.936l-.478-.239a1 1 0 00-.894 0l-.478.239a1 1 0 01-1.35-.936l-.067-.53a1 1 0 00-.611-.822l-.49-.198a1 1 0 01-.554-1.266l.18-.52a1 1 0 00-.174-.952l-.325-.44a1 1 0 010-1.19l.325-.44a1 1 0 00.174-.952l-.18-.52a1 1 0 01.554-1.266l.49-.198a1 1 0 00.611-.822l.067-.53z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15a3 3 0 100-6 3 3 0 000 6z"></path></svg>')


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
     'active': lambda n: n in ('repository', 'contract_list', 'contract_detail', 'contract_update', 'contract_create'), 'visible': _always},
    {'kind': 'item', 'label': 'DPA Reviews', 'url_name': 'contracts:dpa_review_pack_list', 'icon': _ICON_FOLDER,
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
