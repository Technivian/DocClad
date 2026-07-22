# CLM One Engineering Guardrails

**Status:** Accepted  
**Purpose:** Prevent local implementation choices from weakening the platform.

**Authority:** Accepted supporting documentation ([PDR-0003](../governance/decisions/pdr/PDR-0003-documentation-operating-model.md)). Does not supersede the active Governance Charter at [`../governance/GOVERNANCE_CHARTER.md`](../governance/GOVERNANCE_CHARTER.md). Charter v3 remains separately proposed.

## 1. No duplicate domain models

Before creating a model, field, enum, or table, check whether the concept already exists canonically.

## 2. No page-owned business logic

Business rules belong in domain or application services, not templates, view components, serializers, or controllers.

## 3. No direct cross-module table access

Use public application services, repositories, and events.

## 4. Published objects are immutable

Enforce immutability in domain logic and persistence, not only in the UI.

## 5. All material actions emit audit events

Audit is part of the transaction boundary where practical.

## 6. Authorization is server-side

Client-side hiding is not authorization.

## 7. Search and analytics are permission-aware

Indexing and projection layers must preserve access constraints.

## 8. Every persistent object has provenance

Record:

- creator;
- creation time;
- source;
- workspace;
- version where applicable.

## 9. Stable identifiers

Use opaque stable IDs. Do not expose sequential IDs where that increases enumeration risk.

## 10. Canonical enums

Statuses and types come from approved canonical definitions.

## 11. Migrations are reversible where possible

Every material migration requires:

- forward plan;
- rollback or compensating plan;
- data verification;
- operational impact.

## 12. Event contracts are versioned

Breaking event changes require versioning and migration.

## 13. External failures are explicit

Integrations require idempotency, retries, timeouts, and dead-letter handling.

## 14. AI is isolated behind governed services

Do not call model providers directly from feature code.

## 15. Feature flags do not replace governance

A feature flag controls exposure. It does not legalize a conflicting architecture or domain model.

## 16. Tests protect invariants

Mandatory invariant tests include:

- tenant isolation;
- published immutability;
- access revocation;
- approval-state binding;
- audit append-only behavior;
- AI non-authority;
- workflow version pinning;
- record provenance;
- obligation ownership.

## 17. Agent instructions

AI coding agents must receive:

- Governance Charter;
- relevant domain docs;
- applicable ADRs and PDRs;
- module boundaries;
- acceptance criteria;
- test requirements.

Agents must not infer new platform rules from current code alone.
