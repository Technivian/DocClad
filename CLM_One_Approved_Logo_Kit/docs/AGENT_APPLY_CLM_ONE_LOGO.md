# Agent Task: Apply the Approved CLM One Logo

Use the supplied files in this package. Do not redraw, reinterpret, trace, typeset, or regenerate the logo.

## Exact approved master

The approved visual source is:

`source/clm-one-approved-master.png`

The code-ready primary files are:

- `logo/clm-one-logo-transparent.webp`
- `logo/clm-one-logo-transparent.png`
- `logo/clm-one-logo-exact.svg`
- `mark/clm-one-mark-transparent.webp`
- `mark/clm-one-mark-transparent.png`
- `mark/clm-one-mark-exact.svg`
- `icons/favicon.ico`
- `icons/favicon-16x16.png`
- `icons/favicon-32x32.png`
- `icons/apple-touch-icon.png`
- `icons/android-chrome-192x192.png`
- `icons/android-chrome-512x512.png`
- `site.webmanifest`
- `clm-one-brand.css`

The SVG files intentionally embed the exact approved raster artwork. They are supplied for convenient SVG integration without approximating the approved symbol or wordmark. Do not edit their internal image data.

## Naming

Customer-facing name: `CLM One`

Use `CLMOne` only where spaces are technically impossible.

Remove customer-facing references to:

- DocClad
- Docclad
- docclad
- ModuClad
- Moduclad
- moduclad

Do not blindly rename immutable migrations, database history, deployed infrastructure identifiers, or compatibility-sensitive APIs. Report every preserved legacy occurrence.

## Asset installation

Copy the approved assets to one canonical location, preferably:

`static/brand/`

Do not copy separate logo files into feature-specific folders.

Recommended mappings:

- Expanded app shell and login:
  `clm-one-logo-transparent.webp`
- PNG fallback and documents:
  `clm-one-logo-transparent.png`
- Collapsed sidebar and mobile:
  `clm-one-mark-transparent.webp`
- Favicon:
  `favicon.ico`
- Apple icon:
  `apple-touch-icon.png`
- PWA icons:
  `android-chrome-192x192.png`
  `android-chrome-512x512.png`

## Strict visual rules

- Preserve the original aspect ratio.
- Never rebuild the wordmark with HTML text.
- Never recreate the C1 symbol with CSS or an icon library.
- Never recolor, stretch, crop, rotate, skew, outline, or add shadows.
- Do not add a gradient.
- Do not put the logo inside a pill unless the existing product shell requires a neutral container.
- Use the full logo only where enough horizontal space exists.
- Use the mark for collapsed and mobile navigation.
- Do not mix old and new branding.

## Suggested rendered sizes

- Desktop shell full logo: 24–30 px high
- Authentication page: 36–44 px high
- Mobile or collapsed mark: 24–30 px square
- Generated document header: 40–52 px high

Use CSS height with `width: auto`.

## Accessibility

- A single informative logo uses `alt="CLM One"`.
- A duplicate decorative logo uses `alt=""` and `aria-hidden="true"`.
- Keep keyboard focus styling on the parent link.
- Verify no clipping or overflow at 390 px viewport width.

## Required repository audit

Before editing, locate:

- Existing logo files
- Favicon and manifest
- Header and sidebar templates/components
- Login and onboarding
- Email templates
- PDF and document templates
- Browser titles and metadata
- Help/about pages
- Empty and error states
- Active documentation
- Tests and snapshots containing legacy branding

## Verification

Run the normal repository checks and additionally verify:

1. Expanded desktop shell
2. Collapsed desktop shell
3. 390 px mobile viewport
4. Authentication page
5. Favicon and browser title
6. Generated document or PDF header if present
7. Email branding if present
8. No unexplained customer-facing legacy names remain
9. No horizontal overflow
10. No blurry upscaling beyond the supplied master dimensions
11. No old/new brand mixture

## Final report

Report:

- Files changed
- Canonical asset location
- Surfaces migrated
- Legacy references preserved and why
- Tests and builds run
- Visual checks performed
- Remaining risks
- Commit hash if committed
