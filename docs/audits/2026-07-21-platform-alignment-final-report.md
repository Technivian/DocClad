# Platform Alignment Final Report

**Date:** 2026-07-21  
**Programme branch:** `cursor/feat-platform-documentation-alignment-d7f1`  
**Authority:** Active Charter · PDR-0003 · supporting accepted docs  

---

## 1. Executive summary

CLM One was audited against the documentation operating model and a repository-grounded alignment roadmap was executed for **Foundation** and **Pilot hardening** items.

Critical published-immutability and silent instance-migration defects were remediated with tests. Canonical Configuration nav gaps (Data Manager, Entities) were closed at pilot depth. Auth alias redirects that bypassed login were fixed.

**Honest recommendation: Ready with controlled limitations** for continued controlled pilot on the hardened workflow/nav/security slices. **Not ready** to claim full canonical domain completion or enterprise readiness.

---

## 2. Starting maturity

| Lens | Starting |
|---|---|
| Pilot product | Pilot-ready with limitations |
| Domain fidelity | Skeletal → Partial |
| Workflow engine vs docs | Partial / conflicting immutability |
| Enterprise | Not ready |

Baseline: Django check PASS; workflow suite 62 PASS; broader isolation suite had pre-existing failures (recorded).

---

## 3. Final maturity

| Lens | Ending |
|---|---|
| Pilot product | **Pilot-ready with fewer critical workflow defects** |
| Domain fidelity | Still Partial (Definition/Obligation/Property not first-class) |
| Workflow engine | **Improved Partial** — mutate gates, defaults, governed migration |
| Enterprise | Not ready |

---

## 4. Completed capabilities (this programme)

- Published workflow template immutability enforcement (HTTP + Admin)
- Unpublished-by-default templates
- Governed instance migration with audit
- Workflow invariant automated tests
- Data Manager interim hub + Entities nav
- Login-required legacy list aliases
- My Work / Command Center boundary documentation

---

## 5. Canonical domain changes

- No new first-class Definition/Obligation/Property models (Future + ADR required)
- Terminology: Entities nav maps to Counterparty (interim)
- Data Manager exposes FieldDefinition catalog with explicit Property Definition gap

---

## 6. Architecture changes

- Modular monolith retained
- Migration helper API tightened (reason required)
- Proposed ADR-0010 documents interim pin model

---

## 7. Security and access changes

- Server-side blocks on published template edits
- Anonymous users cannot skip login via legacy list aliases
- Cross-org activity alias returns 404 via tenant queryset

---

## 8. Workflow-engine changes

- UpdateView mutate gate
- Admin readonly/save_model guard
- `is_active` default False + migration 0105
- `migrate_workflows_to_template` audit + reason
- Invariant tests for simulation dry-run and publish blockers

---

## 9. UX and accessibility changes

- Nav: Data Manager, Entities
- Data Manager hub empty/forbidden states
- Full WCAG AA sweep **not** claimed

---

## 10. Test and evidence results

- Verification suite: **74 passed** (`docs/audits/evidence/2026-07-21-platform-alignment-final/verification-suite.txt`)
- Baseline evidence: `docs/audits/evidence/2026-07-21-platform-alignment-baseline/`

---

## 11. Migrations

- `0105_workflowtemplate_is_active_default_false`

---

## 12. Rollback strategy

1. Revert programme commits on the feature branch.
2. `migrate contracts 0104` to restore prior field default.
3. Redeploy previous artifact if shipped.

---

## 13. Approved decisions used

- GOVERNANCE_CHARTER (active)
- PDR-0003 Accepted
- PDR-0001 / PDR-0002 (referenced, not reopened)
- ADR-0009 Accepted (Charter supersession)

---

## 14. Proposed decisions awaiting approval

- **ADR-0010** Workflow instance version pinning interim

---

## 15. External blockers

- Charter v3 approval
- Production cutover for Definition/Version split
- External IdP/vuln-scan credentials

---

## 16. Remaining future roadmap items

See `docs/roadmap/PLATFORM_ALIGNMENT_ROADMAP.md` Future section (PAR-WF-010, PAR-OBL-*, PAR-DATA-001, PAR-AI-001, etc.).

---

## 17. Deployment sequence

1. Merge feature branch after review.
2. Run `manage.py migrate`.
3. Smoke: Workflow Designer publish/edit, Data Manager hub, Entities list, anonymous `/contracts/` → login.
4. Confirm Admin cannot save published templates.

---

## 18. Operational handover

- Monitor AuditLog for `workflow_instance_template_migrated`
- Ops using `migrate_workflow_template` must pass `--migration-reason`
- Do not treat Proposed ADR-0010 as Accepted

---

## 19. Definition-of-done assessment

