# PAR-ID-001 — INACTIVE_ASSIGNMENT remediation

**Programme:** PAR-ID-001  
**Authorization:** [`RESOLVER_READINESS_REMEDIATION_AUTHORIZATION.md`](RESOLVER_READINESS_REMEDIATION_AUTHORIZATION.md) (votes **Requested**)  
**Environment:** Staging-equivalent controlled-pilot SQLite  
**Timestamp:** 2026-07-22T15:14:28Z  
**Constraint:** CERTAIN mappings only; no ADMIN / AMBIGUOUS assignment create or activate for cutover remediation.

---

## Finding summary

Pre-remediation parity reported **14** `INACTIVE_ASSIGNMENT` classifications.  
They were driven by **one** inactive canonical row:

| Field | Value |
|---|---|
| Organization | `controlled-pilot-org` |
| Legacy process role label | `ASSOCIATE` (profile_role) |
| Expected canonical `RoleDefinition` | `legal_reviewer` |
| Mapping confidence | **CERTAIN** |
| Assignment PK | `4` |
| Before `is_active` | `false` |

Repeated classifications came from the management-command sweep (contracts × approval rules / steps) resolving the same ASSOCIATE → `legal_reviewer` path while the only matching canonical assignment was inactive.

No AMBIGUOUS roles were remediated.

---

## Before state

| Organization | Assignments total | Active | Inactive |
|---|---:|---:|---:|
| controlled-pilot-org | 5 | 4 | 1 (`legal_reviewer`) |
| controlled-pilot-org-b | 0 | 0 | 0 |

Inactive detail (no user identities):

| org | assignment_pk | role_code | profile_role | mapped_code | confidence |
|---|---:|---|---|---|---|
| controlled-pilot-org | 4 | legal_reviewer | ASSOCIATE | legal_reviewer | CERTAIN |

---

## Remediation

| Action | Org | Assignment PK | Role code | Confidence | Correlation ID | Audit event | Actor |
|---|---|---:|---|---|---|---|---|
| Reactivate via `repair_process_role_assignment` | controlled-pilot-org | 4 | legal_reviewer | CERTAIN | `03077e86-9b2f-49c4-9610-d69f0e895b09` | `role.assignment.repaired` | Org OWNER/ADMIN present |

Preserved / recorded:

- `assignment_source` unchanged (`SYSTEM`)
- `legacy_source_field` / `legacy_source_value` (`profile_role` / `ASSOCIATE`)
- `mapping_confidence` = `CERTAIN`
- Reason includes remediation tag + correlation ID
- Membership consistency re-validated on repair

**Not done:** automatic production repair; ADMIN assignment changes; resolver logic changes.

---

## After state

| Organization | Assignments total | Active | Inactive |
|---|---:|---:|---:|
| controlled-pilot-org | 5 | 5 | 0 |
| controlled-pilot-org-b | 1 | 1 | 0 (see LEGACY_ONLY remediation) |

Post-remediation parity (all orgs): `INACTIVE_ASSIGNMENT` = **0**.

---

## Evidence

- Action log: `/tmp/remediation-actions.json` (local run artifact; summary above)
- Audit: `role.assignment.repaired` for assignment `4` with change keys `is_active`, `membership_id`, `reason`
- Parity rerun: [`STAGING_RESOLVER_PARITY_RESULTS.md`](STAGING_RESOLVER_PARITY_RESULTS.md)
