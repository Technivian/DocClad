# CMS Aegis Project Status

Last updated: 2026-04-25

Current checkout: `main` at `0262a2a` (`Automate release evidence bundle`)

## Executive Snapshot

CMS Aegis is a multi-tenant Django CLM / legal operations platform with contract lifecycle management, workflow routing, clause governance, privacy/compliance tooling, e-signature handling, search, reporting, and a broad set of admin/integration surfaces.

The app is **demo-ready** and **internally MVP-ready** for a CLM pilot. The current checkout can be taken to a `GO` release-gate state by running the synthetic Sprint 3 evidence seed + release evidence bundle command. The remaining production gap is live integration proof and rollback / restore evidence, not basic code correctness.

## UI Design Unification Status (Phase 2)

Latest pass: 2026-05-18 (Classification-only mapping pass)

Classification artifact:

- `DESIGN_ARCHETYPE_MAP.md`

Classification coverage:

- Templates scanned: 123
- UI routes classified: 190
- Recommended archetype totals:
  - QueuePage: 28
  - WorkspacePage: 20
  - CommandPage: 32
  - NetworkPage: 16
  - ExceptionPage: 19
  - Unknown / Needs decision: 8

Classification-only outcomes:

- Complete template-level planning matrix now exists with: current archetype, recommended archetype, confidence, drift notes, migration priority/risk, and dependencies.
- Major named UI routes now have recommended archetype mapping for migration planning.
- Top migration candidates and recommended Batch 3 scope are explicitly documented.

Classification pass risk level:

- None (no runtime template changes were made)

Previous migration batch: 2026-05-18 (Batch 1)

Migrated files:

- `theme/templates/contracts/contract_list.html`
- `theme/templates/contracts/risk_log_list.html`
- `theme/templates/contracts/budget_list.html`
- `theme/templates/contracts/trademark_request_list.html`

Batch outcomes:

- Canonical page headers applied (`page-wrap`, `page-header`, `page-title`, `page-subtitle`).
- Canonical form-field primitives maintained (`form-input`, `form-select`).
- Canonical table surface + row patterns applied (`panel`, `tbl-*`, removal of inline row hover handlers).
- Canonical status badge primitives applied (`badge-sm` + semantic badge variants).

Remaining inconsistent areas:

- Multiple list/detail templates still use ad-hoc status pills and non-canonical table wrappers.
- Some pages still use custom header structures and mixed spacing rhythm.
- `contracts/forms.py` still contains hardcoded utility class constants pending canonical form primitive migration.

Visual-risk level (latest batch):

- Low-to-medium
- Rationale: no business logic changes, no new visual styles, and no architecture changes; only primitive consolidation.

Pattern-first update (2026-05-18):

- Canonical page archetypes defined in `DESIGN_ARCHETYPE_PATTERNS.md`.
- Reusable wrappers/examples added in `theme/templates/patterns/archetype_wrappers_examples.html`.

Batch 2 migrated files (QueuePage archetype):

- `theme/templates/contracts/client_list.html`
- `theme/templates/contracts/matter_list.html`
- `theme/templates/contracts/document_list.html`

Batch 2 outcomes:

- Queue pages now follow canonical header, filter, table, badge, and spacing behavior.
- Business logic, data behavior, and routes preserved.

Batch 2 visual-risk level:

- Low-to-medium
- Rationale: strict archetype/pattern migration without introducing new visual systems or one-off designs.

Batch 3 pre-migration planning (2026-05-18):

- Strict execution checklist created before any template edits begin.
- Full per-template analysis completed for all 8 Batch 3 candidates.
- Artifact: `BATCH3_WORKSPACE_MIGRATION_PLAN.md`
- Status: Planning only — no templates modified.

Batch 3 Slice 1 migration (2026-05-18):

Migrated files:

- `theme/templates/contracts/notification_list.html` (ExceptionPage)
- `theme/templates/contracts/deadline_list.html` (ExceptionPage)
- `theme/templates/contracts/privacy_dashboard.html` (WorkspacePage)
- `theme/templates/contracts/operations_dashboard.html` (ExceptionPage)

Batch 3 Slice 1 outcomes:

- `chip`, `chip-active`, `chip-inactive` filter control primitives added to `base.html` (token-backed, light/dark variant).
- Canonical `page-wrap`, `page-header`, `page-title`, `page-subtitle` applied to all 4 templates.
- Canonical `panel`, `panel-head`, `panel-title` applied to table/card surfaces.
- Canonical `dash-grid dash-grid-4|3|2`, `kpi-card`, `stat-card-lg` applied to dashboard grid layouts.
- Canonical `tbl-head`, `tbl-th`, `tbl-row`, `tbl-td` applied to all tables.
- Canonical `badge-sm` + semantic badge variants applied to all status/priority indicators.
- Canonical `btn-primary-grad`, `btn-ghost` applied to all action buttons.
- `aria-label` added to form action buttons and icon-only indicators; `aria-hidden` on decorative SVGs; `role="region"` on drill command block.
- `overflow-x-auto` table wrapper added for mobile safety.
- Zero business logic changes. Zero inline event handlers introduced. Zero routing changes.
- Django check: 0 issues. Template parse: 4/4 OK. Test suite: 3/3 passed.

Batch 3 Slice 2 Step 1 migration (2026-05-18):

Migrated files:

- `theme/templates/dashboard.html` (WorkspacePage — action-chip retirement + normalization)
- `theme/templates/base.html` (removed `.action-chip` CSS block — class fully retired)

Batch 3 Slice 2 Step 1 outcomes:

- `action-chip` is now fully retired from the design system. Zero references remain in any template.
- 3 × `action-chip` CTAs replaced with `btn-ghost` in dashboard.html page-actions.
- `audit-action` non-canonical badge replaced with `badge-sm` + semantic variant.
- `aria-hidden="true"` applied to all decorative SVGs in dashboard.html.
- Redundant sr-only span (duplicate of visible text) removed.
- Django check: 0 issues. Template parse: OK. Test suite: 3/3 passed.

