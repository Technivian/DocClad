"""Centralized sidebar nav registry for the standard CLM One shell.

Single source of truth for sidebar order, section grouping, visibility, and
active-state matching. Maps to existing URL names where possible; new hub
routes are added only when no suitable destination exists yet.
"""
from django.conf import settings
from django.utils.safestring import mark_safe

from contracts.permissions import can_manage_organization, get_active_org_membership


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
_ICON_MY_WORK = _nav_icon(
    'my-work',
    '<rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/>'
    '<rect x="4" y="13" width="7" height="7" rx="1.5"/><path d="M14.5 15.5h4M16.5 13.5v4"/>'
)
_ICON_PLUS = _nav_icon(
    'new-contract',
    '<path d="M6 3.8h8l4.2 4.2V20.2H6z"/><path d="M14 3.8V8h4.2"/><path d="M9.5 13h5M12 10.5v5.5"/>'
)
_ICON_FOLDER = _nav_icon(
    'contracts',
    '<path d="M4 7.2A2.2 2.2 0 0 1 6.2 5h4.1l1.4 1.8H20v10.7A2.5 2.5 0 0 1 17.5 20h-11A2.5 2.5 0 0 1 4 17.5z"/>'
    '<path d="M8 11h8M8 15h5"/>'
)
_ICON_REVIEWS = _nav_icon(
    'reviews-approvals',
    '<path d="M9 11.5 11 13.5 15.5 9"/><path d="M4.5 6.5h15v12a2 2 0 0 1-2 2h-11a2 2 0 0 1-2-2v-12Z"/>'
    '<path d="M8 4.5h8"/>'
)
_ICON_TASK = _nav_icon(
    'obligations',
    '<rect x="4" y="5" width="16" height="15" rx="2"/><path d="M8 3v4M16 3v4M4 10h16"/><path d="m8.5 14.5 2 2 4-4"/>'
)
_ICON_PRIVACY = _nav_icon(
    'privacy-reviews',
    '<path d="M12 3.5 6 6.2v4.1c0 4.2 2.6 7.7 6 9.5 3.4-1.8 6-5.3 6-9.5V6.2z"/><path d="m9.5 12.1 1.7 1.7 3.4-3.7"/><path d="M8.8 8.8h6.4"/>'
)
_ICON_TEMPLATES = _nav_icon(
    'templates-playbooks',
    '<path d="M5 5.5h9.5L19 10v9.5H5z"/><path d="M14.5 5.5V10H19"/><path d="M8 13.5h8M8 17h5"/>'
)
_ICON_WORKFLOWS = _nav_icon(
    'workflows',
    '<path d="M6 4h5v5H6zM13 4h5v5h-5zM6 15h5v5H6z"/><path d="M8.5 9v3h7V9"/><path d="M15.5 9v6"/>'
)


def _always(user, organization):
    return bool(get_active_org_membership(user, organization) or (user and user.is_authenticated))


def _not_controlled_pilot(user, organization):
    return not getattr(settings, 'CONTROLLED_PILOT_ENABLED', False)


def _can_configure(user, organization):
    return can_manage_organization(user, organization)


def _governance_visible(user, organization):
    return _always(user, organization) and _not_controlled_pilot(user, organization)


def _configuration_visible(user, organization):
    return (
        _always(user, organization)
        and _not_controlled_pilot(user, organization)
        and _can_configure(user, organization)
    )


def _reviews_approvals_visible(user, organization):
    # Any active org member may receive or act on review/approval work.
    return _always(user, organization)


_NEW_CONTRACT_ACTIVE = frozenset({
    'contract_template_picker',
    'contract_create',
    'dpa_workflow_builder',
    'msa_workflow_builder',
    'nda_workflow_builder',
    'upload_signed_contract',
})

_CONTRACTS_ACTIVE = frozenset({
    'repository',
    'contract_list',
    'contract_detail',
    'contract_update',
})

_REVIEWS_APPROVALS_ACTIVE = frozenset({
    'approval_request_list',
    'approval_request_create',
    'approval_request_update',
})

_PRIVACY_REVIEW_ACTIVE = frozenset({
    'dpa_review_pack_list',
    'dpa_review_pack_detail',
    'dpa_review_pack_memo',
    'dpa_review_run_analysis',
    'dpa_review_set_approval_status',
    'dpa_review_link_related_contract',
    'dpa_review_generate_memo',
    'dpa_review_memo_export',
    'dpa_risk_item_create',
    'transfer_record_list',
    'transfer_record_create',
    'transfer_record_update',
    'subprocessor_list',
    'subprocessor_create',
    'subprocessor_detail',
    'subprocessor_update',
    'data_inventory_list',
    'data_inventory_create',
    'data_inventory_detail',
    'data_inventory_update',
})

