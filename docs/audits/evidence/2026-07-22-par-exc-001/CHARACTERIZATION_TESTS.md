# PAR-EXC-001 — Characterization tests

## Purpose

Prove current scattered exception-like behavior and protect new canonical invariants without cutting over production paths.

## Module

`tests/test_par_exc_001_exception.py`

### Canonical invariant coverage

| Test | Invariant |
|---|---|
| `test_create_requires_owner_reason_and_expiry` | Owner + reason + expiry |
| `test_decision_immutable_and_activates` | Immutable history; activate on APPROVED |
| `test_owner_cannot_self_approve_without_designation` | Explicit authority / SoD |
| `test_critical_security_requires_security_approval` | Critical security needs Security approval |
| `test_expired_stops_applying` | Expired stops applying + privilege deny |
| `test_renewal_creates_new_request` | Renewal = new governed request |
| `test_cross_tenant_create_denied` | Tenant isolation |
| `test_unknown_privilege_rejected` | No silent unrelated privileges |
| `test_permanent_requires_explicit_decision_flag` | Temporary unless explicitly approved otherwise |

### Legacy characterization

| Test | Path | Assertion |
|---|---|---|
| `test_deadline_defer_has_no_canonical_exception` | EXC-DL-001 | +7 days still works; **no** ExceptionRequest created |
| `test_keep_exception_audits_without_exception_request` | EXC-POL-001 | drafting action module remains write path; ExceptionRequest count 0 |

## Known related tests (unchanged)

- `tests/test_msa_workflow.py::test_keep_exception_requires_reason_and_owner`
- `tests/test_phase2_core_loop.py` deadline defer/escalate
- `tests/test_production_config_gate.py` ALLOW_SQLITE warnings

## Run

```bash
make test-fast APP=tests.test_par_exc_001_exception
```
