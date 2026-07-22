# Platform Alignment Roadmap

**Created:** 2026-07-21  
**Last refined:** 2026-07-22  
**Authority:** Gap audit `docs/audits/2026-07-21-platform-gap-audit.md` · active `docs/governance/GOVERNANCE_CHARTER.md` · Accepted PDR-0003  
**Branch:** `cursor/feat-platform-documentation-alignment-d7f1`  
**Living document:** update statuses only with implementation, tests, audit evidence, migration evidence (if any), documentation, and rollback proof.

Statuses: Completed · In progress · Blocked · Deferred by approved decision · Future roadmap · Cancelled with rationale

---

## Catalogue count (reconciled)

| Rollup | Count | Notes |
|---|---:|---|
| **Unique PAR IDs in this roadmap** | **21** | All distinct `PAR-*` identifiers below |
| Completed unique PAR IDs | 8 | Includes `PAR-AUD-001` |
| Future unique PAR IDs | 13 | Milestone 1–5 catalogue items |
| Non-PAR Milestone 1 follow-ups | 2 | Playwright DPA bootstrap; stale `PAR-SEC-001` isolation assertion |

### Bundling rule for `PAR-AUD-001`

`PAR-AUD-001` (Admin published immutability / material Admin mutate audit) was **intentionally bundled** with `PAR-WF-001` for delivery and evidence. It remains a **distinct catalogue ID** and is **included** in the unique total of **21**.

If a rollup prefers one line per delivery bundle:

- Completed **delivery bundles** = **7** (`PAR-AUD-001` folded under `PAR-WF-001`) + Future **13** = **20 delivery lines**
- Completed **unique PAR IDs** = **8**; catalogue total remains **21**

Do **not** drop `PAR-AUD-001` from the catalogue; state the bundling explicitly when summarizing.

### Unique PAR ID inventory

**Completed (8):** `PAR-WF-001`, `PAR-AUD-001`, `PAR-WF-002`, `PAR-WF-003`, `PAR-WF-005`, `PAR-NAV-001`, `PAR-SEC-001`, `PAR-WORK-001`

**Future (13):** `PAR-CORE-001`, `PAR-CORE-003`, `PAR-DOC-001`, `PAR-WF-010`, `PAR-APR-001`, `PAR-ID-001`, `PAR-EXC-001`, `PAR-DATA-001`, `PAR-OBL-001`, `PAR-OBL-002`, `PAR-AI-001`, `PAR-ENT-001`, `PAR-INT-001`

---

## Immediate next items

1. **PAR-CORE-001** — Finish remaining PDR-0002 UI/test drift (Milestone 1)
2. **PAR-CORE-003** — Contract Record provenance completeness (Milestone 2)
3. **PAR-DOC-001** — Document Version entity harden (Milestone 2)
4. **PAR-WF-010** — Workflow Definition aggregate (Milestone 2; requires Accepted ADR before cutover)

Parallel Milestone 1 hygiene (not ahead of `PAR-CORE-001` in product priority, but may ship alongside):

- Fix Playwright DPA bootstrap (`seed_demo_command_center` / assignee launch block)
- Close stale `PAR-SEC-001` isolation expectation (`ContractIsolationTest.test_list_shows_only_own_org`)

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
| PAR-SEC-001 | Auth redirect / isolation defects | Pilot hardening | Auth bypass fixed; **residual stale list assertion** tracked in Milestone 1 |
| PAR-WORK-001 | My Work vs Command Center boundaries | Pilot hardening | `docs/product/MY_WORK_AND_COMMAND_CENTER_BOUNDARIES.md` |

---

## Proposed decisions (awaiting approval)

| ID | Title | Status |
|---|---|---|
| ADR-0010 | Workflow instance version pinning interim | **Proposed** — `docs/governance/decisions/adr/0010-workflow-instance-version-pinning-interim.md`. Non-authorizing until Accepted. |

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

| ID / work | Title | Priority |
|---|---|---|
| **PAR-CORE-001** | Complete remaining PDR-0002 UI/test drift | P0 — **next** |
| M1-E2E-001 | Fix Playwright DPA bootstrap | P1 |
| M1-SEC-001 | Close stale PAR-SEC-001 isolation expectation | P1 |

### Milestone 2 — Canonical contract core

| ID | Title | Priority |
|---|---|---|
| **PAR-CORE-003** | Contract Record provenance completeness | P0 (after CORE-001) |
| **PAR-DOC-001** | Document Version entity harden | P0 (after CORE-003) |
| **PAR-WF-010** | Workflow Definition aggregate | P0 (after DOC-001; ADR gate) |

### Milestone 3 — Authority and decision models

| ID | Title | Priority |
|---|---|---|
| PAR-APR-001 | Approval Requirement/Decision split | P1 |
| PAR-ID-001 | Role Definition reconciliation | P1 |
| PAR-EXC-001 | Governed Exception | P1 |

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

### PAR-SEC-001 — Completed (with Milestone 1 residual)

