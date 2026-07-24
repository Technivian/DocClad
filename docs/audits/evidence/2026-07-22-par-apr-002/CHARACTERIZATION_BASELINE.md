# PAR-APR-002 — characterization baseline

**Scope:** default-off, non-authoritative evidence under the expiring
characterization exception. `ApprovalRequest` remains authoritative. This
record neither enables a feature nor changes a resolver, permission, write
path, or read authority.

## Method and count reconciliation

The baseline phrase "40 non-migration references" was checked against the
current source tree. There are **40 source-reference files total**:

- **37 runtime/support files**; and
- **3 historical migration files** (`0002`, `0006`, and `0111`).

The three migrations are retained history, not live cutover targets. The 37
runtime/support files and the 3 historical files are all included below so the
matrix accounts for the complete 40-file reference set.

## Ownership matrix

| # | File | Owner / dependency | Current role | Cutover disposition |
|---:|---|---|---|---|
| 1 | `contracts/admin.py` | Approval administration | Admin registration/display | Characterize; legacy retained |
| 2 | `contracts/api/_helpers.py` | API shared imports | API dependency surface | Characterize; no API change |
| 3 | `contracts/api/admin.py` | Operations API | Approval lookup/action API | Characterize; legacy retained |
| 4 | `contracts/api/analytics.py` | Analytics API | Shared API dependency | Characterize |
| 5 | `contracts/api/contracts_endpoints.py` | Contract API | Shared API dependency | Characterize |
| 6 | `contracts/api/documents_ai.py` | AI exception flow | Opens/mentions human approval requests | AI remains non-authoritative |
| 7 | `contracts/api/integrations.py` | Integrations API | Shared API dependency | Characterize |
| 8 | `contracts/api/obligations_dsar_jobs.py` | Privacy/obligation API | Shared API dependency | Characterize |
| 9 | `contracts/api/scim.py` | SCIM API | Shared API dependency | Characterize |
| 10 | `contracts/forms.py` | Approval forms | Legacy form model surface | Characterize UI/API dependency |
| 11 | `contracts/management/commands/audit_null_organizations.py` | Tenant audit | Audits legacy tenant-owned rows | Preserve; not a read cutover |
| 12 | `contracts/management/commands/seed_demo.py` | Demo seed | Creates seed approvals | Characterize seed dependency |
| 13 | `contracts/management/commands/seed_payrollminds_demo.py` | Demo seed | Creates seed approvals | Characterize seed dependency |
| 14 | `contracts/management/commands/send_contract_reminders.py` | Operations job | Legacy approval reminder query | Characterize operations dependency |
| 15 | `contracts/migrations/0002_clausecategory_counterparty_contract_currency_and_more.py` | Migration history | Historical model reference | Retain unchanged |
| 16 | `contracts/migrations/0006_approvalrequest_organization_and_more.py` | Migration history | Introduces tenant field | Retain unchanged |
| 17 | `contracts/migrations/0111_approval_requirement_decision.py` | Canonical foundation migration | Creates legacy-to-canonical relation | Retain unchanged |
| 18 | `contracts/models.py` | Approval domain | Legacy model and canonical linkage | Legacy authoritative |
| 19 | `contracts/services/ai_actions.py` | AI workflow | Legacy approval guard/reference | AI remains non-authoritative |
| 20 | `contracts/services/approval_canonical.py` | Canonical approval service | Creates/mirrors requirements and decisions | Canonical evidence, not read authority |
| 21 | `contracts/services/approval_workflow.py` | Approval workflow | Legacy DTO, reads, writes, action service | Primary characterization boundary |
| 22 | `contracts/services/assignments.py` | Assignment service | Approval-related assignment dependency | Characterize |
| 23 | `contracts/services/command_center.py` | Command Center | Pending legacy approval projection | Characterize projection |
| 24 | `contracts/services/contract_detail_workspace.py` | Contract workspace | Approval display dependency | Characterize UI dependency |
| 25 | `contracts/services/contract_lifecycle.py` | Lifecycle/signature | Requires legacy approval status alongside canonical requirements | Read cutover blocker |
| 26 | `contracts/services/dpa_activation.py` | Privacy activation | Checks legacy approval state | DPA reconciliation residual |
| 27 | `contracts/services/legal_signals.py` | Legal signals | Approval signal dependency | Characterize |
| 28 | `contracts/services/pilot_monitoring.py` | Monitoring | Legacy approval metrics/reference | Characterize operations dependency |
| 29 | `contracts/services/queue_rows.py` | My Work queue | Pending legacy approval queue rows | Inbox/read dependency |
| 30 | `contracts/services/work_instrumentation.py` | Work metrics | Legacy approval instrumentation | Characterize operations dependency |
| 31 | `contracts/services/workflow_operations.py` | Workflow runtime | Pending legacy approval guard | Workflow dependency |
| 32 | `contracts/services/workflow_routing.py` | Workflow routing | Builds legacy approval-request plans | Route mapping residual |
| 33 | `contracts/templatetags/clmone_format.py` | Template formatting | Legacy approval status formatting | UI dependency |
| 34 | `contracts/view_support.py` | View support | Approval support/context dependency | Characterize |
| 35 | `contracts/views.py` | Legacy views | Approval route/view dependency | Characterize UI/API dependency |
| 36 | `contracts/views_domains/client_matter_document.py` | Document workspace | Approval dependency | Characterize |
| 37 | `contracts/views_domains/contracts.py` | Contract views | Approval dependency | Characterize |
| 38 | `contracts/views_domains/core.py` | Core views | Approval dependency | Characterize |
| 39 | `contracts/views_domains/privacy_approvals.py` | Approval inbox/actions | Direct legacy list, detail, edit, and action surface | Primary inbox/UI dependency |
| 40 | `contracts/views_domains/workflow_management.py` | Workflow UI | Creates, lists, and audits legacy approvals | Primary workflow/UI dependency |

