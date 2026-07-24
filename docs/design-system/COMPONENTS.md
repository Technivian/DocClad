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

- Standard operational tables use this semantic column order when the fields
  are relevant: **Record → context/type → stage/status → owner → due/key date
  → activity/value → actions**. Keep the primary record visible first; do not
  add placeholder columns solely to satisfy the sequence.
- Approved surface exceptions are deliberate: **My Work** keeps `Priority`
  first because it is a personal action queue; **Legal Intelligence** keeps
  `Severity` first because urgency is the primary decision signal; and the
  **Contracts Repository** keeps its leading native selection checkbox because
  it has implemented bulk actions. Do not add row-selection checkboxes to
  tables without a supported bulk action and backend API.
- Repository-like page tabs must be alternate views of the same object set.
  They should not duplicate sidebar destinations or mix personal queues with
  inventory views.
- Use precise labels when the data supports them, such as `Next key date`,
  `Assigned on`, or `Last updated`, instead of generic date headers.
- Left-align text; right-align numeric and monetary values.
- Authenticated tables use the compact density by default: `8px 12px` cell
  padding, vertically centered content, and content-led rows that normally land
  near the 44px compact-row target. Use a documented relaxed mode only when a
  row's content genuinely needs more space.
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
- Rows provide shared hover and keyboard-focus feedback. Only rows with a real
  destination or action use the pointer cursor; navigable rows must also expose
  an equivalent keyboard interaction.
- Use TanStack Table Core only for genuinely complex client-side tables. It is
  a behavior engine; Casefile owns the markup and appearance.
- On mobile, preserve comparison through horizontal scrolling or switch to a
  documented record-list pattern. Do not silently hide critical columns.

### Legacy table migration follow-up

The following user-facing templates still contain legacy table markup and are
not part of the shared-table normalization. Migrate them as a dedicated,
behavior-preserving follow-up rather than folding them into operational table
work: `audit_log_list.html`, `budget_detail.html`, `budget_list.html`,
`client_list.html`, `compliance_checklist_list.html`, `conflict_check_list.html`,
`contract_list.html`, `counterparty_list.html`, `data_inventory_list.html`,
`document_compare.html`, `document_ocr_queue.html`, `dpa_playbook_list.html`,
`dsar_list.html`, `ethical_wall_list.html`, `identity_telemetry_recovery_body.html`,
`invoice_list.html`, `legal_hold_list.html`, `matter_list.html`,
`privacy_dashboard.html`, `retention_policy_list.html`, `risk_log_list.html`,
`signature_request_list.html`, `subprocessor_list.html`, `time_entry_list.html`,
`trademark_request_list.html`, `transfer_record_list.html`,
`trust_account_list.html`, and `workflow_template_detail.html`. Design-system
examples and preview templates are likewise excluded from product migration.

## Empty States

An empty state must identify whether the condition is initial, filtered, or
permission-based. Initial CLM states prioritize activation; operational states
preserve the normal page structure and explain what will appear.

Use the `activation` tone when the empty state is itself a prominent surface,
and `compact` when it lives inside an existing surface. Both support the shared
icon slot; recovery actions should use setup actions or standard buttons.
