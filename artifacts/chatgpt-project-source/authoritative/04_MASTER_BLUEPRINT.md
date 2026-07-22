# CLM One Master Blueprint

**Status:** Accepted  
**Version:** 2.0  
**Date:** 21 July 2026

**Authority:** Accepted supporting documentation ([PDR-0003](../governance/decisions/pdr/PDR-0003-documentation-operating-model.md)). Does not supersede the active Governance Charter at [`../governance/GOVERNANCE_CHARTER.md`](../governance/GOVERNANCE_CHARTER.md). Charter v3 remains separately proposed.

## Vision

Build CLM One into a formidable enterprise contract operating system that combines category-leading lifecycle depth with unusually strong governance, conceptual clarity, auditability, and role-aware user experience.

## The product spine

> Configure → Request → Generate or ingest → Review → Approve → Sign → Record → Operate → Renew or terminate

Every module must strengthen this spine.

## The canonical object chain

> Workflow Definition → Workflow Version → Workflow Instance → Contract Record

Supporting objects:

- Workspace
- Membership
- Group
- Role Definition
- Contract Type
- Property Definition
- Entity
- Document
- Document Version
- Template
- Clause Type
- Clause Version
- Playbook
- Work Item
- Approval Requirement
- Approval Decision
- Signature Packet
- Obligation
- Audit Event
- AI Suggestion

## The major capabilities

1. My Work
2. Contracts
3. Contract Workspace
4. Workflow Designer
5. Templates and Clauses
6. Negotiation Playbooks
7. Data Manager
8. Entities and Relationships
9. Review and Collaboration
10. Approvals
11. Privacy Review
12. Signatures
13. Records and Repository Intelligence
14. Obligations and Renewals
15. Command Center and Insights
16. Integrations
17. Security, Access, and Audit
18. AI Orchestration

## Non-negotiable invariants

- Published configuration is immutable.
- Blocking validation issues block publication.
- Every live workflow is pinned to one immutable workflow version.
- Every durable contract record has provenance.
- Approval is tied to the approved contract state.
- Every material action creates an immutable audit event.
- AI is non-authoritative until governed verification.
- Search, analytics, exports, notifications, and AI enforce the same access rules as the source object.
- Canonical data definitions are centrally governed.
- Historical restoration creates a new draft.

## Product surfaces

### My Work

Personal actionable queue only.

### Contracts

Complete accessible contract inventory.

### Command Center

Organization-wide operations, risk, and governance.

### Specialist workspaces

Deep review, privacy, and obligation operations.

### Configuration

Workflow Designer, Templates and Playbooks, Data Manager, Entities, Settings.

## Competitive posture

Do not copy competitors page-for-page.

Adopt the structural strengths of leading CLM platforms:

- powerful workflow configuration;
- reusable structured data;
- document and clause governance;
- lifecycle continuity;
- entity and relationship intelligence;
- post-signature management;
- integration depth;
- AI grounded in contract context.

Improve on them through:

- clearer object boundaries;
- stronger personal work design;
- explicit configuration testing;
- immutable governance history;
- traceable AI;
- coherent terminology;
- fewer duplicated destinations;
- visible policy and access reasoning.

## Build order

1. Constitutional and domain foundation
2. Contract operating core
3. Workflow depth
4. Templates, clauses, and playbooks
5. Records, entities, and relationships
6. Obligations and renewals
7. AI and intelligence
8. Enterprise platform controls
9. Portfolio command

## Release standard

A feature is complete only when:

- product behavior is approved;
- domain ownership is clear;
- permissions are correct;
- audit events exist;
- failure states exist;
- migrations and rollback exist;
- automated tests pass;
- accessibility is verified;
- operational evidence exists;
- documentation and agent context are current.

CLM One should become powerful by accumulating coherent capabilities, not by accumulating pages.
