# Phase 4B: counterparty and governance record/detail scaffolds

Status: complete, pending Phase 4 review.

This record is incremental to Phase 4A. It covers existing standard counterparty,
privacy, governance, policy, compliance, and risk record routes only. There are
no separate runtime entity or contact templates; those values are fields on the
counterparty record. Due diligence remains out of scope as a workflow system.

## Families migrated

| Family | Standard templates migrated | Scaffold use |
|---|---|---|
| Counterparties | detail, create/edit | Shell context, labelled back navigation, action zone, metadata rows, form rhythm |
| Compliance checklists | detail, create/edit | Shell context, action zone, section rhythm, checklist structure, form rhythm |
| Data inventory | detail, create/edit | Shell context, action zone, metadata rows, form rhythm |
| Legal holds | detail, create/edit | Shell context, action zone, metadata rows, form rhythm |
| Subprocessors | detail, create/edit | Shell context, action zone, metadata rows, form rhythm |
| Transfer records; retention policies; risk register; ethical walls | create/edit | Shell context, labelled back navigation, form rhythm |

All headers now use the authenticated shell for title, optional subtitle, and
labelled back navigation. Existing detail actions remain visible in the canonical
action zone. The selected families have no tabs, so none were introduced. Fields,
validation rendering, submission endpoints, object scoping, and permissions are
unchanged.

## Shared API additions

| API | Responsibility |
|---|---|
| `.dc-ds-record-metadata` and `__row`, `__label`, `__value` | Compact detail label/value rows within an existing shared surface |
| `.dc-ds-record-checklist-item` and elements | Existing compliance-checklist item geometry, completion state, and checkbox affordance |
| `.dc-ds-record-checklist-add` and `__title` | Existing add-item section divider and label |

The additions use existing spacing, surface, border, type, and radius tokens.
They replace page-local structural CSS only; no new visual language or status
meaning was introduced.

## Consumer and removal evidence

Counts use automated `rg` searches over the 14 scoped runtime templates and
source CSS. Tests, documentation, and generated CSS are excluded.

| Item | Before | After | Result |
|---|---:|---:|---|
| Scoped runtime templates using `.dc-ds-record-page` | 0 | 14 | Complete adoption for every scoped template. |
| Scoped legacy canvas header/scaffold consumers | 14 | 0 | `page-wrap`, `page-header`, and canvas `page-title` are absent. |
| Scoped local `<style>` blocks | 3 | 0 | Data inventory, legal hold, and compliance detail styles were moved or replaced. |
| Page-local CSS rules | 23 | 0 | All three local blocks reached the zero-consumer gate before removal. |
| Local selector families | 16 | 0 | `di-*`, `detail-*`, `back-link`, checklist, checkbox, and add-item aliases map to canonical APIs. |
| Canonical detail/action/form API occurrences | 0 | 161 | Includes intentional elements and modifiers across the scoped families. |

The shared `page-wrap`, `page-header`, and page-title compatibility selectors
remain: the 113 out-of-scope runtime consumers recorded in Phase 4A still
prevent repository-wide removal. No route-specific or workflow selector was
removed.

## Validation and visual decision

- Tailwind v4 build and `manage.py check`: passed.
- `test_design_system_phase2a`: 19 passing tests, including Phase 4B structure
  and zero-local-style assertions.
- All 14 scoped templates parsed successfully through Django's template loader.
- `phase-4b-governance-record-scaffolds.spec.js`: 2 passing browser tests,
  covering desktop and 390px containment, shell labels, back navigation, action
  hierarchy, keyboard focus, and counterparty validation errors.
- `git diff --check`: passed.
- Existing Phase 2B.5 baseline replay used `--update-snapshots=none`. It keeps
  the known 550-pixel (0.01%) sidebar-glyph raster variance on both images and
  has no record-canvas difference. No baseline, tolerance, or expectation changed.

## Deferred work

No business, permission, accessibility, or security decision is unresolved.
Phase 5 should separately scope the remaining cross-record shell compatibility
APIs and complex record-detail/workspace families, beginning with a decision on
contract-detail layouts, workflow workspaces, and dashboard scaffolds.
