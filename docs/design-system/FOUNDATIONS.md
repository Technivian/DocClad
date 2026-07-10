# Foundations

## Color

Casefile uses semantic roles, never color names in product decisions.

| Role | Token | Use |
|---|---|---|
| Canvas | `--paper`, `--ds-color-canvas` | Application background |
| Surface | `--card`, `--ds-color-surface` | Working panels and controls |
| Well | `--well`, `--ds-color-surface-muted` | Grouped controls and quiet bands |
| Text | `--ink-900`, `--ds-color-text` | Primary content |
| Secondary text | `--ink-500`, `--ds-color-text-secondary` | Supporting content |
| Border | `--line`, `--ds-color-border` | Structural separation |
| Primary/trust | `--seal`, `--ds-color-trust` | Primary action, selection, verified state |
| Progress | `--status-progress-*` | Review and active workflow states |
| Attention | `--status-pending-*` | Waiting, renewal, and due-soon states |
| Danger | `--status-danger-*` | Blocking exceptions and destructive actions |
| Special | `--status-special-*` | Specialist or privileged review states |

Forest is not decoration. It means action, selection, progress, or trust.
Amber and red require a real operational reason. Never communicate status by
color alone; pair color with text, iconography, or position.

## Typography

Use Inter across product UI. Do not introduce Geist unless DocClad adopts a
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
- Cards and panels: 10px radius.
- Pills: status, filters, and people only.
- Working surfaces use borders first and restrained shadows second.
- Nested cards are prohibited. Use bands, dividers, or list rows inside cards.

## Icons

Lucide is the icon grammar. Icons use a 24px view box, round caps and joins,
and a 2px stroke unless a smaller optical size needs 1.75px. Use familiar icons
without labels only when the meaning is universal; otherwise include text or a
tooltip.
