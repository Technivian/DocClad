# PAR-EXC-001 — controlled-pilot monitoring extension

**Status:** Implementation proposed on `agent/par-exc-001-pilot-monitoring`  
**Authority:** Motion 3 Authorized; controlled-pilot activation PASS  
**Programme status:** PAR-EXC-001 remains **In progress**

## Scope

Extend the existing read-only `pilot_daily_health` report with metadata-only PAR-EXC-001 monitoring for `controlled-pilot-org`.

The extension reports:

- operational flag and exact allowlist state;
- actions per six authorized legacy source paths;
- canonical request and decision counts;
- submitted-only requests without a decision, including the authorized AI pattern;
- dual-write failures;
- Security gate blocks;
- cross-tenant denials;
- duplicate correlation groups;
- requests with multiple canonical decisions;
- active exceptions missing owner or expiry;
- a derived `stop_required` indicator and machine-readable stop reasons.

## Boundaries

- No contract content, credentials, secrets, reasons, comments, or identity payloads are emitted.
- No database migration.
- No write or repair operation.
- No change to committed feature-flag defaults.
- No canonical read authority.
- Legacy remains authoritative.
- No PAR-APR-002, PAR-WF-010, or PAR-ID-002 work.

## Validation

Focused tests cover:

1. normal daily counters, including AI `SUBMITTED` without a decision;
2. duplicate correlation detection;
3. multiple-decision detection;
4. active missing-expiry detection;
5. derived stop-condition output.

## Rollback

Revert the monitoring service and focused test commits. No data or schema rollback is required.
