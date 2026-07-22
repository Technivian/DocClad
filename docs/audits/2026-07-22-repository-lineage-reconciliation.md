# Repository lineage and governance-authority reconciliation

**Date:** 2026-07-22  
**Auditor:** Cursor Cloud Agent (read-only audit)  
**Scope:** Checkout identity, commit lineage, governance authority, ADR numbering, migration history, roadmap truth, PAR-APR-001 salvage assessment, recovery plan  
**Constraints observed:** No commits, migrations, models, ADRs, PDRs, or roadmap status edits during this audit.

---

## 1. Canonical repository and branch

| Field | Value |
|---|---|
| Absolute repository path | `/workspace` |
| Git remote URL | `https://github.com/technivian/clmone` (GitHub redirect: `Technivian/CLMOne`) |
| Current branch | `cursor/feat-platform-documentation-alignment-d7f1` |
| HEAD commit | `c9ae73051d9103a8730e8dc436221dce94d8c3db` |
| Upstream branch | `origin/cursor/feat-platform-documentation-alignment-d7f1` (tracking; in sync) |
| `git status` | Clean (no uncommitted changes at audit time) |
| Worktrees | Single worktree: `/workspace` → `c9ae7305` on `cursor/feat-platform-documentation-alignment-d7f1` |
| Canonical CLM One repository? | **Yes** — README, project layout (`config`, `contracts`, `theme`), and remote identify this as the CLM One Django monorepo. |

### Command capture

```text
$ pwd
/workspace

$ git remote -v
origin  https://github.com/technivian/clmone (fetch)
origin  https://github.com/technivian/clmone (push)

$ git branch --show-current
cursor/feat-platform-documentation-alignment-d7f1

$ git rev-parse HEAD
c9ae73051d9103a8730e8dc436221dce94d8c3db

$ git status --short
(clean)

$ git log --oneline --decorate -30
c9ae7305 (HEAD -> cursor/feat-platform-documentation-alignment-d7f1, origin/cursor/feat-platform-documentation-alignment-d7f1) feat(approvals): complete PAR-APR-001 Requirement/Decision split
cf2d5ae2 docs(workflow): PAR-WF-010 discovery and cutover design (blocked)
74260855 feat(documents): complete PAR-DOC-001 Document Version hardening
69ba8a1f feat(domain): complete PAR-CORE-002 Contract Type catalogue reconciliation
0ebf69d9 feat(provenance): complete PAR-CORE-003 Contract Record provenance
d7678108 feat(lifecycle): complete PAR-CORE-001 PDR-0002 ownership gaps
c4f67b50 feat(lifecycle): start PAR-CORE-001 PDR-0002 alignment slices
47414726 docs(roadmap): refine living platform alignment roadmap
308884a4 docs(audit): record PR #48 final merge gate evidence
678d1f3a docs(roadmap): record completed alignment milestones and final report
7fe24736 fix(security): require login before legacy list alias redirects
c8a4da71 feat(nav): add Data Manager hub and Entities configuration entries
f3e4645f fix(workflows): enforce published immutability and governed migration
c4d04d46 docs(audit): platform gap assessment and alignment roadmap
a643a41d (origin/cursor/cloud-agent-1784667803792-nvw9u) Cursor: Apply local changes for cloud agent
aca20a0c Adopt CLM One documentation operating model under docs/.
0aa59204 (origin/cursor/phase13-ship-evidence-harden-c916) Complete Phase 13: adoption evidence and team-queue hardening
16289dd8 (origin/cursor/phase12-backlog-polish-c916) Complete Phase 12: backlog polish tests and roadmap
d449d411 Wire Phase 12 polish UI: live assignee search, suggest reasons, trends.
67025113 (origin/cursor/phase11-backlog-amplifiers-c916) Note Phase 10 deferred items completed in Phase 11
2a9c861a Complete Phase 11: backlog amplifiers tests and roadmap
3562b764 Complete Phase 11 UI: combobox reassign, decision suggest, team queue, work-health charts.
fb144188 (origin/cursor/phase10-reassign-assignee-picker-c916) Drop unused reassign_members_json from view context
1328db2a Complete Phase 10: reassign assignee name picker
ad529c2d (origin/cursor/phase9-my-work-reassign-privacy-c916) Complete Phase 9: My Work reassign and privacy resolve
7f45d6a0 (origin/cursor/phase8-my-work-action-parity-c916) Complete Phase 8: My Work specialist action parity
ea96488e (origin/cursor/phase7-priority-reason-everywhere-c916) Complete Phase 7: priority reason on every work queue
48fa66d0 (origin/cursor/phase3-governance-phase4-nav-c916) Complete Phase 6: work health, saved views, measured priority
c5534448 Complete Phase 5: work operating-loop instrumentation
b689a691 Complete Phases 3–4: governance UX and nav retirement

$ git worktree list
/workspace  c9ae7305 [cursor/feat-platform-documentation-alignment-d7f1]
```

