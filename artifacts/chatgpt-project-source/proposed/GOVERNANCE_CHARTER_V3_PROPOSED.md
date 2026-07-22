# CLM One Governance Charter v3

> **PROPOSED — NOT YET APPROVED**
>
> This document is a **proposed amendment**. It does **not** supersede the
> active Governance Charter at
> [`GOVERNANCE_CHARTER.md`](GOVERNANCE_CHARTER.md).
>
> Until this proposal is formally approved through the repository governance
> process, agents and contributors must treat
> [`GOVERNANCE_CHARTER.md`](GOVERNANCE_CHARTER.md) as the sole authoritative
> Charter. Do not implement this document as if it were already active,
> approved, canonical, or effective.

**Status:** Proposed amendment  
**Version:** 3.0  
**Effective date:** Pending approval  
**Supersedes:** Existing CLM One Governance Charter only after formal approval

## 1. Mandate

Once approved, the CLM One Governance Charter is the constitutional source of truth for the product’s operating model, domain model, architecture, user experience, security, privacy, artificial intelligence, engineering, quality, and delivery governance.

CLM One must evolve as one coherent platform. It must not become a loose collection of screens, duplicated data models, local rules, temporary workarounds, disconnected modules, or agent-generated implementation preferences.

Once this amendment is approved, when uncertainty exists, this Charter provides the default governing position.

## 2. Product identity

The official product name is **CLM One**.

`CLMOne` may be used only where technical constraints prevent spaces, such as:

- repository and package names;
- domains and URLs;
- environment variables;
- database identifiers;
- service names;
- namespaces;
- CSS prefixes;
- machine-readable configuration.

All customer-facing interfaces and materials must use **CLM One**.

## 3. Product definition

CLM One is a governance-first contract operating system that manages the complete contract lifecycle:

1. configure governed contracting processes;
2. request or launch contract work;
3. generate first-party documents or ingest third-party paper;
4. collaborate and negotiate;
5. perform legal, privacy, commercial, finance, security, and business review;
6. collect approvals;
7. execute through signature or accepted alternative evidence;
8. archive the final contract as a durable record;
9. manage obligations, renewals, amendments, and related agreements;
10. provide portfolio intelligence, auditability, and operational control.

The platform must preserve a clear distinction between reusable configuration, live work, and durable records.

## 4. Constitutional principles

### 4.1 One lifecycle, one object graph

Every major capability must connect to the same canonical contract lifecycle and domain model.

Modules may present different views of the same objects, but they must not create competing versions of contract, counterparty, task, approval, property, obligation, or audit data.

### 4.2 Configuration is not execution

Reusable configuration must remain distinct from live work.

- Workflow definitions are reusable blueprints.
- Workflow versions are immutable published or editable draft configurations.
- Workflow instances are live executions.
- Contract records are durable post-execution or imported records.

These concepts must never be collapsed into one ambiguous object.

### 4.3 Published configuration is immutable

A published workflow, template, playbook, clause version, or policy version may not be edited in place.

Changes must create a new draft version. Historical versions remain available for audit and comparison.

### 4.4 Blocking issues block publication

A configuration with blocking validation issues must not be publishable through the normal release path.

If an already published version later becomes invalid, the platform must record:

- the reason;
- detection time;
- affected usage;
- launch restrictions;
- remediation path;
- relevant exception or incident.

### 4.5 Data is governed centrally

Canonical definitions for contract types, properties, clauses, entities, relationship types, obligation types, roles, and statuses must be managed centrally.

Feature teams may consume canonical data definitions. They may not silently create near-duplicates.

### 4.6 Access follows the object

Permissions must be enforced consistently across:

- user interface;
- APIs;
- search;
- analytics;
- exports;
- integrations;
- AI retrieval;
- audit views;
- notifications.

A user must never learn restricted contract information through metadata leakage.

### 4.7 Auditability is a product capability

Material actions must produce immutable audit events.

