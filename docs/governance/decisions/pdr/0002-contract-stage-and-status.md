# PDR 0002: Contract Stage, Status, and Document State

Status: **Approved** (supersedes earlier two-field wording)

Approved on: 2026-07-20  
Revised on: 2026-07-20  
Owner: Product / Contract Lifecycle

## Three canonical dimensions

| Dimension | Field | Purpose |
|---|---|---|
| **Record status** | `Contract.status` | Business condition of the contract **record** |
| **Workflow stage** | `Contract.lifecycle_stage` | Position in the operating pipeline |
| **Document state** | `Document.status` | Maturity of a document artifact |

These are related but never interchangeable. Never use “Draft” as a record status
label — drafting is a **workflow stage**. Document “Draft” is artifact state only.

## Record status values

| Value | Label |
|---|---|
| `IN_PROGRESS` | In progress |
| `ACTIVE` | Active |
| `EXPIRED` | Expired |
| `TERMINATED` | Terminated |
| `CANCELLED` | Cancelled |
| `ARCHIVED` | Archived |

Default: `IN_PROGRESS`. AI/upload/review nuance lives in workflow stage and
review-run models — not as extra record statuses.

## Workflow stage values

| Value | Label |
|---|---|
| `INTAKE` | Intake |
| `DRAFTING` | Drafting |
| `INTERNAL_REVIEW` | Internal review |
| `NEGOTIATION` | Negotiation |
| `APPROVAL` | Approval |
| `SIGNATURE` | Signature |
| `EXECUTED` | Executed |
| `OBLIGATION_TRACKING` | Obligation tracking |
| `RENEWAL` | Renewal |

`ARCHIVED` is **not** a workflow stage; archive is record status `ARCHIVED`.

Default: `DRAFTING` (create flows that are pre-field-capture may use `INTAKE`).

## Document state values

| Value | Label |
|---|---|
| `DRAFT` | Draft |
| `FINAL` | Final |
| `EXECUTED` | Executed |
| `SUPERSEDED` | Superseded |

## Allowed combinations (enforced)

Record ↔ stage:

- `IN_PROGRESS` ↔ `INTAKE` … `EXECUTED` (not `OBLIGATION_TRACKING` / `RENEWAL`)
- `ACTIVE` ↔ `EXECUTED` | `OBLIGATION_TRACKING` | `RENEWAL`
- Terminal statuses (`EXPIRED`, `TERMINATED`, `CANCELLED`, `ARCHIVED`) freeze stage;
  no further stage advances except `system=True` repair

Document ↔ contract:

- Document `EXECUTED` only when contract stage ∈ `{EXECUTED, OBLIGATION_TRACKING, RENEWAL}`
  or status ∈ `{ACTIVE, EXPIRED, TERMINATED, ARCHIVED}`
- New versions mark prior `FINAL` / `EXECUTED` as `SUPERSEDED` when replacing

## Happy-path activation

Signature (or equivalent) completion uses a single activation triad:

```text
status = ACTIVE
lifecycle_stage = OBLIGATION_TRACKING
primary_document.status = EXECUTED
```

Workflow stage `EXECUTED` remains a valid resting stage (signed, obligations not yet opened).

## Transition ownership

| Change | Authority |
|---|---|
| `status` | `ContractLifecycleService.transition()` |
| `lifecycle_stage` | `ContractLifecycleService.transition_lifecycle_stage()` |
| Combined updates | `apply_contract_operational_position()` |
| Activation triad | `activate_contract()` |

Direct model writes from views, AI endpoints, or jobs that bypass these services
are defects.

## Audit requirements

- `contract.status_changed`
- `contract.lifecycle_stage_changed`
- `contract.operational_position_changed` / `contract.activated`
- `document.status_changed` when document state transitions

Historical audit payloads keep original strings; migration does not rewrite logs.

## UI display rules

| Surface | Display |
|---|---|
| Compact header | `In progress · Drafting` (status · stage) |
| Right rail | Record status, workflow stage, **document state** for primary document |
| Repository | Status filter = six record statuses; Stage filter = `lifecycle_stage` |
| Badges | Separate helpers for record / stage / document |

Do not pair a “Draft” record badge with a “Drafting” stage — that ambiguity is retired.

## Tests

Matrix unit tests, migration mapping tests, repository/API filters, contract header
label guards, and lifecycle rehearsal / pilot-gate coverage must assert the
three-dimension vocabulary.
