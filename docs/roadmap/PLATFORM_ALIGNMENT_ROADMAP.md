# Platform Alignment Roadmap

**Created:** 2026-07-21  
**Last refined:** 2026-07-22 (Tranche-1 integration / PR-scope normalization)  
**Authority:** Gap audit `docs/audits/2026-07-21-platform-gap-audit.md` · active `docs/governance/GOVERNANCE_CHARTER.md` · Accepted PDR-0003  
**Branch:** `cursor/feat-platform-alignment-tranche-1` (integration PR) · PAR-APR-001 continuation: `cursor/feat-platform-documentation-alignment-d7f1`  
**Living document:** update statuses only with implementation, tests, audit evidence, migration evidence (if any), documentation, and rollback proof.

Statuses: Completed · In progress · Blocked · Deferred by approved decision · Future roadmap · Cancelled with rationale

---

## Catalogue count (reconciled)

| Rollup | Count | Notes |
|---|---:|---|
| **Unique PAR IDs in this roadmap** | **24** | All distinct `PAR-*` identifiers below |
| Completed unique PAR IDs | 12 | Includes `PAR-AUD-001`, `PAR-CORE-001`, `PAR-CORE-003`, `PAR-CORE-002`, `PAR-DOC-001` |
| In progress | 1 | `PAR-APR-001` — additive schema + primary dual-write on continuation branch; not in Tranche-1 PR |
| Future / residual unique PAR IDs | 11 | Includes `PAR-SEC-002`, `PAR-SEC-003` |
| Non-PAR Milestone 1 follow-ups | 1 | Playwright DPA bootstrap (`M1-E2E-001`) |

### Bundling rule for `PAR-AUD-001`

`PAR-AUD-001` remains intentionally bundled with `PAR-WF-001` for delivery and is **included** in the unique total of **24**.

### Unique PAR ID inventory

**Completed (12):** `PAR-WF-001`, `PAR-AUD-001`, `PAR-WF-002`, `PAR-WF-003`, `PAR-WF-005`, `PAR-NAV-001`, `PAR-SEC-001`, `PAR-WORK-001`, `PAR-CORE-001`, `PAR-CORE-003`, `PAR-CORE-002`, `PAR-DOC-001`

**In progress (1):** `PAR-APR-001` — continuation branch `cursor/feat-platform-documentation-alignment-d7f1` @ `c9ae7305`

**Future / residual (11):** `PAR-SEC-002`, `PAR-SEC-003`, `PAR-WF-010`, `PAR-ID-001`, `PAR-EXC-001`, `PAR-DATA-001`, `PAR-OBL-001`, `PAR-OBL-002`, `PAR-AI-001`, `PAR-ENT-001`, `PAR-INT-001`

**Blocked (1):** `PAR-WF-010` — discovery complete; production cutover blocked pending Accepted ADR-0012

---

## Immediate next items

1. **Tranche-1 programme integration gate** — merge `cursor/feat-platform-alignment-tranche-1` to `main` (governance docs + Foundation/Pilot + CORE/DOC + WF-010 discovery only) — **required before PAR-ID-001**
2. **PAR-APR-001** — **In progress** on continuation branch (`c9ae7305`); additive schema + primary dual-write delivered; legacy cutover pending Accepted ADR-0013
3. **PAR-WF-010** — production cutover **blocked** pending Accepted ADR-0012 (discovery complete — see evidence)

Parallel Milestone 1 hygiene:

- `M1-E2E-001` Fix Playwright DPA bootstrap
- `PAR-SEC-003` Close stale ContractIsolationTest assertion (separate from Completed `PAR-SEC-001`)
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
| ADR-0013 | Approval Requirement / Decision split | **Proposed** — continuation branch only (`c9ae7305`); not in Tranche-1 PR. Required before PAR-APR-001 legacy cutover. |

---

## Blocked (external / governance)

| Item | Why |
|---|---|
| Charter v3 activation | Separate constitutional review and formal Charter amendment approval required. PDR-0003 does not approve Charter v3. |
| Production Definition/Version cutover | Needs Accepted ADR covering `PAR-WF-010` + ops window |
| External IdP production credentials | External dependency |
| Commercial vuln-scan SaaS evidence | External tooling |

---

## Future milestones (ordered)

### Milestone 1 — Finish pilot hardening

