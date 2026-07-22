# CLM One Platform and Module Architecture

**Status:** Accepted  
**Purpose:** Define the major modules, responsibilities, boundaries, and dependency direction.

**Authority:** Accepted supporting documentation ([PDR-0003](../governance/decisions/pdr/PDR-0003-documentation-operating-model.md)). Does not supersede the active Governance Charter at [`../governance/GOVERNANCE_CHARTER.md`](../governance/GOVERNANCE_CHARTER.md). Charter v3 remains separately proposed.

## 1. Architecture thesis

CLM One must be modular without becoming fragmented.

Each module owns a coherent domain responsibility, but all modules operate on the same canonical lifecycle and object graph.

The architecture should begin as a well-structured modular monolith unless scale or isolation requirements justify extraction. Service boundaries must follow domain ownership, not page boundaries.

## 2. Core platform modules

### 2.1 Identity and Workspace

Owns:

- users;
- memberships;
- groups;
- workspace roles;
- authentication;
- MFA;
- sessions;
- SCIM and SSO;
- delegation;
- workspace settings.

### 2.2 Access Control

Owns:

- authorization policies;
- object-level access;
- role resolution;
- ethical walls;
- confidentiality restrictions;
- permission checks;
- policy evaluation.

Access Control is cross-cutting but must have one authoritative implementation.

### 2.3 Contract Intake

Owns:

- launch eligibility;
- request forms;
- prefilled intake;
- request validation;
- draft requests;
- counterparty input;
- intake provenance.

### 2.4 Workflow Configuration

Owns:

- workflow definitions;
- workflow versions;
- steps;
- conditions;
- assignments;
- validation;
- simulation definitions;
- publication;
- restoration.

### 2.5 Workflow Runtime

Owns:

- workflow instances;
- state transitions;
- work item creation;
- assignment resolution;
- SLA timers;
- escalation;
- blocking;
- completion.

### 2.6 Documents

Owns:

- logical documents;
- document versions;
- upload;
- generation;
- redlines;
- merge;
- checksum;
- provenance;
- document access.

### 2.7 Templates and Clauses

Owns:

- document templates;
- template versions;
- clause types;
- clause versions;
- approved variants;
- generation mappings;
- deprecation.

### 2.8 Playbooks and Review Intelligence

Owns:

- playbooks;
- playbook versions;
- rules;
- positions;
- fallbacks;
- escalation criteria;
- review guidance;
- AI-assisted clause comparison.

### 2.9 Review and Collaboration

Owns:

- comments;
- directed questions;
- review status;
- participant communication;
- negotiation turns;
- issue tracking;
- reviewer actions.

### 2.10 Approval

Owns:

- approval requirements;
- approver resolution;
- decision state;
- validity;
- reset behavior;
- delegation;
- evidence.

### 2.11 Privacy Review

Owns:

- privacy assessment;
- processing activities;
- data categories;
- data subjects;
- transfer evaluation;
- subprocessors;
- risk and mitigations;
- privacy decisions.

Privacy Review integrates with Workflow Runtime and Approval but retains its own specialist model.

### 2.12 Signature

Owns:

- signature packets;
- signers;
- order;
- provider integration;
- signature fields;
- evidence;
- failure and expiry handling;
- wet-sign fallback.

### 2.13 Contract Records

Owns:

- durable records;
- record provenance;
- final metadata;
- archival;
- contract status;
- record access;
- imported records.

### 2.14 Entities and Relationships

Owns:

- entities;
- aliases;
- identifiers;
- parent-child relationships;
- contacts;
- contract relationships;
- entity families.

### 2.15 Obligations and Renewals

Owns:

- obligation types;
- obligations;
- renewal dates;
- notice periods;
- reminders;
- evidence;
- recurrence;
- escalation.

### 2.16 Data Manager

Owns canonical definitions for:

- properties;
- contract types;
- entity types;
- relationship types;
- obligation types;
- enums;
- data quality;
- deprecation;
- schema usage.

### 2.17 Search and Repository Intelligence

Owns:

- full-text search;
- structured filtering;
- OCR;
- duplicate detection;
- saved views;
- indexing;
- search permissions;
- verification queues.

### 2.18 My Work

Owns no duplicate business objects.

It projects authorized Work Items from workflow, approval, privacy, review, obligation, and signature domains into one personal queue.

### 2.19 Command Center and Insights

Owns:

- operational projections;
- portfolio metrics;
- bottlenecks;
- risk views;
- SLA views;
- renewal exposure;
- data quality metrics.

It does not own source-of-truth contract data.

### 2.20 Audit and Evidence

Owns:

- append-only audit events;
- correlation IDs;
- export;
- retention;
- integrity;
- administrative audit access;
- evidence packaging.

### 2.21 Integrations

Owns:

- connections;
- credentials references;
- mappings;
- webhooks;
- retries;
- dead-letter handling;
- external IDs;
- sync state;
- integration audit events.

### 2.22 AI Orchestration

Owns:

- AI policies;
- allowed use cases;
- prompt and model configuration;
- source retrieval;
- output provenance;
- confidence;
- human verification;
- cost and usage controls;
- redaction.

## 3. Dependency direction

Preferred dependency flow:

- UX calls application services.
- Application services coordinate domain modules.
- Domain modules publish events.
- Projections support My Work, Command Center, search, and analytics.
- Integrations consume and emit governed events.
- AI reads only authorized, policy-approved context.

No module may reach directly into another module’s tables as a shortcut.

## 4. Event model

Important events include:

- workflow.version.published;
- workflow.instance.launched;
- work_item.assigned;
- document.version.created;
- approval.requested;
- approval.decided;
- signature.sent;
- signature.completed;
- contract.record.created;
- obligation.created;
- obligation.overdue;
- contract.renewal_due;
- access.revoked;
- ai.suggestion.created;
- ai.suggestion.verified.

Events require:

- event ID;
- workspace ID;
- actor;
- object;
- timestamp;
- correlation ID;
- schema version;
- source;
- payload classification.

## 5. Build rule

Do not create a new module merely because a new page exists.

Pages are views. Modules are domain ownership boundaries.
