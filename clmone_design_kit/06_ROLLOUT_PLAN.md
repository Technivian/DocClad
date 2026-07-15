# Rollout Plan

## Phase 1 — Foundation

1. Add design tokens.
2. Create or refactor shared shell components.
3. Create reusable card, button, input, chip, table, and workflow rail components.
4. Add visual regression-friendly examples if Storybook or similar exists.

Do not redesign every page directly first. That creates drift.

## Phase 2 — Canonical Screens

Redesign these first:

1. New Contract Request
2. Dashboard
3. Contract Workspace
4. Repository

These establish the full design language: intake form, dashboard/work queue, operational table, repository table.

## Phase 3 — Workflow Screens

Redesign:

1. Tasks
2. Workflows
3. Approvals
4. Signature Requests

## Phase 4 — Governance Screens

Redesign:

1. Risk Register
2. Compliance
3. Privacy
4. DPA Reviews
5. Audit Trail

## Phase 5 — Reference Screens

Redesign:

1. Documents
2. Any settings/help/reference modules

## Phase 6 — QA and Hardening

Review each page against:

- visual hierarchy
- spacing
- shell consistency
- action clarity
- accessibility
- keyboard states
- responsive behavior
- empty states
- loading states
- error states
- terminology consistency

## Suggested branch naming

```text
feature/clmone-premium-design-system
```

## Suggested commit structure

1. `style: add CLM One design tokens`
2. `feat(ui): add premium CLM shell components`
3. `feat(contracts): redesign new contract request`
4. `feat(dashboard): redesign legal operations dashboard`
5. `feat(workspace): redesign contract workspace and repository`
6. `feat(governance): redesign risk compliance privacy audit pages`
7. `test(ui): update visual and accessibility coverage`
