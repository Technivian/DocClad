# PDR 0001: Finance approval threshold

Status: **Approved**

Approved on: 2026-07-20  
Owner: Product / Commercial Operations  
Supersedes: ad-hoc `$250,000` constants in MSA workflow code and templates

## Decision

CLM One uses a **single Finance approval threshold of USD 100,000** for governed
contract routing during the internal pilot unless this record is explicitly
superseded by a newer approved decision.

## Rules

| Topic | Rule |
|---|---|
| Threshold | **100,000** in the organisation's contract currency for pilot comparisons |
| Owner | Product (Commercial Operations policy) |
| Configurability | **Globally fixed** for pilot; `contracts.services.finance_approval_policy.get_finance_approval_threshold()` is the only code entry point |
| Currency treatment | Compare numeric `value` / `total_contract_value` / `recurring_value` fields in the contract's stated currency without FX conversion during pilot |
| Unknown value | **Do not** trigger Finance by value alone; other rules (payment terms, manual confirmation) may still apply |
| Recurring / TCV | Use `total_contract_value` or `tcv` when present, else `recurring_value` / `annual_value`, else headline `value` |
| Finance approver | Approval step **`FINANCE`** resolved via `ApprovalRule` / route cards; role label **Finance Director** |
| Audit | Every automated routing decision must persist `finance_approval_threshold`, `finance_routing_reason`, and compared value in audit metadata |

## Migration implications

- Remove duplicated `250000` / `250_000` finance constants from MSA workflow,
  workflow builder JavaScript, intake copy, and tests.
- Seed/demo approval rules should reference the unified threshold in descriptions.
- Historical contracts routed under the incorrect threshold remain unchanged; new
  routing uses this policy only.

## Implementation

- Code: `contracts/services/finance_approval_policy.py`
- Consumers: intake launch, MSA workflow risk detection, workflow routing copy,
  draft cockpit, repository explanations, audit events, tests, seed configuration
