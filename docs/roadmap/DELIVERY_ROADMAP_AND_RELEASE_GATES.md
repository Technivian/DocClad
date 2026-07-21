# CLM One Delivery Roadmap and Release Gates

**Status:** Accepted  
**Purpose:** Define the build sequence that produces depth without creating uncontrolled scope.

**Authority:** Accepted supporting documentation ([PDR-0003](../governance/decisions/pdr/PDR-0003-documentation-operating-model.md)). Does not supersede the active Governance Charter at [`../governance/GOVERNANCE_CHARTER.md`](../governance/GOVERNANCE_CHARTER.md). Charter v3 remains separately proposed.

## 1. Delivery principle

Build the platform in domain order, not page order.

A beautiful surface on an unstable domain model creates expensive rework.

## 2. Stage 0: Constitutional foundation

Deliver:

- Governance Charter v3 approval;
- canonical terminology;
- PDR and ADR process;
- exception process;
- module ownership;
- object IDs and audit conventions;
- permission model baseline.

Exit gate:

- no unresolved contradiction between Charter, domain model, and current pilot scope.

## 3. Stage 1: Contract operating core

Deliver:

- Workspace and Membership;
- Contract Type;
- canonical Property Definitions;
- Entity baseline;
- Workflow Definition and Version;
- Workflow Instance;
- Contract Record;
- Document and Document Version;
- Work Item;
- Audit Event;
- basic object-level access.

Primary surfaces:

- New Contract;
- My Work;
- Contracts;
- Contract Workspace;
- Workflow Designer.

Exit gate:

- a governed NDA or MSA can move from request to final record with complete audit history.

## 4. Stage 2: Workflow depth

Deliver:

- conditional forms;
- assignment resolution;
- approvals;
- SLA and escalation;
- signature packet;
- publication validation;
- simulation;
- version comparison;
- restoration as draft.

Exit gate:

- workflow configuration supports real role, value, risk, and document-based routing without custom code.

## 5. Stage 3: Templates, clauses, and playbooks

Deliver:

- template versioning;
- clause types and variants;
- negotiation playbooks;
- approval policies;
- document generation;
- review guidance.

Exit gate:

- a third-party contract can be compared against approved positions and escalated through governed rules.

## 6. Stage 4: Records, entities, and relationships

Deliver:

- imported records;
- entity profiles;
- parent and subsidiary relationships;
- contract families;
- amendments;
- SOW relationships;
- duplicate detection;
- full-text search.

Exit gate:

- users can understand the complete relationship between a counterparty and its contracts.

## 7. Stage 5: Obligations and renewals

Deliver:

- obligation types;
- owner and due date;
- recurrence;
- reminders;
- renewal and notice logic;
- evidence;
- obligation views;
- My Work integration.

Exit gate:

- post-signature work is owned, timed, auditable, and visible.

## 8. Stage 6: AI and intelligence

Deliver:

- extraction;
- verification queue;
- clause detection;
- playbook review;
- summaries;
- obligation extraction;
- natural-language search;
- governed AI policies.

Exit gate:

- AI outputs have provenance, confidence, authorization, and human verification.

## 9. Stage 7: Enterprise platform

Deliver:

- SAML;
- SCIM;
- advanced groups;
- ethical walls;
- audit export;
- SIEM integration;
- API;
- webhooks;
- integration framework;
- data residency controls;
- enterprise reporting.

Exit gate:

- platform satisfies enterprise deployment, security, support, and operational requirements.

## 10. Stage 8: Portfolio command

Deliver:

- Command Center;
- operational analytics;
- governance analytics;
- portfolio risk;
- bottlenecks;
- renewal exposure;
- data quality views;
- saved views;
- executive reporting.

Exit gate:

- leadership can govern the contract portfolio without bypassing source permissions.

## 11. Release gates for every stage

### Product

- defined user problem;
- approved PDR;
- clear lifecycle;
- canonical terminology;
- permission behavior;
- empty and error states.

### Architecture

- approved ADR where required;
- aggregate ownership;
- migration;
- rollback;
- event contracts;
- observability.

### Security and privacy

- threat review;
- authorization tests;
- data classification;
- audit coverage;
- retention behavior;
- export controls.

### Quality

- unit tests;
- integration tests;
- end-to-end critical paths;
- accessibility;
- performance;
- negative-path testing;
- evidence pack.

### Operations

- feature flags;
- support procedure;
- monitoring;
- incident ownership;
- backup;
- restore test;
- release notes.

## 12. Prioritization rule

Choose depth over breadth.

A smaller coherent lifecycle is more valuable than many disconnected modules.

Do not add a new major module until the objects and events it depends on are canonical and stable.
