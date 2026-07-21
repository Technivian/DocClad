"""
API views for CLM One repository functionality.

Thin facade: implementations live in domain-aligned submodules under
``contracts.api``. Every public symbol is re-exported here so existing imports
(``from contracts.api import views as api_views``) and URL routes keep working.
"""
from contracts.api._helpers import (
    _error_response,
    _scim_response,
    _api_version_response,
    _scim_paginated_list,
    _api_paginated_contracts,
    _resolve_scim_organization,
    _resolve_api_organization,
    _require_org_member_context,
)
from contracts.api.scim import (
    _scim_user_payload,
    _scim_error,
    _scim_value_to_bool,
    _scim_first_non_empty_value,
    _scim_member_queryset,
    _scim_group_queryset,
    _scim_role_priority,
    _scim_normalize_role,
    _scim_parse_filter,
    _scim_filter_memberships,
    _scim_filter_groups,
    _upsert_scim_member,
    _apply_scim_user_updates,
    _scim_group_payload,
    _scim_group_membership_contains,
    _reconcile_scim_group_membership_role,
    _reconcile_all_scim_group_memberships,
    _resolve_scim_group_reference,
    _sync_scim_group_relations,
    _upsert_scim_group,
    scim_users_api,
    scim_user_api,
    scim_groups_api,
    scim_group_api,
)
from contracts.api.contracts_endpoints import (
    contracts_api,
    contracts_api_v1,
    case_detail_api,
    contract_detail_api_v1,
    contract_detail_api,
    cases_bulk_update_api,
    contract_versions_api,
    contract_version_detail_api,
    contract_version_diff_api,
    _version_to_dict,
    contracts_bulk_update_api,
)
from contracts.api.integrations import (
    _require_org_admin_for_salesforce,
    salesforce_connection_status_api,
    salesforce_oauth_start_api,
    salesforce_oauth_callback_api,
    salesforce_disconnect_api,
    salesforce_field_map_api,
    salesforce_ingest_preview_api,
    salesforce_sync_api,
    salesforce_sync_runs_api,
    netsuite_sync_api,
    webhook_deliveries_api,
    documenso_esign_webhook_api,
    esign_webhook_api,
    api_webhook_failed,
    api_webhook_retry,
    api_webhook_dlq,
    api_webhook_diagnostics,
    api_webhook_requeue,
    api_import_contracts_csv,
    api_import_contracts_json,
    api_crm_sync_status,
    api_crm_list_integrations,
    api_crm_trigger_sync,
)
from contracts.api.analytics import (
    executive_analytics_api,
    work_interaction_api,
    work_operating_metrics_api,
    executive_dashboard_presets_api,
    executive_dashboard_preset_delete_api,
    clause_analytics_stats,
    clause_analytics_top_clauses,
    clause_dependency_graph,
    clause_record_usage,
    mandatory_clause_compliance_contract,
    mandatory_clause_org_summary,
    playbook_list,
    playbook_detail,
    playbook_for_contract,
    api_contract_search,
    api_clause_search,
    api_search_facets,
    api_search_telemetry,
)
from contracts.api.documents_ai import (
    document_upload_api,
    document_extract_preview_api,
    contract_ai_extract_api,
    ai_extraction_span_review_api,
    contract_review_finding_action_api,
    contract_review_confirm_api,
    ai_suggest_clauses_api,
    ai_clause_recommendations_api,
    ai_accept_clause_api,
    ai_draft_section_api,
    _rec_to_dict,
)
from contracts.api.obligations_dsar_jobs import (
    _obligation_to_dict,
    contract_obligations_api,
    obligation_detail_api,
    obligation_reminders_api,
    _dsar_dto_to_dict,
    dsar_list_api,
    dsar_detail_api,
    dsar_evidence_api,
    _job_to_dict,
    job_list_api,
    job_detail_api,
    job_retry_api,
    api_subprocessor_alerts,
    api_transfer_risk_flags,
    api_retention_overdue,
    api_retention_log_action,
    api_retention_log,
)
from contracts.api.admin import (
    admin_settings_api,
    admin_policy_api,
    admin_integrations_api,
    admin_audit_api,
    permissions_matrix_api,
    contract_access_api,
    user_permissions_api,
    onboarding_status_api,
    onboarding_advance_api,
    onboarding_complete_api,
    billing_usage_api,
    billing_plan_api,
    compliance_trust_report_api,
    compliance_export_api,
    approval_initiate_api,
    approval_contract_list_api,
    approval_approve_api,
    approval_reject_api,
    approval_request_changes_api,
    approval_delegate_api,
    approval_reassign_api,
    approval_suggest_decision_api,
    assignee_options_api,
    work_suggest_comment_api,
    approval_overdue_api,
    approval_escalate_overdue_api,
    approval_list_api,
    _approval_dto_to_dict,
    api_db_health,
    api_migration_status,
    api_cve_gate_status,
    api_cve_scan_requirements,
    api_restore_drill_list,
    api_restore_drill_schedule,
    api_restore_drill_record,
    api_restore_drill_summary,
)

