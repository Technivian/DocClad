# Commercial V1 Remediation Backlog

This is a prioritised planning backlog, not implementation authorisation. Each item requires the applicable PDR/ADR, security review, and GitHub evidence under the active Charter before release.

## P0 — Commercial launch blockers

| ID | Problem and commercial impact | Governing requirement | Acceptance criteria | Test evidence required | Dependencies | Suggested PR boundary | Stop condition |
|---|---|---|---|---|---|---|---|
| P0-01 | Golden NDA and DPA flows have failing focused assertions; a sales demo cannot claim a proven end-to-end lifecycle | Roadmap stage 1 exit; CR-03, CR-06 | Clean seed completes NDA and DPA flows without developer intervention; Command Center/My Work render correct state; negative and recovery paths work | Browser + Django tests for intake, record, audit, access; all focused tests green | Workflow/config seed | Test/behaviour repair only | Any needed status/role/permission change lacks accepted authority |
| P0-02 | Workflow configuration/versioning is interim and cannot meet immutable publication/pinning promise | Domain invariants 1–2; workflow architecture; CR-02, CR-13 | Definition/Version/Instance model is authorised; published version immutability and instance pinning enforced in persistence; restoration creates draft | Migration, invariant, concurrency, tenant, rollback tests | Accepted ADR/PDR | One aggregate-cutover slice | Data migration cannot be reversibly validated |
| P0-03 | Approval decisions may not be proven against exact changed contract/document state or stable role resolution | Domain invariant 5; workflow §8; CR-12 | Every approval identifies requirement, authority basis, exact version/state; material change reset policy is deterministic; no self/cross-tenant approval | Positive/negative approval reset, delegation, role, and tenant tests | Role resolver authority | Approval domain slice | Requires privilege widening without release gate |
| P0-04 | Signature execution is not commercially evidenced | Signature module; CR-14 | One supported provider or governed alternative acceptance has send/webhook/retry/expiry/cancel/fallback/reconciliation evidence and retained final artifact | Contract tests, provider sandbox integration, replay/idempotency and operator rehearsal | Credentials, security review | Provider adapter + evidence only | Provider data/security terms are not approved |
| P0-05 | Durable record/provenance and MSA/SOW relationship are not proven across v1 packages | Domain invariant 3; CR-04, CR-16 | Final record is created transactionally after authorised execution and preserves source workflow, versions, decisions, evidence, related agreement, and import source | Four golden journey integration tests; provenance immutability tests | P0-02–P0-04 | Record-finalisation service | Requires unapproved new domain terminology |
| P0-06 | Privacy DPA gate lacks end-to-end immutable blocking proof | Privacy Review architecture; CR-06, CR-15 | Unresolved privacy risks or missing decision block progression; decision is version-bound, access-controlled, audited, and recoverable | DPA E2E, negative bypass, role, audit, and tenant tests | P0-03 | Privacy gate service | Privacy policy/authority is unresolved |
| P0-07 | Restricted metadata may leak across projections and legacy integer routes | Security §§3–5; CR-21–CR-22 | One server-side object-policy contract covers document, workflow, record, review, approval, signature, obligation, search, analytics, exports, notifications, and AI; denial leaks neither existence nor metadata | Exhaustive cross-channel deny suite, enumeration test, independent security review | P0-02 | Policy extraction + one surface migration at a time | A policy exception is required without formal exception |
| P0-08 | Operations cannot substantiate recovery or support commitments | Security release gate; CR-25–CR-26 | Defined RPO/RTO; scheduled backup, restore drill, alert triage, severity/on-call/support ownership and evidence recorded for named environment | Restore rehearsal, alert-to-incident exercise, deployment/operator logs | Hosting | Operations runbook/evidence package | No named environment/operator owner |
| P0-09 | No sellable commercial package | Commercial v1 objective; CR-30 | Approved pricing/package, order form, SLA, DPA, privacy/security schedule, support terms, and claim guide exist | Legal/Finance approval via GitHub review; sales dry run | Legal / Finance | Documentation package | Terms require business decision not authorised |
| P0-10 | No controlled-customer production/reference evidence | Release gates; CR-32 | Authorised controlled pilot runs the four journeys; approved release evidence, support outcomes, and customer consent/reference decision retained | Immutable CI/review SHA, deployment logs, pilot evidence | P0-01–P0-09 | Pilot activation package | Any release gate is unsatisfied |

