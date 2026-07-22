# ADR-0015 governance acceptance — meeting record

**Meeting type:** Programme governance review (decision record)  
**Date:** 2026-07-22 (UTC)  
**Vote window:** 2026-07-22T19:12:31Z – 2026-07-22T19:12:39Z  
**Status:** **Ratified**  
**Chair:** @haroonwahed (repository steward — Product governance)  
**Quorum:** Product governance · Engineering governance · Security & privacy (advisory) — **met**  
**Package under review:**

- [`0015-exception-request-decision-model.md`](0015-exception-request-decision-model.md)
- [`../../../audits/evidence/2026-07-22-par-exc-001/`](../../../audits/evidence/2026-07-22-par-exc-001/)
- [`../../../audits/evidence/2026-07-22-par-exc-001/DECISION_PACKAGE.md`](../../../audits/evidence/2026-07-22-par-exc-001/DECISION_PACKAGE.md)
- [`../../../audits/evidence/2026-07-22-par-exc-001/DUAL_WRITE_IMPLEMENTATION_AUTHORIZATION.md`](../../../audits/evidence/2026-07-22-par-exc-001/DUAL_WRITE_IMPLEMENTATION_AUTHORIZATION.md)

**Foundation branch:** `cursor/feat-par-exc-001-exception-waiver-discovery-d7f1`  
**Foundation PR:** [#66](https://github.com/Technivian/CLMOne/pull/66)  
**Dual-write PR:** [#67](https://github.com/Technivian/CLMOne/pull/67)

---

## 1. Motions and votes

### Motion 1 — Accept ADR-0015

**Motion:** Change ADR-0015 status from **Proposed** to **Accepted** as the canonical Exception and Waiver model (`ExceptionRequest`, immutable `ExceptionDecision`, owner/expiry, authority basis, compensating controls, privilege-token boundaries, tenant isolation, Security approval for Critical-control bypasses, governed renewal/closure).

**Acceptance scope limitation:** ADR acceptance establishes the model and invariants. It does **not** authorize canonical read-path authority, legacy path retirement, or controlled-pilot activation.

| Approver | GitHub identity | Governance capacity | Authority basis | Vote | Consent |
|---|---|---|---|---|---|
| Haroon Wahed | @haroonwahed | Product governance / repository steward | `.github/CODEOWNERS` (`/docs/`); `GOVERNANCE_CHARTER.md` v2.0 | **Approve** | 2026-07-22T19:12:31Z |
| Technivian | @Technivian | Engineering governance / repository steward | `.github/CODEOWNERS` (`/contracts/`, `/docs/`); PDR-0003 | **Approve** | 2026-07-22T19:12:35Z |
| Security & privacy (advisory) | @Technivian | Security review capacity | `SECURITY_PRIVACY_ACCESS_AND_AUDIT.md`; Charter §7 | **Approve with conditions** | 2026-07-22T19:12:39Z |

**Result:** **Ratified** — ADR-0015 **Accepted** effective 2026-07-22T19:12:39Z

---

### Motion 2 — Authorize priority dual-write implementation (default-off)

**Motion:** Authorize **default-off** dual-write implementation for these paths only (legacy remains authoritative):

1. `KEEP_EXCEPTION`
2. `ACCEPTED_RISK`
3. `AI_EXCEPTION`
4. `CONFLICT_CHECK_WAIVER`
5. `DEADLINE_DEFER`
6. `DPA_APPROVE_WITH_BLOCKERS`

**Explicitly not authorized by this motion:** controlled-pilot flag enablement; canonical read authority; legacy retirement; automatic repair; retrospective historical invention.

| Approver | GitHub identity | Governance capacity | Vote | Consent |
|---|---|---|---|---|
| @haroonwahed | Product | **Approve** | 2026-07-22T19:12:31Z |
| @Technivian | Engineering | **Approve** | 2026-07-22T19:12:35Z |
| @Technivian | Security advisory | **Approve with conditions** | 2026-07-22T19:12:39Z |

**Result:** **Carried** — implementation Authorized (flags remain default off; activation requires a separate vote)

---

## 2. Verbatim recorded votes (authoritative)

### Product — @haroonwahed (accepted)

```text
APPROVE — ADR-0015 and PAR-EXC-001 Priority Dual-Write

Approver: @haroonwahed
Capacity: Product governance
Timestamp: 2026-07-22T19:12:31Z

Motion 1:
Approve ADR-0015 as the canonical Exception and Waiver model.

Vote: Approve

Motion 2:
Authorize the default-off dual-write implementation for:

- KEEP_EXCEPTION
- ACCEPTED_RISK
- AI_EXCEPTION
- CONFLICT_CHECK_WAIVER
- DEADLINE_DEFER
- DPA_APPROVE_WITH_BLOCKERS

Vote: Approve

Conditions:

- legacy behavior remains authoritative;
- every approved exception has an owner and expiry;
- AI exceptions remain submitted until an authorized decision exists;
- no retrospective invention of historical approval data;
- canonical read authority and legacy retirement require separate authorization;
- controlled-pilot activation requires a separate vote.
```

### Engineering — @Technivian (accepted)

```text
APPROVE — ADR-0015 and PAR-EXC-001 Priority Dual-Write

Approver: @Technivian
Capacity: Engineering governance
Timestamp: 2026-07-22T19:12:35Z

Motion 1:
Approve ADR-0015 as the canonical Exception and Waiver model.

Vote: Approve

Motion 2:
Authorize the default-off six-path dual-write implementation.

Vote: Approve

Conditions:

- implementation remains additive;
- legacy paths remain authoritative;
- dual-write is idempotent;
- request and decision history remain immutable;
- migration forward, rollback, and re-forward must pass;
- canonical failures are audited;
- no automatic repair or legacy retirement;
- controlled-pilot activation requires a separate authorization.
```

### Security advisory — @Technivian (accepted with conditions)

```text
APPROVE WITH CONDITIONS — ADR-0015 and PAR-EXC-001 Priority Dual-Write

Approver: @Technivian
Capacity: Security advisory
Timestamp: 2026-07-22T19:12:39Z

Motion 1:
Approve ADR-0015 as the canonical Exception and Waiver model.

Vote: Approve with conditions

Motion 2:
Authorize the default-off six-path dual-write implementation.

Vote: Approve with conditions

Binding conditions:

- Critical-control bypasses require explicit Security approval;
- cross-tenant exception creation fails closed;
- malformed or unrestricted privilege scope fails closed;
- no exception silently grants unrelated privileges;
- every active exception has an owner, expiry, authority basis, and compensating controls;
- audit evidence must not expose restricted contract or identity content;
- no automatic repair;
- no canonical read authority;
- controlled-pilot activation requires a separate Security vote.
```

---

## 3. Implementation boundary

| Authorized | Not authorized |
|---|---|
| Additive ExceptionRequest / ExceptionDecision foundation | Canonical read-path authority |
| Default-off six-path dual-write (PR #67) | Enabling `EXCEPTION_DUAL_WRITE_ENABLED` |
| Migrations `0114` / `0115` | Legacy path retirement / field deletion |
| Idempotent correlation + fail-closed Security/tenant gates | Retrospective bulk historical invention |
| | Controlled-pilot activation (separate package) |

---

## 4. Approvers and effective date

| Field | Value |
|---|---|
| **Status** | Ratified |
| **ADR-0015** | **Accepted** |
| **Effective date** | 2026-07-22T19:12:39Z |
| **Approved by** | @haroonwahed (Product) · @Technivian (Engineering) · @Technivian (Security advisory, with conditions) |
