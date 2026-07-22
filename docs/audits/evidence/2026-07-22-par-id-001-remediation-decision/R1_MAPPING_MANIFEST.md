# R1 mapping manifest — CERTAIN non-ADMIN only

**Baseline:** `main` @ `0404e284`  
**Source of truth for codes:** [`../2026-07-22-par-id-001/PROCESS_ROLE_MAPPING_MATRIX.md`](../2026-07-22-par-id-001/PROCESS_ROLE_MAPPING_MATRIX.md) + `resolve_legacy_process_role_code('profile_role', …)`  
**Policy:** P1+P3; P2 rejected — ADMIN / AMBIGUOUS excluded from this manifest

---

## Included CERTAIN mappings (R1 may create)

| Rule ID | Legacy source | Legacy value | Canonical code | Confidence | R1 action |
|---|---|---|---|---|---|
| R1-MAP-01 | `profile_role` | `PARTNER` | `partner_reviewer` | CERTAIN | Create missing active PRA per org membership |
| R1-MAP-02 | `profile_role` | `SENIOR_ASSOCIATE` | `senior_reviewer` | CERTAIN | Create missing active PRA per org membership |
| R1-MAP-03 | `profile_role` | `ASSOCIATE` | `legal_reviewer` | CERTAIN | Create missing active PRA per org membership |
| R1-MAP-04 | `profile_role` | `PARALEGAL` | `paralegal_reviewer` | CERTAIN | Create missing active PRA per org membership |
| R1-MAP-05 | `profile_role` | `LEGAL_ASSISTANT` | `legal_assistant` | CERTAIN | Create if present in target env (none in R0 corpus) |
| R1-MAP-06 | `profile_role` | `CLIENT` | `external_participant` | CERTAIN | Create if present in target env (none in R0 corpus) |

**Determinism:** For each active `OrganizationMembership`, if profile role maps via an included rule, and no active PRA exists for `(org, user, canonical_code)`, create exactly one row. Re-apply is a no-op.

---

## Excluded mappings (hard deny in R1)

| Legacy source | Legacy value | Canonical code | Confidence | Why excluded |
|---|---|---|---|---|
| `profile_role` | `ADMIN` | `legacy_process_admin` | AMBIGUOUS | P1+P3; P2 rejected; no automatic process authority |
| `membership_role` | `OWNER` / `ADMIN` / `MEMBER` | workspace_* | N/A | Workspace roles are not process targets |
| `profile_role` | *(unknown)* | `legacy_unknown` | UNKNOWN | Not CERTAIN |

---

## Provenance fields required on each created row

| Field | Value |
|---|---|
| organization | Target workspace |
| user | Membership user |
| role_definition.code | Canonical code from rule |
| assignment_source | `LEGACY_BACKFILL` |
| mapping_confidence | `CERTAIN` |
| legacy_source_field | `profile_role` |
| legacy_source_value | Legacy enum (e.g. `PARTNER`) |
| mapping rule | Rule ID (e.g. `R1-MAP-01`) in reason/audit |
| assigned_by / actor | Documented actor |
| timestamp | `created_at` / apply time |
| remediation run ID | Shared UUID for the apply invocation |

---

## Expected R0 corpus effect (planning)

| Metric | R0 verified | Expected after R1 apply (same corpus) |
|---|---|---|
| CERTAIN missing | 12 | **0** |
| AMBIGUOUS ADMIN missing | 8 | **8** (unchanged) |
| MATCH_ACTIVE (CERTAIN) | 0 | **12** |
| LEGACY_ONLY comparisons | 89 | Reduced for CERTAIN-covered role labels; residual published in R1 exit evidence |
| AMBIGUOUS resolver comparisons | 5 | Unchanged or residual published |
| CROSS_TENANT / DIFFERENT_USER | 0 / 0 | Must remain 0 / 0 |
