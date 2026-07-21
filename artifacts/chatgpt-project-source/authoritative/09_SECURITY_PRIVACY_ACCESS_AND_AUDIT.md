# CLM One Security, Privacy, Access, and Audit

**Status:** Accepted  
**Purpose:** Define the enterprise control model.

**Authority:** Accepted supporting documentation ([PDR-0003](../governance/decisions/pdr/PDR-0003-documentation-operating-model.md)). Does not supersede the active Governance Charter at [`../governance/GOVERNANCE_CHARTER.md`](../governance/GOVERNANCE_CHARTER.md). Charter v3 remains separately proposed.

## 1. Security model

CLM One must enforce defense in depth across:

- identity;
- authentication;
- sessions;
- authorization;
- tenant isolation;
- encryption;
- secrets;
- audit;
- integrations;
- AI;
- exports;
- operations.

## 2. Authentication

Support:

- secure password authentication where enabled;
- MFA;
- passkeys where available;
- SAML SSO;
- SCIM;
- session management;
- recovery controls;
- administrator policy enforcement.

## 3. Authorization

Authorization must combine:

- workspace membership;
- workspace role;
- permission set;
- object-level access;
- workflow participation;
- group membership;
- confidentiality;
- ethical walls;
- contract access policy;
- field sensitivity;
- delegation;
- time-bounded access.

Role-based access alone is insufficient.

## 4. Object-level access

Access evaluation must occur for:

- workflows;
- contract records;
- documents;
- comments;
- approvals;
- entities;
- obligations;
- analytics;
- exports;
- audit events;
- AI context.

## 5. Sensitive metadata

Restricted object existence must not leak through:

- counts;
- search suggestions;
- notifications;
- dashboard totals;
- entity pages;
- exports;
- audit summaries;
- AI answers;
- URLs or predictable identifiers.

## 6. Privacy

Privacy controls must cover:

- purpose limitation;
- data minimization;
- retention;
- deletion policy;
- legal hold;
- data subject rights;
- processor information;
- subprocessor transparency;
- cross-border transfer controls;
- data residency;
- access logging.

## 7. Audit

Audit events must be append-only and tamper-evident.

Each event includes:

- event ID;
- timestamp;
- actor;
- actor type;
- workspace;
- source;
- object type;
- object ID;
- action;
- previous value;
- new value;
- version;
- IP or source metadata where appropriate;
- correlation ID;
- reason;
- delegated actor;
- integration identity.

## 8. Required audit coverage

Record at minimum:

- sign-in and session events;
- permission changes;
- contract access;
- document access where policy requires;
- exports;
- workflow configuration changes;
- publication;
- assignment;
- approval;
- signature;
- AI suggestion and verification;
- record creation;
- obligation changes;
- integration changes;
- exception approval.

## 9. Audit retention and export

Retention must be configurable according to legal, security, and contractual requirements.

Exports must be permission-controlled, logged, and protected against accidental data leakage.

## 10. Integration security

Integrations require:

- scoped credentials;
- secret rotation;
- least privilege;
- signed webhooks;
- replay protection;
- retries;
- dead-letter handling;
- data classification;
- integration audit events;
- revocation.

## 11. Secure defaults

New features must default to:

- least privilege;
- private visibility;
- explicit publication;
- verified destinations;
- non-destructive changes;
- audit logging;
- secure error handling.

## 12. Security release gate

No enterprise release without evidence for:

- tenant isolation;
- authorization tests;
- object-level access;
- export controls;
- audit coverage;
- session controls;
- secrets management;
- dependency scanning;
- vulnerability review;
- incident response;
- backup and restore.
