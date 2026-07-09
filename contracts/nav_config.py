"""Centralized sidebar nav registry — Phase 1 of the Product Coherence
Redesign (see the Payrollminds product-strategy memo).

This module is the single source of truth for what the sidebar renders. It
maps to existing URL names ONLY — it introduces zero new routes and changes
zero permission checks. `workspace_mode` only changes what's *emphasized* in
the sidebar; every route stays reachable by direct URL regardless of mode
(see contracts/permissions.py for the authoritative access checks, which
this module never duplicates or overrides).

`law_firm_ops` (the default) reproduces the current sidebar byte-for-byte —
same items, same order, same sections, same icons, same active-state rules,
same permission gate on Escrow. `in_house_clm` renders the focused
Payrollminds nav from the memo's Section D.

One nav item in `in_house_clm` still points at the closest existing page
rather than a dedicated one, because building the dedicated page is out of
scope for this phase:
  - "Playbooks" -> the DPA playbook positions list (`dpa_playbook_list`)
    until Clause Library playbooks are merged in.
This is called out explicitly in NAV_ITEMS below — not a silent stand-in.

"Obligations" -> `obligations_workspace` (Phase 4), a dedicated view built
on the existing Deadline entity — see contracts/views_domains/deadlines.py.
"""
from django.utils.safestring import mark_safe

from contracts.permissions import can_manage_organization

# ── Icons — copied verbatim from the existing sidebar markup so visual
#    output is unchanged; nothing here is a new visual language. ──────────
_ICON_DASHBOARD = mark_safe('<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"></path></svg>')
_ICON_PLUS = mark_safe('<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path></svg>')
_ICON_FOLDER = mark_safe('<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>')
_ICON_ARCHIVE = mark_safe('<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4"></path></svg>')
_ICON_TASK = mark_safe('<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"></path></svg>')
_ICON_BOLT = mark_safe('<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>')
_ICON_APPROVAL = mark_safe('<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7h8m-8 5h8m-8 5h5M7 3h10a2 2 0 012 2v14a2 2 0 01-2 2H7a2 2 0 01-2-2V5a2 2 0 012-2z"></path></svg>')
_ICON_SIGNATURE = mark_safe('<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.828 14.828a4 4 0 01-5.656 0M9 10h.01M15 10h.01M7 19a8 8 0 1110 0l-5 2-5-2z"></path></svg>')
_ICON_RISK = mark_safe('<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>')
_ICON_SHIELD = mark_safe('<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path></svg>')
_ICON_AUDIT = mark_safe('<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path></svg>')
_ICON_DOCUMENT = mark_safe('<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"></path></svg>')
_ICON_COUNTERPARTY = mark_safe('<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"></path></svg>')
_ICON_CLIENT = mark_safe('<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path></svg>')
_ICON_REPORT = mark_safe('<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path></svg>')
_ICON_BUDGET = mark_safe('<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>')
_ICON_ESCROW = mark_safe('<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"></path></svg>')
_ICON_SETTINGS = mark_safe('<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317a1 1 0 011.35-.936l.478.239a1 1 0 00.894 0l.478-.239a1 1 0 011.35.936l.067.53a1 1 0 00.611.822l.49.198a1 1 0 01.554 1.266l-.18.52a1 1 0 00.174.952l.325.44a1 1 0 010 1.19l-.325.44a1 1 0 00-.174.952l.18.52a1 1 0 01-.554 1.266l-.49.198a1 1 0 00-.611.822l-.067.53a1 1 0 01-1.35.936l-.478-.239a1 1 0 00-.894 0l-.478.239a1 1 0 01-1.35-.936l-.067-.53a1 1 0 00-.611-.822l-.49-.198a1 1 0 01-.554-1.266l.18-.52a1 1 0 00-.174-.952l-.325-.44a1 1 0 010-1.19l.325-.44a1 1 0 00.174-.952l-.18-.52a1 1 0 01.554-1.266l.49-.198a1 1 0 00.611-.822l.067-.53z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15a3 3 0 100-6 3 3 0 000 6z"></path></svg>')


def _always(user, organization):
    return True


def _org_admin_only(user, organization):
    return can_manage_organization(user, organization)


