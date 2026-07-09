# Token Porting Notes

This adapter ports the extracted design-system intent into DocClad's current Django/Tailwind CSS pipeline without replacing existing tokens.

## Token Namespace

All new adapter tokens use `--ds-*`.

Examples:

- `--ds-color-shell`
- `--ds-color-canvas`
- `--ds-color-surface`
- `--ds-color-border`
- `--ds-color-text`
- `--ds-color-trust`
- `--ds-color-action`
- `--ds-color-attention`
- `--ds-color-danger`
- `--ds-space-*`
- `--ds-radius-*`

Reason:

- Existing DocClad pages rely on `--primary`, `--accent`, `--card-bg`, `--border`, `--btn-gradient`, and many page-local values.
- A global token replacement would alter current UI before page migration.

## Color Role Mapping

| Carelane-style role | Django adapter token | DocClad meaning |
|---|---|---|
| App shell | `--ds-color-shell` | deep navy sidebar/shell |
| Canvas | `--ds-color-canvas` | cool off-white workspace |
| Surface | `--ds-color-surface` | white work cards/panels |
| Border | `--ds-color-border` | thin enterprise dividers |
| Primary text | `--ds-color-text` | navy legal-tech text |
| Secondary text | `--ds-color-text-secondary` | operational support copy |
| Trust/validated | `--ds-color-trust` | teal for workflow/trust/compliance |
| Primary action | `--ds-color-action` | burnt orange CTA |
| Attention | `--ds-color-attention` | pending/attention amber |
| Critical | `--ds-color-danger` | blocker/critical rose-red |

## Spacing and Radius

The adapter uses a conservative 4px/8px-compatible spacing scale:

- `--ds-space-1`: 4px
- `--ds-space-2`: 8px
- `--ds-space-3`: 12px
- `--ds-space-4`: 16px
- `--ds-space-5`: 20px
- `--ds-space-6`: 24px
- `--ds-space-8`: 32px
- `--ds-space-10`: 40px

Radius tokens:

- `--ds-radius-sm`: 4px
- `--ds-radius-md`: 6px
- `--ds-radius-lg`: 8px
- `--ds-radius-pill`: 999px

Reason:

- DocClad's visual direction calls for restrained enterprise surfaces and cards at 8px radius or less.

## Tailwind v3/v4 Handling

Current state:

- `theme/static_src` uses Tailwind v4 syntax in `styles.css`.
- `theme/package.json` still references Tailwind v3.

Adapter decision:

- The adapter is plain CSS and does not depend on Tailwind-specific `@apply`, `@theme`, CVA, or JS config.
- It is imported from `theme/static_src/src/styles.css`, which is the active CSS source used by the build command.

Reason:

- Plain CSS avoids coupling this adapter to Tailwind v3/v4 until the project chooses one canonical build root.

## Collision Avoidance

New component classes use `dc-ds-*`.

Avoided names:

- `.button`
- `.btn`
- `.card`
- `.badge`
- `.table`
- `.input`
- `.rail`
- `.toast`
- `.drawer`

Reason:

- Those names already exist or are likely to collide with incoming libraries.

## Generated CSS

Running `cd theme/static_src && npm run build` is expected to update:

- `theme/static/css/dist/styles.css`

This is expected once the adapter CSS is added. The output is generated/minified by the existing pipeline.

## Future Token Work

Before migrating multiple pages:

- Decide whether `--ds-*` becomes the permanent public token namespace.
- Decide whether existing DocClad tokens should map to `--ds-*` or vice versa.
- Add dark-mode token equivalents if migrated pages require dark mode.
- Add an icon token strategy for size/stroke/color.
- Add form-state tokens for focus, invalid, disabled, and readonly states.