| Criterion | Met? |
|---|---|
| Audit complete | Yes |
| Traceability matrix complete | Yes (material rules) |
| Roadmap complete with terminal states | Yes |
| All implementable in-scope Foundation/Pilot items complete | Yes |
| No Critical/High without decision/exception/blocker | Criticals remediated or ADR Proposed; remaining Highs Future/Blocked |
| Full canonical domain implemented | **No** — Future |
| Full a11y / enterprise identity | **No** |
| Unrelated WIP untouched | Yes (started clean) |

---

## 20. Final recommendation

### Ready with controlled limitations

Safe to continue the **controlled pilot** with the hardened workflow immutability, migration audit, nav IA, and auth alias fixes.

**Not ready** to declare enterprise completion or full documentation-domain parity until Future Core items and Accepted ADRs land.

---

## PR #48 Final Merge Gate

**Gate date:** 2026-07-22 (UTC)  
**PR:** https://github.com/Technivian/CLMOne/pull/48  
**Branch:** `cursor/feat-platform-documentation-alignment-d7f1`  
**Mode:** Verification only — no new roadmap capabilities implemented during this gate.  
**Evidence root:** `docs/audits/evidence/2026-07-22-pr48-merge-gate/`

### Critical and High gap disposition table

| Gap ID | Severity | Title | Final disposition | Pilot reachability |
|---|---|---|---|---|
| G-WF-01 | Critical | Published templates editable via UpdateView/Admin | **Completed** | Mutate gates + Admin save block; invariant tests |
| G-WF-02 | Critical | Silent live-instance template rebinding | **Completed** (code + audit); ADR-0010 remains Proposed docs only | `reason` required; AuditLog `workflow_instance_template_migrated`; mgmt `--migration-reason` |
| G-WF-03 | High | `is_active` default True | **Completed** | Model default False + migration 0105; seeds set True explicitly |
| G-DOM-01 | High | No Workflow Definition entity | **Outside controlled-pilot scope with enforced controls** | Designer authoring denied under `CONTROLLED_PILOT_ENABLED`; Future PAR-WF-010 |
| G-DOM-02 | High | Dual ContractType enum vs model | **Deferred by approved decision** | Known interim; Future roadmap (no cutover in this PR) |
| G-DOM-03 | High | Obligations = Deadline alias | **Outside controlled-pilot scope with enforced controls** | `/contracts/obligations` denied in pilot middleware |
| G-NAV-01 | High | Data Manager / Entities missing from nav | **Completed** | Nav + Data Manager hub; Entities → counterparties |
| G-SEC-01 | High | Cross-tenant / unauthenticated list redirect failures | **Completed** for auth-bypass defects; residual stale list assertion **Deferred by approved decision** (PAR-SEC-001 follow-up) | Anonymous alias bypass fixed; remaining FAIL is intentional 302→repository (not a leak) |
| Matrix: publish validation | High | Blocking validation before publish | **Completed** for pilot depth | `validate_template_for_publish` + invariant tests (PAR-WF-005) |
| Matrix: Contract provenance depth | High | Record provenance completeness | **Deferred by approved decision** | Future PAR-CORE-003; not opened in pilot UI as new claim |
| Matrix: Approval Requirement/Decision | High | Collapsed approval model | **Deferred by approved decision** | Future PAR-APR-001 |
| Matrix: Material Audit completeness | High | Admin/publish/migration audit gaps | **Completed** for published-mutate + instance-migration slices; remainder **Deferred by approved decision** | Migration/Admin immutability audited in this programme |
| Matrix: Uniform authz (search/AI) | High | Same access rules everywhere | **Outside controlled-pilot scope with enforced controls** | AI entry points denied when `GEMINI_AI_ENABLED=false` (pilot default) |
| Matrix: Property Definitions | High | Central Property Definition governance | **Outside controlled-pilot scope with enforced controls** | Configuration nav hidden in pilot; hub documents gap; Future PAR-DATA-001 |
| Matrix: PDR-0002 remaining drift | High | Stage/status vocabulary leftovers | **Deferred by approved decision** | Future PAR-CORE-001 |
| Matrix: Role Definition dualism | High | Membership vs Profile roles | **Deferred by approved decision** | Future PAR-ID-001; pilot seed uses both intentionally |

No Critical or High gap remains **reachable through controlled-pilot routes, roles, workflows, APIs, seeded data, navigation, or background jobs** without an explicit disposition above.

### ADR-0010 dependency conclusion

**PR #48 implementation does not depend on Proposed ADR-0010 being Accepted.**

- Governed migration (`reason` + AuditLog) is enforced in code under already-accepted domain/engine rules and the Foundation roadmap item PAR-WF-002.
- ADR-0010 is **Proposed documentation only** of the interim pin model (`Workflow.template` FK → `WorkflowTemplate` row).
- ADR-0010 is **non-authorizing**: it must not be cited as Accepted approval for Definition/Version cutover or silent rebinds.
- **Do not mark ADR-0010 Accepted** without an authorized approver. No temporary exception is required for merge on this point because runtime behaviour does not require ADR acceptance.