# ── law_firm_ops — reproduces the current sidebar exactly. ────────────────
_LAW_FIRM_NAV = [
    {'kind': 'item', 'label': 'Dashboard', 'url_name': 'dashboard', 'icon': _ICON_DASHBOARD,
     'active': lambda n: n == 'dashboard', 'visible': _always},

    {'kind': 'section', 'label': 'EXECUTION'},
    {'kind': 'item', 'label': 'New Contract', 'url_name': 'contracts:contract_template_picker', 'icon': _ICON_PLUS,
     'active': lambda n: n in ('contract_template_picker', 'contract_create', 'dpa_workflow_builder', 'msa_workflow_builder', 'nda_workflow_builder'), 'visible': _always},
    {'kind': 'item', 'label': 'Contract Workspace', 'url_name': 'contracts:contract_list', 'icon': _ICON_FOLDER,
     'active': lambda n: n in ('contract_list', 'contract_detail', 'contract_update'), 'visible': _always},
    {'kind': 'item', 'label': 'Repository', 'url_name': 'contracts:repository', 'icon': _ICON_ARCHIVE,
     'active': lambda n: n == 'repository', 'visible': _always},
    {'kind': 'item', 'label': 'Tasks', 'url_name': 'contracts:legal_task_kanban', 'icon': _ICON_TASK,
     'active': lambda n: bool(n) and 'legal_task' in n, 'visible': _always},
    {'kind': 'item', 'label': 'Workflows', 'url_name': 'contracts:workflow_dashboard', 'icon': _ICON_BOLT,
     'active': lambda n: bool(n) and ('workflow' in n or n == 'workflow_dashboard'), 'visible': _always},
    {'kind': 'item', 'label': 'Approvals', 'url_name': 'contracts:approval_request_list', 'icon': _ICON_APPROVAL,
     'active': lambda n: bool(n) and 'approval_request' in n, 'visible': _always},
    {'kind': 'item', 'label': 'Signature Requests', 'url_name': 'contracts:signature_request_list', 'icon': _ICON_SIGNATURE,
     'active': lambda n: bool(n) and 'signature_request' in n, 'visible': _always},

    {'kind': 'section', 'label': 'RISK & COMPLIANCE'},
    {'kind': 'item', 'label': 'Risk Register', 'url_name': 'contracts:risk_log_list', 'icon': _ICON_RISK,
     'active': lambda n: bool(n) and ('risk' in n or n in ('risk_log_list', 'risk_log_create', 'risk_log_update')), 'visible': _always},
    {'kind': 'item', 'label': 'Compliance', 'url_name': 'contracts:compliance_checklist_list', 'icon': _ICON_SHIELD,
     'active': lambda n: bool(n) and ('compliance' in n or 'checklist' in n), 'visible': _always},
    {'kind': 'item', 'label': 'Privacy', 'url_name': 'contracts:privacy_dashboard', 'icon': _ICON_SHIELD,
     'active': lambda n: n == 'privacy_dashboard', 'visible': _always},
    {'kind': 'item', 'label': 'Audit Trail', 'url_name': 'contracts:audit_log_list', 'icon': _ICON_AUDIT,
     'active': lambda n: bool(n) and 'audit' in n, 'visible': _always},
    {'kind': 'item', 'label': 'DPA Reviews', 'url_name': 'contracts:dpa_review_pack_list', 'icon': _ICON_FOLDER,
     'active': lambda n: bool(n) and 'dpa_review' in n, 'visible': _always},

    {'kind': 'section', 'label': 'REFERENCE'},
    {'kind': 'item', 'label': 'Documents', 'url_name': 'contracts:document_list', 'icon': _ICON_DOCUMENT,
     'active': lambda n: bool(n) and 'document' in n, 'visible': _always},
    {'kind': 'item', 'label': 'Counterparties', 'url_name': 'contracts:counterparty_list', 'icon': _ICON_COUNTERPARTY,
     'active': lambda n: bool(n) and 'counterparty' in n, 'visible': _always},
    {'kind': 'item', 'label': 'Clients', 'url_name': 'contracts:client_list', 'icon': _ICON_CLIENT,
     'active': lambda n: bool(n) and 'client' in n, 'visible': _always},
    {'kind': 'item', 'label': 'Reports', 'url_name': 'contracts:reports_dashboard', 'icon': _ICON_REPORT,
     'active': lambda n: bool(n) and 'report' in n, 'visible': _always},

    {'kind': 'section', 'label': 'PLANNING'},
    {'kind': 'item', 'label': 'Budget & Capacity', 'url_name': 'contracts:budget_list', 'icon': _ICON_BUDGET,
     'active': lambda n: bool(n) and 'budget' in n, 'visible': _always},

    {'kind': 'section', 'label': 'ADMIN'},
    {'kind': 'item', 'label': 'Escrow', 'url_name': 'contracts:trust_account_list', 'icon': _ICON_ESCROW,
     'active': lambda n: bool(n) and 'trust' in n, 'visible': _org_admin_only},
    {'kind': 'item', 'label': 'Settings', 'url_name': 'settings_hub', 'icon': _ICON_SETTINGS,
     'active': lambda n: n == 'settings_hub', 'visible': _always},
]

