# PAR-ID-001 — Focused threat review for resolver cutover readiness

**Programme:** PAR-ID-001  
**Date:** 2026-07-22  
**Scope:** Diagnostic parity + proposed future canonical authority (not enabled)  
**Status:** **Complete** for readiness gate (advisory). Does not authorize enabling `PROCESS_ROLE_CANONICAL_RESOLVER_ENABLED`.  
**Related:** [`RESOLVER_READINESS_REMEDIATION_AUTHORIZATION.md`](RESOLVER_READINESS_REMEDIATION_AUTHORIZATION.md)

---

## Threat model summary

| # | Threat | Control in current design | Residual risk | Cutover implication |
|---|---|---|---|---|
| T1 | Cross-tenant assignment injection | Org FK on `ProcessRoleAssignment` / `RoleDefinition`; membership consistency checks; parity `CROSS_TENANT_ANOMALY` when rule/template org ≠ contract org; fail-closed shadow sync without membership | Misconfigured manual assignment with wrong org still blocked by model FK; comparison flags anomaly | **Hard stop** if `CROSS_TENANT_ANOMALY` > 0 |
| T2 | Stale or inactive assignments | Active-only canonical candidate set; `INACTIVE_ASSIGNMENT` classification; governed repair for reactivation | Operators may forget reactivation after role change | Staging remediation required before cutover auth |
| T3 | Role escalation via label mapping | CERTAIN map only for known profile roles; ADMIN is AMBIGUOUS → `legacy_process_admin`; workspace roles never process targets | Incorrect future map edits could escalate | Mapping matrix + auth gate; no silent map changes |
| T4 | Workspace ADMIN becoming process ADMIN | Explicit non-mapping of membership ADMIN; profile ADMIN excluded from first cutover | Name collision remains a UX/confusion risk | First cutover **excludes** ADMIN; later dedicated reconciliation |
| T5 | Canonical resolver failure | Proposed cutover must fall back to legacy; comparison today fail-open | Bug in dual-return could raise | Authority flag default off; fail-open to legacy mandatory |
| T6 | Rollback failure | Diagnostic and proposed authority flags independent; disable restores legacy-only path | Mis-deployed settings in hosted staging | Rollback proven by flag disable in staging-equivalent |
| T7 | Audit-data leakage | Permission-safe parity evidence keys only; assignment audits use codes not contract content | Verbose logs elsewhere could leak | Keep report/audit contracts; no identity dumps in evidence docs |
| T8 | Conflicting active assignments | Unique active (org, user, role_def) enforced at create; DIFFERENT_USER / DIFFERENT_ROLE classifications | Multiple users on same role is allowed (set membership) — first-match legacy nondeterminism | Cutover must document selection rule parity |
| T9 | Delegation misuse | Delegation remains on legacy approval paths; parity does not alter authorize/delegate | Cutover must not expand delegate authority via process roles | Out of first cutover unless separately authorized |
| T10 | Multi-organization users | Assignments are org-scoped; companion org remediated with CERTAIN-only create | User with profile role in org A and membership in org B without assignment → LEGACY_ONLY | Companion coverage verified; do not blind-clone |

---

## Staging evidence linkage

| Signal | Pre-remediation | Post-remediation |
|---|---|---|
| CROSS_TENANT_ANOMALY | 0 | 0 |
| DIFFERENT_USER | 0 | 0 |
| RESOLUTION_ERROR | 0 | 0 |
| INACTIVE_ASSIGNMENT | 14 | 0 |
| LEGACY_ONLY | 1 | 0 |
| AMBIGUOUS (ADMIN) | 13 | 13 (accepted exclusion) |

---

## Verdict

**Threat review: PASS for cutover-authorization packaging**, provided:

1. First cutover excludes ADMIN / AMBIGUOUS paths (legacy continues).
2. Authority flag remains default off until separately voted.
3. Fallback to legacy on canonical failure is mandatory.
4. Any future `CROSS_TENANT_ANOMALY` blocks rollout.

**Does not authorize** enabling canonical authority or privilege changes.
