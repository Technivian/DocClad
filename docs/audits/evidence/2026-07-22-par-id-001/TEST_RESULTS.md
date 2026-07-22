# PAR-ID-001 — test results

**Date:** 2026-07-22  
**`main` HEAD:** `598b7a12` (PR #58 merged)  
**PR #55 merge:** `bb881ac2`  
**Resolver parity:** Authorized + **merged**; flag default off

## Post-merge gate (`main` @ `598b7a12`)

| Suite | Result |
|---|---|
| `tests.test_par_id_001_resolver_parity` | **18 PASS** |
| `tests.test_par_id_001_characterization` | **19 PASS** |
| Combined | **37 PASS** (`django-tests-post-merge-resolver-parity.txt`) |
| `make check` | **PASS** |
| `scripts/check_governance_authority.sh` | **PASS** |

## Flags (default off — verified post-merge)

- `PROCESS_ROLE_SHADOW_WRITE_ENABLED` = false
- `PROCESS_ROLE_PARITY_REPORTING_ENABLED` = false
- `PROCESS_ROLE_RESOLVER_PARITY_ENABLED` = false

Legacy resolvers remain authoritative. Staging activation / dual-return / privilege cutover **not** authorized.
