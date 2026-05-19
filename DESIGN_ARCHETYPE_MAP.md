# DESIGN ARCHETYPE MAP

Date: 2026-05-18
Pass type: Classification and planning only (no template migrations)
Source of truth: DESIGN_CONSTITUTION.md + DESIGN_ARCHETYPE_PATTERNS.md

## Scope and Method

- Scanned all HTML templates under theme/templates/**/*.html.
- Classified each template into current and recommended archetype with confidence, drift notes, migration priority/risk, and dependencies.
- Parsed named non-API routes from contracts/urls.py and config/urls.py and assigned recommended archetypes for planning.
- This pass does not modify runtime templates or behavior.

## Totals

- Templates scanned: 123
- UI routes classified: 190

### Count Per Recommended Archetype

- QueuePage: 28
- WorkspacePage: 20
- CommandPage: 32
- NetworkPage: 16
- ExceptionPage: 19
- Unknown / Needs decision: 8

## Top 10 Highest-Priority Migration Candidates

|Template|Recommended archetype|Priority|Risk|Why now|
|---|---|---|---|---|
|theme/templates/contracts/repository.html|WorkspacePage|Critical|Medium|Has custom helper classes and mixed list/table treatments|
|theme/templates/contracts/workflow_dashboard.html|WorkspacePage|Critical|Medium|Mixed table/filter idioms vs canonical wrappers|
|theme/templates/dashboard.html|WorkspacePage|Critical|Medium|Legacy mixed utility patterns in sections; needs stricter workspace panel rhythm|
|theme/templates/contracts/_task_card.html|WorkspacePage|High|Medium|Component-level variant drift possible|
|theme/templates/contracts/budget_detail.html|WorkspacePage|High|Medium|Panel density and secondary actions vary|
|theme/templates/contracts/clause_template_detail.html|WorkspacePage|High|Medium|Panel density and secondary actions vary|
|theme/templates/contracts/client_detail.html|NetworkPage|High|Medium|Link-density and identity columns vary|
|theme/templates/contracts/client_form.html|NetworkPage|High|Medium|Link-density and identity columns vary|
|theme/templates/contracts/client_list.html|NetworkPage|High|Medium|Link-density and identity columns vary|
|theme/templates/contracts/contract_detail.html|WorkspacePage|High|Medium|Panel density and secondary actions vary|

## Unknown / Needs Decision

|Template|Current archetype|Confidence|Decision needed|
|---|---|---|---|
|theme/templates/base.html|Unknown / Needs decision|High|Shell consolidation and token boundary decisions required|
|theme/templates/base_fullscreen.html|Unknown / Needs decision|High|Shell unification plan and auth/public constraints|
|theme/templates/base_redesign.html|Unknown / Needs decision|High|Decision: adopt, archive, or remove|
|theme/templates/components_demo.html|Unknown / Needs decision|High|Use for examples only after canonical update|
|theme/templates/landing.html|Unknown / Needs decision|Low|Decision needed: keep separate public archetype or align to fullscreen standard|
|theme/templates/layout_toggle.html|Unknown / Needs decision|Medium|No migration needed unless retained in workflow|
|theme/templates/patterns/archetype_wrappers_examples.html|Unknown / Needs decision|High|Keep in sync with archetype source of truth|
|theme/templates/styleguide.html|Unknown / Needs decision|High|Keep synced with canonical primitives|

## Recommended Batch 3 Scope (Pattern-First)

Recommended target set (high-impact mixed-surface pages):

- theme/templates/dashboard.html
- theme/templates/contracts/workflow_dashboard.html
- theme/templates/contracts/repository.html
- theme/templates/contracts/privacy_dashboard.html
- theme/templates/contracts/operations_dashboard.html
- theme/templates/contracts/legal_task_board.html
- theme/templates/contracts/deadline_list.html
- theme/templates/contracts/notification_list.html

Batch 3 rationale:

- Concentrates on high-traffic dashboards/workspaces where drift is most visible.
- Clusters WorkspacePage + ExceptionPage pages to reduce context switching and enforce archetype discipline.
- Keeps risk medium by avoiding shell/auth migration in the same batch.

Batch 3 prerequisites before any edits:

- Confirm shell strategy decisions for base.html and base_fullscreen.html remain out of scope for this batch.
- Lock shared WorkspacePage and ExceptionPage wrappers/checklist for header/filter/table/state parity.
- Validate no route/view behavior changes are required; template-only normalization.

## Complete Template Classification Matrix

