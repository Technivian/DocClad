# PAR-ID-001 Slice 4 — Resolver parity test matrix

**Status:** **Implemented** under [`RESOLVER_PARITY_IMPLEMENTATION_AUTHORIZATION.md`](RESOLVER_PARITY_IMPLEMENTATION_AUTHORIZATION.md) (**Authorized**).  
**Flag:** `PROCESS_ROLE_RESOLVER_PARITY_ENABLED` (default false)  
**Hard rule:** Canonical comparison must never change the value returned to production callers.  
**Suite:** `tests.test_par_id_001_resolver_parity`

---

## Behavioural invariants

| # | Assertion | Coverage |
|---|---|---|
| I1 | Flag off → legacy resolvers behave identically (no extra failures; return unchanged) | `test_flag_off_leaves_behavior_unchanged`, `test_flag_defaults_false_in_settings` |
| I2 | Flag on → returned actor/role is **identity-equal** to legacy-only run | All classification tests assert legacy return |
| I3 | Canonical exception → legacy result still returned; `RESOLUTION_ERROR` recorded | `test_resolution_error_returns_legacy` |
| I4 | Drift never writes `UserProfile`, `OrganizationMembership`, or auto-repairs PRA | `test_no_automatic_repair` |
| I5 | Cross-tenant anomaly never “fixes” by adopting canonical user | `test_cross_tenant_anomaly_returns_legacy_and_escalates` |
| I6 | No contract content / credentials in report or audit payload | `test_evidence_hygiene` |

---

## Classification cases

| Classification | Test |
|---|---|
| MATCH | `test_match_returns_legacy` |
| LEGACY_ONLY | `test_legacy_only_returns_legacy` |
| CANONICAL_ONLY | `test_canonical_only_returns_legacy_none` |
| DIFFERENT_USER | `test_different_user_returns_legacy` |
| DIFFERENT_ROLE | `test_different_role_returns_legacy` |
| AMBIGUOUS | `test_ambiguous_admin_returns_legacy` |
| INACTIVE_ASSIGNMENT | `test_inactive_assignment_returns_legacy` |
| CROSS_TENANT_ANOMALY | `test_cross_tenant_anomaly_returns_legacy_and_escalates` |
| RESOLUTION_ERROR | `test_resolution_error_returns_legacy` |

---

## Resolver coverage

| Area | Tests |
|---|---|
| A1 `resolve_assignee` | specific_assignee short-circuit; role match; None; flag on/off |
| A2 `resolve_rule_assignee` | specific_approver short-circuit; role match; None; flag on/off |
| Delegation fields | `test_delegation_does_not_change_resolver_result` (gates unchanged) |
| Report command | `test_json_reporting_and_critical_drift_counts` |
| Audit | permission-safe `role.resolver.parity_compared` / `cross_tenant_anomaly` / `parity_resolution_error` |

---

## Regression suites (must remain green)

| Suite | Why |
|---|---|
| `tests.test_par_id_001_shadow_sync` | Slice 3 unchanged |
| `tests.test_par_id_001_role_definition` | Catalogue |
| `tests.test_par_id_001_process_role_assignment` | Dual-read diagnostics |
| `tests.test_par_id_001_characterization` | Baseline behaviour |
| `tests.test_cross_tenant_isolation` | Tenant safety |
| Approval authorization / workflow / PAR-APR-001 | No authz outcome change |
| `tests.test_par_wf_010_characterization` | Workflow isolation |
| Governance authority script | Docs integrity |

---

## Explicit non-goals for tests

- Do not assert that canonical becomes preferred.
- Do not assert flagship drafting (B2) starts using `approver_role`.
- Do not enable the flag in default test settings.
