# PAR-EXC-001 — Test results

**Date:** 2026-07-22  
**Command:** `make test-fast APP=tests.test_par_exc_001_exception`  
**Result:** **11 OK**

Raw log: [`django-tests.txt`](django-tests.txt)

## Coverage

- Canonical create / decide / immutability / expiry / renewal / cross-tenant / privilege / permanent / Security gate
- Legacy characterization: deadline defer creates no ExceptionRequest; keep_exception path still module-owned

## Migration proof

- Forward `0114`: [`migrate-reforward.txt`](migrate-reforward.txt)
- Rollback to `0113`: [`migrate-rollback.txt`](migrate-rollback.txt)