|Template|Current archetype|Recommended archetype|Confidence|Classification reason|Current drift issues|Migration priority|Migration risk|Dependencies before migration|
|---|---|---|---|---|---|---|---|---|
|theme/templates/base.html|Unknown / Needs decision|Unknown / Needs decision|High|Application shell, not a page archetype|Contains broad utility compatibility layer and duplicated concerns|Critical|High|Shell consolidation and token boundary decisions required|
|theme/templates/base_fullscreen.html|Unknown / Needs decision|Unknown / Needs decision|High|Fullscreen shell for auth/public surfaces, not page archetype|Second styling stack causes drift risk|Critical|High|Shell unification plan and auth/public constraints|
|theme/templates/base_redesign.html|Unknown / Needs decision|Unknown / Needs decision|High|Experimental shell bridge not active archetype page|Not adopted and can drift from base shell|Medium|Low|Decision: adopt, archive, or remove|
|theme/templates/components_demo.html|Unknown / Needs decision|Unknown / Needs decision|High|Demo/reference artifact, not operational page|Contains legacy samples that can mislead implementation|Low|Low|Use for examples only after canonical update|
|theme/templates/contracts/_task_card.html|Unknown / Needs decision|WorkspacePage|Medium|Partial component used inside workspace board contexts|Component-level variant drift possible|High|Medium|Migrate hosting workspace first then component|
|theme/templates/contracts/approval_request_form.html|CommandPage|CommandPage|High|Input/action-driven page with form-first flow|Field spacing and button variants may drift|Medium|**MIGRATED** Batch 6 Step 6|Full WorkspacePage migration; page-wrap/header; panel+panel-inner space-y-4; form-label/c-muted/c-danger; btn-primary-grad/btn-ghost; enctype preserved; field.id_for_label + field.errors|join preserved|
|theme/templates/contracts/approval_request_list.html|QueuePage|QueuePage|Medium|Record-oriented page with list/table/filter behavior|Mixed utility and canonical primitives may coexist|Medium|**MIGRATED** Batch 6 Step 6|Full WorkspacePage migration; page-wrap/header/title/subtitle/page-actions; panel table; tbl-head/tbl-th/tbl-row/tbl-td; badge-sm (green/yellow/red/blue) for approval status; c-muted on assignee/delegated/created; btn-ghost Edit; empty-state; aria-hidden SVG|
|theme/templates/contracts/approval_rule_form.html|CommandPage|CommandPage|High|Input/action-driven page with form-first flow|Field spacing and button variants may drift|Medium|**MIGRATED** Batch 6 Step 6|Full WorkspacePage migration; same form pattern as approval_request_form; enctype/field.id_for_label/errors|join preserved|
|theme/templates/contracts/approval_rule_list.html|QueuePage|QueuePage|Medium|Record-oriented page with list/table/filter behavior|Mixed utility and canonical primitives may coexist|Medium|**MIGRATED** Batch 6 Step 6|Full WorkspacePage migration; page-wrap/header/actions; panel table; tbl-head/tbl-th/tbl-row/tbl-td; badge-sm badge-green/c-muted for active; c-muted on trigger_value/sla_hours; btn-ghost Edit; empty-state; aria-hidden SVG|
|theme/templates/contracts/audit_log_list.html|ExceptionPage|ExceptionPage|High|Audit stream is operational exception/compliance evidence feed|Legacy gray table stack on some rows|High|Low|Canonical queue table wrappers and severity chips|
|theme/templates/contracts/budget_detail.html|WorkspacePage|WorkspacePage|Medium|Context-rich page combining panels/details/actions|Panel density and secondary actions vary|High|**MIGRATED** Batch 6 Step 7|Full WorkspacePage migration; page-wrap/header/title/subtitle/page-actions; 3-col panel panel-inner KPI cards (Allocated/Spent/Remaining); c-warning for Spent; c-success/c-danger conditional for Remaining; panel+panel-head+tbl-head/tbl-th/tbl-row/tbl-td for Expenses table; empty-state; btn-primary-grad Add Expense; btn-ghost Edit; budget.total_spent/budget.remaining/expense.get_category_display/expense.amount|floatformat:2 preserved|
|theme/templates/contracts/budget_form.html|CommandPage|CommandPage|High|Input/action-driven page with form-first flow|Field spacing and button variants may drift|Medium|**MIGRATED** Batch 6 Step 7|Full WorkspacePage migration; page-wrap/header/title; max-w-2xl; panel+panel-inner; form-label/c-danger; btn-primary-grad/btn-ghost; non-field errors + per-field error display added; {% block page_title %} removed (non-standard); btn-outline→btn-ghost; btn-primary→btn-primary-grad text-white|
|theme/templates/contracts/budget_list.html|QueuePage|QueuePage|Medium|Record-oriented page with list/table/filter behavior|Mixed utility and canonical primitives may coexist|Medium|**MIGRATED** Batch 6 Step 7|Partial migration (already mostly canonical); stat-card KPI cards→panel panel-inner; panel overflow-hidden stat-card→panel; c-red→c-danger on over-budget remaining; aria-hidden on Add SVG; btn-ghost px-3 py-1 on View row action|
|theme/templates/contracts/checklist_item_form.html|CommandPage|CommandPage|High|Input/action-driven page with form-first flow|Field spacing and button variants may drift|Medium|Low|Canonical form-field and command header primitives|
|theme/templates/contracts/clause_category_form.html|CommandPage|CommandPage|High|Input/action-driven page with form-first flow|Field spacing and button variants may drift|Medium|**MIGRATED** Batch 6 Step 8|Full CommandPage migration; page-wrap/header/title; max-w-3xl; panel+panel-inner; form-label/c-muted/c-danger; btn-primary-grad text-white/btn-ghost; {% for field in form %} loop preserved; enctype preserved; cancel→clause_category_list|
|theme/templates/contracts/clause_category_list.html|QueuePage|QueuePage|Medium|Record-oriented page with list/table/filter behavior|Mixed utility and canonical primitives may coexist|Medium|**MIGRATED** Batch 6 Step 8|Full QueuePage migration; page-wrap/page-header/page-title/page-subtitle; panel/tbl-head/tbl-th/tbl-row/tbl-td; btn-primary-grad text-white; btn-ghost row edit; aria-hidden SVG; empty-state|
|theme/templates/contracts/clause_library.html|QueuePage|QueuePage|Medium|Record-oriented page with list/table/filter behavior|Mixed utility and canonical primitives may coexist|Medium|**MIGRATED** Batch 6 Step 8|Shell-only migration (JS prototype page); page-wrap/page-header/page-title; c-muted subtitle; btn-primary-grad text-white; panel panel-inner for search bar; panel for list; empty-state; modal form-label/btn-primary-grad; ALL JS logic preserved intact; text-primary-*/bg-primary-* inside JS template literals kept; structural exception: hover:text-gray-600 on modal close|
|theme/templates/contracts/clause_template_compare.html|QueuePage|QueuePage|Medium|Record-oriented page with list/table/filter behavior|Mixed utility and canonical primitives may coexist|Medium|**MIGRATED** Batch 6 Step 10|Full QueuePage migration; page-wrap; mb-6 header block (c-link back, page-title, page-subtitle); 3 panel+panel-inner blocks for left/right versions and field diffs; variant diffs list; <pre> blocks preserved as structural exception; c-muted for metadata; h2 → text-sm font-semibold|
|theme/templates/contracts/clause_template_detail.html|WorkspacePage|WorkspacePage|Medium|Context-rich page combining panels/details/actions|Panel density and secondary actions vary|High|**MIGRATED** Batch 6 Step 8|Full WorkspacePage migration; page-wrap/page-header; max-w-3xl inner wrapper; space-y-6; panel+panel-inner for all 8 sections; panel-title for section headings; form-label/c-muted/c-danger; btn-primary-grad text-white; c-link; 2 inline POST forms (variant_create/playbook_create) preserved with csrf_token/action URLs/field names; non_field_errors added to both forms; <pre> blocks preserved exactly for clause/fallback content; version history blue highlight kept as structural exception; amber policy_issues panel kept as structural exception; resolved_variant/variants/playbooks panels migrated|
|theme/templates/contracts/clause_template_form.html|CommandPage|CommandPage|High|Input/action-driven page with form-first flow|Field spacing and button variants may drift|Medium|**MIGRATED** Batch 6 Step 8|Full CommandPage migration; page-wrap/header/title; max-w-3xl; panel+panel-inner; form-label/c-muted/c-danger; btn-primary-grad text-white/btn-ghost; {% for field in form %} loop preserved; enctype preserved; cancel→clause_template_list|
|theme/templates/contracts/clause_template_list.html|QueuePage|QueuePage|Medium|Record-oriented page with list/table/filter behavior|Mixed utility and canonical primitives may coexist|Medium|**MIGRATED** Batch 6 Step 8|Full QueuePage migration; page-wrap/page-header/page-title/page-subtitle; panel/tbl-head/tbl-th/tbl-row/tbl-td; badge-sm badge-green/badge-yellow for is_approved; c-danger/c-muted for is_mandatory; c-link for title; btn-primary-grad text-white; btn-ghost row edit; empty-state|
|theme/templates/contracts/client_detail.html|NetworkPage|NetworkPage|Medium|Relationship/entity network view across linked records|Link-density and identity columns vary|High|**MIGRATED** Batch 6 Step 2|Full WorkspacePage migration; panel/panel-head/badge-sm/c-muted/c-link; hover:bg-gray-50 kept as structural UX exception on link rows|
|theme/templates/contracts/client_form.html|NetworkPage|NetworkPage|Medium|Relationship/entity network view across linked records|Link-density and identity columns vary|High|**MIGRATED** Batch 6 Step 2|Full WorkspacePage migration; panel/panel-inner/form-label/btn-primary-grad/btn-ghost; max-w-3xl + grid kept as structural exceptions|
|theme/templates/contracts/client_list.html|NetworkPage|NetworkPage|Medium|Relationship/entity network view across linked records|Link-density and identity columns vary|High|**MIGRATED** Batch 6 Step 2|Minimal changes: aria-hidden on decorative SVG; removed redundant overflow-hidden stat-card from panel wrapper|
|theme/templates/contracts/compliance_checklist_detail.html|ExceptionPage|ExceptionPage|Medium|Exception/compliance/alert oriented operational flow|Severity/status emphasis inconsistent|High|**TARGETED FIX Batch 6 Step 11** — btn-primary→btn-primary-grad text-white; full structural migration deferred|Exception severity badge + queue conventions|
|theme/templates/contracts/compliance_checklist_form.html|ExceptionPage|ExceptionPage|Medium|Exception/compliance/alert oriented operational flow|Severity/status emphasis inconsistent|High|**TARGETED FIX Batch 6 Step 11** — btn-primary→btn-primary-grad text-white; full structural migration deferred|Exception severity badge + queue conventions|
|theme/templates/contracts/compliance_checklist_list.html|ExceptionPage|ExceptionPage|Medium|Exception/compliance/alert oriented operational flow|Severity/status emphasis inconsistent|High|**TARGETED FIX Batch 6 Step 11** — btn-primary→btn-primary-grad text-white; full structural migration deferred|Exception severity badge + queue conventions|
|theme/templates/contracts/conflict_check_form.html|CommandPage|CommandPage|High|Input/action-driven page with form-first flow|Field spacing and button variants may drift|Medium|**MIGRATED** Batch 6 Step 9|Full CommandPage migration; max-w-2xl; page-wrap/header/title; panel+panel-inner; form-label/c-muted/c-danger; grid grid-cols-1 md:grid-cols-2 gap-4; md:col-span-2 for notes/conflicts_found; non_field_errors added; btn-primary-grad text-white/btn-ghost; Back link; csrf_token preserved; no enctype (no file uploads)|
|theme/templates/contracts/conflict_check_list.html|QueuePage|QueuePage|Medium|Record-oriented page with list/table/filter behavior|Mixed utility and canonical primitives may coexist|Medium|**MIGRATED** Batch 6 Step 9|Full QueuePage migration; page-wrap/page-header/page-title/page-actions; panel; tbl-head/tbl-th/tbl-row/tbl-td; badge-sm badge-green(CLEAR)/badge-red(CONFLICT)/badge-yellow(WAIVED)/badge-gray(else) for status; c-muted on secondary cols; btn-primary-grad text-white; btn-ghost row edit; empty-state; aria-hidden SVG on New Check CTA|
|theme/templates/contracts/contract_detail.html|WorkspacePage|WorkspacePage|Medium|Context-rich page combining panels/details/actions|**MIGRATED — Batch 4 Step 5 Slice B (2026-05-18)**|✅ Done|—|
|theme/templates/contracts/contract_form.html|CommandPage|CommandPage|High|Input/action-driven page with form-first flow|Field spacing and button variants may drift|Medium|Low|Canonical form-field and command header primitives|
|theme/templates/contracts/contract_list.html|QueuePage|QueuePage|Medium|Record-oriented page with list/table/filter behavior|**MIGRATED — Batch 4 Step 4 Slice B (2026-05-18); TARGETED FIX Batch 6 Step 11** — removed redundant stat-card from panel wrapper|✅ Done|—|
|theme/templates/contracts/counterparty_detail.html|NetworkPage|NetworkPage|Medium|Relationship/entity network view across linked records|Link-density and identity columns vary|High|**MIGRATED** Batch 6 Step 3|Full WorkspacePage migration; page-wrap/header/actions; panel+panel-inner; c-muted; btn-primary-grad/btn-ghost; max-w-3xl on detail panel (structural exception)|
|theme/templates/contracts/counterparty_form.html|NetworkPage|NetworkPage|Medium|Relationship/entity network view across linked records|Link-density and identity columns vary|High|**MIGRATED** Batch 6 Step 3|Full WorkspacePage migration; page-wrap/header; panel+panel-inner; form-label/c-muted/c-danger; btn-primary-grad/btn-ghost; max-w-3xl kept; enctype/object|yesno/field.id_for_label preserved|
|theme/templates/contracts/counterparty_list.html|NetworkPage|NetworkPage|Medium|Relationship/entity network view across linked records|Link-density and identity columns vary|High|**MIGRATED** Batch 6 Step 3|Full WorkspacePage migration; page-wrap/header/actions; panel table; tbl-head/tbl-th/tbl-row/tbl-td; badge-sm; c-link; empty-state; hover:bg-gray-50 kept as UX exception|
|theme/templates/contracts/data_inventory_detail.html|WorkspacePage|WorkspacePage|Medium|Context-rich page combining panels/details/actions|Panel density and secondary actions vary|High|Medium|Workspace panel/header conventions and state patterns|
|theme/templates/contracts/data_inventory_form.html|CommandPage|CommandPage|High|Input/action-driven page with form-first flow|Field spacing and button variants may drift|Medium|Low|Canonical form-field and command header primitives|
|theme/templates/contracts/data_inventory_list.html|QueuePage|QueuePage|Medium|Record-oriented page with list/table/filter behavior|Mixed utility and canonical primitives may coexist|Medium|**MIGRATED** Batch 6 Step 10|Full QueuePage migration; page-wrap/page-header/page-title/page-subtitle; panel overflow-hidden; tbl-head/tbl-th/tbl-row/tbl-td; c-link; c-danger/c-muted for 3rd country; c-success/c-warning/c-muted for DPIA; aria-hidden SVG; empty-state|
|theme/templates/contracts/dd_risk_form.html|ExceptionPage|ExceptionPage|Medium|Exception/compliance/alert oriented operational flow|Severity/status emphasis inconsistent|High|Low|Exception severity badge + queue conventions|
|theme/templates/contracts/dd_task_form.html|CommandPage|CommandPage|High|Input/action-driven page with form-first flow|Field spacing and button variants may drift|Medium|Low|Canonical form-field and command header primitives|
|theme/templates/contracts/deadline_form.html|ExceptionPage|ExceptionPage|Medium|Exception/compliance/alert oriented operational flow|Severity/status emphasis inconsistent|High|Low|Exception severity badge + queue conventions|
|theme/templates/contracts/deadline_list.html|ExceptionPage|ExceptionPage|High|Deadline breaches and upcoming due items are exception-oriented queue|**MIGRATED — Batch 3 Slice 1 (2026-05-18)**|✅ Done|—|
|theme/templates/contracts/document_compare.html|QueuePage|QueuePage|Medium|Record-oriented page with list/table/filter behavior|Mixed utility and canonical primitives may coexist|Medium|**MIGRATED** Batch 6 Step 10|Full QueuePage migration; page-wrap/page-header/page-title/page-subtitle; btn-ghost back; panel+panel-inner for side panels; <pre> preserved; field diff: panel overflow-hidden + panel-head/panel-title + tbl-head/tbl-th/tbl-row/tbl-td; c-muted for metadata|
|theme/templates/contracts/document_detail.html|WorkspacePage|WorkspacePage|Medium|Context-rich page combining panels/details/actions|Panel density and secondary actions vary|High|Medium|Workspace panel/header conventions and state patterns|
|theme/templates/contracts/document_form.html|CommandPage|CommandPage|High|Input/action-driven page with form-first flow|Field spacing and button variants may drift|Medium|Low|Canonical form-field and command header primitives|
|theme/templates/contracts/document_list.html|QueuePage|QueuePage|Medium|Record-oriented page with list/table/filter behavior|Mixed utility and canonical primitives may coexist|Medium|**MIGRATED** Batch 6 Step 10|Targeted fix: removed redundant stat-card class from panel wrapper (panel overflow-hidden preserved)|
|theme/templates/contracts/document_ocr_queue.html|ExceptionPage|ExceptionPage|Medium|Exception/compliance/alert oriented operational flow|Severity/status emphasis inconsistent|High|Low|Exception severity badge + queue conventions|
|theme/templates/contracts/document_ocr_review.html|QueuePage|QueuePage|Medium|Record-oriented page with list/table/filter behavior|Mixed utility and canonical primitives may coexist|Medium|**MIGRATED** Batch 6 Step 10|Full QueuePage migration; page-wrap/page-header/page-title/page-subtitle; btn-ghost back; panel+panel-inner for doc info and form; form-label; c-danger for errors; btn-primary-grad text-white submit; btn-ghost cancel; <pre> for extracted_text preserved; csrf_token preserved|
|theme/templates/contracts/dsar_detail.html|ExceptionPage|ExceptionPage|Medium|Exception/compliance/alert oriented operational flow|Severity/status emphasis inconsistent|High|Low|Exception severity badge + queue conventions|
|theme/templates/contracts/dsar_form.html|ExceptionPage|ExceptionPage|Medium|Exception/compliance/alert oriented operational flow|Severity/status emphasis inconsistent|High|Low|Exception severity badge + queue conventions|
|theme/templates/contracts/dsar_list.html|ExceptionPage|ExceptionPage|Medium|Exception/compliance/alert oriented operational flow|Severity/status emphasis inconsistent|High|Low|Exception severity badge + queue conventions|
|theme/templates/contracts/due_diligence_detail.html|WorkspacePage|WorkspacePage|Medium|Context-rich page combining panels/details/actions|Panel density and secondary actions vary|High|Medium|Workspace panel/header conventions and state patterns|
|theme/templates/contracts/due_diligence_form.html|CommandPage|CommandPage|High|Input/action-driven page with form-first flow|Field spacing and button variants may drift|Medium|Low|Canonical form-field and command header primitives|
|theme/templates/contracts/due_diligence_list.html|QueuePage|QueuePage|Medium|Record-oriented page with list/table/filter behavior|Mixed utility and canonical primitives may coexist|Medium|**MIGRATED** Batch 6 Step 10|Targeted fix: removed redundant stat-card class from panel wrapper; page-wrap/page-header/page-title/page-subtitle/page-actions/panel/badge-sm/empty-state/list-row/c-muted already canonical|
|theme/templates/contracts/ethical_wall_form.html|CommandPage|CommandPage|High|Input/action-driven page with form-first flow|Field spacing and button variants may drift|Medium|Low|Canonical form-field and command header primitives|
|theme/templates/contracts/ethical_wall_list.html|QueuePage|QueuePage|Medium|Record-oriented page with list/table/filter behavior|Mixed utility and canonical primitives may coexist|Medium|**MIGRATED** Batch 6 Step 10|Full QueuePage migration; page-wrap/page-header/page-title/page-subtitle; panel overflow-hidden; tbl-head/tbl-th/tbl-row/tbl-td; badge-sm badge-red (Active)/badge-gray (Inactive); c-link; aria-hidden SVG; c-muted empty row|
|theme/templates/contracts/expense_form.html|CommandPage|CommandPage|High|Input/action-driven page with form-first flow|Field spacing and button variants may drift|Medium|Low|Canonical form-field and command header primitives|
|theme/templates/contracts/identity_telemetry_dashboard.html|WorkspacePage|WorkspacePage|Medium|Context-rich page combining panels/details/actions|**MIGRATED — Batch 4 Step 2 Slice A (2026-05-18)**|✅ Done|—|
|theme/templates/contracts/invoice_detail.html|WorkspacePage|WorkspacePage|Medium|Context-rich page combining panels/details/actions|**MIGRATED — Batch 5 Step 2 (2026-05-18)**|✅ Done|—|
|theme/templates/contracts/invoice_form.html|CommandPage|CommandPage|High|Input/action-driven page with form-first flow|**MIGRATED — Batch 5 Step 2 (2026-05-18)**|✅ Done|—|
|theme/templates/contracts/invoice_list.html|QueuePage|QueuePage|Medium|Record-oriented page with list/table/filter behavior|**MIGRATED — Batch 5 Step 2 (2026-05-18)**|✅ Done|—|
|theme/templates/contracts/legal_hold_detail.html|ExceptionPage|ExceptionPage|Medium|Exception/compliance/alert oriented operational flow|Severity/status emphasis inconsistent|High|Low|Exception severity badge + queue conventions|
|theme/templates/contracts/legal_hold_form.html|ExceptionPage|ExceptionPage|Medium|Exception/compliance/alert oriented operational flow|Severity/status emphasis inconsistent|High|Low|Exception severity badge + queue conventions|
|theme/templates/contracts/legal_hold_list.html|ExceptionPage|ExceptionPage|Medium|Exception/compliance/alert oriented operational flow|Severity/status emphasis inconsistent|High|Low|Exception severity badge + queue conventions|
|theme/templates/contracts/legal_task_board.html|WorkspacePage|WorkspacePage|High|Kanban-like operational workspace rather than pure queue|**MIGRATED — Batch 3 Slice 2 Step 4 (2026-05-18)**|✅ Done|—|
|theme/templates/contracts/legal_task_form.html|CommandPage|CommandPage|High|Input/action-driven page with form-first flow|Field spacing and button variants may drift|Medium|**TARGETED FIX Batch 6 Step 11** — btn-primary→btn-primary-grad text-white; full structural migration deferred|Canonical form-field and command header primitives|
|theme/templates/contracts/matter_detail.html|NetworkPage|NetworkPage|Medium|Relationship/entity network view across linked records|Link-density and identity columns vary|High|**MIGRATED** Batch 6 Step 4|Full WorkspacePage migration; page-wrap/header/actions; panel+panel-inner for Details/Team/Billing/Case Info; panel+panel-head for Time Entries/Deadlines; badge-sm (green/yellow/gray/red/blue); c-muted/c-danger; btn-primary-grad/btn-ghost; empty-state|
|theme/templates/contracts/matter_form.html|NetworkPage|NetworkPage|Medium|Relationship/entity network view across linked records|Link-density and identity columns vary|High|**MIGRATED** Batch 6 Step 4|Full WorkspacePage migration; page-wrap/header; panel+panel-inner; form-label/c-danger; btn-primary-grad/btn-ghost; max-w-3xl + grid + md:col-span-2 preserved|
|theme/templates/contracts/matter_list.html|NetworkPage|NetworkPage|Medium|Relationship/entity network view across linked records|Link-density and identity columns vary|High|**MIGRATED** Batch 6 Step 4|Minimal hardening: aria-hidden on decorative SVG; removed redundant overflow-hidden stat-card from panel; already had tbl-*/badge-sm/c-link/c-muted from prior migration|
|theme/templates/contracts/negotiation_note_form.html|CommandPage|CommandPage|High|Input/action-driven page with form-first flow|Field spacing and button variants may drift|Medium|**TARGETED FIX Batch 6 Step 11** — btn-primary→btn-primary-grad text-white; btn-secondary→btn-ghost; full structural migration deferred|Canonical form-field and command header primitives|
|theme/templates/contracts/notification_list.html|ExceptionPage|ExceptionPage|Medium|Notifications are stateful exception/event queue|**MIGRATED — Batch 3 Slice 1 (2026-05-18)**|✅ Done|—|
|theme/templates/contracts/obligations_list.html|QueuePage|QueuePage|Medium|Record-oriented page with list/table/filter behavior|Mixed utility and canonical primitives may coexist|Medium|**RETIRED — Batch 7 Step 2 (2026-05-19).** Dead/unreachable JS prototype. No URL route, no Obligation model, no Django context vars, no backend coupling. All CRUD was in-memory mock only. File deleted. Not a migration — intentional removal of prototype debt.|
|theme/templates/contracts/operations_dashboard.html|ExceptionPage|ExceptionPage|High|Operations view centers on job health and exception-like states|**MIGRATED — Batch 3 Slice 1 (2026-05-18)**|✅ Done|—|
|theme/templates/contracts/organization_activity.html|NetworkPage|QueuePage|Medium|Audit log list with filters + pagination — QueuePage pattern|**MIGRATED Batch 5 Step 7 (2026-05-18)** — page-wrap, page-header/title/subtitle/actions, panel, tbl-*, badge-sm, select-base/input-base/btn-primary-grad/btn-ghost, empty-state, sr-only labels, pagination nav; 2× `onchange` handlers preserved.|Medium|Medium|Complete ✅|
|theme/templates/contracts/organization_identity_settings.html|QueuePage|WorkspacePage|Medium|Settings form workspace with multiple panels (SAML/SCIM/API tokens/webhooks)|**MIGRATED — Batch 5 Step 6 Slice A (2026-05-18)** — fixed `btn-primary`→`btn-primary-grad`, `btn-secondary`→`btn-ghost` (×2 each); preserved 2× onsubmit confirm guards|✅ Done|—|
|theme/templates/contracts/organization_security_settings.html|QueuePage|WorkspacePage|Medium|MFA policy + session revocation settings form workspace|**MIGRATED — Batch 5 Step 6 Slice A (2026-05-18)** — `ds-badge`→`badge-sm`, removed `checkbox-primary`, `btn-primary`→`btn-primary-grad`, `btn-secondary`→`btn-ghost`, `page-container`→`page-wrap`; preserved onsubmit confirm|✅ Done|—|
|theme/templates/contracts/organization_session_audit.html|ExceptionPage|QueuePage|Medium|Active sessions list with revoke actions — QueuePage pattern|**MIGRATED — Batch 5 Step 6 Slice A (2026-05-18)** — `page-container`→`page-wrap`, raw border div→`panel-item`, `btn-secondary`→`btn-ghost`; preserved onsubmit confirm|✅ Done|—|
|theme/templates/contracts/organization_team.html|NetworkPage|WorkspacePage|Medium|Team member management with table + invite + destructive actions|**Batch 6 Step 1 (2026-05-19)** — Fully migrated. page-wrap/header/title/subtitle/actions; panel+panel-head+panel-title for Active Members; panel+panel-inner for all 4 sidebar panels; tbl-head/tbl-th/tbl-row/tbl-td/c-muted; panel-item for inactive members, pending invites, history rows; select-base; btn-primary-grad (invite), btn-ghost (all small actions); c-warning (Revoke Sessions), c-danger (Deactivate, Revoke Invite), c-success (Reactivate); empty-state; onsubmit confirm guards added to 3 destructive actions (Revoke Sessions, Deactivate, Revoke Invite); all 7 forms, CSRF, owner-gate, self-guard preserved.|High|**MIGRATED**|Batch 6 Step 1 complete|
|theme/templates/contracts/privacy_dashboard.html|WorkspacePage|WorkspacePage|High|Policy/compliance dashboard with multiple panels and tabular slices|**MIGRATED — Batch 3 Slice 1 (2026-05-18)**|✅ Done|—|
|theme/templates/contracts/reports_dashboard.html|WorkspacePage|WorkspacePage|Medium|Context-rich page combining panels/details/actions|**MIGRATED — Batch 4 Step 2 Slice A (2026-05-18)**|✅ Done|—|
|theme/templates/contracts/repository.html|WorkspacePage|WorkspacePage|High|Repository combines controls, result set, and side context|**MIGRATED — Batch 3 Slice 2 Step 3 (2026-05-18)**|✅ Done|—|
|theme/templates/contracts/retention_policy_form.html|CommandPage|CommandPage|High|Input/action-driven page with form-first flow|**MIGRATED — Batch 5 Step 4 (2026-05-18)**|✅ Done|—|
|theme/templates/contracts/retention_policy_list.html|QueuePage|QueuePage|Medium|Record-oriented page with list/table/filter behavior|**MIGRATED — Batch 5 Step 4 (2026-05-18)**|✅ Done|—|
|theme/templates/contracts/risk_log_form.html|ExceptionPage|ExceptionPage|Medium|Exception/compliance/alert oriented operational flow|Severity/status emphasis inconsistent|High|**TARGETED FIX Batch 6 Step 11** — btn-primary→btn-primary-grad text-white; full structural migration deferred|Exception severity badge + queue conventions|
|theme/templates/contracts/risk_log_list.html|ExceptionPage|ExceptionPage|Medium|Exception/compliance/alert oriented operational flow|Severity/status emphasis inconsistent|High|**TARGETED FIX Batch 6 Step 11** — removed redundant stat-card from panel wrapper; full structural migration deferred|Exception severity badge + queue conventions|
|theme/templates/contracts/saml_select.html|CommandPage|CommandPage|High|Auth command flow page|Auth shell style split from app shell|High|Medium|Fullscreen shell governance decisions|
|theme/templates/contracts/search_results.html|QueuePage|QueuePage|Medium|Global result queue across entities|**MIGRATED — Batch 4 Step 6 (2026-05-18)**|✅ Done|—|
|theme/templates/contracts/signature_request_detail.html|WorkspacePage|WorkspacePage|Medium|Context-rich page combining panels/details/actions|Panel density and secondary actions vary|High|Medium|Workspace panel/header conventions and state patterns|
|theme/templates/contracts/signature_request_form.html|CommandPage|CommandPage|High|Input/action-driven page with form-first flow|Field spacing and button variants may drift|Medium|Low|Canonical form-field and command header primitives|
|theme/templates/contracts/signature_request_list.html|QueuePage|QueuePage|Medium|Record-oriented page with list/table/filter behavior|Mixed utility and canonical primitives may coexist|Medium|**MIGRATED** Batch 6 Step 10|Full QueuePage migration; page-wrap/page-header/page-title/page-subtitle; form-label + btn-ghost Filter; panel overflow-hidden; tbl-head/tbl-th/tbl-row/tbl-td; badge-sm SIGNED→green/PENDING→yellow/DECLINED→red/else→gray; c-link; empty-state; aria-hidden SVG; GET filter preserved|
|theme/templates/contracts/subprocessor_detail.html|NetworkPage|NetworkPage|Medium|Relationship/entity network view across linked records|Link-density and identity columns vary|High|**MIGRATED** Batch 6 Step 5|Full WorkspacePage migration; page-wrap/header/actions; panel+panel-inner for field rows; c-muted labels; back breadcrumb; btn-primary-grad Edit; max-w-3xl preserved|
|theme/templates/contracts/subprocessor_form.html|NetworkPage|NetworkPage|Medium|Relationship/entity network view across linked records|Link-density and identity columns vary|High|**MIGRATED** Batch 6 Step 5|Full WorkspacePage migration; page-wrap/header; panel+panel-inner space-y-4; form-label/c-muted help/c-danger errors; btn-primary-grad/btn-ghost; enctype preserved; field.id_for_label preserved|
|theme/templates/contracts/subprocessor_list.html|NetworkPage|NetworkPage|Medium|Relationship/entity network view across linked records|Link-density and identity columns vary|High|**MIGRATED** Batch 6 Step 5|Full WorkspacePage migration; page-wrap/header/title/subtitle/page-actions; panel table; tbl-head/tbl-th/tbl-row/tbl-td; badge-sm (red/yellow/green) for risk; c-link on name; c-success/c-danger for DPA/SCC; btn-ghost Edit; empty-state|
|theme/templates/contracts/templates_list.html|QueuePage|QueuePage|Medium|Record-oriented page with list/table/filter behavior|Mixed utility and canonical primitives may coexist|Medium|**RETIRED — Batch 7 Step 2 (2026-05-19).** Dead/unreachable JS prototype. The `templates_list` URL name (urls.py line 173) already resolves to `WorkflowTemplateListView` → `workflow_template_list.html` (migrated canonical page). This file was never rendered. All CRUD was in-memory mock only. File deleted. Not a migration — intentional removal of prototype debt.|
|theme/templates/contracts/time_entry_form.html|CommandPage|CommandPage|High|Input/action-driven page with form-first flow|Field spacing and button variants may drift|Medium|Low|Canonical form-field and command header primitives|
|theme/templates/contracts/time_entry_list.html|QueuePage|QueuePage|Medium|Record-oriented page with list/table/filter behavior|Mixed utility and canonical primitives may coexist|Medium|**MIGRATED** Batch 6 Step 10|Full QueuePage migration; page-wrap/page-header/page-title; 3-col KPI grid panel+panel-inner; panel overflow-hidden for table; tbl-head/tbl-th/tbl-row/tbl-td; c-success/c-muted for Billable; tabular-nums on hours/amount; aria-hidden SVG; empty-state|
|theme/templates/contracts/trademark_request_detail.html|WorkspacePage|WorkspacePage|Medium|Context-rich page combining panels/details/actions|Panel density and secondary actions vary|High|**TARGETED FIX Batch 6 Step 11** — btn-primary→btn-primary-grad text-white; full structural migration deferred|Workspace panel/header conventions and state patterns|
|theme/templates/contracts/trademark_request_form.html|CommandPage|CommandPage|High|Input/action-driven page with form-first flow|Field spacing and button variants may drift|Medium|**TARGETED FIX Batch 6 Step 11** — btn-primary→btn-primary-grad text-white; full structural migration deferred|Canonical form-field and command header primitives|
|theme/templates/contracts/trademark_request_list.html|QueuePage|QueuePage|Medium|Record-oriented page with list/table/filter behavior|Mixed utility and canonical primitives may coexist|Medium|**MIGRATED** Batch 6 Step 10 (docs only)|No code changes needed — already uses all canonical primitives (stat-card-lg, stat-card-amber/red, table-card, tab-pill variants, stat-label/value/sub-text, surface-bubble, btn-soft-primary, c-secondary/dim/amber/amber-soft/primary/accent all verified in base.html)|
|theme/templates/contracts/transfer_record_form.html|NetworkPage|NetworkPage|Medium|Relationship/entity network view across linked records|Link-density and identity columns vary|High|**MIGRATED** Batch 6 Step 5|Full WorkspacePage migration; page-wrap/header; panel+panel-inner space-y-4; form-label/c-muted help/c-danger errors; btn-primary-grad/btn-ghost; enctype preserved; field.id_for_label preserved|
|theme/templates/contracts/transfer_record_list.html|NetworkPage|NetworkPage|Medium|Relationship/entity network view across linked records|Link-density and identity columns vary|High|**MIGRATED** Batch 6 Step 5|Full WorkspacePage migration; page-wrap/header/title/subtitle/page-actions; panel table; tbl-head/tbl-th/tbl-row/tbl-td; c-success/badge-yellow for TIA; badge-sm badge-green/c-muted for Active; btn-ghost Edit; empty-state|
|theme/templates/contracts/trust_account_detail.html|WorkspacePage|WorkspacePage|Medium|Context-rich page combining panels/details/actions|Panel density and secondary actions vary|High|Medium|Workspace panel/header conventions and state patterns|
|theme/templates/contracts/trust_account_form.html|CommandPage|CommandPage|High|Input/action-driven page with form-first flow|Field spacing and button variants may drift|Medium|Low|Canonical form-field and command header primitives|
|theme/templates/contracts/trust_account_list.html|QueuePage|QueuePage|Medium|Record-oriented page with list/table/filter behavior|Mixed utility and canonical primitives may coexist|Medium|**MIGRATED** Batch 6 Step 10|Full QueuePage migration; page-wrap/page-header/page-title/page-subtitle (Total Balance); panel overflow-hidden; tbl-head/tbl-th/tbl-row/tbl-td; balance: c-success (>0)/c-muted (else) + tabular-nums; c-link for account name and View|
|theme/templates/contracts/trust_transaction_form.html|CommandPage|CommandPage|High|Input/action-driven page with form-first flow|Field spacing and button variants may drift|Medium|Low|Canonical form-field and command header primitives|
|theme/templates/contracts/workflow_dashboard.html|WorkspacePage|WorkspacePage|High|Operational orchestration dashboard with filters + multiple workflow states|**MIGRATED — Batch 3 Slice 2 Step 2 (2026-05-18); TARGETED FIX Batch 6 Step 11** — btn-primary→btn-primary-grad text-white|✅ Done|—|
|theme/templates/contracts/workflow_detail.html|WorkspacePage|WorkspacePage|Medium|Context-rich page combining panels/details/actions|Panel density and secondary actions vary|High|**TARGETED FIX Batch 6 Step 11** — btn-primary→btn-primary-grad text-white; full structural migration deferred|Workspace panel/header conventions and state patterns|
|theme/templates/contracts/workflow_form.html|CommandPage|CommandPage|High|Input/action-driven page with form-first flow|Field spacing and button variants may drift|Medium|**TARGETED FIX Batch 6 Step 11** — btn-primary→btn-primary-grad text-white; btn-outline→btn-ghost; full structural migration deferred|Canonical form-field and command header primitives|
|theme/templates/contracts/workflow_step_form.html|CommandPage|CommandPage|High|Input/action-driven page with form-first flow|Field spacing and button variants may drift|Medium|**TARGETED FIX Batch 6 Step 11** — btn-primary→btn-primary-grad text-white; full structural migration deferred|Canonical form-field and command header primitives|
|theme/templates/contracts/workflow_template_compare.html|QueuePage|QueuePage|Medium|Record-oriented page with list/table/filter behavior|Mixed utility and canonical primitives may coexist|Medium|**MIGRATED** Batch 6 Step 10|Full QueuePage migration; page-wrap; panel+panel-inner; page-title/page-subtitle; btn-ghost Back; btn-secondary→btn-ghost (critical: btn-secondary not canonical); version spans→badge-sm badge-gray; description→c-muted; preset tabs preserved as structural exception (no canonical active-tab primitive; bg-blue-600 active state kept)|
|theme/templates/contracts/workflow_template_detail.html|WorkspacePage|WorkspacePage|Medium|Context-rich page combining panels/details/actions|Panel density and secondary actions vary|High|**TARGETED FIX Batch 6 Step 11** — btn-primary→btn-primary-grad text-white; btn-secondary→btn-ghost; full structural migration deferred|Workspace panel/header conventions and state patterns|
|theme/templates/contracts/workflow_template_form.html|CommandPage|CommandPage|High|Input/action-driven page with form-first flow|Field spacing and button variants may drift|Medium|Low|Canonical form-field and command header primitives|
|theme/templates/contracts/workflow_template_list.html|QueuePage|QueuePage|Medium|Record-oriented page with list/table/filter behavior|Mixed utility and canonical primitives may coexist|Medium|**MIGRATED** Batch 6 Step 10|Full QueuePage migration; page-wrap/page-header/page-title/page-subtitle; btn-ghost Back; btn-primary-grad text-white Create; card grid as structural exception (hover:shadow-md preserved; no canonical card-grid primitive); version→badge-sm badge-gray; description/count→c-muted; View→c-link; empty-state; aria-hidden SVG|
|theme/templates/dashboard.html|WorkspacePage|WorkspacePage|High|Multi-panel executive operating surface with KPI, alerts, and task slices|**MIGRATED — Batch 3 Slice 2 Step 1 (2026-05-18)**|✅ Done|—|
|theme/templates/landing.html|Unknown / Needs decision|Unknown / Needs decision|Low|Public marketing/auth-adjacent surface does not map cleanly to operational archetypes|Separate visual language from app shell|Low|Medium|Decision needed: keep separate public archetype or align to fullscreen standard|
|theme/templates/layout_toggle.html|Unknown / Needs decision|Unknown / Needs decision|Medium|Tooling utility page for feature flag toggle|Not part of user-facing archetype flows|Low|Low|No migration needed unless retained in workflow|
|theme/templates/patterns/archetype_wrappers_examples.html|Unknown / Needs decision|Unknown / Needs decision|High|Pattern snippet library, not runtime page|None; planning artifact|Low|Low|Keep in sync with archetype source of truth|
|theme/templates/profile.html|CommandPage|WorkspacePage|High|User profile + MFA enrollment + recovery codes — multi-panel WorkspacePage|**Batch 5 audit (2026-05-19)** — 65 lines; 25 raw Tailwind hits; 1 form with 3 named submit actions (`update_profile`, `send_mfa_code`, `generate_mfa_recovery_codes`); `mfa_required` / `mfa_admin_user` conditional gates; MFA enrollment and recovery code flow. DEFER INDEFINITELY.|High|High|Defer indefinitely — MFA/security-critical; requires dedicated MFA-aware review|
|theme/templates/registration/login.html|CommandPage|CommandPage|High|Auth command flow page|Auth shell style split from app shell|High|Medium|Fullscreen shell governance decisions|
|theme/templates/registration/logout.html|CommandPage|CommandPage|High|Auth command flow page|Auth shell style split from app shell|High|Medium|Fullscreen shell governance decisions|
|theme/templates/registration/register.html|CommandPage|CommandPage|High|Auth command flow page|Auth shell style split from app shell|High|Medium|Fullscreen shell governance decisions|
|theme/templates/settings_hub.html|CommandPage|WorkspacePage|High|Settings hub/nav landing — links to all settings areas; already uses settings design system|**MIGRATED — Batch 5 Step 6 Slice A (2026-05-18)** — `page-container`→`page-wrap` only; all other classes already canonical|✅ Done|—|
|theme/templates/styleguide.html|Unknown / Needs decision|Unknown / Needs decision|High|Reference/demo page, not user workflow page|Can diverge from production primitives if unmanaged|Low|Low|Keep synced with canonical primitives|