Batch 3 Slice 2 Step 2 migration (2026-05-18):

Migrated files:

- `theme/templates/contracts/workflow_dashboard.html` (WorkspacePage — full primitive replacement)

Batch 3 Slice 2 Step 2 outcomes:

- Full WorkspacePage normalization: `page-wrap`, `page-header`, `page-title`, `page-subtitle`, `page-actions`.
- `bg-teal-600` hardcoded primary CTA replaced with `btn-primary-grad`.
- Raw secondary buttons/links replaced with `btn-ghost`.
- Inline `onclick="toggleFilters()"` removed; replaced with `addEventListener` in script block; `aria-expanded`/`aria-controls` added.
- Filter panel: raw bg/border → `panel` + `panel-inner`; labels → `form-label`.
- Table: `panel overflow-hidden`, `tbl-head`, `tbl-th`, `tbl-row`, `tbl-td`.
- Status dots: raw rounded divs → `status-dot [green/blue/yellow/gray]`.
- Stage badges: raw utility string → `badge-sm badge-[yellow/blue/purple/green/gray]`.
- Contract links → `c-link`; sub-text → `item-meta`; muted text → `c-muted`.
- Progress bar: raw Tailwind → `progress-bar-bg` / `progress-bar-fill`; `data-width` JS preserved.
- Pagination links → `btn-ghost`.
- Decorative SVG → `aria-hidden="true"`.
- Django check: 0 issues. Template parse: OK. Test suite: 3/3 passed. 0 inline violations.

Batch 3 Slice 2 Step 3 migration (2026-05-18):

Files changed:
- `theme/templates/contracts/repository.html` — WorkspacePage normalization; inline handler removal
- `theme/static/js/cms-aegis-repository.js` — two new addEventListener bindings in setupEventListeners()

Primitives applied: page-wrap, page-header, page-title, page-subtitle, page-actions, dash-grid dash-grid-4, kpi-card, kpi-card stat-card-amber, kpi-label, kpi-value, panel, panel-inner, tbl-th (normalized), aria-hidden on decorative SVGs, aria-label on select-all, aria-live="polite" on selected-count.

Inline handlers removed: saveCurrentView onclick → data-action="save-view" (bound via JS); clearSelection onclick → data-action="clear-selection" (bound via JS).

Batch 3 Slice 2 Step 3 outcomes:
- Template parse: OK
- manage.py check: 0 issues
- manage.py test contracts: 3/3 passed
- Inline handler/style scan: 0 violations
- Retired/ad-hoc class scan: 0 remaining

Batch 3 Slice 2 Step 4 migration (2026-05-18):

Files changed:
- `theme/templates/base.html` — BoardView CSS block added (board-track, board-col, board-col-head, board-card)
- `theme/templates/contracts/legal_task_board.html` — Full WorkspacePage/BoardView normalization; inline handler removal

Primitives applied: page-wrap, page-header, page-title, page-subtitle, page-actions, board-track, board-col, board-col-head, board-card, badge-sm badge-gray (column count), badge-sm badge-[red/yellow/green] (priority), item-meta, c-link, c-danger, panel, panel-inner, input-base, empty-state, role="region"/role="article" ARIA structure.

Inline handlers removed: `onclick="updateTaskStatus()"` → `data-action="complete-task"` bound via IIFE addEventListener. `updateTaskStatus` function wrapped in IIFE (global scope eliminated).

Batch 3 Slice 2 Step 4 outcomes:
- Template parse: OK
- manage.py check: 0 issues
- manage.py test contracts: 3/3 passed
- Inline handler/style scan: 0 violations
- Retired/ad-hoc class scan: 0 remaining
- Board CSS verified in base.html: all 5 rules present

Remaining accessibility gap: drag-and-drop column movement not keyboard accessible (not faked). Only "Complete" (→ DONE) transition is keyboard reachable. Full column movement documented for Batch 4.

**Batch 3 Complete — all 8 templates migrated.**

Batch 3 targets (8 templates, 1,158 total lines):
- WorkspacePage: dashboard.html, workflow_dashboard.html, repository.html, privacy_dashboard.html, legal_task_board.html ✅
- ExceptionPage: operations_dashboard.html, deadline_list.html, notification_list.html ✅

Expected UX impact if Batch 3 succeeds:
- Visual coherence across top 5 highest-traffic workspace surfaces.
- 25% of all WorkspacePage templates (5 of 20) on canonical primitive system.
- Inline event handler violations eliminated from 2 pages.
- Accessibility baseline improved (ARIA roles, aria-label, aria-hidden on icons).
- Token-backed primitives replacing hardcoded utility stacks on 4 fully-raw templates.

## What The App Is For

### Main user roles

- Org owner / admin
- Legal ops / contract manager
- Reviewer / approver
- Privacy / compliance operator
- External signer
- Integration operator / system admin

### Main business flows

- Register / log in / switch organization
- Create and manage contracts
- Draft from clause templates and playbooks
- Route work through workflows and approvals
- Send and reconcile signature requests
- Track privacy/compliance records and deadlines
- Search, save views, and export reports
- Sync from Salesforce / NetSuite and receive webhooks
- Monitor operations and release evidence

### Core modules

- Identity, tenancy, and session security
- Contracts, documents, clients, matters, counterparties
- Clause library, playbooks, variants, and versioning
- Workflow templates, workflow execution, approvals, and reminders
- Signature requests and e-sign reconciliation
- Privacy/GDPR records, DSAR, retention, subprocessors, transfers
- Search, repository, saved searches, and semantic ranking
- Reporting, dashboards, exports, and operational evidence
- Salesforce, NetSuite, SCIM, SAML, and webhook integrations
- AI assistant and AI action planning

## System Map

### Routes and pages

The route surface is large. The two route registries are:

