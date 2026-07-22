# PAR-ID-001 — Canonical resolver authority cutover authorization (R5)

**Programme:** PAR-ID-001  
**ADR:** ADR-0014 **Accepted**  
**Policy binding:** P1 labels + P3 authority; **P2 rejected**  
**Prerequisite:** R4 staging diagnostic **Completed, PASS** — [`../2026-07-22-par-id-001-r4-staging/R4_EXIT_REPORT.md`](../2026-07-22-par-id-001-r4-staging/R4_EXIT_REPORT.md)  
**R4 verification:** [`R4_EVIDENCE_VERIFICATION.md`](R4_EVIDENCE_VERIFICATION.md)  
**Authority transition:** [`AUTHORITY_TRANSITION.md`](AUTHORITY_TRANSITION.md)  
**Evidence manifest:** [`EVIDENCE_MANIFEST.md`](EVIDENCE_MANIFEST.md)  
**Execution readiness:** [`R5_EXECUTION_READINESS.md`](R5_EXECUTION_READINESS.md)  

**Status:** **Authorized** (Motions 1–4 carried)  
**R5 programme gate:** **Authorized** — votes carried; **cutover not executed**; flags not enabled; committed defaults remain false  

**Do not use** `CANONICAL_RESOLVER_ACTIVATION_AUTHORIZATION.md` for this residual gate.  
**This document is the sole R5 vehicle.**

**PROHIBITION:** Do **not** enable `PROCESS_ROLE_CANONICAL_RESOLVER_ENABLED`, change runtime authority, or execute cutover until a separate operational execution step is performed under this carried authorization in `par-id-001-r5-staging-equivalent` only, with abort/rollback binding. This vote record **authorizes** but does **not** itself perform enablement.

---

## Decision outcome

| Field | Value |
|---|---|
| Decision | **Authorized** — Motions 1–4 carried |
| Carried at | `2026-07-22T20:38:18Z` |
| Result | All required Product / Engineering / Security votes recorded; Security conditions 1–10 acknowledged: **yes** |
| Package content baseline (unchanged) | `198ed13c93e56fdabb3d0e72246225284a619fc3` |
| Reviewed deployment HEAD at vote time | `058c5ed09cb79b9460cb875e80a9d5ad0cc9367d` (`main` tip; no `PROCESS_ROLE_*` / resolver-authority code drift vs package baseline) |
| Cutover executed by this vote? | **No** |
| Flags enabled by this vote? | **No** |

---

## Proposed environment (staging-equivalent only)

| Field | Proposed value |
|---|---|
| Named environment | `par-id-001-r5-staging-equivalent` |
| Class | Non-production **staging-equivalent** (local/controlled SQLite recreate of verified R0/R1/R4 corpus) |
| Path (proposed) | `docs/audits/evidence/2026-07-22-par-id-001-r5-canonical-authority-cutover/staging_env/` (DB gitignored; not committed) |
| Production | **OUT OF SCOPE** — not proposed; requires a separate later package if ever requested |
| Remote shared staging URL | **Not identified** in programme docs — not inferred |

---

## Proposed deployment / immutable artifact reference

