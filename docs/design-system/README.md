# Casefile: The CLM One Design System

Casefile is the product and engineering standard for every CLM One interface.
It applies to Django templates, JavaScript interactions, generated UI, design
previews, and any future frontend runtime.

## Product Character

**Calm, confident, actionable.**

- Calm: information is structured, quiet, and readable under pressure.
- Confident: status, ownership, and consequences are explicit.
- Actionable: every operational surface makes the next valid action clear.

CLM One is a governed contract operations system. It must not look like a
generic document store, a marketing site, or an AI demonstration.

## Authority

When sources disagree, use this order:

1. [`GOVERNANCE_CHARTER.md`](../governance/GOVERNANCE_CHARTER.md) (the active CLM One Governance Charter).
2. [`DESIGN_CONSTITUTION.md`](../governance/archive/DESIGN_CONSTITUTION.md) — historical CMS Aegis v1.5 snapshot only.
3. [Frontend Architecture](ARCHITECTURE.md).
4. `theme/static/css/clmone-tokens.css`.
5. Live components under `theme/templates/design_system/` and canonical
   `.dc-ds-*` CSS under `theme/static_src/src/design-system/components.css`.
6. Older redesign plans, audits, and screenshots as historical context only.

Phase 6 (authenticated legacy retirement + anti-drift) is recorded in
[PHASE_6_LEGACY_RETIREMENT.md](PHASE_6_LEGACY_RETIREMENT.md) and
[LEGACY_COMPATIBILITY_INVENTORY.md](LEGACY_COMPATIBILITY_INVENTORY.md).
ADR/PDR [0008](../governance/decisions/adr/0008-frontend-design-system-phase-1.md) is marked
completed for the authenticated app. Optional public-shell follow-up:
[PHASE_6_1_PUBLIC_SHELL_FOLLOWUP.md](PHASE_6_1_PUBLIC_SHELL_FOLLOWUP.md).
The Phase 1 inventory is retained as superseded:
[LEGACY_COMPATIBILITY_INVENTORY_PHASE1.md](LEGACY_COMPATIBILITY_INVENTORY_PHASE1.md).

## Contents

- [Foundations](FOUNDATIONS.md)
- [Frontend Architecture](ARCHITECTURE.md)
- [Components](COMPONENTS.md)
- [Domain Patterns](DOMAIN_PATTERNS.md)
- [Interactions](INTERACTIONS.md)
- [Page Archetypes](PAGE_ARCHETYPES.md)
- [Content Standards](CONTENT_STANDARDS.md)
- [Engineering Contract](ENGINEERING.md)
- [Migration Status](MIGRATION.md)

## Live Catalogue

Authenticated users can inspect the executable component standard at:

`/contracts/design-system/`

The catalogue demonstrates approved tokens, component states, domain badges,
forms, tables, empty states, toasts, and interaction hooks. It is a validation
surface, not a production navigation destination.

## Change Policy

A design-system change is complete only when all applicable layers change:

1. Document the rule.
2. Update semantic tokens or the shared primitive.
3. Update the live catalogue.
4. Add or update an enforcement test.
5. Verify desktop, mobile, focus, empty, loading, and error behavior.

Page-specific CSS must not redefine a semantic color, control height, status
meaning, or focus treatment that belongs in Casefile.
