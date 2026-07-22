# ADR-0015: Exception Request and Exception Decision model

- Status: **Accepted**
- Date: 2026-07-22
- Effective date: **2026-07-22T19:12:39Z**
- Deciders: @haroonwahed (Product governance) · @Technivian (Engineering governance)
- Related: PAR-EXC-001 (In progress), CANONICAL_DOMAIN_MODEL §2.33, G-DOM-03, PAR-APR-001 / ADR-0013 (pattern precedent)
- Evidence: [`../../../audits/evidence/2026-07-22-par-exc-001/`](../../../audits/evidence/2026-07-22-par-exc-001/)
- Decision package: [`../../../audits/evidence/2026-07-22-par-exc-001/DECISION_PACKAGE.md`](../../../audits/evidence/2026-07-22-par-exc-001/DECISION_PACKAGE.md)
- Meeting record: [`0015-governance-acceptance-meeting-record-2026-07-22.md`](0015-governance-acceptance-meeting-record-2026-07-22.md)

## Approval metadata

| Field | Value |
|---|---|
| **Submitted for ratification** | 2026-07-22 |
| **Ratified** | **2026-07-22T19:12:39Z** |
| **Product governance** | **Approve** — @haroonwahed (`2026-07-22T19:12:31Z`) |
| **Engineering governance** | **Approve** — @Technivian (`2026-07-22T19:12:35Z`) |
| **Security & privacy** | **Approve with conditions** — @Technivian (`2026-07-22T19:12:39Z`) |
| **Authority basis** | `.github/CODEOWNERS`; `GOVERNANCE_CHARTER.md` v2.0; PDR-0003 |
| **Written consent** | Verbatim votes in meeting record §2 |
| **Acceptance scope** | Canonical Exception/Waiver foundation (vocabulary, invariants, additive schema, governed service). Motion 2 separately authorizes **default-off** six-path dual-write only. |
| **Does not authorize** | Canonical read-path authority; legacy retirement; controlled-pilot flag enablement; automatic repair; retrospective historical invention |

**Implementation boundary:** Foundation merge (PR #66) + default-off dual-write (PR #67) under Motion 2. Activation requires a separate authorization package and votes.

## Context

Accepted domain documentation requires a first-class **Exception**: a temporary approved deviation from platform governance (§2.33).

CLM One previously had **no** unified Exception/Waiver object. Deviations were scattered across RiskSignal keep/accept audits, DPARiskItem `ACCEPTED_RISK`, AI finding exception dispositions, ConflictCheck `WAIVED`, deadline deferrals, lifecycle/system skips, repairs, and environment kill-switches (see evidence matrix).

PAR-APR-001 established the Requirement/Decision split pattern for approvals. Exceptions need an analogous governed aggregate with stronger temporal and privilege invariants.

## Decision

### 1. Canonical entities

| Entity | Role |
|---|---|
| `ExceptionRequest` | The governed deviation: reason, scope, owner, authority, risk class, compensating controls, privilege tokens, start/expiry |
| `ExceptionDecision` | Immutable outcome history (`APPROVED`, `REJECTED`, `RENEWED`, `CLOSED`, `REVOKED`, `EXPIRED_RECORDED`) |

### 2. Required invariants

1. Exceptions are temporary unless explicitly approved otherwise (`is_permanent_approved` on decision).
2. Every exception has an owner and an expiry (unless permanent).
3. Approval authority must be explicit (`authority_basis` + designated approver / Security flag).
4. An exception cannot silently grant unrelated privileges (closed privilege token catalogue).
5. Expired exceptions stop applying (`exception_is_applicable` / `privilege_granted`).
6. Renewal creates a new ExceptionRequest; prior is superseded via governed decision.
7. Historical decisions are immutable.
8. Cross-tenant exceptions are prohibited.
9. UI visibility is not authorization.
10. No exception may bypass a Critical security control without explicit Security approval (`security_approval=True`).

### 3. Governed write path

`contracts/services/exception_canonical.py`:

- `create_exception_request`
- `record_exception_decision`
- `renew_exception`
- `mark_exception_expired_if_due`
- `exception_is_applicable` / `privilege_granted`

### 4. Audit events

`exception.request.created`, `exception.request.submitted`, `exception.decision.recorded`, `exception.request.expired`, `exception.request.renewed`, `exception.cross_tenant.denied`.

### 5. Migration posture

Additive migration `0114_exception_request_decision` with **no** automatic legacy backfill (avoids inventing authority/expiry).

### 6. Explicit non-goals / residuals

- Production cutover of EXC-POL-*, EXC-DL-001, EXC-APR-001, etc. requires separate authorization after Acceptance.
- Platform break-glass (EXC-SEC/ADM/REP) may share the schema but needs Security review before dual-write.
- Expanding CANONICAL_DOMAIN_MODEL §2.33 prose beyond the one-line definition awaits Acceptance.
- PAR-APR-002, PAR-WF-010, and PAR-ID-002 are out of scope.

## Alternatives considered

### Alternative 1 — Extend ApprovalRequirement for exceptions

Rejected: approvals and exceptions have different temporal, privilege, and Security-approval semantics; conflating them recreates SoD failures (e.g. EXC-POL-007 assigning exception approval to contract owner).

### Alternative 2 — Keep status-enum-only deviations

Rejected: fails §2.33 and cannot enforce owner/expiry/authority/privilege invariants.

### Alternative 3 — Governance markdown exceptions only

Rejected: process template cannot enforce runtime applicability or tenant isolation.

## Consequences

### Positive

- One governed object for temporary deviations.
- Aligns with §2.33 and gap G-DOM-03 remediation path.
- Reuses proven Requirement/Decision immutability pattern.

### Negative

- Dual-path period until cutover.
- Privilege catalogue must be curated deliberately.

### Risks

- Premature cutover without Security review of Critical paths.
- Incomplete historical backfill if treated as authoritative.

### Migration

Additive `0114`; dual-write later under flag; optional non-authoritative backfill.

### Rollback

Reverse `0114` while no production writers depend on the tables; disable any future dual-write flags.

## Security and privacy impact

- Cross-tenant denied at service boundary.
- Critical security-control bypass gated on explicit Security approval.
- Privilege grants are allowlisted tokens only.
- Staff/platform break-glass remains separately reviewed.

## Data and audit impact

Append-only decision history; material actions emit `exception.*` audit events on the tenant chain.

## Test evidence required

`tests/test_par_exc_001_exception.py` — create/decide/immutability/expiry/renewal/cross-tenant/privilege/Security gates + legacy characterization.

## Approval

**Accepted** 2026-07-22T19:12:39Z by @haroonwahed (Product), @Technivian (Engineering), and @Technivian (Security advisory, Approve with conditions) per meeting record. Motion 2 authorizes default-off dual-write only; controlled-pilot activation and canonical read authority require separate votes.
