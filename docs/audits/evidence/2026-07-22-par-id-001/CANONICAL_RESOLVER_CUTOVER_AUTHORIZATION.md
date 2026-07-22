# Implementation authorization — PAR-ID-001 canonical resolver cutover (proposed)

**Programme:** PAR-ID-001  
**ADR:** ADR-0014 **Accepted**  
**Prerequisite staging:** [`STAGING_RESOLVER_PARITY_RESULTS.md`](STAGING_RESOLVER_PARITY_RESULTS.md) post-remediation — **READY FOR CUTOVER AUTHORIZATION**  
**Threat review:** [`RESOLVER_CUTOVER_THREAT_REVIEW.md`](RESOLVER_CUTOVER_THREAT_REVIEW.md) — PASS for packaging  
**PR #58 merge:** `598b7a128cb8d0f5be0c7cd2fb1880f631ca9608`  
**Review package timestamp:** 2026-07-22T15:20:00Z  
**Status:** **Requested** — do not invent votes. **Do not implement or enable** the authority flag in this documentation slice.

---

## Motion — Authorize a separate default-off canonical resolver authority flag

**Text:** Authorize design and a future implementation of `PROCESS_ROLE_CANONICAL_RESOLVER_ENABLED` (default **off**) that, when explicitly enabled in an approved environment, may return canonical `ProcessRoleAssignment`-based resolution for **in-scope CERTAIN** process roles on the listed resolver paths only, with mandatory legacy fallback for excluded ADMIN / AMBIGUOUS cases and on canonical failure. This motion does **not** authorize privilege, permission, membership, navigation, or `UserProfile.role` removal changes. Staging diagnostic flags remain independent.

| Approver | GitHub identity | Governance capacity | Vote | Consent |
|---|---|---|---|---|
| Haroon Wahed | @haroonwahed | Product | **Requested** | — |
| Technivian | @Technivian | Engineering | **Requested** | — |
| Security & privacy (advisory) | @Technivian | Security advisory | **Requested** | — |

**Result:** **Not Authorized** until votes are recorded. Implementation must not begin solely on staging readiness.

---

## Proposed flag

| Setting | Default | Meaning when on |
|---|---|---|
| `PROCESS_ROLE_CANONICAL_RESOLVER_ENABLED` | **false** | Canonical resolution may influence return values for **in-scope** paths only |

Independent of:

- `PROCESS_ROLE_SHADOW_WRITE_ENABLED`
- `PROCESS_ROLE_PARITY_REPORTING_ENABLED`
- `PROCESS_ROLE_RESOLVER_PARITY_ENABLED`

---

## Exact resolver paths (in scope when authorized + flag on)

1. `WorkflowTemplateStep.resolve_assignee` and launch/materialize/simulation call chains that use it.
2. `workflow_routing.resolve_rule_assignee` and plan/initiate/API/workflow-create call chains that use it.

**Out of path scope:** membership authority, navigation, signer email transitions, explicit reviewer FKs, contract owner FK, finance threshold policy, `authorize_approval_actor` workspace checks.

---

## Excluded ADMIN cases (mandatory)

| Case | Behaviour when authority flag on |
|---|---|
| `profile_role` / step / rule label `ADMIN` | **Legacy resolution continues**; do not use canonical authority |
| Workspace `OWNER` / `ADMIN` / `MEMBER` | Never treated as process-role resolution targets |
| `legacy_process_admin` AMBIGUOUS mappings | Excluded from first cutover; later dedicated reconciliation required |

Do not reclassify AMBIGUOUS parity rows as MATCH.

---

## Fallback behaviour

1. Authority flag off → legacy only (current production behaviour).
2. Authority flag on + excluded ADMIN / AMBIGUOUS → legacy.
3. Authority flag on + canonical failure / empty unexpected → **fail open to legacy**; emit diagnostic/audit; do not hard-fail the business path unless a separate security policy requires fail-closed for cross-tenant anomalies.
4. `CROSS_TENANT_ANOMALY` → security escalation; do not repair automatically; stop rollout.

---

## Staged rollout order

1. Implement flag default off behind separate PR (after this package is Authorized).
2. Enable in staging-equivalent only; keep parity flag on; verify pilot flows.
3. Controlled-pilot org only.
4. Expand only after monitoring gate + recorded go/no-go.
5. Production enablement requires an additional activation vote (not this package alone).

---

## Monitoring

- Continue `process_role_resolver_parity_report` while dual-running.
- Alert on `CROSS_TENANT_ANOMALY`, `DIFFERENT_USER`, unexplained `RESOLUTION_ERROR`.
- Track AMBIGUOUS volume as excluded (not failure).
- Permission-safe audit events only.

---

## Rollback

1. Set `PROCESS_ROLE_CANONICAL_RESOLVER_ENABLED=false` → immediate legacy-only returns.
2. Leave shadow / parity diagnostic flags as previously configured.
3. No data migration required to roll back authority.
4. Prove rollback in staging before production enablement.

---

## Pilot verification

Required before production activation:

- DPA / MSA / NDA / generic workflow launch
- Approval initiation
- Legal / finance / privacy CERTAIN paths
- Delegation / reassignment
- Unresolved / inactive negative cases
- Ambiguous ADMIN still legacy
- Multi-organization users

---

## Staging evidence (precondition)

| Metric | Post-remediation |
|---|---:|
| MATCH (in-scope) | 24 |
| AMBIGUOUS (excluded) | 13 |
| INACTIVE / LEGACY_ONLY / CANONICAL_ONLY | 0 |
| Critical drift | 0 |

---

## Explicitly not authorized by this package

- Enabling the flag in any environment without recorded votes + activation gate
- Privilege / permission / membership changes
- Returning canonical results before implementation PR is Authorized and merged
- PAR-APR-002 / PAR-WF-010
- ADMIN cutover

---

## Vote templates (do not invent)

```text
@haroonwahed Product: Approve | Reject | Abstain
Timestamp: YYYY-MM-DDTHH:MM:SSZ
ADMIN exclusion acknowledged: yes|no
Flag default off: yes|no
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

## Stop condition

PAR-ID-001 remains **In progress**.  
**Do not implement or enable** `PROCESS_ROLE_CANONICAL_RESOLVER_ENABLED` in this task.
