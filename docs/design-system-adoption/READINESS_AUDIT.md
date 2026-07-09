# Design System Adoption Readiness Audit

Date: 2026-07-09  
Scope: pre-adoption audit for a future reusable design system transplant under `src/design-system`.  
Constraint: no page redesign, no new design-system files, no business logic changes.

## Executive Summary

DocClad is ready for a controlled design-system transplant only after the CSS/package conflicts and migration boundaries below are acknowledged. The current frontend is a Django-template application with Tailwind-generated CSS, large global shell styles in `base.html`, several page-local style systems, and repeated UI vocabularies for buttons, cards, badges, tables, rails, and cockpit layouts.

The safest adoption path is incremental and page-by-page. Do not attempt a global CSS swap. The current app depends on local class families such as `btn-*`, `badge-*`, `arch-*`, `dc-*`, `cform-*`, `cw-*`, and workspace-mode conditional rendering. A new design system should be mounted behind namespaced classes or wrapper includes first, then applied to one surface at a time.

## Current Frontend Folder Structure

- `theme/templates/`: primary Django templates, including `base.html`, auth pages, dashboards, workflow cockpits, CRUD pages, and module pages.
- `theme/templates/components/`: partial table/activity/chip components used by some newer surfaces.
- `theme/templates/contracts/`: most product screens and forms.
- `theme/static_src/src/`: Tailwind/CSS source entrypoints:
  - `styles.css`: Tailwind v4-style entrypoint and theme declarations.
  - `base.css`: foundational variables and global base rules.
  - `components.css`: app component utilities and archetype classes.
  - `theme.css`: older token layer with additional global styles.
- `theme/static/css/dist/styles.css`: generated CSS output consumed by `base.html`.
- `client/tests/e2e/`: Playwright smoke/regression tests.
- `client/package.json`: Playwright/Vite-only package area.
- `theme/package.json` and `theme/static_src/package.json`: overlapping build manifests with different Tailwind versions.

## Current UI Architecture

DocClad is server-rendered. Most presentation is template-driven, not React-driven. JavaScript is mostly page-local behavior in templates plus `static/js/csp-handlers.js`.

The app shell is primarily in `theme/templates/base.html`. It provides:

- Deep navy sidebar and top bar.
- Workspace-mode navigation differences.
- Global token declarations.
- Shared utility classes and shell styles.
- Generated CSS import from `theme/static/css/dist/styles.css`.

Some full-screen/auth surfaces use `base_fullscreen.html`. `base_redesign.html` exists but is not the canonical shell for most pages.

## App Shell and Layout Components

- Shell: `theme/templates/base.html`
- Fullscreen/auth shell: `theme/templates/base_fullscreen.html`
- Legacy/alternate shell: `theme/templates/base_redesign.html`
- Dashboard surface: `theme/templates/dashboard.html`
- Component partials:
  - `components/_work_queue_table.html`
  - `components/_approval_queue_table.html`
  - `components/_obligations_matrix_table.html`
  - `components/_task_queue_table.html`
  - `components/_activity_line.html`
  - `components/_assignee_chip.html`
  - `components/_stage_dots.html`
- Field input partial:
  - `contracts/_dpa_field_input.html`

## Repeated Page Patterns

- Page headers: `page-header`, `arch-header`, `dc-page-head`, cockpit-specific headers such as `msa-page-head` / `nda-page-head`.
- List/table pages: contract list, repository, approval list, audit log, document list, risk list, DPA reviews, privacy registries.
- Detail workspaces: contract detail, workflow detail, matter detail, document detail, DPA/MSA/NDA workspaces.
- Form pages: many CRUD forms reuse Django forms but not a single canonical section/action layout.
- Right rails: `arch-context-rail`, `cw-rail`, cockpit sidebars, dashboard operational rail.
- Workflow/cockpit pages: DPA, MSA, NDA builders and generated workflow workspaces.
- Admin/settings surfaces: organization security, identity settings, team, activity, session audit.

## Repeated Component Families

Approximate class-family occurrences found in templates/static source:

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
- Inline `style=` attributes: 103

These counts are not defects by themselves, but they show that visual primitives are duplicated instead of centralized.

## Mixed Business and Presentation Risk

High-risk templates include UI markup interleaved with workflow/risk/state behavior:

- `contracts/dpa_workflow_builder.html`
- `contracts/msa_workflow_builder.html`
- `contracts/nda_workflow_builder.html`
- `contracts/dpa_contract_workspace.html`
- `contracts/msa_contract_workspace.html`
- `contracts/nda_contract_workspace.html`
- `contracts/workflow_detail.html`
- `dashboard.html`
- `contracts/contract_template_picker.html`
- `contracts/contract_form.html`
- `contracts/approval_request_list.html`
- `contracts/privacy_dashboard.html`
- `contracts/legal_intelligence_hub.html`

