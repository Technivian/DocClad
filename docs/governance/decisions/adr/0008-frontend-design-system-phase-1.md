# ADR/PDR 0008: CLM One frontend design-system unification

Status: **Completed** (authenticated application)

Approval metadata:

- Approved by: CLM One design-system review
- Approved on: 2026-07-18 (Phase 1 foundation)
- Effective completion date: **2026-07-19** (Phase 6 authenticated
  retirement + anti-drift)
- Approval scope: Phases 1–6 for the authenticated app. Public-shell and
  legal-document systems remain explicit exceptions (optional Phase 6.1).

## Context

The authenticated application historically resolved visual rules through
canonical tokens, Tailwind utilities, Casefile components, compatibility
selectors, `base.html` inline CSS, and page-local styles. That made visually
neutral change hard to validate and made calibration non-local.

## Final architecture (authenticated app)

1. `theme/static/css/clmone-tokens.css` is the sole canonical source of CLM
   One design tokens (colour, typography, spacing, shape, elevation, motion,
   layout, chart, focus).
2. `theme/static_src/src/styles.css` (Tailwind CSS v4 / PostCSS) is the sole
   active utility and application-style build path. Generated
   `theme/static/css/dist/*.css` files are build artefacts and are never
   hand-edited.
3. Django partials in `theme/templates/design_system/` and `.dc-ds-*` styles
   are the canonical authenticated-app component API.
4. `base.html` owns structural shell markup via `.dc-ds-shell*`, stylesheet
   ordering, navigation, and runtime hooks. Shell CSS is compiled
   (`global-shell.css`) and loaded after optional page CSS.
5. New page-local CSS is prohibited by default. Documented exceptions are
   limited to route-scoped, non-reusable composition that consumes canonical
   tokens and does not redefine primitives.
6. Authenticated templates no longer use dual `btn-*` / `badge-*` class
   attributes. Global `.btn-*` / `.badge-*` CSS definitions remain only as a
   bridge for approved public/legal exceptions until Phase 6.1.
7. Command Center (`dashboard.html` + route-local `command-center.css`) keeps
   expressive hero/score/chip chrome under `.cc-v3-*`; shared controls use
   `.dc-ds-*`. Dead zero-consumer `.cc-v3-*` layers are purged.
8. The public landing page, registration/error shells, and legal-document
   rendering remain separate concerns. They do not define authenticated-app
   tokens or components.

## Consequences

- Authenticated-app design-system unification through Phase 6 is complete:
  no further dual-class retirement is required to ship the authenticated
  release.
- Anti-drift and colour-contrast checks run in CI
  (`.github/workflows/design-system-guardrails.yml`).
- Visual baselines fail on unexplained pixel drift and never regenerate
  snapshots automatically (`.github/workflows/visual-regression.yml`).
- Optional Phase 6.1 (public-shell migration + global alias deletion) does
  **not** block the authenticated-app release.

## Phase completion record

| Phase | Outcome |
|---|---|
| 1 | Tokens, build path, shell ownership, inventory |
| 2 / 2A–2B | Shared component consolidation |
| 3–5 | Lists, records, shell, workspaces, Command Center |
| **6** | Authenticated `btn-*`/`badge-*` retirement, dead CC purge, anti-drift + contrast enforcement |

## Evidence and inventories

- Phase 6 evidence: [`docs/design-system/PHASE_6_LEGACY_RETIREMENT.md`](../../../design-system/PHASE_6_LEGACY_RETIREMENT.md)
- Current inventory: [`docs/design-system/LEGACY_COMPATIBILITY_INVENTORY.md`](../../../design-system/LEGACY_COMPATIBILITY_INVENTORY.md)
- Historical Phase 1 inventory (superseded): [`docs/design-system/LEGACY_COMPATIBILITY_INVENTORY_PHASE1.md`](../../../design-system/LEGACY_COMPATIBILITY_INVENTORY_PHASE1.md)
- Optional follow-up (non-blocking): [`docs/design-system/PHASE_6_1_PUBLIC_SHELL_FOLLOWUP.md`](../../../design-system/PHASE_6_1_PUBLIC_SHELL_FOLLOWUP.md)

## Approved exceptions (remain)

- Public shell templates: `landing.html`, `legal_front_door.html`,
  `base_fullscreen.html`, `registration/**`, `404` / `403` / `500`
- Landing `lp-btn-*` family and legal-document typography
- Global `.btn-*` / `.badge-*` CSS definitions until public migration
- Route-private builder step chrome (`dpa-step-*`, pickers)
- Command Center expressive hero / score / stage-risk chips

## Validation and rollback

Build CSS from `theme/static_src`, run design-system and UI suites, run
visual baselines with `--update-snapshots=none`, and treat unexplained
screenshot drift as a failing gate. Intentional baseline replacement requires
an explicit, reviewed local update — never CI auto-regeneration.