| Field | Value |
|---|---|
| Implementation already on `main` (default off) | `contracts/services/process_role_resolver_authority.py` + settings flags (PR #62 lineage) |
| Baseline `main` at package prep | `2e7b5adc9f1d9e1aae4478888d0994f4edaf9e60` |
| Prep documentation branch | `cursor/par-id-001-r5-authority-cutover-prep` |
| **Reviewed deployment HEAD for execution** | `058c5ed09cb79b9460cb875e80a9d5ad0cc9367d` (recorded at vote time `2026-07-22T20:38:18Z`) |
| Material code drift vs reviewed HEAD | **Abort condition** |

Do not execute against an unnamed or drifting artifact.

---

## Proposed activation window

| Field | Value |
|---|---|
| Window start (UTC) | **PENDING** — set only after votes carried |
| Window end / observation end (UTC) | **PENDING** |
| Proposed observation period | Minimum **60 minutes** continuous monitoring after activation, or until abort/rollback |
| Operators on watch | **PENDING** identities (roles below) |

---

## Flag state machine (proposed)

Committed defaults must remain `false` in repository settings at all times.

| Phase | SHADOW | PARITY_REPORTING | RESOLVER_PARITY | CANONICAL | ORG_ALLOWLIST |
|---|---|---|---|---|---|
| Before activation | false | false | false | false | empty |
| During authorized cutover (proposed) | false | false | **true** (diagnostic observation; Motion 1 must accept) | **true** | `controlled-pilot-org` only |
| After successful observation (proposed) | false | false | false (unless separately re-authorized) | **false** until a follow-on sustainment vote | empty or as later voted |
| Immediate rollback | false | false | false | false | empty |

**Allowlist proposal (narrow):** `PROCESS_ROLE_CANONICAL_RESOLVER_ORG_ALLOWLIST=controlled-pilot-org`  
All other corpus orgs remain **out of scope** for this first R5 proposal.

---

## Authority transition (summary)

See [`AUTHORITY_TRANSITION.md`](AUTHORITY_TRANSITION.md).

| Before | After (if voted and activated in named env only) |
|---|---|
| Legacy resolver output is always returned to callers | For allowlisted org + CERTAIN eligible paths, canonical PRA user **may** be returned |
| Canonical output diagnostic-only | Canonical output authoritative **only** under flag+allowlist+eligibility |
| AMBIGUOUS ADMIN non-authoritative | **Unchanged** — excluded; legacy returned |
| Cross-tenant | Fail closed (`None`) under authority path |
| Canonical failure | Return **legacy** (fail-open for product path); audit `canonical_failure` |

---

## Legacy fallback behaviour (binding)

- Missing / inactive PRA → legacy  
- Excluded ADMIN / workspace / AMBIGUOUS → legacy + `cutover_excluded`  
- Canonical exception → legacy + `canonical_failure` (must not raise into caller)  
- Cross-tenant → `None` (fail closed); no foreign-tenant identity adoption  
- Flag off / org not allowlisted → legacy  

Legacy retirement is **out of scope**.

---

## Excluded scope (hard)

- Production activation  
- ADMIN authority / automatic ADMIN mapping (P2)  
- Privilege, permission, membership, signer, approval, or navigation changes  
- Automatic repair of assignments  
- Removal of legacy fallback / fail-open  
- Dual-return API redesign  
- PAR-ID-002, PAR-APR-002, PAR-WF-010  
- Expanding allowlist beyond Motion 1 without a new vote  

---

## Preconditions (must all be true before any enablement)

1. This authorization package carried (Motions 1–4) with real Product + Engineering + Security votes and UTC timestamps.  
2. Exact reviewed deployment HEAD recorded and deployed without material drift.  
3. Named environment `par-id-001-r5-staging-equivalent` prepared from authorized recreate procedure.  
4. All committed `PROCESS_ROLE_*` defaults remain `false`.  
5. Legacy authoritative at start (CANONICAL false).  
6. Assignment: CERTAIN missing = 0; AMBIGUOUS ADMIN remain explicit non-authoritative.  
7. Resolver diagnostics (pre-cutover, flag-off or parity-only as authorized): LEGACY_ONLY = 0; CANONICAL_ONLY = 0 unless explicitly explained and accepted in the vote; DIFFERENT_USER = 0; CROSS_TENANT_ANOMALY = 0; RESOLUTION_ERROR = 0; INACTIVE unexpected = 0.  
8. No unauthorized privilege/permission differences attributable to this programme.  
9. Required PAR-ID-001 tests green; `manage.py check` green.  
10. All 16 required scenarios available for execution.  
11. Rollback procedure dry-validated (flag-off) **before** CANONICAL enablement.  
12. Evidence capture locations created (this directory + `pending/`).  
13. Monitoring owner and rollback operator identified (names recorded below).  

Any deviation **blocks** execution unless explicitly included in the carried vote text.

---

## Go criteria

- Preconditions 1–13 met  
- Motions 1–4 carried  
- Activation window open  
- Operators present  
- Evidence capture started  
- Abort channels open (Security stop instruction honored immediately)

---

## Immediate abort conditions (single-incident stop)

Rollback immediately on **any** of:

1. Cross-tenant assignment or data exposure  
2. Different-user resolution vs expected legacy/CERTAIN identity contract for the case  
3. Privilege or permission expansion  
4. ADMIN ambiguity becoming authoritative  
5. Automatic ADMIN mapping  
6. Resolver exception affecting the returned legacy-fail-open result (caller sees error instead of legacy)  
7. Fail-open failure  
8. Unexpected CERTAIN missing  
9. Unexpected LEGACY_ONLY or CANONICAL_ONLY drift (unless pre-accepted in vote)  
10. Resolution error classified as critical in authority/parity evidence  
11. Diagnostic or metadata leakage (credentials, contract content, unrestricted cross-tenant identity)  
12. Inability to produce required audit evidence  
13. Inability to restore legacy authority immediately  
14. Material difference between reviewed and deployed code  
15. Material required-scenario failure  
16. Security reviewer stop instruction  

Abort criteria do **not** depend solely on aggregate percentages.  
A single tenant-isolation, identity, authorization, or ADMIN-authority violation is a **stop**.

---

## Rollback procedure

### Who may execute

- Designated rollback operator (Engineering capacity) — identity **PENDING**  
- Security may order stop; Engineering executes  

### Steps (flag-based; non-destructive)

```bash
# In par-id-001-r5-staging-equivalent only
export PROCESS_ROLE_CANONICAL_RESOLVER_ENABLED=false
export PROCESS_ROLE_CANONICAL_RESOLVER_ORG_ALLOWLIST=
export PROCESS_ROLE_RESOLVER_PARITY_ENABLED=false
export PROCESS_ROLE_SHADOW_WRITE_ENABLED=false
export PROCESS_ROLE_PARITY_REPORTING_ENABLED=false
# Restart / reload process so settings re-read, if required by the runtime
```

Committed repository defaults must already be `false` (no code change required for rollback).

### Verify rollback success

1. Settings/env show CANONICAL false; allowlist empty  
2. Resolver returns match legacy-only behaviour (authority path inactive)  
3. Parity/authority reports show no canonical_used for new resolutions  
4. Capture `flag_state_after_rollback.*` and counts into evidence  

### Telemetry expected after rollback

- No new `role.resolver.canonical_used` for the window after flag-off  
- Legacy authoritative  
- Diagnostic flags off unless separately authorized  

### Persisted assignments during cutover

- Authority path does **not** create PRA rows  
- Any PRA created by unrelated processes remain; **no automatic repair / mass deactivate** as part of R5 rollback  
- Do not delete historical audit rows  

### Evidence retention

- Retain all pre/during/after artifacts under this evidence directory  
- Record failed cutover / abort in `pending/INCIDENT_OR_ABORT.md` (template)  

### R5 status after abort/rollback

- Return programme gate to **Blocked**  
- Do not re-enable without a **new** carried vote set  

---

## Post-cutover observation period

| Item | Proposed |
|---|---|
| Duration | ≥ 60 minutes or until abort |
| Monitoring owner | **PENDING** |
| Watch | `canonical_used` / `legacy_fallback` / `cutover_excluded` / `canonical_failure` / `cross_tenant_anomaly` volumes; scenario matrix; privilege unchanged |
| End state options | Sustain (requires follow-on vote) · Suspend (flag-off) · Abort (rollback + Blocked) |

---

## Evidence requirements

See [`EVIDENCE_MANIFEST.md`](EVIDENCE_MANIFEST.md). All result files remain **PENDING** until a future authorized execution.

---

## Responsible operators (roles; identities pending)

| Role | Capacity | Identity |
|---|---|---|
| Cutover operator | Engineering | **PENDING** |
| Rollback operator | Engineering | **PENDING** |
| Monitoring owner | Engineering | **PENDING** |
| Product reviewer | Product (@haroonwahed) | ballot below |
| Engineering reviewer | Engineering (@Technivian) | ballot below |
| Security reviewer | Security advisory (@Technivian) | ballot below |

---

## Motions (explicit)

### Motion 1 — Accept exact R5 cutover scope and environment

**Text:** Accept the R5 cutover scope limited to named environment `par-id-001-r5-staging-equivalent`, org allowlist `controlled-pilot-org` only, CERTAIN non-ADMIN roles on the two approved resolver paths, with production out of scope, and accept the flag state machine and observation plan in this document.

| Approver | Vote | Timestamp (UTC) | Conditions acknowledged |
|---|---|---|---|
| @haroonwahed Product | **Approve** | `2026-07-22T20:38:16Z` | yes |
| @Technivian Engineering | **Approve** | `2026-07-22T20:38:17Z` | yes |
| @Technivian Security advisory | **Approve with conditions** | `2026-07-22T20:38:18Z` | yes |

**Motion 1 result:** **Carried**

### Motion 2 — Authorize canonical resolver authority in that exact environment

**Text:** Authorize setting `PROCESS_ROLE_CANONICAL_RESOLVER_ENABLED=true` with `PROCESS_ROLE_CANONICAL_RESOLVER_ORG_ALLOWLIST=controlled-pilot-org` **only** in `par-id-001-r5-staging-equivalent`, for the exact reviewed deployment HEAD recorded at vote time, such that eligible CERTAIN resolutions may return canonical PRA users; AMBIGUOUS ADMIN remains excluded and non-authoritative; committed defaults remain false.

| Approver | Vote | Timestamp (UTC) | Conditions acknowledged |
|---|---|---|---|
| @haroonwahed Product | **Approve** | `2026-07-22T20:38:16Z` | yes |
| @Technivian Engineering | **Approve** | `2026-07-22T20:38:17Z` | yes |
| @Technivian Security advisory | **Approve with conditions** | `2026-07-22T20:38:18Z` | yes |

**Motion 2 result:** **Carried**  
**Reviewed deployment HEAD bound by this motion:** `058c5ed09cb79b9460cb875e80a9d5ad0cc9367d`

### Motion 3 — Authorize defined rollback on abort

**Text:** Authorize the designated rollback operator to execute the flag-based rollback procedure in this document immediately upon any abort condition, restoring legacy authority, without requiring a second vote during an active incident.

| Approver | Vote | Timestamp (UTC) | Conditions acknowledged |
|---|---|---|---|
| @haroonwahed Product | **Approve** | `2026-07-22T20:38:16Z` | yes |
| @Technivian Engineering | **Approve** | `2026-07-22T20:38:17Z` | yes |
| @Technivian Security advisory | **Approve with conditions** | `2026-07-22T20:38:18Z` | yes |

**Motion 3 result:** **Carried**

### Motion 4 — Confirm hard exclusions remain out of scope

**Text:** Confirm that ADMIN authority, automatic repair, permission/privilege/membership/navigation/signer/approval changes, production activation, and legacy retirement remain **out of scope** for this R5 package and are not authorized by Motions 1–3.

| Approver | Vote | Timestamp (UTC) | Conditions acknowledged |
|---|---|---|---|
| @haroonwahed Product | **Approve** | `2026-07-22T20:38:16Z` | yes |
| @Technivian Engineering | **Approve** | `2026-07-22T20:38:17Z` | yes |
| @Technivian Security advisory | **Approve with conditions** | `2026-07-22T20:38:18Z` | yes |

**Motion 4 result:** **Carried**

### Verbatim recorded votes (authoritative)

```text
@haroonwahed Product: Approve
Timestamp: 2026-07-22T20:38:16Z
Motions 1–4: Approve
Conditions acknowledged: yes

@Technivian Engineering: Approve
Timestamp: 2026-07-22T20:38:17Z
Motions 1–4: Approve
Conditions acknowledged: yes

@Technivian Security advisory: Approve with conditions
Timestamp: 2026-07-22T20:38:18Z
Motions 1–4: Approve with conditions
Conditions 1–10 acknowledged: yes
```

Timestamps obtained at recording via `date -u +"%Y-%m-%dT%H:%M:%SZ"`.

**Aggregate:** Motions 1–4 **all carried**. R5 **Authorized**. Cutover **not** executed by this record. Flags **not** enabled by this record.

---

## Security acknowledgement conditions (must be acknowledged with Security vote)

1. Activation limited to `par-id-001-r5-staging-equivalent` only.  
2. Committed `PROCESS_ROLE_*` defaults remain false.  
3. AMBIGUOUS ADMIN never becomes authoritative; P2 remains rejected.  
4. Cross-tenant anomalies fail closed; no repair.  
5. Canonical failure fails open to legacy for product callers (except cross-tenant fail-closed).  
6. Diagnostic evidence remains tenant-scoped and permission-safe.  
7. No privilege/permission expansion.  
8. No automatic repair.  
9. Production not authorized.  
10. Single isolation/identity/authz/ADMIN violation is an immediate stop.  

---

## Ballot recording rules

- Use `date -u +"%Y-%m-%dT%H:%M:%SZ"` at recording time.  
- Do **not** invent votes or timestamps.  
- Documentation-preparation PR merge ≠ R5 authorization.  
- Earlier low-risk bundled authorizations (R0/R1/R4 diagnostic) **do not** authorize R5.

---

## Relationship to prior packages

| Package | Role vs R5 |
|---|---|
| R4 diagnostic activation | Prerequisite PASS; does not authorize authority |
| Historical `CANONICAL_RESOLVER_CUTOVER_AUTHORIZATION.md` | Implementation-only auth (default-off) — already landed |
| Historical `CANONICAL_RESOLVER_ACTIVATION_AUTHORIZATION.md` | **Do not use** for this residual R5 gate |
| **This file** | Sole R5 activation authorization vehicle |
