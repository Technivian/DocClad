# R1 test matrix and rollback plan

**Package:** [`R1_CERTAIN_REMEDIATION_AUTHORIZATION.md`](R1_CERTAIN_REMEDIATION_AUTHORIZATION.md)  
**Baseline:** `0404e284`

---

## Test matrix

| ID | Case | Expect |
|---|---|---|
| T1 | Dry-run on R0-equivalent corpus | Reports 12 planned creates; **zero** DB writes |
| T2 | Apply once | Creates exactly 12 CERTAIN active PRAs; provenance + run ID present |
| T3 | Apply twice (idempotent) | Second apply creates **0**; still 12 active |
| T4 | Skip AMBIGUOUS ADMIN | Apply never creates `legacy_process_admin` |
| T5 | Skip workspace membership roles | No PRA from OWNER/ADMIN/MEMBER alone |
| T6 | Tenant isolation | Actor/org mismatch cannot create in foreign org; no cross-org FK |
| T7 | Preserve existing | Pre-seeded active CERTAIN PRA for one row → skipped, not duplicated |
| T8 | Provenance | Each new row has source=`LEGACY_BACKFILL`, confidence=`CERTAIN`, legacy field/value, run ID |
| T9 | No privilege escalation | Permissions / membership roles unchanged; authz checks unchanged |
| T10 | Flags remain false | After apply, all `PROCESS_ROLE_*` settings still false |
| T11 | Parity before/after | Assignment critical CERTAIN gaps for 12 rows cleared; CROSS_TENANT=0; DIFFERENT_USER=0 |
| T12 | Rollback by run ID | Deactivates/removes only R1 rows for that run; other PRAs untouched |
| T13 | Rollback idempotent | Second rollback is no-op / safe |
| T14 | Re-apply after rollback | Can recreate the 12 rows with a **new** run ID |

Suggested module: `tests/test_par_id_001_r1_certain_remediation.py` (when implementation authorized).

---

## Rollback plan

1. Every apply generates `r1_remediation_run_id=<uuid>`.  
2. Rollback command: `--rollback --run-id <uuid>` (or service equivalent).  
3. Select only `ProcessRoleAssignment` rows created by that run (reason tag and/or dedicated field).  
4. Prefer **deactivate** (`is_active=False`, `effective_end=now`) with audit event — compensating removal allowed if Product prefers hard delete of LEGACY_BACKFILL R1 rows only.  
5. Must **not** touch AMBIGUOUS rows, MANUAL rows, or other run IDs.  
6. Emit rollback evidence JSON: counts deactivated, remaining active CERTAIN, flags still false.  
7. Automated T12–T14 must pass before merge of implementation PR.

---

## Evidence artifacts (post-apply; not this package)

| Artifact | Purpose |
|---|---|
| `R1_APPLY_EVIDENCE.md` | Run ID, dry-run vs apply counts, actor, timestamps |
| `R1_BEFORE_AFTER_INVENTORY.json` | Row inventory delta |
| `R1_PARITY_AFTER.json` | Assignment + resolver parity |
| `R1_ROLLBACK_EVIDENCE.md` | Rollback test / drill proof |
