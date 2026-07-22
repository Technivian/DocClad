# PAR-ID-001 — Staging resolver-parity results

**Programme:** PAR-ID-001  
**Gate:** Resolver-parity staging (diagnostic only) + readiness remediation  
**Date:** 2026-07-22  
**PR #58 merge SHA:** `598b7a128cb8d0f5be0c7cd2fb1880f631ca9608` (merged 2026-07-22T14:42:13Z)  
**Evidence PR:** [#60](https://github.com/Technivian/CLMOne/pull/60)  
**Environment:** Staging-equivalent local SQLite (`config.settings_development`) with controlled-pilot seed data  
**Authority:** Legacy resolvers remain authoritative. Canonical results are **not** returned to callers.

---

## Staging activation

| Flag | Staging value | Production / default |
|---|---|---|
| `PROCESS_ROLE_SHADOW_WRITE_ENABLED` | `true` | `false` |
| `PROCESS_ROLE_PARITY_REPORTING_ENABLED` | `true` | `false` |
| `PROCESS_ROLE_RESOLVER_PARITY_ENABLED` | `true` | `false` |

**Canonical authority / dual-return:** **not enabled**  
**Activation method:** local `.env` only (gitignored)

**Staging period:** 2026-07-22 (initial gate + post-remediation rerun)  
**Organizations covered:** `controlled-pilot-org` (id=1), `controlled-pilot-org-b` (id=2)

---

## Commands run

```text
python manage.py process_role_resolver_parity_report --json --require-flag
python manage.py process_role_resolver_parity_report --organization-id=1 --json --require-flag
python manage.py process_role_resolver_parity_report --organization-id=2 --json --require-flag
```

---

## Parity counts — post-remediation (authoritative for this update)

Source: `process_role_resolver_parity_report --json --require-flag` after CERTAIN assignment remediation.

| Metric | Count | Bucket |
|---|---:|---|
| total_comparisons | 37 | — |
| MATCH | 24 | **In-scope** |
| AMBIGUOUS | 13 | **Accepted ADMIN exclusion** (not MATCH; not unresolved drift) |
| INACTIVE_ASSIGNMENT | 0 | In-scope |
| LEGACY_ONLY | 0 | In-scope |
| CANONICAL_ONLY | 0 | In-scope |
| DIFFERENT_USER | 0 | In-scope / critical |
| DIFFERENT_ROLE | 0 | In-scope |
| CROSS_TENANT_ANOMALY | 0 | Critical |
| RESOLUTION_ERROR | 0 | Critical |
| critical_drift_count | 0 | — |

`authoritative_for_runtime`: **false**

### Per organization (post-remediation)

| Organization | total | MATCH | AMBIGUOUS | INACTIVE | LEGACY_ONLY | critical |
|---|---:|---:|---:|---:|---:|---:|
| controlled-pilot-org (1) | 36 | 23 | 13 | 0 | 0 | 0 |
| controlled-pilot-org-b (2) | 1 | 1 | 0 | 0 | 0 | 0 |

### Pre-remediation (historical)

| Metric | Count |
|---|---:|
| total | 37 |
| MATCH | 9 |
| AMBIGUOUS | 13 |
| INACTIVE_ASSIGNMENT | 14 |
| LEGACY_ONLY | 1 |
| critical | 0 |

See [`INACTIVE_ASSIGNMENT_REMEDIATION.md`](INACTIVE_ASSIGNMENT_REMEDIATION.md).

---

## Separated result sets

### In-scope cutover results

Comparisons whose role labels map with **CERTAIN** confidence (e.g. ASSOCIATE → `legal_reviewer`, PARALEGAL → `paralegal_reviewer`, and both-unresolved empty paths):

- MATCH: **24**
- Unresolved INACTIVE / LEGACY_ONLY / CANONICAL_ONLY / DIFFERENT_*: **0**
- Critical: **0**

### Accepted ADMIN exclusions

- AMBIGUOUS: **13** (profile/step/rule `ADMIN` → `legacy_process_admin`)
- Explicitly **excluded** from first cutover authority
- Must **not** be reclassified as MATCH
- Legacy continues for these cases after any future CERTAIN-role authority flag

### Unresolved drift

**None** remaining after remediation for in-scope CERTAIN paths.

---

## Scenarios exercised (post-remediation)

| Scenario | Result |
|---|---|
| DPA / MSA / NDA / generic workflow | Exercised via template `resolve_assignee` |
| Approval initiation | `resolve_rule_assignee` across pilot contracts |
| Legal / finance / privacy resolution | Role-label paths exercised |
| Delegation / reassignment | Covered beside legacy |
| Unresolved assignee | Covered |
| Inactive assignment | Re-checked; classifications **0** |
| Ambiguous ADMIN | Covered; remains AMBIGUOUS (exclusion) |
| Multi-organization users | org-b MATCH after CERTAIN create |

No contract content or restricted identities in this evidence.

---

## LEGACY_ONLY remediation (`controlled-pilot-org-b`)

| Field | Value |
|---|---|
| Missing target | `legal_reviewer` for ASSOCIATE profile member |
| Mapping | CERTAIN |
| Membership | Active MEMBER in org-b verified |
| Action | `create_process_role_assignment` (not blind clone from primary org) |
| Assignment PK | 6 |
| Correlation ID | `31d229e7-c3e1-47ce-ac03-a419f8078b55` |
| Audit | `role.assignment.legacy_mapped` |
| Post-parity | org-b LEGACY_ONLY **0** / MATCH **1** |

---

## Diagnostic leakage check

Parity audit keys: `organization_id`, `resolver_type`, `classification`, `correlation_id`, `legacy_result_present`, `canonical_result_present`, `criticality`, `timestamp`, `authoritative_for_runtime`.

**No** credentials, contract content, or unrestricted identity dumps.

---

## Rollback test

| Check | Result |
|---|---|
| Flag on → comparisons increment | PASS |
| Flag off → comparisons stay 0 | PASS |
| Legacy return unchanged | PASS |

---

## Readiness checklist

| Requirement | Status |
|---|---|
| CROSS_TENANT_ANOMALY = 0 | Met |
| DIFFERENT_USER = 0 | Met |
| RESOLUTION_ERROR = 0 | Met |
| unresolved INACTIVE_ASSIGNMENT = 0 | Met |
| unresolved LEGACY_ONLY = 0 | Met |
| unresolved CANONICAL_ONLY = 0 | Met |
| unexplained DIFFERENT_ROLE = 0 | Met |
| ADMIN cases explicitly excluded | Met (policy recorded; Product/Security votes on packages remain Requested) |
| Threat review complete | Met — [`RESOLVER_CUTOVER_THREAT_REVIEW.md`](RESOLVER_CUTOVER_THREAT_REVIEW.md) |
| Rollback by flag disable proven | Met |
| Controlled-pilot flows pass | Met (diagnostic) |

### Verdict

**READY FOR CUTOVER AUTHORIZATION**

This does **not** authorize or enable canonical authority.  
Next: [`CANONICAL_RESOLVER_CUTOVER_AUTHORIZATION.md`](CANONICAL_RESOLVER_CUTOVER_AUTHORIZATION.md) (votes Requested; flag `PROCESS_ROLE_CANONICAL_RESOLVER_ENABLED` default off — **not implemented in this slice**).

PAR-ID-001 remains **In progress**.