During adoption, keep all view context, form field names, `data-field-key` attributes, route names, and POST targets intact.

## Low-Risk Migration Candidates

These are mostly static, list, or simple form surfaces with limited client-side behavior:

- Error pages: `400.html`, `403.html`, `404.html`, `500.html`
- Static policy pages: `privacy.html`, `terms.html`
- Settings hub: `settings_hub.html`
- Style/component demo pages after the new system is copied.
- Simple list pages with tenant-scoped querysets and no complex actions:
  - `contracts/clause_category_list.html`
  - `contracts/retention_policy_list.html`
  - `contracts/legal_hold_list.html`
  - `contracts/conflict_check_list.html`

## Medium-Risk Migration Candidates

These have forms, filters, tenant scoping, or moderate state:

- `contracts/contract_list.html`
- `contracts/repository.html`
- `contracts/counterparty_list.html`
- `contracts/client_list.html`
- `contracts/matter_list.html`
- `contracts/document_list.html`
- `contracts/audit_log_list.html`
- `contracts/notification_list.html`
- `contracts/approval_request_list.html`
- Standard CRUD form templates such as `contract_form.html`, `matter_form.html`, `document_form.html`, `counterparty_form.html`.

## High-Risk Migration Candidates

These contain dense workflow, permissions, live preview, route transitions, workspace-mode branching, or specialized behavior:

- `dashboard.html`
- `contracts/contract_template_picker.html`
- `contracts/dpa_workflow_builder.html`
- `contracts/msa_workflow_builder.html`
- `contracts/nda_workflow_builder.html`
- `contracts/workflow_detail.html`
- `contracts/dpa_contract_workspace.html`
- `contracts/msa_contract_workspace.html`
- `contracts/nda_contract_workspace.html`
- `contracts/matter_detail.html`
- `contracts/legal_intelligence_hub.html`
- `contracts/privacy_dashboard.html`
- `contracts/dpa_review_pack_detail.html`
- `contracts/signature_request_detail.html`
- `contracts/signature_packet_detail.html`
- `contracts/organization_security_settings.html`

## Recommended First Migration Target

Recommended first target: `settings_hub.html`.

Reason: it is visible, authenticated, low business-risk, uses repeated card/header patterns, and does not drive workflow creation or approval transitions. It can validate the design-system shell/card/button primitives without risking contracts, approvals, or workflow logic.

Recommended first golden-product target after that: `contract_template_picker.html`, but only after base primitives are mounted and tested on a lower-risk page.

## Files to Leave Untouched During Visual Migration

Do not touch these unless the migration explicitly requires a backend contract and has test coverage:

- `contracts/models.py`
- `contracts/forms.py`
- `contracts/permissions.py`
- `contracts/tenancy.py`
- `contracts/nav_config.py`
- `contracts/views_domains/*` view/query logic
- `contracts/services/*`
- `contracts/api/*`
- `contracts/urls.py`
- `config/urls.py`
- migrations
- workflow seed/creation services
- audit and organization scoping helpers

Template migration must preserve:

- `name=` attributes
- CSRF blocks
- form `method` and `action`
- `data-*` hooks used by Playwright and page scripts
- element IDs used by JavaScript
- route `{% url %}` calls
- permission/workspace-mode conditionals

## Checks After Each Migrated Page

Run at minimum:

- `DJANGO_SETTINGS_MODULE=config.settings_test .venv/bin/python manage.py check`
- Focused Django tests for the page/module.
- Existing Playwright smoke for the page if present.
- Manual check for both workspace modes when the page is mode-sensitive.
- Verify no change to generated POST payloads, query params, or redirect targets.
- Verify empty, populated, and validation/error states.

## Blockers Before Copying `src/design-system`

- Resolve or deliberately document the Tailwind version split between `theme/package.json` and `theme/static_src/package.json`.
- Decide whether the new system is React-based, CSS-only, or Django-template compatible. The current app is not a React app.
- Namespace new design-system CSS to avoid collisions with existing `.card`, `.badge`, `.btn`, `.table`, `.input`, `.drawer`, `.toast`, and token names.
- Decide whether global tokens in `base.html`, `base_fullscreen.html`, and `theme/static_src/src/*.css` remain authoritative or are superseded.
- Establish a migration adapter for Django templates before replacing existing components.
- Create guardrail tests for deprecated classes only after new replacement classes exist.

## Audit-Only Changes Made

Only documentation under `docs/design-system-adoption/` was added. No frontend appearance, backend logic, routes, models, forms, permissions, APIs, queries, workflows, or tests were changed.
