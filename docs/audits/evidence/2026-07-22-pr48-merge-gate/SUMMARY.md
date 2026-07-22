# PR #48 merge-gate evidence — 2026-07-22

## Commands and results

| Check | Result | Evidence |
|---|---|---|
| Django system checks | PASS (0 issues) | `django-check.txt` |
| Governance authority | PASS | `governance-authority.txt` |
| Doc link validation (audit/roadmap/ADR-0010) | PASS | `doc-link-validation.txt` |
| Targeted workflow + invariants + pilot scope + migration 0105 | PASS (68 tests) | `targeted-tests.txt` |
| Migration 0105 Django proof (forward/rollback/re-forward) | PASS (1 test) | `migration-0105-django-test.txt` |
| Full isolation suite | 74 PASS / 1 FAIL | `full-isolation-suite.txt` |
| Controlled-pilot Playwright | BLOCKED at e2e webServer seed (`WorkflowLaunchBlocked` DPA assignees) | `playwright-pilot-gate.txt`, `e2e-seed-demo.txt`, `known-preexisting-failures.md` |

## Playwright note

Playwright 1.59.1 installed for the gate attempt. `start_e2e_server.sh` fails during `seed_demo_command_center` because the seeded DPA template has required steps without assignees (`WorkflowLaunchBlocked`). This path is outside PR #48’s behavioural diff (designer launch policy / DPA seed not changed by this programme). Prior controlled-pilot Playwright evidence remains in `docs/audits/evidence/2026-07-20-pilot-verification/` (27 passed). Django `tests.test_controlled_pilot_scope` covered in this gate (PASS).

## Isolation residual

Only remaining failure vs baseline (which had 5 failures + 1 import error):

- `tests.test_cross_tenant_isolation.ContractIsolationTest.test_list_shows_only_own_org`
- Assertion `200`, actual `302` to repository (intentional `ContractListView` alias)
- Cross-org detail/update still 404 (PASS)
- Not a tenant data leak; not pilot-blocking
