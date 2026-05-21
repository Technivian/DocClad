# FIGMA REDESIGN PREP

Date: 2026-05-21
Purpose: prepare CMS Aegis for a Figma-driven redesign without breaking backend behavior, RBAC, tenant scoping, filters, forms, or JS hooks.

## 1. Current Implementation Reality

CMS Aegis is a Django server-rendered application. The redesign will be driven primarily through template and shared-style refactors, not frontend component replacement.

Primary redesign anchors:

- `theme/templates/base.html` - global authenticated shell, nav, topbar, design tokens, shared helper classes.
- `theme/templates/dashboard.html` - legal operations landing workspace.
- `theme/templates/contracts/contract_list.html` - primary contract queue.
- `theme/templates/contracts/contract_form.html` - new/edit contract intake flow.
- `theme/templates/contracts/contract_detail.html` - contract workspace cockpit.
- `theme/templates/contracts/repository.html` - repository control center with preserved JS hooks.
- `theme/templates/contracts/workflow_dashboard.html` - workflow queue/orchestration surface.
- `theme/templates/contracts/workflow_detail.html` - workflow execution detail.
- `theme/templates/contracts/signature_request_list.html` - signature queue.
- `theme/templates/contracts/signature_request_detail.html` - signature execution detail.
- `theme/templates/contracts/audit_log_list.html` - audit evidence queue.
- `theme/templates/contracts/privacy_dashboard.html` - privacy workspace.
- `theme/templates/contracts/reports_dashboard.html` - reporting workspace.

Shared design constraints already visible in the codebase:

- Many pages extend a single authenticated shell.
- Shared tokens and compatibility styles currently live partly in `base.html`.
- Several pages already use canonical wrappers such as `page-wrap`, `panel`, `badge-sm`, `tbl-*`, and workspace rail patterns.
- Some pages still preserve structural exceptions because they carry workflow-specific forms, modal logic, or JS controllers.

## 2. What I Need From Figma

When you send the design, include as much of the following as possible:

- Figma file or share link.
- Which frame is the source of truth for desktop.
- Whether mobile/tablet layouts are in scope now or later.
- Final theme direction: dark only, light only, or dual-theme.
- Typography choices: font families, weights, sizes, line heights.
- Color tokens: brand, neutrals, semantic states, backgrounds, borders.
- Spacing and radius system.
- Table patterns: header treatment, row density, hover, sticky columns, bulk actions.
- Navigation patterns: sidebar width, collapse behavior, breadcrumbs, top search, header actions.
- Form patterns: labels, help text, validation, section dividers, sticky actions.
- Status language: badges, pills, warnings, escalations, disabled states.
- Empty, loading, error, and success states.
- Any motion rules worth keeping in scope.
- Which pages are highest priority for visual parity.

If the Figma uses named frames, the best handoff format is:

- frame name
- intended app route or page type
- priority
- desktop width
- notes on interaction/state changes

## 3. Translation Rules For This Repo

The redesign must stay within these safety boundaries:

- Do not change route names, form actions, field names, or query parameter behavior unless explicitly required.
- Do not remove IDs, `data-*` attributes, or JS anchors used by existing scripts.
- Do not change tenant, RBAC, workflow, repository, audit, or search logic during visual migration.
- Prefer wrapping and restructuring existing markup over rewriting view logic.
- Preserve Django blocks, includes, CSRF forms, pagination, filters, and modal hooks.

Known sensitive surfaces:

- `theme/templates/base.html` - shell-wide impact.
- `theme/templates/contracts/repository.html` - custom JS and preserved selectors.
- `theme/templates/contracts/workflow_detail.html` - modal/update interactions.
- `theme/templates/contracts/contract_form.html` - draft section editing and preview flow.
- security/profile/auth pages - should be isolated from broad redesign work unless intentionally scoped.

## 4. Recommended Execution Sequence Once Figma Arrives

### Phase A - Token Extraction

Translate the Figma into implementation primitives before touching page markup:

- CSS variables for color, spacing, radius, elevation, typography.
- canonical shell primitives
- canonical table primitives
- canonical form primitives
- canonical badge/state primitives
- canonical empty/loading/error patterns

Primary file target:

- `theme/templates/base.html`

### Phase B - Shell Alignment

Align the authenticated shell to the Figma:

- sidebar
- topbar
- page header rhythm
- workspace split behavior
- global search/action affordances
- panel density and border treatment

This creates visual leverage across the largest number of pages with minimal behavior risk.

### Phase C - Archetype Rollout

Apply the design by page archetype, not randomly by file:

- WorkspacePage: dashboard, repository, workflow detail, contract detail, reports, privacy dashboards.
- QueuePage: contract list, signature list, audit log, list screens.
- CommandPage: contract form and high-volume creation/edit flows.
- NetworkPage: entity-centric views like client, matter, counterparty, subprocessor.
- ExceptionPage: risk, deadlines, notifications, privacy exception flows.

### Phase D - Hardening And Parity

After each batch:

- run `manage.py check`
- run targeted regression tests where available
- smoke key routes over HTTP
- verify no selectors or form hooks were lost

## 5. First Batch Recommendation For Figma Parity

When the Figma arrives, start here unless your design centers somewhere else:

1. `theme/templates/base.html`
2. `theme/templates/dashboard.html`
3. `theme/templates/contracts/contract_list.html`
4. `theme/templates/contracts/contract_detail.html`
5. `theme/templates/contracts/contract_form.html`
6. `theme/templates/contracts/repository.html`
7. `theme/templates/contracts/workflow_dashboard.html`
8. `theme/templates/contracts/signature_request_list.html`

This batch covers the shell plus the most visible enterprise CLM surfaces.

## 6. Handoff Format I Will Use After You Share Figma

Once you provide the design, I will convert it into:

- a frame-to-template mapping
- a token delta list
- a batch-by-batch implementation plan
- a risk list for pages with preserved JS or modal behavior
- a validation checklist per batch

## 7. Immediate Next Step

Send the Figma link, screenshots, or exported frames. I can then map each frame to the exact Django templates and begin the redesign in a controlled sequence.