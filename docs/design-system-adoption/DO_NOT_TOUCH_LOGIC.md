# Do Not Touch Logic During Visual Migration

This file defines logic boundaries for design-system adoption. Visual migration must not change these without explicit approval and focused tests.

## Hard No-Change Areas

- Models and migrations.
- URL patterns and route names.
- API endpoints and serializers/responses.
- Permissions and authorization checks.
- Tenant scoping and organization filters.
- Workspace-mode containment.
- Form classes, field names, validation, and cleaning.
- Workflow creation, approval routing, risk detection, and audit creation.
- Querysets, ordering, filtering, and pagination logic.
- Background jobs, management commands, and seed logic.

## Files to Avoid Unless Explicitly Required

- `contracts/models.py`
- `contracts/forms.py`
- `contracts/permissions.py`
- `contracts/tenancy.py`
- `contracts/nav_config.py`
- `contracts/api/**`
- `contracts/services/**`
- `contracts/views_domains/**`
- `contracts/urls.py`
- `config/urls.py`
- `contracts/migrations/**`
- `contracts/management/**`

## Template Contracts to Preserve

When editing templates, preserve:

- `{% csrf_token %}`
- form `method`
- form `action`
- submit button `type`, `name`, and `value`
- input/select/textarea `name`
- IDs used by scripts
- `data-*` attributes used by scripts and tests
- `{% url %}` route names and parameters
- workspace-mode conditionals
- permission conditionals
- empty/error rendering branches
- pagination and filter query params

## High-Risk Template Hooks

Do not alter these casually:

- DPA/MSA/NDA cockpit `data-field-key` inputs.
- DPA/MSA/NDA submit button IDs.
- `workflow_detail` modal and step update IDs.
- Approval decision buttons and status form fields.
- Signature send/reminder/transition forms.
- Organization security workspace-mode form controls.
- Search/filter form input names.
- Pagination links.
- Audit/export links.

## Workspace-Mode Containment

Existing containment rules must remain intact:

- `law_firm_ops` remains the default workspace mode.
- `in_house_clm` surfaces must not leak into law-firm-only pages.
- Law-firm operational navigation/content must not appear in in-house-only contexts unless already canonical.
- Mode checks in `dashboard`, `matter_detail`, `risk_log_list`, navigation, and organization settings are functional product logic, not presentation.

Relevant guardrail docs/tests:

- `docs/WORKSPACE_MODE_CONTAINMENT.md`
- `tests/test_workspace_mode_containment.py`
- `tests/test_nav_workspace_mode.py`
- `tests/test_nav_law_firm_baseline.py`
- `tests/test_command_center_in_house_clm.py`

## Workflow Logic Boundaries

Do not change:

- `contracts/services/dpa_workflow.py`
- `contracts/services/msa_workflow.py`
- `contracts/services/nda_workflow.py`
- field definitions
- risk signal detection
- approval route generation
- draft document creation
- audit event creation
- Command Center work item creation

Visual migration can wrap or restyle the rendered fields, but must keep values and posting behavior identical.

## Approval and Signature Logic Boundaries

Do not change:

- Approval access checks.
- Self-approval prevention.
- Delegation behavior.
- Signature transition/send/reminder behavior.
- Packet retry/cancel/resend behavior.

Relevant tests:

- `tests/test_approval_authorization.py`
- `tests/test_self_approval_blocked.py`
- `tests/test_approval_workflow.py`
- `tests/test_signature_workspace.py`
- `tests/test_esign_outbound.py`
- `tests/test_esign_reconciliation.py`

## Safe Visual Edit Pattern

Allowed during future page migration:

- Change wrapper classes.
- Replace repeated markup with template includes.
- Move page-local CSS into design-system classes.
- Add non-functional visual containers.
- Add accessible labels where they do not alter behavior.

Not allowed without approval:

- Change field or route names.
- Move forms outside their current submission structure unless tested.
- Convert server forms to client-managed forms.
- Replace anchor links with buttons or buttons with anchors where behavior differs.
- Remove conditionals because they "look empty".
- Remove hidden inputs.
- Remove IDs/data attributes.
