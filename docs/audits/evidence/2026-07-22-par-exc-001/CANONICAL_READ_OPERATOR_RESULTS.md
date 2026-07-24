# PAR-EXC-001 canonical-read operator results

## Result: PASS

**Implemented and observed main SHA:** `86625b95cfbc968dea2f7cb31b8fc354a36584cf` (PR [#85](https://github.com/Technivian/CLMOne/pull/85))  
**Operator record:** [PR #85 comment 5068883933](https://github.com/Technivian/CLMOne/pull/85#issuecomment-5068883933)  
**Environment:** `par-exc-001-canonical-read-authority` (isolated non-production SQLite operator database)

The observation enabled both reversible flags only for `controlled-pilot-org`, ran the six approved sources, and then returned both flags to `false` with both allowlists empty. Legacy authority is restored.

| Control | Observed evidence |
|---|---|
| Scope | `controlled-pilot-org` only; six approved paths only |
| Canonical use | 6 correlated canonical reads |
| Legacy fallback | 1 correlation miss returned the supplied legacy result |
| AI boundary | `AI_EXCEPTION` remained `SUBMITTED`, was non-applicable, and granted no privilege |
| Tenant isolation | Exact implementation cross-tenant suite passed (75 tests); resolver rejects cross-tenant reads fail-closed |
| Permissions | No permission mutation path was exercised |
| Abort state | No abort condition triggered; `stop_required: false` |
| Counters | used 6; fallbacks 1; canonical-read denials 0; cross-tenant denials 0; canonical requests 6; decisions 5; submitted-without-decision 1 |
| Rollback | Both flags disabled; both allowlists empty; legacy authoritative |

## Verification

- Six required GitHub checks were green for the immutable implementation head `823b302ec9c57cf1d4faa1edab8dec06c3d2635d` before merge.
- `python manage.py check` passed.
- Canonical-read and dual-write tests passed (21 tests).
- Cross-tenant isolation passed (75 tests).
- `python manage.py audit_null_organizations` passed.

This result is limited to the named non-production observation. It does not authorize production activation, repair, permission changes, ADMIN authority, or legacy retirement.
