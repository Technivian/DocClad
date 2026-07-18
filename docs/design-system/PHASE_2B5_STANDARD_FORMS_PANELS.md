# Phase 2B.5: standard record and admin forms and panels

Status: complete, pending Phase 3 review.

## Approved baseline replacement decision

Approval was given explicitly for Phase 2B.5 to replace the documented
obsolete list, detail, and contract-form baselines using fresh deterministic
data. This is a reviewed replacement, not a snapshot update to suppress a
new failure.

| Baseline | Prior evidence | Replacement rationale | Approval evidence |
|---|---|---|---|
| Phase 1 list | Stable 2,101-pixel delta; geometry matched while approved token/button/badge/footer treatments differed. | The prior image predates approved Phase 2 work. | User approved Phase 2B.5 baseline replacement after the Phase 2B.4 record. |
| Phase 1 detail | Stable 28,564-pixel delta across page-wide approved text/surface treatment. | The prior image predates approved Phase 2 work and is no longer an assertion of the accepted product. | Same explicit approval. |
| Phase 2A contract form | 11,887-pixel delta; old image showed superseded draft actions. | The route’s approved labels and validation behavior are intentionally different. | Same explicit approval; source contract-launch tests verify the behavior. |

The replacement used the existing Playwright E2E seed/server and unchanged
viewport, screenshot, and animation settings. List, detail, and form images
were regenerated only after this decision was recorded; the existing
Phase 2A form-validation image was refreshed for the same approved route.

The first detail replay exposed a 7,078-pixel delta caused by the pre-existing
`.reveal-stagger` entrance effect being captured before its final opacity.
`visual-baselines.spec.js` now waits for the first and last reveal children to
reach opacity `1` before capture. The detail image was then regenerated once
through this deterministic harness and replayed cleanly. This is a test
stability correction, not a product-style change.

## Migrated standard families

The following complete record-maintenance and policy-administration form
families now use the shared form-field API while preserving their existing
form tags, field names, grid spans, help copy, server validation, permissions,
and actions:

| Family | Templates | Canonical adoption |
|---|---:|---|
| Standard record / policy maintenance | 14 | 10 simple-loop forms include `design_system/form_field.html`; four grid/edit branches retain their layout and use the equivalent canonical field anatomy. All 14 co-apply `.dc-ds-surface`. |
| Approval-request administration | 1 | Uses `form_field.html` for every editable field and canonicalizes the main and both guidance panels. |

The shared partial now accepts `preserve_help=True`. This keeps existing
visible help text rather than replacing it with the partial’s optional tooltip
presentation, while still providing the canonical label, control, error, and
focus contracts.

The document-upload creation branch remains a bespoke upload/review flow. Its
one direct legacy control alias is retained because its progressive disclosure,
file handling, and generated-field interactions are a route-specific system;
the standard document-edit branch is migrated.

## Consumer and removal evidence

Repository counts use `rg` over the named runtime templates; generated CSS,
tests, and documentation are excluded.

| Runtime item | Before | After | Result |
|---|---:|---:|---|
| Canonical surfaces in the migrated family | 0 | 15 | Complete family co-application. |
| Shared `form_field.html` consumers in the migrated family | 0 | 11 | Simple-loop record/admin forms use the shared partial. |
| Explicit canonical field anatomy in layout-sensitive branches | 0 | 4 | Client, matter, deadline, and document edit preserve their grids. |
| Legacy `panel` compatibility consumers in the migrated family | 15 | 15 | Co-applied; zero-consumer gate not met. |
| Direct legacy control-alias consumers in the migrated family | 1 | 1 | Document-upload compatibility exception above. |
| Legacy selectors removed | 0 | 0 | None reached zero runtime consumers. |

## Validation and visual evidence

- Refreshed Phase 1 list, detail, and form baseline tests: passed at 1440px.
- Refreshed Phase 2A contract-form validation baseline: passed at 1440px and
  390px.
- `phase-2b5-standard-forms-panels.spec.js`: passed. It verifies keyboard
  focus, server validation/error state, desktop and 390px record layout, and
  the approval-admin field/panel family. Two new snapshots cover the record
  error and admin form archetypes.
- Focused Django suites: 86 passing tests; `manage.py check` passed.

## Remaining decisions and recommended Phase 3

There is no unresolved business, permission, accessibility, or security
decision. Legacy panel/control aliases remain compatibility APIs with active
consumers. Phase 3 should separately scope list/table and page-scaffold
consolidation, beginning with standard record lists before dashboards and
workflow workspaces.
