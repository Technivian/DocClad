# Phase 3A: standard lists and tables

Status: complete, pending Phase 3B review.

This record covers only the repository, document, and standard
administration-list migration. It is incremental to Phase 2B.5; dashboard,
workflow, builder, review-studio, scaffold, form/panel, public, and legal
document systems were not changed.

## Canonical API added

| API | Responsibility | Shared owner |
|---|---|---|
| `.dc-ds-table-wrap` | Horizontal containment, including the 390px overflow contract | `components.css` |
| `.dc-ds-table` | Semantic table typography, row focus, numeric alignment, caption | `components.css` |
| `.dc-ds-table-toolbar` | Flat filter/sort/action strip | `components.css` + `filter_search_bar.html` |
| `.dc-ds-table-selection` | Selected-row announcement and bulk-action container | `components.css` |
| `.dc-ds-table-pagination` | Result count and page controls | `components.css` |
| `.dc-ds-table-state` | In-table asynchronous status announcement | `components.css` |

The mobile rule is deliberate containment: at 700px and below, standard
tables retain columns and scroll within `.dc-ds-table-wrap` rather than
silently dropping data. `data-loading="true"` is an implementation hook, not
a visual variant. Server-owned tables retain `data-table-core="server"`.

## Complete family migration and mappings

| Family | Runtime units | Before | After | Compatibility disposition |
|---|---|---|---|---|
| Repository | `repository.html`, `clmone-repository.js` | Existing `dc-ds-table` only; bespoke filter, bulk, pagination, and transient state markup | Canonical toolbar, selection, pagination, loading state, row `aria-selected`, labelled checkboxes/pagination; existing filters/sort/page/bulk requests preserved | `repo-filter-shell`, `repo-bulk-bar`, `repo-mini-btn`, `wq-row-selected`, `tbl-*` remain because they provide live route-specific layout or state behavior. |
| Documents | `document_list.html`, `document_list_filters.html` | Raw form and table; legacy row class | Shared filter partial, filter `<select>`, canonical table/wrap, caption/scopes/numeric cell | Document type query parameter and status adapter unchanged. Badge aliases for privileged/confidential metadata are outside this table phase. |
| Clause-library administration | category and template list templates | Raw tables, local row-hover rules, raw empty states | Canonical table/wrap, caption/scopes/numeric cells, shared empty states, canonical quiet actions | Two local hover overrides removed after the local class consumers reached zero. Global `.tbl-row*` compatibility APIs remain live elsewhere. |
| Approval administration | request list, approval queue partial, rule-table partial | Queue table was already canonical but had incomplete table semantics; rule table was raw | Canonical containment, caption/scopes, and rule-table API | Queue tabs, decisions, permissions, and request state logic unchanged. |

## Automated consumer evidence

Counts are `rg` counts over the seven runtime templates/partials above (tests,
documentation, generated CSS, and out-of-scope routes excluded).

| Item | Before | After | Evidence / disposition |
|---|---:|---:|---|
| Runtime units declaring a canonical table/list API | 2 | 7 | Repository and approval queue were prior adopters; all scoped units now declare a canonical table, wrap, or toolbar API. |
| Standard table containment consumers | 0 | 6 | Repository, documents, clause categories, clause templates, approval requests, and approval rules. |
| Shared filter-toolbar consumers | 0 | 2 | Repository and documents. |
| Scoped raw/local row-class uses (`tbl-row`, `tbl-row-hover`) | 3 | 0 | Zero local runtime consumers verified before the corresponding local overrides were removed. |
| Local legacy hover overrides removed | 0 | 2 | The category and clause-template template-local overrides only; the shared compatibility selector was not deleted. |
| Shared legacy table/repository aliases removed | 0 | 0 | Zero-consumer gate is not met; remaining consumers are listed in the compatibility disposition above. |

The repository-wide check confirms `.tbl-row*` remains in other standard,
dashboard, workflow, and specialist lists, and
`theme/static_src/src/global-shell/legacy-layout.css` still defines the shared
bridge. Those systems are intentionally untouched in this phase.

## Accessibility and behaviour evidence

### Repository recovery snapshot decision

The first no-update replay of the newly introduced Phase 3A repository-error
snapshot reported 525 changed pixels (0.01%). This is an **obsolete
phase-local baseline**, not a product regression and not a change to an
established Phase 1 baseline. Evidence: the expected image includes the
transient `CLMOne.toast()` notification emitted by `showError()`;
`clmone-ui.js` starts its 4.2-second dismissal timer immediately and then
applies a 160ms leaving state. The durable table error panel, table geometry,
and controls were unchanged. The test now asserts the durable error panel and
removes the already-verified transient toast before capture, so the visual
assertion measures the table recovery state rather than animation timing.
The replacement snapshot is generated only after this recorded classification
and must pass a no-update replay.

- Table captions, `scope="col"`, numeric alignment, labelled action columns,
  selection checkbox labels, selected-row ARIA state, `aria-busy`, and a
  polite loading announcement are present in migrated table paths.
- Repository filters, sorting, pagination, selection, bulk status/export,
  drawer actions, data requests, permissions, and existing labels were kept;
  no route or data contract changed.
- `phase-3a-standard-lists.spec.js` covers selection by keyboard, focus,
  loading/error states, pagination controls, document empty state,
  approval-tab focus, desktop, and 390px horizontal overflow. Four new
  snapshots cover material migrated states/archetypes: repository recovery
  error, document empty state, clause-library empty state, and approval
  administration.
- Focused Django suites passed: 148 tests. Hermetic `manage.py check` passed.
  The first non-hermetic check was refused by the remote database guard and
  was not counted as a product failure.
- The targeted Playwright suite passed: 3 tests. Existing baselines were
  replayed; none was regenerated.

## Deferred work

No unresolved business, permission, security, or accessibility decision was
found. Phase 3B consolidates page headers and standard record-list scaffolds.
**Phase 3C** (`PHASE_3C_APP_WIDE_TABLES.md`) closes the remaining primary list,
Workflow Designer, and Command Center table families against the Contracts
Repository contract.
