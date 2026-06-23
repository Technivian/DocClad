# Vertical Slice Findings — /profile/ canonicalization

Date: 2026-06-23. Verdict: **approach holds — proceed to phased rollout, with two plan amendments.**

## What was changed (minimal, isolated)
1. `theme/static_src/src/components.css` — **additive only**: added canonical
   `.btn-soft-accent`, `.form-control`, `.form-check-input` (themed checkbox via
   `appearance:none`), `.form-file`. No existing selector modified.
2. `contracts/forms.py` — `UserProfileForm` widgets now use `FORM_CONTROL` /
   `FORM_CHECK` constants instead of the hardcoded light-mode `TAILWIND_*` strings.
   Shared `TAILWIND_*` constants left intact so other forms are untouched.
3. `theme/templates/profile.html` — deleted page-local `.btn-primary/.btn-secondary/
   .btn-green` redefinitions; buttons now use canonical `.btn-cta / .btn-quiet /
   .btn-soft-accent`.
4. `theme/templates/base.html` — narrowed the `!important` blanket
   `[data-theme="dark"] input` rule to exclude `checkbox/radio/.form-check-input`.

## Result (verified in browser, dark theme)
- Buttons now have one coherent hierarchy: solid-blue primary (Save), gray ghost
  (Send), green soft-accent (Generate). Previously four unrelated styles.
- All form inputs render uniformly from `.form-control`.
- MFA checkbox renders as a proper blue checkbox with white check — the white-box
  bug from the baseline is gone.
- 14 form/UI/redesign tests pass; no console errors; settings page (regression
  spot-check) unchanged.

## Two findings that AMEND the rollout plan
### A. The real root cause is deeper than "tokens live in base.html"
`base.html` carries `!important` blanket element rules:
`[data-theme="dark"] input, select, textarea { background-color:#0B0F19 !important; ... }`
These **forcibly defeat any canonical component class** (the checkbox `:checked`
state could not turn blue until the blanket rule was narrowed). Implication:
**Phase 1 must retire these `!important` blanket element overrides**, not merely
relocate token definitions. Forms currently look dark only because of these
blanket overrides — which is also why the hardcoded `bg-white` in `TAILWIND_*`
never visibly mattered.

### B. `dist/styles.css` has no cache-busting → stale CSS
The served stylesheet URL is unversioned, so browsers (and the preview) serve a
stale cached `styles.css` after every rebuild. This will bite the rollout: visual
changes won't appear without a hard refresh. Fix before the sweep: enable
`ManifestStaticFilesStorage` (hashed filenames) or append a build-version query.

## Process lesson
Verifying CSS by hot-swapping `<link>` tags in the live page produced false
artifacts (a transient white-card render on /settings/). Reliable verification =
rebuild → restart server → fresh navigation, accepting one manual hard-refresh.
