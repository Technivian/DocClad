# PAR-APR-001 / ADR-0013 — test results

**Captured:** 2026-07-22 (UTC)  
**Branch:** `cursor/feat-platform-documentation-alignment-d7f1` @ `c9ae7305`  
**Settings:** `config.settings_test`  
**Command:**

```bash
.venv/bin/python manage.py test \
  tests.test_par_apr_001_approval \
  tests.test_approval_workflow \
  tests.test_approval_authorization \
  tests.test_workflow_routing.WorkflowRoutingTests.test_workflow_dashboard_and_detail_surface_routing_endpoints \
  tests.test_cross_tenant_isolation.ContractIsolationTest.test_list_shows_only_own_org \
  --settings=config.settings_test -v 2
```

---

## 1. PAR-APR targeted suites

| Module | Tests | Result |
|---|---:|---|
| `tests/test_par_apr_001_approval.py` | 10 | **PASS** |
| `tests/test_approval_workflow.py` | 15 | **PASS** |
| `tests/test_approval_authorization.py` | 8 | **PASS** |
| **Subtotal** | **33** | **PASS** |

Evidence archive: [`django-tests.txt`](django-tests.txt) (PAR-APR module run).

---

## 2. Known programme test issues (recorded at ADR-0013 acceptance)

### Issue A — Workflow routing (orthogonal to PAR-APR foundation)

| Field | Value |
|---|---|
| **Test** | `WorkflowRoutingTests.test_workflow_dashboard_and_detail_surface_routing_endpoints` |
| **Module** | `tests/test_workflow_routing.py` |
| **Failure** | `AssertionError: '/contracts/approval-rules/' unexpectedly found` |
| **Cause** | Workflow Designer workspace tabs now surface routing rules link; test expects absence |
| **PAR-APR relevance** | **None** — UI routing assertion predates / is independent of ApprovalRequirement split |
| **Disposition** | Track under workflow UX test hygiene; **not** a PAR-APR-001 foundation blocker |

### Issue B — Tenant isolation list alias (PAR-SEC-003)

| Field | Value |
|---|---|
| **Test** | `ContractIsolationTest.test_list_shows_only_own_org` |
| **Module** | `tests/test_cross_tenant_isolation.py` |
| **Failure** | `AssertionError: 302 != 200` |
| **Cause** | Legacy `contract_list` alias intentionally 302-redirects to repository |
| **PAR-APR relevance** | **Indirect** — programme isolation gate not clean |
| **Disposition** | **PAR-SEC-003**; tenant isolation remains **unproven** at programme level until resolved |
| **Data leak?** | **No** — cross-org detail/update still 404 |

---

## 3. Aggregate gate run (this package)

| Metric | Value |
|---|---|
| Tests run | 35 |
| Pass | 33 |
| Fail | 2 (Issues A and B above) |
| Errors | 0 |

---

## 4. Implications for PAR-APR-002

- ADR-0013 acceptance is based on **PAR-APR targeted suites (33/33 PASS)**.
- PAR-APR-002 implementation authorization must not assume a green full isolation suite until PAR-SEC-003 closes.
- Workflow routing test failure does not block ADR-0013 foundation acceptance.
