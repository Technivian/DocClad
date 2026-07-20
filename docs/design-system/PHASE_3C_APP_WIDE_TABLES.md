# Phase 3C: app-wide table standardization

Status: complete.

Closes the Phase 3A deferred work for remaining primary list/admin tables,
Workflow Designer workspace tables, and the Command Center Recent Matters
queue. **Contracts Repository remains the source of truth** for the table
contract; Repository-only features (selection, bulk, columns menu, sticky
columns, JS-rendered rows) are not copied onto simpler lists.

## Canonical contract (unchanged)

| API | Responsibility |
|---|---|
| `.dc-ds-table-wrap` | Horizontal containment |
| `.dc-ds-table` | Typography, hover, numeric alignment, caption |
| `<caption class="sr-only">` | Accessible table name |
| `scope="col"` | Column header semantics |
| `data-col="actions"` + `wq-kebab` | Row actions overlay |
| In-cell `empty_state.html` | Empty/filtered/permission states inside the table |
| `[data-numeric]` | Numeric/monetary alignment |

## Families migrated in this phase

| Family | Runtime units | Before | After |
|---|---|---|---|
| Workflow Designer | `workflow_template_detail.html` Versions + Activity | `.wf-table` / `.wf-table-wrap` | `.dc-ds-table` + wrap; Activity filters keep local form chrome with `dc-ds-table-toolbar` rhythm class |
| Core entity lists | matter, client, counterparty, contract work list, deadline | `w-full` / `cw-table` / `tbl-row` | Canonical wrap/table/caption/empty |
| Finance / ops lists | budget, invoice, time, trust, signature, risk, audit + budget detail expenses | `w-full` / `tbl-row` | Canonical |
| Privacy / compliance | conflict, ethical wall, compliance, retention, subprocessor, transfer, inventory, DSAR, legal hold, DPA playbook, trademark, OCR queue, privacy dashboard embeds | `w-full` / `tbl-row` | Canonical |
| Command Center | `dashboard.html` Recent Matters | `.cc-v3-table` | `.dc-ds-table` inside CC card; CC row content classes retained; CSS retargeted |
| Nested tooling | document compare diffs, identity recovery telemetry | raw `w-full` | Canonical |

## Explicit non-goals

- No selection/bulk/columns menu on lists that never had them.
- No change to Repository itself.
- Design-preview templates remain out of scope.
- Shared `.tbl-row*` bridge CSS may remain in legacy-layout for zero-consumer cleanup later; runtime templates no longer use those classes on migrated tables.

## Evidence

- Consumer assertions extended in `tests/test_design_system_phase2a.py`.
- Playwright visual baseline mask updated from `.cc-v3-table` to `.cc-v3-matters .dc-ds-table`.
