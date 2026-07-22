# PAR-EXC-001 — Governance review

**Date:** 2026-07-22  
**Programme:** PAR-EXC-001  
**ADR:** ADR-0015 **Proposed** (not Accepted)

## Charter / documentation compliance

| Check | Result |
|---|---|
| Read Governance Charter (active) | Yes — no Charter amendment in this slice |
| CANONICAL_DOMAIN_MODEL §2.33 | Aligns; §2.33 text not expanded pending ADR acceptance |
| ENGINEERING_GUARDRAILS | Service-owned logic; audit events; server-side authz; additive migration |
| No silent new domain objects outside ADR | New objects introduced under **Proposed** ADR-0015 only |
| No unauthorized cutover | Legacy paths unchanged |
| Explicit non-starts honored | PAR-APR-002, PAR-WF-010, PAR-ID-002 not started |
| PAR-ID-001 | Treated Closed per programme instruction |

## Planning boundary

This slice delivers:

- discovery matrix;
- target model;
- additive schema + governed service;
- migration plan;
- tests;
- roadmap update (In progress);
- decision package for ADR-0015.

This slice does **not**:

- mark ADR-0015 Accepted;
- mark PAR-EXC-001 Completed;
- wire production exception paths;
- invent votes or approvals.

## Vote gate for ADR-0015

Required before any production path cutover:

| Role | Vote needed |
|---|---|
| Product governance | Approve / Approve with conditions / Reject |
| Engineering governance | Approve / Approve with conditions / Reject |
| Security & privacy | Required for Critical-control and break-glass clauses |

Do not fabricate votes.
