# Casefile: The DocClad Design System

Casefile is the product and engineering standard for every DocClad interface.
It applies to Django templates, JavaScript interactions, generated UI, design
previews, and any future frontend runtime.

## Product Character

**Calm, confident, actionable.**

- Calm: information is structured, quiet, and readable under pressure.
- Confident: status, ownership, and consequences are explicit.
- Actionable: every operational surface makes the next valid action clear.

DocClad is a governed contract operations system. It must not look like a
generic document store, a marketing site, or an AI demonstration.

## Authority

When sources disagree, use this order:

1. This directory and the code tokens it references.
2. Live components under `theme/templates/design_system/`.
3. `theme/static/css/docclad-tokens.css` and `theme/static_src/src/design-system/`.
4. Older redesign plans and screenshots as historical context only.

## Contents

- [Foundations](FOUNDATIONS.md)
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
