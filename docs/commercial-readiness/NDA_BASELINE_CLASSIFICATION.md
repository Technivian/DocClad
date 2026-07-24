# NDA Golden-Journey Test Baseline Classification

## Scope and authority

This documentation-only classification is of origin/main commit
e413da6b669b9d405f0ceac4488f2c8b2eff8890. The active authority is the
approved Governance Charter v2.3, accepted engineering, domain, platform,
workflow, security/audit and roadmap documents, PDR-0003, ADR-0013, ADR-0014
and ADR-0015. Charter v3, PDR-0004, ADR-0010 and ADR-0012 are proposed; PDR-0005
is accepted planning context only. None authorizes implementation here.

## Runs and counts

| Run | Result |
| --- | --- |
| Full existing suite | 2,495 run; 41 failures, 45 errors, 32 skipped; exit 1 |
| Focused Commercial v1 suite | 277 run; 5 failures, 1 error; exit 1 |
| NDA-specific suite | 17 run; 1 failure; exit 1 |
| DPA-specific suite | 115 run; 2 failures; exit 1 |
| Tenant/auth/audit/version/approval/provenance/signature set | 233 run; OK |

| Classification | Count |
| --- | ---: |
| COMMERCIAL_V1_BLOCKER | 1 |
| DUPLICATE_ROOT_CAUSE | 46 |
| PRE_EXISTING_BASELINE | 33 |
| UNRELATED_TO_COMMERCIAL_V1 | 5 |
| ENVIRONMENT_OR_FIXTURE | 1 |
| FUTURE_WORK_CHARACTERIZATION | 0 |
| UNKNOWN | 0 |
| **Total** | **86** |

### Exact commands

```sh
make PYTHON='/Users/haroonwahed/Documents/Projects/CLMOne/.venv/bin/python' test
DJANGO_SETTINGS_MODULE=config.settings_test /Users/haroonwahed/Documents/Projects/CLMOne/.venv/bin/python manage.py test tests.test_nda_workflow tests.test_dpa_workflow tests.test_dpa_review tests.test_contract_launch_setup tests.test_workflow_template_versioning tests.test_approval_workflow tests.test_approval_authorization tests.test_par_apr_001_approval tests.test_document_versioning tests.test_par_doc_001_document_version tests.test_signature_workspace tests.test_par_core_003_provenance -v 2
DJANGO_SETTINGS_MODULE=config.settings_test /Users/haroonwahed/Documents/Projects/CLMOne/.venv/bin/python manage.py test tests.test_nda_workflow -v 2
DJANGO_SETTINGS_MODULE=config.settings_test /Users/haroonwahed/Documents/Projects/CLMOne/.venv/bin/python manage.py test tests.test_dpa_workflow tests.test_dpa_review -v 2
DJANGO_SETTINGS_MODULE=config.settings_test /Users/haroonwahed/Documents/Projects/CLMOne/.venv/bin/python manage.py test tests.test_cross_tenant_isolation tests.test_permission_matrix tests.test_permissions tests.test_approval_authorization tests.test_approval_workflow tests.test_par_apr_001_approval tests.test_audit_integrity tests.test_workflow_audit_trail tests.test_workflow_template_versioning tests.test_document_versioning tests.test_par_doc_001_document_version tests.test_par_core_003_provenance tests.test_signature_workspace -v 2
```

The results are the run table above; the raw command output was captured during
the classification run. No production test, fixture, source, migration or
runtime configuration was modified.

## Register

Every failing/erroring test is named below. In a duplicate group, the first
test owns the described root cause and every subsequent named test is exactly
DUPLICATE_ROOT_CAUSE.

### C-01 — document lock writer (1)

| Field | Record |
| --- | --- |
| Test | tests.test_5i_document_durability.DeletionAuthorizationMatrixTests.test_admin_can_delete_ordinary_document |
| Classification | COMMERCIAL_V1_BLOCKER |
| Observed error | DocumentVersionError: Document field "file" is immutable after version lock while soft delete saves deletion fields only. |
| Root cause/evidence | Document.save() applies locked-file comparison before a permitted non-file mutation (contracts/models.py:1401; document_version_service.py:403). The same trace recurs across deletion and e-sign setup. |
| Commercial relationship | A final NDA must preserve immutable evidence while allowing governed tombstone/archive handling and binding a signature packet to the artifact. |
| Audit effect | Does not invalidate the current audit; it corroborates its non-launch conclusion. |
| Disposition | Fix only in the coherent vertical slice; prove locked artifact fields cannot mutate while permitted deletion/audit fields can. |

