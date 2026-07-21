# PDR-0003: Documentation operating model

**Status:** Accepted  
**Date:** 2026-07-21  
**Approved on:** 2026-07-21  
**Approved by:** Product / Engineering governance (repository steward review)  
**Product:** CLM One  
**Related:** [`../adr/0009-governance-charter-supersession.md`](../adr/0009-governance-charter-supersession.md), [`../../GOVERNANCE_CHARTER.md`](../../GOVERNANCE_CHARTER.md), [`../../GOVERNANCE_CHARTER_V3_PROPOSED.md`](../../GOVERNANCE_CHARTER_V3_PROPOSED.md)

## Problem

CLM One documentation was fragmented across the repository root, `docs/`, audits, pilot packs, and design-system notes. Agents and contributors lacked a single operating model for:

- which Charter is active;
- where product, architecture, engineering, and roadmap authority live;
- how ADRs, PDRs, and exceptions are created;
- how proposed documentation differs from approved governance.

Without that structure, teams risk inventing domain objects, modules, roles, statuses, permissions, lifecycle stages, terminology, or architecture patterns that conflict with approved governance — or treating proposed documents as if they were already approved.

## Proposal

Adopt the canonical documentation operating model under `docs/`:

```text
docs/
├── README.md
├── governance/
│   ├── GOVERNANCE_CHARTER.md                  # active
│   ├── GOVERNANCE_CHARTER_V3_PROPOSED.md      # proposed (separate decision)
│   ├── PRODUCT_OPERATING_MODEL.md             # accepted supporting
│   ├── archive/
│   └── decisions/
│       ├── README.md
│       ├── adr/
│       ├── pdr/
│       └── exceptions/
├── product/
├── architecture/
├── engineering/
└── roadmap/
```

This PDR adopts:

- the repository documentation structure and index;
- placement of decision templates and naming conventions;
- mandatory agent reading rules in root `AGENTS.md`;
- the supporting product, architecture, engineering, and roadmap documents as **Accepted** guidance under the active Charter (they remain subordinate to the active Charter and accepted decision records).

## Explicit non-adoption in this PDR

**Governance Charter v3 remains separately proposed.**

This PDR does **not** approve, activate, or make effective [`../../GOVERNANCE_CHARTER_V3_PROPOSED.md`](../../GOVERNANCE_CHARTER_V3_PROPOSED.md). Changing the constitution requires a distinct, deliberate approval. The active Charter remains [`../../GOVERNANCE_CHARTER.md`](../../GOVERNANCE_CHARTER.md) until that separate formal approval amends or supersedes it.

## Review notes (approval)

Reviewed against acceptance criteria on 2026-07-21:

- Canonical `docs/` tree is present with a working index and decision templates.
- Active Charter path is preserved; Charter v3 carries a prominent Proposed banner and is not marked Approved/Active.
- Supporting documentation is adopted as Accepted under this PDR, without elevating it above the active Charter.
- Root `AGENTS.md` includes mandatory documentation reading rules.
- No application behavior change is required by this adoption (path references only).

## Consequences

### Product

- Product choices must cite the active Charter and relevant accepted PDRs/ADRs.
- Accepted supporting product docs guide product work; they do not override the active Charter.

### Engineering

- Implementation must follow the active Charter and accepted decision records.
- Accepted engineering guardrails guide implementation; conflicts with the active Charter require a decision record, not silent override.

### Testing / design / security / AI agents

- Agents must read the mandatory documentation set in `AGENTS.md`.
- Agents must not treat Charter v3 as approved authority until separately approved.
- Current code does not override approved governance documentation.

## Migration steps

1. Relocate the active Charter to `docs/governance/GOVERNANCE_CHARTER.md` (preserving history).
2. Archive the superseded design constitution under `docs/governance/archive/`.
3. Relocate existing ADRs/PDRs under `docs/governance/decisions/`.
4. Add supporting documentation from the Documentation package.
5. Publish `docs/README.md` and `docs/governance/decisions/README.md`.
6. Update root `AGENTS.md` and documentation path references.
7. Keep Governance Charter v3 status as **Proposed** until separately approved.
8. Mark supporting product/architecture/engineering/roadmap docs **Accepted** under this PDR.

## Approval

Accepted on 2026-07-21 by Product / Engineering governance review.

Charter v3 approval is **out of scope** for this PDR and must be decided separately.

## Acceptance criteria

- [x] Canonical `docs/` tree exists with working relative links
- [x] Active Charter remains clearly identifiable and not replaced by Charter v3
- [x] Charter v3 is marked Proposed and not presented as approved
- [x] Decision templates and naming conventions are documented
- [x] Root `AGENTS.md` includes mandatory documentation reading rules
- [x] No application behavior changed solely for this documentation adoption
- [x] Supporting documentation status updated to Accepted under this PDR
- [x] This PDR marked Accepted with approval metadata