# ── in_house_clm — the focused Payrollminds nav (memo Section D). Flat list,
#    no section headers, matching the spec's literal 12-item list. Two items
#    (Obligations, Playbooks) point at the closest existing page — see the
#    module docstring and the Phase 1 summary for why. ─────────────────────
_IN_HOUSE_CLM_NAV = [
    {'kind': 'item', 'label': 'Command Center', 'url_name': 'dashboard', 'icon': _ICON_DASHBOARD,
     'active': lambda n: n == 'dashboard', 'visible': _always},
    {'kind': 'item', 'label': 'Contracts', 'url_name': 'contracts:contract_list', 'icon': _ICON_FOLDER,
     'active': lambda n: n in ('contract_list', 'contract_detail', 'contract_update', 'contract_create'), 'visible': _always},
    {'kind': 'item', 'label': 'Repository', 'url_name': 'contracts:repository', 'icon': _ICON_ARCHIVE,
     'active': lambda n: n == 'repository', 'visible': _always},
    {'kind': 'item', 'label': 'Matters', 'url_name': 'contracts:matter_list', 'icon': _ICON_CLIENT,
     'active': lambda n: bool(n) and 'matter' in n, 'visible': _always},
    {'kind': 'item', 'label': 'Counterparties', 'url_name': 'contracts:counterparty_list', 'icon': _ICON_COUNTERPARTY,
     'active': lambda n: bool(n) and 'counterparty' in n, 'visible': _always},
    {'kind': 'item', 'label': 'Risk Review', 'url_name': 'contracts:risk_log_list', 'icon': _ICON_RISK,
     'active': lambda n: bool(n) and ('risk' in n or n in ('risk_log_list', 'risk_log_create', 'risk_log_update')), 'visible': _always},
    {'kind': 'item', 'label': 'DPA Reviews', 'url_name': 'contracts:dpa_review_pack_list', 'icon': _ICON_FOLDER,
     'active': lambda n: bool(n) and 'dpa_review' in n, 'visible': _always},
    {'kind': 'item', 'label': 'Approvals', 'url_name': 'contracts:approval_request_list', 'icon': _ICON_APPROVAL,
     'active': lambda n: bool(n) and 'approval_request' in n, 'visible': _always},
    {'kind': 'item', 'label': 'Obligations', 'url_name': 'contracts:obligations_workspace', 'icon': _ICON_TASK,
     'active': lambda n: bool(n) and ('obligations' in n or 'deadline' in n), 'visible': _always},
    {'kind': 'item', 'label': 'Playbooks', 'url_name': 'contracts:dpa_playbook_list', 'icon': _ICON_SHIELD,
     'active': lambda n: n == 'dpa_playbook_list', 'visible': _always},
    {'kind': 'item', 'label': 'Reports', 'url_name': 'contracts:reports_dashboard', 'icon': _ICON_REPORT,
     'active': lambda n: bool(n) and 'report' in n, 'visible': _always},
    {'kind': 'item', 'label': 'Admin', 'url_name': 'settings_hub', 'icon': _ICON_SETTINGS,
     'active': lambda n: n == 'settings_hub', 'visible': _always},
]

_NAV_BY_MODE = {
    'law_firm_ops': _LAW_FIRM_NAV,
    'in_house_clm': _IN_HOUSE_CLM_NAV,
}


def get_nav_for(organization, user):
    """Return the sidebar entries for this organization/user.

    Each entry is either `{'kind': 'section', 'label': ...}` or
    `{'kind': 'item', 'label', 'url_name', 'icon', 'is_active'}` — permission
    filtering (`visible`) is already applied, so the template only needs to
    render what it's given. Consecutive section headers with no visible
    items between them are dropped so hiding a gated item never leaves a
    dangling empty section.
    """
    mode = getattr(organization, 'workspace_mode', None) or 'law_firm_ops'
    spec = _NAV_BY_MODE.get(mode, _LAW_FIRM_NAV)

    resolved = []
    for entry in spec:
        if entry['kind'] == 'section':
            resolved.append({'kind': 'section', 'label': entry['label']})
            continue
        if not entry['visible'](user, organization):
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
