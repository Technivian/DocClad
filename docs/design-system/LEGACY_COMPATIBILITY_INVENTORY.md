# Legacy compatibility inventory (Phase 6 — current)

Status: **Authoritative** for the authenticated app as of 2026-07-19.

Phase 6 retires authenticated-app `btn-*` / `badge-*` dual classes. Entries
below are **approved exceptions** or **retired-but-defined** CSS adapters.
New authenticated work must use `.dc-ds-*` only.

Historical Phase 1 inventory (superseded, retained):
[`LEGACY_COMPATIBILITY_INVENTORY_PHASE1.md`](LEGACY_COMPATIBILITY_INVENTORY_PHASE1.md).

Phase 6 evidence: [`PHASE_6_LEGACY_RETIREMENT.md`](PHASE_6_LEGACY_RETIREMENT.md).  
ADR/PDR 0008: [`docs/governance/decisions/adr/0008-frontend-design-system-phase-1.md`](../governance/decisions/adr/0008-frontend-design-system-phase-1.md).  
Optional non-blocking follow-up: [`PHASE_6_1_PUBLIC_SHELL_FOLLOWUP.md`](PHASE_6_1_PUBLIC_SHELL_FOLLOWUP.md).

## Approved template exceptions (may still use legacy classes)

- `theme/templates/landing.html` (uses `lp-btn-*`, not legacy `btn-*`)
- `theme/templates/legal_front_door.html`
- `theme/templates/base_fullscreen.html`
- `theme/templates/registration/**`
- `theme/templates/404.html`, `403.html`, `500.html`

## Deprecated token aliases

Unchanged from Phase 1 — see `theme/static/css/clmone-tokens.css` for the
`--ds-*` compatibility map (includes `--ds-color-shell` and peers). Do not
introduce new `--ds-*` consumers. Prefer `--seal` / `--ink-*` / `--dc-ds-*`.

## Legacy selector families (disposition)

| Family | Disposition (Phase 6) |
|---|---|
| `.btn*`, `.btn-cta`, `.btn-quiet`, `.btn-primary-grad` | CSS retained for public exceptions; **zero authenticated class consumers** |
| `.badge-*` | CSS retained for public exceptions; **zero authenticated class consumers** |
| `.card*`, `.panel*`, `.kpi-*`, … | Map incrementally to `.dc-ds-surface` / metric; not blocking Phase 6 |
| `.table*`, `.wq-*`, `.cw-*` | List scaffolds may retain domain structure; controls are `.dc-ds-*` |
| `.cform-*`, `.dpa-step-*`, builder pickers | Route-scoped unique chrome OK |
| `.cc-v3-*` | Private to Command Center; expressive hero preserved; **zero-consumer orphans purged** |
| `.lp-*` / legal document typography | Explicitly out of authenticated migration |

## Removal gate (still required for global CSS aliases)

Before deleting a CSS alias definition:

1. Repository-wide consumer search including public exceptions reaches zero, **or**
2. Public shell is migrated in optional Phase 6.1.
3. Record evidence in the PR; update visual baselines only via explicit,
   reviewed local regeneration (`PLAYWRIGHT_UPDATE_SNAPSHOTS=1`) — never in CI.

## Enforcement

- `scripts/check_design_system_drift.sh`
- `scripts/check_design_system_contrast.sh`
- `scripts/check_visual_baselines.sh` (`--update-snapshots=none`)
- `.github/workflows/design-system-guardrails.yml`
- `.github/workflows/visual-regression.yml`
- Foundation gate: `test_phase_six_authenticated_templates_have_no_btn_badge_dual_classes`