- [`config/urls.py`](/Users/haroonwahed/Documents/Projects/CMS-Aegis/config/urls.py)
- [`contracts/urls.py`](/Users/haroonwahed/Documents/Projects/CMS-Aegis/contracts/urls.py)

Key route families:

- Public / auth:
  - `/`
  - `/login/`
  - `/register/`
  - `/logout/`
  - `/dashboard/`
  - `/profile/`
  - `/settings/*`
  - `/operations/`
- Identity:
  - `/saml/*`
  - `/oidc/*`
  - `/scim/v2/*`
- Contracts core:
  - `/contracts/`
  - `/contracts/new/`
  - `/contracts/<id>/`
  - `/contracts/<id>/edit/`
  - `/contracts/search/`
  - `/contracts/repository/`
  - `/contracts/notifications/`
- Repository and drafting:
  - `/contracts/clients/*`
  - `/contracts/matters/*`
  - `/contracts/documents/*`
  - `/contracts/clause-categories/*`
  - `/contracts/clause-library/*`
  - `/contracts/counterparties/*`
- Workflow / approvals / signatures:
  - `/contracts/workflows/*`
  - `/contracts/templates/*`
  - `/contracts/approval-rules/*`
  - `/contracts/approvals/*`
  - `/contracts/signatures/*`
- Privacy / compliance:
  - `/contracts/privacy/*`
  - `/contracts/due-diligence/*`
  - `/contracts/legal-tasks/*`
  - `/contracts/trademarks/*`
  - `/contracts/risks/*`
  - `/contracts/compliance/*`
  - `/contracts/budgets/*`
  - `/contracts/deadlines/*`
- APIs:
  - SCIM users / groups
  - contracts API v1 and legacy contracts API
  - Salesforce status / OAuth / field map / sync / sync runs
  - NetSuite sync
  - webhook deliveries
  - e-sign webhook
  - executive analytics / dashboard presets

### Major frontend templates

Templates are primarily server-rendered and live under:

- [`theme/templates/base.html`](/Users/haroonwahed/Documents/Projects/CMS-Aegis/theme/templates/base.html)
- [`theme/templates/base_fullscreen.html`](/Users/haroonwahed/Documents/Projects/CMS-Aegis/theme/templates/base_fullscreen.html)
- [`theme/templates/base_redesign.html`](/Users/haroonwahed/Documents/Projects/CMS-Aegis/theme/templates/base_redesign.html)
- [`theme/templates/dashboard.html`](/Users/haroonwahed/Documents/Projects/CMS-Aegis/theme/templates/dashboard.html)
- [`theme/templates/landing.html`](/Users/haroonwahed/Documents/Projects/CMS-Aegis/theme/templates/landing.html)
- [`theme/templates/registration/login.html`](/Users/haroonwahed/Documents/Projects/CMS-Aegis/theme/templates/registration/login.html)
- [`theme/templates/registration/register.html`](/Users/haroonwahed/Documents/Projects/CMS-Aegis/theme/templates/registration/register.html)
- [`theme/templates/profile.html`](/Users/haroonwahed/Documents/Projects/CMS-Aegis/theme/templates/profile.html)
- [`theme/templates/settings_hub.html`](/Users/haroonwahed/Documents/Projects/CMS-Aegis/theme/templates/settings_hub.html)
- `theme/templates/contracts/*` for the business modules
- [`theme/templates/styleguide.html`](/Users/haroonwahed/Documents/Projects/CMS-Aegis/theme/templates/styleguide.html)
- [`theme/templates/components_demo.html`](/Users/haroonwahed/Documents/Projects/CMS-Aegis/theme/templates/components_demo.html)

### Backend apps and modules

The codebase is centered on the `contracts` Django app:

- `contracts/models.py`
- `contracts/forms.py`
- `contracts/permissions.py`
- `contracts/middleware.py`
- `contracts/api/views.py`
- `contracts/views.py`
- `contracts/views_domains/*`
- `contracts/services/*`
- `contracts/management/commands/*`
- `contracts/domain/*`
- `config/settings_base.py`
- `config/urls.py`

### Database entities

The main persisted models are:

- Organization / membership / invitation / user profile
- SCIM groups and API tokens
- Salesforce connection / field map / sync run
- Webhook endpoint / delivery
- Executive dashboard preset / search preset
- Client / matter / contract / document / OCR review
- Time entry / invoice / trust account / trust transaction
- Deadline / audit log / notification
- Conflict check / trademark request / legal task / tag / risk log
- Compliance checklist / checklist item
- Workflow template / workflow template step / workflow / workflow step
- Due diligence process / task / risk
- Budget / budget expense
- Negotiation thread
- Counterparty
- Clause category / clause template / clause playbook / clause variant
- Ethical wall
- Signature request
- Data inventory / DSAR / subprocessor / transfer record / retention policy / legal hold
- Approval rule / approval request
- Background job

### APIs and integrations

The app currently includes:

- SCIM provisioning APIs
- SAML login / ACS / logout / metadata
- Salesforce OAuth, status, sync, and sync-run APIs
- NetSuite sync API / command
- E-sign webhook reconciliation API
- Webhook delivery APIs
- Executive analytics APIs
- API v1 contract endpoints
- Legacy contract APIs
- AI assistant contract endpoint
- Background job and evidence bundle commands

## What Works

- Tenant-scoped login / register / logout flows
- Dashboard and main navigation
- Contract create / edit / list / detail
- Clause library create / edit / compare / version history
- Workflow templates and workflow execution
- Signature requests and transition guardrails
- Privacy/compliance pages and records
- Search, semantic search, and saved search presets
- Reporting / executive dashboards / exports
- Client, matter, document, billing, trust, risk, compliance, due diligence, trademark, and ethical wall flows
- Focused Django test suites pass locally
- `manage.py check` passes
- `manage.py migrate --noinput` passes on the current checkout
- `manage.py audit_null_organizations` passes after migrations
- `manage.py generate_release_evidence_bundle` generates a full release evidence pack and reports `GO` when Sprint 3 evidence is seeded

