# PAR-APR-002 — characterization exception

**Programme ID:** PAR-APR-002  
**Status:** Effective only when this documentation-only exception is merged to `main`; expires when the authorized characterization PR merges.  
**Authority:** Narrow exception to ADR-0013's planning-only boundary and the PAR-APR-002 closure checklist.

## Named accountable owners

GitHub shows one direct human repository collaborator with push and admin access:
`@haroonwahed`. The account is also the repository code owner. For this
exception only, the named accountable owners are:

| Accountability | Named owner |
|---|---|
| Programme | `@haroonwahed` |
| Product | `@haroonwahed` |
| Engineering | `@haroonwahed` |
| Security | `@haroonwahed` |

These assignments identify responsibility for the limited characterization
slice. They are not GitHub review approvals and do not replace independent
Product, Engineering, and Security approval where that is required.

## Authorized scope

This exception authorizes only a default-off, non-authoritative
characterization PR containing:

- focused characterization tests;
- a complete ownership matrix for the 40 non-migration `ApprovalRequest`
  references identified in the verified baseline;
- canonical and legacy parity and residual inventories;
- workflow, inbox, lifecycle, API, operations, route, and UI dependency
  evidence;
- DPA reconciliation analysis; and
- ABSTAIN and explicit REVOKE gap documentation.

The PR may touch `contracts/services/approval_workflow.py` only when a
deterministic observation seam is required and only when that change does not
alter behaviour.

## Explicit exclusions

This exception does **not** authorize:

- migrations;
- feature enablement or flag changes;
- canonical read authority or any read-authority change;
- dual-write changes;
- permission or privilege changes;
- data repair;
- legacy removal or retirement;
- production activation; or
- ADMIN authority.

`ApprovalRequest` remains authoritative throughout the exception and the
characterization PR.

## Controls and expiry

- The characterization PR must retain default-off, non-authoritative scope.
- Required CI must be green for its immutable reviewed SHA before merge.
- The PR body and evidence must state the unchanged scope, the legacy-authority
  boundary, the pre-existing workflow-dashboard assertion drift, and rollback
  by reverting the characterization commit(s).
- This exception expires automatically when that characterization PR merges.
- Any residual reconciliation, read cutover, dual-write change, legacy
  retirement, or production action requires separate authorization.

No feature flag grants authority under this exception.