### D-01 — document lock duplicates (33)

DUPLICATE_ROOT_CAUSE; observed error, evidence, relationship, audit effect
and disposition are C-01.

* tests.test_5i_document_durability.DeletionAuthorizationMatrixTests.test_document_referenced_by_pending_approval_ordinary_policy
* tests.test_5i_document_durability.DeletionAuthorizationMatrixTests.test_legal_hold_on_client_blocks_deletion
* tests.test_5i_document_durability.DeletionAuthorizationMatrixTests.test_member_can_delete_own_upload
* tests.test_5i_document_durability.DeletionAuthorizationMatrixTests.test_owner_can_delete_ordinary_document
* tests.test_5i_document_durability.DeletionAuthorizationMatrixTests.test_released_legal_hold_does_not_block_deletion
* tests.test_5i_document_durability.DeletionAuthorizationMatrixTests.test_repeated_deletion_is_idempotent
* tests.test_5i_document_durability.DeletionAuthorizationMatrixTests.test_soft_delete_emits_chained_audit_event
* tests.test_5i_document_durability.DeletionAuthorizationMatrixTests.test_soft_delete_excludes_document_from_list
* tests.test_5i_document_durability.DeletionAuthorizationMatrixTests.test_soft_delete_makes_detail_page_404
* tests.test_5i_document_durability.DeletionAuthorizationMatrixTests.test_soft_delete_retains_db_row
* tests.test_5i_document_durability.EvidentiaryProtectionTests.test_cancelled_signature_request_does_not_block_deletion
* tests.test_5i_document_durability.EvidentiaryProtectionTests.test_declined_signature_request_does_not_block_deletion
* tests.test_5i_document_durability.EvidentiaryProtectionTests.test_draft_court_filing_can_be_deleted
* tests.test_5i_document_durability.EvidentiaryProtectionTests.test_draft_doc_on_executed_contract_can_be_deleted
* tests.test_5i_document_durability.EvidentiaryProtectionTests.test_final_correspondence_is_not_evidentiary_by_type
* tests.test_5i_document_durability.EvidentiaryProtectionTests.test_final_doc_on_drafting_contract_can_be_deleted
* tests.test_5i_document_durability.EvidentiaryProtectionTests.test_pending_signature_request_does_not_block_deletion
* tests.test_document_deletion.DeletionAuthorizationTests.test_admin_can_delete_any
* tests.test_document_deletion.DeletionAuthorizationTests.test_member_can_delete_own_upload
* tests.test_document_deletion.DeletionAuthorizationTests.test_owner_can_delete_any
* tests.test_document_deletion.DeletionRetentionTests.test_idempotent_repeat
* tests.test_document_deletion.DeletionRetentionTests.test_soft_delete_preserves_row_and_audits
* tests.test_document_deletion.DeletionVisibilityTests.test_deleted_detail_returns_404
* tests.test_document_deletion.DeletionVisibilityTests.test_deleted_excluded_from_list
* tests.test_esign_outbound.DocuSignProviderTests.test_builds_envelope_and_parses_envelope_id
* tests.test_esign_outbound.DocuSignProviderTests.test_factory_builds_docusign
* tests.test_esign_outbound.DocuSignProviderTests.test_missing_document_raises
* tests.test_esign_outbound.DocuSignProviderTests.test_unconfigured_raises
* tests.test_esign_outbound.DocumensoProviderTests.test_detail_exposes_webhook_free_refresh_action
* tests.test_esign_outbound.DocumensoProviderTests.test_factory_builds_documenso
* tests.test_esign_outbound.DocumensoProviderTests.test_refresh_maps_opened_recipient_to_viewed
* tests.test_esign_outbound.DocumensoProviderTests.test_v2_completed_webhook_marks_request_signed
* tests.test_esign_outbound.DocumensoProviderTests.test_v2_provider_creates_and_distributes_envelope

### B-01 — lifecycle/status fixture drift (1)

| Field | Record |
| --- | --- |
| Test | tests.test_5f_role_walkthrough.AdminJourneys.test_admin_cannot_self_approve_created_contract |
| Classification | PRE_EXISTING_BASELINE |
| Observed error | ValidationError: record status PENDING cannot pair with workflow stage DRAFTING. |
| Root cause/evidence | Legacy test construction omits a compatible lifecycle stage after status/stage separation (lifecycle_dimensions.py:187); recorded as known pre-existing refactor drift. |
| Commercial relationship / audit effect | Not an NDA execution result; the NDA builder creates compatible IN_PROGRESS / DRAFTING. Does not invalidate audit. |
| Disposition | Reconcile legacy fixtures separately; do not weaken state-pair validation. |

