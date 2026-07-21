> **SUPERSEDED (2026-07-19).** This is the historical Phase 1 compatibility
> inventory retained for audit trail. The authoritative post–Phase 6 inventory
> is [`LEGACY_COMPATIBILITY_INVENTORY.md`](LEGACY_COMPATIBILITY_INVENTORY.md).
> Phase 6 evidence: [`PHASE_6_LEGACY_RETIREMENT.md`](PHASE_6_LEGACY_RETIREMENT.md).
> ADR/PDR: [`docs/governance/decisions/adr/0008-frontend-design-system-phase-1.md`](../governance/decisions/adr/0008-frontend-design-system-phase-1.md).

# Legacy compatibility inventory (Phase 1 — superseded)

Phase 1 retains every entry below. They are compatibility APIs, not approved
targets for new authenticated-app work. The complete token-alias mapping is
kept beside canonical replacements in
`theme/static/css/clmone-tokens.css`.

## Deprecated token aliases

`--ds-color-shell`, `--ds-color-shell-border`, `--ds-color-canvas`,
`--ds-color-surface`, `--ds-color-surface-muted`,
`--ds-color-surface-raised`, `--ds-color-border`,
`--ds-color-border-strong`, `--ds-color-text`,
`--ds-color-text-secondary`, `--ds-color-text-muted`, `--ds-color-trust`,
`--ds-color-trust-hover`, `--ds-color-trust-soft`, `--ds-color-action`,
`--ds-color-action-hover`, `--ds-color-action-soft`, `--ds-color-progress`,
`--ds-color-progress-soft`, `--ds-color-attention`,
`--ds-color-attention-soft`, `--ds-color-danger`, `--ds-color-danger-soft`,
`--ds-color-special`, `--ds-color-special-soft`, `--ds-color-success`,
`--ds-color-success-soft`, `--ds-font-sans`, `--ds-font-serif`,
`--ds-text-xs`, `--ds-text-sm`, `--ds-text-md`, `--ds-text-lg`,
`--ds-text-xl`, `--ds-text-title`, `--ds-line-tight`, `--ds-line-base`,
`--ds-space-1`, `--ds-space-2`, `--ds-space-3`, `--ds-space-4`,
`--ds-space-5`, `--ds-space-6`, `--ds-space-8`, `--ds-space-10`,
`--ds-space-16`, `--ds-space-20`, `--ds-space-24`, `--ds-space-30`,
`--ds-grid-columns`, `--ds-grid-margin`, `--ds-grid-gutter`,
`--ds-radius-sm`, `--ds-radius-md`, `--ds-radius-lg`, `--ds-radius-pill`,
`--ds-shadow-hairline`, `--ds-focus-ring`, `--ds-motion-fast`,
`--ds-motion-base`, `--ds-motion-slow`, `--ds-ease-standard`,
`--ds-chart-1`, `--ds-chart-2`, `--ds-chart-3`, `--ds-chart-4`,
`--ds-chart-5`, `--ds-chart-grid`, `--ds-chart-axis`, `--ds-page-max`,
`--ds-page-x`, `--ds-page-top`, `--ds-page-bottom`, `--ds-control-height`,
`--ds-surface-shadow`, and `--ds-surface-shadow-hover`.

## Legacy selector families

| Family | Current owner | Consumer scope | Phase 2 disposition |
|---|---|---|---|
| `.btn*`, `.btn-cta`, `.btn-quiet`, `.btn-primary-grad` | `components.css`, shell compatibility CSS, local templates | authenticated app | Map to `.dc-ds-button`; do not delete in Phase 1. |
| `.card*`, `.panel*`, `.kpi-*`, `.summary-*`, `.stat*` | `components.css`, compatibility CSS | dashboards, records, settings | Map to `.dc-ds-surface`/metric primitives. |
| `.table*`, `.wq-*`, `.cw-*` | components, partials, list templates | repository and queues | Map to `.dc-ds-table` and work rows. |
| `.badge-*`, `.status-*`, `.chip-*` | components, shell compatibility CSS | all authenticated routes | Map to `.dc-ds-badge` and `.dc-ds-choice`. |
| `.input`, `.form-*`, bare controls | components, compatibility CSS, local forms | forms and builders | Map to Casefile form-field/control contracts. |
| `.arch-*` | `components.css` | list/detail/workspace archetypes | Replace by scaffold, hero, rail, actions, and choice primitives. |
| `.cform-*`, `.dpa-*`, `.nda-*`, `.msa-*`, `.crs-*` | workflow/review templates | specialised routes | Keep route-scoped until a dedicated migration. |
| `.cc-v3-*` | `command-center.css`, dashboard only | dashboard | Keep private; promote only reusable decisions. |
| `.lp-*` and legal document typography | landing/legal templates | public and document rendering | Explicitly separate from authenticated-app migration. |

## Removal gate

Before deleting a selector or alias, run a repository-wide consumer search,
record zero consumers in the migration PR, and include visual coverage for
each prior route family. Phase 1 performs none of these removals.
