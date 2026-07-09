# Dependency and Tooling Checklist

This checklist records current dependencies and gaps before introducing a reusable design system under `src/design-system`.

## Current Package Areas

### `client/package.json`

Purpose appears to be Playwright/E2E support, not product UI.

Installed:

- `@playwright/test`
- `vite`
- low-level Vite/Rollup/PostCSS dependencies

Missing for a React design-system runtime:

- `react`
- `react-dom`
- `typescript`
- `@types/react`
- `@types/react-dom`
- `lucide-react`
- `class-variance-authority`
- `clsx`
- `tailwind-merge`
- `@radix-ui/*`
- `react-hook-form`
- `zod`
- routing/runtime integration

### `theme/static_src/package.json`

Purpose is canonical CSS build for Django templates.

Installed:

- Tailwind `^4.1.11`
- `@tailwindcss/postcss`
- `postcss`
- `postcss-cli`
- `postcss-nested`
- `postcss-simple-vars`
- `autoprefixer`
- `cross-env`
- `rimraf`

Notes:

- This package is closest to the current product CSS pipeline.
- It is not a React component build pipeline.

### `theme/package.json`

Purpose appears older/duplicated.

Installed:

- Tailwind `^3.3.6`
- PostCSS CLI
- Autoprefixer
- Cross-env
- Rimraf

Risk:

- Tailwind version mismatch with `theme/static_src/package.json`.
- Both packages define similar build scripts targeting `../static/css/dist/styles.css`.

## Tailwind Readiness

Status: not ready for blind transplant.

Checklist:

- [ ] Decide Tailwind v3 vs v4 as canonical.
- [ ] Decide whether incoming design system requires `tailwind.config.ts`, CSS `@theme`, or JS config.
- [ ] Ensure content scanning includes Django templates and any future `src/design-system` files.
- [ ] Decide whether design-system utilities should be emitted globally or only under a namespace.
- [ ] Verify generated CSS size after adding the design system.

## Radix / shadcn Readiness

Status: not currently installed.

Checklist:

- [ ] Confirm whether the extracted design system depends on React and Radix.
- [ ] If yes, decide whether DocClad will add a React island/runtime or port components to Django templates.
- [ ] Confirm CSP compatibility for portals, overlays, focus guards, and inline style injection.
- [ ] Define server-rendered fallbacks for menus, dialogs, tabs, accordions, popovers.

## CVA / Class Utility Readiness

Status: not currently installed.

Potential dependencies:

- `class-variance-authority`
- `clsx`
- `tailwind-merge`

Checklist:

- [ ] Install only when a JS/TS component build exists.
- [ ] If staying in Django templates, create variant class maps as template includes or CSS classes instead.

## Icons

Status: current app mostly uses inline SVGs.

Gaps:

- `lucide-react` not installed.
- `react-icons` not installed.
- No shared Django icon include/sprite identified.

Checklist:

- [ ] Choose icon strategy before migration.
- [ ] If no React runtime is adopted, do not use `lucide-react` directly in templates.
- [ ] Prefer a static SVG include/sprite or a small Django template icon library.

## Routing

Status: Django server-rendered routes.

Checklist:

- [ ] Do not introduce client-side routing for existing product pages.
- [ ] Preserve Django route names and `{% url %}` calls.
- [ ] Keep POST targets and redirects unchanged.

## Forms

Status: Django forms and server validation.

Missing for React forms:

- `react-hook-form`
- `zod`

Checklist:

- [ ] Do not introduce client-side form state for existing forms during visual migration.
- [ ] Preserve `name`, `id`, `data-*`, `method`, `action`, and CSRF.
- [ ] Keep Django validation messages server-rendered unless explicitly approved.

## Verification Commands

Current reliable commands:

- `make check`
- `DJANGO_SETTINGS_MODULE=config.settings_test .venv/bin/python manage.py test <module>`
- `cd theme/static_src && npm run build`
- `cd client && npm run test:e2e -- <spec>` for targeted Playwright smoke

Not reliable as product UI checks:

- `client npm test` currently exits with `Error: no test specified`.

## Verification Findings From This Audit

- `make check` passed with `config.settings_test`.
- `cd theme/static_src && npm run build` completed successfully.
- The CSS build emitted an existing Node warning: `MODULE_TYPELESS_PACKAGE_JSON` for `theme/static_src/postcss.config.js`. The package uses ES module syntax but `theme/static_src/package.json` does not declare `"type": "module"`.
- The CSS build rewrites `theme/static/css/dist/styles.css` into a minified generated artifact. That file should not be included in audit-only commits unless the task explicitly asks for a built asset refresh.

## Blockers Before Transplant

- Tailwind version split must be resolved or explicitly isolated.
- Need a decision on React runtime vs Django-template adaptation.
- Need namespacing strategy for design-system CSS.
- Need token ownership decision between `base.html`, `base_fullscreen.html`, and `theme/static_src/src`.
- Need icon strategy.
- Need a component demo/sandbox before applying to real pages.
