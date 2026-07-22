# Activation authorization — PAR-ID-001 canonical resolver authority

**Programme:** PAR-ID-001  
**Prerequisite implementation authorization:** [`CANONICAL_RESOLVER_CUTOVER_AUTHORIZATION.md`](CANONICAL_RESOLVER_CUTOVER_AUTHORIZATION.md) — **Authorized** (implementation only)  
**Status:** **Requested** — activation votes must not be invented.  
**Implementation merge:** PR #62 → `main` @ `4c08fb9c` (2026-07-22T15:59:25Z). Post-merge authority + rollback tests **PASS**.  
**Do not enable** `PROCESS_ROLE_CANONICAL_RESOLVER_ENABLED` until this package is Authorized.

---

## Implementation reference (fill at PR merge / review)

| Field | Value |
|---|---|
| Implementation branch | `cursor/feat-par-id-001-canonical-resolver-authority-d7f1` |
| Implementation PR | [#62](https://github.com/Technivian/CLMOne/pull/62) |
| Implementation HEAD (pre-merge tip) | `7ed7b2d9` (final push before merge) |
| Merge SHA | `4c08fb9c98e934ece9b1ed00ae788055cccae6f0` (2026-07-22T15:59:25Z) |
| Flag default | `PROCESS_ROLE_CANONICAL_RESOLVER_ENABLED=false` |
| Org allowlist default | empty (no orgs) |

---

## Motion — Authorize activation in controlled-pilot staging only

**Text:** After implementation review, green tests, and rollback verification, authorize enabling `PROCESS_ROLE_CANONICAL_RESOLVER_ENABLED=true` **only** for organizations listed in `PROCESS_ROLE_CANONICAL_RESOLVER_ORG_ALLOWLIST` (initially `controlled-pilot-org` and optionally `controlled-pilot-org-b`), with diagnostic parity remaining available, legacy fallback retained, and ADMIN exclusions enforced. Production activation requires a further decision.

| Approver | GitHub identity | Capacity | Vote | Consent |
|---|---|---|---|---|
| Haroon Wahed | @haroonwahed | Product | **Requested** | — |
| Technivian | @Technivian | Engineering | **Requested** | — |
| Security advisory | @Technivian | Security | **Requested** | — |

---

## Eligible role scope (when activated)

- CERTAIN profile → process mappings only (e.g. ASSOCIATE → `legal_reviewer`, PARALEGAL → `paralegal_reviewer`, …)
- Active `ProcessRoleAssignment` in the contract organization
- Approved paths: `resolve_assignee`, `resolve_rule_assignee`

## ADMIN / workspace exclusions (unchanged)

- profile ADMIN → legacy only (`cutover_excluded`)
- workspace OWNER / ADMIN / MEMBER → never process targets
- AMBIGUOUS / LEGACY_UNKNOWN → legacy only

## Controlled-pilot organization scope (proposed)

| Org slug | Proposed allowlist |
|---|---|
| `controlled-pilot-org` | Yes |
| `controlled-pilot-org-b` | Optional companion |

## Monitoring plan

- Keep `PROCESS_ROLE_RESOLVER_PARITY_ENABLED` on in staging during pilot
- Alert on `role.resolver.cross_tenant_anomaly`, `role.resolver.canonical_failure`
- Track `canonical_used` vs `legacy_fallback` / `cutover_excluded` volumes
- Permission-safe evidence only

## Fallback policy

| Condition | Behaviour |
|---|---|
| Flag off / org not allowlisted | Legacy |
| Excluded role | Legacy + `cutover_excluded` |
| Missing / inactive assignment | Legacy + `legacy_fallback` |
| Canonical error | Legacy + `canonical_failure` |
| Cross-tenant | **Fail closed** (`None`) + security event; no cross-tenant fallback |

## Rollback command

```bash
# Immediate legacy-only restoration
PROCESS_ROLE_CANONICAL_RESOLVER_ENABLED=false
# Optionally clear allowlist
PROCESS_ROLE_CANONICAL_RESOLVER_ORG_ALLOWLIST=
```

## Stop conditions

- Any `CROSS_TENANT_ANOMALY` / unresolved critical drift
- Sensitive evidence leakage
- Unexpected permission / membership / navigation change
- Failure of flag-disable rollback

## Test results (implementation slice)

Recorded on implementation PR evidence / CI:

- Canonical authority unit suite
- Resolver parity suite
- Shadow sync, RoleDefinition, ProcessRoleAssignment, characterization
- Cross-tenant isolation
- Approval suites
- WF-010 characterization

## Vote templates (do not invent)

```text
@haroonwahed Product: Approve | Reject | Abstain
Timestamp: YYYY-MM-DDTHH:MM:SSZ
Activation environment: staging-controlled-pilot | production | other
Allowlist acknowledged: yes|no
```

```text
@Technivian Engineering: Approve | Reject | Abstain
Timestamp: YYYY-MM-DDTHH:MM:SSZ
```

```text
@Technivian Security advisory: Approve | Approve with conditions | Reject | Abstain
Timestamp: YYYY-MM-DDTHH:MM:SSZ
Conditions acknowledged: yes|no
```

---

## Stop

PAR-ID-001 remains **In progress**.  
**Do not enable** the authority flag under this Requested package.