_TEMPLATES_PLAYBOOKS_ACTIVE = frozenset({
    'templates_playbooks_hub',
    'clause_template_list',
    'clause_template_create',
    'clause_template_detail',
    'clause_template_update',
    'clause_template_compare',
    'clause_category_list',
    'clause_category_create',
    'clause_category_update',
    'dpa_playbook_list',
})

_WORKFLOW_DESIGNER_ACTIVE = frozenset({
    'workflow_dashboard',
    'workflow_dashboard_legacy',
    'workflow_detail',
    'workflow_create',
    'workflow_activity',
    'workflow_template_list',
    'workflow_template_detail',
    'workflow_template_create',
    'workflow_template_update',
    'workflow_template_preview',
    'workflow_template_activity',
    'workflow_template_duplicate',
    'workflow_template_archive',
    'workflow_template_delete',
    'workflow_approval_route_list',
    'workflow_designer_history',
    'approval_rule_list',
    'approval_rule_create',
    'approval_rule_update',
})

_OBLIGATIONS_ACTIVE_TOKENS = ('obligations', 'deadline')


def _privacy_active(url_name):
    if not url_name:
        return False
    if url_name in _PRIVACY_REVIEW_ACTIVE:
        return True
    return 'dpa_review' in url_name


def _obligations_active(url_name):
    if not url_name:
        return False
    return any(token in url_name for token in _OBLIGATIONS_ACTIVE_TOKENS)


def _templates_active(url_name):
    if not url_name:
        return False
    if url_name in _TEMPLATES_PLAYBOOKS_ACTIVE:
        return True
    return url_name.startswith('clause_')


_STANDARD_NAV = [
    {'kind': 'section', 'label': 'Workspace'},
    {'kind': 'item', 'label': 'Command Center', 'url_name': 'dashboard', 'icon': _ICON_DASHBOARD,
     'active': lambda n: n == 'dashboard', 'visible': _always},
    {'kind': 'item', 'label': 'My Work', 'url_name': 'contracts:my_work', 'icon': _ICON_MY_WORK,
     'active': lambda n: n == 'my_work', 'visible': _always},
    {'kind': 'item', 'label': 'Contracts', 'url_name': 'contracts:repository', 'icon': _ICON_FOLDER,
     'active': lambda n: n in _CONTRACTS_ACTIVE, 'visible': _always},

    {'kind': 'section', 'label': 'Create'},
    {'kind': 'item', 'label': 'New Contract', 'url_name': 'contracts:contract_template_picker', 'icon': _ICON_PLUS,
     'variant': 'action',
     'active': lambda n: n in _NEW_CONTRACT_ACTIVE, 'visible': _always},

    {'kind': 'section', 'label': 'Governance'},
    {'kind': 'item', 'label': 'Reviews & Approvals', 'url_name': 'contracts:approval_request_list', 'icon': _ICON_REVIEWS,
     'active': lambda n: n in _REVIEWS_APPROVALS_ACTIVE, 'visible': _reviews_approvals_visible},
    {'kind': 'item', 'label': 'Privacy Reviews', 'url_name': 'contracts:dpa_review_pack_list', 'icon': _ICON_PRIVACY,
     'active': _privacy_active, 'visible': _governance_visible},
    {'kind': 'item', 'label': 'Obligations', 'url_name': 'contracts:obligations_workspace', 'icon': _ICON_TASK,
     'active': _obligations_active, 'visible': _governance_visible},

    {'kind': 'section', 'label': 'Configuration'},
    {'kind': 'item', 'label': 'Templates & Playbooks', 'url_name': 'contracts:templates_playbooks_hub', 'icon': _ICON_TEMPLATES,
     'active': _templates_active, 'visible': _configuration_visible},
    {'kind': 'item', 'label': 'Workflow Designer', 'url_name': 'contracts:workflow_dashboard', 'icon': _ICON_WORKFLOWS,
     'active': lambda n: n in _WORKFLOW_DESIGNER_ACTIVE, 'visible': _configuration_visible},
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


def nav_item_labels(organization, user):
    """Ordered item labels for tests and diagnostics."""
    return [entry['label'] for entry in get_nav_for(organization, user) if entry['kind'] == 'item']