### D-02 — lifecycle/status duplicates (13)

DUPLICATE_ROOT_CAUSE; observed error, evidence and disposition are B-01.

* tests.test_5h_expiration_rehearsal.ExpirationEligibility.test_terminal_and_non_active_excluded
* tests.test_tasks_inbox.TasksRowComponentTests.test_row_renders_stage_dots_assignee_chip_and_activity_line
* tests.test_workflow_operations.WorkflowOperationsPageTests.test_designer_hub_owns_templates_and_routing
* tests.test_workflow_operations.WorkflowOperationsPageTests.test_filters_status_and_type
* tests.test_workflow_operations.WorkflowOperationsPageTests.test_operations_page_surface_and_tabs
* tests.test_workflow_operations.WorkflowOperationsPageTests.test_related_surfaces_share_hub_tabs
* tests.test_workflow_operations.WorkflowOperationsPageTests.test_row_maps_stage_type_business_unit_and_progress
* tests.test_workflow_operations.WorkflowOperationsPageTests.test_split_exception_from_title
* tests.test_5f_role_walkthrough.AdminJourneys.test_admin_can_create_contract_via_http
* tests.test_5f_role_walkthrough.CrossTenantNegative.test_bulk_transition_with_foreign_id
* tests.test_5f_role_walkthrough.CrossTenantNegative.test_contract_transition
* tests.test_contract_expiration.ContractExpirationTests.test_non_active_statuses_excluded
* tests.test_seed_demo_command.SeedDemoCommandTests.test_contracts_span_meaningful_lifecycle_states

### B-02 — established non-NDA drift (2)

| Test | Classification | Observed error, root, evidence, relationship and disposition |
| --- | --- | --- |
| tests.test_contract_detail_record_shell.ContractDetailMetadataHeaderTests.test_no_owner_renders_unassigned_not_a_crash | PRE_EXISTING_BASELINE | ProvenanceError when the test clears immutable created_by. The locked-provenance invariant is correct; the presentation fixture is stale. Not an NDA result; reconcile outside this tranche. |
| tests.test_contract_launch_setup.NewContractRequestPageTests.test_create_audit_records_derived_risk_and_routing | PRE_EXISTING_BASELINE | KeyError: risk_assessment because the legacy expected audit payload no longer matches the launch event. Generic launch audit, not end-to-end NDA proof; reconcile the documented event contract separately. |

### B-03 — stale presentation/routing assertions (30)

PRE_EXISTING_BASELINE. These tests observe renamed/recomposed surfaces,
redirect routes or fixture assumptions. They reproduced on the exact baseline,
do not prove an NDA invariant false, and do not invalidate the audit. Do not
change them until the owning surface contract is reviewed.

