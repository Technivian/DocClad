# PAR-ID-001 evidence index

**Programme ID:** PAR-ID-001  
**Status:** **Closed** (2026-07-22) — controlled-pilot activation PASS + rollback PASS; residual **PAR-ID-002** (ADMIN)  
**ADR:** ADR-0014 **Accepted**  
**PR #62 merge:** `4c08fb9c98e934ece9b1ed00ae788055cccae6f0`  
**Baseline `main`:** `4c08fb9c`  
**Next roadmap item:** **PAR-EXC-001**

---

## Closure

| Artifact | Purpose |
|---|---|
| [`CLOSURE.md`](CLOSURE.md) | Closure record |
| [`CANONICAL_RESOLVER_ACTIVATION_AUTHORIZATION.md`](CANONICAL_RESOLVER_ACTIVATION_AUTHORIZATION.md) | Activation **Authorized** (`17:58–18:00Z`) |
| [`CANONICAL_RESOLVER_ACTIVATION_RESULTS.md`](CANONICAL_RESOLVER_ACTIVATION_RESULTS.md) | Pilot counts + rollback |
| [`PAR-ID-002-ADMIN-RECONCILIATION.md`](PAR-ID-002-ADMIN-RECONCILIATION.md) | Named ADMIN residual |

---

## Governance (selected)

| Artifact | Purpose |
|---|---|
| [`CANONICAL_RESOLVER_CUTOVER_AUTHORIZATION.md`](CANONICAL_RESOLVER_CUTOVER_AUTHORIZATION.md) | Implementation Authorized |
| [`RESOLVER_READINESS_REMEDIATION_AUTHORIZATION.md`](RESOLVER_READINESS_REMEDIATION_AUTHORIZATION.md) | Remediation Authorized |
| [`RESOLVER_PARITY_IMPLEMENTATION_AUTHORIZATION.md`](RESOLVER_PARITY_IMPLEMENTATION_AUTHORIZATION.md) | Slice 4 |
| [`../2026-07-22-par-id-001-pr58-merge/SUMMARY.md`](../2026-07-22-par-id-001-pr58-merge/SUMMARY.md) | PR #58 merge evidence |

---

## Scope after closure

- Canonical authority implemented (default off) + pilot activation proven
- Committed defaults remain off; pilot enablement via env under activation votes
- Legacy resolvers retained (removal separately governed)
- ADMIN cutover → **PAR-ID-002**
- Do not begin PAR-APR-002 / PAR-WF-010 from this closure
