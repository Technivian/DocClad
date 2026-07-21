# CLM One Product Operating Model

**Status:** Accepted  
**Purpose:** Define the complete product model, users, lifecycle, and operating principles.

**Authority:** Accepted supporting documentation ([PDR-0003](decisions/pdr/PDR-0003-documentation-operating-model.md)). Does not supersede the active Governance Charter at [`GOVERNANCE_CHARTER.md`](GOVERNANCE_CHARTER.md). Charter v3 remains separately proposed.

## 1. Product thesis

CLM One is a governed contract operating system for organizations that need contracting to be faster without becoming opaque, uncontrolled, or dependent on tribal knowledge.

The platform must combine:

- contract request and intake;
- document generation and ingestion;
- workflow automation;
- negotiation and review;
- approval routing;
- privacy and risk governance;
- signatures;
- contract records;
- entities and relationships;
- obligations and renewals;
- portfolio intelligence;
- integrations;
- enterprise administration;
- AI assistance with human control.

The product should match the depth of category-leading CLM platforms while being more coherent, more explicit about governance, and easier to reason about.

## 2. Primary user groups

### Business requester

Needs to start a contract, answer governed questions, provide documents, and track progress without understanding legal operations.

### Contract owner

Owns the business outcome, coordinates participants, provides information, and remains accountable for the contract relationship.

### Legal reviewer

Reviews deviations, negotiates language, uses clauses and playbooks, and makes or recommends legal decisions.

### Privacy reviewer

Evaluates data processing, transfers, subprocessors, legal basis, security, and privacy risk.

### Finance or commercial approver

Reviews value, pricing, liability exposure, payment terms, budget, and commercial exceptions.

### Signer

Executes the final agreement within delegated authority.

### Legal operations or contract administrator

Configures workflows, templates, properties, roles, policies, data, permissions, integrations, and reporting.

### Executive or governance leader

Needs organization-wide visibility into risk, throughput, bottlenecks, value, renewals, and obligations.

### Auditor or security reviewer

Needs complete, immutable, permission-aware evidence.

## 3. End-to-end lifecycle

### Stage 1: Configure

Authorized administrators create and publish:

- contract types;
- intake forms;
- workflow definitions;
- templates;
- clauses;
- playbooks;
- approval policies;
- signature rules;
- archival rules;
- access policies;
- property definitions;
- obligation types.

### Stage 2: Request

A user launches a governed contract request.

The system captures:

- contract type;
- counterparty;
- requester;
- business owner;
- value;
- jurisdiction;
- governing law;
- risk inputs;
- privacy inputs;
- required documents;
- related agreements.

### Stage 3: Generate or ingest

The request either:

- generates first-party paper from a template;
- accepts third-party paper;
- creates multiple related documents;
- references an existing master agreement;
- launches a click-to-accept or lightweight acceptance flow where permitted.

### Stage 4: Review and negotiate

The system coordinates:

- internal review;
- external negotiation;
- comments;
- document versions;
- redlines;
- clause comparison;
- AI-assisted review;
- playbook guidance;
- directed questions;
- issue resolution.

### Stage 5: Approve

Approvals are resolved from policies, conditions, risk, value, deviations, role, and authority.

Approval validity must be bound to the approved state of the contract. Material changes may reset approval.

### Stage 6: Sign

The system prepares and executes a signature packet or captures another approved form of acceptance.

### Stage 7: Record

The final executed contract becomes a durable contract record containing:

- final documents;
- canonical metadata;
- participants;
- approvals;
- signatures;
- activity;
- relationships;
- entities;
- obligations;
- renewal data;
- source workflow.

Historical contracts may be imported directly as records with provenance.

### Stage 8: Operate

Users manage:

- obligations;
- notices;
- renewals;
- expiry;
- amendments;
- terminations;
- usage;
- performance;
- compliance;
- related records.

### Stage 9: Learn and govern

Data feeds:

- My Work;
- specialist workspaces;
- Contracts;
- Command Center;
- reporting;
- integrations;
- AI extraction and verification;
- operational improvement.

## 4. Product surfaces

### My Work

The current user’s actionable queue.

### Contracts

The complete accessible contract inventory, covering active work and durable records while preserving their lifecycle distinction.

### Contract Workspace

The operational workspace for one contract or contract process.

### Workflow Designer

The configuration engine for reusable contract processes.

### Templates and Playbooks

Governed document templates, clauses, positions, fallbacks, and negotiation guidance.

### Data Manager

The canonical schema registry for contract data.

### Entities

Counterparty and organization intelligence.

### Obligations

Post-signature commitments, ownership, deadlines, and evidence.

### Command Center

Organization-level operational and risk visibility.

### Settings and Administration

Identity, roles, permissions, security, policies, integrations, and workspace configuration.

## 5. Product differentiation

CLM One should not compete by copying page-for-page.

It should differentiate through:

- explicit governance;
- a clean canonical object model;
- stronger distinction between personal work and portfolio views;
- clearer lifecycle states;
- traceable AI;
- role-aware privacy;
- immutable configuration history;
- coherent terminology;
- first-class testing and simulation;
- first-class auditability;
- lower conceptual debt.

## 6. Non-goals

CLM One is not:

- a generic document drive;
- a task manager with contract attachments;
- a visual flowchart tool;
- a legal chatbot detached from contract data;
- an ungoverned form builder;
- a CRM replacement;
- an ERP replacement;
- a fully autonomous legal decision-maker.
