# Phase 6.1 (optional): public-shell migration and global alias deletion

Status: **Optional / non-blocking.** Does not gate the authenticated-app
release completed under ADR/PDR 0008 Phase 6 (2026-07-19).

## Goal

Migrate public and registration shells onto canonical `.dc-ds-*` controls,
then delete global `.btn-*` / `.badge-*` CSS alias definitions once a
repository-wide consumer search is clean.

## In scope

- `landing.html` / `lp-btn-*` → Casefile button API (or retain a documented
  public-only `lp-*` system that does not depend on authenticated `.btn-*`)
- `legal_front_door.html`, `base_fullscreen.html`, `registration/**`,
  error pages (`404` / `403` / `500`)
- Remove standalone `.btn-cta`, `.btn-quiet`, `.btn-primary-grad`,
  `.badge-sm`, `.badge-{green,blue,…}` definitions from `static_src` after
  zero consumers (including public exceptions)
- Optional: move `command-center.css` into `theme/static_src` with a dedicated
  build target (no visual redesign)

## Out of scope

- Authenticated-app dual-class retirement (done in Phase 6)
- Legal-document typography systems
- Redesign of landing marketing composition

## Exit criteria

1. Zero `btn-*` / `badge-*` class consumers repository-wide (or only
   documented `lp-*` public primitives).
2. Global alias CSS deleted; drift check updated.
3. Visual baselines for public routes updated via explicit local regeneration
   and reviewed PR — never CI auto-regen.
4. ADR/PDR 0008 amended with Phase 6.1 effective date.

## Related

- [`PHASE_6_LEGACY_RETIREMENT.md`](PHASE_6_LEGACY_RETIREMENT.md)
- [`LEGACY_COMPATIBILITY_INVENTORY.md`](LEGACY_COMPATIBILITY_INVENTORY.md)
- [`docs/governance/decisions/adr/0008-frontend-design-system-phase-1.md`](../governance/decisions/adr/0008-frontend-design-system-phase-1.md)
