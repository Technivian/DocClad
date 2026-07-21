# ADR 0009: Governance charter supersession

Status: **Accepted**

Approval metadata:

- Approved by: CLM One Product / Engineering governance (Pilot Stabilisation Sprint 0)
- Approved on: **2026-07-20**
- Effective date: **2026-07-20**
- Approval scope: Supersession of CMS Aegis `DESIGN_CONSTITUTION.md` v1.5 by
  `docs/governance/GOVERNANCE_CHARTER.md` v2.0, including the light-first pilot amendment that
  explicitly defers dark-theme parity.

## Context

The repository still treated `DESIGN_CONSTITUTION.md` (CMS Aegis v1.5) as the
live governance document while product branding, pilot scope, and design-system
docs had moved to **CLM One**. Conflicting guidance (for example mandatory dark
theme parity) blocked a controlled pilot reassessment.

## Decision

1. **`docs/governance/GOVERNANCE_CHARTER.md` is the canonical CLM One Governance Charter** for
   product, design-system, and engineering governance.
2. **`docs/governance/archive/DESIGN_CONSTITUTION.md` is retained as a historical record** with an
   explicit supersession banner; it must not be implemented when it conflicts
   with the current charter.
3. **CLM One is the only customer-facing product name.** CMS Aegis references
   are historical or technical migration remnants only.
4. **Dark theme parity is deferred** for the pilot. The authenticated app
   operates light-first per charter §4 amendment; obsolete dark-theme
   requirements from the superseded document are not in scope for Sprint 0.
5. Design-system documentation authority order is updated to reference
   `docs/governance/GOVERNANCE_CHARTER.md` first.

## Consequences

- README, agent context links, and governance checks point at
  `docs/governance/GOVERNANCE_CHARTER.md`.
- `docs/governance/archive/DESIGN_CONSTITUTION.md` remains in git for traceability with ADR/PDR cross-links.
- Brand regression checks continue to forbid CMS Aegis in active code paths.

## Traceability

| Artifact | Role |
|---|---|
| `docs/governance/GOVERNANCE_CHARTER.md` | Canonical charter (v2.0) |
| `docs/governance/archive/DESIGN_CONSTITUTION.md` | Historical CMS Aegis v1.5 snapshot |
| `docs/governance/decisions/pdr/0001-finance-approval-threshold.md` | Finance threshold authority |
| `docs/governance/decisions/pdr/0002-contract-stage-and-status.md` | Stage vs Status authority |