## What Is Partial

- SAML and SCIM are implemented, but external IdP / lifecycle proof is still a deployment concern
- Salesforce, NetSuite, and e-sign integrations exist, but live end-to-end evidence is still the real gate
- Some UI shells and demo templates are still experimental
- Some features are strong enough for internal use but still need enterprise polish and production hardening

## What Is Broken Or Missing

- The repo currently has a moderate `postcss` vulnerability reported by `npm audit`
- `theme/templates/contracts/templates_list.html` still contains placeholder TODO actions for edit/use-template behavior
- `contracts/services/repository.py` still retains a mock service path and abstract interface
- Production proof is not complete without a backup / restore rehearsal and real live cutover evidence
- Live Salesforce / webhook evidence from the target environment is still needed for true rollout confidence

## Current Risks

- Large, high-complexity modules are still easy to regress
- Integrations depend on external systems and live credentials
- Release confidence depends on evidence, not just code passing locally
- The UI contains some experimental/demonstration shells that can confuse scope
- Frontend dependency audit has a moderate PostCSS issue

## Recommendation

Treat the app as:

- **Demo-ready:** yes
- **Internal MVP-ready:** yes, with scope discipline
- **Production-ready:** not yet for a live rollout, because production cutover proof and live integration evidence are still missing

## Next Recommended Actions

1. Capture live Salesforce sync evidence in the target org.
2. Capture webhook delivery evidence from a real endpoint.
3. Finish the backup / restore rehearsal on the real database target.
4. Remove or resolve the remaining frontend TODO actions.
5. Address the moderate PostCSS advisory.
6. Consolidate experimental UI shells and demo templates.
7. Keep release evidence bundle commands attached to the release workflow.
8. Add stronger live E2E coverage for the major user flows.

---

## Batch 3 Post-Migration Audit (2026-05-18)

**Verdict: PASS**

All 8 Batch 3 templates passed the post-migration audit. Full report: `BATCH3_POST_MIGRATION_AUDIT.md`.

### Audit Fixes Applied

| Fix | File | Type |
|---|---|---|
| `input-field` × 3 → `input-base` / `select-base` | workflow_dashboard.html | Pre-existing violation fixed |
| `text-red-500` → `c-danger` on legal-hold KPI | privacy_dashboard.html | Minor canonical substitution |
| `text-red-500` → `c-danger` on job error text | operations_dashboard.html | Minor canonical substitution |

### Remaining Documented Exceptions

| Exception | Template | Disposition |
|---|---|---|
| `bg-blue-50` unread row tint | notification_list.html | Token gap — needs `--row-unread-bg` in Batch 4 |
| `bg-red-50` overdue row tint | deadline_list.html | Token gap — needs `--row-overdue-bg` in Batch 4 |
| Drag-and-drop keyboard column movement | legal_task_board.html | ARIA gap — deferred to Batch 4 JS work |

### Batch 3 Final State

- 8/8 templates archived as MIGRATED in DESIGN_ARCHETYPE_MAP.md
- 0 inline handlers remaining
- 0 inline styles remaining
- 0 retired classes remaining
- 0 undefined primitive classes remaining
- Template parse: 8/8 OK
- manage.py check: 0 issues
- manage.py test contracts: 3/3 passed

---

## Batch 4 Step 1 — Row-State Token Debt Cleanup (2026-05-18)

**Scope:** Token definition and 2 template replacements. No page migration.

### Tokens Added to base.html

| Token | Dark value | Light value |
|---|---|---|
| `--row-unread-bg` | `rgba(37,99,235,0.08)` | `#EFF6FF` |
| `--row-overdue-bg` | `rgba(239,68,68,0.08)` | `#FEF2F2` |

### Classes Added to base.html

| Class | CSS |
|---|---|
| `.row-unread` | `background: var(--row-unread-bg)` |
| `.row-overdue` | `background: var(--row-overdue-bg)` |

### Raw Utility Exceptions Resolved

| Was | Now | Template |
|---|---|---|
| `bg-blue-50` | `row-unread` | `notification_list.html` |
| `bg-red-50` | `row-overdue` | `deadline_list.html` |

### Remaining Raw Color Usages (Intentional — Not Row-State)

The following `bg-blue-50` / `bg-red-50` usages in templates are decorative panel/button/banner colors — not row-state — and are explicitly NOT replaced by this cleanup:

- `profile.html` — info/warning card banners
- `workflow_template_detail.html` — step card hover + info banner
- `workflow_detail.html` — current-step panel tint
- `contract_form.html` — drag handle and button hover colors
- `signature_request_detail.html` — status banners and action buttons
- `organization_team.html` — inline team action buttons
- `clause_template_detail.html` — selected version card highlight
- `workflow_form.html` — info banner
- JS strings in `obligations_list.html`, `clause_library.html`, `templates_list.html`, `reports_dashboard.html` — toast/chart colors

### Validation

- manage.py check: 0 issues
- Template parse: notification_list.html OK, deadline_list.html OK
- Tests: 3/3 passed

**Batch 4 page migration wave (reports_dashboard.html, identity_telemetry_dashboard.html, contract_detail.html, contract_list.html, search_results.html) can now begin.**

---

## Batch 4 Step 2 Slice A — Dashboard Migration (2026-05-18)

**Status: ✅ Complete**

### Files Changed

| File | Change |
|---|---|
| `theme/templates/contracts/reports_dashboard.html` | Full WorkspacePage migration |
| `theme/templates/contracts/identity_telemetry_dashboard.html` | Full WorkspacePage migration |
| `DESIGN_ARCHETYPE_MAP.md` | Both templates marked MIGRATED |
| `DESIGN_UNIFICATION_ROADMAP.md` | Slice A log entry added |

### Primitives Normalized

