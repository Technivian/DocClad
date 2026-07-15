# Foundations

## Color

Casefile uses semantic roles, never color names in product decisions.

| Role | Token | Use |
|---|---|---|
| Canvas | `--paper` | Application background |
| Surface | `--card` | Working panels and controls |
| Well | `--well` | Grouped controls and quiet bands |
| Cool canvas | `--color-surface-canvas-cool` | Alias for expressive compositions on the canonical application canvas |
| Soft surface | `--color-surface-soft` | Setup actions and low-emphasis grouped controls |
| Text | `--ink-900` | Primary content |
| Secondary text | `--ink-500` | Supporting content |
| Border | `--line` | Structural separation |
| Primary/trust | `--seal` | Primary action, selection, verified state |
| Progress | `--status-progress-*` | Review and active workflow states |
| Attention | `--status-pending-*` | Waiting, renewal, and due-soon states |
| Danger | `--status-danger-*` | Blocking exceptions and destructive actions |
| Special | `--status-special-*` | Specialist or privileged review states |
| Clear | `--color-state-clear*` | Explicitly empty operational queues, always paired with “Clear” text |

Semantic colour follows the Command Center contract: green means monitored and
clear; amber means setup incomplete or not measured; red means genuine risk or
required intervention; blue/teal means neutral category, information, action,
selection, or trust. Never communicate status by color alone; pair color with
text, iconography, or position.

`--ds-*` names are deprecated aliases retained for compatibility. New code
uses the canonical tokens shown above.

## Typography

Use Inter across product UI. Do not introduce Geist unless CLM One adopts a
new frontend runtime and validates the full application again.

| Style | Size / line height | Weight | Use |
|---|---|---|---|
| Display | 28 / 36 | 650 | Page titles and dashboard dates |
| Title | 24 / 32 | 650 | Major page sections |
| Section | 20 / 28 | 650 | Primary panel groups |
| Heading | 16 / 24 | 600 | Card and panel titles |
| Body | 14 / 22 | 400 | Default reading text |
| Small | 13 / 18 | 400 | Supporting and table content |
| Meta | 12 / 16 | 400 | Dates, IDs, and auxiliary labels |
| Eyebrow | 11 / 16 | 600 | Sparse uppercase categorization |

Use tabular numerals for money, percentages, dates, durations, and comparable
metrics. Letter spacing is zero except for uppercase metadata labels.

## Spacing

Casefile uses an 8px structural grid with 4px half-steps for component internals.

- 4: icon and label micro-spacing only.
- 8: inline controls and compact action groups.
- 12/20: component internals where 8 or 16 is optically insufficient.
- 16: compact card padding and list rhythm.
- 24: tablet page margins, panel padding, and dense workspace gutters.
- 32: desktop page margins and major section separation.
- 40/48/56/64+: page-level composition and terminal spacing.

Application pages use the shared frame: `32px` desktop, `24px` tablet and
specialized workspaces, and `16px` mobile. Templates must not set their own
outer page padding.

## Grid

- 12 columns.
- 32px desktop page margin.
- 24px desktop gutter.
- Default operational split: 8 columns main, 4 columns context rail.
- Collapse to one column when the main content can no longer remain useful.
- Mobile page margin: 16px.

## Shape And Elevation

- Controls: 8px radius.
- Primary cards and panels: 14px radius through `--radius-subpanel`.
- Inner action rows and compact nested controls: 10px radius through `--radius-card`.
- Spacious contextual surfaces: 20px radius through `--radius-surface`.
- Branded feature surfaces: 20px radius through `--radius-feature`.
- Pills: status, filters, and people only.
- Working surfaces use subtle borders and `--shadow-card`; clickable cards may
  use `--shadow-card-hover` only on hover.
- Expressive dashboard surfaces may use `--shadow-surface-expressive`; one
  branded feature surface per page may use `--shadow-feature`.
- Nested cards are prohibited. Use bands, dividers, or list rows inside cards.

The expressive palette (`--color-feature-*`, `--gradient-feature*`) establishes
hierarchy; it does not communicate workflow status. Dense forms, tables, and
record cards retain the default compact shape and elevation contract.

## Icons

Lucide is the icon grammar. Icons use a 24px view box, round caps and joins,
and a 2px stroke unless a smaller optical size needs 1.75px. Use familiar icons
without labels only when the meaning is universal; otherwise include text or a
tooltip.
