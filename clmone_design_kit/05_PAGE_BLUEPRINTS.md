# Page Blueprints

## Dashboard

Purpose: legal operations command desk.

It should answer: what needs attention today?

Layout:

- header: `Dashboard`
- subtitle: `Track contract work, approvals, risk, and lifecycle activity.`
- actions: `View Repository`, `+ New Contract`
- priority action strip
- main priority work queue
- lifecycle status overview
- right rail with deadlines, risk watch, recent activity

Priority cards:

- Needs Legal Review: 8
- Awaiting Approval: 5
- Signature Pending: 3
- Expiring Soon: 6

Main table: `Priority Work Queue`

Columns:

- Contract
- Counterparty
- Stage
- Owner
- Risk
- Due
- Action

Rows:

- Supplier Agreement | Northline B.V. | Legal Review | Sarah | Medium | Today | Review
- DPA Addendum | CloudCore Ltd. | DPA Review | Legal | High | Overdue | Open
- SaaS Agreement | BrightOps | Approval | Finance | Low | 2 days | Approve
- NDA Renewal | Delta Partners | Signature | Marc | Low | 5 days | Track

Right rail:

- Upcoming Deadlines
- Risk Watch
- Recent Activity

Avoid charts unless requested by product requirements.

## New Contract Request

Purpose: governed legal intake workspace.

Use:

- lifecycle rail: Draft, Legal Review, Business Approval, Signature, Executed
- main card: `Request Intake`
- right rail: completion, routing preview, what happens next

Fields:

- Title *
- Contract type *
- Status *
- Counterparty
- Value
- Currency *
- Governing law
- Jurisdiction

Right rail:

- Request Completion
- Routing Preview
- What Happens Next

## Contract Workspace

Purpose: active contract work management.

Layout:

- header: `Contract Workspace`
- subtitle: `Manage active contract work across review, approval, and signature.`
- action: `+ New Contract`
- tabs or filter chips: All, Draft, Legal Review, Approval, Signature, Blocked
- main table: active contracts
- right rail: workload summary, blocked items, SLA/deadline watch

Table columns:

- Contract
- Counterparty
- Stage
- Owner
- Last Activity
- Due
- Risk
- Action

## Repository

Purpose: source of truth for executed and stored contracts.

Layout:

- header: `Repository`
- subtitle: `Search, filter, and manage the contract record.`
- actions: Upload Document, Export
- search and filters: counterparty, type, status, owner, effective date, expiry date
- main table: repository records
- right rail: missing metadata, expiring soon, recently added

Table columns:

- Contract
- Counterparty
- Type
- Status
- Effective Date
- Expiry/Renewal
- Owner
- Metadata

## Tasks

Purpose: personal/team action list.

Layout:

- header: `Tasks`
- subtitle: `Track contract actions assigned to you or your team.`
- filters: My tasks, Team tasks, Overdue, Due today, Completed
- table/list grouped by due date
- right rail: task load, overdue, recent completions

Task row fields:

- Task
- Related contract
- Assignee
- Due
- Priority
- Status

## Workflows

Purpose: workflow template and automation management.

Layout:

- header: `Workflows`
- subtitle: `Design and manage contract routing patterns.`
- actions: New Workflow Template
- cards/table for workflow templates
- right rail: active workflow usage, recent changes, unpublished drafts

Template fields:

- Workflow name
- Contract types
- Steps
- Owner
- Last updated
- Status

## Approvals

Purpose: approval queue.

Layout:

- header: `Approvals`
- subtitle: `Review approval requests and decision history.`
- tabs: Pending, Approved, Rejected, Delegated
- main table: approval requests
- right rail: approval SLA, overdue approvals, escalation rules

Columns:

- Request
- Contract
- Approver
- Stage
- Due
- Risk
- Decision

## Signature Requests

Purpose: signature tracking.

Layout:

- header: `Signature Requests`
- subtitle: `Track contracts prepared, sent, and completed for signature.`
- status filters: Draft, Sent, Viewed, Signed, Declined, Expired
- main table
- right rail: pending signatures, expiring envelopes, recent completions

Columns:

- Contract
- Counterparty
- Signers
- Status
- Sent
- Due
- Action

## Risk Register

Purpose: contract and compliance risk register.

Layout:

- header: `Risk Register`
- subtitle: `Track legal, commercial, privacy, and compliance risks.`
- actions: Add Risk
- filters: High, Medium, Low, Open, Accepted, Mitigated
- main table
- right rail: high-risk count, overdue mitigations, missing owner

Columns:

- Risk
- Contract
- Category
- Severity
- Owner
- Mitigation
- Status
- Due

## Compliance

Purpose: compliance controls and evidence overview.

Layout:

- header: `Compliance`
- subtitle: `Monitor compliance obligations, controls, and evidence.`
- cards: Open controls, Evidence missing, Overdue reviews
- main table: controls/evidence
- right rail: compliance gaps, recent evidence, audit readiness

Columns:

- Control
- Area
- Owner
- Evidence
- Status
- Review Date

## Privacy

Purpose: privacy and data processing governance.

Layout:

- header: `Privacy`
- subtitle: `Manage privacy obligations, DPAs, and data-processing records.`
- cards: Open DPAs, Missing subprocessors, Review due
- table: privacy records
- right rail: DPA gaps, subprocessors, upcoming reviews

Columns:

- Record
- Counterparty
- Data category
- Processing role
- DPA status
- Review date
- Risk

## Audit Trail

Purpose: immutable system and contract activity evidence.

Layout:

- header: `Audit Trail`
- subtitle: `Review recorded actions, decisions, and system events.`
- filters: actor, entity, event type, date range
- main audit event list/table
- right rail: export options, event categories, integrity note

Columns:

- Time
- Actor
- Event
- Entity
- Source
- Details

Use monospaced detail snippets only when useful.

## DPA Reviews

Purpose: privacy/legal review workflow for DPAs.

Layout:

- header: `DPA Reviews`
- subtitle: `Review data processing agreements and privacy obligations.`
- tabs: New, In Review, Blocked, Completed
- main table
- right rail: missing clauses, high-risk reviews, recent decisions

Columns:

- DPA
- Counterparty
- Reviewer
- Risk
- Status
- Due
- Action

## Documents

Purpose: document library and attachment management.

Layout:

- header: `Documents`
- subtitle: `Manage contract documents, attachments, and supporting files.`
- actions: Upload Document
- filters: contract, type, uploaded by, date
- main table
- right rail: unattached documents, recent uploads, storage policy

Columns:

- Document
- Related contract
- Type
- Version
- Uploaded by
- Uploaded date
- Status