### Migration evidence (`0105_workflowtemplate_is_active_default_false`)

| Claim | Evidence |
|---|---|
| Existing active/published rows retain `is_active` | Django gate test PASS — `tests/test_migration_0105_gate_proof.py` |
| New templates default inactive | Same test: create-after-forward → `is_active=False` |
| Controlled-pilot / product seeds remain launchable (active) | NDA/MSA/DPA RunPython seeds set `is_active=True` explicitly (`0071`/`0075`/`0077`); `seed_controlled_pilot` does not create templates |
| Forward migration succeeds | Applied in test DB + gate proof |
| Rollback to `0104_myworksavedview` succeeds | Gate proof reverse migrate; row values unchanged |
| Re-forward succeeds | Gate proof re-apply; no orphaned/missing rows |
| No silent deactivation / rewrite | Migration is **AlterField-only** (no `RunPython`) — `contracts/migrations/0105_workflowtemplate_is_active_default_false.py` |

Artifact: `docs/audits/evidence/2026-07-22-pr48-merge-gate/migration-0105-django-test.txt`

### Test results

| Suite | Result |
|---|---|
| Django system checks | PASS |
| Governance authority (`scripts/check_governance_authority.sh`) | PASS |
| Doc link validation (audit / roadmap / ADR-0010) | PASS |
| Targeted workflow + invariants + versioning + simulation + audit trail + execution + controlled-pilot scope + migration 0105 | **68 PASS** |
| Full `tests.test_cross_tenant_isolation` | **74 PASS / 1 FAIL** (catalogued below) |
| Controlled-pilot critical Playwright | **Not executed to green** — e2e webServer bootstrap blocked by pre-existing `seed_demo_command_center` / DPA assignee launch policy (see known failures). Substituted: Django pilot-scope tests PASS + prior 2026-07-20 Playwright evidence (27 passed). |

### Known pre-existing failures

Full catalog: `docs/audits/evidence/2026-07-22-pr48-merge-gate/known-preexisting-failures.md`

1. **`ContractIsolationTest.test_list_shows_only_own_org`** — expects 200; gets intentional 302 → repository. Baseline evidence identical. Pilot impact: none. Owner: Eng. Tracking: G-SEC-01 / PAR-SEC-001 follow-up. Does not block: not a tenant leak; PR reduced isolation failures from 5→1.
2. **Playwright e2e bootstrap `WorkflowLaunchBlocked` (DPA steps lack assignees)** — pre-existing relative to PR #48 behaviour diffs. Pilot impact: e2e demo seed only. Owner: Eng (fixtures). Does not block: NDA/MSA/DPA seeds remain `is_active=True`; Django controlled-pilot scope PASS.

### PR diff hygiene

| Check | Result |
|---|---|
| Unrelated WIP | No uncommitted feature WIP in gate pass. Historical commits include `artifacts/chatgpt-project-source/` mirror + `logs/devserver.boot_sha` — documentation upload aids, not product behaviour; no secrets/contract content observed. |
| Proposed Charter as authority | PASS — Charter v3 remains Proposed; governance script PASS |
| Generated export artifacts | None in behaviour path |
| Secrets / contract content | No production secrets; test passwords only |
| Unrelated UI/theme | Only `theme/templates/contracts/data_manager_hub.html` (nav programme) |
| Material behaviour changes tested + audited | Immutability, migration reason/audit, defaults, nav, auth aliases covered |

### Pilot-scope safety conclusion

With `CONTROLLED_PILOT_ENABLED=true`, designer authoring, obligations, DPA review packs, approval-rule authoring, signatures, upload/freeform create, and law-firm commercial modules remain denied. Configuration nav (including Data Manager / Entities / Designer) is hidden. Published-template mutate and silent instance retarget defects are closed. Remaining High domain gaps are deferred or outside pilot with enforced controls. **No unresolved Critical or High issue is reachable through the controlled-pilot surface.**

### Exact merge recommendation

**APPROVE WITH NAMED CONDITIONS**

Named conditions (must remain true at merge):

1. **ADR-0010 stays Proposed** — do not Accept without authorized approval; do not treat it as merge authority.
2. **PAR-SEC-001 follow-up** remains open for updating `ContractIsolationTest.test_list_shows_only_own_org` to assert repository redirect + repository isolation (not a blocker).
3. **Playwright re-run** on a healthy e2e seed (DPA assignee fixtures) is recommended post-merge or as a follow-up CI job; this gate relies on Django pilot-scope + prior pilot Playwright evidence because bootstrap is blocked by a pre-existing demo-seed issue outside PR #48’s behavioural diff.
4. **Future High domain items** (Definition, Obligation model, Property Definition, Role dualism, provenance depth, dual ContractType) remain out of claim for this merge — Future roadmap only.

**Not APPROVE (unconditional)** solely because conditions 2–3 are operational follow-ups that should stay visible.  
**Not DO NOT MERGE** because no reachable Critical/High gap remains unresolved.
