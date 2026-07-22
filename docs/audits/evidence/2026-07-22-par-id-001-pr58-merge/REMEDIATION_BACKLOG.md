# PAR-ID-001 — post-Slice-4 remediation backlog (after PR #58 ratification)

**Status:** **Planning open** — GI-2026-07-22-PR58-PREAUTH-MERGE **Ratified and Closed** (`15:31:55Z`)  
**Opened:** 2026-07-22T15:19:31Z  
**Planning started:** 2026-07-22T15:32:33Z  
**Programme status:** **In progress** — resolver parity merged; remediation required before staging activation  
**Staging activation:** **Not requested** until REM-01..REM-06 progress and separate activation authorization

Related:
- [`GOVERNANCE_INCIDENT_AND_RATIFICATION_ADDENDUM.md`](GOVERNANCE_INCIDENT_AND_RATIFICATION_ADDENDUM.md) (**Ratified and Closed**)
- [`REMEDIATION_PLANNING.md`](REMEDIATION_PLANNING.md)

---

## Preconditions

Do **not** start this remediation as production cutover work.  
Do **not** enable `PROCESS_ROLE_RESOLVER_PARITY_ENABLED` / shadow / parity-reporting flags until separate staging activation authorization exists **after** remediation progress.

Remediation here is **diagnostic cleanup and policy acceptance**, not authority flip.  
**No automatic repair** without separate write authorization.

---

## Backlog items

| ID | Item | Count / scope | Owner capacity | Acceptance |
|---|---|---|---|---|
| REM-01 | Inactive or missing `ProcessRoleAssignment` rows relative to legacy profile roles | **14** inactive or missing assignments | Engineering | Triage list; no auto-repair; propose create/deactivate plan under separate write authorization if needed |
| REM-02 | Organization with persistent `LEGACY_ONLY` resolver/assignment posture | **1** organization | Engineering + Product | Org-scoped investigation; document residual or repair plan |
| REM-03 | Ambiguous ADMIN profile → `legacy_process_admin` mappings | **13** AMBIGUOUS ADMIN mappings | Engineering | Keep explicit `AMBIGUOUS`; never map to workspace ADMIN |
| REM-04 | Product acceptance of ADMIN mapping policy | Policy decision | Product | Accept retain-`legacy_process_admin` / AMBIGUOUS, or authorize alternate catalogue policy via PDR/ADR path |
| REM-05 | Security acceptance of ADMIN mapping policy | Advisory | Security | Threat/privacy review of AMBIGUOUS ADMIN handling; confirm no privilege conflation |
| REM-06 | Threat review completion for resolver-parity residual risk | Review package | Security + Engineering | Close threat items for comparison-only mode; confirm fail-open + tenant scoping |

---

## Remediation order (planning)

1. **REM-01** — Inventory inactive/missing assignments (org-scoped, permission-safe).  
2. **REM-02** — Characterize the LEGACY_ONLY organization.  
3. **REM-03** — Enumerate 13 AMBIGUOUS ADMIN mappings (ids/codes only; no privilege change).  
4. **REM-04** — Product ADMIN policy decision package (draft for vote; not auto-accepted).  
5. **REM-05** — Security advisory on ADMIN policy.  
6. **REM-06** — Threat review write-up for comparison-only residuals.  
7. **Only then** — separate staging activation authorization request (not opened here).

---

## Explicit non-goals

- Enabling any `PROCESS_ROLE_*` flag
- Dual-return / privilege cutover
- Automatic repair of assignments
- Marking PAR-ID-001 Completed
- Changing permissions, memberships, navigation, or legacy resolver return values