| ID / work | Title | Priority | Status |
|---|---|---|---|
| **PAR-CORE-001** | Complete remaining PDR-0002 UI/test drift | P0 | **Completed** |
| **PAR-SEC-002** | Uniform authz for search/analytics/AI; client-hide ≠ authorization | P1 | Future |
| **PAR-SEC-003** | Stale ContractIsolationTest repository-redirect assertion | P1 | Future residual |
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
| PAR-APR-001 | Approval Requirement/Decision split | P1 | **In progress** (continuation branch) |
| *(gate)* | **Tranche-1 programme integration** | P0 | **Required before PAR-ID-001** |
| PAR-ID-001 | Role Definition reconciliation | P1 | Future (blocked on gate) |
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
| Status | Future roadmap (Milestone 1 residual) — **not Completed**; separate from Completed `PAR-SEC-001` |
| Priority | P1 |
| Problem | `ContractIsolationTest.test_list_shows_only_own_org` expects HTTP 200 on legacy `contract_list`; product intentionally 302-redirects authenticated users to repository. |
| Governance source | ENGINEERING_GUARDRAILS tenant isolation; gap G-SEC-01 / PAR-SEC-001 follow-up |
| Current evidence | Baseline + merge-gate: `AssertionError: 302 != 200`; cross-org detail/update still 404 PASS; catalog `known-preexisting-failures.md` |
| Target outcome | Test asserts redirect to repository and verifies org isolation on the canonical repository surface |
| Dependencies | Stable `contracts:repository` isolation behaviour |
| Decision required | None — align test to intentional alias behaviour |
| Migration impact | None |
| Security and permissions impact | Strengthens regression signal; no authz change |
| Audit requirements | None |
| UX requirements | None |
| Tests | Updated isolation test(s); full `test_cross_tenant_isolation` green |
| Rollback strategy | Revert test-only change |
| Acceptance criteria | Isolation suite 0 failures; no anonymous alias bypass regressions |
| Evidence | TBD |
| PR/commits | TBD |
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
| Status | **Required before PAR-ID-001** |
| Integration branch | `cursor/feat-platform-alignment-tranche-1` @ `cf2d5ae2` (+ non-destructive `origin/main` merge) |
| PR scope | Accepted governance documentation; Foundation + Pilot hardening; PAR-CORE-001/002/003; PAR-DOC-001; PAR-WF-010 discovery |
| Explicitly excluded | `c9ae7305` / PAR-APR-001 implementation (continuation branch preserved) |
| Gate evidence | `docs/audits/2026-07-22-platform-alignment-tranche-1-merge-gate.md` |
| Acceptance criteria | Governance checks PASS; migrations 0105–0109 forward/rollback/re-forward PASS; CORE/DOC/WF characterization + isolation + pilot-scope tests PASS |
| Next after gate | Land Tranche-1 PR; complete PAR-APR-001 cutover on continuation branch; then **PAR-ID-001** |
| Last updated | 2026-07-22 |

### PAR-APR-001 — Approval Requirement/Decision split

| Field | Content |
|---|---|
| Status | **In progress** (2026-07-22) — continuation branch `cursor/feat-platform-documentation-alignment-d7f1` @ `c9ae7305`; **not included in Tranche-1 PR** |
| Priority | P1 |
| Problem | `ApprovalRequest` collapses Requirement and Decision; domain requires Decision bound to approved state/document version. |
| Delivered (continuation branch) | Additive `ApprovalRequirement` + `ApprovalDecision` schema; migration `0110`; `approval_canonical.py`; primary dual-write from `ApprovalWorkflowService`; document-version binding; invalidation on supersession |
| Proposed ADR | **ADR-0013** (not Accepted) — `docs/governance/decisions/adr/0013-approval-requirement-decision-split.md` on continuation branch only |
| Evidence (continuation) | `docs/audits/evidence/2026-07-22-par-apr-001/` |
| Remaining cutover criteria | **Accepted ADR-0013**; legacy `ApprovalRequest` read-path retirement plan; `DPAReviewPack` parallel model reconciliation; `ApprovalRoute` → runtime requirement mapping; `ABSTAIN` UI action; full approval regression sign-off; Tranche-1 landed on `main` before continuation merge |
| Tests (continuation) | `tests/test_par_apr_001_approval.py` + approval regression suites — on continuation branch only |
| Acceptance criteria | Separate concepts; governed decisions; version binding; invalidation; audit — **partially met** (additive path delivered; legacy cutover and ADR acceptance pending) |
| Next after cutover | **PAR-ID-001** (blocked until Tranche-1 gate + PAR-APR-001 completion) |
| Last updated | 2026-07-22 |

### PAR-ID-001 — Role Definition reconciliation

| Field | Content |
|---|---|
| Status | Future roadmap (Milestone 3) — **not Completed**; **blocked on Tranche-1 programme integration gate** |
| Priority | P1 |
| Problem | Dual role systems (`OrganizationMembership` vs `UserProfile.Role`) conflict with canonical Role Definition. |
| Governance source | CANONICAL_DOMAIN_MODEL §2.5; SECURITY_PRIVACY_ACCESS_AND_AUDIT |
| Current evidence | Membership + Profile roles in pilot seed; gap audit Conflicting |
| Target outcome | Single terminology and mapping for process vs org roles; no silent privilege escalation |
| Dependencies | Authz matrix inventory; avoid breaking pilot seeds |
| Decision required | **ADR** for terminology/mapping |
| Migration impact | Mapping table / backfill; possibly no destructive drop initially |
| Security and permissions impact | **High** — must preserve least privilege; server-side checks remain source of truth |
| Audit requirements | Role/mapping changes audited |
| UX requirements | Consistent role labels in My Work, Approvals, Admin |
| Tests | Permission matrix tests; pilot role fixtures; isolation |
| Rollback strategy | Keep dual-read mapping; revert ADR implementation behind flag |
| Acceptance criteria | Accepted ADR; documented mapping; tests prove no privilege widening |
| Evidence | TBD |
| PR/commits | TBD |
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
| 2026-07-22 | **Tranche-1 integration / PR-scope normalization:** branch `cursor/feat-platform-alignment-tranche-1` at `cf2d5ae2`; excludes `c9ae7305`; PAR-APR-001 → **In progress** on continuation branch; programme integration gate added before PAR-ID-001 |
