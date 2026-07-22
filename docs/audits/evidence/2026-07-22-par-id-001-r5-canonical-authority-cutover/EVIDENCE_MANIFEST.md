# PAR-ID-001 R5 — evidence manifest

**Status:** Execution results captured  
**Evidence root:** `docs/audits/evidence/2026-07-22-par-id-001-r5-canonical-authority-cutover/`  
**Verdict:** Completed, PASS

| Artifact | Path / name | Status |
|---|---|---|
| Authorization record | `CANONICAL_RESOLVER_AUTHORITY_CUTOVER_AUTHORIZATION.md` | Present (votes + execution) |
| Exit report | `R5_EXIT_REPORT.md` | Present |
| Reviewed HEAD | `pending/reviewed_head.txt` | `058c5ed0…` |
| Deployed artifact | `pending/deployed_artifact.txt` | match |
| Environment identity | `pending/environment.txt` | Present |
| Operators | Authorization operator table | Engineering (@Technivian) |
| Flag state before/during/after | `pending/flag_state_*.txt` | Present |
| Activation timestamps | `pending/activation_timestamp.txt`, `activation_window_*.txt` | Present |
| Resolver / assignment parity | `pending/resolver_parity_during.json`, `assignment_parity_during.json` | Present |
| Scenarios | `pending/scenarios_executed.json` | Present |
| Authority probes | `pending/authority_path_probes.json` | Present |
| Tenant isolation | `pending/tenant_isolation.txt` | Present |
| Permissions | `pending/permission_unchanged.txt` | Present |
| Fail-open | `pending/fail_open_probe.json` | Present |
| Monitoring | `pending/monitoring.txt` | Present |
| Abort review | `pending/abort_condition_review.md` | Present |
| Rollback / flag-off | `pending/rollback_result.json` | Present (planned end) |
| Tests / check | `pending/django-*.txt` | Present |
| Security / final reviews | `pending/SECURITY_REVIEW.md`, `FINAL_REVIEW.md`, `FINAL_DECISION.md` | Present |
| Roadmap | `docs/roadmap/PLATFORM_ALIGNMENT_ROADMAP.md` | Updated with this PR |
