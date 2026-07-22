# PAR-CORE-001 — PDR-0002 Traceability Checklist

**Date:** 2026-07-22  
**Authority:** `docs/governance/decisions/pdr/0002-contract-stage-and-status.md` (Approved)  
**Status:** In progress (vertical slices shipped; remaining limitations below)

| # | PDR requirement | Pre-slice evidence | Severity | Slice status |
|---|---|---|---|---|
| 1 | Never use “Draft” as record status | Model OK; UI tabs/JS/compliance used Draft | Conflicting | **Fixed** — list labels, dashboard buckets, compliance stats, bulk JS |
| 2 | Six record statuses + default IN_PROGRESS | Model compliant | Compliant | Maintained |
| 3 | Nine workflow stages; ARCHIVED not a stage | Model compliant | Compliant | Maintained |
| 4 | Four document states | Model compliant | Compliant | Maintained |
| 5 | Status↔stage pairs enforced | Service + clean(); raw save gap | Partial | Ownership improved for bulk stage + jobs; raw ORM still open |
| 6 | Doc EXECUTED gates + supersede | Validators exist; supersede audit thin | Partial | **Deferred** (not in this slice) |
| 7 | Activation triad | `activate_contract` OK | Compliant | Maintained |
| 8 | Transition ownership via lifecycle service | Bulk status OK; bulk stage + jobs bypassed | Conflicting | **Fixed** bulk stage + renewal job |
| 9 | Audit events named in PDR | Stage job used `renewal_promoted` | Partial | Job now `contract.lifecycle_stage_changed` |
| 10 | Compact header `status · stage` | Template OK; command helper invented labels | Partial | **Fixed** `build_lifecycle_command_label` |
| 11 | Right rail three dimensions | Present | Compliant | Maintained |
| 12 | Repository status/stage filters | Repository OK; legacy list + bulk JS drifted | Partial | **Fixed** bulk JS; list tab labels |
| 13 | Separate badge helpers | Present | Compliant | Maintained |
| 14 | Tests for matrix/filters/header/jobs | Partial coverage | Partial | Added `tests/test_pdr0002_core001.py`; updated shell/audit tests |

## Remaining limitations (do not mark Completed)

- CRM/CSV/inbound import paths still set `contract.status` then `.save()` bypassing the lifecycle service.
- `Document` supersede paths may omit `document.status_changed` audit.
- `Model.save()` does not call `full_clean()` / pair validation globally.
- Legacy list query keys (`DRAFT`, `IN_REVIEW`, …) remain as **stage-filter aliases** (labels no longer say record-status Draft); prefer repository filters for new work.

## Evidence

- Tests: `docs/audits/evidence/2026-07-22-par-core-001/django-tests.txt` (40 OK)
- Code: repository bulk stage ownership; lifecycle job; command label; dashboard/list/compliance vocabulary; repository JS whitelist
