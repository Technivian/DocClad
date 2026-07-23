# Decision records

This directory holds Architecture Decision Records (ADRs), Product Decision Records (PDRs), and temporary exceptions for **CLM One**.

## When to use what

| Instrument | Use when |
|---|---|
| **ADR** | A durable technical or architectural choice is needed (module boundary, storage pattern, auth mechanism, workflow engine invariant, integration approach). |
| **PDR** | A durable product, domain, policy, or UX choice is needed (lifecycle semantics, permission model, terminology, release gate, operating process). |
| **Combined ADR/PDR** | The same change requires both product and architecture authority in one tightly coupled decision. Prefer one record with both product and architecture sections, or linked ADR + PDR pairs with cross-references. |
| **Temporary exception** | A time-boxed deviation from approved governance or an accepted decision is required to ship safely. Must include expiry, owner, and remediation plan. |
| **Charter amendment** | The active Governance Charter itself must change. Use a proposed Charter document plus a PDR that requests formal approval. Do not silently replace the active Charter. |

## Naming conventions

New records should use:

- `ADR-0001-short-title.md`
- `PDR-0001-short-title.md`
- `EXC-0001-short-title.md`

Use zero-padded sequence numbers. Prefer kebab-case short titles.

### Historical naming

Earlier accepted records may use the legacy forms `0008-….md` / `0001-….md` without the `ADR-` / `PDR-` prefix. Those remain valid; do not renumber them casually. New records should follow the conventions above.

## Templates

- [ADR template](adr/ADR_TEMPLATE.md)
- [PDR template](pdr/PDR_TEMPLATE.md)
- [Exception template](exceptions/EXCEPTION_TEMPLATE.md)
- [GitHub review and release evidence](../GITHUB_REVIEW_AND_RELEASE_EVIDENCE.md)

## Repository review and release evidence

For new authorization and release work, the GitHub PR, submitted reviews, CI
results, immutable reviewed and merged SHAs, and the required operator or
release record are the evidence.

Decision records may link to the PR and release record, but must not recreate
approval evidence in a manually maintained vote table or copy approval text
into the record. Historical decision evidence remains unchanged.

See the active Charter and
[`GITHUB_REVIEW_AND_RELEASE_EVIDENCE.md`](../GITHUB_REVIEW_AND_RELEASE_EVIDENCE.md)
for the applicable gate.


## Status values

- **Proposed** — under review; not binding
- **Accepted** / **Approved** — binding for its scope
- **Superseded** — replaced by a later accepted record; keep for history
- **Rejected** / **Withdrawn** — not adopted; keep for history
- **Expired** (exceptions) — no longer authorized

Do not fabricate approved decisions. Do not mark a record Accepted without documented approval metadata.

## Current records

### ADRs

| Record | Status |
|---|---|
| [0008-frontend-design-system-phase-1.md](adr/0008-frontend-design-system-phase-1.md) | See file |
| [0009-governance-charter-supersession.md](adr/0009-governance-charter-supersession.md) | Accepted |
| [0013-approval-requirement-decision-split.md](adr/0013-approval-requirement-decision-split.md) | Accepted |
| [0014-role-definition-reconciliation.md](adr/0014-role-definition-reconciliation.md) | Accepted |
| [0015-exception-request-decision-model.md](adr/0015-exception-request-decision-model.md) | **Accepted** |

### PDRs

| Record | Status |
|---|---|
| [0001-finance-approval-threshold.md](pdr/0001-finance-approval-threshold.md) | See file |
| [0002-contract-stage-and-status.md](pdr/0002-contract-stage-and-status.md) | See file |
| [PDR-0003-documentation-operating-model.md](pdr/PDR-0003-documentation-operating-model.md) | Accepted |
| [PDR-0004-github-review-and-release-evidence.md](pdr/PDR-0004-github-review-and-release-evidence.md) | Proposed |

### Exceptions

No active exceptions yet. Use [EXCEPTION_TEMPLATE.md](exceptions/EXCEPTION_TEMPLATE.md).

## Authority reminder

The active Charter is [`../GOVERNANCE_CHARTER.md`](../GOVERNANCE_CHARTER.md).

The proposed Charter amendment is [`../GOVERNANCE_CHARTER_V3_PROPOSED.md`](../GOVERNANCE_CHARTER_V3_PROPOSED.md) and is **not** approved. Constitutional change requires a separate deliberate decision.

Documentation index: [`../../README.md`](../../README.md).
