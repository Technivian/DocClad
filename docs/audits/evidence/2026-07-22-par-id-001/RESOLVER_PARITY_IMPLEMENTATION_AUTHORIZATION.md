# Implementation authorization — PAR-ID-001 Slice 4 resolver parity (comparison only)

**Programme:** PAR-ID-001  
**ADR:** ADR-0014 **Accepted**  
**Prerequisite:** PR [#55](https://github.com/Technivian/CLMOne/pull/55) merged to `main` @ `bb881ac2` (feature-flagged shadow sync); merge evidence PR [#59](https://github.com/Technivian/CLMOne/pull/59) → `0d9712ca`  
**Baseline `main` HEAD:** `0d9712ca`  
**Draft PR:** [#58](https://github.com/Technivian/CLMOne/pull/58) — `cursor/feat-par-id-001-resolver-parity`  
**Review package timestamp:** 2026-07-22T14:09:08Z  
**Authorization complete timestamp:** 2026-07-22T14:18:31Z  
**Merge commit:** `598b7a128cb8d0f5be0c7cd2fb1880f631ca9608`  
**Merged at:** `2026-07-22T14:42:13Z`  
**Reviewed HEAD (code):** `44926da923ff3b71bbfe8434794bd91f7cfe8d2e` (docs-only follow-up `f7b56ab5` before merge; config/contracts/tests unchanged vs `44926da9`)  
**Status:** **Authorized and merged**; pre-auth merge incident **Ratified and Closed** (`15:31:55Z`). Dual-return / privilege cutover / staging flag activation remain **not** authorized. PAR-ID-001: **In progress** — resolver parity merged; remediation required before staging activation.  
**Governance incident:** [`../2026-07-22-par-id-001-pr58-merge/GOVERNANCE_INCIDENT_AND_RATIFICATION_ADDENDUM.md`](../2026-07-22-par-id-001-pr58-merge/GOVERNANCE_INCIDENT_AND_RATIFICATION_ADDENDUM.md) — **Ratified and Closed**.

**Related evidence:**
- [`RESOLVER_USAGE_MATRIX.md`](RESOLVER_USAGE_MATRIX.md)
- [`RESOLVER_PARITY_TEST_MATRIX.md`](RESOLVER_PARITY_TEST_MATRIX.md)
- [`SHADOW_ROLE_SYNC_IMPLEMENTATION_AUTHORIZATION.md`](SHADOW_ROLE_SYNC_IMPLEMENTATION_AUTHORIZATION.md) (Slice 3 — merged; flags remain default off)

---

## Review disposition

| Artifact | Review finding |
|---|---|
| `RESOLVER_USAGE_MATRIX.md` | **Accepted as inventory** — correctly separates parity-candidates from workspace-only / explicit-FK / display-only paths |
| Candidate resolvers | **Accepted** — `WorkflowTemplateStep.resolve_assignee` and `workflow_routing.resolve_rule_assignee` plus launch/initiation chains (RES-WF-01…04, RES-APR-01…05) |
| Out of scope paths | **Confirmed excluded** — membership authority, navigation, signer email transitions, explicit reviewer FKs, contract owner FK, finance threshold policy |
| Implementation in PR #58 | **Authorized** — comparison wiring lands after votes recorded; legacy return remains authoritative |

---

## Motion — Authorize non-authoritative resolver comparison

**Text:** Authorize a default-off feature flag that evaluates legacy and canonical process-role resolution **in parallel** for the approved candidate resolvers only, records diagnostic outcomes, emits tenant-scoped permission-safe evidence, and **always returns the legacy resolver result unchanged**. No production decision may use canonical output. No automatic repair. Immediate rollback by disabling the flag. No staging flag activation and no merge without separate authorization.

| Approver | GitHub identity | Governance capacity | Authority basis | Vote | Consent |
|---|---|---|---|---|---|
| Haroon Wahed | @haroonwahed | Product governance | CODEOWNERS `/docs/`; Charter v2.0 | **Approve** | Recorded 2026-07-22T14:17:31Z (verbatim below) |
| Technivian | @Technivian | Engineering governance | CODEOWNERS `/contracts/`; PDR-0003 | **Approve** | Recorded 2026-07-22T14:18:31Z (verbatim below) |
| Security & privacy (advisory) | @Technivian | Security review capacity | SECURITY_PRIVACY_ACCESS_AND_AUDIT; Charter §7 | **Approve with conditions** | Recorded 2026-07-22T14:15:31Z (verbatim below) |

**Result:** **Authorized** for diagnostic-only resolver parity implementation. Merge authorization recorded below. **Does not authorize** dual-return, privilege cutover, or staging flag activation.

---

## Verbatim recorded votes (authoritative)

Source: direct user-provided authorization text (2026-07-22).  
Supersedes earlier draft vote block timestamps `14:04:28Z` / `14:05:28Z` / `14:06:28Z`.

### Product — @haroonwahed (accepted)

```text
@haroonwahed Product: Approve
Timestamp: 2026-07-22T14:17:31Z

Conditions acknowledged: yes
Slice remains non-authoritative: yes
Feature flag remains default off: yes
```

### Engineering — @Technivian (accepted)

```text
@Technivian Engineering: Approve
Timestamp: 2026-07-22T14:18:31Z
```

### Security advisory — @Technivian (accepted)

```text
@Technivian Security advisory: Approve with conditions
Timestamp: 2026-07-22T14:15:31Z

Conditions acknowledged: yes
Slice remains non-authoritative: yes
Feature flag remains default off: yes
```

Binding Security conditions (from authorization package; acknowledged with the Security vote):

1. Canonical comparison output must never replace, reorder, or filter the legacy resolver return value.
2. `PROCESS_ROLE_RESOLVER_PARITY_ENABLED` must remain disabled by default.
3. Comparison must be fail-open for product behaviour: comparison errors must not raise into or block the legacy call path.
4. Cross-tenant anomalies must be classified `CROSS_TENANT_ANOMALY` / security findings and must not attempt repair.
5. Ambiguous ADMIN mappings must remain explicit (`AMBIGUOUS`); never equate workspace ADMIN with process ADMIN.
6. Diagnostic output must be tenant-scoped and must not leak credentials, contract content, or unrestricted cross-tenant metadata via logs, reports, metrics, or audit summaries.
7. Parity must not automatically create, deactivate, or rewrite `ProcessRoleAssignment` / `UserProfile` / `OrganizationMembership` rows.
8. Enabling the flag must be explicit, reversible, auditable, and limited to an approved environment or workspace (separate activation authorization).
9. Resolver cutover, privilege migration, and returning canonical results to callers require a separate authorization, threat review, test matrix, and rollback plan.
10. This approval does not authorize merging the implementation PR.

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
9. Add tests proving legacy output remains authoritative in every outcome class (see [`RESOLVER_PARITY_TEST_MATRIX.md`](RESOLVER_PARITY_TEST_MATRIX.md)).
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
| Blocking production flows on drift / comparison failure | **No** |
| Staging flag activation (requires separate activation authorization) | **No** |
| Merge without separate explicit merge authorization | **No** |
| PAR-APR-002 / PAR-WF-010 | **No** |
| Privilege / resolver cutover | **No** |
| Merging or implementing before votes recorded | **No** |

---

## Threat and privacy conditions

### Threat model (slice-local)

| Threat | Mitigation required by this slice |
|---|---|
| Canonical path silently becomes authoritative | Hard rule: legacy return always; flag default off; tests assert identity of returned actor |
| Comparison exception breaks workflow/approval launch | Fail-open wrapper; never re-raise into caller |
| Cross-tenant assignment appears “better” and gets adopted | Classify `CROSS_TENANT_ANOMALY`; no repair; non-zero report exit |
| Workspace ADMIN conflated with process ADMIN | Keep `AMBIGUOUS` / `legacy_process_admin`; never map to `workspace_admin` |
| First-match nondeterminism misread as cutover readiness | Report candidate sets; do not change selection order |
| Flagship drafting path ignores `approver_role` (split-brain) | Document separately; do not “fix” by returning canonical actors |
| Diagnostic leakage of sensitive content | No contract bodies, secrets, or tokens in events/reports; limit fields to ids, role codes, classifications |

### Privacy / data minimization

Allowed diagnostic fields (preferred): `organization_id`, `user_id` / resolved user ids, role codes, resolver type, classification, correlation id, flag state.  
Disallowed: contract content, document bytes, credentials, API tokens, unrestricted cross-tenant dumps.

### Binding Security advisory conditions

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

Proposed audit event names (avoid Slice 3 shadow-sync semantics):

| Event | When |
|---|---|
| `role.resolver.parity_checked` | Comparison completed (MATCH or non-critical drift) |
| `role.resolver.drift_detected` | Non-security drift classifications |
| `role.resolver.security_anomaly` | `CROSS_TENANT_ANOMALY` (and similarly severe) |
| `role.resolver.comparison_failed` | Canonical side threw / `RESOLUTION_ERROR` |

---

## Rollback plan

| Layer | Action |
|---|---|
| Runtime | Set `PROCESS_ROLE_RESOLVER_PARITY_ENABLED=false` (default). Immediate; no migration. |
| Code | Revert implementation PR if needed. Legacy resolvers unchanged by design. |
| Data | No authoritative data writes in this slice — nothing to roll back in `UserProfile` / membership / permissions. |
| Evidence | Retain audit/report artifacts for forensics; they are diagnostic only. |

**Kill switch:** environment / settings flag off. No schema dependency expected.

---

## Test matrix (implementation gate)

Full planned cases: [`RESOLVER_PARITY_TEST_MATRIX.md`](RESOLVER_PARITY_TEST_MATRIX.md).

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

## Merge authorization (PR #58) — authoritative

**PR:** [#58](https://github.com/Technivian/CLMOne/pull/58)  
**Reviewed HEAD (code):** `44926da923ff3b71bbfe8434794bd91f7cfe8d2e`  
**Pre-merge tip (docs-only):** `f7b56ab57b2842fba0d7a00bb0333f93f304ec39` — authorization text only; `config/` / `contracts/` / `tests/` identical to `44926da9`  
**Merge commit:** `598b7a128cb8d0f5be0c7cd2fb1880f631ca9608`  
**Merged at:** `2026-07-22T14:42:13Z`  
**CI at reviewed HEAD:** 6/6 SUCCESS  
**Process note:** Merge occurred **before** the Product/Engineering Approve merge votes below. Retrospective **Ratify \| Revert** is required — see [`../2026-07-22-par-id-001-pr58-merge/GOVERNANCE_INCIDENT_AND_RATIFICATION_ADDENDUM.md`](../2026-07-22-par-id-001-pr58-merge/GOVERNANCE_INCIDENT_AND_RATIFICATION_ADDENDUM.md).

| Approver | Vote | Timestamp |
|---|---|---|
| @haroonwahed Product | **Approve merge** | `2026-07-22T15:06:30Z` |
| @Technivian Engineering | **Approve merge** | `2026-07-22T15:06:45Z` |

### Verbatim Product merge authorization

Source: direct user-provided authorization text (placeholders filled with recording UTC timestamps).

```text
PR #58 MERGE AUTHORIZATION — 2026-07-22

PR: #58
Reviewed HEAD: 44926da9

@haroonwahed Product: Approve merge
Timestamp: 2026-07-22T15:06:30Z

Merge authorization confirms:

- Resolver-parity implementation authorization remains valid
- Security-advisory conditions remain binding
- PROCESS_ROLE_RESOLVER_PARITY_ENABLED remains default off after merge
- Legacy resolver output remains authoritative
- Canonical resolver output remains diagnostic only
- Comparison failures remain fail-open
- No staging flag activation is authorized
- No resolver cutover is authorized
- No privilege, permission, membership-authority, signer, approval, or navigation changes are authorized
- No automatic repair or authoritative data overwrite is authorized
- Dual-return and privilege cutover remain separately gated
```

### Verbatim Engineering merge authorization

```text
@Technivian Engineering: Approve merge
Timestamp: 2026-07-22T15:06:45Z
```

**Post-merge constraints (binding):**
- `PROCESS_ROLE_RESOLVER_PARITY_ENABLED` remains default **false** (do not enable)
- `PROCESS_ROLE_SHADOW_WRITE_ENABLED` / `PROCESS_ROLE_PARITY_REPORTING_ENABLED` remain default **false**
- No staging flag activation
- No dual-return / privilege / resolver cutover
- PAR-ID-001 remains **In progress**

### Superseded draft merge/staging note

The docs-only block previously recorded at `2026-07-22T14:34:37Z` that purported to authorize staging enablement of `PROCESS_ROLE_*` flags is **superseded and not in force**. Authoritative merge votes above explicitly state **no staging flag activation is authorized**.

---

## PR readiness verdict

| Gate | Verdict |
|---|---|
| Authorization votes | **Recorded** — Product `14:17:31Z` / Engineering `14:18:31Z` / Security `14:15:31Z` |
| Implementation present | **Yes** — merged to `main` @ `598b7a12` |
| Legacy authoritative | **Yes** — every path returns legacy result |
| Flag default | **off** (verified post-merge) |
| Dual-return / cutover | **Not authorized** |
| Staging flag activation | **Not authorized** (14:34:37Z staging claim superseded) |
| Merge authorization | **Recorded** — Product `15:06:30Z` / Engineering `15:06:45Z` |
| Ready to merge | **Merged** |

**Verdict:** Slice 4 comparison implementation is **merged**. Staging flag activation, dual-return, and privilege cutover remain **blocked**.

---

## Next cutover gate (after this slice, separate authorization)

Comparison slice merge does **not** authorize cutover or staging flag enablement. Next gates require separate Product + Engineering (+ Security where required) authorization and all of:

1. Separate staging activation authorization before enabling any `PROCESS_ROLE_*` flag.
2. Staging shadow + assignment critical drift = 0 for target orgs (when activation authorized).
3. Resolver comparison free of H-risk `DIFFERENT_USER` / `CROSS_TENANT_ANOMALY` on candidates (or accepted with explicit residual).
4. Ambiguous ADMIN cases explicitly classified and accepted.
5. Threat review + rollback plan accepted.
6. Separate dual-return / privilege-cutover authorization.
7. Legacy resolvers retained until cutover criteria met.

---

## Implementation gate

Comparison hooks behind `PROCESS_ROLE_RESOLVER_PARITY_ENABLED` (default false) are **merged**.  
Do **not** enable the flag without separate activation authorization.  
Do **not** return canonical results to callers or begin privilege/resolver cutover.
