# PAR-ID-001 — remediation planning notes (analysis only)

**Started:** 2026-07-22T15:32:33Z  
**Basis:** GI-2026-07-22-PR58-PREAUTH-MERGE **Ratified and Closed**  
**Mode:** Analysis and planning only — **no** flag enablement, **no** auto-repair, **no** cutover  
**Programme:** **In progress** — resolver parity merged; remediation required before staging activation

Related: [`REMEDIATION_BACKLOG.md`](REMEDIATION_BACKLOG.md)

---

## Order of work

| Step | ID | Planning activity | Deliverable (docs only until further auth) |
|---|---|---|---|
| 1 | REM-01 | Diff legacy `UserProfile.role` vs active `ProcessRoleAssignment` per org | Org-scoped inactive/missing table (14 expected); proposed repair classes (create / leave / escalate) — **no writes** |
| 2 | REM-02 | Isolate the LEGACY_ONLY org; compare shadow sync + resolver classifications | Org case note; residual vs fix recommendation |
| 3 | REM-03 | List AMBIGUOUS ADMIN mappings (`legacy_process_admin`) | 13-row inventory; confirm never mapped to workspace ADMIN |
| 4 | REM-04 | Draft Product ADMIN policy options | Decision brief: retain AMBIGUOUS vs PDR/ADR alternate |
| 5 | REM-05 | Security review of REM-04 options | Advisory conditions; privilege-conflation check |
| 6 | REM-06 | Threat review for comparison-only residuals | Threat close-out checklist (fail-open, tenant scope, evidence hygiene) |

---

## Methods (non-mutating)

- Prefer existing management commands with flags **off** where possible; offline org-scoped queries in evidence scripts.
- If diagnostic reporting requires a flag, that requires **separate staging activation authorization** — not granted by ratification.
- Evidence fields: organization id, user id, role codes, classification — no credentials, no contract content.

---

## Exit to staging activation request

Staging activation may be **requested** only after:

1. REM-01..03 inventories recorded  
2. REM-04 Product + REM-05 Security acceptance of ADMIN policy  
3. REM-06 threat review complete  
4. Separate Product + Engineering (+ Security as required) **staging activation** authorization with real ISO-8601 timestamps  

Until then: all `PROCESS_ROLE_*` flags remain default **false**.
