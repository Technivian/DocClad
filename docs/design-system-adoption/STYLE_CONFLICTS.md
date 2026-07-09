# Style Conflicts and CSS Readiness

This file lists CSS and token risks that could interfere with a future `src/design-system` transplant.

## Global Token Conflicts

Current token sources:

- `theme/templates/base.html`
- `theme/templates/base_fullscreen.html`
- `theme/static_src/src/styles.css`
- `theme/static_src/src/base.css`
- `theme/static_src/src/theme.css`
- page-local `<style>` blocks

Conflicting token names:

- `--bg`
- `--surface`
- `--surface-alt`
- `--primary`
- `--accent`
- `--ink`
- `--muted`
- `--border`
- `--card`
- `--card-bg`
- `--card-border`
- `--danger`
- `--warn`
- `--radius`

Risk:

- A copied design system using common names like `--background`, `--primary`, `--card`, or `--border` may silently change existing pages.

Recommendation:

- Namespace incoming tokens at first, for example `--ds-*`, or mount them under a scoped root such as `.ds-scope`.
- Do not globally override `:root` until page migrations are complete.

## Tailwind and Build Conflicts

Current package split:

- `theme/package.json`: Tailwind `^3.3.6`
- `theme/static_src/package.json`: Tailwind `^4.1.11`
- `theme/static_src/src/styles.css`: Tailwind v4-style `@import "tailwindcss";`, `@theme`, and `@source`
- `theme/static_src/tailwind.config.js`: Tailwind config written for config-based scanning.

Risk:

- Running build commands from different directories may use different Tailwind versions and produce different CSS.
- Incoming design-system Tailwind config may assume a single app root and React/TSX scanning.

Recommendation:

- Choose one canonical frontend package/build root before transplant.
- Prefer `theme/static_src` as the canonical CSS build root unless the app is converted to a JS app.
- Document whether Tailwind v4 is required by the incoming system.

## Global Class Name Collisions

Existing generic classes likely to collide:

- `.btn`
- `.card`
- `.badge`
- `.table`
- `.input`
- `.label`
- `.drawer`
- `.toast`
- `.progress`
- `.stepper`
- `.empty-state`

Risk:

- A reusable design system often defines exactly these names. Copying it unscoped can alter many pages immediately.

Recommendation:

- Import new CSS under a namespace or with explicit component classes.
- Avoid global utility names until all old classes are removed or aliased.

## Page-Local CSS Blocks

Several major pages define their own CSS in templates:

- `dashboard.html`
- `contracts/contract_list.html`
- `contracts/contract_form.html`
- `contracts/dpa_workflow_builder.html`
- `contracts/msa_workflow_builder.html`
- `contracts/nda_workflow_builder.html`
- `contracts/dpa_contract_workspace.html`
- `contracts/msa_contract_workspace.html`
- `contracts/nda_contract_workspace.html`
- `contracts/workflow_detail.html`
- `contracts/dpa_review_pack_detail.html`

Risk:

- Page-local styles can override design-system primitives unpredictably.

Recommendation:

- During migration, move each page from local CSS to design-system components in the same page-specific commit.
- Do not delete local CSS globally before the page has been migrated and visually checked.

## Inline Style Hotspots

There are roughly 103 `style=` attributes across template/static sources. Known hotspots include:

- error pages
- DPA review detail
- workflow/detail pages
- SVG/preview/demo templates
- old cards and panels

Risk:

- Inline styles bypass component tokens and can defeat the new system.

Recommendation:

- Replace inline styles only as part of each page migration.
- Preserve dynamic style values that encode real progress or visual state until a component prop/variant exists.

## Color Conflicts

Current app uses both:

- DocClad legal-tech palette: navy, off-white, teal, copper, amber, rose.
- Older/generic palette: blue primary, green accent, yellow warning, red danger, gray utility colors.

Risk:

- New design-system colors may be close but semantically different.

Recommendation:

- Create a mapping table before migration:
  - primary action = copper
  - active/trust/workflow = teal
  - attention = muted amber
  - critical/blocker = muted rose/red
  - background = cool off-white
  - shell = deep navy

## Shadow, Radius, Spacing Conflicts

Current patterns:

- Some docs/standards prefer minimal shadows and 8px radii.
- Existing utilities include `rounded-xl`, 12-16px radii, and `shadow-lg`.
- Page-specific cockpit panels use 6-8px radii.

Risk:

- Transplanted components may introduce softer SaaS styling or larger radii.

Recommendation:

- Set a DocClad adapter theme before replacing pages.
- Keep cards at 8px radius or less unless a canonical exception is approved.

## CSS Transition Conflict

`theme/static_src/src/base.css` contains a universal transition rule:

```css
* {
  transition: colors 150ms ease, background-color 150ms ease, border-color 150ms ease;
}
```

Risk:

- `colors` is not a standard property. Universal transitions can also affect new design-system components unexpectedly.

Recommendation:

- Do not edit in this audit. Review during token wiring.

## CSP and Script Constraints

The app uses CSP nonces in templates and loads `static/js/csp-handlers.js`.

Risk:

- A React/Radix/shadcn system may assume inline scripts, client hydration, portals, or style injection.

Recommendation:

- Confirm CSP compatibility before adding runtime components.
- Prefer server-rendered/static components for first migrations.