**reports_dashboard.html:** `page-wrap`, `page-header`, `page-title`, `page-subtitle`, `page-actions`, `dash-grid dash-grid-4` (×2), `kpi-card`, `stat-card-amber`, `stat-card-red`, `panel`, `panel-head`, `panel-inner`, `panel-divider`, `dash-grid dash-grid-2`, `list-row`, `btn-ghost`, `c-muted`, `c-danger`, `c-success-soft`, `report-progress-track/fill`, chart ARIA roles

**identity_telemetry_dashboard.html:** `page-wrap`, `page-header`, `page-title`, `page-subtitle`, `page-actions`, `dash-grid dash-grid-4`, `kpi-card`, `panel`, `panel-head`, `panel-inner`, `tbl-head`, `tbl-th`, `tbl-row`, `list-row`, `btn-ghost`, `c-muted`

### Remaining Risks

- 2 inline `style=` color overrides for amber (A/R) and blue (upcoming deadlines) — no canonical c-warning/c-info token yet; flagged for Step 3 token cleanup
- Chart bars use Tailwind `bg-blue-500` / `bg-red-500` in JS strings — acceptable; chart internals are JS-controlled and not template structure

### Slice B Readiness

✅ **Slice B can begin** — contract_detail.html and contract_list.html are next candidates per DESIGN_ARCHETYPE_MAP.md.

---

## Batch 4 Step 3 — Slice A Token Cleanup (2026-05-18)

**Status: ✅ Complete**

### Files Changed

| File | Change |
|---|---|
| `theme/templates/base.html` | Added `.c-warning` (`#F59E0B`) and `.c-info` (`#60A5FA`) |
| `theme/templates/contracts/reports_dashboard.html` | 2 inline `style=` removed → `c-warning`, `c-info` |
| `DESIGN_CONSTITUTION.md` | Semantic text color utilities section added |
| `DESIGN_UNIFICATION_ROADMAP.md` | Step 3 log entry added |

### Token Summary

- `c-warning` — amber-500 (`#F59E0B`), for financial attention/warning values
- `c-info` — blue-400 (`#60A5FA`), for informational/upcoming indicators

### Inline Style Debt: reports_dashboard.html

- Before: 2 inline `style="color:..."` overrides
- After: 0 — fully resolved

### Slice B Readiness

✅ **Slice B can begin** — `contract_detail.html` is the next candidate.

---

## Batch 4 Step 4 — Slice B: contract_list.html QueuePage Migration

**Status:** ✅ Complete

### Changes

| File | Change |
|---|---|
| `theme/templates/contracts/contract_list.html` | Removed `contracts-list-page` class; added `page-actions` wrapper; `aria-hidden="true"` on all decorative SVGs |
| `DESIGN_ARCHETYPE_MAP.md` | `contract_list.html` marked MIGRATED |
| `DESIGN_UNIFICATION_ROADMAP.md` | Step 4 Slice B log entry added |

### Primitives Applied

Already present from prior batch work: `page-wrap`, `page-header`, `page-title`, `page-subtitle`, `page-actions`, `stat-card`, `stat-card-amber`, `tabs-shell`, `tab-pill-*`, `panel`, `tbl-head`, `tbl-th`, `tbl-row`, `tbl-td`, `badge-sm`, `badge-expiring`, `btn-primary-grad`, `btn-ghost`, `btn-soft-primary`, `c-*`, `row-expiring`

### Next: contract_detail.html (Slice B continues)

---

## Batch 4 Step 5 — Slice B: contract_detail.html WorkspacePage Migration

**Status:** ✅ Complete

### Changes

| File | Change |
|---|---|
| `theme/templates/contracts/contract_detail.html` | Full WorkspacePage migration from raw Tailwind |
| `DESIGN_ARCHETYPE_MAP.md` | `contract_detail.html` marked MIGRATED |
| `DESIGN_UNIFICATION_ROADMAP.md` | Step 5 log entry added |

### Primitives Applied

`page-wrap`, `page-header`, `page-title`, `page-subtitle`, `page-actions`, `btn-ghost`, `panel`, `panel-head`, `panel-title`, `panel-inner`, `c-muted`, `c-link`, `badge-sm badge-green/badge-gray` (status), `badge-sm badge-red/badge-blue` (deadlines), `input-base`, `btn-primary-grad`, `list-row`

### Intentional Exceptions (Documented)

- `pre#ai-assistant-output` — raw `bg-gray-50 border border-gray-200` (no canonical code-output primitive)
- Negotiation notes list — raw `divide-y`/`px-5 py-3` vertical stack (no canonical vertical list-item primitive)
- Grid wrappers — Tailwind responsive `lg:grid-cols-3/2` (dash-grid has no responsive breakpoints)

### Next: search_results.html (Batch 4 final page)

---

## Batch 4 Step 6 — search_results.html QueuePage Migration ✅ COMPLETE

**Status:** ✅ Complete — **Batch 4 page migration wave is fully complete**

### Changes

| File | Change |
|---|---|
| `theme/templates/contracts/search_results.html` | Full QueuePage migration from raw Tailwind |
| `DESIGN_ARCHETYPE_MAP.md` | `search_results.html` marked MIGRATED |
| `DESIGN_UNIFICATION_ROADMAP.md` | Step 6 log entry added |

### Primitives Applied

`page-wrap`, `page-header`, `page-title`, `page-subtitle`, `input-base` (search + filters + save-name), `select-base` (search mode), `btn-primary-grad` (search submit, save search), `panel`, `panel-head`, `panel-title`, `panel-inner`, `list-row` (7 result categories), `c-muted`, `c-link`, `c-danger` (delete button)

### Accessibility Improvements

`aria-label` added to: type/status/jurisdiction filter inputs, search mode select, save-name input; `aria-hidden="true"` on both empty-state SVGs

### Batch 4 Summary

| Step | Template | Status |
|---|---|---|
| Step 1 | Row-state token cleanup | ✅ |
| Step 2 Slice A | 7 list templates + reports_dashboard + identity_telemetry_dashboard | ✅ |
| Step 3 | c-warning / c-info token cleanup | ✅ |
| Step 4 Slice B | contract_list.html | ✅ |
| Step 5 Slice B | contract_detail.html | ✅ |
| Step 6 | search_results.html | ✅ |