# ---------------------------------------------------------------------------
# Test/patch compatibility surface.
#
# Historically every view lived in this module, so the test-suite patches
# collaborators via ``contracts.api.views.<name>`` (e.g.
# ``mock.patch('contracts.api.views.Contract')``). After splitting the views
# into domain submodules, those collaborators are imported and used inside the
# submodules, so a plain ``setattr`` on this facade would no longer reach the
# running function. To preserve the exact public/test surface with zero
# behaviour change, we (a) re-export the patchable collaborators here and
# (b) install a module wrapper whose ``__setattr__`` forwards assignments to
# the domain submodules. ``mock.patch`` therefore transparently affects the
# implementation modules, and restoration on exit works the same way.
# ---------------------------------------------------------------------------
import sys as _sys
import types as _types

from contracts.api import (  # noqa: F401  (domain submodules used for patch forwarding)
    _helpers as _m_helpers,
    scim as _m_scim,
    contracts_endpoints as _m_contracts_endpoints,
    integrations as _m_integrations,
    analytics as _m_analytics,
    documents_ai as _m_documents_ai,
    obligations_dsar_jobs as _m_obligations_dsar_jobs,
    admin as _m_admin,
)

# Collaborators that the test-suite patches via ``contracts.api.views.<name>``.
# Re-exported here so ``mock.patch`` can locate them on this facade; the
# forwarding ``__setattr__`` below propagates the patch into the submodules
# where the views actually execute.
from contracts.models import (  # noqa: F401
    Contract,
    Document,
    BackgroundJob,
    ContractVersion,
    ClauseRecommendation,
)
from contracts.tenancy import get_user_organization  # noqa: F401
from django.contrib.auth.decorators import login_required  # noqa: F401
from contracts.services.contract_versions import get_version_service  # noqa: F401
from contracts.services.dsar import get_dsar_service  # noqa: F401
from contracts.services.obligations import get_obligation_service  # noqa: F401
from contracts.services.admin_console import get_admin_console_service  # noqa: F401
from contracts.services.ai_drafting import get_ai_drafting_service  # noqa: F401
from contracts.services.salesforce import (  # noqa: F401
    exchange_salesforce_code_for_tokens,
    sync_salesforce_connection,
)
from contracts.services.netsuite import fetch_netsuite_records  # noqa: F401

_PATCH_FORWARD_SUBMODULES = (
    _m_helpers,
    _m_scim,
    _m_contracts_endpoints,
    _m_integrations,
    _m_analytics,
    _m_documents_ai,
    _m_obligations_dsar_jobs,
    _m_admin,
)


class _ViewsFacadeModule(_types.ModuleType):
    """Module wrapper that forwards attribute assignments to domain submodules.

    Keeps ``mock.patch('contracts.api.views.<name>')`` working after the views
    were split into submodules: any name present on a submodule is updated there
    too, so the running view picks up the patched collaborator (and restoration
    on patch exit is forwarded the same way).
    """

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        for _submodule in self.__dict__.get('_PATCH_FORWARD_SUBMODULES', ()):  # pragma: no cover
            if hasattr(_submodule, name):
                setattr(_submodule, name, value)


_self_module = _sys.modules[__name__]
if not isinstance(_self_module, _ViewsFacadeModule):
    _wrapped = _ViewsFacadeModule(__name__)
    _wrapped.__dict__.update(_self_module.__dict__)
    _sys.modules[__name__] = _wrapped
