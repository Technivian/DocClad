# Engineering Contract

## Current Runtime

DocClad is server-rendered Django with Tailwind CSS v4, semantic CSS tokens,
and CSP-safe vanilla JavaScript. Casefile is framework-independent, but its
current production adapters must remain native to this architecture.

Do not introduce React solely to consume shadcn/ui, Recharts, cmdk, Sonner, or
Motion. If a React migration is approved later, these tools may implement the
same Casefile contracts without changing product semantics.

## File Ownership

- Tokens: `theme/static/css/docclad-tokens.css`
- Adapter tokens: `theme/static_src/src/design-system/tokens.css`
- Components: `theme/static_src/src/design-system/components.css`
- Django primitives: `theme/templates/design_system/`
- Interaction runtime: `theme/static/js/docclad-ui.js`
- Living catalogue: `theme/templates/design_system/catalog.html`
- Enforcement: `tests/test_design_system.py`

## CSS Rules

- Use semantic custom properties, not page-local hex values.
- Shared classes use the `dc-ds-` prefix.
- Page CSS may compose layout but may not redefine primitive anatomy.
- Support 1536px desktop and 390px mobile without horizontal page overflow.
- Respect reduced motion and visible focus.

## JavaScript Rules

- No inline event handlers; Content Security Policy remains enforceable.
- Shared behavior uses `data-*` contracts and delegated listeners.
- Expose only the minimal stable global API under `window.DocClad`.
- Commands and links must be permission-derived from server-rendered context.
- Transient UI must restore focus and provide accessible announcements.

## Component Adoption

Casefile is the default for every public and authenticated screen. Existing
page classes remain compatibility adapters only; they may not introduce new
tokens, icon paths, toast systems, or primitive anatomy. Material page changes
must remove the relevant compatibility layer and use `dc-ds-*` directly.

## External Libraries

- Lucide: approved icon grammar; centralize paths/components.
- TanStack Table Core: approved only when a table owns complex data state in
  the browser. Current repository and queues retain API-owned sorting,
  filtering, and pagination through the shared `data-table-core="server"`
  contract; do not duplicate that state client-side.
- Motion: defer unless CSS/Web Animations cannot express the required behavior.
- Chart libraries: must consume `DocClad.chartTheme`. No chart dependency ships
  until a production chart exists.
- shadcn/ui: reference for composition and accessibility, not a runtime
  dependency in Django templates.
