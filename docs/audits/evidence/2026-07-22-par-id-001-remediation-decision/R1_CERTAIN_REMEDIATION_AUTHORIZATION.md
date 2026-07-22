# PAR-ID-001 — R1 CERTAIN non-ADMIN remediation authorization

**Programme:** PAR-ID-001  
**Baseline `main`:** `0404e284`  
**Prerequisite:** R0 inventory **PASS** ([`R0_EXIT_REPORT.md`](R0_EXIT_REPORT.md))  
**Policy binding:** P1 labels + P3 authority; **P2 rejected**; Security package conditions 1–6 + R0 conditions 1–8 remain in force  
**Status:** **Requested** — do not invent votes; do not implement until Product / Engineering / Security Approve with real ISO-8601 UTC timestamps  
**Related:** [`R1_MAPPING_MANIFEST.md`](R1_MAPPING_MANIFEST.md), [`R1_ROW_SCOPE.md`](R1_ROW_SCOPE.md)

---

## Motion — Authorize R1 CERTAIN non-ADMIN remediation only

**Text:** Authorize an idempotent, dry-run/apply remediation that creates **missing** org-scoped `ProcessRoleAssignment` rows **only** where `resolve_legacy_process_role_code('profile_role', …)` returns confidence **CERTAIN** and the mapped code is **not** `legacy_process_admin`; records provenance including a shared remediation run ID; preserves existing valid assignments; produces before/after inventory and parity evidence; supports rollback by remediation run ID; and adds tenant-isolation / idempotency / provenance / rollback / no-privilege-escalation tests — **without** ADMIN/AMBIGUOUS remediation, permission or membership changes, automatic runtime repair, feature-flag enablement, canonical resolver authority, dual-return, staging activation, or R2–R5 implementation.

| Approver | Vote | Consent |
|---|---|---|
| @haroonwahed Product | **Requested** | Pending ISO-8601 UTC |
| @Technivian Engineering | **Requested** | Pending ISO-8601 UTC |
| @Technivian Security advisory | **Requested (with conditions)** | Pending ISO-8601 UTC + conditions acknowledged |

**R1 authorization status:** **Not authorized**

---

## Exact R1 row scope (from R0)

| Set | Count | In R1? |
|---|---|---|
| R0 `MISSING_CANONICAL_SETUP` total | 20 | Split |
| **CERTAIN non-ADMIN missing** | **12** | **Yes — exclusive scope** |
| AMBIGUOUS ADMIN missing (`legacy_process_admin`) | 8 | **No — denied** |
| INACTIVE_HISTORY | 0 | N/A |

Full row list: [`R1_ROW_SCOPE.md`](R1_ROW_SCOPE.md).  
Mapping rules: [`R1_MAPPING_MANIFEST.md`](R1_MAPPING_MANIFEST.md).

**Out of R1 (explicit):** any workspace ADMIN→process map; any AMBIGUOUS confidence; any `legacy_process_admin` create; LEGACY_ONLY path redesign beyond the effect of these 12 CERTAIN creates; R2–R5.

---

## Allowed (when votes recorded)

1. Produce a deterministic tenant-scoped mapping manifest (this package).  
2. Map only roles with explicit **CERTAIN** legacy→canonical equivalence (matrix below).  
3. Create missing `ProcessRoleAssignment` via idempotent management command and/or migration-safe application service wrapping `create_process_role_assignment` (or equivalent governed create).  
4. Support **`--dry-run`** and **`--apply`** modes.  
5. Record provenance: workspace (org), user, canonical role code, legacy source field/value, mapping rule id, actor, timestamp, **remediation run ID**.  
6. Preserve existing valid active assignments (skip / no-op if active CERTAIN row already present).  
7. Produce before/after row inventory and assignment + resolver parity reports (flags remain **false**; offline classifiers allowed as in R0).  
8. Provide rollback / compensating removal **by remediation run ID** (deactivate or delete only R1-created rows for that run).  
9. Add tests: tenant isolation, idempotency, provenance, rollback, no privilege escalation.

### Provenance / run-ID encoding (implementation constraint)

Preferred minimal approach (no privilege change):

- `assignment_source` = `LEGACY_BACKFILL`  
- `mapping_confidence` = `CERTAIN`  
- `legacy_source_field` / `legacy_source_value` = `profile_role` / legacy enum  
- `assigned_by` = actor (or system actor documented in evidence)  
- `assignment_reason` **must** include `r1_remediation_run_id=<uuid>`  
- Shared run UUID also written to audit `changes` and R1 evidence JSON  

Optional additive schema (allowed if Engineering chooses): `remediation_run_id` UUIDField on `ProcessRoleAssignment` — docs-only authorization includes this additive field if needed for clean rollback queries. **No** permission/membership fields may be added for authority.

---

## Denied

