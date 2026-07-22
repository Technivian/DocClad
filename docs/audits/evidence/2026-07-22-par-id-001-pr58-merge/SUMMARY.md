# PR #58 merge evidence — PAR-ID-001 resolver parity

**Date:** 2026-07-22  
**PR:** [#58](https://github.com/Technivian/CLMOne/pull/58) — feature-flagged resolver-parity comparison (non-authoritative)  
**Reviewed HEAD (code):** `44926da923ff3b71bbfe8434794bd91f7cfe8d2e`  
**Pre-merge tip:** `f7b56ab57b2842fba0d7a00bb0333f93f304ec39` (docs-only vs `44926da9`; `config/` / `contracts/` / `tests/` unchanged)  
**Merge commit:** `598b7a128cb8d0f5be0c7cd2fb1880f631ca9608`  
**Merged at:** `2026-07-22T14:42:13Z`  
**Updated `main` HEAD:** `598b7a12`  
**Governance:** [`GOVERNANCE_INCIDENT_AND_RATIFICATION_ADDENDUM.md`](GOVERNANCE_INCIDENT_AND_RATIFICATION_ADDENDUM.md) — **Ratified and Closed** (`15:31:55Z`)

---

## Governance discrepancy (recorded)

PR #58 **merged before** formal merge authorization votes:

| Event | Timestamp |
|---|---|
| Merge to `main` | `2026-07-22T14:42:13Z` |
| Product Approve merge (recorded) | `2026-07-22T15:06:30Z` |
| Engineering Approve merge (recorded) | `2026-07-22T15:06:45Z` |

Post-hoc merge votes are recorded. Retrospective **Ratify merge** is **recorded and closed** (Product `15:31:46Z` / Engineering `15:31:55Z`).  
Staging activation remains **not** authorized. Remediation planning may proceed (REM-01..REM-06).

---

## Merge votes (recorded after merge; timestamps unchanged)

| Approver | Vote | Timestamp |
|---|---|---|
| @haroonwahed Product | Approve merge | `2026-07-22T15:06:30Z` |
| @Technivian Engineering | Approve merge | `2026-07-22T15:06:45Z` |

Full verbatim text: `docs/audits/evidence/2026-07-22-par-id-001/RESOLVER_PARITY_IMPLEMENTATION_AUTHORIZATION.md`  
Prior draft note at `14:34:37Z` purporting to authorize staging flag enablement is **superseded** (not in force).

---

## CI confirmation (reviewed HEAD `44926da9` and pre-merge tip)

| Check | Result |
|---|---|
| Forbidden-brand scan | SUCCESS |
| Anti-drift + contrast | SUCCESS |
| pr-release-evidence | SUCCESS |
| quality-and-tenancy | SUCCESS |
| security-scans | SUCCESS |
| verify-ui | SUCCESS |

---

## Post-merge local verification (`main` @ `598b7a12`)

| Check | Result |
|---|---|
| `PROCESS_ROLE_RESOLVER_PARITY_ENABLED` default | **false** |
| `PROCESS_ROLE_SHADOW_WRITE_ENABLED` default | **false** |
| `PROCESS_ROLE_PARITY_REPORTING_ENABLED` default | **false** |
| `tests.test_par_id_001_resolver_parity` | **18 PASS** |
| `tests.test_par_id_001_characterization` | **19 PASS** |
| Combined post-merge suite | **37 PASS** |
| `make check` | **PASS** |
| `scripts/check_governance_authority.sh` | **PASS** |

Evidence captures:
- `docs/audits/evidence/2026-07-22-par-id-001/django-tests-post-merge-resolver-parity.txt`
- `docs/audits/evidence/2026-07-22-par-id-001/django-check-post-merge.txt`
- `docs/audits/evidence/2026-07-22-par-id-001/governance-authority-post-merge.txt`

---

## Programme impact

- Slice 4 non-authoritative resolver comparison is on `main` behind default-off flag
- Legacy resolvers remain authoritative
- PAR-ID-001 remains **In progress** — resolver parity merged; remediation required before staging activation
- Staging flag activation **not** authorized
- Dual-return / privilege cutover **not** authorized
- Remediation planning: [`REMEDIATION_BACKLOG.md`](REMEDIATION_BACKLOG.md), [`REMEDIATION_PLANNING.md`](REMEDIATION_PLANNING.md)