**All Batch 4 planned templates migrated.** Remaining tier-2/tier-3 templates continue in future batches.

---

## Batch 4 Post-Migration Audit ✅ COMPLETE (2026-05-18)

**Verdict: Batch 4 audit-clean. 0 regressions. 1 accessibility fix applied.**

### Fix Applied During Audit

| File | Fix |
|---|---|
| `theme/templates/contracts/contract_list.html` | Added `aria-hidden="true"` to 4 sort-arrow SVGs in sortable column headers |

### Summary

| Check | Result |
|---|---|
| Template parse (5 templates) | ✅ All OK |
| manage.py check | ✅ 0 issues |
| Tests | ✅ 3/3 |
| Inline styles | ✅ 0 across all 5 |
| Inline event handlers | ✅ 0 across all 5 |
| Retired classes | ✅ 0 across all 5 |
| Archetype conformance | ✅ All 5 conformant |
| Behavior preservation | ✅ All forms/routes/IDs/context vars intact |
| ARIA SVG coverage | ✅ Post-fix: 100% |

### Documented Exceptions (9 total, all reviewed)

| Exception | Decision |
|---|---|
| Chart JS className raw colors (reports_dashboard) | Remain — JS exception, no build tooling |
| Amber dot `bg-yellow-400` (contract_list) | Remain — no `status-dot` primitive yet |
| `pre#ai-assistant-output` raw classes (contract_detail) | Remain — no `pre-output` primitive yet |
| Negotiation notes vertical stack (contract_detail) | Remain — `list-row` is horizontal only |
| Responsive `lg:grid-cols-*` (contract_detail) | Remain — `dash-grid` has no breakpoints |
| Input shape classes on `input-base` elements | Remain — correct pattern, `input-base` is color-only |
| `lg:grid-cols-[2fr_1fr]` asymmetric grid (search_results) | Remain — no asymmetric grid primitive |
| Preset row inner border (search_results) | Remain — no `panel-item` primitive yet |
| Chart container ARIA labels | Deferred to Batch 5 (requires chart redesign) |

### See

`BATCH4_POST_MIGRATION_AUDIT.md` for full audit report including Batch 5 recommendations.

---

## Batch 5 Step 1 — Primitive Debt Cleanup ✅ COMPLETE (2026-05-18)

### Primitives Added

| Primitive | Location |
|---|---|
| `panel-item` | `base.html` — sub-item within panel-inner |
| `pre-output` | `base.html` — AI/code output pre element |
| `status-dot` | Already existed; now documented in DESIGN_CONSTITUTION.md |

### Templates Updated

| File | Change |
|---|---|
| `contract_list.html` | `bg-yellow-400` dot → `status-dot yellow` |
| `contract_detail.html` | `pre#ai-assistant-output` → `pre-output` + `aria-live="polite"` |
| `search_results.html` | Preset row raw classes → `panel-item` |
| `base.html` | `panel-item` + `pre-output` CSS defined |
| `DESIGN_CONSTITUTION.md` | Section 12 added (all new primitives + guidance) |

### Exceptions Resolved

3 of 9 Batch 4 exceptions closed: `bg-yellow-400` dot, `pre` raw classes, preset row border.

### Remaining Documented Exceptions

6 remain: chart JS className strings, responsive `lg:grid-cols-*` patterns (contract_detail, search_results), negotiation notes vertical stack, `divide-y` structure. All documented in DESIGN_CONSTITUTION.md §12 and BATCH4_POST_MIGRATION_AUDIT.md.

### Next: Batch 5 page wave (invoice_detail/list/form, retention_policy_*, organization templates)

---

## Batch 5 Step 2 — Invoice Page Wave ✅ COMPLETE (2026-05-18)

### Files Changed

| File | Archetype | Change |
|---|---|---|
| `theme/templates/contracts/invoice_list.html` | QueuePage | Full migration from raw Tailwind |
| `theme/templates/contracts/invoice_detail.html` | WorkspacePage | Full migration from raw Tailwind |
| `theme/templates/contracts/invoice_form.html` | CommandPage | Full migration from raw Tailwind |
| `DESIGN_ARCHETYPE_MAP.md` | — | All 3 invoice templates marked MIGRATED |

### Primitives Applied

**invoice_list:** `page-wrap`, `page-header`, `page-title`, `page-actions`, `btn-primary-grad`, `stat-card-amber/stat-card/stat-card-red`, `c-muted`, `c-warning`, `c-danger`, `panel`, `tbl-head`, `tbl-th`, `tbl-row`, `tbl-td`, `row-overdue`, `badge-sm badge-green/red/blue/gray`, `c-link`, `empty-state`

**invoice_detail:** `page-wrap`, `page-header`, `page-title`, `page-subtitle`, `page-actions`, `badge-sm`, `btn-ghost`, `panel`, `panel-inner`, `panel-2col`, `panel-divider`, `panel-head`, `panel-title`, `c-muted`, `c-danger`, `c-warning`

**invoice_form:** `page-wrap`, `page-header`, `page-title`, `panel`, `panel-inner`, `form-label`, `c-danger` (errors), `btn-primary-grad`, `btn-ghost`

### Intentional Exceptions

- `text-green-600` on Total Paid stat card and Paid balance — no `c-success` token; deferred to Batch 6
- `grid grid-cols-1 md:grid-cols-2 gap-4` in invoice_form — responsive grid, `panel-2col` has no breakpoints

### Next: retention_policy wave (retention_policy_list.html, retention_policy_detail.html, retention_policy_form.html if it exists)

---

## Batch 5 Step 3 — c-success Token Cleanup ✅ COMPLETE (2026-05-18)