`ContractListView` / `DeadlineListView` authenticate before alias redirect; `workflow_template_activity` tenant-checks before redirect. Isolation suite improved from 5 failures → 1 residual stale assertion (see M1-SEC-001).

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
| Status | Future roadmap (Milestone 1) — **not Completed** |
| Priority | P0 — immediate next |
| Problem | PDR-0002 stage/status vocabulary is partially enforced; residual UI labels, transitions, and tests still drift from binding enums. |
| Governance source | Accepted **PDR-0002**; Canonical Domain Model §5 deferred to PDR-0002 until reconciling PDR; gap audit matrix row for PDR-0002 |
| Current evidence | Lifecycle service exists; gap audit marks Partially compliant; baseline targeted suite previously referenced missing `test_contract_lifecycle_pdr0002` module import error |
| Target outcome | UI, APIs, and tests consistently use PDR-0002 stage/status vocabulary; no conflicting free-text lifecycle claims |
| Dependencies | None blocking; coordinate with repository/list UX |
| Decision required | None if staying within Accepted PDR-0002; reconciling Domain Model §5 needs a separate PDR if reopened |
| Migration impact | Prefer none; data backfill only if persisted illegal values found |
| Security and permissions impact | No new roles; preserve tenant scoping on lifecycle mutations |
| Audit requirements | Material stage/status transitions continue to emit AuditLog events; add coverage where gaps appear |
| UX requirements | Labels and filters match PDR-0002 terms; no dual vocabulary in first-line pilot surfaces |
| Tests | Expand/repair PDR-0002 lifecycle tests; repository/bulk-update rejection paths; no regressions in controlled-pilot flows |
| Rollback strategy | Revert PR; no schema change expected — feature-flag UI copy if needed |
| Acceptance criteria | All targeted PDR-0002 surfaces pass automated tests; audit matrix row moves to Compliant for in-scope surfaces; no new conflicting enums |
| Evidence | TBD at implementation (tests + audit note) |
| PR/commits | TBD |
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

### M1-SEC-001 — Close stale PAR-SEC-001 isolation expectation

| Field | Content |
|---|---|
| Status | Future roadmap (Milestone 1 residual of completed PAR-SEC-001) — **not Completed** |
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

---

## Milestone 2 detail — Canonical contract core

### PAR-CORE-003 — Contract Record provenance completeness

| Field | Content |
|---|---|
| Status | Future roadmap (Milestone 2) — **not Completed** |
| Priority | P0 after PAR-CORE-001 |
| Problem | Contract Record provenance is partial (creator/org present; workflow/document/event linkage incomplete vs domain invariants). |
| Governance source | CANONICAL_DOMAIN_MODEL invariants; gap audit PAR-CORE-003 / G provenance row |
| Current evidence | `contracts.models.Contract` fields; gap audit Partially compliant |
| Target outcome | Every material Contract Record carries required provenance (org, creator, governing workflow version when applicable, source events) with queryable history |
| Dependencies | Prefer after PAR-CORE-001 vocabulary stability; may touch Document/Workflow FKs |
| Decision required | None for incremental fields; schema reshape may need ADR |
| Migration impact | Additive fields/backfill likely; must be reversible or expandable |
| Security and permissions impact | Provenance visible only within tenant; no cross-org leakage |
| Audit requirements | Provenance mutations and backfill jobs emit AuditLog |
| UX requirements | Record header/history surfaces show provenance without cluttering pilot hero flows |
| Tests | Model/service tests; isolation; optional API serializers |
| Rollback strategy | Reverse migration for additive columns; feature-flag UI |
| Acceptance criteria | Domain provenance checklist green for in-scope fields; tests + migration evidence + rollback proof |
| Evidence | TBD |
| PR/commits | TBD |
| Last updated | 2026-07-22 |

### PAR-DOC-001 — Document Version entity harden

| Field | Content |
|---|---|
| Status | Future roadmap (Milestone 2) — **not Completed** |
| Priority | P0 after PAR-CORE-003 |
| Problem | Document Version is partially modelled (`version` int + parent) and not fully immutable as required by domain. |
| Governance source | CANONICAL_DOMAIN_MODEL §2.16 / invariant “Document Version is immutable” |
| Current evidence | `Document` model versioning fields; gap audit Partially compliant |
| Target outcome | Immutable Document Version semantics: edits create new versions; historical versions read-only; approvals bind to version |
| Dependencies | PAR-CORE-003 provenance; PAR-APR-001 later for approval binding depth |
| Decision required | ADR if splitting Document vs DocumentVersion tables |
| Migration impact | Likely non-trivial; dual-write/backfill plan required |
| Security and permissions impact | Version access follows contract/org scoping |
| Audit requirements | Version create/restore/clone audited; forbid silent in-place rewrite |
| UX requirements | Clear version selector; no editable historical bytes in UI |
| Tests | Immutability tests; approval/doc binding; isolation |
| Rollback strategy | Expand-contract migration with documented reverse; feature flag new paths |
| Acceptance criteria | Cannot mutate historical version content via app or Admin; tests + migration + rollback proof |
| Evidence | TBD |
| PR/commits | TBD |
| Last updated | 2026-07-22 |

