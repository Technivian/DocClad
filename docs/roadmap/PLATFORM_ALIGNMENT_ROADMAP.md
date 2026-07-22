# Platform Alignment Roadmap

**Created:** 2026-07-21  
**Last refined:** 2026-07-22 (Tranche-1 integration / PR-scope normalization)  
**Authority:** Gap audit `docs/audits/2026-07-21-platform-gap-audit.md` · active `docs/governance/GOVERNANCE_CHARTER.md` · Accepted PDR-0003  
**Branch:** `main` @ Tranche-1 merge (`c52d699a`) · PAR-APR follow-up: `cursor/feat-par-apr-001-foundation-governance`  
**Living document:** update statuses only with implementation, tests, audit evidence, migration evidence (if any), documentation, and rollback proof.

Statuses: Completed · In progress · Blocked · Deferred by approved decision · Future roadmap · Cancelled with rationale

---

## Catalogue count (reconciled)

| Rollup | Count | Notes |
|---|---:|---|
| **Unique PAR IDs in this roadmap** | **24** | All distinct `PAR-*` identifiers below |
| Completed unique PAR IDs | 14 | Includes `PAR-AUD-001`, `PAR-CORE-001`, `PAR-CORE-003`, `PAR-CORE-002`, `PAR-DOC-001`, `PAR-APR-001`, `PAR-SEC-003` |
| In progress | 1 | `PAR-ID-001` — Role Definition reconciliation (Milestone 3) |
| Future / residual unique PAR IDs | 9 | Includes `PAR-SEC-002` (PAR-SEC-003 Closed) |
| Non-PAR Milestone 1 follow-ups | 1 | Playwright DPA bootstrap (`M1-E2E-001`) |

### Bundling rule for `PAR-AUD-001`

`PAR-AUD-001` remains intentionally bundled with `PAR-WF-001` for delivery and is **included** in the unique total of **24**.

### Unique PAR ID inventory

**Completed (14):** `PAR-WF-001`, `PAR-AUD-001`, `PAR-WF-002`, `PAR-WF-003`, `PAR-WF-005`, `PAR-NAV-001`, `PAR-SEC-001`, `PAR-WORK-001`, `PAR-CORE-001`, `PAR-CORE-003`, `PAR-CORE-002`, `PAR-DOC-001`, `PAR-APR-001`, `PAR-SEC-003`

**In progress (1):** `PAR-ID-001`

**Future / residual (9):** `PAR-SEC-002`, `PAR-WF-010`, `PAR-EXC-001`, `PAR-DATA-001`, `PAR-OBL-001`, `PAR-OBL-002`, `PAR-AI-001`, `PAR-ENT-001`, `PAR-INT-001`

**Blocked (1):** `PAR-WF-010` — discovery complete; production cutover blocked pending Accepted ADR-0012

---

## Immediate next items

