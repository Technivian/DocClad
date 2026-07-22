# Platform Alignment Tranche-1 — programme integration merge gate

**Date:** 2026-07-22  
**Integration branch:** `cursor/feat-platform-alignment-tranche-1`  
**Base commit:** `cf2d5ae2` (+ non-destructive merge of `origin/main` → `60f92dfc`)  
**Continuation branch (preserved):** `cursor/feat-platform-documentation-alignment-d7f1` @ `c9ae7305` (PAR-APR-001)  
**Prior PR:** [#48](https://github.com/Technivian/CLMOne/pull/48) (draft; head branch superseded for merge scope)

---

## 1. Scope verification

| Requirement | Present | Evidence |
|---|---|---|
| Accepted governance documentation | Yes | `docs/governance/GOVERNANCE_CHARTER.md`, PDR-0003, Accepted supporting docs |
| Foundation hardening (PAR-WF-001/002/003/005, PAR-AUD-001) | Yes | Roadmap + `tests/test_platform_workflow_invariants.py` |
| Pilot hardening (PAR-NAV-001, PAR-SEC-001, PAR-WORK-001) | Yes | Nav hub, isolation fixes, boundary doc |
| PAR-CORE-001 | Yes | `d7678108`; `tests/test_pdr0002_core001*.py`; evidence `2026-07-22-par-core-001` |
| PAR-CORE-002 | Yes | `69ba8a1f`; migration 0107; evidence `2026-07-22-par-core-002` |
| PAR-CORE-003 | Yes | `0ebf69d9`; migration 0106; evidence `2026-07-22-par-core-003` |
| PAR-DOC-001 | Yes | `74260855`; migrations 0108–0109; evidence `2026-07-22-par-doc-001` |
| PAR-WF-010 discovery | Yes | `cf2d5ae2`; Proposed ADR-0012; evidence `2026-07-22-par-wf-010` |
| PAR-APR-001 (`c9ae7305`) excluded | Yes | No `approval_canonical.py`; `c9ae7305` not ancestor of tranche-1 HEAD; migration `0110` is flagship assignee backfill only |

---

## 2. Integration gate results

| Check | Result | Evidence |
|---|---|---|
| Governance authority (`scripts/check_governance_authority.sh`) | **PASS** | `docs/audits/evidence/2026-07-22-tranche-1-merge-gate/governance-authority.txt` |
| Documentation links (roadmap, gap audit, ADR-0010/0012, Charter) | **PASS** | `doc-link-validation.txt` |
| Django system checks (`make check`) | **PASS** (0 issues) | `django-check.txt` |
| Migrations 0105→0109 forward | **PASS** | `migration-0105-0109.txt` |
| Migrations 0109→0104 rollback | **PASS** | `migration-0105-0109.txt` |
| Migrations 0104→0109 re-forward | **PASS** | `migration-0105-0109.txt` |
| CORE-001 tests | **PASS** | `tests/test_pdr0002_core001.py`, `tests/test_pdr0002_core001_ownership.py` |
| CORE-002 tests | **PASS** | `tests/test_par_core_002_contract_type.py` |
| CORE-003 tests | **PASS** | `tests/test_par_core_003_provenance.py` |
| DOC-001 tests | **PASS** | `tests/test_par_doc_001_document_version.py` |
| WF-010 characterization tests | **PASS** | `tests/test_par_wf_010_characterization.py` |
| Tenant isolation suite | **PASS with 1 named residual** | `tests/test_cross_tenant_isolation.py` — `test_list_shows_only_own_org` (302 redirect; PAR-SEC-003) |
| Cross-tenant mutation guardrails | **PASS** | `tests/test_cross_tenant_mutation_guardrails.py` |
| Controlled-pilot scope | **PASS** | `tests/test_controlled_pilot_scope.py` |
| Workflow invariants + migration 0105 proof | **PASS** | `tests/test_platform_workflow_invariants.py`, `tests/test_migration_0105_gate_proof.py` |
| **Aggregate targeted gate** | **157 PASS / 1 FAIL (named residual)** | `targeted-tests.txt` — 158 tests |

### Named residual (non-blocking; carried from PR #48 gate)

- `ContractIsolationTest.test_list_shows_only_own_org` — expects 200 on legacy list alias; product returns 302 to repository. Cross-org detail/update remain 404. Tracked as **PAR-SEC-003**; not a tenant data leak.

---

## 3. Included commits (programme stack through WF-010 discovery)

From merge-base `0aa59204` through `cf2d5ae2`:

```
aca20a0c Adopt CLM One documentation operating model under docs/.
a643a41d Cursor: Apply local changes for cloud agent
c4d04d46 docs(audit): platform gap assessment and alignment roadmap
f3e4645f fix(workflows): enforce published immutability and governed migration
c8a4da71 feat(nav): add Data Manager hub and Entities configuration entries
7fe24736 fix(security): require login before legacy list alias redirects
678d1f3a docs(roadmap): record completed alignment milestones and final report
308884a4 docs(audit): record PR #48 final merge gate evidence
47414726 docs(roadmap): refine living platform alignment roadmap
c4f67b50 feat(lifecycle): start PAR-CORE-001 PDR-0002 alignment slices
d7678108 feat(lifecycle): complete PAR-CORE-001 PDR-0002 ownership gaps
0ebf69d9 feat(provenance): complete PAR-CORE-003 Contract Record provenance
69ba8a1f feat(domain): complete PAR-CORE-002 Contract Type catalogue reconciliation
74260855 feat(documents): complete PAR-DOC-001 Document Version hardening
cf2d5ae2 docs(workflow): PAR-WF-010 discovery and cutover design (blocked)
```

Plus integration merge commit:

```
60f92dfc merge: incorporate origin/main (non-destructive) into tranche-1 integration branch
```

---

## 4. Excluded commits (continuation branch only)

```
c9ae7305 feat(approvals): complete PAR-APR-001 Requirement/Decision split
```

Preserved on `cursor/feat-platform-documentation-alignment-d7f1` — not discarded.

---

## 5. Roadmap correction applied

- **PAR-APR-001** → **In progress** (continuation branch `c9ae7305`)
- Recorded: additive schema + primary dual-write delivered on continuation branch
- Listed remaining cutover criteria (ADR-0013 acceptance, legacy read-path retirement, DPAReviewPack, etc.)
- Added **Tranche-1 programme integration gate** before **PAR-ID-001**
- Tranche-1 PR scope excludes PAR-APR-001 implementation

---

## 6. Merge recommendation

**APPROVE WITH NAMED CONDITIONS** — same disposition as PR #48 final merge gate.

| Action | Recommendation |
|---|---|
| Tranche-1 → `main` | **Ready for draft PR / human review** after retargeting from full-stack branch |
| PR #48 | **Retarget head** to `cursor/feat-platform-alignment-tranche-1` **or** close #48 and open a new PR for Tranche-1; update PR body to reflect narrowed scope and PAR-APR-001 deferral |
| Continuation branch | Keep `cursor/feat-platform-documentation-alignment-d7f1` @ `c9ae7305` for PAR-APR-001 completion; merge after Tranche-1 lands and ADR-0013 is Accepted |
| PAR-ID-001 | **Do not start** until Tranche-1 gate passes on `main` |

---

## 7. PR #48 handling

| Item | Detail |
|---|---|
| Current state | Open **draft** PR #48; head = `cursor/feat-platform-documentation-alignment-d7f1` (includes `c9ae7305`) |
| Problem | Full branch scope mixed Tranche-1 deliverables with disputed PAR-APR-001 implementation |
| Resolution | **Normalize PR scope:** Tranche-1 branch is the merge candidate for governance + Foundation/Pilot + CORE/DOC + WF-010 discovery |
| Recommended steps | 1) Push `cursor/feat-platform-alignment-tranche-1`; 2) Change PR #48 base branch head to tranche-1 **or** close #48 with pointer to new Tranche-1 PR; 3) Leave PAR-APR-001 on `d7f1` for follow-up PR after human ADR-0013 decision |
| Evidence continuity | PR #48 merge-gate evidence (`docs/audits/evidence/2026-07-22-pr48-merge-gate/`) remains valid for Foundation/Pilot slices; this gate supersedes it for Tranche-1 scope |

