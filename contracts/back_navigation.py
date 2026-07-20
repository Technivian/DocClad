"""Shell back-link targets: one level up, never Command Center by default.

Primary nav landings hide the topbar back control. Secondary pages map to their
parent list or hub. Templates may still override ``authenticated_page_back``.
"""

from __future__ import annotations

from django.urls import NoReverseMatch, reverse

# Primary shell landings (and Command Center itself): no back control.
ROOT_URL_NAMES = frozenset({
    'dashboard',
    'repository',
    'workflow_dashboard',
    'workflow_dashboard_legacy',
    'dpa_review_pack_list',
    'my_work',
    'templates_playbooks_hub',
    'obligations_workspace',
    'settings_hub',
    'global_search',
    'legal_front_door',
    'design_system_catalog',
    'design_preview_command_center',
    'design_preview_relationship_detail',
    'design_preview_review_studio',
    'components_demo',
    'styleguide',
    'mfa_challenge',
    'mfa_enroll',
    'invite_accept',
})

# url_name → (reverse name, aria/title label). Names without a namespace prefix
# are project-level; everything else is under contracts:.
_PARENT_BY_URL_NAME = {
    # Workflow Designer hub tabs → Active workflows
    'workflow_template_list': ('contracts:workflow_dashboard', 'Back to workflows'),
    'workflow_template_create': ('contracts:workflow_template_list', 'Back to templates'),
    'workflow_template_update': ('contracts:workflow_template_list', 'Back to templates'),
    'workflow_template_preview': ('contracts:workflow_template_list', 'Back to templates'),
    'workflow_template_compare': ('contracts:workflow_template_list', 'Back to templates'),
    'workflow_template_activity': ('contracts:workflow_template_list', 'Back to templates'),
    'approval_request_list': ('contracts:workflow_dashboard', 'Back to workflows'),
    'approval_rule_list': ('contracts:workflow_dashboard', 'Back to workflows'),
    'workflow_approval_route_list': ('contracts:workflow_dashboard', 'Back to workflows'),
    'workflow_designer_history': ('contracts:workflow_dashboard', 'Back to workflows'),
    'workflow_create': ('contracts:workflow_dashboard', 'Back to workflows'),
    'workflow_activity': ('contracts:workflow_dashboard', 'Back to workflows'),
    'workflow_step_add': ('contracts:workflow_dashboard', 'Back to workflows'),
    'workflow_step_update': ('contracts:workflow_dashboard', 'Back to workflows'),

    # Contracts / documents
    'contract_list': ('contracts:repository', 'Back to contracts'),
    'document_list': ('contracts:repository', 'Back to contracts'),
    'document_delete': ('contracts:document_list', 'Back to documents'),
    'activity_timeline': ('contracts:repository', 'Back to contracts'),
    'signature_request_list': ('contracts:repository', 'Back to contracts'),
    'signature_request_create': ('contracts:signature_request_list', 'Back to signature requests'),
    'signature_request_update': ('contracts:signature_request_list', 'Back to signature requests'),
    'signature_request_detail': ('contracts:signature_request_list', 'Back to signature requests'),
    'signature_packet_detail': ('contracts:signature_request_list', 'Back to signature requests'),

    # Obligations
    'deadline_list': ('contracts:obligations_workspace', 'Back to obligations'),
    'legal_task_kanban': ('contracts:obligations_workspace', 'Back to obligations'),
    'legal_task_create': ('contracts:obligations_workspace', 'Back to obligations'),
    'legal_task_update': ('contracts:obligations_workspace', 'Back to obligations'),

    # DPA / privacy
    'dpa_playbook_list': ('contracts:dpa_review_pack_list', 'Back to Privacy Reviews'),
    'dpa_review_pack_memo': ('contracts:dpa_review_pack_list', 'Back to Privacy Reviews'),
    'privacy_dashboard': ('settings_hub', 'Back to settings'),
    'dsar_list': ('contracts:privacy_dashboard', 'Back to privacy'),
    'dsar_create': ('contracts:dsar_list', 'Back to DSARs'),
    'dsar_update': ('contracts:dsar_list', 'Back to DSARs'),
    'dsar_detail': ('contracts:dsar_list', 'Back to DSARs'),
    'data_inventory_list': ('contracts:privacy_dashboard', 'Back to privacy'),
    'subprocessor_list': ('contracts:privacy_dashboard', 'Back to privacy'),
    'transfer_record_list': ('contracts:privacy_dashboard', 'Back to privacy'),
    'retention_policy_list': ('contracts:privacy_dashboard', 'Back to privacy'),
    'compliance_checklist_list': ('contracts:privacy_dashboard', 'Back to privacy'),
    'risk_log_list': ('contracts:privacy_dashboard', 'Back to privacy'),

    # Settings / admin hubs
    'organization_team': ('settings_hub', 'Back to settings'),
    'organization_activity': ('settings_hub', 'Back to settings'),
    'organization_identity_settings': ('settings_hub', 'Back to settings'),
    'organization_security_settings': ('settings_hub', 'Back to settings'),
    'organization_session_audit': ('settings_hub', 'Back to settings'),
    'ai_data_controls': ('settings_hub', 'Back to settings'),
    'billing_dashboard': ('settings_hub', 'Back to settings'),
    'billing_success': ('contracts:billing_dashboard', 'Back to billing'),
    'profile': ('settings_hub', 'Back to settings'),
    'profile_sessions': ('profile', 'Back to account settings'),
    'notification_list': ('settings_hub', 'Back to settings'),
    'audit_log_list': ('settings_hub', 'Back to settings'),
    'reports_dashboard': ('settings_hub', 'Back to settings'),
    'operations_dashboard': ('settings_hub', 'Back to settings'),
    'identity_telemetry_dashboard': ('settings_hub', 'Back to settings'),
    'legal_intelligence_hub': ('settings_hub', 'Back to settings'),

    # Clause library
    'clause_template_list': ('settings_hub', 'Back to settings'),
    'clause_template_detail': ('contracts:clause_template_list', 'Back to clause library'),
    'clause_template_compare': ('contracts:clause_template_list', 'Back to clause library'),
    'clause_category_list': ('contracts:clause_template_list', 'Back to clause library'),

    # Counterparties / clients / matters
    'counterparty_list': ('contracts:repository', 'Back to contracts'),
    'client_list': ('contracts:repository', 'Back to contracts'),
    'client_create': ('contracts:client_list', 'Back to clients'),
    'client_update': ('contracts:client_list', 'Back to clients'),
    'matter_list': ('contracts:repository', 'Back to contracts'),
    'matter_create': ('contracts:matter_list', 'Back to matters'),
    'matter_update': ('contracts:matter_list', 'Back to matters'),
    'matter_detail': ('contracts:matter_list', 'Back to matters'),
    'counterparty_collaboration_access': ('contracts:counterparty_list', 'Back to counterparties'),
    'counterparty_collaboration_portal': ('contracts:counterparty_list', 'Back to counterparties'),

    # Governance lists (detail/forms often override already)
    'legal_hold_list': ('settings_hub', 'Back to settings'),
    'ethical_wall_list': ('settings_hub', 'Back to settings'),
    'conflict_check_list': ('settings_hub', 'Back to settings'),
    'conflict_check_create': ('contracts:conflict_check_list', 'Back to conflict checks'),
    'conflict_check_update': ('contracts:conflict_check_list', 'Back to conflict checks'),

    # Finance / matters ops
    'budget_list': ('contracts:reports_dashboard', 'Back to reports'),
    'budget_create': ('contracts:budget_list', 'Back to budgets'),
    'budget_update': ('contracts:budget_list', 'Back to budgets'),
    'budget_detail': ('contracts:budget_list', 'Back to budgets'),
    'invoice_list': ('contracts:budget_list', 'Back to budgets'),
    'invoice_create': ('contracts:invoice_list', 'Back to invoices'),
    'invoice_update': ('contracts:invoice_list', 'Back to invoices'),
    'invoice_detail': ('contracts:invoice_list', 'Back to invoices'),
    'expense_create': ('contracts:budget_list', 'Back to budgets'),
    'expense_update': ('contracts:budget_list', 'Back to budgets'),
    'time_entry_list': ('contracts:matter_list', 'Back to matters'),
    'time_entry_create': ('contracts:time_entry_list', 'Back to time entries'),
    'time_entry_update': ('contracts:time_entry_list', 'Back to time entries'),
    'trust_account_list': ('settings_hub', 'Back to settings'),
    'trust_account_create': ('contracts:trust_account_list', 'Back to trust accounts'),
    'trust_account_update': ('contracts:trust_account_list', 'Back to trust accounts'),
    'trust_account_detail': ('contracts:trust_account_list', 'Back to trust accounts'),
    'trust_transaction_create': ('contracts:trust_account_list', 'Back to trust accounts'),
    'trust_transaction_update': ('contracts:trust_account_list', 'Back to trust accounts'),

    # Intake / IP / diligence
    'trademark_request_list': ('contracts:repository', 'Back to contracts'),
    'trademark_request_create': ('contracts:trademark_request_list', 'Back to trademark requests'),
    'trademark_request_update': ('contracts:trademark_request_list', 'Back to trademark requests'),
    'trademark_request_detail': ('contracts:trademark_request_list', 'Back to trademark requests'),
    'due_diligence_list': ('contracts:repository', 'Back to contracts'),
    'due_diligence_create': ('contracts:due_diligence_list', 'Back to due diligence'),
    'due_diligence_update': ('contracts:due_diligence_list', 'Back to due diligence'),
    'due_diligence_detail': ('contracts:due_diligence_list', 'Back to due diligence'),
    'dd_task_create': ('contracts:due_diligence_list', 'Back to due diligence'),
    'dd_task_update': ('contracts:due_diligence_list', 'Back to due diligence'),
    'dd_risk_create': ('contracts:due_diligence_list', 'Back to due diligence'),
    'dd_risk_update': ('contracts:due_diligence_list', 'Back to due diligence'),
    'negotiation_note_create': ('contracts:repository', 'Back to contracts'),
    'negotiation_note_update': ('contracts:repository', 'Back to contracts'),
    'checklist_item_create': ('contracts:compliance_checklist_list', 'Back to compliance checklists'),
    'checklist_item_update': ('contracts:compliance_checklist_list', 'Back to compliance checklists'),

    # NDA intake (MSA/DPA already override in templates)
    'nda_workflow_builder': ('contracts:contract_template_picker', 'Back to templates'),
}


def resolve_shell_back(request):
    """Return ``{'href', 'aria_label', 'title'}`` or ``None`` to hide the control."""
    match = getattr(request, 'resolver_match', None)
    if match is None:
        return None

    url_name = match.url_name
    if not url_name or url_name in ROOT_URL_NAMES:
        return None

    parent = _PARENT_BY_URL_NAME.get(url_name)
    if not parent:
        return None

    reverse_name, label = parent
    try:
        href = reverse(reverse_name)
    except NoReverseMatch:
        return None

    return {
        'href': href,
        'aria_label': label,
        'title': label,
    }
