# PAR-EXC-001 — controlled-pilot monitoring extension

**Status:** **Authorized** (votes carried); CI green; ready to merge  
**Reviewed HEAD at vote time:** `3d71d8302afbfcc2e4a87f0c701e1611927615b2`  
**Authority prerequisite:** Motion 3 **Authorized**; controlled-pilot activation **PASS**  
**Programme status:** PAR-EXC-001 remains **In progress** (canonical read unauthorized — separately blocked)  
**PR:** [#78](https://github.com/Technivian/CLMOne/pull/78)

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
- active exceptions missing owner or expiry (temporary only; permanent rows excluded);
- a derived `stop_required` indicator and machine-readable stop reasons.

## Boundaries

- No contract content, credentials, secrets, reasons, comments, or identity payloads are emitted.
- No database migration.
- No write or repair operation.
- No change to committed feature-flag defaults.
- No environment flag enablement by this PR.
- No canonical read authority.
- Legacy remains authoritative.
- No PAR-APR-002, PAR-WF-010, or PAR-ID-002 work.

## Exact commands

```bash
# Focused
.venv/bin/python manage.py test \
  tests.test_par_exc_001_pilot_monitoring \
  tests.test_par_exc_001_exception \
  tests.test_par_exc_001_dual_write \
  tests.test_controlled_pilot_scope -v 1

# Broader (monitoring / audit / exception / pilot surfaces)
.venv/bin/python manage.py test \
  tests.test_par_exc_001_pilot_monitoring \
  tests.test_par_exc_001_exception \
  tests.test_par_exc_001_dual_write \
  tests.test_controlled_pilot_scope \
  tests.test_request_context_logging \
  tests.test_cross_tenant_isolation -v 1

# Command exercise
.venv/bin/python manage.py pilot_daily_health \
  --org-slug controlled-pilot-org \
  --output /tmp/par-exc-001-pilot-health.json
```

## Actual test results

| Suite | Result |
|---|---|
| `tests.test_par_exc_001_pilot_monitoring` (4 tests) | **OK** |
| Focused (pilot monitoring + exception + dual-write + controlled-pilot scope) | **32 OK** |
| Broader (+ request context logging + cross-tenant isolation) | **111 OK** |

## Command-output validation

| Check | Result |
|---|---|
| Reports exact dual-write flag + allowlist | **Pass** (off/empty and on/`controlled-pilot-org`) |
| Reports all six authorized source keys | **Pass** |
| Distinguishes AI `SUBMITTED` without decision | **Pass** (`submitted_without_decision=1`) |
| Duplicate correlations → `stop_required=true` | **Pass** |
| Multiple decisions → `stop_required=true` | **Pass** |
| Missing expiry on active temporary exception → `stop_required=true` | **Pass** |
| Security gate block counted; does not authorize/create rows | **Pass** |
| Flags off represented truthfully | **Pass** |
| Non-allowlisted org not treated as activated | **Pass** (`demo-firm` not in allowlist; zero dual-write rows) |
| Healthy data → `stop_required=false` | **Pass** |

Sample healthy output (metadata only): [`pilot_daily_health_sample.json`](pilot_daily_health_sample.json)

## Privacy / content-redaction checks

- Output contains only counters, flag names/values, org slug, and stop reason tokens.
- Fixture exception `reason` text (`fixture` / `fixture-anomaly`) does **not** appear in JSON output.
- No passwords, credentials, contract content, or identity payloads in monitoring output.
- Pre-existing `notes` string mentions the words “credentials” / “secrets” as a denial statement only.

## Migration impact

**None.**

## Rollback

Revert this PR (monitoring service + tests + evidence). No data or schema rollback required.

## Remaining authority boundaries

- Committed defaults remain **off**.
- Legacy remains **authoritative**.
- Canonical read remains **unauthorized**.
- PAR-EXC-001 remains **In progress**.
- PAR-APR-002 / PAR-WF-010 / PAR-ID-002 remain **unstarted**.

---

## Bundled implementation + merge authorization (Motion — Carried)

**Motion text:** Authorize implementation and merge of PR #78 (`feat(par-exc-001): add controlled-pilot dual-write monitoring`) at the reviewed HEAD recorded at vote time, as a read-only metadata monitoring extension of `pilot_daily_health` only; no migration; no committed default change; no canonical read authority; no automatic repair; no historical invention; legacy remains authoritative; PAR-EXC-001 remains In progress; PAR-APR-002 / PAR-WF-010 / PAR-ID-002 remain unstarted.

| Approver | Capacity | Vote | Timestamp (UTC) | Conditions acknowledged |
|---|---|---|---|---|
| @haroonwahed | Product governance | **Approve** | `2026-07-23T08:56:32Z` | yes |
| @Technivian | Engineering governance | **Approve** | `2026-07-23T08:56:33Z` | yes |
| @Technivian | Security advisory | **Approve with conditions** | `2026-07-23T08:56:34Z` | yes |

**Motion result:** **Carried** at `2026-07-23T08:56:34Z`  
**Reviewed HEAD bound by this motion:** `3d71d8302afbfcc2e4a87f0c701e1611927615b2`

### Security acknowledgement conditions (acknowledged: yes)

1. Monitoring extension is metadata-only; no contract content, credentials, secrets, reasons, comments, or identity payloads.  
2. Committed `EXCEPTION_DUAL_WRITE_*` defaults remain false; this merge does not enable flags.  
3. Canonical read remains unauthorized.  
4. No automatic repair or historical invention.  
5. No privilege / permission / membership changes.  
6. Production activation not authorized.  
7. Legacy remains authoritative.  
8. PAR-EXC-001 remains In progress; PAR-APR-002 / PAR-WF-010 / PAR-ID-002 remain unstarted.  

### Verbatim recorded votes

```text
@haroonwahed Product: Approve
Timestamp: 2026-07-23T08:56:32Z
Conditions acknowledged: yes

@Technivian Engineering: Approve
Timestamp: 2026-07-23T08:56:33Z
Conditions acknowledged: yes

@Technivian Security advisory: Approve with conditions
Timestamp: 2026-07-23T08:56:34Z
Conditions acknowledged: yes
Conditions 1–8: yes
```
