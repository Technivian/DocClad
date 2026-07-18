# Phase 2A component contracts

Status: implemented for shared APIs and a representative template set; legacy
selectors remain supported compatibility adapters.

## Canonical APIs

| Family | API | Supported variants and states |
|---|---|---|
| Button | `.dc-ds-button` / `design_system/button.html` | `default`, `primary`, `ghost`, `quiet`, `soft`, `link`, `danger`, `danger-soft`; `sm`/`lg`; hover, `:focus-visible`, active (`aria-pressed`/`.is-active`), disabled, and loading (`aria-busy`). |
| Form control | `.dc-ds-control`, `.dc-ds-form-field` / `form_field.html` | text, select, textarea, check; default, placeholder, hover-by-browser, focus-visible, disabled, and validation error (`aria-invalid` or `.dc-ds-form-field--error`). |
| Badge | `.dc-ds-badge` / `status_badge.html` | `success`, `progress`, `attention`, `danger`, `special`, `phase`, `neutral`; `sm`. Badges are non-interactive status output, so button states do not apply. |
| Surface | `.dc-ds-surface` / `surface_card.html` | default, `soft`, `expressive`, `feature`, `feature-clear`, `interactive`; interactive surfaces support hover and focus-visible. |

## Existing implementations and disposition

| Family | Implementations inventoried | Disposition |
|---|---|---|
| Buttons | `.btn`, `.btn-primary`, `.btn-secondary`, `.btn-danger`, `.btn-sm`, `.btn-lg`, `.btn-cta`, `.btn-soft`, `.btn-quiet`, `.btn-link`, `.btn-danger-soft`, `.btn-soft-accent`, `.btn-ghost`, `.btn-primary-grad*`, `.btn-soft-primary`, `.btn-ghost-secondary`, `.repo-mini-btn` | First eleven map to canonical variants or sizes. `btn-primary-grad*` and `btn-soft-primary` are aliases; retain while consumed. `repo-mini-btn` is genuinely repository-specific and out of scope. |
| Controls | `.input`, `.input-error`, `.form-control`, `.form-check-input`, `.form-file`, `.input-base`, `.select-base`, and route-scoped control classes | The first five are duplicate shared contracts and map to `.dc-ds-control`/`.dc-ds-check`. `input-base` and `select-base` remain compatibility adapters. Route-scoped controls are distinct and remain out of scope. |
| Badges | `.badge`, `.badge-success`, `.badge-warning`, `.badge-danger`, `.badge-info`, `.badge-neutral`, `.badge-sm`, `.badge-{green,blue,yellow,red,purple,gray}` | The named semantic colours map to canonical tones. `badge-sm` maps to `dc-ds-badge--sm`. `.badge-expiring` was removed in Phase 2B.2 after a zero-runtime-consumer check. |
| Surfaces | `.card*`, `.card-l1`, `.card-l2`, `.card-l3`, `.panel*`, `.stat*`, `.contract-surface*`, `.cform-*`, `.repo-*` | `card*` and `panel*` map to surface/head/body. Contract, form, and repository families are route-specific compatibility systems and are explicitly retained for later phases. |

## Legacy-to-canonical mapping

| Legacy | Canonical | Status |
|---|---|---|
| `.btn-cta`, `.btn-primary`, `.btn-primary-grad*` | `.dc-ds-button--primary` | Temporary adapter; consumers remain. |
| `.btn-quiet`, `.btn-secondary` | `.dc-ds-button--quiet` | Temporary adapter; consumers remain. |
| `.btn-soft`, `.btn-soft-accent`, `.btn-soft-primary` | `.dc-ds-button--soft` | Temporary adapter; consumers remain. |
| `.btn-link` | `.dc-ds-button--link` | Temporary adapter; consumers remain. |
| `.btn-danger`, `.btn-danger-soft` | `.dc-ds-button--danger` / `--danger-soft` | Temporary adapter; consumers remain. |
| `.form-control`, `.input`, `.input-base`, `.select-base` | `.dc-ds-control` | Temporary adapter; consumers remain. |
| `.form-check-input` | `.dc-ds-check` | Temporary adapter; consumers remain. |
| `.badge-{green,blue,yellow,red,purple,gray}` | `.dc-ds-badge--{success,progress,attention,danger,special,neutral}` | Template adapter `legacy_badge_tone` supports staged migration. |
| `.badge-sm` | `.dc-ds-badge--sm` | Temporary adapter; consumers remain. |
| `.card*`, `.panel*` | `.dc-ds-surface*` | Temporary adapter; consumers remain. |

No legacy selector was removed in Phase 2A: repository-wide searches still
find consumers. New uses must select the canonical API; a mixed class list is
allowed only as a clearly temporary visual-compatibility adapter.

## Remaining compatibility usage (zero-removal gate)

The 2026-07-18 repository scan found references in 153 files (templates,
source styles, and the compatibility layer). These are deliberately retained;
counts include definitions and adapters as well as template consumers, and are
therefore a removal gate rather than a migration-progress metric.

| Legacy selector | References | Status |
|---|---:|---|
| `.btn-primary` | 155 | Temporary shared API; consumers remain. |
| `.btn-ghost` | 143 | Temporary shared API; consumers remain. |
| `.btn-quiet` | 57 | Temporary adapter used by the representative migrations. |
| `.btn-cta` | 41 | Temporary adapter used by the representative migrations. |
| `.input-base` / `.select-base` | 33 / 21 | Existing form compatibility contracts. |
| `.form-control` / `.form-check-input` | 31 / 14 | Existing form compatibility contracts. |
| `.badge-sm` | 147 | Temporary status-size API; consumers remain. |
| `.badge-{green,blue,yellow,red,purple,gray}` | 93 / 67 / 74 / 74 / 20 / 110 | Legacy visual-status aliases; template adapter is in use. |
| `.badge-expiring` | 0 | Removed in Phase 2B.2 after the repository-wide runtime-consumer check. |
| `.repo-mini-btn` | 10 | Repository-specific; intentionally out of scope. |

The full selector-family inventory and mandatory zero-consumer removal process
are in `docs/design-system/LEGACY_COMPATIBILITY_INVENTORY.md`.

## Representative migrations

- List: `contracts/repository.html` — search, sort/filter controls, and the
  clear-filter action.
- Create/edit form: `contracts/contract_form.html` — header status badge and
  form actions. Its dense field widgets retain their compatibility classes in
  this phase; canonical controls are exercised on the list and dialog flows.
- Detail: `contracts/contract_detail.html` — header status/action group and
  next-action surface.
- Modal: the negotiation-note dialog in `contract_detail.html` — controls and
  actions.

Public landing-page and legal-document styles are not consumers of this API
and remain outside Phase 2A.