### PAR-WF-010 — Workflow Definition aggregate

| Field | Content |
|---|---|
| Status | Future roadmap (Milestone 2) — **not Completed**; **Blocked** on Accepted ADR before production cutover |
| Priority | P0 after PAR-DOC-001 |
| Problem | No first-class Workflow Definition; versions are `WorkflowTemplate` rows — conflicts with Definition → Version → Instance chain. |
| Governance source | CANONICAL_DOMAIN_MODEL; WORKFLOW_ENGINE_AND_DESIGNER; Proposed ADR-0010 interim only |
| Current evidence | Template+version fields; governed migrate helper; gap G-DOM-01 |
| Target outcome | First-class Definition aggregate with immutable Versions; instances pin to Version; designer operates on drafts |
| Dependencies | Accepted ADR (not ADR-0010 alone); ops migration window; PAR-WF-002 patterns |
| Decision required | **Accepted ADR** for schema + cutover (ADR-0010 remains Proposed interim only) |
| Migration impact | High — data model split, dual-read period, instance pin migration |
| Security and permissions impact | Designer/config permissions stay configuration-scoped; pilot may keep designer denied until ready |
| Audit requirements | Publish, version create, instance pin/migrate fully audited |
| UX requirements | Designer IA: Definition → Versions; no silent edit of published versions |
| Tests | Invariants, migrate forward/rollback/re-forward, designer/publish, isolation |
| Rollback strategy | Dual-read feature flag; reverse migrate only with ops runbook |
| Acceptance criteria | Accepted ADR; migrations proved; no silent rebinds; docs updated; pilot controls respected |
| Evidence | TBD |
| PR/commits | TBD |
| Last updated | 2026-07-22 |

---

## Milestone 3 detail — Authority and decision models

### PAR-APR-001 — Approval Requirement/Decision split

| Field | Content |
|---|---|
| Status | Future roadmap (Milestone 3) — **not Completed** |
| Priority | P1 |
| Problem | `ApprovalRequest` collapses Requirement and Decision; domain requires Decision bound to approved state/document version. |
| Governance source | CANONICAL_DOMAIN_MODEL §2.23–2.24; PDR-0002 where vocabulary intersects |
| Current evidence | `ApprovalRequest` / rules models; gap audit Partially compliant |
| Target outcome | Distinct Requirement vs Decision entities (or equivalent governed states) with document/version binding |
| Dependencies | PAR-DOC-001 for version binding; PDR if vocabulary changes |
| Decision required | PDR if status vocabulary changes; ADR for model split |
| Migration impact | Medium–high; backfill decisions from historical requests |
| Security and permissions impact | Approver authorization unchanged or strengthened; tenant scoped |
| Audit requirements | Requirement creation and Decision outcome audited |
| UX requirements | Approval UI distinguishes “required” vs “decided”; show bound doc version |
| Tests | Binding invariants; isolation; finance threshold still single entry (PDR-0001) |
| Rollback strategy | Expand-contract; flag new model reads |
| Acceptance criteria | Decisions reference approved state/doc version; tests + migration + docs |
| Evidence | TBD |
| PR/commits | TBD |
| Last updated | 2026-07-22 |

### PAR-ID-001 — Role Definition reconciliation

| Field | Content |
|---|---|
| Status | Future roadmap (Milestone 3) — **not Completed** |
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

1. **`PAR-SEC-002`** appears in the gap-audit traceability matrix (uniform authz for search/analytics/AI; client-hide ≠ authorization) but was **never assigned a roadmap PAR slot** in the original future table. It is **not** in the Milestone 1–5 list above. Disposition TBD: fold into Milestone 1/5, or add an explicit future ID later — **do not silently mark complete**.
2. **Dual `Contract.ContractType` enum vs `ContractType` model (G-DOM-02)** remains a High gap without a dedicated `PAR-*` ID in this catalogue. Tracked narratively under domain fidelity; assign a PAR ID before implementation.
3. **`PAR-SEC-001` Completed vs M1-SEC-001 residual:** primary auth-bypass work is Completed; the stale list assertion is residual hygiene, not a reopen of the whole item.
4. **ADR-0010** remains Proposed and non-authorizing for `PAR-WF-010` cutover.

---

## Progress log

| Timestamp (UTC) | Event |
|---|---|
| 2026-07-21 | Audit + roadmap authored; foundation + pilot slices implemented and verified (74 tests OK) |
| 2026-07-22 | PR #48 final merge gate recorded (`APPROVE WITH NAMED CONDITIONS`); migration 0105 proof; isolation residual + Playwright bootstrap catalogued |
| 2026-07-22 | **Roadmap refinement (docs only):** reconciled unique PAR count (21; `PAR-AUD-001` bundled with `PAR-WF-001` but retained in catalogue); corrected Charter v3 blocker (PDR-0003 does not approve v3); reordered Future into Milestones 1–5; expanded all future items + M1 follow-ups with full field schema; set immediate next to PAR-CORE-001 → PAR-CORE-003 → PAR-DOC-001 → PAR-WF-010 |
