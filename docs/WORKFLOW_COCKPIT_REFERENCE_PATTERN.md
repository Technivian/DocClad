# Workflow Cockpit Reference Pattern

DocClad now has three reference workflow-first contract creation paths:

- DPA cockpit route: `/contracts/new/dpa/`
- MSA cockpit route: `/contracts/new/msa/`
- NDA cockpit route: `/contracts/new/nda/`

These are the baseline implementation pattern for governed drafting before more contract types are added.

## Shared creation lifecycle

Both routes follow the same lifecycle:

1. User selects contract type from New Contract.
2. DocClad opens a dedicated workflow cockpit for that type.
3. User completes field definitions and smart routing questions.
4. Live draft preview updates from the approved template.
5. Risk checks and approval reasoning update in the cockpit.
6. Generate governed draft creates the workflow instance and related records.
7. User is redirected to `/contracts/workflows/<id>/`.
8. Workflow detail renders a dedicated contract workspace view.
9. Command Center shows a persisted work item linking back to that workspace.

## Created records

The governed draft create step writes the same core record set for DPA, MSA, and NDA:

- `Contract`
- `Workflow`
- materialized `WorkflowStep` rows from the seeded `WorkflowTemplate`
- `FieldValue` rows for the selected workflow template field definitions
- current `DraftDocument`
- persisted `RiskSignal` rows
- persisted `CommandCenterWorkItem`
- audit event via `log_action(...)`

`ApprovalRoute` remains template-scoped and is read from the seeded workflow template to drive cockpit and workspace approval rendering.

## Risk signal pattern

All three implementations use rule-based risk creation in their service module:

- DPA: `contracts/services/dpa_workflow.py`
- MSA: `contracts/services/msa_workflow.py`
- NDA: `contracts/services/nda_workflow.py`

The pattern is the same:

- evaluate cleaned field values
- create `RiskSignal` rows on the workflow
- derive highest-risk summary for Command Center
- drive approval reasoning and workspace risk cards from persisted signals

## Approval route pattern

All three cockpits:

- read seeded `ApprovalRoute` rows from the workflow template
- render approval routing in the cockpit right rail
- show approval reasoning live in the cockpit
- render approval cards and explanations again in the workspace

Conditional approvals are field/risk driven, but the source of truth remains the template plus persisted risk state.

## Workspace pattern

Generated workspaces use the workflow detail route and switch to a contract-type-specific command room view:

- DPA workspace include: `theme/templates/contracts/dpa_contract_workspace.html`
- MSA workspace include: `theme/templates/contracts/msa_contract_workspace.html`
- NDA workspace include: `theme/templates/contracts/nda_contract_workspace.html`

Shared workspace pattern:

- workflow/contract header
- workflow timeline
- generated draft with section anchors
- source-backed clause labels
- governance rail
- risk cards
- approval route cards
- audit trail preview
- explicit workflow actions

## Command Center work item pattern

All three service modules persist a `CommandCenterWorkItem` with:

- workflow title
- contract type flag
- current stage
- owner label
- highest risk signal
- blocking issue
- next action
- `action_path` to `/contracts/workflows/<id>/`

Dashboard rendering should treat DPA, MSA, and NDA as one workflow-first operating model, differing in risk personality, approval routing, and self-serve eligibility.

## Clause id / source label pattern

Both cockpit previews and workspaces use stable section ids for field/risk-to-clause linking and source labels for governance provenance.

Shared expectations:

- section ids stay stable once published
- risk cards point at section ids
- source labels use the same vocabulary:
  - Approved template
  - Approved clause library
  - AI-assisted suggestion
  - Risk-triggered fallback

## Alignment checkpoints

Avoidable divergence to watch without forcing a broad refactor:

- field definition grouping and section ordering
- merge-field/live-preview substitution behavior
- section id naming used by risk-to-clause linking
- source badge vocabulary and tone usage
- readiness completion and blocker logic
- risk chip phrasing and severity mapping
- approval reasoning copy
- workspace header, governance rail, audit preview, and action placement
- Command Center workflow row fields and workspace linking

The current code intentionally keeps DPA, MSA, and NDA in separate modules, but they should continue to behave as one reference pattern.

## E2E note

Parallel Playwright runs against the SQLite E2E database can emit non-fatal `database is locked` warnings during login audit writes. Current mitigation is to keep the smoke green and deterministic through seeded startup; a fuller stabilization pass should consider serializing the affected auth path, using a separate test database per worker, or reducing worker concurrency for the impacted specs.