No material object may appear without an attributable creation event. No published object may lack a publication event.

### 4.8 AI assists, humans govern

AI may extract, classify, compare, draft, summarize, recommend, and route within approved boundaries.

AI must not silently:

- change authoritative contract data;
- publish workflow configuration;
- approve contracts;
- sign contracts;
- create permanent policy;
- override permissions;
- alter audit history.

Human verification is required where AI output becomes authoritative.

### 4.9 Work is role-aware

Personal work, specialist work, portfolio management, and administration are distinct surfaces:

- **My Work:** personal actions requiring the current user;
- **Specialist workspaces:** deep execution for reviews, privacy, obligations, and other disciplines;
- **Contracts:** complete accessible contract inventory;
- **Command Center:** organization-level risk and operational control;
- **Settings and administration:** configuration, access, security, and governance.

### 4.10 Enterprise capability must remain comprehensible

CLM One may become powerful without becoming conceptually muddy.

Every important object must have:

- one canonical name;
- one clear owner;
- one lifecycle;
- one source of truth;
- explicit permissions;
- explicit audit behavior.

## 5. Authority order

When artifacts conflict, the following order applies:

1. Current CLM One Governance Charter
2. Approved Charter amendments
3. Approved PDRs and ADRs
4. Binding legal, privacy, security, and regulatory obligations
5. Approved product and architecture specifications
6. Approved design-system documentation
7. Approved requirements and acceptance criteria
8. Current implementation
9. Informal discussions, chat messages, and personal preferences

Existing code is evidence of prior implementation, not proof of correctness.

## 6. Anti-drift mandate

CLM One must be protected against:

- product drift;
- domain-model drift;
- architecture drift;
- design drift;
- security drift;
- terminology drift;
- AI-behavior drift;
- data-definition drift.

A local implementation may not establish a new platform rule without an approved decision.

## 7. Mandatory decision records

Use a PDR for material product decisions involving:

- product boundaries;
- lifecycle behavior;
- user roles;
- workflow stages;
- navigation;
- statuses;
- permissions visible to users;
- commercial packaging;
- customer-facing behavior.

Use an ADR for material technical decisions involving:

- aggregate boundaries;
- services;
- database ownership;
- event contracts;
- APIs;
- authentication;
- authorization;
- cryptography;
- infrastructure;
- reliability;
- scalability;
- deployment;
- integration patterns.

Use a combined ADR/PDR when the decision changes both product behavior and system structure.

## 8. Single pull request rule

When implementation changes an active governance rule, the same pull request must contain, where applicable:

- Charter amendment;
- PDR or ADR;
- implementation;
- migrations;
- automated tests;
- documentation;
- agent context;
- design-system guidance;
- migration and rollback plan;
- rationale and consequences.

Governance may not be updated later as housekeeping.

## 9. Temporary exceptions

Temporary deviations require an approved exception containing:

- unique ID;
- affected rule;
- owner;
- scope;
- rationale;
- risk;
- safeguards;
- approval;
- start date;
- hard expiry date;
- exit plan;
- status.

An exception without an owner and expiry date is invalid.

Repeated exceptions do not become policy through repetition.

## 10. Release completeness

A material capability is not release-ready merely because it works technically.

Before release, verify:

- Charter alignment;
- decision records;
- domain-model consistency;
- permissions;
- privacy;
- security;
- validation behavior;
- audit events;
- automated tests;
- manual tests;
- accessibility;
- terminology;
- migration;
- rollback;
- documentation;
- agent context;
- support and operational readiness.

## 11. Amendment procedure

Every amendment must state:

- affected section;
- replacement text;
- reason;
- originating decision record;
- expected consequences;
- approver;
- approval date;
- effective date;
- migration actions.

Previous versions remain available for audit.

## 12. Final governing principle

CLM One is a governance platform and must be governed with the discipline it promises customers.

Every material decision must be intentional, traceable, reviewable, secure, testable, consistent, and reversible where appropriate.
