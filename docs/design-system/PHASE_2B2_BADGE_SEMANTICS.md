# Phase 2B.2: badge semantics and alias removal

Status: complete for one zero-consumer legacy alias family.

## Semantic contract

Canonical badge tones are `success`, `progress`, `attention`, `danger`,
`special`, and `neutral`. `legacy_badge_tone` is the single shared adapter for
dynamic legacy status maps; unknown values fall back to `neutral`.

No business status was reclassified from colour alone in this phase. Existing
dynamic status branches retain their current business logic and are deferred
until their owning page family can be reviewed semantically.

## Alias removal

`.badge-expiring` had zero runtime template or JavaScript consumers. Its sole
source declaration in `global-shell/legacy-layout.css` was removed after a
repository-wide consumer check. The intended canonical treatment for a future
expiring status is `.dc-ds-badge--attention`, but no rendered instance existed
to migrate.

## Corrected consumer breakdown (post-Phase 2B.1)

| Category | References | Notes |
|---|---:|---|
| Runtime template consumers | 723 | 124 authenticated template files; includes compatibility classes retained during adoption. |
| Canonical + legacy co-applied | 202 elements | Intentional temporary visual adapters. |
| Compatibility adapter definitions | 62 | Source CSS only; compiled output excluded. |
| Intentionally out-of-scope systems | 244 | 54 workflow/workspace/dashboard/form/preview/shared-table files. |
| Tests and documentation | 104 | Non-runtime references. |

The counts intentionally distinguish rendered consumers from CSS definitions
and test/documentation mentions. Public landing and legal rendering are not
included in the runtime migration count.

## Deferred semantic mappings

Workflow stage, signature-event, due-diligence, and route-private status
branches remain deferred because their semantic meaning must be confirmed by
their owning workflow rather than inferred from `badge-*` colour aliases.
