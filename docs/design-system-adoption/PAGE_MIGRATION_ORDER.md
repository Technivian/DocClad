# Page Migration Order

This order assumes the new reusable design system will be copied later under `src/design-system`, then adopted page-by-page without changing product logic.

## Migration Principles

- Start with low-risk pages that exercise shell/header/card/buttons.
- Move to list/table pages before dense form/workflow pages.
- Migrate mode-sensitive pages only after workspace-mode guardrails are green.
- Migrate workflow cockpits and generated workspaces only after stable form, rail, badge, table, and stepper primitives exist.

## Phase 0: Pre-Adoption

1. Copy design system into `src/design-system` in a separate commit.
2. Wire CSS/tokens behind a namespace or adapter layer.
3. Do not replace product templates yet.
4. Add a component demo route or update the existing styleguide to render isolated primitives.

## Phase 1: Low-Risk Shell and Static Pages

1. `settings_hub.html` - recommended first migration.
2. `400.html`, `403.html`, `404.html`, `500.html`.
3. `privacy.html`, `terms.html`.
4. `profile.html`.
5. Auth pages:
   - `registration/login.html`
   - `registration/register.html`
   - password reset templates
   - `contracts/mfa_challenge.html`
   - `contracts/mfa_enroll.html`
   - `contracts/saml_select.html`

Checks:

- `make check`
- `tests.test_registration`
- `tests.test_error_pages`
- `tests.test_mfa_policy`
- `tests.test_session_security`

## Phase 2: Simple Admin and Directory Lists

1. `contracts/organization_team.html`
2. `contracts/organization_activity.html`
3. `contracts/organization_session_audit.html`
4. `contracts/clause_category_list.html`
5. `contracts/counterparty_list.html`
6. `contracts/client_list.html`
7. `contracts/conflict_check_list.html`
8. `contracts/notification_list.html`

Checks:

- `tests.test_organization_invitations`
- `tests.test_audit_integrity`
- `tests.test_nav_law_firm_baseline`
- `tests.test_workspace_mode_containment`

## Phase 3: Simple Forms

1. `contracts/counterparty_form.html`
2. `contracts/client_form.html`
3. `contracts/clause_category_form.html`
4. `contracts/conflict_check_form.html`
5. `contracts/deadline_form.html`
6. `contracts/legal_task_form.html`
7. `contracts/risk_log_form.html`

Checks:

- `tests.test_form_validation_guardrails`
- `tests.test_tasks_form`
- `tests.test_deadline_admin`
- relevant module tests

## Phase 4: Repository, Contracts, Documents

1. `contracts/repository.html`
2. `contracts/contract_list.html`
3. `contracts/contract_detail.html`
4. `contracts/document_list.html`
5. `contracts/document_detail.html`
6. `contracts/document_form.html`
7. `contracts/document_compare.html`
8. `contracts/document_ocr_queue.html`
9. `contracts/document_ocr_review.html`

Checks:

- `tests.test_repository_cleanup_gate`
- `tests.test_repository_work_queue`
- `tests.test_contract_detail_record_shell`
- `tests.test_contract_required_fields`
- `tests.test_document_versioning`
- `tests.test_upload_ocr_pipeline`

## Phase 5: Approvals, Signatures, Obligations

1. `contracts/approval_request_list.html`
2. `contracts/approval_request_form.html`
3. `contracts/approval_rule_list.html`
4. `contracts/approval_rule_form.html`
5. `contracts/signature_request_list.html`
6. `contracts/signature_request_detail.html`
7. `contracts/signature_request_form.html`
8. `contracts/signature_packet_detail.html`
9. `contracts/obligations_workspace.html`
10. `contracts/deadline_list.html`

Checks:

- `tests.test_approvals_inbox`
- `tests.test_approval_authorization`
- `tests.test_approval_workflow`
- `tests.test_signature_workspace`
- `tests.test_esign_outbound`
- `tests.test_obligations_workspace`
- `tests.test_obligation_tracker`

## Phase 6: Golden CLM Surfaces

1. `contracts/contract_template_picker.html`
2. `dashboard.html` in `in_house_clm` mode
3. `dashboard.html` in `law_firm_ops` mode
4. Command Center Playwright smoke

Checks:

- `tests.test_draft_cockpit`
- `tests.test_contract_launch_setup`
- `tests.test_command_center_in_house_clm`
- `tests.test_demo_command_center`
- `client/tests/e2e/command-center-demo.spec.js`

## Phase 7: Workflow Cockpits and Workspaces

1. `contracts/msa_workflow_builder.html`
2. `contracts/nda_workflow_builder.html`
3. `contracts/dpa_workflow_builder.html`
4. `contracts/msa_contract_workspace.html`
5. `contracts/nda_contract_workspace.html`
6. `contracts/dpa_contract_workspace.html`
7. `contracts/workflow_detail.html`
8. `contracts/workflow_dashboard.html`
9. workflow template pages

Checks:

- `tests.test_msa_workflow`
- `tests.test_nda_workflow`
- `tests.test_dpa_workflow`
- `tests.test_workflow_cockpit_regression`
- `tests.test_workflow_execution`
- MSA/NDA/DPA Playwright smoke specs

## Phase 8: Privacy, Risk, DPA Review, Compliance

1. `contracts/privacy_dashboard.html`
2. privacy inventory CRUD pages
3. DSAR CRUD pages
4. subprocessor CRUD pages
5. transfer/retention/legal-hold pages
6. `contracts/legal_intelligence_hub.html`
7. `contracts/risk_log_list.html`
8. `contracts/dpa_review_pack_list.html`
9. `contracts/dpa_review_pack_detail.html`
10. `contracts/dpa_review_pack_memo.html`
11. `contracts/dpa_playbook_list.html`
12. compliance checklist pages

Checks:

- `tests.test_privacy_dashboard_layout`
- `tests.test_dsar_sla`
- `tests.test_subprocessor_alerts`
- `tests.test_risk_audit_layout`
- `tests.test_dpa_review`
- `tests.test_compliance_portal`
- `tests.test_workspace_mode_containment`

## Phase 9: Law-Firm Operational Modules

1. matter list/detail/form
2. due diligence pages
3. budget pages
4. invoice/time pages
5. trust account pages
6. trademark pages
7. ethical wall pages

Checks:

- `tests.test_matter_workspace_spine`
- `tests.test_billing`
- `tests.test_budget_access_policy`
- `tests.test_trust_account_permissions`
- `tests.test_nav_law_firm_baseline`

## Do Not Migrate First

- `dashboard.html`
- workflow cockpits
- generated contract workspaces
- `organization_security_settings.html`
- approval mutation/detail flows
- signature packet flows
- DPA review detail/memo generation

These have high business or permission risk and should wait until primitives are stable.
