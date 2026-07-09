# Settings Hub Migration

## Files changed

- `theme/templates/settings_hub.html`
- `theme/templates/settings_hub_content.html`
- `theme/templates/settings_hub_sections.html`
- `theme/templates/settings_hub_surface_meta.html`
- `theme/static_src/src/design-system/components.css`
- `theme/static/css/dist/styles.css`
- `docs/design-system-adoption/SETTINGS_HUB_MIGRATION.md`

The compiled stylesheet changed as expected after rebuilding `theme/static_src`.

## Adapter partials and classes used

- `design_system/page_scaffold.html`
- `design_system/page_hero.html`
- `design_system/surface_card.html`
- `design_system/status_badge.html`
- `dc-ds-page`
- `dc-ds-scaffold`
- `dc-ds-surface`
- `dc-ds-surface__head`
- `dc-ds-surface__title`
- `dc-ds-surface__body`
- `dc-ds-settings-section`
- `dc-ds-settings-section__title`
- `dc-ds-settings-section__copy`
- `dc-ds-rail`
- `dc-ds-action-zone`
- `dc-ds-action-zone__label`
- `dc-ds-action-zone__title`

The adapter CSS received a small anchor-state enhancement for `dc-ds-action-zone[href]` so linked settings rows do not inherit default browser link styling.

## Behavior preserved

- The page still extends `base.html`.
- The page title remains `Settings – DocClad`.
- Every existing settings destination is preserved:
  - `profile`
  - `contracts:organization_team`
  - `contracts:organization_activity`
  - `organization_security_settings`
  - `organization_session_audit`
  - `organization_identity_settings`
  - `contracts:identity_telemetry_dashboard`
  - `contracts:approval_rule_list`
  - `contracts:privacy_dashboard`
  - `operations_dashboard`
- There were no forms, permission checks, conditional blocks, or context-variable-dependent sections in the original template.
- No backend views, URLs, forms, permissions, models, or data fetching were changed.

## Risks avoided

- No shell, sidebar, or topbar templates were changed.
- No route names or context variable names were changed.
- No React, Radix, shadcn, or new JavaScript was introduced.
- Existing global CSS and older page classes remain in place for unmigrated pages.
- The migration uses small page-local includes only so `page_scaffold.html` and `surface_card.html` can remain generic.

## Manual test checklist

- Open `/settings/`.
- Confirm the settings hub renders inside the existing DocClad shell.
- Confirm all ten settings links navigate to the same destinations as before.
- Confirm browser back/forward navigation still works.
- Confirm the page remains usable at desktop and narrow viewport widths.
- Confirm no unrelated pages have adopted `dc-ds-*` markup.

## Before/after notes

- Before: a single local `page-wrap`, `page-header`, and `settings-card` grid.
- After: a design-system scaffold, hero, grouped surface, settings sections, status badge, and action-zone rows.
- The content is grouped by Account, Organization, Security and identity, and Governance to match the adapter's settings-section pattern.

## Known limitations

- The adapter does not yet include a dedicated compact settings link-card partial, so settings destinations use `dc-ds-action-zone` as the clickable row/card affordance.
- The migrated page intentionally does not alter shell spacing, navigation, or global layout behavior.
