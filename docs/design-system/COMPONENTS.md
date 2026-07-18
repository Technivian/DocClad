# Components

Shared Django components live in `theme/templates/design_system/`. Their CSS
API is prefixed `dc-ds-`. Product pages may compose these components but must
not fork their anatomy.

## Required Primitives

| Primitive | Template | Contract |
|---|---|---|
| Button | `button.html` | Primary, secondary, ghost, danger; optional Lucide icon |
| Icon | `icon.html` | Approved central Lucide path set |
| Status badge | `status_badge.html` | Neutral, success, progress, attention, danger, special |
| Surface | `surface_card.html` | Header, metadata slot, unframed body |
| Metric | `metric_card.html` | Label, comparable value, supporting note |
| Form field | `form_field.html` | Label, control, help, error |
| Empty state | `empty_state.html` | Clear condition and one recovery path |
| Attention banner | `attention_banner.html` | Status message, not decoration |
| Data table | `.dc-ds-table` | Semantic table markup and horizontal containment |
| Table toolbar | `.dc-ds-table-toolbar` | Flat filter, sort, and action controls above a table |
| Table selection | `.dc-ds-table-selection` | Announced selected-row actions; selection remains native checkbox behavior |
| Table pagination | `.dc-ds-table-pagination` | Result count and labelled previous/next controls |
| Table state | `.dc-ds-table-state` | Loading, empty, or recoverable-error content inside table geometry |
| Timeline | `audit_timeline_item.html` | Actor/event/time sequence |
| Command palette | `command_palette.html` | Keyboard and search navigation |
| Toast region | `toast_region.html` | Transient non-blocking feedback |
| Setup action | `setup_action.html` | One linked activation step with icon, explanation, and direction |
| Authentication shell | `.dc-ds-auth-*` | One brand mark, contextual enterprise message, canonical form and provider actions |

## Buttons

- One primary action per action group.
- Primary buttons use forest and an action verb.
- Secondary buttons retain a border and white surface.
- Ghost buttons are for tertiary navigation, not primary completion.
- Danger buttons require destructive meaning and confirmation where loss is
  nontrivial.
- Icon-only buttons require an accessible label and tooltip.
- Disabled actions must explain the unmet condition nearby.

## Authentication

Use the `dc-ds-auth-*` composition for sign-in and closely related enterprise
access screens. Keep one brand mark, one primary credential action, canonical
form controls, and secondary provider actions. Render recognizable provider
marks through `provider_icon.html`; do not embed or omit them at the page level.
Context copy should explain
legal operations, governance, security, or access—not unrelated product
modules. On compact screens the context panel is removed while the same form,
validation, routes, and trust message remain available.

## Status Badges

Badges describe state, never commands. Use concise nouns or past participles:
`Draft`, `Legal review`, `Waiting`, `Approved`, `Blocked`, `Signed`.

## Cards And Rows

Cards frame one coherent tool, record, or repeated item. Sections are not
cards by default. Rows inside a card use hairline separators and stable columns.
Do not place a card inside another card.

Shared surface modifiers:

- `dc-ds-surface--expressive`: spacious dashboard or context card.
- `dc-ds-surface--feature`: the single branded feature surface on a page.
- `dc-ds-surface--feature-clear`: all-clear feature treatment.
- `dc-ds-surface--soft`: unframed setup or grouped-control surface.
- `dc-ds-surface--interactive`: hover/focus elevation for linked surfaces.

Metric cards use `dc-ds-metric--expressive` in spacious dashboards and
`dc-ds-metric__value--clear` only when a queue is explicitly clear. Setup rows
use `setup_action.html`; do not fork their icon/copy/arrow anatomy.

## Tables

- Left-align text; right-align numeric and monetary values.
- Put every standard table in `.dc-ds-table-wrap`; it owns the 390px
  horizontal-overflow contract. Give `.dc-ds-table` a real `caption` and use
  `scope="col"` on column headers.
- Use `.dc-ds-table-toolbar` with the shared `filter_search_bar.html` partial
  for flat server-owned filters. Use `.dc-ds-table-selection` only when a
  native checkbox selection model is available.
- Use `.dc-ds-table-state` with `role="status"` for asynchronous loading.
  Recoverable errors and no-result conditions use `empty_state.html` within a
  spanning table cell, preserving the table's column geometry.
- Use sticky headers only inside an explicit scroll container.
- Sorting, filtering, selection, pagination, and column visibility require
  visible state and accessible names.
- Use TanStack Table Core only for genuinely complex client-side tables. It is
  a behavior engine; Casefile owns the markup and appearance.
- On mobile, preserve comparison through horizontal scrolling or switch to a
  documented record-list pattern. Do not silently hide critical columns.

## Empty States

An empty state must identify whether the condition is initial, filtered, or
permission-based. Initial CLM states prioritize activation; operational states
preserve the normal page structure and explain what will appear.

Use the `activation` tone when the empty state is itself a prominent surface,
and `compact` when it lives inside an existing surface. Both support the shared
icon slot; recovery actions should use setup actions or standard buttons.
