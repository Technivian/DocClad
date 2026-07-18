# ADR/PDR 0008: CLM One frontend design-system unification

Status: Accepted

Approval metadata:

- Approved by: CLM One design-system review
- Approved on: 2026-07-18
- Approval scope: Phase 1 foundation; authorizes the constrained Phase 2A
  shared-component consolidation described in this ADR.
- Phase 2B remains subject to a separate review.

## Context

The authenticated application currently resolves visual rules through canonical
tokens, Tailwind utilities, Casefile components, compatibility selectors,
`base.html` inline CSS, and page-local styles. This makes a visually neutral
change difficult to validate and makes future calibration non-local.

## Decision

1. `theme/static/css/clmone-tokens.css` is the sole canonical source of CLM
   One design tokens. It owns colour, typography, spacing, shape, elevation,
   motion, layout, chart, and focus values.
2. `theme/static_src/src/styles.css`, built by Tailwind CSS v4/PostCSS, is the
   sole active utility and application-style build path. Tailwind v3
   configuration and unused theme inputs are archived or removed only after a
   repository-wide runtime-consumer search is clean.
3. Django partials in `theme/templates/design_system/` and their `.dc-ds-*`
   styles are the canonical authenticated-app component API.
4. `base.html` owns structural shell markup, stylesheet ordering, navigation,
   and runtime hooks. Its shell CSS lives in a compiled source stylesheet
   loaded after page CSS, preserving the previous cascade without retaining a
   late template style block.
5. New page-local CSS is prohibited by default. It requires a documented
   exception for route-scoped, non-reusable composition; it must consume
   canonical tokens and cannot redefine component primitives.
6. Legacy selectors and `--ds-*` aliases remain temporary compatibility APIs.
   They receive deprecation comments and an inventory, but remain intact until
   a zero-consumer check authorizes removal.
7. The public landing page and legal-document rendering are explicit separate
   concerns. They may remain scoped systems and do not define authenticated
   application tokens or components.

## Consequences

- Phase 1 changes infrastructure only: no route, workflow, permission,
  content-hierarchy, page migration, or intentional visual change.
- The active stylesheet order remains tokens, compiled app CSS, optional page
  CSS, then compiled shell compatibility CSS.
- The generated `theme/static/css/dist/*.css` files are build artefacts and
  are never hand-edited.
- Phase 2 can consolidate primitives only after this foundation is reviewed.

## Build-path verification

Phase 1 confirmed the only runtime CSS build command is
`npm --prefix theme/static_src run build`, which invokes PostCSS with
Tailwind CSS v4 from `theme/static_src/src/styles.css`. A repository-wide
consumer search found no runtime loader, package script, CI reference, or
Tailwind configuration directive using `theme/static_src/tailwind.config.js`,
`theme/static_src/src/theme.css`, or `theme/package.json`; those disconnected
v3/unused files were removed. `global-shell.css` is compiled as a separate
source input by that same build command.

## Validation and rollback

Build CSS from `theme/static_src`, run the design-system and UI suites, and
use the representative Playwright screenshots as the visual baseline. A
rollback restores the previous shell stylesheet link and does not require
route or template-content changes.