| Item | Authorized |
|---|---|
| Workspace ADMIN → process-role mapping | **No** |
| `legacy_process_admin` automatic authority / create for AMBIGUOUS | **No** |
| AMBIGUOUS remediation | **No** |
| Permission or membership changes | **No** |
| Automatic runtime repair hooks | **No** |
| Enable any `PROCESS_ROLE_*` flag | **No** |
| Canonical resolver authority / dual-return | **No** |
| Staging activation | **No** |
| R2–R5 implementation | **No** |

---

## Binding Security conditions (verbatim — must be acknowledged)

1. R1 may create assignments **only** for CERTAIN non-ADMIN mappings listed in the mapping manifest.  
2. Profile `ADMIN` / `legacy_process_admin` / AMBIGUOUS rows are **hard-excluded**; P2 remains rejected.  
3. Every write must be org-scoped; cross-tenant create/update is forbidden and must fail closed.  
4. R1 must not change `OrganizationMembership`, permissions, navigation, or authz outcomes.  
5. R1 must not enable `PROCESS_ROLE_*` flags or alter resolver return authority (legacy remains authoritative).  
6. No automatic runtime repair — apply only via explicit dry-run/apply command (or authorized one-shot service invocation).  
7. Rollback must be limited to rows tagged with the remediation run ID; must not deactivate unrelated assignments.  
8. Post-apply parity: `CROSS_TENANT_ANOMALY` must remain **0**; R1 must not introduce `DIFFERENT_USER` for remediated CERTAIN paths.  
9. Evidence must distinguish verified post-R1 counts from historical programme targets and from R0 baselines.  
10. Staging activation and canonical cutover remain separately gated.

---

## Exit criteria (R1)

| Criterion | Done when |
|---|---|
| CERTAIN non-ADMIN gaps | All **12** approved rows have active CERTAIN PRA (or documented skip if already present) |
| No ADMIN-derived assignments | Zero new `legacy_process_admin` / AMBIGUOUS creates from R1 |
| No cross-tenant writes | Tests + apply log show org_id match only |
| No new DIFFERENT_USER | Post-apply offline resolver parity: DIFFERENT_USER still **0** (or escalate) |
| CROSS_TENANT_ANOMALY | Remains **0** |
| Flags | All `PROCESS_ROLE_*` default **false** |
| Parity rerun | Assignment + resolver parity evidence committed |
| Remaining counts published | Verified remaining LEGACY_ONLY + AMBIGUOUS published (expected AMBIGUOUS ADMIN still **8**; LEGACY_ONLY expected to drop for CERTAIN-covered paths) |
| Rollback tested | Automated test deactivates/removes by run ID |

---

## Explicit vote blocks (paste verbatim; do not invent)

### Product — @haroonwahed

```text
PAR-ID-001 R1 CERTAIN NON-ADMIN REMEDIATION AUTHORIZATION — 2026-07-22
Baseline main: 0404e284
R0 exit: PASS

@haroonwahed Product: Approve | Reject
Timestamp: <actual ISO-8601 UTC>

Approved scope:
- 12 CERTAIN non-ADMIN missing ProcessRoleAssignment rows only
- Idempotent dry-run/apply remediation with provenance + run ID
- Before/after inventory + parity; rollback by run ID
- Tests: tenant isolation, idempotency, provenance, rollback, no privilege escalation

Denied:
- ADMIN / AMBIGUOUS / P2 mapping
- Flag enablement, canonical authority, dual-return, staging activation
- R2–R5 implementation
- Permission / membership changes

Confirms:
- P1+P3 binding; P2 rejected
- Legacy resolvers remain authoritative
- PAR-ID-001 remains In progress
```

### Engineering — @Technivian

```text
@Technivian Engineering: Approve | Reject
Timestamp: <actual ISO-8601 UTC>

Engineering confirms:
- Implementation limited to CERTAIN non-ADMIN creates
- Dry-run/apply + idempotent + run-ID rollback
- No PROCESS_ROLE_* flag defaults changed
- No resolver authority change
```

### Security advisory — @Technivian

```text
@Technivian Security advisory: Approve with conditions | Reject
Timestamp: <actual ISO-8601 UTC>

Binding Security conditions 1–10 acknowledged: yes | no
No ADMIN/AMBIGUOUS remediation: yes | no
No flag/cutover/dual-return: yes | no
Cross-tenant fail-closed required: yes | no
```

---

## PR readiness verdict (pre-authorization)

**NOT READY TO IMPLEMENT OR MERGE** until:

1. Product + Engineering + Security R1 Approve votes recorded with real ISO-8601 UTC timestamps, and  
2. Implementation PR opened against `main` @ `0404e284` (or later content-identical tip) with tests green, and  
3. Separate merge authorization if programme practice requires it after implementation review.

This authorization package itself is **docs-only** and may land on `main` as Requested evidence without authorizing apply.

---

## Next gate after R1 evidence

1. Record R1 votes → implement → apply in staging-equivalent → commit before/after evidence.  
2. Publish remaining LEGACY_ONLY / AMBIGUOUS counts.  
3. Open **R2** (LEGACY_ONLY residual / path coverage) only under separate authorization — **not** granted here.  
4. Canonical activation and ADMIN CERTAIN coverage remain later gates under P1+P3.
