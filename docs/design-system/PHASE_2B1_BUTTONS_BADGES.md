# Phase 2B.1: canonical buttons and badges

Status: implemented for the in-scope authenticated standard-page families.

## Canonical mappings

| Legacy class | Canonical API | Disposition |
|---|---|---|
| `.btn-primary-grad`, `.btn-cta`, `.btn-primary` | `.dc-ds-button--primary` | Primary submit/create action; retain legacy class as a deprecated visual adapter. |
| `.btn-ghost`, `.btn-quiet`, `.btn-secondary` | `.dc-ds-button--quiet` | Secondary, navigation, cancel, pagination, and non-destructive modal action. |
| `.btn-link` | `.dc-ds-button--link` | Text-only navigation action. |
| `.btn-danger` / `.btn-danger-soft` | `.dc-ds-button--danger` / `--danger-soft` | Destructive action; no semantic remapping was made. |
| `.btn-soft*` | `.dc-ds-button--soft` | Low-emphasis call to action. |
| `.btn-sm` / `.btn-lg` | `.dc-ds-button--sm` / `--lg` | Size adapter only. |
| `.badge-sm` | `.dc-ds-badge.dc-ds-badge--sm` | Canonical base and size; old semantic tone remains a temporary adapter. |
| `.badge-green`, `.badge-blue`, `.badge-yellow`, `.badge-red`, `.badge-purple`, `.badge-gray` | `success`, `progress`, `attention`, `danger`, `special`, `neutral` | Semantic target. Existing dynamic Django branches retain legacy tones while the canonical badge base is adopted. |

## Consumer inventory and migration boundary

The initial authenticated-template scan found 293 legacy button and 378 legacy
badge references, alongside 108 canonical button and 12 canonical badge
references. This phase assessed 59 standard list/detail and admin/settings
templates and migrated the 54 that had in-scope consumers, including their
embedded modal/drawer actions. The other five had no button or badge consumer.

After migration the legacy counts are intentionally unchanged (the classes are
compatibility adapters pending zero-consumer removal), while canonical adoption
increased to 392 button and 150 badge references. Public landing/legal pages,
forms, dashboards, workflow workspaces, route-specific previews, and table
component partials were excluded.

## Ambiguous or deferred consumers

- `.btn-soft-primary-primary` is an explicit deferred compatibility exception:
  it appears in `styleguide.html` and `trademark_request_list.html` but has no
  source-style definition. Its intended replacement is
  `.dc-ds-button--soft`, subject to visual confirmation of the trademark
  “View” action in a dedicated button phase. It is deliberately unchanged in
  this badge-only phase.
- Route-private `.repo-mini-btn`, `.msa-ws-*`, `.nda-ws-*`, `.dpa-*`, and
  `cc-v3-*` controls are out of scope.
- Dynamic badge-tone branches retain their colour alias until the later
  semantic-template migration can replace each branch with an explicit
  canonical tone without changing business status logic.

No selector was removed. The removal gate remains a repository-wide zero-
consumer search plus visual coverage of every former route family.
