# Implementation authorization — PAR-ID-001 canonical resolver cutover

**Programme:** PAR-ID-001  
**ADR:** ADR-0014 **Accepted**  
**Prerequisite staging:** [`STAGING_RESOLVER_PARITY_RESULTS.md`](STAGING_RESOLVER_PARITY_RESULTS.md) — **READY FOR CUTOVER AUTHORIZATION**  
**Threat review:** [`RESOLVER_CUTOVER_THREAT_REVIEW.md`](RESOLVER_CUTOVER_THREAT_REVIEW.md) — PASS for packaging  
**PR #58 merge:** `598b7a128cb8d0f5be0c7cd2fb1880f631ca9608`  
**Review package timestamp:** 2026-07-22T15:20:00Z  
**Authorization complete timestamp:** 2026-07-22T15:29:09Z  
**Status:** **Authorized** for **implementation only** (default-off). Activation remains **not authorized**.

---

## Motion — Authorize a separate default-off canonical resolver authority flag

**Text:** Authorize implementation of `PROCESS_ROLE_CANONICAL_RESOLVER_ENABLED` (default **false**) that, when explicitly enabled in an approved environment **after a separate activation vote**, may return canonical `ProcessRoleAssignment`-based resolution for **in-scope CERTAIN** process roles on the listed resolver paths only, with mandatory legacy fallback for excluded ADMIN / AMBIGUOUS cases and on canonical failure, and fail-closed behaviour for cross-tenant anomalies. This motion does **not** authorize privilege, permission, membership, navigation, or `UserProfile.role` removal changes. Staging diagnostic flags remain independent.

| Approver | GitHub identity | Governance capacity | Authority basis | Vote | Consent |
|---|---|---|---|---|---|
| Haroon Wahed | @haroonwahed | Product | CODEOWNERS `/docs/`; Charter v2.0 | **Approve** | 2026-07-22T15:27:09Z |
| Technivian | @Technivian | Engineering | CODEOWNERS `/contracts/`; PDR-0003 | **Approve** | 2026-07-22T15:28:09Z |
| Security & privacy (advisory) | @Technivian | Security advisory | SECURITY_PRIVACY_ACCESS_AND_AUDIT | **Approve with conditions** | 2026-07-22T15:29:09Z |

### Implementation vs activation

| Decision | Status |
|---|---|
| **Implementation authorization** — land default-off flag + authority wiring | **Authorized** |
| **Activation authorization** — enable flag in staging/production | **Not authorized** — see [`CANONICAL_RESOLVER_ACTIVATION_AUTHORIZATION.md`](CANONICAL_RESOLVER_ACTIVATION_AUTHORIZATION.md) |

Verbatim votes are recorded in [`RESOLVER_READINESS_REMEDIATION_AUTHORIZATION.md`](RESOLVER_READINESS_REMEDIATION_AUTHORIZATION.md) (combined motion). Binding Security conditions from that record apply here.

---

## Flag

| Setting | Default | Meaning when on |
|---|---|---|
| `PROCESS_ROLE_CANONICAL_RESOLVER_ENABLED` | **false** | Canonical resolution may influence return values for **in-scope** paths / allowlisted orgs only |
| `PROCESS_ROLE_CANONICAL_RESOLVER_ORG_ALLOWLIST` | **empty** | Comma-separated org slugs; empty = no orgs (fail-safe) |

Independent of:

- `PROCESS_ROLE_SHADOW_WRITE_ENABLED`
- `PROCESS_ROLE_PARITY_REPORTING_ENABLED`
- `PROCESS_ROLE_RESOLVER_PARITY_ENABLED`

---

## Exact resolver paths

1. `WorkflowTemplateStep.resolve_assignee` (+ launch/materialize/simulation chains)
2. `workflow_routing.resolve_rule_assignee` (+ plan/initiate/API/workflow-create chains)

## Exclusions (mandatory)

- profile ADMIN / AMBIGUOUS / `legacy_process_admin`
- workspace OWNER / ADMIN / MEMBER
- inactive / missing assignments → legacy fallback
- cross-tenant → fail closed (no cross-tenant fallback)

## Explicitly not authorized

- Enabling the flag in any environment without activation votes
- Privilege / permission / membership changes
- PAR-APR-002 / PAR-WF-010
- ADMIN cutover
