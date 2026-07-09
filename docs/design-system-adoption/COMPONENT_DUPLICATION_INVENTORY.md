# Component Duplication Inventory

This inventory documents existing repeated UI patterns that should be replaced by shared design-system components during later migration. No replacement was performed in this audit.

## Summary Counts

Approximate occurrences across templates/static source:

- `btn-*`: 372
- `card*`: 344
- `badge*`: 171
- `chip*`: 38
- `table*`: 61
- `tabs*`: 14
- `rail*`: 81
- `arch-*`: 234
- `dc-*`: 152
- `cform-*`: 329
- Inline `style=`: 103

## Button Families

Current families:

- `btn`, `btn-primary`, `btn-secondary`, `btn-danger`
- `btn-primary-grad`
- `btn-soft-primary-primary`
- `btn-quiet`
- `btn-ghost`
- `btn-link`
- `btn-cta`
- page-local button classes such as `msa-rail-btn`

Migration target:

- One canonical button component with `primary`, `secondary`, `ghost`, `danger`, `link`, and `icon` variants.
- Primary CTA should retain DocClad burnt orange usage.
- Teal should remain trust/workflow/active state, not generic primary CTA unless the visual standard changes.

Risk:

- Buttons are used as anchors and submit buttons. Preserve element type, `type`, `name`, `value`, `form`, and route URLs.

## Card and Panel Families

Current families:

- `card`, `card-section`, `card-l1`, `card-l2`
- `kpi-card`
- `summary-card`
- `panel`, `panel-inner`
- `ad-card`
- `dc-card`, `dc-action-card`, `dc-stat-card`
- `cform-intake-panel`, `cform-draft-panel`, `cform-rail-card`
- `cw-table-card`, `cw-rail-card`
- page-local panels in DPA/MSA/NDA and dashboard templates

Migration target:

- `Surface`
- `Panel`
- `RecordCard`
- `MetricTile`
- `CommandPanel`
- `WorkspaceRail`

Risk:

- Some cards contain table wrappers, forms, and JavaScript-targeted IDs. Replace wrapper classes only after verifying layout and JS hooks.

## Badge and Chip Families

Current families:

- `badge`
- `badge-sm`
- `badge-green`, `badge-blue`, `badge-yellow`, `badge-red`, `badge-gray`, `badge-purple`
- `status-badge`, `status-active`, `status-draft`, `status-inactive`, `status-unverified`
- `arch-chip`
- `dc-badge`, `dc-status`, `dc-risk-chip`
- `cform-risk-chip`
- DPA owner chips and approval/severity badges

Migration target:

- `StatusBadge`
- `RiskBadge`
- `SeverityBadge`
- `ApprovalBadge`
- `FilterChip`
- `SourceBadge`

Risk:

- Colors currently encode business semantics. Map every old status class to the new semantic variant before replacement.

## Table and Queue Families

Current families:

- Tailwind utility tables in legacy templates.
- `table-base`, `table-head`, `table-row`, `table-container`
- `dc-work-table`
- `cw-table`
- component partials:
  - `_work_queue_table.html`
  - `_approval_queue_table.html`
  - `_obligations_matrix_table.html`
  - `_task_queue_table.html`

Migration target:

- `DataTable`
- `WorkQueueTable`
- `ApprovalQueue`
- `EmptyTableState`
- shared filter/search/sort bar

Risk:

- Tables often include query-string filters, pagination links, and row-level action links. Keep href/query params intact.

## Header Families

Current families:

- `page-header`
- `arch-header`
- `dc-page-head`
- `cw-header`
- cockpit-specific headers: `msa-page-head`, `nda-page-head`, `dpa` variants
- settings/auth headers

Migration target:

- `PageHeader`
- `WorkspaceHeader`
- `CommandHeader`
- `FormHeader`

Risk:

- Some headers include primary form submit buttons outside visible form sections. Preserve form association and button types.

## Rail Families

Current families:

- `arch-context-rail`
- `cw-rail`
- dashboard right rail
- DPA/MSA/NDA governance rails
- workflow detail side panels

Migration target:

- `SupportRail`
- `GovernanceRail`
- `ActionRail`
- `AuditRail`

Risk:

- Rails often contain dynamic risk, approval, audit, and route information. Do not treat them as static decoration.

## Tabs, Filters, Search

Current families:

- `top-tabs`, `top-tab`, `top-tab-active`
- `tabs-shell`
- `dc-filter-tabs`, `dc-filter-button`
- contract workspace tabs and chips
- search/filter forms in list pages

Migration target:

- `Tabs`
- `FilterTabs`
- `SearchBar`
- `SavedViewTabs`
- `SortControl`

Risk:

- Many filter controls are plain links or GET forms. Preserve query-string behavior.

## Form Sections

Current families:

- Django form rendering in CRUD templates.
- `cform-*` cockpit forms.
- `arch-*` readiness and missing-field patterns.
- `input` utility and local input styling.

Migration target:

- `FormSection`
- `FieldRow`
- `Input`
- `Select`
- `Textarea`
- `CheckboxCard`
- `ValidationMessage`
- `ReadinessPanel`

Risk:

- Existing form field names are backend contracts. Do not rename or wrap in a way that breaks submission.

## Modal, Drawer, Toast

Current families:

- `.modal-overlay` in `workflow_detail.html`
- `.drawer-*`, `.toast-*` in `components.css`
- page-specific modal behavior where present

Migration target:

- `Dialog`
- `Drawer`
- `Toast`

Risk:

- There is no Radix/shadcn stack yet. If the incoming system is React/Radix-based, server-rendered Django pages need an adapter or static fallback.

## Icon Patterns

Current state:

- Inline SVGs in templates.
- No `lucide-react` or `react-icons` dependency in app packages.
- Icon size/stroke is not centralized.

Migration target:

- One icon strategy for Django templates: inline include, sprite, or static icon partials.
- Do not assume React icon components can render in Django templates without a frontend runtime.
