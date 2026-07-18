# Phase 2B.4: repository lifecycle stages, controls, and surfaces

Status: complete, pending Phase 2B.5 review.

## Baseline decision

The Phase 1 list and detail baselines are **obsolete**, not Phase 2B.4
regressions. They were rerun before the Phase 2B.4 changes and were left
unchanged.

| Baseline | Current evidence | Classification | Decision |
|---|---|---|---|
| List | Two deterministic comparisons report 2,101 changed pixels. The page geometry is unchanged; diffs are the already-approved button, badge, and footer token treatments. | Obsolete baseline | Retain unchanged. |
| Detail | Deterministic comparison reports 28,564 changed pixels (22 pixels from the prior 28,542 run). The stable, page-wide text and surface delta predates this phase and is not the lifecycle chip. | Obsolete baseline | Retain unchanged. |
| Contract form (Phase 2A check) | 11,887 changed pixels. The expected image shows the superseded “Preview draft” / “Create draft” flow; the approved route renders “Save draft” / “Create contract”. The source-level launch test confirms submit is intentionally enabled so validation can render. | Obsolete baseline | Retain unchanged. |

No screenshot was regenerated or overwritten. This supersedes the earlier
detail-only non-reproducible-harness classification with fresh deterministic
evidence; the older decision record remains as historical evidence.

## Repository lifecycle adapter

`lifecycle_stage_badge_tone` in `contracts/templatetags/clmone_format.py` is
the dedicated adapter for `Contract.lifecycle_stage`. It is consumed in the
repository DTO as `stage_badge_tone`, and the repository’s compact Stage chip
uses `.dc-ds-badge--${stage_badge_tone}`.

| Lifecycle stage | Tone | Lifecycle meaning |
|---|---|---|
| `DRAFTING`, `ARCHIVED` | neutral | Inert start/retained record. |
| `INTERNAL_REVIEW`, `NEGOTIATION`, `SIGNATURE` | progress | Work is in flight. |
| `APPROVAL`, `RENEWAL` | attention | A decision or follow-up is required. |
| `EXECUTED`, `OBLIGATION_TRACKING` | success | Agreement is operational. |
| null, unknown, obsolete | neutral | Safe fallback; never a positive implication. |

The full lifecycle dot track remains on the detail route. The compact chip is
an intentionally separate repository representation, not a replacement of
that detail component.

## Compatibility retirement and adoption evidence

| Item | Before | After | Verification / disposition |
|---|---:|---:|---|
| Contract-specific `status_badge_class` adapter definition | 1 | 0 | Exact repository-wide zero-consumer search completed before removal. |
| Repository `contract.status_badge_class` rendering path | 1 | 0 | Replaced with `stage_badge_tone`; the API contract test asserts absence. |
| Repository lifecycle semantic consumers | 0 | 3 | DTO, data contract, and JS renderer consume `stage_badge_tone`. |
| Shared canonical form constructors | 0 | 3 | `FORM_CONTROL`, `FORM_CHECK`, and `FORM_FILE`; 13 shared widget references inherit them. Legacy aliases remain co-applied adapters. |
| Contract-intake panels with canonical surface co-application | 0 | 12 | Existing route-specific geometry remains in place. |
| Contract-detail manually authored controls with canonical co-application | 0 | 3 | Reviewer/comment/decision controls retain their existing compatibility class. |
| Legacy CSS selectors removed | 0 | 0 | No selector met the zero-runtime-consumer gate. |

`legacy_badge_class_for_tone` and `lifecycle_stage_badge_class` remain only as
explicitly deprecated generic bridges for out-of-scope dashboard/table
rendering. They accept semantic tones or stages, not a contract-status API;
the retired contract-specific adapter no longer exists.

## Tests and visual evidence

- `tests.test_contract_launch_setup`, `tests.test_repository_work_queue`,
  `tests.test_design_system_phase2`, and `tests.test_design_system_phase2a`:
  84 passed. The repository API test now asserts semantic status/stage tones
  and absence of the retired presentation field.
- `manage.py check --settings=config.settings_test`: passed.
- `client/tests/e2e/phase-2b3-contract-document-statuses.spec.js`: passed at
  1440px and 390px, including canonical compact lifecycle-chip verification.
- Existing list/detail visual baselines and the Phase 2A contract-form visual
  check were run but remain failing only against the obsolete baselines above.
  No baseline changed and no new screenshot was added because no new page
  archetype or component state was introduced.

## Remaining decisions and recommended Phase 2B.5

There are no unresolved lifecycle semantics. A reviewed baseline replacement
decision is still needed before the obsolete visual expectations can become
active assertions; it is not part of this phase. Phase 2B.5 should migrate the
remaining standard record/admin form-and-panel families through the shared
control and surface APIs, then retire only the compatibility selectors that
reach zero runtime consumers. Tables, dashboards, workflows, and scaffolds
should remain excluded.
