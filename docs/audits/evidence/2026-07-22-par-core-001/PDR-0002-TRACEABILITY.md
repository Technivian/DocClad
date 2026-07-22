# PAR-CORE-001 — PDR-0002 Traceability Checklist

**Date:** 2026-07-22  
**Authority:** `docs/governance/decisions/pdr/0002-contract-stage-and-status.md` (Approved)  
**Status:** **Completed** (all in-scope PDR-0002 requirements covered for application writers)

| # | PDR requirement | Evidence | Severity | Status |
|---|---|---|---|---|
| 1 | Never use “Draft” as record status | List/dashboard/compliance/JS whitelists | Was conflicting | **Compliant** |
| 2 | Six record statuses + default IN_PROGRESS | Model + import mapping | Compliant | **Compliant** |
| 3 | Nine workflow stages; ARCHIVED not a stage | Model + lifecycle_dimensions | Compliant | **Compliant** |
| 4 | Four document states | Model | Compliant | **Compliant** |
| 5 | Status↔stage pairs enforced | `Contract.save` + service + import resolve | Was partial | **Compliant** (app-layer; no DB constraint) |
| 6 | Doc EXECUTED gates + supersede audit | Validators + `document.superseded` | Was partial | **Compliant** for supersede paths |
| 7 | Activation triad | `activate_contract` | Compliant | **Compliant** |
| 8 | Transition ownership via lifecycle service | Bulk stage/jobs + CRM/CSV/inbound | Was conflicting | **Compliant** |
| 9 | Audit events named in PDR (+ supersede) | `lifecycle_stage_changed`, `operational_position_changed`, `document.superseded` | Was partial | **Compliant** |
| 10 | Compact header `status · stage` | Template + command label | Was partial | **Compliant** |
| 11 | Right rail three dimensions | Detail template | Compliant | **Compliant** |
| 12 | Repository status/stage filters | Repository + bulk JS | Was partial | **Compliant** |
| 13 | Separate badge helpers | clmone_format | Compliant | **Compliant** |
| 14 | Tests | ownership + prior CORE-001 suites | Was partial | **Compliant** |

## Ownership gaps closed (this pass)

1. **CRM/CSV/inbound** — `persist_contract_with_imported_lifecycle` / `resolve_import_status_stage` used by Salesforce, NetSuite, CSV command, inbound import. Illegal pairs rejected.
2. **Document supersession** — `supersede_document` emits `document.superseded` with actor, contract, previous/replacement, reason/source, correlation_id. Wired in document update view + AI upload.
3. **Raw Model.save** — `Contract.save` validates status/stage when those fields are written; create-time coerce for default `DRAFTING` + non-`IN_PROGRESS` status; `skip_lifecycle_validation` for repair; partial updates safe.

## Out-of-band notes (not PDR blockers)

- `QuerySet.update()` / `bulk_update` still bypass `Model.save` (documented; no DB CHECK added).
- Legacy list query keys remain stage-filter aliases (labels fixed earlier).

## Evidence artifacts

- `ownership-suite.txt` — 88 OK
- `django-tests.txt` — earlier vocabulary slice (40 OK)
- Code: `contract_import_lifecycle.py`, `document_supersession.py`, `Contract.save`, import/upsert call sites

## Rollback

Revert the PAR-CORE-001 commits. No schema migration. `skip_lifecycle_validation` unused in product paths.