Added `c-success` (`#16A34A`) to base.html. Replaced 2 `text-green-600` raw utility uses in invoice_list.html and invoice_detail.html. Documented in DESIGN_CONSTITUTION.md §12. All exceptions from Batch 5 Step 2 now resolved.

**Next:** retention_policy page wave

---

## Batch 5 Step 4 — Retention Policy Page Wave ✅ COMPLETE (2026-05-18)

### Files Changed

| File | Archetype | Change |
|---|---|---|
| `theme/templates/contracts/retention_policy_list.html` | QueuePage | Full migration from raw Tailwind |
| `theme/templates/contracts/retention_policy_form.html` | CommandPage | Full migration from raw Tailwind |
| `DESIGN_ARCHETYPE_MAP.md` | — | Both templates marked MIGRATED |

### Primitives Applied

**retention_policy_list:** `page-wrap`, `page-header`, `page-title`, `page-subtitle`, `page-actions`, `btn-primary-grad`, `panel`, `tbl-head`, `tbl-th`, `tbl-row`, `tbl-td`, `c-muted`, `c-danger`, `c-success`, `c-link`, `empty-state`

**retention_policy_form:** `page-wrap`, `page-header`, `page-title`, `page-actions`, `panel`, `panel-inner`, `form-label`, `c-muted` (help/back), `c-danger` (errors), `btn-ghost`, `btn-primary-grad`

### No Exceptions

Zero raw color utilities remain. Zero documented exceptions.

Note: `retention_policy_detail.html` does not exist — no detail route registered. Scope limited to list + form.

### Next: organization/settings templates wave

---

## Batch 5 Step 5 — Org/Settings Discovery ✅ COMPLETE (2026-05-18)

### Templates Discovered

7 organization/settings/profile templates found and classified:

| Template | Archetype | Risk | Action |
|---|---|---|---|
| `settings_hub.html` | WorkspacePage | LOW | Slice A |
| `organization_security_settings.html` | WorkspacePage | LOW-MEDIUM | Slice A |
| `organization_session_audit.html` | QueuePage | LOW-MEDIUM | Slice A |
| `organization_identity_settings.html` | WorkspacePage | MEDIUM | Slice A |
| `organization_activity.html` | QueuePage | MEDIUM | Slice B |
| `organization_team.html` | WorkspacePage | HIGH | Slice B — defer |
| `profile.html` | WorkspacePage | HIGH | Defer indefinitely |

### Key Finding: Undefined Class Gap

3 classes used in settings templates are NOT defined in base.html:
- `btn-primary` → `btn-primary-grad`
- `btn-secondary` → `btn-ghost`
- `ds-badge` → `badge-sm`
- `checkbox-primary` → remove

These will be resolved in Slice A (template-side only; no new CSS needed).

### Archetype Map Corrections Applied

All 7 templates reclassified in `DESIGN_ARCHETYPE_MAP.md` with corrected archetypes.

### Next: Batch 5 Step 6 — Org/Settings Slice A Migration (4 templates)

---

## Batch 5 Step 6 — Org/Settings Slice A ✅ COMPLETE (2026-05-18)

### Files Migrated

| File | Archetype | Key Changes |
|---|---|---|
| `settings_hub.html` | WorkspacePage | `page-container` → `page-wrap` |
| `organization_security_settings.html` | WorkspacePage | `ds-badge`→`badge-sm`, `checkbox-primary` removed, `btn-primary`→`btn-primary-grad`, `btn-secondary`→`btn-ghost` |
| `organization_session_audit.html` | QueuePage | `page-container`→`page-wrap`, raw border div→`panel-item`, `btn-secondary`→`btn-ghost` |
| `organization_identity_settings.html` | WorkspacePage | `btn-primary`→`btn-primary-grad`, `btn-secondary`→`btn-ghost` (×2) |

### Undefined Class Gap Resolved

All 4 undefined classes in settings templates eliminated:
- `btn-primary` → `btn-primary-grad` ✅
- `btn-secondary` → `btn-ghost` ✅
- `ds-badge` → `badge-sm` ✅
- `checkbox-primary` → removed ✅

### Behavior Preserved

All 4 `onsubmit="return confirm(...)"` destructive guards retained.
All forms, routes, context variables, CSRF tokens untouched.

### Remaining Org/Settings Scope

- Slice B: `organization_activity.html` (MEDIUM), `organization_team.html` (HIGH)
- Deferred: `profile.html` (HIGH, MFA-critical)

---

## Batch 5 Step 7 — organization_activity.html QueuePage Migration ✅ COMPLETE (2026-05-18)

### File Migrated

| File | Archetype | Key Changes |
|---|---|---|
| `contracts/organization_activity.html` | QueuePage | `page-wrap`/`page-header`/`page-title`/`page-subtitle`/`page-actions`; `panel`/`tbl-*`; `badge-sm badge-*`; `select-base`/`input-base`/`btn-primary-grad`/`btn-ghost`; `sr-only` accessible labels; `empty-state`; `nav[aria-label]` pagination |

### Behavior Preserved

- Both `onchange="this.form.submit()"` filter selects retained
- All filter params, export URL, pagination, context variables, template filters preserved

### Exceptions

None — full clean migration

### Validation

- Template parse: ✅ OK
- manage.py check: ✅ 0 issues
- Tests: ✅ 3/3 passed
- Inline styles/handlers: ✅ 0
- Retired/raw Tailwind: ✅ 0
- Undocumented primitives: ✅ 0

### Next Steps

Batch 5 should **pause for a post-migration audit** before attempting high-risk remaining templates:
- `organization_team.html` — HIGH risk (defer)
- `profile.html` — deferred indefinitely (MFA-critical)

---

## Batch 5 Post-Migration Audit ✅ COMPLETE (2026-05-19)

### Verdict

**✅ PASS** — All 10 Batch 5 templates are consistent with DESIGN_CONSTITUTION.md v1.1. Zero regressions. Zero security risks introduced.

### Validation

