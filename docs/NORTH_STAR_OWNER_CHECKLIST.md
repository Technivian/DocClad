# CMS Aegis North-Star Owner Checklist

Last updated: 2026-05-16

This checklist is the execution view of the north-star maturity matrix. It groups the remaining work by accountable owner so the team can drive the app from strong internal MVP to production-complete.

## Legend

- `READY` = can start immediately
- `IN PROGRESS` = actively being worked
- `BLOCKED` = waiting on external dependency or evidence
- `DONE` = complete and accepted

## TL: Tech Lead / Delivery Owner

| Item | Status | Why it matters | Exit signal |
|---|---|---|---|
| Close SPR3 release gates | IN PROGRESS | This is the main go/no-go path for north-star readiness | `SPR3-001`, `SPR3-002`, and `SPR3-003` are all complete with evidence attached |
| Enforce release discipline | READY | The platform needs repeatable evidence and clear signoff | PR/release process always includes required artifacts and checklist completion |
| Consolidate product surface area | READY | Too many shells and demo surfaces dilute the product | Supported UI shells are reduced and clearly documented |

## BE: Backend Owner

| Item | Status | Why it matters | Exit signal |
|---|---|---|---|
| Live integration proof support | IN PROGRESS | Salesforce, webhook, NetSuite, and e-sign need real target-env runs | Live evidence is captured for each integration path |
| Workflow and signature hardening | IN PROGRESS | These are core enterprise flows and must be robust | Invalid transitions, replayed events, and actor violations are rejected consistently |
| Contract lifecycle completion | READY | Archive / renewal flows still need final automation polish | Draft-to-archive and renewal paths feel complete and predictable |
| Search and reporting depth | READY | Users need stronger filters and clearer exports | Faceted search and export/reporting behavior is richer and more explainable |

## FE: Frontend Owner

| Item | Status | Why it matters | Exit signal |
|---|---|---|---|
| Remove placeholder/demo behavior | IN PROGRESS | The UI must feel like a product, not a lab | Placeholder actions are replaced with real navigation or state changes |
| Consolidate alternate shells | READY | Multiple shells add maintenance cost and user confusion | Supported shell count is smaller and intentionally documented |
| Responsive and empty-state polish | READY | The app must hold up on smaller screens and in edge states | Core pages have consistent responsive and empty/error handling |

## SRE: Platform / DevOps Owner

| Item | Status | Why it matters | Exit signal |
|---|---|---|---|
| Postgres cutover proof | IN PROGRESS | Production readiness depends on database migration confidence | Cutover evidence exists with `cutover_ready=true` in the target env |
| Backup / restore / rollback rehearsal | BLOCKED | Safe production operation requires real recovery evidence | Backup, restore, and rollback are executed and logged with timings |
| Release evidence automation | IN PROGRESS | Evidence should be repeatable, not manual | Release workflow reliably captures and stores required artifacts |
| Observability and alerts | IN PROGRESS | Production issues must be diagnosable quickly | Dashboards, alerts, and drill evidence are attached to the operating model |

## SEC: Security Owner

| Item | Status | Why it matters | Exit signal |
|---|---|---|---|
| Live identity proof | BLOCKED | SAML/SCIM/MFA must work with real enterprise systems | Live IdP/SCIM runs prove the flows work end to end |
| Dependency and advisory hygiene | IN PROGRESS | Security debt should stay below the release threshold | Dependency audit stays clean at required severity levels |
| Governance and SLA enforcement | IN PROGRESS | Vulnerability and incident handling need an operating model | SLA cycles, drill evidence, and response paths are documented and active |
| Compliance evidence packaging | IN PROGRESS | Auditable release evidence is part of enterprise trust | Tamper-evident artifacts are generated and verified in workflow |

## QA: Test / Release Owner

| Item | Status | Why it matters | Exit signal |
|---|---|---|---|
| Release candidate validation | IN PROGRESS | The app needs a repeatable gate before shipping | Gate checklist passes with all required artifacts linked |
| Live smoke coverage | BLOCKED | Local tests are not enough for production readiness | Critical flows pass in the target environment |
| Regression expansion | READY | The codebase is large and regression risk is real | High-risk flows are covered with stable regression tests |
| Evidence traceability | IN PROGRESS | Decision records need reproducible proof | Test runs and evidence files are connected to each release |

## PO: Product Owner

| Item | Status | Why it matters | Exit signal |
|---|---|---|---|
| Commercial readiness scope | READY | Enterprise onboarding and support surfaces are still thin | Onboarding, billing, support, and trust surfaces are defined and prioritized |
| Integration acceptance criteria | IN PROGRESS | Live integration proof needs product-level acceptance rules | Each integration has a clear success/failure definition |
| UX priority ranking | READY | The remaining polish work should be sequenced by value | UI cleanup and workflow polish are ordered by customer impact |

## First Wave Priorities

1. Finish the release gates and live evidence capture.
2. Complete Postgres cutover and recovery proof.
3. Validate live integrations in a target environment.
4. Remove placeholder UI behavior and consolidate shells.
5. Lock the remaining enterprise/commercial scope.

## Readout Rule

The app can be treated as north-star ready only when:

- release gates are green,
- live integration proof exists,
- recovery drills are documented,
- the UI surface is consolidated,
- and the remaining enterprise support/commercial work is scheduled.