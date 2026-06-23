# Phase 1 — Foundation refactor (design-system/phase1-foundation)

Goal: establish canonical component authority for form controls, retire the
hardcoded `!important` blanket overrides that defeated them, and make dev CSS
rebuilds reliably visible. Sequenced so each step is safe.

## Changes
### 1. All form widgets → canonical `.form-control` (forms.py)
`TAILWIND_INPUT/SELECT/TEXTAREA/CHECKBOX/FILE` (382 usages) were hardcoded
light-mode utility strings (`border-gray-300`, `bg-white`) that only looked
correct because of `!important` blanket overrides. They are now **aliases** of
the canonical classes:
- `TAILWIND_INPUT/SELECT/TEXTAREA → FORM_CONTROL ('form-control')`
- `TAILWIND_CHECKBOX → FORM_CHECK ('form-check-input')`
- `TAILWIND_FILE → FORM_FILE ('form-file')`

One 6-line change migrated every form in the app to token-backed styling.
Verified: Contract Create form (16/16 inputs on `.form-control`, never touched
directly) renders uniformly and **adapts to light theme** — which the old
dark-only blanket could not do.

### 2. Retired the `!important` blanket input overrides (base.html)
`[data-theme="dark"] input/select/textarea { ...#hex... !important }` became a
**token-backed, non-`!important` fallback** that excludes `.form-control` /
`.form-check-input`:
- canonical component classes now fully own their appearance;
- bare/hand-written inputs still theme dark via the fallback (its attribute+
  element+`:not()` specificity beats utility classes, so `!important` is no
  longer needed);
- uses `var(--input-bg/--border/--primary)` instead of hardcoded hex.

The fallback is transitional — it shrinks to nothing as the remaining ~77
hand-written template inputs migrate to `.form-control` (Phase 2).

### 3. Dev CSS cache-busting (context_processors.py + base templates)
Production already hashes filenames via `CompressedManifestStaticFilesStorage`;
dev used plain storage, so rebuilt CSS was served stale. Added an
`asset_version` context processor (mtime of the built stylesheet, DEBUG-only)
and `?v={{ ASSET_VERSION }}` on the stylesheet links in `base.html` and
`base_fullscreen.html`. Returns '' in prod (no redundant query).

## Verification
- 92 automated tests pass: form validation, redesign components/layout, UI
  click integrity, bolton redesign, contract required fields, MFA policy/
  fail-closed, onboarding, organization invitations.
- Manual: Contract Create (dark + light), Profile (slice), Settings hub,
  Contracts list (bare search inputs) — all consistent, no console errors.
- `manage.py check` clean.

## Known follow-ups (Phase 2)
- Migrate ~77 hand-written template `<input>/<select>/<textarea>` to
  `.form-control`, then delete the transitional fallback block entirely.
- Rename the `TAILWIND_*` aliases to `FORM_*` at the ~380 call sites (mechanical).
- Light-theme input border resolves to the dark `--border` token in some spots —
  investigate token cascade in `[data-theme="light"]` (cosmetic, dark-first app).
- Retire remaining `!important` blanket rules for tables/badges similarly.
