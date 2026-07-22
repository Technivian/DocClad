# Canonical mapping — priority dual-write paths

| Source | Legacy action | ExceptionRequest | ExceptionDecision | Privileges |
|---|---|---|---|---|
| `KEEP_EXCEPTION` | `keep_exception` audit | ACTIVE | APPROVED | `policy.deviation` |
| `ACCEPTED_RISK` | DPARiskItem → ACCEPTED_RISK | ACTIVE | APPROVED | `risk.accept` |
| `AI_EXCEPTION` | finding `create_exception` | SUBMITTED | *(none — not invented)* | none |
| `CONFLICT_CHECK_WAIVER` | ConflictCheck → WAIVED | ACTIVE | APPROVED | `policy.deviation` |
| `DEADLINE_DEFER` | +7 day defer | ACTIVE | APPROVED | `deadline.extend` |
| `DPA_APPROVE_WITH_BLOCKERS` | APPROVED with open HIGH/CRITICAL blockers | ACTIVE | APPROVED | `approval.defer_blocker` |

## Fail-closed

| Condition | Behavior when dual-write enabled for org |
|---|---|
| Cross-tenant | Raise; no canonical row |
| Critical bypass without `security_approval` | Raise / HTTP 403; Security gate audit |
| Malformed privilege token | Raise; no canonical row |

## Expiry / renewal

- Applicability: `exception_is_applicable` / `privilege_granted`
- Expiry records `EXPIRED_RECORDED` without rewriting APPROVED history
- Renewal creates a new ExceptionRequest linked via `renewed_from`
