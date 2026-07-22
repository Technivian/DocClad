# Known pre-existing isolation / e2e failures (PR #48 merge gate)

## 1. ContractIsolationTest.test_list_shows_only_own_org

| Field | Value |
|---|---|
| Exact test | `tests.test_cross_tenant_isolation.ContractIsolationTest.test_list_shows_only_own_org` |
| Pre-existing evidence | Baseline `docs/audits/evidence/2026-07-21-platform-alignment-baseline/targeted-suite.txt` — same `AssertionError: 302 != 200` |
| Current evidence | `full-isolation-suite.txt` / `isolation-contract-list-failure.txt` |
| Cause | `ContractListView.dispatch` intentionally redirects authenticated users to `contracts:repository` (legacy alias). Test still expects HTTP 200 + list context. |
| Pilot impact | None. Canonical Contracts surface is Repository; cross-org detail/update remain 404 (PASS). Controlled pilot uses repository / governed builders, not the legacy list renderer. |
| Owner | Engineering (isolation suite hygiene) |
| Tracking | G-SEC-01 / PAR-SEC-001 follow-up (stale assertion; not a tenant leak) |
| Why not blocking PR #48 | Not a data-isolation defect; product behaviour intentional; PR #48 fixed the related anonymous alias bypass (baseline had 5 isolation failures; now 1 residual). |

## 2. Baseline failures fixed by this PR (for contrast)

| Exact test | Baseline | Now |
|---|---|---|
| `DeadlineIsolationTest.test_list_excludes_other_org` | FAIL 302!=200 | PASS (auth then alias) |
| `UnauthenticatedAccessTest` × contract_list / deadline_list | FAIL login not in redirect | PASS |
| `WorkflowIsolationTest.test_workflow_template_activity_cross_org_returns_404` | FAIL 302!=404 | PASS |

## 3. Playwright e2e server bootstrap

| Field | Value |
|---|---|
| Exact failure | `seed_demo_command_center` → `WorkflowLaunchBlocked` on DPA template (required steps have no assignee) |
| Evidence | `playwright-pilot-gate.txt`, `e2e-seed-demo.txt` |
| Pre-existing vs PR | `workflow_designer.assert_template_safe_to_launch` / DPA seed not modified in PR #48 behaviour commits; DPA seed rows retain `is_active=True` after 0105 |
| Pilot impact | E2E demo seed path only. Controlled-pilot Django scope tests PASS. NDA/MSA/DPA RunPython seeds set `is_active=True` explicitly. |
| Owner | Engineering (e2e fixtures) |
| Tracking | Separate from PAR-WF-*; not a gap-audit Critical/High |
| Why not blocking PR #48 | Outside PR behavioural diff; prior pilot Playwright evidence `docs/audits/evidence/2026-07-20-pilot-verification/` (27 passed). Gate substitutes Django `test_controlled_pilot_scope` + migration/seed inspection. |