* tests.test_5f_role_walkthrough.CrossTenantNegative.test_client_detail
* tests.test_5f_role_walkthrough.CrossTenantNegative.test_guessed_and_altered_org_switch
* tests.test_5f_role_walkthrough.MemberJourneys.test_member_can_read_own_org
* tests.test_5f_role_walkthrough.StaleSessionAuthz.test_membership_removal_revokes_access_next_request
* tests.test_bolton_redesign.BoltonRedesignTestCase.test_contracts_list_filters_and_actions
* tests.test_bolton_redesign.BoltonRedesignTestCase.test_contracts_table_structure
* tests.test_bolton_redesign.BoltonRedesignTestCase.test_dashboard_panels
* tests.test_clmone_features.CLMOneFeaturesTests.test_contract_list_has_search_filter_and_table
* tests.test_command_center_in_house_clm.CommandCenterDashboardTests.test_dashboard_uses_persisted_command_center_model
* tests.test_command_center_in_house_clm.CommandCenterDashboardTests.test_priority_queue_and_right_rail_render
* tests.test_command_center_in_house_clm.CommandCenterDashboardTests.test_reference_command_center_shell_renders
* tests.test_command_center_operating_surface.CommandCenterProductionSurfaceTests.test_deadline_status_distinguishes_setup_from_clear
* tests.test_contract_launch_setup.NewContractRequestPageTests.test_new_request_create_ctas_use_standard_teal_button_treatment
* tests.test_contract_launch_setup.NewContractRequestPageTests.test_new_request_workflow_header_is_intake_first_and_compact
* tests.test_dashboard_work_queue.DashboardEmptyStateTests.test_onboarding_checklist_hidden_once_a_contract_exists
* tests.test_dashboard_work_queue.DashboardQueueRowContentTests.test_queue_rows_render_without_raw_enums_iso_timestamps_or_model_names
* tests.test_dpa_workflow.CommandCenterKanbanProjectionTests.test_generated_dpa_workflow_row_renders_workspace_operational_fields
* tests.test_dpa_workflow.DPAWorkflowBuilderViewIntegrationTests.test_intake_does_not_expose_pre_generation_governance_or_ai_controls
* tests.test_nda_workflow.NDAWorkflowBuilderIntegrationTests.test_command_center_row_links_back_to_generated_workspace
* tests.test_redesign_components.RedesignComponentsTestCase.test_contracts_list_core_components
* tests.test_redesign_layout.RedesignLayoutTests.test_dashboard_right_rail
* tests.test_repository_work_queue.LegacyContractListMigrationTests.test_legacy_list_still_works_and_links_to_repository
* tests.test_settings_hub.SettingsHubViewTests.test_hub_cards_point_to_real_destinations
* tests.test_settings_hub.SettingsHubViewTests.test_hub_renders_compact_groups_and_subtitle
* tests.test_tasks_inbox.TasksCopyQualityTests.test_empty_states_render_exact_specified_copy
* tests.test_ui_click_integrity.UIButtonAndFlowIntegrityTests.test_case_flow_semantics_on_high_traffic_pages
* tests.test_ui_click_integrity.UIButtonAndFlowIntegrityTests.test_click_targets_and_forms_are_wired_on_core_pages
* tests.test_workflow_cockpit_regression.WorkflowCockpitRegressionTests.test_reference_workflows_generate_records_and_render_workspaces
* tests.test_workflow_routing.WorkflowRoutingTests.test_workflow_dashboard_and_detail_surface_routing_endpoints
* tests.test_expressive_design_system.ExpressiveDesignSystemContractTests.test_reference_layer_uses_tokens_instead_of_page_hex_values

The three NDA/DPA assertions in B-03 are **stale assertions, not product
defects and not environment discrepancies**. The NDA CommandCenterWorkItem
still records self_serve_eligible; the current renderer no longer renders
literal Self-serve eligible. The DPA row exists (its companion test passes)
but no longer renders literal Draft. The DPA intake assertion bans the word
Governance anywhere, while shared navigation legitimately contains a Governance
section; it does not prove a prohibited intake control is present.

### U-01 — unrelated baseline failures (5)

UNRELATED_TO_COMMERCIAL_V1; all are non-NDA feature/fixture expectations and
do not invalidate the audit.

* tests.test_ai_clause_review_workflow.AIClauseReviewWorkflowTests.test_incomplete_review_is_truthful_and_surfaces_resolvable_blockers
* tests.test_mfa_policy.MfaPolicyTests.test_mfa_required_org_blocks_dashboard_until_profile_enabled
* tests.test_mfa_policy.MfaPolicyTests.test_recovery_codes_can_be_generated_and_used
* tests.test_phase11_backlog_amplifiers.Phase11BacklogAmplifiersTests.test_reassign_options_include_workload_and_sort
* tests.test_phase5l_notifications.RecoveryCodeServiceTests.test_profile_view_uses_canonical_service_for_recovery_code

### E-01 — external/feature fixture (1)

| Field | Record |
| --- | --- |
| Test | tests.test_upload_ocr_pipeline.TestDocumentUploadApiView.test_valid_txt_file_creates_document |
| Classification | ENVIRONMENT_OR_FIXTURE |
| Observed error | Expected 201; got 503. |
| Root/evidence | OCR processing is unavailable in the local feature-flagged test context; the route takes its 503 fallback. |
| Commercial relationship / disposition | Not the NDA journey and does not invalidate the audit. Reproduce against the declared OCR fixture before changing code or assertion. |

## Interpretation

The green 233-test invariant set is useful component evidence for tenant
isolation, authorization, append-only audit chaining, approvals, document
versions, signature workspace and provenance. It does not prove their
composition into an executable NDA. In particular, legacy workflow-template
tests do not make an is_active template selection an immutable published,
version-pinned workflow configuration. The audit remains evidence-limited and
its design-partner/non-launch conclusion stands.
