# CLM One Canonical Domain Model

**Status:** Accepted  
**Purpose:** Define the authoritative objects, relationships, invariants, and ownership boundaries.

**Authority:** Accepted supporting documentation ([PDR-0003](../governance/decisions/pdr/PDR-0003-documentation-operating-model.md)). Does not supersede the active Governance Charter at [`../governance/GOVERNANCE_CHARTER.md`](../governance/GOVERNANCE_CHARTER.md). Charter v3 remains separately proposed.

## 1. Domain model rule

Every persistent business concept must have one canonical definition.

UI labels may vary by context only when an approved product decision allows it. Storage models, APIs, events, and permissions must refer to the canonical object.

## 2. Core objects

### 2.1 Workspace

The tenant and primary security boundary.

Contains:

- members;
- groups;
- roles;
- settings;
- contract data;
- workflow configuration;
- integrations;
- audit events.

### 2.2 User

An authenticated person.

A user may belong to multiple workspaces but receives workspace-specific membership and permissions.

### 2.3 Workspace Membership

Joins a user to a workspace.

Contains:

- workspace role;
- permission set;
- status;
- start and end date;
- delegation;
- restrictions.

### 2.4 Group

A reusable set of workspace members used for access, assignment, approval, and notification.

### 2.5 Role Definition

A canonical responsibility in a process, such as:

- requester;
- contract owner;
- legal reviewer;
- privacy reviewer;
- finance approver;
- signer;
- archiver.

Role definitions are distinct from workspace permissions.

### 2.6 Contract Type

A governed classification such as NDA, MSA, DPA, SOW, or supplier agreement.

Defines default schema, workflow, templates, access behavior, and lifecycle expectations.

### 2.7 Property Definition

A canonical data field reusable across workflows, records, search, analytics, integrations, and AI.

Examples:

- contract value;
- currency;
- effective date;
- governing law;
- auto-renewal;
- notice period;
- risk level.

### 2.8 Entity

A reusable party such as a company, supplier, customer, partner, government body, or individual.

Contains:

- legal name;
- aliases;
- identifiers;
- jurisdiction;
- entity type;
- parent relationships;
- contacts;
- risk information;
- linked contracts.

### 2.9 Entity Relationship

A typed relationship between entities, such as parent, subsidiary, affiliate, supplier, or customer.

### 2.10 Workflow Definition

The stable identity of a reusable workflow configuration.

It owns a sequence of Workflow Versions.

### 2.11 Workflow Version

A versioned workflow configuration.

States:

- Draft
- In validation
- Ready to publish
- Published
- Superseded
- Archived

A published version is immutable.

### 2.12 Workflow Instance

A live execution launched from one immutable Workflow Version.

Contains:

- inputs;
- participants;
- resolved assignments;
- tasks;
- approvals;
- documents;
- decisions;
- current state;
- activity;
- output record.

### 2.13 Contract Record

The durable representation of a contract.

A record may originate from:

- completed workflow instance;
- imported historical contract;
- external integration;
- migration.

A record is not the same as a workflow instance.

### 2.14 Contract Relationship

A typed relationship between contract records:

- master agreement;
- statement of work;
- amendment;
- renewal;
- addendum;
- termination;
- supersedes;
- related agreement.

### 2.15 Document

A logical document within a workflow or record.

### 2.16 Document Version

An immutable version of a document with provenance, checksum, author, timestamp, and source.

### 2.17 Template

A governed document source used to generate first-party paper.

Templates are versioned and may reference clauses and properties.

### 2.18 Clause Type

A canonical legal or commercial concept, such as limitation of liability or audit rights.

### 2.19 Clause Version

A versioned approved clause text or clause variant.

May be designated as:

- preferred;
- acceptable;
- fallback;
- prohibited;
- informational.

### 2.20 Playbook

A governed set of positions, fallback rules, escalation criteria, and review guidance.

### 2.21 Playbook Rule

A rule that evaluates detected or missing language and returns guidance, risk, fallback, or escalation.

### 2.22 Work Item

An actionable unit assigned to a person or group.

Types include:

- task;
- review;
- approval;
- question;
- privacy assessment;
- obligation action;
- correction;
- signature action.

My Work is a view over authorized Work Items.

### 2.23 Approval Requirement

A resolved requirement that approval is needed from a role, user, or group.

### 2.24 Approval Decision

An immutable approve, reject, return, abstain, or revoke decision tied to a specific contract state or document version.

### 2.25 Signature Packet

The governed collection of documents, signers, order, fields, provider, and evidence required for execution.

### 2.26 Signature Evidence

The durable evidence of signature or accepted alternative execution.

### 2.27 Obligation Type

A canonical definition of a post-signature commitment.

### 2.28 Obligation

A contract-linked commitment with owner, due date, status, evidence, recurrence, and escalation.

### 2.29 Reminder

A notification schedule linked to a contract, obligation, renewal, or date property.

### 2.30 Audit Event

An immutable event recording who or what performed a material action, on which object, when, from where, and with what before/after values.

### 2.31 AI Suggestion

A non-authoritative AI output linked to source evidence, confidence, model metadata, reviewer status, and final disposition.

### 2.32 Integration Connection

A governed connection to an external system.

### 2.33 Exception

A temporary approved deviation from platform governance.

## 3. Critical invariants

1. A Workflow Instance always references exactly one immutable Workflow Version.
2. A published Workflow Version is never edited in place.
3. A Contract Record may exist without a Workflow Instance, but provenance is mandatory.
4. A Work Item must reference an authorized object and a valid assignee.
5. An Approval Decision must reference the state or document version it approved.
6. A Document Version is immutable.
7. An Audit Event is immutable.
8. AI Suggestions are never authoritative until verified or approved by an allowed action.
9. Restricted object metadata must not leak through search, analytics, notifications, exports, or AI.
10. Canonical Property Definitions may be deprecated but not silently repurposed.
11. Restoring a historical version creates a new draft.
12. Deleting referenced configuration must be blocked or handled through governed deprecation.

## 4. Aggregate boundaries

Recommended aggregates:

- Workspace and Membership
- Workflow Definition and Workflow Versions
- Workflow Instance
- Contract Record and Contract Relationships
- Entity
- Template
- Clause Type and Clause Versions
- Playbook
- Obligation
- Signature Packet
- Work Item
- Audit Event

Cross-aggregate coordination should use explicit application services and domain events rather than hidden database coupling.

## 5. Canonical status vocabulary

### Workflow Version

Draft, Validating, Ready, Published, Superseded, Archived

### Workflow Instance

Requested, In review, Awaiting approval, Awaiting signature, Executed, Archived, Withdrawn, Cancelled, Blocked

### Contract Record

Draft record, Active, Expiring, Expired, Terminated, Superseded, Archived

### Work Item

Assigned, Due soon, Due today, Overdue, Blocked, Returned, Rejected, Completed, Cancelled

### Obligation

Planned, Open, Due soon, Due, Overdue, Completed, Waived, Cancelled

Status additions require a PDR.
