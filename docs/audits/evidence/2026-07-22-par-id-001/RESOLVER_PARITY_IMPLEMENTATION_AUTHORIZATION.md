# Implementation authorization — PAR-ID-001 Slice 4 resolver parity (comparison only)

**Programme:** PAR-ID-001  
**ADR:** ADR-0014 **Accepted**  
**Prerequisite:** PR [#55](https://github.com/Technivian/CLMOne/pull/55) merged to `main` @ `bb881ac2` (feature-flagged shadow sync); merge evidence PR [#59](https://github.com/Technivian/CLMOne/pull/59) → `0d9712ca`  
**Baseline `main` HEAD:** `0d9712ca`  
**Draft PR:** [#58](https://github.com/Technivian/CLMOne/pull/58) — `cursor/feat-par-id-001-resolver-parity`  
**Review package timestamp:** 2026-07-22T14:09:08Z  
**Authorization complete timestamp:** 2026-07-22T14:06:28Z  
**Status:** **Authorized** — Product, Engineering, and Security-advisory votes recorded verbatim; dual-return / privilege cutover / staging activation / merge still require programme gates as noted below

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
| Haroon Wahed | @haroonwahed | Product governance | CODEOWNERS `/docs/`; Charter v2.0 | **Approve** | Recorded 2026-07-22T14:05:28Z (verbatim below) |
| Technivian | @Technivian | Engineering governance | CODEOWNERS `/contracts/`; PDR-0003 | **Approve** | Recorded 2026-07-22T14:04:28Z (verbatim below) |
| Security & privacy (advisory) | @Technivian | Security review capacity | SECURITY_PRIVACY_ACCESS_AND_AUDIT; Charter §7 | **Approve with conditions** | Recorded 2026-07-22T14:06:28Z (verbatim below) |

**Result:** **Authorized** for diagnostic-only resolver parity implementation. Does **not** by itself authorize dual-return, privilege cutover, staging flag activation, or merge without green CI + programme merge step.

---

## Verbatim recorded votes

### Product — @haroonwahed

```text
APPROVE — PAR-ID-001 Resolver Parity Slice

Approver: @haroonwahed
Capacity: Product governance
Vote: Approve
Timestamp: 2026-07-22T14:05:28Z

I approve the diagnostic-only resolver parity scope documented in
RESOLVER_PARITY_IMPLEMENTATION_AUTHORIZATION.md.

This approval authorizes parallel comparison of legacy and canonical resolution
for the named assignee resolvers behind a default-off feature flag.

The legacy result must remain authoritative in every outcome.

This approval does not authorize dual-return, resolver cutover, privilege
changes, membership changes, navigation changes, automatic repair, or removal
of legacy role resolution.
```

### Engineering — @Technivian

```text
APPROVE — PAR-ID-001 Resolver Parity Slice

Approver: @Technivian
Capacity: Engineering governance
Vote: Approve
Timestamp: 2026-07-22T14:04:28Z

Engineering approves implementation of the narrowly scoped resolver parity
slice.

Conditions:

- PROCESS_ROLE_RESOLVER_PARITY_ENABLED defaults off
- legacy results are always returned
- canonical errors fail safely
- no automatic repair or overwrite
- no authorization, routing, permission, or privilege behavior changes
- tests must prove legacy authority for every drift classification
- rollback is disabling the feature flag
```

### Security advisory — @Technivian

```text
APPROVE WITH CONDITIONS — PAR-ID-001 Resolver Parity Slice

Approver: @Technivian
Capacity: Security advisory
Vote: Approve with conditions
Timestamp: 2026-07-22T14:06:28Z

Security approves diagnostic-only resolver comparison subject to these binding
conditions:

- canonical output must never influence a production decision
- no cross-tenant identity or role leakage
- CROSS_TENANT_ANOMALY triggers security escalation
- diagnostic evidence must be tenant-scoped and permission-safe
- workspace roles must never become process-role targets
- ADMIN remains explicitly ambiguous
- canonical failures produce RESOLUTION_ERROR while returning the legacy result
- no automatic correction
- the feature flag defaults off
- dual-return or privilege cutover requires separate authorization
```

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

## PR readiness verdict

| Gate | Verdict |
|---|---|
| Docs-only authorization package on PR #58 | **Acceptable / complete for voting** |
| Implementation present | **No** (correct) |
| Votes recorded | **No** — Product / Engineering / Security still **Requested** |
| Ready to implement comparison hooks | **No** |
| Ready to merge implementation | **No** |
| Staging flag activation | **Not requested** |
| Ready to merge this docs PR | **Yes after human review** (docs-only; separate from implementation authorization) |

**Verdict:** Authorization package is **ready for Product / Engineering / Security votes**.  
**NOT READY TO IMPLEMENT** comparison hooks until this file shows **Authorized** with three real ISO-8601 UTC vote timestamps.  
Implementation merge and staging flag activation each require **separate** authorization after that.

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
