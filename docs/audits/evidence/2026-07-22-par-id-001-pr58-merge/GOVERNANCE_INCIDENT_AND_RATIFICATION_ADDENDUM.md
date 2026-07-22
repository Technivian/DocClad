# Governance incident / ratification addendum — PR #58 pre-authorization merge

**Programme:** PAR-ID-001  
**PR:** [#58](https://github.com/Technivian/CLMOne/pull/58)  
**Merge commit:** `598b7a128cb8d0f5be0c7cd2fb1880f631ca9608`  
**Incident ID:** `GI-2026-07-22-PR58-PREAUTH-MERGE`  
**Opened:** 2026-07-22T15:19:31Z  
**Closed:** 2026-07-22T15:31:55Z  
**Status:** **Ratified and Closed**  
**Responsible owner:** Product governance (@haroonwahed) with Engineering co-owner (@Technivian)  
**PAR-ID-001 programme status:** **In progress** — resolver parity merged; remediation required before staging activation  

Related:
- [`SUMMARY.md`](SUMMARY.md)
- [`../2026-07-22-par-id-001/RESOLVER_PARITY_IMPLEMENTATION_AUTHORIZATION.md`](../2026-07-22-par-id-001/RESOLVER_PARITY_IMPLEMENTATION_AUTHORIZATION.md)
- [`REMEDIATION_BACKLOG.md`](REMEDIATION_BACKLOG.md) (prepared for after ratification; not a staging activation request)

---

## 1. Finding

PR #58 was **merged to `main` before** formal Product and Engineering **Approve merge** votes were recorded with the authoritative ISO-8601 UTC timestamps.

This is a **process/governance discrepancy**, not a runtime authority change. Implementation authorization for the comparison slice existed earlier; **merge authorization** was recorded after the merge commit.

---

## 2. Exact timeline (timestamps unchanged)

| Event | Timestamp (UTC) | SHA / note |
|---|---|---|
| Review package locked | `2026-07-22T14:09:08Z` | authorization package |
| Security advisory Approve with conditions | `2026-07-22T14:15:31Z` | implementation auth |
| Product Approve (implementation) | `2026-07-22T14:17:31Z` | implementation auth |
| Engineering Approve (implementation) | `2026-07-22T14:18:31Z` | implementation auth |
| Draft docs note claiming merge+staging auth | `2026-07-22T14:34:37Z` | later **superseded**; staging enablement **not** in force |
| Reviewed code HEAD (CI green) | — | `44926da9` |
| Docs-only tip before merge | — | `f7b56ab5` (`config/`/`contracts/`/`tests/` identical to `44926da9`) |
| **PR #58 merged to `main`** | **`2026-07-22T14:42:13Z`** | **`598b7a12`** |
| Product Approve merge (recorded) | `2026-07-22T15:06:30Z` | **after** merge |
| Engineering Approve merge (recorded) | `2026-07-22T15:06:45Z` | **after** merge |
| This addendum opened | `2026-07-22T15:19:31Z` | retrospective decision requested |
| Product Ratify merge | `2026-07-22T15:31:46Z` | closes process gap |
| Engineering Ratify merge | `2026-07-22T15:31:55Z` | incident **Ratified and Closed** |

**Gap:** ~24 minutes between merge (`14:42:13Z`) and Product merge vote (`15:06:30Z`); ~24.5 minutes to Engineering merge vote (`15:06:45Z`).  
**Retrospective ratification:** recorded at `15:31:46Z` / `15:31:55Z` (does not alter earlier timestamps).

---

## 3. Scope of merged code

Merged under PR #58 (non-authoritative Slice 4):

| Area | Change |
|---|---|
| Settings | `PROCESS_ROLE_RESOLVER_PARITY_ENABLED` default **false** |
| Service | `contracts/services/process_role_resolver_parity.py` — compare beside legacy; always return legacy; fail-open |
| Hooks | `WorkflowTemplateStep.resolve_assignee`; `workflow_routing.resolve_rule_assignee` |
| Report | `process_role_resolver_parity_report` management command |
| Tests / evidence | `tests/test_par_id_001_resolver_parity.py` + docs under `docs/audits/evidence/2026-07-22-par-id-001/` |

**Not in scope of the merge:** dual-return, privilege/permission/membership/navigation changes, automatic repair, staging flag enablement, resolver cutover.

---

## 4. Technical impact

| Dimension | Impact |
|---|---|
| Runtime resolver return values | **Unchanged** when flag is off (default) |
| Permissions / privileges | **None** |
| Membership authority | **None** |
| Navigation | **None** |
| Schema / migrations | **None** |
| Default flag state on `main` | All `PROCESS_ROLE_*` flags **false** (verified post-merge) |
| Canonical path | Diagnostic only; never returned to callers under authorized design |

---

## 5. Why runtime authority remained unchanged

1. `PROCESS_ROLE_RESOLVER_PARITY_ENABLED` defaults to **false** in `config/settings_base.py`.
2. Comparison runs only when the flag is on; otherwise resolvers return the pre-computed legacy result without side effects beyond a no-op path.
3. When the flag is on (not enabled on `main`), the wrapper still **always returns the legacy user** and fails open on comparison errors.
4. No code path in the merge alters `authorize_approval_actor`, workspace membership roles, or navigation gates.

---

## 6. Safeguards confirmed (post-merge)

| Safeguard | Status |
|---|---|
| Flag default off | **Confirmed** |
| Legacy output authoritative | **Confirmed** |
| Canonical diagnostic only | **Confirmed** |
| Fail-open comparison errors | **Confirmed** (design + tests) |
| CI green at reviewed HEAD | **Confirmed** (6/6) |
| Post-merge tests green | **Confirmed** (37 PASS resolver-parity + characterization) |
| `make check` / governance authority | **Confirmed** PASS |
| Staging flags not enabled | **Confirmed** |
| Dual-return / cutover not started | **Confirmed** |
| Draft staging-activation claim (`14:34:37Z`) | **Superseded / not in force** |

---

## 7. Recommendation (historical)

At open, recommendation was **Ratify merge** subject to Product + Engineering votes.  
**Outcome:** **Ratified and Closed** (`15:31:46Z` / `15:31:55Z`). Staging activation remains **not** authorized by this ratification.

---

## 8. Corrective action

| Action | Owner | Status |
|---|---|---|
| Open this incident/addendum with exact timeline | Engineering (docs) | **Done** (this file) |
| Request Ratify \| Revert votes (Product + Engineering) | Product / Engineering | **Requested** |
| Keep PAR-ID-001 **In progress** | Programme | **Confirmed** |
| Keep all `PROCESS_ROLE_*` flags default off | Engineering | **Confirmed** |
| Prepare remediation backlog (no staging request) | Engineering | **Done** ([`REMEDIATION_BACKLOG.md`](REMEDIATION_BACKLOG.md)) |
| If Revert: revert `598b7a12` under separate execution auth | Engineering | Contingent |
| If Ratify: close incident; proceed only to remediation (not staging) | Product / Engineering | Contingent |

---

## 9. Prevention measure

1. **Hard gate:** do not mark PRs ready / merge until Product + Engineering **Approve merge** votes with real ISO-8601 UTC timestamps are recorded in the authorization file **and** pasted on the PR.
2. Agents must not treat “implementation Authorized” as “merge Authorized.”
3. Docs-only commits that claim merge/staging authorization must not be used to unblock merge unless they contain named votes with real timestamps matching this programme’s vote protocol.
4. Prefer draft PRs until merge votes are recorded; empty CI re-triggers must not coincide with merge without the vote record.

---

## 10. Retrospective decision — recorded votes

### Product — @haroonwahed (accepted)

Source: direct user-provided ratification text  
Timestamp: `2026-07-22T15:31:46Z`

```text
PR #58 RETROSPECTIVE RATIFICATION — 2026-07-22

Incident:
GI-2026-07-22-PR58-PREAUTH-MERGE

PR:
#58

Merge SHA:
598b7a128cb8d0f5be0c7cd2fb1880f631ca9608

@haroonwahed Product: Ratify merge
Timestamp: 2026-07-22T15:31:46Z
```

### Engineering — @Technivian (accepted)

Source: direct user-provided ratification text  
Timestamp: `2026-07-22T15:31:55Z`

```text
@Technivian Engineering: Ratify merge
Timestamp: 2026-07-22T15:31:55Z
```

### Ratification confirms (binding)

- The merge occurred before formal merge authorization
- The original timestamps remain unchanged
- The governance discrepancy is accepted and documented
- All resolver-related feature flags remain default off
- Legacy resolver output remains authoritative
- Canonical resolver output remains diagnostic only
- No staging activation is authorized
- No resolver, privilege, permission, membership-authority, signer, approval, or navigation cutover is authorized
- No automatic repair is authorized
- PAR-ID-001 remains In progress
- Remediation items REM-01 through REM-06 remain required before any staging activation request

| Approver | Vote | Consent |
|---|---|---|
| @haroonwahed Product | **Ratify merge** | Recorded `2026-07-22T15:31:46Z` |
| @Technivian Engineering | **Ratify merge** | Recorded `2026-07-22T15:31:55Z` |

**Ratification status:** **Ratified and Closed**

---

## 11. Closure

**Closed — Ratified** at `2026-07-22T15:31:55Z`.

Authorized next steps (only):
- Merge documentation-only evidence PR #61 after CI + review
- Begin remediation backlog **analysis and planning only** (REM-01..REM-06)
- Do **not** enable flags
- Do **not** begin dual-return, canonical authority, privilege cutover, or automatic repair
- Do **not** request staging activation until remediation progress + separate activation authorization