### Branch divergence from `origin/main`

| Metric | Value |
|---|---|
| `origin/main` HEAD | `ccf90a5397c34c2ab2feefcdd0c10489037c30cb` (Merge PR #46 — Phase 13) |
| Merge-base with `main` | `0aa59204cbc5e6cedf525a7966590cff96ed835f` |
| Commits ahead of `main` | **16** (from `aca20a0c` through `c9ae7305`) |
| Commits behind `main` | **1** (`ccf90a53` — merge commit only; second parent is `0aa59204`, already an ancestor) |

**Interpretation:** This is a long-lived feature branch forked at Phase 13 tip (`0aa59204`). The sole “behind” commit is a merge wrapper whose content is already contained in the branch ancestry. Rebasing onto `ccf90a53` should be low-conflict for shared history but has not been performed.

---

## 2. Current HEAD and history — reported commit verification

All ten previously reported commits **exist**, are **reachable from current HEAD**, and reside **only on this feature branch** (not on `origin/main`).

| Short SHA | Exists | Branches containing | Subject | Parent(s) | Reachable from HEAD |
|---|---|---|---|---|---|
| `aca20a0c` | Yes | `cursor/feat-platform-documentation-alignment-d7f1`, `cursor/cloud-agent-1784667803792-nvw9u` | Adopt CLM One documentation operating model under docs/. | `0aa59204` | Yes |
| `308884a4` | Yes | feature branch only | docs(audit): record PR #48 final merge gate evidence | `678d1f3a` | Yes |
| `47414726` | Yes | feature branch only | docs(roadmap): refine living platform alignment roadmap | `308884a4` | Yes |
| `c4f67b50` | Yes | feature branch only | feat(lifecycle): start PAR-CORE-001 PDR-0002 alignment slices | `47414726` | Yes |
| `d7678108` | Yes | feature branch only | feat(lifecycle): complete PAR-CORE-001 PDR-0002 ownership gaps | `c4f67b50` | Yes |
| `0ebf69d9` | Yes | feature branch only | feat(provenance): complete PAR-CORE-003 Contract Record provenance | `d7678108` | Yes |
| `69ba8a1f` | Yes | feature branch only | feat(domain): complete PAR-CORE-002 Contract Type catalogue reconciliation | `0ebf69d9` | Yes |
| `74260855` | Yes | feature branch only | feat(documents): complete PAR-DOC-001 Document Version hardening | `69ba8a1f` | Yes |
| `cf2d5ae2` | Yes | feature branch only | docs(workflow): PAR-WF-010 discovery and cutover design (blocked) | `74260855` | Yes |
| `c9ae7305` | Yes | feature branch only (HEAD) | feat(approvals): complete PAR-APR-001 Requirement/Decision split | `cf2d5ae2` | Yes |

**Missing or divergent commits:** None of the ten reported SHAs are missing. No orphan or conflicting SHAs were found for these identifiers.

---

## 3. Governance authority conclusion

### File presence and status

| File | Present on branch | Present on `origin/main` | Status |
|---|---|---|---|
| `docs/governance/GOVERNANCE_CHARTER.md` | Yes | **No** | **Active** — v2.0, Mandatory canonical repository governance document |
| `docs/governance/GOVERNANCE_CHARTER_V3_PROPOSED.md` | Yes | **No** | **Proposed** — explicitly not authoritative |
| `docs/governance/decisions/pdr/PDR-0003-documentation-operating-model.md` | Yes | **No** | **Accepted** (2026-07-21) |
| `docs/governance/PRODUCT_OPERATING_MODEL.md` | Yes | **No** | **Accepted** (per PDR-0003) |
| `docs/product/MASTER_BLUEPRINT.md` | Yes | **No** | **Accepted** |
| `docs/product/CANONICAL_DOMAIN_MODEL.md` | Yes | **No** | **Accepted** |
| `docs/product/UX_NAVIGATION_AND_WORK_SURFACES.md` | Yes | **No** | **Accepted** |
| `docs/architecture/PLATFORM_AND_MODULE_ARCHITECTURE.md` | Yes | **No** | **Accepted** |
| `docs/architecture/WORKFLOW_ENGINE_AND_DESIGNER.md` | Yes | **No** | **Accepted** |
| `docs/architecture/SECURITY_PRIVACY_ACCESS_AND_AUDIT.md` | Yes | **No** | **Accepted** |
| `docs/architecture/DATA_AI_AND_INTELLIGENCE.md` | Yes | **No** | **Accepted** |
| `docs/engineering/ENGINEERING_GUARDRAILS.md` | Yes | **No** | **Accepted** |
| `docs/roadmap/PLATFORM_ALIGNMENT_ROADMAP.md` | Yes | **No** | Living alignment roadmap (feature-branch artefact; not PDR-0003 canonical delivery roadmap) |
| `docs/roadmap/DELIVERY_ROADMAP_AND_RELEASE_GATES.md` | Yes | **No** | **Accepted** (per PDR-0003) |

### Authority determinations

| Question | Conclusion |
|---|---|
| Which Charter is active? | **`docs/governance/GOVERNANCE_CHARTER.md` (v2.0)** on this branch. Charter v3 is Proposed only. |
| Is PDR-0003 Accepted? | **Yes.** Adopts supporting documentation as Accepted guidance under the active Charter. |
| Is supporting documentation Accepted? | **Yes** on this branch, per PDR-0003 metadata in each file. |
| Is `clm_one_documentation_v2/` authoritative? | **No.** Listed in `.gitignore`; not present on disk; treated as stale export material outside version control. |
| Did the agent incorrectly use proposed documentation? | **Partial risk, mostly mitigated on-branch.** Work correctly cites Accepted docs and labels ADR-0010/0012/0013 as **Proposed**. Charter v3 is not implemented as authority. **However:** the entire `docs/governance/` tree and Accepted supporting docs **do not exist on `origin/main`**, so governance authority is branch-local until merged. PAR-WF-010 and PAR-APR-001 implementation proceeded under **Proposed** ADRs — consistent with discovery/implementation notes but **not** governance-authorized for production cutover or legacy removal. |

### Critical governance gap

`origin/main` retains legacy `docs/` layout (177 top-level operational docs) and **lacks** the PDR-0003 documentation operating model tree. Until the feature branch merges, **`main` has no in-repo Governance Charter file** (`git show origin/main:docs/governance/GOVERNANCE_CHARTER.md` fails). The canonical governance corpus lives on `cursor/feat-platform-documentation-alignment-d7f1` starting at `aca20a0c`.

---

## 4. ADR collision table

Seven ADR files exist under `docs/governance/decisions/adr/`. **No duplicate ADR numbers** were found.

| ADR | Filename | Title | Status | Creation commit | Intended scope | Collision |
|---|---|---|---|---|---|---|
| ADR-0010 | `0010-workflow-instance-version-pinning-interim.md` | Workflow instance version pinning during Definition/Version interim | **Proposed** | `c4d04d46` | Interim pinning of `Workflow.template` FK; forbids silent rebinding until PAR-WF-010 schema ships | **None** |
| ADR-0011 | `0011-canonical-contract-type-catalogue.md` | Canonical Contract Type catalogue (G-DOM-02) | **Proposed** | `69ba8a1f` | FK catalogue + transitional char mirror for contract types | **None** |
| ADR-0012 | `0012-workflow-definition-aggregate-cutover.md` | Workflow Definition aggregate and Definition/Version cutover | **Proposed** | `cf2d5ae2` | Target Definition/Version schema; production cutover blocked until Accepted | **None** |
| ADR-0013 | `0013-approval-requirement-decision-split.md` | Approval Requirement and Approval Decision split | **Proposed** | `c9ae7305` | Canonical `ApprovalRequirement` / `ApprovalDecision`; legacy `ApprovalRequest` mirror | **None** |

**Note:** ADR-0010 explicitly states it does **not** authorize schema split or production cutover; ADR-0012 references ADR-0010 as interim-only. No renumbering required.

---

## 5. Migration collision table

### Migrations ≥ 0100 on current branch

| # | Filename | Depends on | Created in commit | On `origin/main` |
|---|---|---|---|---|
| 0100 | `0100_workflowtemplate_governance_metadata.py` | 0099 | (Phase 11–13 lineage) | Yes |
| 0101 | `0101_workflowtemplate_fallback_signer.py` | 0100 | (Phase 11–13 lineage) | Yes |
| 0102 | `0102_approvalrequest_delegation_coverage.py` | 0101 | (Phase 11–13 lineage) | Yes |
| 0103 | `0103_workinteractionevent.py` | 0102 | (Phase 11–13 lineage) | Yes |
| 0104 | `0104_myworksavedview.py` | 0103 | (Phase 11–13 lineage) | Yes |
| 0105 | `0105_workflowtemplate_is_active_default_false.py` | 0104 | `f3e4645f` | **No** |
| 0106 | `0106_contract_record_provenance.py` | 0105 | `0ebf69d9` | **No** |
| 0107 | `0107_contract_type_catalogue_fk.py` | 0106 | `69ba8a1f` | **No** |
| 0108 | `0108_document_version_entity.py` | 0107 | `74260855` | **No** |
| 0109 | `0109_signature_request_document_version.py` | 0108 | `74260855` | **No** |
| 0110 | `0110_approval_requirement_decision.py` | 0109 | `c9ae7305` | **No** |

### Reported migration name reconciliation

| Reported name | Exists? | Actual on branch |
|---|---|---|
| `0105_workflowtemplate_is_active_default_false` | **Yes** | Exact match |
| `0106_contract_record_provenance` | **Yes** | Exact match |
| `0107_contract_type_catalogue_fk` | **Yes** | Exact match |
| `0108_document_version_entity` | **Yes** | Exact match |
| `0109_signature_request_document_version` | **Yes** | Exact match |
| `0105_approval_requirement_decision` | **No** | **Misreported.** Approval migration is **`0110_approval_requirement_decision`**, not 0105. No file matching `*0105_approval*` exists in any branch history searched. |

### Collision / divergence analysis

| Check | Result |
|---|---|
| Duplicate migration numbers on branch | **None** — linear chain 0100→0110 |
| Divergent migration branches | **None on this branch.** `origin/main` stops at 0104. |
| Missing dependencies | **None detected** — each migration depends on immediate predecessor. |
| Approval migration from outdated branch? | **No** — `0110` correctly depends on `0109` (DocumentVersion + signature binding from PAR-DOC-001). Not based on pre-0108 model. |
| Merge migration required? | **Not on this branch alone.** A merge migration would be required only if another branch independently added conflicting `0105+` files onto `main`. Currently `main` has no competing 0105+. |
| Locally applied? | **`e2e.sqlite3`:** 0100–0110 all applied. **`db.sqlite3`:** empty / no 01xx records. `showmigrations` reports all 0100–0110 applied in current dev environment. |

---

## 6. Roadmap truth table

Source: `docs/roadmap/PLATFORM_ALIGNMENT_ROADMAP.md` (feature branch only). Statuses below are **not modified** by this audit.

| PAR ID | Roadmap file status | Implementation evidence | Evidence folder | Commit | Tests | Verified status |
|---|---|---|---|---|---|---|
| **PAR-CORE-001** | **Completed** | Ownership/provenance guards, lifecycle wiring | `docs/audits/evidence/2026-07-22-par-core-001/` | `d7678108` (complete), `c4f67b50` (start) | `tests/test_pdr0002_core001.py`, `tests/test_pdr0002_core001_ownership.py` — run OK in audit | **Completed** on branch — implementation + evidence + tests present. Roadmap header stale (“Last refined: PAR-CORE-002”). |
| **PAR-CORE-003** | **Completed** | Provenance fields, migration 0106 | `docs/audits/evidence/2026-07-22-par-core-003/` | `0ebf69d9` | `tests/test_par_core_003_provenance.py` — OK | **Completed** on branch |
| **PAR-CORE-002** | **Completed** | ContractType catalogue FK, migration 0107, ADR-0011 Proposed | `docs/audits/evidence/2026-07-22-par-core-002/` | `69ba8a1f` | `tests/test_par_core_002_contract_type.py` — OK | **Completed** on branch |
| **PAR-DOC-001** | **Completed** | `DocumentVersion` entity, migrations 0108–0109 | `docs/audits/evidence/2026-07-22-par-doc-001/` | `74260855` | `tests/test_par_doc_001_document_version.py` — OK | **Completed** on branch |
| **PAR-WF-010** | **Blocked** (discovery complete) | Evidence + characterization tests only; no production schema cutover | `docs/audits/evidence/2026-07-22-par-wf-010/` | `cf2d5ae2` | `tests/test_par_wf_010_characterization.py` — OK | **Blocked** — matches prior report. ADR-0012 remains Proposed. |
| **PAR-APR-001** | **Completed** (roadmap) / **disputed** (operator) | `ApprovalRequirement`, `ApprovalDecision`, migration 0110, `approval_canonical.py` | `docs/audits/evidence/2026-07-22-par-apr-001/` | `c9ae7305` | `tests/test_par_apr_001_approval.py` — OK; `tests/test_approval_workflow.py` patched — OK in evidence | **Implementation present and tests pass**, but **governance completion is disputed**: ADR-0013 is Proposed (not Accepted); operator flagged item as disputed. **Do not treat as canonically complete without human decision.** |

### Roadmap internal inconsistencies (documented, not fixed)

- Catalogue table claims **11** Completed unique PAR IDs; list below claims **13** Completed (includes PAR-DOC-001 and PAR-APR-001).
- `Last refined` header still references PAR-CORE-002 despite later progress log entries through PAR-APR-001.
- PAR-APR-001 marked Completed in roadmap conflicts with operator dispute.

### Aggregate test run (audit verification)

```text
tests.test_pdr0002_core001
tests.test_pdr0002_core001_ownership
tests.test_par_core_003_provenance
tests.test_par_core_002_contract_type
tests.test_par_doc_001_document_version
tests.test_par_wf_010_characterization
tests.test_par_apr_001_approval
→ Ran 81 tests — OK
```

---

## 7. PAR-APR-001 salvage assessment

**Commit:** `c9ae7305` — 18 files, +1674 / −26 lines.

### Findings

| Question | Assessment |
|---|---|
| Based on outdated model? | **No.** Correctly depends on `DocumentVersion` (0108) and `SignatureRequest.document_version` (0109). Uses current `Contract` lifecycle fields. |
| Overlaps/conflicts with prior approval work? | **Extends, does not replace.** `ApprovalWorkflowService` retained; new `approval_canonical.py` layered in. `ApprovalRequest` kept as legacy mirror via `ApprovalRequirement.legacy_request` OneToOne. Overlaps with existing `ApprovalRequest` delegation (0102) and workflow approval paths — by design, not accidental fork. |
| Migration numbering conflicts? | **None on this branch.** Uses `0110`, not the misreported `0105_approval_requirement_decision`. Linear after 0109. |
| ADR numbering conflicts? | **None.** ADR-0013 is unique and Proposed. |
| Safe to rebase? | **Likely yes onto `ccf90a53`** — branch shares merge-base `0aa59204`; main adds only merge commit. Full PAR chain (0105–0110) must move together. Expect conflicts in `approval_workflow.py` / `models.py` if main evolved same files independently (low risk — main stops at 0104). |
| Safe to cherry-pick? | **PAR-APR-001 alone (`c9ae7305`): No.** Requires 0108, 0109, and all upstream migrations (0105–0107) plus service wiring from PAR-CORE/DOC slices. Cherry-pick would need ordered picks: `f3e4645f` → … → `c9ae7305` or squash merge of full stack. |
| Discard and reimplement on canonical branch? | **Optional.** Technically sound implementation, but **human decision required** because: (1) ADR-0013 not Accepted; (2) operator disputes Completed status; (3) entire governance doc tree not on `main`; (4) legacy mirror strategy may need product sign-off before merge. |

### Residuals documented in evidence (not blockers for salvage review)

- `DPAReviewPack` parallel approval model not merged
- `ApprovalRoute` template config not runtime requirements
- `ABSTAIN` outcome defined without UI
- Legacy `CHANGES_REQUESTED` char maps to `RETURNED` decision

---

## 8. Exact safe recovery plan

### Phase A — Freeze (current state)

1. **Stop implementation** on disputed items until governance reconciliation merges to `main`.
2. **Do not** mark PAR-APR-001 Completed in roadmap or accept ADR-0013 without explicit human approval.
3. **Do not** generate merge migrations or renumber ADRs/migrations during reconciliation.

### Phase B — Align branch with `main`

1. `git fetch origin main`
2. `git rebase origin/main` (or merge `origin/main` into feature branch if rebase policy forbids rewrite)
3. Resolve any conflicts in shared Phase 13 files (`approval_workflow.py`, `models.py`, migrations 0100–0104)
4. Re-run full PAR test stack (81 tests above) + `make check`

### Phase C — Governance landing

1. Open PR for **entire** `aca20a0c..c9ae7305` stack — governance docs are prerequisites for interpreting PAR work
2. Human review: accept PDR-0003 tree landing on `main` before treating branch docs as org-wide authority
3. Decide ADR disposition:
   - Accept ADR-0011 before declaring PAR-CORE-002 production-canonical
   - Keep ADR-0012 Proposed; PAR-WF-010 remains Blocked
   - **Human gate on ADR-0013** before affirming PAR-APR-001

### Phase D — PAR-APR-001 decision fork

| Path | When to use |
|---|---|
| **Keep slice** | Human accepts ADR-0013 (or amends it), disputes resolved, full migration chain merged |
| **Cherry-pick stack without APR** | Land CORE/DOC/WF-010 discovery only; defer approval split |
| **Discard APR slice** | Revert `c9ae7305` after landing 0105–0109; reimplement after ADR-0013 Accepted |

### Phase E — Post-merge hygiene

1. Fix roadmap count inconsistencies (11 vs 13) in a separate docs-only commit after human status rulings
2. Update `Last refined` header
3. Rename test modules for discoverability (`test_pdr0002_core001*` → `test_par_core_001*` optional, non-blocking)

---

## 9. Recommendation

| Option | Recommendation |
|---|---|
| Continue on current branch | **Yes, for reconciliation work** — branch holds the only in-repo governance corpus and coherent migration chain. |
| Switch to canonical branch | **`origin/main` is code-canonical but governance-incomplete.** Use `main` for production baseline; use feature branch for alignment programme until merged. |
| Rebase | **Recommended** onto `origin/main` (`ccf90a53`) before PR to eliminate “1 behind” and validate conflict surface. |
| Cherry-pick selected work | **Partial** — cherry-pick ordered groups (e.g. `aca20a0c` docs only; or CORE+DOC without APR). Do not cherry-pick `c9ae7305` alone. |
| Discard conflicting slice | **PAR-APR-001 only** — viable if human rejects Proposed ADR-0013 or disputes Completed status. Implementation quality does not appear defective; dispute is governance/status, not technical corruption. |
| Human decision required | **Yes — mandatory** for: (1) PAR-APR-001 Completed vs disputed status; (2) ADR-0013 acceptance; (3) merging governance tree to `main`; (4) whether to land approval split before or after ADR acceptance. |

### Primary recommendation

**Pause implementation. Rebase `cursor/feat-platform-documentation-alignment-d7f1` onto `origin/main`. Prepare a single PR landing the governance doc tree (`aca20a0c`) and migrations 0105–0109 with PAR-CORE/DOC evidence. Hold PAR-APR-001 (`c9ae7305`) behind an explicit human decision on ADR-0013 and disputed Completed status — do not auto-resume approval work after this audit.**

---

## 10. Audit metadata

- **Migrations generated:** None  
- **Commits created:** None  
- **Roadmap modified:** No  
- **ADRs/PDRs modified:** No  
- **Next action:** Await human direction per §9 before resuming implementation
