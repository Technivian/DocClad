# Phase 3B: standard record-list headers and page scaffolds

Status: complete, pending Phase 4 review.

This record is incremental to Phase 3A. It covers only repository, document,
clause-library, and approval-administration record-list shells. The tables,
filters, route data, permissions, and all out-of-scope systems remain as they
were.

## Canonical contract and family adoption

| API | Responsibility | Scoped consumers after |
|---|---|---:|
| `.dc-ds-list-page` | Standard wide page container and vertical flow for an operational list | 6 |
| `.dc-ds-list-header` | Canvas action row; the authenticated shell owns the visible title, subtitle, and labelled back control | 5 |
| `.dc-ds-list-tabs` | Tabs beneath the shell context, wrapping/scrolling safely on compact widths | 2 |
| `.dc-ds-list-toolbar` | Flat repository filter/action toolbar | 1 |
| `page_scaffold.html` `flow` + `scaffold_class_name` | Shared page-flow composition without leaking a caller's generic class into nested partials | 1 shared caller |

The repository family retains its existing shell context and uses the list
markers for its toolbar and tabs. Documents, clause categories, clause
templates, and approval requests replace their local legacy page headers with
the canonical action header. Approval rules use the shared scaffold and page
hero. No route changes, labels, permissions, filter parameters, sort state,
pagination, bulk actions, or table markup changed.

The authenticated shell continues to provide title/subtitle/back navigation.
The canvas hides the duplicate context while retaining the action row. Thus
the title hierarchy is not rendered twice and a page with no subtitle remains
valid through the optional `page_hero.html` subtitle block.

## Consumer and compatibility evidence

Counts were generated with `rg` over the seven scoped runtime templates and
partials; tests, documentation, and generated CSS are excluded.

| Item | Before | After | Result |
|---|---:|---:|---|
| Scoped runtime templates using `.dc-ds-list-page` | 0 | 6 | Complete scoped family adoption; approval-rule content is reached via the shared scaffold call. |
| Scoped runtime templates using `.dc-ds-list-header` | 0 | 5 | Repository has shell context and a toolbar/tabs rather than a duplicate canvas header. |
| Scoped runtime templates using `.dc-ds-list-tabs` | 0 | 2 | Repository and approval queue. |
| Legacy header/scaffold runtime template consumers | 4 | 0 | Document, clause category, clause template, and approval request families reached the zero-consumer gate. |
| Legacy header/scaffold selector occurrences in those families | 16 | 0 | Includes `page-wrap`, `page-header`, `page-title`, `arch-header`, and `arch-title`. |
| Shared legacy header/scaffold runtime templates outside scope | 113 | 113 | Compatibility APIs remain; the repository-wide zero-consumer gate is not met. |

The local `.approvals-header-row` rule was removed after an all-runtime
search returned zero consumers. No shared `page-wrap`, `page-header`, or
`arch-header` selector was removed because their 113 out-of-scope runtime
consumers remain. The direct filter-to-table rule records the prior compact
list rhythm using shared spacing tokens; it has one runtime consumer and is
not a template-local exception.

## Visual baseline decision

No baseline was regenerated. The first Phase 3A replay found the documents
table 16px lower after the new page-flow gap. The header, actions, filter,
and table semantics were otherwise unchanged. The shared direct
filter-to-table rhythm rule restores the established geometry. A no-update
replay then reduced the difference to 84 pixels, matching the existing
repository and clause-list replays.

The remaining 84 pixels are confined to anti-aliasing on the sidebar Admin
glyph; they are outside every migrated page canvas and were present in the
same location before the document geometry correction. This is an existing
renderer-level baseline variance, not a product regression or an approved
baseline replacement. The snapshots remain unchanged. The Phase 3B browser
suite exercises the migrated desktop and 390px structures directly; no new
snapshot was added because the existing Phase 3A baselines already cover the
same list archetypes and no new visual state was introduced.

## Validation

- `npm --prefix theme/static_src run build:tailwind`: passed; generated CSS
  came only from the Tailwind v4 build.
- `phase-3b-list-scaffolds.spec.js`: 3 passing tests. It covers shell title,
  labelled back focus, tabs, action hierarchy, long action label, approval
  routes, desktop, and 390px containment.
- Focused Django suite: 149 passing tests, including scaffold contract,
  repository behaviour, approvals, and tenant isolation. `manage.py check`
  passed. `git diff --check` passed.
- Phase 3A baseline replay: canvas geometry restored; retained 84-pixel
  sidebar glyph variance above; no baseline updated.

## Deferred work

No business, permission, security, or accessibility decision is unresolved.
Phase 4 should separately scope dashboards and complex workspaces, starting
with dashboard page scaffolds and headers; their widgets and data-density
rules must not be folded into this standard-list contract.
