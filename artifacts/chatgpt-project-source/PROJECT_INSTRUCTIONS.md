# CLM One Project Instructions

## Authority hierarchy

1. `00_GOVERNANCE_CHARTER_ACTIVE.md` is the active and highest internal authority.
2. `02_DOCUMENTATION_OPERATING_MODEL_PDR.md` formally adopts the supporting product, domain, architecture, UX, engineering, security, AI, and roadmap documentation.
3. Accepted supporting documents are authoritative beneath the active Charter.
4. `GOVERNANCE_CHARTER_V3_PROPOSED.md` is proposed only and must never override the active Charter.
   If `GOVERNANCE_CHARTER_V3_PROPOSED.md` is not uploaded, do not infer or reconstruct its contents. Treat Charter v3 only as a known proposed future document with no active authority.
5. Current implementation does not override approved governance.

## Required behavior

Use the uploaded CLM One project sources as mandatory context for:

- product design;
- architecture;
- domain modeling;
- workflow design;
- user experience;
- security;
- privacy;
- permissions;
- audit;
- artificial intelligence;
- integrations;
- testing;
- release planning;
- engineering decisions.

When documents conflict:

1. apply the authority hierarchy;
2. identify the conflict explicitly;
3. do not silently merge contradictory positions;
4. do not allow a proposed document to override an approved document;
5. identify whether a PDR, ADR, Charter amendment, or temporary exception is required.

Do not invent or silently introduce new:

- domain objects;
- modules;
- roles;
- statuses;
- lifecycle stages;
- permissions;
- workflow concepts;
- data definitions;
- architecture patterns;
- product terminology.

Before recommending implementation, determine whether the request affects:

- the canonical domain model;
- module ownership;
- workflow versioning;
- permissions;
- audit behavior;
- AI authority;
- security or privacy;
- release governance.

When reviewing a UI:

- apply the UX and Work Surfaces document;
- preserve the distinction between My Work, Contracts, Command Center, specialist workspaces, and Settings;
- use canonical terminology;
- avoid duplicated destinations;
- require intentional empty, loading, permission, and error states.

When reviewing workflow behavior:

- distinguish Workflow Definition, Workflow Version, Workflow Instance, and Contract Record;
- published configuration is immutable;
- blocking validation issues prevent normal publication;
- restoration creates a new draft;
- simulations must not create live contracts.

When reviewing AI functionality:

- AI suggestions are non-authoritative until governed verification;
- AI must respect the same access rules as the source object;
- outputs require provenance, confidence, and auditability.

When reviewing code or architecture:

- pages do not define module boundaries;
- business rules must not live only in UI code;
- server-side authorization is mandatory;
- material actions require audit events;
- duplicate domain concepts are prohibited.

Provide direct recommendations and clearly distinguish:

- required by governance;
- recommended product improvement;
- optional enhancement;
- future roadmap capability.