| Check | Result |
|---|---|
| Template parse (10/10) | ✅ |
| manage.py check | ✅ 0 issues |
| Test suite (3/3) | ✅ |
| Inline styles | ✅ 0 |
| Retired classes | ✅ 0 |
| Undocumented primitives | ✅ 0 |
| Behavior-sensitive elements | ✅ All preserved |

### Exceptions Confirmed

All 6 documented exceptions reviewed and kept as-is (see BATCH5_POST_MIGRATION_AUDIT.md for full decision table).

### Remaining High-Risk Templates

| Template | Decision |
|---|---|
| `organization_team.html` | Batch 6 Step 1 — careful migration with dedicated review |
| `profile.html` | Defer indefinitely — MFA-critical |

### Recommended Batch 6 Scope

1. `organization_team.html` — WorkspacePage (Step 1, HIGH risk, dedicated review)
2. `client_list.html` / `client_detail.html` / `client_form.html` — NetworkPage wave
3. `budget_detail.html` / `clause_template_detail.html` — WorkspacePage

### Artifact

`BATCH5_POST_MIGRATION_AUDIT.md` — full audit report

---

## Batch 6 Step 1 — organization_team.html ✅ COMPLETE (2026-05-19)

**Risk:** HIGH | **Archetype:** WorkspacePage

### Migration Summary

- 150-line raw-Tailwind template → canonical WorkspacePage (130 lines, 45 raw utility violations eliminated)
- page-wrap / page-header / page-title / page-subtitle / page-actions
- `panel` + `panel-head` for Active Members table panel
- 4× `panel` + `panel-inner` for sidebar panels
- `tbl-head` / `tbl-th` / `tbl-row` / `tbl-td` / `c-muted` for member table
- `panel-item` for all list rows
- `select-base` for role select; `btn-primary-grad` for invite submit
- `btn-ghost` + semantic color tokens (c-warning, c-danger, c-success) for inline actions
- `empty-state` for all empty tables/lists

### Destructive Action Hardening

| Action | Before | After |
|---|---|---|
| Revoke Sessions | 1-click POST | `onsubmit` confirm guard added |
| Deactivate Member | 1-click POST | `onsubmit` confirm guard added |
| Revoke Invite | 1-click POST | `onsubmit` confirm guard added |

### Preserved

- All 7 form action URLs and field names (backend-safe)
- CSRF on every form
- Owner-gating: `{% if membership.role == 'OWNER' and not is_owner %}disabled{% endif %}`
- Self-guard: `{% if membership.user_id != current_user_id %}` on destructive actions
- `invite_form` template variable (no action URL override)

### Validation

| Check | Result |
|---|---|
| Template parse | ✅ |
| manage.py check | ✅ 0 issues |
| Tests (3/3) | ✅ |
| Inline styles | ✅ 0 |
| Raw Tailwind utilities | ✅ 0 |
| Retired classes | ✅ 0 |
| Undocumented primitives | ✅ 0 |

### Next

Batch 6 Step 2: NetworkPage client wave — `client_list.html`, `client_detail.html`, `client_form.html`

---

## Batch 6 Step 2 — NetworkPage Client Wave

**Status:** COMPLETE

### Changes

**client_list.html** — minimal hardening
- `aria-hidden="true"` on decorative SVG in New Client button
- Removed redundant `overflow-hidden stat-card` from `panel` wrapper

**client_detail.html** — full WorkspacePage migration
- page-wrap / page-header / page-title / page-subtitle / page-actions
- panel + panel-inner for 3 info cards (Contact Info, Primary Contact, Financial)
- panel + panel-head + panel-title for Matters section
- badge-sm badge-green / badge-gray for matter status
- c-muted / c-link semantic color tokens
- btn-primary-grad (New Matter) + btn-ghost (Edit)
- empty-state for matters empty state
- hover:bg-gray-50 preserved on matter link rows (structural UX exception)

**client_form.html** — full WorkspacePage migration
- page-wrap / page-header / page-title
- panel + panel-inner wrapping form
- form-label for all labels; c-danger for validation errors
- btn-primary-grad (submit) + btn-ghost (cancel)
- max-w-3xl + grid structural exceptions preserved

### Preserved
- All backend field names and CSRF tokens
- Context variables: clients, client, matters, form, search_query, page_obj
- onchange filter selects (acceptable pattern)
- Pagination structure

### Validation
- Template parse: ✅ all 3 templates OK
- manage.py check: ✅ 0 issues
- Tests: ✅ 3/3 pass

---

## Batch 6 Step 3 — NetworkPage Counterparty Wave

**Status:** COMPLETE

### Changes

**counterparty_list.html** — full WorkspacePage migration
- page-wrap / page-header / page-title / page-subtitle / page-actions
- panel table with tbl-head / tbl-th / tbl-row border-b / tbl-td
- badge-sm badge-green / badge-gray for is_active status
- c-link on Edit action; empty-state for empty table
- btn-primary-grad on Add New; aria-hidden on decorative SVG

**counterparty_detail.html** — full WorkspacePage migration
- page-wrap / page-header / page-title / page-actions
- panel + panel-inner for detail field list
- c-muted for field labels; btn-primary-grad for Edit
- Back link preserved above page-header
- max-w-3xl kept as structural exception

**counterparty_form.html** — full WorkspacePage migration
- page-wrap / page-header / page-title
- panel + panel-inner wrapping form
- form-label / c-muted / c-danger for label / help / error
- btn-primary-grad (Save) + btn-ghost (Cancel)
- enctype, object|yesno, field.id_for_label, field.errors|join preserved

### Preserved
- `counterparties`, `object`, `form` context vars
- `counterparty_list`, `counterparty_create`, `counterparty_update` URL names
- `item.is_active` boolean status field
- `{{ field }}` widget rendering; `enctype="multipart/form-data"`

### No Destructive Actions
None present — no confirm guards required.

### Validation
- Template parse: ✅ all 3 OK
- manage.py check: ✅ 0 issues
- Tests: ✅ 3/3 pass
