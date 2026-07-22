# PAR-ID-001 — Resolver usage matrix

**Date:** 2026-07-22  
**Branch:** `cursor/feat-par-id-001-resolver-parity`  
**Baseline `main`:** `0d9712ca` (PR #55 shadow sync merged @ `bb881ac2`)  
**Authorization:** `RESOLVER_PARITY_IMPLEMENTATION_AUTHORIZATION.md` (**Authorized**)

Purpose: inventory production consumers that resolve actors for workflow, approval, signer, owner, and reviewer paths — prior to any comparison-mode implementation.

Legend:
- **comparison safety:** `parity-candidate` = safe to dual-run for diagnostics only; `workspace-only` = membership role, not process-role; `explicit-fk` = already user FK, not profile.role; `display-only` = labels/UI.
- **risk:** H / M / L if comparison or cutover were mishandled.

---

## A. Direct `UserProfile.role` process-role resolvers (primary parity targets)

| ID | Caller | Org context | Legacy source | Returned actor | Authz consequence | Canonical equivalent | Comparison safety | Risk |
|---|---|---|---|---|---|---|---|---|
| RES-WF-01 | `WorkflowTemplateStep.resolve_assignee` (`contracts/models.py`) | `contract.organization` via active memberships | `assignee_role` ↔ `user.profile.role` (first match); prefers `specific_assignee` | `User` or `None` | Sets workflow step assignee | `ProcessRoleAssignment` / Workflow Role Definition | **parity-candidate** | **H** |
| RES-WF-02 | `workflow_execution.materialize_workflow_from_template` → create steps | Workflow/contract org | Calls `resolve_assignee`; signature may use `fallback_signer` | Sets `WorkflowStep.assigned_to` | Later step work gated by contract EDIT / step UI | Runtime Role Assignment | **parity-candidate** | **H** |
| RES-WF-03 | `workflow_create` / launch / MSA·DPA·NDA materialize (`views_domains/workflow_management.py`, flagship workflows) | Org of launched workflow | Indirect via `resolve_assignee` | Step assignees at launch | Same | Runtime Role Assignment | **parity-candidate** | **H** |
| RES-WF-04 | `workflow_simulation._resolve_assignment` | Simulated contract org | Calls `resolve_assignee` | Display name or unresolved role | Preview only | Simulation Role Definition | **parity-candidate** | **M** |
| RES-APR-01 | `workflow_routing.resolve_rule_assignee` | `contract.organization` | `ApprovalRule.specific_approver` else `approver_role` ↔ `profile.role` | `User` or `None` | Becomes `ApprovalRequest.assigned_to` | Runtime Role Assignment | **parity-candidate** | **H** |
| RES-APR-02 | `workflow_routing.build_approval_request_plan_for_contract` | Contract org + active rules | Via `resolve_rule_assignee` | Plan rows with `assigned_to` | Creates pending approvals when consumed | Runtime Role Assignment | **parity-candidate** | **H** |
| RES-APR-03 | `ApprovalWorkflowService.initiate_approval_workflow` | Contract org | Plan from RES-APR-02 | Creates `ApprovalRequest` (+ canonical requirement) | Assignee/delegate/admin may decide | Runtime Role Assignment | **parity-candidate** | **H** |
| RES-APR-04 | `api/admin.approval_initiate_api` | Actor org-scoped contract | Via initiate | Same | Same | Runtime Role Assignment | **parity-candidate** | **H** |
| RES-APR-05 | `WorkflowCreateView.form_valid` / `workflow_create` direct plan create | Workflow contract org | Direct `build_approval_request_plan_for_contract` | `ApprovalRequest` via `get_or_create` | Same assignee authz once pending | Runtime Role Assignment | **parity-candidate** | **H** |
| RES-CFG-01 | `starter_content.STARTER_APPROVAL_RULES` / `ensure_org_starter_content` | New org | Seeds `approver_role` = PARTNER / SENIOR_ASSOCIATE | Config only until match | Future resolve uses profile.role | Workflow Role Definition (config) | **parity-candidate** | **M** |

---

## B. Explicit FK / workspace-role paths (not profile.role process resolution)

| ID | Caller | Org context | Legacy source | Returned actor | Authz consequence | Canonical equivalent | Comparison safety | Risk |
|---|---|---|---|---|---|---|---|---|
| RES-REV-01 | `drafting_submit_for_review` / MSA·DPA·NDA submit | Workflow org | Requires `ApprovalRule.specific_approver` for LEGAL/FINANCE/PRIVACY | Explicit reviewer `User` | Assignee authz; may set DPA pack reviewer | Runtime Role Assignment (explicit) | **explicit-fk** | **M** |
| RES-REV-02 | `contracts.contract_submit_for_review` | Actor org | POST `reviewer_id` among members | Chosen reviewer | Default LEGAL step assignee | Runtime Role Assignment (manual) | **explicit-fk** | **L** |
| RES-REV-03 | `ApprovalWorkflowService.submit_for_review` | Contract org | Explicit `reviewer` arg | `ApprovalRequest.assigned_to` | Assignee/admin decide | Runtime Role Assignment | **explicit-fk** | **M** |
| RES-AUTH-01 | `authorize_approval_actor` / `actor_can_decide` | Approval/contract org | `OrganizationMembership.role` OWNER/ADMIN **or** assignee/delegate | Boolean | Approve/reject/delegate gate; SoD vs owner | Permission Set + Delegation | **workspace-only** | **H** |
| RES-AUTH-02 | `ApprovalWorkflowService.delegate` / `reassign` + APIs + HTML update | Approval org | Membership / `can_manage_organization` | Updates assignee/delegate | Decision rights transfer | Delegation / Runtime Assignment | **workspace-only** / **explicit-fk** | **M** |
| RES-OWN-01 | Contract create/update owner defaults | Contract org | FK `Contract.owner` | Owner user | EDIT + SoD | Runtime Role Assignment `contract_owner` | **explicit-fk** | **M** |
| RES-OWN-02 | MSA renewal obligation / AI review defaults | Contract org | `contract.owner` | Deadline / finding assignee | Ownership of follow-up work | Runtime Role Assignment | **explicit-fk** | **L** |
| RES-PRIV-01 | `dpa_activation.ensure_dpa_review_pack` | Contract org | Latest `ApprovalRequest.assigned_to` | `DPAReviewPack.reviewer` | Seeds privacy reviewer FK | Runtime Role Assignment `privacy_reviewer` | **explicit-fk** | **M** |
| RES-PRIV-02 | `dpa_review._can_review_pack` / My Work privacy queues | Pack org | `reviewer_id` or workspace admin | Boolean / queue rows | Mutation / inbox visibility | Runtime Assignment + Workspace Role | **explicit-fk** / **workspace-only** | **M** |
| RES-SIGN-01 | `SignatureRequest.can_actor_transition` | Signature org | Email / creator / workspace admin; `signer_role` display-only | Boolean | SIGN/VIEW/DECLINE | Runtime Role Assignment `signer` | **display-only** / **workspace-only** | **L** |
| RES-SIGN-02 | Workflow signature `fallback_signer` | Template org | Explicit FK | Step `assigned_to` | Signature step assignee | Runtime Role Assignment `signer` | **explicit-fk** | **M** |
| RES-FIN-01 | `finance_approval_policy.requires_finance_approval` | Org reserved | Threshold; label text only | `(required, reason, audit)` | Whether FINANCE step needed — **not who** | Workflow Role Definition `finance_approver` | **display-only** | **L** |
| RES-NOTIF-01 | Workflow / contract / signature reminder recipients | Org | Workspace OWNER/ADMIN + assignees/creators | Notification recipients | Notify (+ some escalate status) | Workspace Role + Runtime Assignment | **workspace-only** | **M** |
| RES-JOB-01 | `approval_escalate_overdue_api` / escalate overdue steps | Org / all orgs | Pending overdue rows; no profile.role resolve | Status / notifications | Escalation | System + Runtime Assignment | **n/a** | **M** |
| RES-ADM-01 | Org admin / SCIM / SAML membership writers | Target org | Write `OrganizationMembership.role` only | Membership | Workspace privileges; **never** process role | Workspace Role | **workspace-only** (must not shadow as process) | **H** if conflated |

---

## C. Non-runtime / diagnostic (already non-authoritative)

| ID | Caller | Notes |
|---|---|---|
| RES-DIAG-01 | `dual_read_process_roles` / `process_role_parity_report` / shadow sync | Reads `UserProfile.role`; `authoritative_for_runtime=False` |
| RES-DIAG-02 | `UserProfile.can_approve` / `is_attorney` | Profile.role helpers; **no production callers** found |

---

## D. Comparison-mode candidate set (when authorized)

Implement comparison **only** for parity-candidate rows that still match on `UserProfile.role`:

1. `WorkflowTemplateStep.resolve_assignee` (RES-WF-01…04 chain)
2. `workflow_routing.resolve_rule_assignee` (RES-APR-01…05 chain)

Do **not** compare workspace membership ADMIN/OWNER/MEMBER as process roles.  
Do **not** change return values.  
Do **not** auto-repair assignments.

---

## E. Cutover-readiness criteria (future; not this slice)

Resolver cutover may be proposed only when all are true under separate authorization:

1. Shadow sync + assignment parity critical drift = 0 in staging for target orgs.
2. Resolver comparison shows no H-risk DIFFERENT_USER / CROSS_TENANT_ANOMALY for candidate paths.
3. Ambiguous ADMIN cases explicitly classified and accepted.
4. Threat review + rollback plan accepted.
5. Feature-flagged dual-return / privilege cutover separately authorized.
6. Legacy resolvers remain available until cutover criteria met.
