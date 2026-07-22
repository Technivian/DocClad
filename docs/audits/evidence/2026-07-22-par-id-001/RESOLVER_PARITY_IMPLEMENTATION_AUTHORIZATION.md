# Implementation authorization — PAR-ID-001 resolver parity (comparison only)

**Programme:** PAR-ID-001  
**ADR:** ADR-0014 **Accepted**  
**Prerequisite:** PR [#55](https://github.com/Technivian/CLMOne/pull/55) merged to `main` @ `bb881ac2` (feature-flagged shadow sync)  
**Draft PR:** [#58](https://github.com/Technivian/CLMOne/pull/58) — `cursor/feat-par-id-001-resolver-parity` @ `282c66e3`  
**Review package timestamp:** 2026-07-22T14:00:00Z  
**Status:** **Reviewed — Pending Votes** — scope and binding conditions locked below; Product, Engineering, and Security-advisory votes **not invented** and remain **Requested**

---

## Review disposition

| Artifact | Review finding |
|---|---|
| `RESOLVER_USAGE_MATRIX.md` | **Accepted as inventory** — correctly separates parity-candidates from workspace-only / explicit-FK / display-only paths |
| Candidate resolvers | **Accepted** — `WorkflowTemplateStep.resolve_assignee` and `workflow_routing.resolve_rule_assignee` plus launch/initiation chains (RES-WF-01…04, RES-APR-01…05) |
| Out of scope paths | **Confirmed excluded** — membership authority, navigation, signer email transitions, explicit reviewer FKs, contract owner FK, finance threshold policy |
| Implementation in PR #58 | **None present** (docs-only) — correct; no comparison wiring until votes recorded |

---

## Motion — Authorize non-authoritative resolver comparison

**Text:** Authorize a default-off feature flag that evaluates legacy and canonical process-role resolution **in parallel** for the approved candidate resolvers only, records diagnostic outcomes, emits tenant-scoped permission-safe evidence, and **always returns the legacy resolver result unchanged**. No production decision may use canonical output. No automatic repair. Immediate rollback by disabling the flag.

| Approver | GitHub identity | Governance capacity | Authority basis | Vote | Consent |
|---|---|---|---|---|---|
| Haroon Wahed | @haroonwahed | Product governance | CODEOWNERS `/docs/`; Charter v2.0 | **Requested** | Pending — requires real ISO-8601 UTC timestamp |
| Technivian | @Technivian | Engineering governance | CODEOWNERS `/contracts/`; PDR-0003 | **Requested** | Pending — requires real ISO-8601 UTC timestamp |
| Security & privacy (advisory) | @Technivian | Security review capacity | SECURITY_PRIVACY_ACCESS_AND_AUDIT; Charter §7 | **Requested (advisory, with binding conditions)** | Pending — requires real ISO-8601 UTC timestamp + conditions acknowledged |

**Result:** **Not authorized for implementation** until all three votes are recorded verbatim with ISO-8601 UTC timestamps and explicit confirmation that the slice remains non-authoritative.

---

## Exact approved scope (when votes are recorded)

The authorized slice may **only**:

1. Add `PROCESS_ROLE_RESOLVER_PARITY_ENABLED`, default **off**.
2. Evaluate legacy and canonical resolution in parallel for:
   - `WorkflowTemplateStep.resolve_assignee` and its launch/materialize/simulation call chains;
   - `workflow_routing.resolve_rule_assignee` and its plan/initiate/API/workflow-create call chains.
3. Always return the legacy resolver result to callers.
4. Record diagnostic outcomes only:
   - `MATCH`
   - `LEGACY_ONLY`
   - `CANONICAL_ONLY`
   - `DIFFERENT_USER`
   - `DIFFERENT_ROLE`
   - `AMBIGUOUS`
   - `INACTIVE_ASSIGNMENT`
   - `CROSS_TENANT_ANOMALY`
   - `RESOLUTION_ERROR`
5. Emit tenant-scoped, permission-safe evidence **without** exposing restricted identity or role metadata (no credentials; no contract content; no privileged membership dumps).
6. Never auto-repair, overwrite, block, or alter production behaviour.
7. Fail safely when the canonical comparison path errors (legacy result still returned).
8. Support immediate rollback by disabling the flag.
9. Add tests proving legacy output remains authoritative in every outcome class.
10. Produce staging parity evidence and critical-drift counts (diagnostics only).

| Item | Authorized when votes recorded |
|---|---|
| Flag `PROCESS_ROLE_RESOLVER_PARITY_ENABLED` (default off) | **Yes** |
| Parallel legacy + canonical evaluation (candidates above) | **Yes** |
| Always return legacy result | **Yes** |
| Diagnostic classifications listed above | **Yes** |
| Tenant-scoped permission-safe evidence | **Yes** |
| Staging parity evidence + critical-drift counts | **Yes** |
| Tests proving legacy authority for every outcome | **Yes** |
| Fail-safe on canonical errors | **Yes** |
| Flag-off rollback | **Yes** |

---

## Explicitly excluded (binding)

| Item | Authorized |
|---|---|
| Canonical result returned to callers / dual-return | **No** |
| Production decision uses canonical output | **No** |
| Access or privilege changes | **No** |
| Membership-authority changes | **No** |
| Navigation changes | **No** |
| Approval routing changes | **No** |
| Signer-selection changes | **No** |
| Workflow-assignment return-value changes | **No** |
| Contract-owner changes | **No** |
| Legacy resolver removal | **No** |
| Automatic repair / correction / overwrite | **No** |
| Blocking production flows on drift | **No** |
| PAR-APR-002 / PAR-WF-010 | **No** |
| Privilege / resolver cutover | **No** |
| Merging or implementing before votes recorded | **No** |

---

## Binding Security advisory conditions

Must be acknowledged in the Security vote:

1. **No production decision uses canonical output** — legacy return value remains authoritative for every caller.
2. **No cross-tenant data leakage** — comparison and evidence remain org-scoped; tenant mismatch is not reported with foreign org payloads.
3. **No automatic correction** — drift never repairs, overwrites, or mutates assignments/resolvers.
4. **Security escalation for `CROSS_TENANT_ANOMALY`** — diagnostic fail-closed for that comparison operation plus a security finding; still return the legacy result to the production caller.
5. **Diagnostic-only logging** — permission-safe; no restricted identity/role metadata, credentials, or contract content.
6. **Feature flag default off** — `PROCESS_ROLE_RESOLVER_PARITY_ENABLED` defaults false; enabling is explicit, reversible, auditable.
7. **Separate authorization required** for dual-return or privilege cutover.
8. Workspace OWNER/ADMIN/MEMBER are never treated as process-role comparison targets.
9. Ambiguous ADMIN mappings remain explicit (`legacy_process_admin` / `AMBIGUOUS`); never merged with workspace ADMIN.
10. Canonical path errors → `RESOLUTION_ERROR` evidence; legacy result unchanged.

---

## Proposed test matrix (implementation gate)

| Case | Flag | Expectation |
|---|---|---|
| Flag off | off | Identical legacy behaviour; no comparison events |
| Flag on + MATCH | on | Legacy user returned; diagnostic MATCH; no mutation |
| LEGACY_ONLY | on | Legacy user returned; canonical empty |
| CANONICAL_ONLY | on | Legacy `None`/prior result returned; canonical-only recorded |
| DIFFERENT_USER | on | Legacy user returned; drift recorded |
| DIFFERENT_ROLE | on | Legacy user returned; drift recorded |
| AMBIGUOUS (profile ADMIN) | on | Legacy result returned; AMBIGUOUS classification |
| INACTIVE_ASSIGNMENT | on | Legacy result returned; inactive canonical noted |
| Delegation present | on | Compare active status/delegation fields; return legacy |
| Unresolved legacy | on | Legacy `None` returned; classification recorded |
| Canonical RESOLUTION_ERROR | on | Legacy result returned; error audited; no raise to caller |
| CROSS_TENANT_ANOMALY | on | Legacy result returned; security finding; diagnostic fail-closed |
| No automatic repair | on | Assignments/resolvers unchanged after comparison |
| Evidence hygiene | on | No credentials/contract content; no restricted role dumps |
| Staging critical-drift counts | on | Deterministic counts for CI/staging evidence |
| JSON diagnostics | on | Deterministic, org-filterable output suitable for evidence |

Regression gate after implementation (not now): shadow-sync, RoleDefinition, ProcessRoleAssignment, PAR-ID characterization, tenant-isolation, approval suites, WF-010 characterization, governance checks.

---

## PR readiness verdict

| Gate | Verdict |
|---|---|
| Docs-only draft PR #58 @ `282c66e3` | **Acceptable as authorization package** |
| CI on #58 | **Green** (6/6 at review time) |
| Implementation present | **No** (correct) |
| Votes recorded | **No** — Product / Engineering / Security still **Requested** |
| Ready to implement | **No** |
| Ready to merge implementation | **No** |
| Ready to mark non-docs implementation PR | **Blocked** until votes recorded |

**Verdict:** **NOT READY TO IMPLEMENT OR MERGE** — review package is complete; authorization incomplete pending three named votes with real ISO-8601 UTC timestamps.

---

## Next cutover gate (after this slice, separate authorization)

Comparison slice completion does **not** authorize cutover. Cutover readiness requires separate Product + Engineering + Security authorization and all of:

1. Staging shadow + assignment critical drift = 0 for target orgs.
2. Resolver comparison free of H-risk `DIFFERENT_USER` / `CROSS_TENANT_ANOMALY` on candidates (or accepted with explicit residual).
3. Ambiguous ADMIN cases explicitly classified and accepted.
4. Threat review + rollback plan accepted.
5. Separate dual-return / privilege-cutover authorization.
6. Legacy resolvers retained until cutover criteria met.

---

## Implementation gate

Do **not** add `PROCESS_ROLE_RESOLVER_PARITY_ENABLED` wiring, comparison hooks, or merge any implementation PR until this file records verbatim Product, Engineering, and Security-advisory Approve votes with ISO-8601 UTC timestamps.