## Characterized current behaviour

- Creating a legacy `ApprovalRequest` creates a linked canonical
  `ApprovalRequirement` with open status.
- The workflow approval service records an immutable canonical decision while
  updating the linked legacy request to its legacy status. The default runtime
  DTOs, inbox, lifecycle, routing, queues, and projections still use the
  legacy model.
- Lifecycle signature/activation checks retain a legacy approval-status gate;
  they are not eligible for a canonical read switch in this slice.
- Tenant authorization is enforced by the approval service before legacy
  actions; the characterization suite does not alter it.

## Residual inventory

| Area | Verified residual | Status |
|---|---|---|
| DPA | `DPAReviewPack.approval_status` remains a parallel specialist state; `dpa_activation` reads `ApprovalRequest` | Reconciliation planned |
| Routes | `ApprovalRoute` template configuration is not mapped as a first-class canonical runtime requirement | Reconciliation planned |
| Inbox/UI | Privacy approval inbox and actions are modelled directly on `ApprovalRequest` | Read cutover blocked |
| Lifecycle | Signature and activation require legacy status in addition to canonical state | Read cutover blocked |
| API/operations | API, queues, Command Center, reminders, seeds, and monitoring retain legacy dependencies | Ownership captured |
| ABSTAIN | `ApprovalDecision` has an outcome, but `record_approval_decision` has no `abstain` action and no UI/API action | Missing |
| REVOKE | Revocation is used for invalidation, but there is no explicit reviewer UI/API `revoke` action | Missing |

## Rollback and cutover prerequisites

- This characterization change has no runtime behaviour; rollback is a normal
  commit revert.
- Before any reconciliation, the owners must separately authorize the exact
  residual slice and define parity acceptance criteria.
- Before a read cutover, a separately authorized, reversible plan must cover
  lifecycle, inbox, API, operations, DPA, route mapping, tenant isolation,
  authorization, mismatch handling, observation, and rollback.
- Before retirement, the independent Product, Engineering, and Security review
  requirements and a release record remain mandatory.

## Verification record

- `tests.test_par_apr_002_cutover_baseline`: **3/3 passed**.
- Focused approval, authorization, inbox, lifecycle, and workflow selection:
  **86/87 passed**. The sole failure remains
  `WorkflowRoutingTests.test_workflow_dashboard_and_detail_surface_routing_endpoints`,
  which expects the rendered dashboard not to contain `/contracts/approval-rules/`.
  The characterization PR does not touch that dashboard or routing surface; the
  failure is retained as the pre-existing assertion drift recorded in the
  programme baseline.
