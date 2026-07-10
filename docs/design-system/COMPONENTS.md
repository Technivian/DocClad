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
| Timeline | `audit_timeline_item.html` | Actor/event/time sequence |
| Command palette | `command_palette.html` | Keyboard and search navigation |
| Toast region | `toast_region.html` | Transient non-blocking feedback |

## Buttons

- One primary action per action group.
- Primary buttons use forest and an action verb.
- Secondary buttons retain a border and white surface.
- Ghost buttons are for tertiary navigation, not primary completion.
- Danger buttons require destructive meaning and confirmation where loss is
  nontrivial.
- Icon-only buttons require an accessible label and tooltip.
- Disabled actions must explain the unmet condition nearby.

## Status Badges

Badges describe state, never commands. Use concise nouns or past participles:
`Draft`, `Legal review`, `Waiting`, `Approved`, `Blocked`, `Signed`.

## Cards And Rows

Cards frame one coherent tool, record, or repeated item. Sections are not
cards by default. Rows inside a card use hairline separators and stable columns.
Do not place a card inside another card.

## Tables

- Left-align text; right-align numeric and monetary values.
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
