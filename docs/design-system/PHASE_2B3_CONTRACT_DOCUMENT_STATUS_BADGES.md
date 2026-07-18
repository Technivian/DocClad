# Phase 2B.3: contract and document status badge semantics

Status: complete, pending Phase 2B.4 review.

## Scope and adapter

`contract_status_badge_tone` and `document_status_badge_tone` in
`contracts/templatetags/clmone_format.py` are the canonical shared adapters.
They resolve one of the six `.dc-ds-badge--*` tones. `None`, unknown, and
retired values always return `neutral`.

The existing `status_badge_class` adapter remains deprecated only for the
Repository lifecycle-stage chip. That chip renders `stage_display`, not a
contract status, and its lifecycle-stage semantics are explicitly out of this
phase. The document-status adapter had zero repository consumers after the
migration and was removed.

## Complete status inventory and semantic mapping

| Domain | Status | Canonical tone | Lifecycle evidence |
|---|---|---|---|
| Contract | `NEEDS_INPUT` | attention | AI upload/review flow blocks until required information is supplied. |
| Contract | `UPLOADED` | progress | Intake accepted; processing has begun. |
| Contract | `PROCESSING` | progress | Automated processing is in flight. |
| Contract | `CLASSIFICATION_REQUIRED` | attention | Classification is required before review. |
| Contract | `AI_REVIEW_IN_PROGRESS` | progress | Automated review is in flight. |
| Contract | `AI_REVIEW_READY` | special | A completed review handoff is ready for human assessment, not a final agreement outcome. |
| Contract | `HUMAN_REVIEW_IN_PROGRESS` | progress | Human assessment is in flight. |
| Contract | `INFORMATION_REQUIRED` | attention | Further information is required. |
| Contract | `INTERNAL_APPROVAL_REQUIRED` | attention | Approval action is required. |
| Contract | `NEGOTIATION_IN_PROGRESS` | progress | Negotiation is in flight. |
| Contract | `READY_FOR_SIGNATURE` | attention | Signature routing still requires action. |
| Contract | `SIGNATURE_IN_PROGRESS` | progress | The contract-level signature step is in flight. This is not the out-of-scope `SignatureRequest` status system. |
| Contract | `EXECUTED` | success | The agreement has been executed. |
| Contract | `OBLIGATIONS_ACTIVE` | success | The executed agreement is in active obligation management. |
| Contract | `DRAFT` | neutral | Inert, editable starting state. |
| Contract | `PENDING` | attention | Waiting for a next action. |
| Contract | `IN_REVIEW` | progress | Review is in flight. |
| Contract | `APPROVED` | progress | Contract approval precedes final execution. |
| Contract | `ACTIVE` | success | Agreement is operational. |
| Contract | `EXPIRED` | danger | Agreement validity has ended. |
| Contract | `TERMINATED` | danger | Agreement was terminated. |
| Contract | `COMPLETED` | success | Positive terminal completion. |
| Contract | `CANCELLED` | neutral | Inert, non-operational terminal state. |
| Document | `DRAFT` | neutral | Editable starting version. |
| Document | `REVIEW` | attention | Reviewer action is required. |
| Document | `APPROVED` | progress | Approved but not finalised. |
| Document | `FINAL` | success | Final document, including executed-source retention protection. |
| Document | `ARCHIVED` | neutral | Inert retained record. |
| Either | `null`, unknown, obsolete | neutral | Safe fallback; never implies success. |

The lifecycle evidence is in `contracts/models.py`,
`contracts/api/documents_ai.py`, and `contracts/services/contract_lifecycle.py`.
No mapping was selected from a predecessor colour name alone.

## Runtime migration and compatibility evidence

| Consumer category | Before | After | Result |
|---|---:|---:|---|
| Contract-status template adapters | 3 | 0 | `contract_detail`, `contract_form`, and the contract rail in `matter_detail` now call `contract_status_badge_tone`. |
| Document-status template adapters | 2 | 0 | `document_list` and the document rail in `matter_detail` now call `document_status_badge_tone`. |
| Repository actual-status drawer | 1 | 0 | Uses the API's `status_badge_tone` field and canonical markup. |
| Document legacy adapter definitions | 2 | 0 | `_DOCUMENT_STATUS_BADGES` and `document_status_badge_class` removed after the zero-consumer check. |
| Contract legacy adapter definitions | 2 | 2 | Explicit deferred compatibility adapter for the out-of-scope lifecycle-stage chip. |
| Lifecycle-stage runtime chip | 1 | 1 | Intentionally out of scope; it renders `stage_display` through the deprecated contract adapter. |

Before/after counts were produced with repository-wide `rg` plus the
Python file scan over runtime templates, JavaScript, service, and domain
sources; generated CSS and dependencies were excluded. The post-migration
zero-consumer search for `document_status_badge_class` and
`_DOCUMENT_STATUS_BADGES` returned no references before their removal.

## Validation evidence

- `tests.test_design_system_phase2` and `tests.test_design_system_phase2a`:
  30 passing tests. The added coverage asserts every `Contract.Status` and
  `Document.Status`, plus unknown and null fallback, against the model choices.
- `manage.py check --settings=config.settings_test`: passed.
- `client/tests/e2e/phase-2b3-contract-document-statuses.spec.js`: passed at
  1440px and 390px. It verifies the canonical repository drawer status badge;
  the E2E tenant's document list is empty, so document-status permutations are
  covered deterministically by the adapter/model-choice tests instead.
- Existing Phase 1 list/detail visual snapshots were reused and deliberately
  not regenerated. They currently fail by 2,101 and 28,542 pixels,
  respectively. The list route was not changed in this phase; the detail diff
  spans page-wide text and surfaces rather than the one status chip. Both are
  therefore unrelated baseline regressions in the already-dirty workspace,
  not evidence for a Phase 2B.3 visual change. The captured Playwright diff
  images remain in `client/test-results/` for review.

## Deferred decisions

No contract or document status is semantically ambiguous. Lifecycle-stage,
`SignatureRequest`, workflow, due-diligence, and route-private statuses remain
outside this phase. The Repository stage chip's use of the deprecated
contract-status class is a documented compatibility exception; Phase 2B.4
should give lifecycle stages their own semantic adapter before removing it.
