# Baseline summary — platform documentation alignment

**Date:** 2026-07-21  
**Branch:** `cursor/feat-platform-documentation-alignment-d7f1`  
**Authority:** GOVERNANCE_CHARTER.md (active) + PDR-0003 Accepted supporting docs  

## Commands and results

| Command | Result | Duration | Notes |
|---|---|---|---|
| `DJANGO_SETTINGS_MODULE=config.settings_test manage.py check` | **PASS** (0 issues) | ~2s | See `django-check.txt` |
| Workflow suite: `test_workflow_template_versioning`, `test_workflow_simulation`, `test_workflow_audit_trail`, `test_workflow_execution`, `test_workflow_designer_canvas` | See `workflow-suite.txt` | — | Primary workflow invariants |
| Broader targeted: + `test_cross_tenant_isolation`, `test_contract_lifecycle_pdr0002` | **FAIL** (5 failures, 1 error of 122) | ~26s | See `targeted-suite.txt` |

## Failure classification (targeted suite)

| Failure | Classification |
|---|---|
| Cross-tenant list endpoints returning 302 instead of 200 / login redirect mismatches (`contract_list` → `/contracts/repository/`, `deadline_list` → `/contracts/obligations/`) | **Pre-existing / environment or route-alias drift** — not introduced by this programme (clean tree at start) |
| `test_workflow_template_activity_cross_org_returns_404` → 302 | **Pre-existing / auth redirect** |
| Other isolation assertion failures in same module | **Pre-existing** pending separate remediation |

## Environment

- Python venv: `.venv`
- Test DB: in-memory SQLite (`settings_test`)
- No secrets captured
- Setup install status: `/tmp/cursor/async-install/install-user.status` = 0

## Honesty note

Baseline is **not** falsely marked green. Pre-existing isolation/auth redirect failures are recorded separately from programme-introduced regressions.