## P1 — Production-quality requirements

| ID | Problem and commercial impact | Governing requirement | Acceptance criteria | Test evidence required | Dependencies | Suggested PR boundary | Stop condition |
|---|---|---|---|---|---|---|---|
| P1-01 | Customer configuration/onboarding is not repeatable | Workflow designer; CR-29 | Versioned onboarding pack configures NDA/MSA/SOW/DPA, role mapping, access, templates, and validation without engineering | Clean-tenant bootstrap and admin UX tests | P0-02, P0-03 | Starter-content/onboarding docs | Requires new role/type without PDR |
| P1-02 | Search/data quality needs broader coverage | Data architecture §4–5; CR-19 | Search supports authorised contract/document criteria with duplicate/quality queues and safe empty/failure states | Search relevance, data-quality, non-leakage, load tests | P0-07 | Search/quality slice | Access policy incomplete |
| P1-03 | Obligations/renewals need canonical ownership and operational delivery evidence | Domain §2.28; CR-17 | Canonical obligations have owner, status, due date, recurrence, evidence, escalation; notice/reminder delivery is observable | Scheduler, ownership, delivery, retry, audit, tenant tests | P0-05 | Obligations aggregate | Canonical-model conflict unresolved |
| P1-04 | Accessibility/mobile/failure coverage is insufficient | Charter accessibility; UX §§7–11; CR-27 | WCAG AA audit and responsive acceptance pack cover four journeys and error/recovery states | Automated axe/keyboard tests, manual assistive-tech record, visual/mobile tests | P0-01 | Per-surface UX PRs | Shared primitive gaps not approved |
| P1-05 | Performance capacity is unknown | Roadmap quality gate; CR-28 | Customer-volume profile, SLOs, concurrent load results, query plans, job throughput, and monitoring dashboard are defined | Repeatable load tests and production-like report | P0-08 | Performance evidence package | Production-like environment unavailable |
| P1-06 | Export/offboarding is incomplete | Security §9; CR-24 | Access-controlled, audited customer data package with documented scope and revoke/expiry behaviour | Export authorization, leak, audit, and restore tests | P0-07, P0-08 | Export service + docs | Data classification unresolved |

## P2 — Post-launch improvements

| ID | Problem and commercial impact | Governing requirement | Acceptance criteria | Test evidence required | Dependencies | Suggested PR boundary | Stop condition |
|---|---|---|---|---|---|---|---|
| P2-01 | Advanced AI review/extraction is not needed for v1, but must remain governed | Data/AI §§6–10 | Every enabled AI use case has source, policy, reviewer, disposition, access/redaction, and cost controls | AI non-authority and redaction tests | P0-07 | One AI use case at a time | AI would become authoritative |
| P2-02 | Broad marketplace/CRM/ERP expansion is outside v1 | Integrations module; CR-33 | Each integration has scoped credentials, retry/DLQ/replay controls, mapping, audit, and support owner | Sandbox integration and failure-mode tests | P0-08 | One connector per PR | External security review incomplete |
| P2-03 | Enterprise entity intelligence and portfolio analytics are deferred | Roadmap stages 4 and 8 | Models and projections have canonical data/access controls and value hypothesis | Permission-aware analytics and scale tests | P0-07, P1-05 | One bounded insight surface | Canonical data governance absent |

## Not required for Commercial v1

- Broad integration marketplace.
- Advanced AI clauses, drafting, natural-language search, or autonomous decisioning.
- Advanced entity intelligence and large-enterprise analytics.

These remain subject to the accepted roadmap and must not be marketed as current capability without their own evidence.