1. **PAR-ID-001** — Role Definition reconciliation (Milestone 3) — **In progress** (canonical authority **implemented** default-off on PR #62; **activation pending**; legacy retained; ADMIN deferred)
2. **PAR-APR-002** — legacy approval cutover — **Planned** (blocked on owner + cutover plan)
3. **PAR-WF-010** — production cutover **blocked** pending Accepted ADR-0012 (discovery complete — see evidence)

Parallel Milestone 1 hygiene:

- `M1-E2E-001` Fix Playwright DPA bootstrap
- `PAR-SEC-002` Uniform authz / client-hide ≠ authorization

---

## Completed this programme

| ID | Title | Class | Notes |
|---|---|---|---|
| PAR-WF-001 | Enforce published template mutate gates | Foundation | UpdateView + Admin locked |
| PAR-AUD-001 | Admin published immutability | Foundation | **Bundled with PAR-WF-001**; distinct catalogue ID |
| PAR-WF-002 | Govern live instance template migration | Foundation | Reason + AuditLog; Proposed ADR-0010 (non-authorizing) |
| PAR-WF-003 | Default new templates unpublished | Foundation | Model + migration 0105 |
| PAR-WF-005 | Workflow invariant tests | Foundation | `tests/test_platform_workflow_invariants.py` |
| PAR-NAV-001 | Data Manager + Entities nav | Pilot hardening | Hub + Counterparty as Entities |
| PAR-SEC-001 | Auth redirect / isolation defects | Pilot hardening | **Completed** — auth bypass + tenant activity check. Residual list assertion is **PAR-SEC-003** (not attached here). |
| PAR-WORK-001 | My Work vs Command Center boundaries | Pilot hardening | `docs/product/MY_WORK_AND_COMMAND_CENTER_BOUNDARIES.md` |
| PAR-CORE-001 | PDR-0002 lifecycle vocabulary + ownership | Pilot hardening | **Completed** 2026-07-22 |

---

## Proposed decisions (awaiting approval)

| ID | Title | Status |
|---|---|---|
| ADR-0010 | Workflow instance version pinning interim | **Proposed** — `docs/governance/decisions/adr/0010-workflow-instance-version-pinning-interim.md`. Non-authorizing until Accepted. Interim pinning only. |
| ADR-0012 | Workflow Definition aggregate and cutover | **Proposed** — `docs/governance/decisions/adr/0012-workflow-definition-aggregate-cutover.md`. Required for PAR-WF-010 production cutover. |
| ADR-0013 | Approval Requirement / Decision split | **Accepted** — `docs/governance/decisions/adr/0013-approval-requirement-decision-split.md`. Foundation scope only; PAR-APR-002 required for legacy cutover. |
| ADR-0014 | Role Definition reconciliation | **Accepted** — `docs/governance/decisions/adr/0014-role-definition-reconciliation.md`. Target model + additive catalogue; privilege/resolver cutover requires separate authorization. |

---

## Blocked (external / governance)

| Item | Why |
|---|---|
| Charter v3 activation | Separate constitutional review and formal Charter amendment approval required. PDR-0003 does not approve Charter v3. |
| Production Definition/Version cutover | Needs **Accepted ADR-0012** (ADR-0010 alone insufficient) + ops window |
| External IdP production credentials | External dependency |
| Commercial vuln-scan SaaS evidence | External tooling |

---

## Future milestones (ordered)

### Milestone 1 — Finish pilot hardening

| ID / work | Title | Priority | Status |
|---|---|---|---|
| **PAR-CORE-001** | Complete remaining PDR-0002 UI/test drift | P0 | **Completed** |
| **PAR-SEC-002** | Uniform authz for search/analytics/AI; client-hide ≠ authorization | P1 | Future |
| **PAR-SEC-003** | Stale ContractIsolationTest repository-redirect assertion | P1 | **Closed** |
| M1-E2E-001 | Fix Playwright DPA bootstrap | P1 | Future (non-PAR) |

### Milestone 2 — Canonical contract core

| ID | Title | Priority | Status |
|---|---|---|---|
| **PAR-CORE-003** | Contract Record provenance completeness | P0 (after CORE-001) | **Completed** |
| **PAR-CORE-002** | Dual ContractType enum vs model (G-DOM-02) | P0 (before WF-010 cutover) | **Completed** |
| **PAR-DOC-001** | Document Version entity harden | P0 | **Completed** |
| **PAR-WF-010** | Workflow Definition aggregate | P0 (Accepted ADR required for cutover) | **Blocked** (discovery complete) |

### Milestone 3 — Authority and decision models

| ID | Title | Priority | Status |
|---|---|---|---|
| PAR-APR-001 | Approval Requirement/Decision split | P1 | **Completed** |
| PAR-APR-002 | Legacy approval cutover | P1 | **Planned** |
| PAR-ID-001 | Role Definition reconciliation | P1 | **In progress** |
| PAR-EXC-001 | Governed Exception | P1 | Future |

### Milestone 4 — Canonical data and post-signature

| ID | Title | Priority |
|---|---|---|
| PAR-DATA-001 | Property Definition CRUD | P1 |
| PAR-OBL-001 | First-class Obligation | P1 |
| PAR-OBL-002 | Reminder object | P2 |

### Milestone 5 — Intelligence and enterprise

| ID | Title | Priority |
|---|---|---|
| PAR-AI-001 | AI Suggestion provenance | P2 |
| PAR-ENT-001 | Entity Relationship graph | P2 |
| PAR-INT-001 | Generic Integration Connection | P2 |

---

## Item detail (completed) — preserved history

### PAR-WF-001 / PAR-AUD-001 — Completed

Published templates cannot be edited via UpdateView or Admin; must clone/unpublish via product paths. `PAR-AUD-001` delivered in the same change set (Admin save/readonly guards).

- Evidence: PR #48 behaviour commits; `tests/test_platform_workflow_invariants.py`; Admin guards in `contracts/admin.py`
- Last updated: 2026-07-21

### PAR-WF-002 — Completed

`migrate_workflows_to_template` requires `reason`, emits AuditLog `workflow_instance_template_migrated`; management command requires `--migration-reason`.

- Related: Proposed ADR-0010 (documentation only; not Accepted)
- Last updated: 2026-07-21

### PAR-WF-003 — Completed

`WorkflowTemplate.is_active` default `False`; migration `0105_workflowtemplate_is_active_default_false.py` (AlterField-only).

- Gate proof: `tests/test_migration_0105_gate_proof.py`; evidence `docs/audits/evidence/2026-07-22-pr48-merge-gate/`
- Last updated: 2026-07-22

### PAR-WF-005 — Completed

Invariant suite covers defaults, mutate gate, simulation dry-run, migration audit, publish validation block.

- Last updated: 2026-07-21

### PAR-NAV-001 — Completed

Nav: Data Manager → `/contracts/data-manager/`; Entities → counterparties list. Hub documents Property Definition gap.

- Last updated: 2026-07-21

### PAR-SEC-001 — Completed

`ContractListView` / `DeadlineListView` authenticate before alias redirect; `workflow_template_activity` tenant-checks before redirect. Isolation suite improved from 5 failures → 1 residual stale assertion, now tracked only under **PAR-SEC-003** (not unfinished work on this Completed item).

- Last updated: 2026-07-22

### PAR-WORK-001 — Completed

Boundary doc published; no semantic merge of My Work and Command Center.

- Doc: `docs/product/MY_WORK_AND_COMMAND_CENTER_BOUNDARIES.md`
- Last updated: 2026-07-21

---

## Milestone 1 detail — Finish pilot hardening

### PAR-CORE-001 — Complete remaining PDR-0002 UI/test drift

| Field | Content |
|---|---|
| Status **before** | In progress |
| Status **after** | **Completed** |
| Priority | P0 |
| Problem | PDR-0002 vocabulary/ownership drift across UI, imports, document supersede, and raw saves. |
| Governance source | Accepted **PDR-0002** |
| Work completed | Vocabulary slices + ownership close-out: Salesforce/NetSuite/CSV/inbound via `persist_contract_with_imported_lifecycle`; `document.superseded` audit; `Contract.save` pair protection |
| Decision impact | None — stayed within Accepted PDR-0002 |
| Remaining limitations | `QuerySet.update`/`bulk_update` bypass `Model.save` (no DB CHECK); legacy list stage-filter query keys retained as aliases |
| Migration impact | **None** |
| Security and permissions impact | Cross-tenant supersede denied; bulk stage still permissioned via lifecycle service |
| Audit requirements | `contract.operational_position_changed`, `contract.lifecycle_stage_changed`, `document.superseded` |
| Tests | `tests/test_pdr0002_core001.py`, `tests/test_pdr0002_core001_ownership.py`, inbound/document/lifecycle suites — ownership-suite **88 OK** |
| Rollback strategy | Revert commits; no schema migration |
| Acceptance criteria | Checklist all Compliant for in-scope writers — **met** |
| Evidence | `docs/audits/evidence/2026-07-22-par-core-001/` |
| PR/commits | `cursor/feat-platform-documentation-alignment-d7f1` |
| Next roadmap item | **PAR-DOC-001** |
| Last updated | 2026-07-22 |

### M1-E2E-001 — Fix Playwright DPA bootstrap

| Field | Content |
|---|---|
| Status | Future roadmap (Milestone 1 operational) — **not a PAR ID** |
| Priority | P1 |
| Problem | E2E `start_e2e_server.sh` → `seed_demo_command_center` raises `WorkflowLaunchBlocked` because seeded DPA template required steps lack assignees. |
| Governance source | WORKFLOW_ENGINE launch invariants; PR #48 merge-gate known failure catalog |
| Current evidence | `docs/audits/evidence/2026-07-22-pr48-merge-gate/playwright-pilot-gate.txt`; `e2e-seed-demo.txt`; prior green run `docs/audits/evidence/2026-07-20-pilot-verification/` |
| Target outcome | Fresh e2e DB migrate + seed boots server; critical `pilot-gate` / pilot verification Playwright can run |
| Dependencies | Seeded DPA/MSA/NDA templates remain `is_active=True`; assignee or fallback-signer policy |
| Decision required | None (fixture fix); do not weaken launch safety to greenwash tests |
| Migration impact | None (fixture/seed only) |
| Security and permissions impact | None |
| Audit requirements | None beyond existing launch/audit paths |
| UX requirements | None |
| Tests | Playwright pilot-gate critical paths green twice consecutively when required by pilot ops |
| Rollback strategy | Revert seed fixture commit |
| Acceptance criteria | `scripts/start_e2e_server.sh` reaches `runserver`; documented Playwright suite runs without bootstrap failure |
| Evidence | TBD |
| PR/commits | TBD |
| Last updated | 2026-07-22 |

### PAR-SEC-003 — Close stale ContractIsolationTest assertion

| Field | Content |
|---|---|
| Status | **Closed** (2026-07-22) |
| Priority | P1 |
| Problem | `ContractIsolationTest.test_list_shows_only_own_org` expected HTTP 200 on legacy `contract_list`; product intentionally 302-redirects to repository. |
| Resolution | Test asserts 302 → repository and verifies org isolation on the canonical repository surface. |
| Fix commit | `d9ded244` (merged via Tranche-1 / PR #50 lineage) |
| Tests | Full `test_cross_tenant_isolation` **75/75 PASS** |
| Evidence | `docs/audits/evidence/2026-07-22-par-sec-003/CLOSURE.md` |
| Programme isolation | Proven for additive PAR-ID catalogue slice; does **not** authorize privilege cutover |
| Last updated | 2026-07-22 |

### PAR-SEC-002 — Uniform authz for search / analytics / AI

| Field | Content |
|---|---|
| Status | Future roadmap (Milestone 1) — **not Completed** |
| Priority | P1 |
| Milestone | 1 — Finish pilot hardening |
| Problem | Gap audit rows: same access rules for search/analytics/AI are mixed; client-side hide is not authorization (GUARDRAILS §6). |
| Governance source | `docs/architecture/SECURITY_PRIVACY_ACCESS_AND_AUDIT.md`; ENGINEERING_GUARDRAILS; gap audit matrix → PAR-SEC-002 |
| Current evidence | Tenancy helpers mixed; AI kill switch in pilot middleware; gap audit Partially compliant |
| Target outcome | Search, analytics, and AI endpoints enforce the same tenant + permission rules as primary contract APIs; UI hide never substitutes for server checks |
| Dependencies | Inventory of search/AI/analytics routes; may touch `PAR-AI-001` surfaces without claiming AI provenance complete |
| Decision required | None for enforcement parity; ADR only if new permission model introduced |
| Migration impact | None expected |
| Security and permissions impact | **High** — close authz gaps; regression tests mandatory |
| Audit requirements | Denied cross-tenant access attempts remain free of contract content in logs |
| UX requirements | Forbidden/empty states honest; no “hidden but callable” controls |
| Tests | Cross-tenant + unauthenticated tests for search/AI/analytics; permission matrix |
| Rollback strategy | Revert authz harden commits behind flags if needed |
| Acceptance criteria | Matrix rows for uniform authz and client-hide≠authz move to Compliant for in-scope routes; tests green |
| Evidence | TBD |
| PR/commits | TBD |
| Last updated | 2026-07-22 |

---

## Milestone 2 detail — Canonical contract core

### PAR-CORE-003 — Contract Record provenance completeness

| Field | Content |
|---|---|
| Status | **Completed** |
| Priority | P0 after PAR-CORE-001 |
| Problem | Contract Record provenance is partial (creator/org present; workflow/document/event linkage incomplete vs domain invariants). |
| Governance source | CANONICAL_DOMAIN_MODEL invariants; gap audit PAR-CORE-003 / G provenance row |
| Current evidence | `contracts.models.Contract` provenance fields; `contracts/services/contract_provenance.py`; evidence `docs/audits/evidence/2026-07-22-par-core-003/` |
| Target outcome | Every material Contract Record carries required provenance (org, creator, governing workflow version when applicable, source events) with queryable history |
| Dependencies | Prefer after PAR-CORE-001 vocabulary stability; may touch Document/Workflow FKs |
| Decision required | None for incremental fields; schema reshape may need ADR |
| Migration impact | Additive `0106_contract_record_provenance`; truthful backfill; reversible RunPython |
| Security and permissions impact | Provenance visible only within tenant; repair requires OWNER/ADMIN/staff; no cross-org repair |
| Audit requirements | `contract.record.created`, `contract.record.provenance_assigned`, `contract.record.provenance_repaired` (+ retained equivalents) |
| UX requirements | Record header/history surfaces show provenance without cluttering pilot hero flows (server slice first; UI panel residual) |
| Tests | `tests/test_par_core_003_provenance.py` (19 OK) + ownership suite regression |
| Rollback strategy | Reverse migration 0106; proven rollback + re-forward |
| Acceptance criteria | Domain provenance checklist green for in-scope fields; tests + migration evidence + rollback proof |
| Evidence | `docs/audits/evidence/2026-07-22-par-core-003/` |
| PR/commits | Branch `cursor/feat-platform-documentation-alignment-d7f1` |
| Last updated | 2026-07-22 |


### PAR-CORE-002 — Dual ContractType enum vs ContractType model (G-DOM-02)

| Field | Content |
|---|---|
| Status | **Completed** |
| Priority | P0 after PAR-CORE-003; **before any Workflow Definition production cutover (`PAR-WF-010`)** |
| Problem | Two type systems coexist: `Contract.ContractType` TextChoices on the contract row and a separate `ContractType` model used by workflow templates / builders — duplicate source of truth (gap **G-DOM-02**). |
| Governance source | CANONICAL_DOMAIN_MODEL §2.6; gap audit G-DOM-02 |
| Resolution | `ContractType` model catalogue canonical; `Contract.contract_type_catalogue` FK; char field transitional mirror synced on save |
| Decision record | **Proposed ADR-0011** (CharField removal gate — not Accepted) |
| Current evidence | `contracts/services/contract_type_catalogue.py`; migration `0107`; `docs/audits/evidence/2026-07-22-par-core-002/` |
| Migration impact | `0107_contract_type_catalogue_fk` — seed 21 rows; backfill FK; rollback proven |
| Security and permissions impact | Catalogue global; repairs OWNER/ADMIN/staff; tenant isolation on contract rows |
| Audit requirements | `contract.type.catalogue.*`, `contract_type.catalogue.updated` |
| Tests | `tests/test_par_core_002_contract_type.py` (14 OK) + regression suites |
| Rollback strategy | Reverse 0107; char field remains authoritative for legacy readers |
| Acceptance criteria | Canonical write path; legacy mapped; historical truthful; tests + migration proof — **met** (char removal deferred per ADR-0011) |
| Evidence | `docs/audits/evidence/2026-07-22-par-core-002/` |
| PR/commits | Branch `cursor/feat-platform-documentation-alignment-d7f1` |
| Last updated | 2026-07-22 |

### PAR-DOC-001 — Document Version entity harden

| Field | Content |
|---|---|
| Status | **Completed** (2026-07-22) |
| Priority | P0 after PAR-CORE-003 |
| Problem | Document Version is partially modelled (`version` int + parent) and not fully immutable as required by domain. |
| Governance source | CANONICAL_DOMAIN_MODEL §2.16 / invariant “Document Version is immutable” |
| Resolution | Additive `DocumentVersion` entity + `create_document_version()` service; immutability guards; truthful legacy backfill |
| Current evidence | `docs/audits/evidence/2026-07-22-par-doc-001/` |
| Target outcome | Immutable Document Version semantics: edits create new versions; historical versions read-only; signatures bind to version |
| Dependencies | PAR-CORE-003 provenance; PAR-APR-001 later for approval binding depth |
| Decision required | Expand-contract pattern (no table split ADR required) |
| Migration impact | `0108_document_version_entity`, `0109_signature_request_document_version`; rollback/re-forward proven |
| Security and permissions impact | Tenant checks in service; QuerySet.update guards |
| Audit requirements | `document.version.created`, `document.version.marked_final`; reuse `document.superseded` |
| UX requirements | Version compare unchanged; edits create new version rows |
| Tests | `tests/test_par_doc_001_document_version.py` (14 OK) + `tests/test_document_versioning.py` |
| Rollback strategy | Reverse 0109 → 0108; clear `DocumentVersion` rows |
| Acceptance criteria | Production upload/edit paths use service; immutability enforced; signatures pin version — **met** (approval FK deferred) |
| Evidence | `docs/audits/evidence/2026-07-22-par-doc-001/` |
| PR/commits | Branch `cursor/feat-platform-documentation-alignment-d7f1` |
| Last updated | 2026-07-22 |

### PAR-WF-010 — Workflow Definition aggregate

| Field | Content |
|---|---|
| Status | **Blocked pending architecture approval** — discovery/design complete 2026-07-22; **not Completed** |
| Priority | P0 after PAR-DOC-001 |
| Problem | No first-class Workflow Definition; versions are `WorkflowTemplate` rows — conflicts with Definition → Version → Instance chain. |
| Governance source | CANONICAL_DOMAIN_MODEL; WORKFLOW_ENGINE_AND_DESIGNER; ADR-0010 interim only (Proposed, non-authorizing) |
| Discovery evidence | `docs/audits/evidence/2026-07-22-par-wf-010/` — matrix, target aggregate, cutover plan, risks, characterization tests |
| Proposed ADR | **ADR-0012** (`docs/governance/decisions/adr/0012-workflow-definition-aggregate-cutover.md`) — **Proposed, not Accepted** |
| Target outcome | First-class Definition aggregate with immutable Versions; instances pin to Version; designer operates on drafts |
| Dependencies | **Accepted ADR-0012** (ADR-0010 alone insufficient); ops migration window; PAR-WF-002 patterns |
| Decision required | Accept ADR-0012 or successor + ops sign-off before phase 3+ |
| Migration impact | Planned 0110–0115 additive sequence (not executed) |
| Security and permissions impact | Designer/config permissions stay configuration-scoped; pilot protected until flag opt-in |
| Audit requirements | Canonical events mapped in TARGET_AGGREGATE.md; reuse interim events during dual-write |
| UX requirements | Designer IA: Definition → Versions; no silent edit of published versions |
| Tests | Existing workflow suites + `test_par_wf_010_characterization.py` (4 OK) |
| Rollback strategy | Per-phase checkpoints in CUTOVER_PLAN.md |
| Acceptance criteria | Accepted ADR; migrations proved; no silent rebinds; pilot verified — **not met** (cutover blocked) |
| Evidence | `docs/audits/evidence/2026-07-22-par-wf-010/` |
| PR/commits | Branch `cursor/feat-platform-documentation-alignment-d7f1` |
| Next unblocked item | **Tranche-1 integration gate** (then PAR-APR-001 continuation merge) |
| Last updated | 2026-07-22 |

---

## Milestone 3 detail — Authority and decision models

### Programme integration gate (Tranche-1)

| Field | Content |
|---|---|
| Status | **Completed** (2026-07-22) — PR #50 merged to `main` @ `c52d699a` |
| Integration branch | `cursor/feat-platform-alignment-tranche-1` |
| Gate evidence | `docs/audits/2026-07-22-platform-alignment-tranche-1-merge-gate.md` |
| Next after gate | PAR-APR-001 foundation merge; **PAR-ID-001** |
| Last updated | 2026-07-22 |

### PAR-APR-001 — Approval Requirement/Decision split

| Field | Content |
|---|---|
| Status | **Completed** (2026-07-22) |
| Priority | P1 |
| Problem | `ApprovalRequest` collapses Requirement and Decision; domain requires Decision bound to approved state/document version. |
| Resolution | `ApprovalRequirement` + immutable `ApprovalDecision`; `approval_canonical.py`; migration **0111** (renumbered after Tranche-1 `0110` flagship assignees) |
| Accepted ADR | **ADR-0013** — ratified 2026-07-22 with named approvers (see meeting record) |
| Evidence | `docs/audits/evidence/2026-07-22-par-apr-001/` |
| Cutover residuals | Transferred to **PAR-APR-002** (legacy read-path retirement, DPAReviewPack, ABSTAIN UI, etc.) |
| Tests | `tests/test_par_apr_001_approval.py` + approval regression suites |
| Acceptance criteria | Separate concepts; governed decisions; version binding; invalidation; audit — **met** for foundation scope |
| Next | **PAR-ID-001** (In progress) |
| Last updated | 2026-07-22 |

### PAR-ID-001 — Role Definition reconciliation

| Field | Content |
|---|---|
| Status | **In progress** (2026-07-22) — cutover **implementation** on PR #62 (`PROCESS_ROLE_CANONICAL_RESOLVER_ENABLED` default off); activation **pending** separate votes; GI-2026-07-22-PR58-PREAUTH-MERGE **Ratified and Closed**; legacy retained; ADMIN reconciliation deferred |
| Priority | P1 |
| Problem | Dual role systems (`OrganizationMembership` vs `UserProfile.Role`) conflict with canonical Role Definition. |
| Governance source | CANONICAL_DOMAIN_MODEL §2.5; SECURITY_PRIVACY_ACCESS_AND_AUDIT |
| Current evidence | `docs/audits/evidence/2026-07-22-par-id-001/` + `docs/audits/evidence/2026-07-22-par-id-001-pr58-merge/`; implementation Authorized `15:27–15:29Z`; activation package **Requested** |
| Target outcome | Single terminology and mapping for process vs org roles; no silent privilege escalation |
| Dependencies | ADR-0014 Accepted (**met**); PAR-SEC-003 Closed (**met**); privilege/resolver cutover needs separate authorization |
| Decision required | **ADR-0014 Accepted** — privilege/resolver cutover still needs separate implementation authorization |
| Migration impact | `0112` catalogue + `0113` org-scoped `ProcessRoleAssignment`; Slice 3 adds no migration; production resolvers unchanged |
| Security and permissions impact | **High** — labels grant no permissions; dual-read/shadow non-authoritative; runtime authz unchanged |
| Audit requirements | `role.definition.*`; `role.assignment.created/deactivated/legacy_mapped/drift_detected/shadow_sync_failed` |
| UX requirements | Consistent role labels in My Work, Approvals, Admin (copy audit residual) |
| Tests | Characterization (19) + catalogue + assignment + shadow sync + isolation (75) + approvals (33) + WF-010 |
| Rollback strategy | Flags default off; reverse 0113 then 0112 if needed; no resolver flip to roll back |
| Acceptance criteria | Accepted ADR (**met**); additive catalogue (**met**); org-scoped adapter + dual-read (**met**); feature-flagged shadow sync + parity (**met**); runtime cutover criteria **not yet** |
| Evidence | `docs/audits/evidence/2026-07-22-par-id-001/` |
| Accepted ADR | **ADR-0014** + 0112/0113 implementation authorizations; Slice 3 auth **Authorized** (non-authoritative; merge recorded separately) |
| PR/commits | PR #51 `21e65f09`; PR #53 `0bf7c9dc`; PR #54 `58966de7`; PR #52 `3c5e628b`; PR #55 `bb881ac2`; evidence PR #57 `2f14c034`; merge evidence PR #59 `0d9712ca`; PR #58 `598b7a12` (resolver parity); PR [#62](https://github.com/Technivian/CLMOne/pull/62) (canonical authority default-off) |
| Last updated | 2026-07-22 |

### PAR-EXC-001 — Governed Exception

| Field | Content |
|---|---|
| Status | Future roadmap (Milestone 3) — **not Completed** |
| Priority | P1 |
| Problem | No first-class governed Exception; risk/actions are scattered. |
| Governance source | CANONICAL_DOMAIN_MODEL §2.33; PRODUCT_OPERATING_MODEL exception handling |
| Current evidence | RiskSignal / ad hoc actions; gap audit Missing/Medium–High path |
| Target outcome | Governed Exception object with approval/audit path and clear lifecycle |
| Dependencies | PAR-APR-001 helpful; policy owners |
| Decision required | **PDR** for Exception vocabulary and authority |
| Migration impact | New model + optional backfill from RiskLog/signals |
| Security and permissions impact | Exception raise/resolve restricted roles |
| Audit requirements | Create/resolve/waive audited |
| UX requirements | Exception surfaces outside hero clutter; actionable queues |
| Tests | Lifecycle, permissions, isolation |
| Rollback strategy | Feature-flag new object; reverse additive migration |
| Acceptance criteria | Accepted PDR; Exception CRUD governed; tests + audit evidence |
| Evidence | TBD |
| PR/commits | TBD |
| Last updated | 2026-07-22 |

---

## Milestone 4 detail — Canonical data and post-signature

### PAR-DATA-001 — Property Definition CRUD

| Field | Content |
|---|---|
| Status | Future roadmap (Milestone 4) — **not Completed** |
| Priority | P1 |
| Problem | Property Definitions not centrally governed; `FieldDefinition` is template-scoped; Data Manager hub is interim only. |
| Governance source | DATA_AI_AND_INTELLIGENCE; CANONICAL_DOMAIN_MODEL §2.7; UX_NAVIGATION Data Manager |
| Current evidence | Data Manager hub (PAR-NAV-001); FieldDefinition per template; gap G Property row |
| Target outcome | Central Property Definition catalogue with governed CRUD, deprecation (no silent repurpose) |
| Dependencies | PAR-NAV-001 hub; ADR/PDR for model |
| Decision required | **PDR and/or ADR** for Property Definition schema |
| Migration impact | Medium — map FieldDefinition → Property Definition |
| Security and permissions impact | Configuration-role only; pilot may keep config nav hidden until ready |
| Audit requirements | Create/update/deprecate audited |
| UX requirements | Data Manager becomes real catalogue, not gap stub |
| Tests | CRUD authz; deprecation invariants; isolation |
| Rollback strategy | Dual-read FieldDefinition; flag UI |
| Acceptance criteria | Decision accepted; CRUD live; tests + migration + docs; hub gap closed |
| Evidence | TBD |
| PR/commits | TBD |
| Last updated | 2026-07-22 |

### PAR-OBL-001 — First-class Obligation

| Field | Content |
|---|---|
| Status | Future roadmap (Milestone 4) — **not Completed** |
| Priority | P1 |
| Problem | Obligations aliased to `Deadline`; conflicts with canonical Obligation object. |
| Governance source | CANONICAL_DOMAIN_MODEL Obligation; UX obligations workspace; gap G-DOM-03 |
| Current evidence | `obligations.py` / Deadline alias; pilot middleware denies `/contracts/obligations` |
| Target outcome | First-class Obligation model + migration from Deadline alias with no silent data loss |
| Dependencies | ADR/PDR; careful pilot re-enable plan |
| Decision required | **ADR/PDR** for Obligation schema and Deadline mapping |
| Migration impact | **High** — data rewrite risk; expand-contract mandatory |
| Security and permissions impact | Re-enable obligations only with tenant + role checks |
| Audit requirements | Migrate job audited; obligation mutations audited |
| UX requirements | Obligations workspace becomes canonical (not alias) |
| Tests | Migration forward/rollback/re-forward; isolation; pilot flag behaviour |
| Rollback strategy | Dual-write period; reverse migrate with row counts proved |
| Acceptance criteria | Decision accepted; zero silent loss; tests + migration + rollback proof; docs |
| Evidence | TBD |
| PR/commits | TBD |
| Last updated | 2026-07-22 |

### PAR-OBL-002 — Reminder object

| Field | Content |
|---|---|
| Status | Future roadmap (Milestone 4) — **not Completed** |
| Priority | P2 after PAR-OBL-001 |
| Problem | Reminders exist as fields/jobs (`Deadline.reminder_days`) not first-class Reminder objects. |
| Governance source | CANONICAL_DOMAIN_MODEL Reminder; gap audit PAR-OBL-002 |
| Current evidence | Reminder jobs / deadline fields; `send_contract_reminders` command |
| Target outcome | First-class Reminder entity linked to Obligation/Contract with schedule and delivery audit |
| Dependencies | PAR-OBL-001 |
| Decision required | Optional ADR if scheduling semantics change |
| Migration impact | Backfill from reminder_days / jobs |
| Security and permissions impact | Reminder visibility tenant-scoped |
| Audit requirements | Reminder schedule/send/cancel audited |
| UX requirements | Reminder management on obligation/contract surfaces |
| Tests | Scheduling, permissions, job idempotency |
| Rollback strategy | Additive model + flag; keep legacy fields until cutover |
| Acceptance criteria | Reminder object live; jobs use new model; tests + docs |
| Evidence | TBD |
| PR/commits | TBD |
| Last updated | 2026-07-22 |

---

## Milestone 5 detail — Intelligence and enterprise

### PAR-AI-001 — AI Suggestion provenance

| Field | Content |
|---|---|
| Status | Future roadmap (Milestone 5) — **not Completed** |
| Priority | P2 |
| Problem | `ClauseRecommendation` lacks model/provider/prompt provenance; AI must stay non-authoritative until verified. |
| Governance source | DATA_AI_AND_INTELLIGENCE; gap G-AI-01 |
| Current evidence | ClauseRecommendation accept flags; pilot AI kill switch |
| Target outcome | Every AI suggestion stores provider/model/prompt hash (or equivalent) and verification state |
| Dependencies | AI feature flags; may follow Data Manager property stability |
| Decision required | None for additive provenance fields; PDR if suggestion lifecycle vocabulary changes |
| Migration impact | Additive columns/backfill nullable |
| Security and permissions impact | AI endpoints remain authz-aligned with search; kill switch respected |
| Audit requirements | Accept/reject suggestion audited with provenance snapshot |
| UX requirements | Show “unverified AI” affordance; no authoritative auto-apply |
| Tests | Provenance persistence; non-authoritative defaults; authz parity |
| Rollback strategy | Reverse additive migration; disable UI provenance panel |
| Acceptance criteria | Provenance fields populated for new suggestions; tests + docs |
| Evidence | TBD |
| PR/commits | TBD |
| Last updated | 2026-07-22 |

### PAR-ENT-001 — Entity Relationship graph

| Field | Content |
|---|---|
| Status | Future roadmap (Milestone 5 / Enterprise) — **not Completed** |
| Priority | P2 |
| Problem | Entities nav interim maps to Counterparty only; no Entity Relationship graph. |
| Governance source | CANONICAL_DOMAIN_MODEL Entity; UX_NAVIGATION Entities |
| Current evidence | PAR-NAV-001 Entities → counterparties; gap Future Enterprise |
| Target outcome | Governed Entity model + relationships usable beyond Counterparty alias |
| Dependencies | PAR-DATA-001 helpful; enterprise data modelling |
| Decision required | ADR/PDR for Entity graph |
| Migration impact | High — new graph tables |
| Security and permissions impact | Relationship visibility tenant-scoped; ethical walls considerations |
| Audit requirements | Entity/relationship mutations audited |
| UX requirements | Entities IA beyond counterparty list |
| Tests | Graph integrity, isolation, walls |
| Rollback strategy | Flag new graph; keep Counterparty alias |
| Acceptance criteria | Decision accepted; graph MVP; tests + docs |
| Evidence | TBD |
| PR/commits | TBD |
| Last updated | 2026-07-22 |

### PAR-INT-001 — Generic Integration Connection

| Field | Content |
|---|---|
| Status | Future roadmap (Milestone 5 / Enterprise) — **not Completed** |
| Priority | P2 |
| Problem | Integrations are point solutions (e.g. Salesforce); no generic Integration Connection model. |
| Governance source | PLATFORM_AND_MODULE_ARCHITECTURE; DATA_AI / integrations guidance |
| Current evidence | Salesforce connection models/APIs; enterprise gap |
| Target outcome | Generic Connection abstraction with credentials isolation, sync audit, and per-org enablement |
| Dependencies | Secrets management; enterprise IdP/ops readiness may block production |
| Decision required | ADR for connection model and secret handling |
| Migration impact | Medium — wrap existing connectors |
| Security and permissions impact | **High** — secrets never logged; admin-only; tenant isolation |
| Audit requirements | Connect/disconnect/sync audited without secret material |
| UX requirements | Admin integrations surface; no pilot claim until ready |
| Tests | Authz, secret redaction, isolation, sync failure handling |
| Rollback strategy | Keep legacy connectors; flag generic layer |
| Acceptance criteria | Accepted ADR; one connector on generic model; security review evidence |
| Evidence | TBD |
| PR/commits | TBD |
| Last updated | 2026-07-22 |

---

## Unresolved ambiguities

1. ~~PAR-SEC-002 unassigned~~ → **Resolved:** added as Milestone 1 `PAR-SEC-002`.
2. ~~G-DOM-02 without PAR~~ → **Resolved:** `PAR-CORE-002` in Milestone 2 before WF-010 cutover.
3. ~~SEC-001 residual attached to Completed~~ → **Resolved:** residual is `PAR-SEC-003` only.
4. **ADR-0010** remains Proposed and non-authorizing; WF-010 cutover still needs an **Accepted** ADR (may be a successor ADR, not ADR-0010).
5. ~~PAR-CORE-001 remaining gaps~~ → **Resolved / Completed** (2026-07-22 ownership close-out).

---

## Progress log

| Timestamp (UTC) | Event |
|---|---|
| 2026-07-21 | Audit + roadmap authored; foundation + pilot slices implemented and verified (74 tests OK) |
| 2026-07-22 | PR #48 final merge gate recorded (`APPROVE WITH NAMED CONDITIONS`); migration 0105 proof; isolation residual + Playwright bootstrap catalogued |
| 2026-07-22 | **Roadmap refinement (docs only):** reconciled unique PAR count (21; `PAR-AUD-001` bundled with `PAR-WF-001` but retained in catalogue); corrected Charter v3 blocker (PDR-0003 does not approve v3); reordered Future into Milestones 1–5; expanded all future items + M1 follow-ups with full field schema; set immediate next to PAR-CORE-001 → PAR-CORE-003 → PAR-DOC-001 → PAR-WF-010 |
| 2026-07-22 | **Ambiguity reconciliation:** added `PAR-SEC-002`, `PAR-CORE-002` (G-DOM-02), `PAR-SEC-003` (isolation residual); unique PAR count → **24**; ADR-0010 remains Proposed/non-authorizing; started **PAR-CORE-001** (In progress) with PDR-0002 slices + evidence — not Completed |
| 2026-07-22 | **PAR-CORE-001 Completed:** closed CRM/CSV/inbound ownership, document supersession audit, and Contract.save pair protection; checklist Compliant; next item **PAR-CORE-003** |
| 2026-07-22 | **PAR-CORE-003 Completed:** Contract Record provenance fields + immutability + governed repair; migration 0106 truthful backfill; import/workflow/manual/admin/seed paths wired; tests + rollback proof; next item **PAR-CORE-002** |
| 2026-07-22 | **PAR-CORE-002 Completed:** canonical `ContractType` catalogue + `contract_type_catalogue` FK; transitional char mirror; migration 0107; Proposed ADR-0011; evidence `2026-07-22-par-core-002`; next **PAR-DOC-001** |
| 2026-07-22 | **PAR-DOC-001 Completed:** `DocumentVersion` entity + immutability service; migrations 0108–0109; signature version binding; evidence `2026-07-22-par-doc-001`; next **PAR-WF-010** (design only until Accepted ADR) |
| 2026-07-22 | **PAR-WF-010 discovery complete (Blocked):** evidence `2026-07-22-par-wf-010`; Proposed ADR-0012; characterization tests; production cutover blocked pending Accepted ADR |
| 2026-07-22 | **Tranche-1 integration gate Completed:** PR #50 merged to `main` @ `c52d699a` |
| 2026-07-22 | **PAR-APR-001 Completed:** `ApprovalRequirement` + `ApprovalDecision`; migration 0111; ADR-0013 **Accepted**; evidence `2026-07-22-par-apr-001`; cutover residuals → PAR-APR-002 |
| 2026-07-22 | **PAR-ID-001 discovery complete:** ROLE_USAGE_MATRIX, TARGET_ROLE_MODEL, CUTOVER_PLAN, ADR-0014 decision package; 19 characterization tests |
| 2026-07-22 | **PR #51 merged** to `main` @ `21e65f09` |
| 2026-07-22 | **ADR-0014 Accepted**; **PAR-SEC-003 Closed**; migration `0112` authorized and implemented (additive RoleDefinition catalogue); PAR-ID-001 remains **In progress** |
| 2026-07-22 | **PR #53 merged** to `main` @ `0bf7c9dc` |
| 2026-07-22 | **PAR-ID-001 process-role adapter:** migration `0113` `ProcessRoleAssignment` + dual-read parity; production authority still legacy resolvers; privilege/resolver cutover **not** authorized |
| 2026-07-22 | **PR #54 merged** to `main` @ `58966de7` |
| 2026-07-22 | **PR #52 merged** to `main` @ `3c5e628b` — PR #50 visual + E2E remediation closed; evidence `docs/audits/evidence/2026-07-22-pr52-merge/` |
| 2026-07-22 | **PAR-ID-001 Slice 3:** feature-flagged shadow sync (`PROCESS_ROLE_SHADOW_WRITE_ENABLED`) + `process_role_parity_report`; parity evidence; production resolvers still legacy; next cutover slice needs separate authorization |
| 2026-07-22 | **PR #55 merged** to `main` @ `bb881ac2` (reviewed HEAD `432a55b1`, 2026-07-22T13:35:32Z); flags remain default off; merge auth Product `13:36:50Z` / Engineering `15:15:23Z` |
| 2026-07-22 | **PR #57 merged** to `main` @ `2f14c034` — PR #52 merge-evidence documentation |
| 2026-07-22 | **PR #59 merged** to `main` @ `0d9712ca` — PR #55 merge-evidence documentation |
| 2026-07-22 | **PAR-ID-001 Slice 4 authorization package:** resolver usage matrix + test matrix + non-authoritative comparison authorization on PR [#58](https://github.com/Technivian/CLMOne/pull/58) |
| 2026-07-22 | **PAR-ID-001 Slice 4 Authorized (authoritative vote record):** Product `14:17:31Z` / Engineering `14:18:31Z` / Security advisory `14:15:31Z` (Approve with conditions); prior draft `14:04–14:06Z` record superseded; comparison hooks on PR #58 behind default-off flag; merge + staging activation still separate |
| 2026-07-22 | **PR #58 merged** to `main` @ `598b7a12` (2026-07-22T14:42:13Z); reviewed code HEAD `44926da9`; flags remain default off; merge auth Product `15:06:30Z` / Engineering `15:06:45Z` recorded **after** merge; staging activation **not** authorized (`14:34:37Z` staging claim superseded); PAR-ID-001 remains **In progress** |
| 2026-07-22 | **GI-2026-07-22-PR58-PREAUTH-MERGE opened:** merge preceded formal merge votes; ratification addendum requests **Ratify \| Revert**; recommend Ratify if safeguards hold; remediation backlog prepared; **no** staging activation until ratification + remediation progress |
| 2026-07-22 | **GI-2026-07-22-PR58-PREAUTH-MERGE Ratified and Closed:** Product `15:31:46Z` / Engineering `15:31:55Z`; PAR-ID-001 **In progress** — resolver parity merged; remediation required before staging activation; flags remain default off |
| 2026-07-22 | **PAR-ID-001 staging resolver-parity gate + remediation:** CERTAIN assignment gaps fixed; ADMIN first-cutover exclusion; threat review PASS for packaging; post-parity MATCH 24 / AMBIGUOUS 13 / critical 0; verdict **READY FOR CUTOVER AUTHORIZATION** |
| 2026-07-22 | **PAR-ID-001 cutover implementation Authorized:** Product `15:27:09Z` / Engineering `15:28:09Z` / Security `15:29:09Z` (Approve with conditions); `PROCESS_ROLE_CANONICAL_RESOLVER_ENABLED` default off on PR [#62](https://github.com/Technivian/CLMOne/pull/62); activation votes **Requested**; flag **not** enabled; PAR-ID-001 remains **In progress** |

