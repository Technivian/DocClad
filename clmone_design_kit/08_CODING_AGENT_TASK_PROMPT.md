# Coding Agent Task Prompt

You are implementing the CLM One premium CLM design system.

Read all files in:

```text
/docs/design-system/clmone-premium-clm/
```

Then perform the redesign in this order:

1. Inventory existing pages, routes, shared layout components, styles, tokens, and UI primitives.
2. Identify current duplicate one-off components and style drift.
3. Add/align design tokens from `02_DESIGN_TOKENS.css` or the Tailwind snippet.
4. Build reusable components from `04_COMPONENT_SPECS.md`.
5. Redesign `New Contract Request` and `Dashboard` first as canonical examples.
6. Use those examples to redesign the remaining pages listed in `05_PAGE_BLUEPRINTS.md`.
7. Do not add decorative analytics, gradients, or new domain concepts not supported by the app.
8. Preserve existing functionality, routes, permissions, forms, and tests unless a change is explicitly required.
9. Add/adjust tests only where needed to reflect UI changes.
10. Run typecheck, lint, unit tests, and relevant e2e tests.

For every redesigned page, verify:

- same shell
- same spacing logic
- same color discipline
- clear page header
- main work object is dominant
- right rail only when useful
- primary action uses burnt orange
- active/workflow/compliance states use teal
- no generic dashboard-template styling

Deliverables:

- list of files changed
- before/after summary per page
- verification commands and results
- any known limitations or follow-up work