---

## 8. Capability confirmation

**No new product capabilities were implemented during this integration normalization.** Changes are limited to:

- Branch creation at `cf2d5ae2`
- Non-destructive merge of `origin/main`
- Roadmap status / PR-scope documentation
- Merge-gate evidence capture

---

## 9. HEAD reference

```
Branch: cursor/feat-platform-alignment-tranche-1
HEAD:   7afa7b73
Parent: d9ded244 (PAR-SEC-003 + DOC-001 seed fix)
```

---

## 10. PR #50 CI blocker triage (2026-07-22)

**PR:** [#50](https://github.com/Technivian/CLMOne/pull/50) — `cursor/feat-platform-alignment-tranche-1`  
**Pre-fix CI (run `29903469042` et al.):** 7/8 checks failing; only `verify-ui` green.

### Root-cause classification

| Check | Root cause | Class | Fix applied |
|---|---|---|---|
| Forbidden-brand scan | Historical audit markdown + `artifacts/` archive mention legacy CMS Aegis/DocClad in negative findings — not live product copy | **#5** pre-existing historical docs; **#2** missing scan exclusions | Added `artifacts/` to `EXCLUDE_DIRS`; added `PAYROLLMINDS_CLM_READINESS_AUDIT.md` and `PRE_DEMO_READINESS_REPORT.md` to `EXCLUDE_FILES` with documented rationale |
| Anti-drift + contrast | ADR-0008 path moved under `docs/governance/decisions/adr/`; `approval_request_list.html` intentionally uses `_workflow_designer_tabs.html` | **#1** Genuine Tranche-1 defect | Updated `tests/test_design_system_phase1_foundation.py` ADR path; aligned `tests/test_design_system_phase2a.py` expectations |
| pr-release-evidence | PR body missing required checklist lines | **#2** Missing required evidence | PR #50 body updated with checked verification items + smoke/rollback evidence |
| quality-and-tenancy | Production deploy check missing `APP_BASE_URL`, `OPERATOR_ALERT_EMAIL`, and durable storage env | **#3** CI configuration defect | Added valid HTTPS `APP_BASE_URL`, operator email, and S3 storage env to `.github/workflows/platform-guardrails.yml` (validation unchanged) |
| security-scans | `theme/static_src` npm audit: `brace-expansion` (high), `tar` (critical) | **#5** pre-existing transitive deps | `npm audit fix` in `theme/static_src` (lockfile updated) |
| redesigned-e2e | Smoke test expected legacy `.page-wrap.cw-page` at `/contracts/` (302→repository) and hidden subtitle copy | **#1** Genuine Tranche-1 test drift | Updated `client/tests/e2e/smoke.spec.js` selectors for repository + workflow ops shells |
| Phase 1 visual baselines | Template migration drift + wrong markers/paths; bootstrap fixed in pass 2 | **#1** Genuine Tranche-1 visual drift | Updated `visual-baselines.spec.js` paths/markers; regenerated `phase-1-*-darwin.png` snapshots |
| quality-and-tenancy (pass 2) | `test_contract_list_query_count_*` hit 302 on legacy list alias | **#1** Test drift (PAR-SEC-003) | Point performance guardrail at `contracts:repository` |

### Why visual / redesigned-E2E ran on this PR

Both workflows path-filter on `theme/templates/**` and `client/**`. Tranche-1 includes template and navigation changes, so the filters correctly triggered despite programme scope being governance/CORE/DOC.

### Local re-verification (post-fix)

| Check | Local result |
|---|---|
| `scripts/check_brand_regression.sh` | **PASS** |
| `tests/test_design_system_phase1_foundation` + `phase2a` | **PASS** (33 tests) |
| `tests/test_demo_command_center` | **PASS** (4 tests) |
| `tests/test_cross_tenant_isolation.ContractIsolationTest.test_list_shows_only_own_org` | **PASS** (302 → repository) |
| `seed_payrollminds_demo` (idempotent ×2) | **PASS** |
| Production deploy check (CI-equivalent env) | **PASS** (`manage.py check --deploy --fail-level WARNING`) |
| `theme/static_src` npm audit `--audit-level=high` | **PASS** (0 vulnerabilities) |
| `client` npm audit `--audit-level=high` | **PASS** (0 high/critical) |
| `scripts/check_design_system_contrast.sh` | **PASS** |

### Named residual (unchanged)

- **M1-E2E-001** — Playwright DPA assignee bootstrap flake (non-blocking; isolated from Tranche-1 merge gate)
- **Human review** — required before merge per programme gate; PR #50 not auto-merged

### Merge recommendation (@ `e5956ca2`)

**NOT MERGE READY** — 6/8 required GitHub checks green; 2 residuals remain:

| Check | CI result | Residual |
|---|---|---|
| Phase 1 visual baselines | **FAIL** (1/5 snapshots) | `phase-1-list-darwin.png` pixel drift on macos-14 CI vs local capture — **#1** Tranche-1 UI drift |
| redesigned-e2e | **FAIL** | Smoke likely green; `critical-flows.spec.js` create/edit `selectOption` timeout — **#1** test drift vs contract create UX |

All other merge-blocking checks (**Forbidden-brand**, **Anti-drift + contrast**, **pr-release-evidence**, **quality-and-tenancy**, **security-scans**, **verify-ui**) are **PASS**.

Human review required before merge. PR #50 must not be merged until visual + e2e residuals are green or formally exempted.