## Major UI Route Archetype Map

|Route|Name|Recommended archetype|Confidence|Classification reason|
|---|---|---|---|---|
||contract_list|QueuePage|Medium|Mapped by URL name to template stem|
||home|Unknown / Needs decision|Low|Route-template mapping not direct from URL name|
||home|Unknown / Needs decision|Low|Route-template mapping not direct from URL name|
||index|Unknown / Needs decision|Low|Landing/index route may be public shell page|
|<int:pk>/|contract_detail|WorkspacePage|Medium|Mapped by URL name to template stem|
|<int:pk>/add_note/|add_negotiation_note|Unknown / Needs decision|Low|Route-template mapping not direct from URL name|
|<int:pk>/ai-assistant/|contract_ai_assistant|Unknown / Needs decision|Low|Route-template mapping not direct from URL name|
|<int:pk>/edit/|contract_update|CommandPage|Medium|Action/form command route|
|_health/|health_check|Unknown / Needs decision|Low|Route-template mapping not direct from URL name|
|approval-rules/|approval_rule_list|QueuePage|Medium|Mapped by URL name to template stem|
|approval-rules/<int:pk>/edit/|approval_rule_update|CommandPage|Medium|Action/form command route|
|approval-rules/new/|approval_rule_create|CommandPage|Medium|Action/form command route|
|approvals/|approval_request_list|QueuePage|Medium|Mapped by URL name to template stem|
|approvals/<int:pk>/edit/|approval_request_update|CommandPage|Medium|Action/form command route|
|approvals/new/|approval_request_create|CommandPage|Medium|Action/form command route|
|audit-log/|audit_log_list|ExceptionPage|High|Mapped by URL name to template stem|
|budgets/|budget_list|QueuePage|Medium|Mapped by URL name to template stem|
|budgets/<int:budget_pk>/add-expense/|add_expense|Unknown / Needs decision|Low|Route-template mapping not direct from URL name|
|budgets/<int:pk>/|budget_detail|WorkspacePage|Medium|Mapped by URL name to template stem|
|budgets/<int:pk>/edit/|budget_update|CommandPage|Medium|Action/form command route|
|budgets/new/|budget_create|CommandPage|Medium|Action/form command route|
|clause-categories/|clause_category_list|QueuePage|Medium|Mapped by URL name to template stem|
|clause-categories/<int:pk>/edit/|clause_category_update|CommandPage|Medium|Action/form command route|
|clause-categories/new/|clause_category_create|CommandPage|Medium|Action/form command route|
|clause-library/|clause_template_list|QueuePage|Medium|Mapped by URL name to template stem|
|clause-library/<int:pk>/|clause_template_detail|WorkspacePage|Medium|Mapped by URL name to template stem|
|clause-library/<int:pk>/compare/<int:other_pk>/|clause_template_compare|QueuePage|Medium|Mapped by URL name to template stem|
|clause-library/<int:pk>/edit/|clause_template_update|CommandPage|Medium|Action/form command route|
|clause-library/<int:pk>/playbooks/add/|clause_playbook_create|CommandPage|Medium|Action/form command route|
|clause-library/<int:pk>/variants/add/|clause_variant_create|CommandPage|Medium|Action/form command route|
|clause-library/new/|clause_template_create|CommandPage|Medium|Action/form command route|
|clients/|client_list|NetworkPage|Medium|Mapped by URL name to template stem|
|clients/<int:pk>/|client_detail|NetworkPage|Medium|Mapped by URL name to template stem|
|clients/<int:pk>/edit/|client_update|NetworkPage|Medium|Entity-network oriented route|
|clients/new/|client_create|NetworkPage|Medium|Entity-network oriented route|
|compliance/|compliance_checklist_list|ExceptionPage|Medium|Mapped by URL name to template stem|
|compliance/<int:pk>/|compliance_checklist_detail|ExceptionPage|Medium|Mapped by URL name to template stem|
|compliance/<int:pk>/add-item/|add_checklist_item|QueuePage|Medium|List/search queue route|
|compliance/<int:pk>/edit/|compliance_checklist_update|CommandPage|Medium|Action/form command route|
|compliance/<int:pk>/toggle-item/|toggle_checklist_item|CommandPage|Medium|Action/form command route|
|compliance/new/|compliance_checklist_create|CommandPage|Medium|Action/form command route|
|conflicts/|conflict_check_list|QueuePage|Medium|Mapped by URL name to template stem|
|conflicts/<int:pk>/edit/|conflict_check_update|CommandPage|Medium|Action/form command route|
|conflicts/new/|conflict_check_create|CommandPage|Medium|Action/form command route|
|counterparties/|counterparty_list|NetworkPage|Medium|Mapped by URL name to template stem|
|counterparties/<int:pk>/|counterparty_detail|NetworkPage|Medium|Mapped by URL name to template stem|
|counterparties/<int:pk>/edit/|counterparty_update|NetworkPage|Medium|Entity-network oriented route|
|counterparties/new/|counterparty_create|NetworkPage|Medium|Entity-network oriented route|
|dashboard/|dashboard|WorkspacePage|High|Mapped by URL name to template stem|
|dd-item/<int:pk>/toggle/|toggle_dd_item|CommandPage|Medium|Action/form command route|
|deadlines/|deadline_list|ExceptionPage|High|Mapped by URL name to template stem|
|deadlines/<int:pk>/complete/|deadline_complete|ExceptionPage|Medium|Exception/event workload route|
|deadlines/<int:pk>/edit/|deadline_update|ExceptionPage|Medium|Exception/event workload route|
|deadlines/new/|deadline_create|ExceptionPage|Medium|Exception/event workload route|
|documents/|document_list|QueuePage|Medium|Mapped by URL name to template stem|
|documents/<int:pk>/|document_detail|WorkspacePage|Medium|Mapped by URL name to template stem|
|documents/<int:pk>/compare/<int:other_pk>/|document_compare|QueuePage|Medium|Mapped by URL name to template stem|
|documents/<int:pk>/edit/|document_update|CommandPage|Medium|Action/form command route|
|documents/new/|document_create|CommandPage|Medium|Action/form command route|
|documents/ocr-queue/|document_ocr_queue|ExceptionPage|Medium|Mapped by URL name to template stem|
|documents/ocr-queue/<int:pk>/|document_ocr_review|QueuePage|Medium|Mapped by URL name to template stem|
|due-diligence-processes/|due_diligence_list_legacy|QueuePage|Medium|Mapped by URL name to template stem|
|due-diligence/|due_diligence_list|QueuePage|Medium|Mapped by URL name to template stem|
|due-diligence/<int:pk>/|due_diligence_detail|WorkspacePage|Medium|Mapped by URL name to template stem|
|due-diligence/<int:pk>/edit/|due_diligence_update|CommandPage|Medium|Action/form command route|
|due-diligence/<int:process_pk>/add-item/|add_dd_item|Unknown / Needs decision|Low|Route-template mapping not direct from URL name|
|due-diligence/<int:process_pk>/add-risk/|add_dd_risk|ExceptionPage|Medium|Exception/event workload route|
|due-diligence/new/|due_diligence_create|CommandPage|Medium|Action/form command route|
|ethical-walls/|ethical_wall_list|QueuePage|Medium|Mapped by URL name to template stem|
|ethical-walls/<int:pk>/edit/|ethical_wall_update|CommandPage|Medium|Action/form command route|
|ethical-walls/new/|ethical_wall_create|CommandPage|Medium|Action/form command route|
|invoices/|invoice_list|QueuePage|Medium|Mapped by URL name to template stem|
|invoices/<int:pk>/|invoice_detail|WorkspacePage|Medium|Mapped by URL name to template stem|
|invoices/<int:pk>/edit/|invoice_update|CommandPage|Medium|Action/form command route|
|invoices/new/|invoice_create|CommandPage|Medium|Action/form command route|
|legal-tasks/|legal_task_kanban|Unknown / Needs decision|Low|Route-template mapping not direct from URL name|
|legal-tasks/<int:pk>/edit/|legal_task_update|CommandPage|Medium|Action/form command route|
|legal-tasks/new/|legal_task_create|CommandPage|Medium|Action/form command route|
|login/|login|CommandPage|High|Mapped by URL name to template stem|
|logout/|logout|CommandPage|High|Mapped by URL name to template stem|
|matters/|matter_list|NetworkPage|Medium|Mapped by URL name to template stem|
|matters/<int:pk>/|matter_detail|NetworkPage|Medium|Mapped by URL name to template stem|
|matters/<int:pk>/edit/|matter_update|NetworkPage|Medium|Entity-network oriented route|
|matters/new/|matter_create|NetworkPage|Medium|Entity-network oriented route|
|new/|contract_create|CommandPage|Medium|Action/form command route|
|notifications/|notification_list|ExceptionPage|Medium|Mapped by URL name to template stem|
|notifications/<int:pk>/read/|mark_notification_read|ExceptionPage|Medium|Exception/event workload route|
|notifications/mark-all-read/|mark_all_notifications_read|ExceptionPage|Medium|Exception/event workload route|
|operations/|operations_dashboard|ExceptionPage|High|Mapped by URL name to template stem|
|organizations/activity/|organization_activity|NetworkPage|Medium|Mapped by URL name to template stem|
|organizations/activity/export/|organization_activity_export|Unknown / Needs decision|Low|Route-template mapping not direct from URL name|
|organizations/identity-telemetry/|identity_telemetry_dashboard|WorkspacePage|Medium|Mapped by URL name to template stem|
|organizations/invitations/<int:invite_id>/resend/|resend_organization_invite|CommandPage|Medium|Action/form command route|
|organizations/invitations/<int:invite_id>/revoke/|revoke_organization_invite|CommandPage|Medium|Action/form command route|
|organizations/invitations/<uuid:token>/accept/|accept_organization_invite|CommandPage|Medium|Action/form command route|
|organizations/members/<int:membership_id>/deactivate/|deactivate_organization_member|Unknown / Needs decision|Low|Route-template mapping not direct from URL name|
|organizations/members/<int:membership_id>/reactivate/|reactivate_organization_member|Unknown / Needs decision|Low|Route-template mapping not direct from URL name|
|organizations/members/<int:membership_id>/revoke-sessions/|revoke_member_sessions|CommandPage|Medium|Action/form command route|
|organizations/members/<int:membership_id>/role/|update_membership_role|CommandPage|Medium|Action/form command route|
|organizations/session-audit/|organization_session_audit|ExceptionPage|Medium|Mapped by URL name to template stem|
|organizations/session-audit/export/|organization_session_audit_export|ExceptionPage|Medium|Exception/event workload route|
|organizations/switch/|switch_organization|Unknown / Needs decision|Low|Route-template mapping not direct from URL name|
|organizations/team/|organization_team|NetworkPage|Medium|Mapped by URL name to template stem|
|privacy/|privacy_dashboard|WorkspacePage|High|Mapped by URL name to template stem|
|privacy/data-inventory/|data_inventory_list|QueuePage|Medium|Mapped by URL name to template stem|
|privacy/data-inventory/<int:pk>/|data_inventory_detail|WorkspacePage|Medium|Mapped by URL name to template stem|
|privacy/data-inventory/<int:pk>/edit/|data_inventory_update|CommandPage|Medium|Action/form command route|
|privacy/data-inventory/new/|data_inventory_create|CommandPage|Medium|Action/form command route|
|privacy/dsar/|dsar_list|ExceptionPage|Medium|Mapped by URL name to template stem|
|privacy/dsar/<int:pk>/|dsar_detail|ExceptionPage|Medium|Mapped by URL name to template stem|
|privacy/dsar/<int:pk>/edit/|dsar_update|CommandPage|Medium|Action/form command route|
|privacy/dsar/new/|dsar_create|CommandPage|Medium|Action/form command route|
|privacy/evidence-export/|privacy_evidence_export|Unknown / Needs decision|Low|Route-template mapping not direct from URL name|
|privacy/legal-holds/|legal_hold_list|ExceptionPage|Medium|Mapped by URL name to template stem|
|privacy/legal-holds/<int:pk>/|legal_hold_detail|ExceptionPage|Medium|Mapped by URL name to template stem|
|privacy/legal-holds/<int:pk>/edit/|legal_hold_update|CommandPage|Medium|Action/form command route|
|privacy/legal-holds/new/|legal_hold_create|CommandPage|Medium|Action/form command route|
|privacy/retention/|retention_policy_list|QueuePage|Medium|Mapped by URL name to template stem|
|privacy/retention/<int:pk>/edit/|retention_policy_update|CommandPage|Medium|Action/form command route|
|privacy/retention/new/|retention_policy_create|CommandPage|Medium|Action/form command route|
|privacy/subprocessors/|subprocessor_list|NetworkPage|Medium|Mapped by URL name to template stem|
|privacy/subprocessors/<int:pk>/|subprocessor_detail|NetworkPage|Medium|Mapped by URL name to template stem|
|privacy/subprocessors/<int:pk>/edit/|subprocessor_update|NetworkPage|Medium|Entity-network oriented route|
|privacy/subprocessors/new/|subprocessor_create|NetworkPage|Medium|Entity-network oriented route|
|privacy/transfers/|transfer_record_list|NetworkPage|Medium|Mapped by URL name to template stem|
|privacy/transfers/<int:pk>/edit/|transfer_record_update|CommandPage|Medium|Action/form command route|
|privacy/transfers/new/|transfer_record_create|CommandPage|Medium|Action/form command route|
|profile/|profile|CommandPage|High|Mapped by URL name to template stem|
|register/|register|CommandPage|High|Mapped by URL name to template stem|
|reports/|reports_dashboard|WorkspacePage|Medium|Mapped by URL name to template stem|
|reports/export/|reports_export|Unknown / Needs decision|Low|Route-template mapping not direct from URL name|
|repository/|repository|WorkspacePage|High|Mapped by URL name to template stem|
|risk-log/|risk_log_list_legacy|ExceptionPage|Medium|Mapped by URL name to template stem|
|risks/|risk_log_list|ExceptionPage|Medium|Mapped by URL name to template stem|
|risks/<int:pk>/edit/|risk_log_update|ExceptionPage|Medium|Exception/event workload route|
|risks/new/|risk_log_create|ExceptionPage|Medium|Exception/event workload route|
|saml/|saml_select|CommandPage|High|Mapped by URL name to template stem|
|saml/|saml_select|CommandPage|High|Mapped by URL name to template stem|
|saml/<slug:organization_slug>/acs/|saml_acs|Unknown / Needs decision|Low|Route-template mapping not direct from URL name|
|saml/<slug:organization_slug>/acs/|saml_acs|Unknown / Needs decision|Low|Route-template mapping not direct from URL name|
|saml/<slug:organization_slug>/login/|saml_login|CommandPage|Medium|Action/form command route|
|saml/<slug:organization_slug>/login/|saml_login|CommandPage|Medium|Action/form command route|
|saml/<slug:organization_slug>/logout/|saml_logout|CommandPage|Medium|Action/form command route|
|saml/<slug:organization_slug>/logout/|saml_logout|CommandPage|Medium|Action/form command route|
|saml/<slug:organization_slug>/metadata/|saml_metadata|Unknown / Needs decision|Low|Route-template mapping not direct from URL name|
|saml/<slug:organization_slug>/metadata/|saml_metadata|Unknown / Needs decision|Low|Route-template mapping not direct from URL name|
|search/|global_search|QueuePage|Medium|List/search queue route|
|search/presets/<int:preset_id>/delete/|delete_search_preset|QueuePage|Medium|List/search queue route|
|search/save/|save_search_preset|QueuePage|Medium|List/search queue route|
|settings/|settings_hub|CommandPage|High|Mapped by URL name to template stem|
|settings/identity/|organization_identity_settings|QueuePage|Medium|Mapped by URL name to template stem|
|settings/organization-security/|organization_security_settings|QueuePage|Medium|Mapped by URL name to template stem|
|settings/organization-security/export/|organization_security_export|Unknown / Needs decision|Low|Route-template mapping not direct from URL name|
|settings/organization-security/sessions/|organization_session_audit|ExceptionPage|Medium|Mapped by URL name to template stem|
|settings/organization-security/sessions/export/|organization_session_audit_export|ExceptionPage|Medium|Exception/event workload route|
|signatures/|signature_request_list|QueuePage|Medium|Mapped by URL name to template stem|
|signatures/<int:pk>/|signature_request_detail|WorkspacePage|Medium|Mapped by URL name to template stem|
|signatures/<int:pk>/edit/|signature_request_update|CommandPage|Medium|Action/form command route|
|signatures/<int:pk>/reminder/|signature_request_send_reminder|Unknown / Needs decision|Low|Route-template mapping not direct from URL name|
|signatures/<int:pk>/transition/<str:new_status>/|signature_request_transition|Unknown / Needs decision|Low|Route-template mapping not direct from URL name|
|signatures/new/|signature_request_create|CommandPage|Medium|Action/form command route|
|templates/|templates_list|QueuePage|Medium|URL name resolves to WorkflowTemplateListView → workflow_template_list.html (canonical). templates_list.html was a dead prototype — RETIRED Batch 7 Step 2.|
|time/|time_entry_list|QueuePage|Medium|Mapped by URL name to template stem|
|time/<int:pk>/edit/|time_entry_update|CommandPage|Medium|Action/form command route|
|time/new/|time_entry_create|CommandPage|Medium|Action/form command route|
|toggle-redesign/|toggle_redesign|CommandPage|Medium|Action/form command route|
|trademark-requests/|trademark_request_list_legacy|QueuePage|Medium|Mapped by URL name to template stem|
|trademarks/|trademark_request_list|QueuePage|Medium|Mapped by URL name to template stem|
|trademarks/<int:pk>/|trademark_request_detail|WorkspacePage|Medium|Mapped by URL name to template stem|
|trademarks/<int:pk>/edit/|trademark_request_update|CommandPage|Medium|Action/form command route|
|trademarks/new/|trademark_request_create|CommandPage|Medium|Action/form command route|
|trust-accounts/|trust_account_list|QueuePage|Medium|Mapped by URL name to template stem|
|trust-accounts/<int:account_pk>/add-transaction/|add_trust_transaction|Unknown / Needs decision|Low|Route-template mapping not direct from URL name|
|trust-accounts/<int:pk>/|trust_account_detail|WorkspacePage|Medium|Mapped by URL name to template stem|
|trust-accounts/new/|trust_account_create|CommandPage|Medium|Action/form command route|
|workflow-dashboard/|workflow_dashboard_legacy|WorkspacePage|High|Mapped by URL name to template stem|
|workflows/|workflow_dashboard|WorkspacePage|High|Mapped by URL name to template stem|
|workflows/<int:pk>/|workflow_detail|WorkspacePage|Medium|Mapped by URL name to template stem|
|workflows/<int:pk>/steps/add/|workflow_step_add|Unknown / Needs decision|Low|Route-template mapping not direct from URL name|
|workflows/create/|workflow_create|CommandPage|Medium|Action/form command route|
|workflows/step/<int:pk>/complete/|workflow_step_complete|Unknown / Needs decision|Low|Route-template mapping not direct from URL name|
|workflows/step/<int:pk>/edit/|workflow_step_update|CommandPage|Medium|Action/form command route|
|workflows/step/<int:pk>/update/|update_workflow_step|CommandPage|Medium|Action/form command route|
|workflows/templates/|workflow_template_list|QueuePage|Medium|Mapped by URL name to template stem|
|workflows/templates/<int:pk>/|workflow_template_detail|WorkspacePage|Medium|Mapped by URL name to template stem|
|workflows/templates/<int:pk>/clone-version/|workflow_template_clone_version|Unknown / Needs decision|Low|Route-template mapping not direct from URL name|
|workflows/templates/<int:pk>/compare/<int:other_pk>/|workflow_template_compare|QueuePage|Medium|Mapped by URL name to template stem|
|workflows/templates/<int:pk>/restore-version/|workflow_template_restore_version|Unknown / Needs decision|Low|Route-template mapping not direct from URL name|
|workflows/templates/<int:pk>/steps/add/|workflow_template_step_add|Unknown / Needs decision|Low|Route-template mapping not direct from URL name|
|workflows/templates/create/|workflow_template_create|CommandPage|Medium|Action/form command route|
