# NDA Golden-Journey Minimum Remediation Tranche

## Decision

Implement one coherent NDA vertical slice after the required design decision is
accepted. The slice starts with immutable published workflow configuration and
ends only after an authorized user can retrieve/export the executed NDA, its
signature evidence, provenance and append-only history. It must not split
workflow pinning, final-document binding, approval invalidation and signature
evidence across unrelated partial implementations.

This is a plan, not authorization to change production code.

## Exact scope

1. Accept or replace the proposed workflow-version decision with an approved
   ADR/PDR defining Definition, immutable published Version, Instance pinning,
   publication authority, retirement and migration.
2. Introduce the minimal canonical Definition/Version/Instance representation
   and migrate NDA configuration. Publication creates an immutable snapshot;
   existing live workflows remain readable through a legacy adapter.
3. Launch NDA only from one published Version and persist its immutable
   identifier/snapshot on the instance and Contract provenance.
4. Generate the final NDA as canonical immutable DocumentVersion. Repair C-01
   so permitted tombstone/audit metadata writes do not mutate locked artifacts.
5. Create version-bound ApprovalRequirements; record immutable decisions; on
   material NDA revision invalidate/reopen requirements.
6. Create a version-bound signature packet and record receipt/status, signer
   evidence and execution certificate; promote only after all signatures.
7. Promote the Contract Record only with complete immutable workflow, document,
   approval and signature provenance; archive evidence; enforce object access
   and export logging.
8. Emit and test all required audit events, authorization decisions, recovery
   behaviour and E2E golden-journey evidence.

## Explicitly excluded scope

* DPA specialist implementation, privacy routing and cross-product workflow
  migration; PDR-0005 remains planning context.
* MSA/SOW and generic Workflow Designer cutover beyond adapter support.
* AI/extraction, redline UX, billing, background OCR, dashboard copy redesign
  and unrelated full-suite fixture cleanup.
* New roles, permissions, lifecycle states or provider activation without
  separately approved authority and release gates.

## Governing requirements and affected areas

| Area | Required result | Affected aggregate/module |
| --- | --- | --- |
| Configuration | Published config immutable; launch pins exactly one version; later publish affects new launches only. | Workflow Definition/Version/Instance; workflow services/designer. |
| Document | Final NDA is DocumentVersion, not DraftDocument; material change creates a new version. | Document/DocumentVersion; document_version_service. |
| Approval | Requirement/decision bind evaluated version; material change invalidates it. | ApprovalRequirement/ApprovalDecision; approval_canonical. |
| Signature | Packet/evidence bind that version; terminal provider state is auditable/idempotent. | SignatureRequest/provider adapter. |
| Record | Provenance references pinned instance/version/final artifact and locks only with complete evidence. | Contract; contract_provenance. |
| Security/audit | Object-level allow/deny/no-leak and append-only correlated history. | permissions, audit service, export views. |

The approved Charter, Canonical Domain Model, Master Blueprint, Workflow Engine
and Designer, Security/Privacy/Access/Audit, Engineering Guardrails, Roadmap,
PDR-0003, ADR-0013, ADR-0014 and ADR-0015 govern the tranche. Proposed
ADR-0010/0012 and PDR-0004 must be accepted, superseded or explicitly excluded
before implementation; they cannot be implemented by implication.

## Decisions, migrations, compatibility and rollback

* Required decision: approved ADR/PDR for Definition/Version lifecycle and
  explicit NDA execution-state contract; it must resolve current mutable
  WorkflowTemplate conflict with accepted documentation.
* Migrations: additive Definition/Version tables or approved equivalent;
  immutable snapshot/checksum; nullable pin fields on legacy instances;
  final document/approval/signature correlation fields. Data migration marks
  legacy links as legacy; it must never invent missing historical evidence.
* Compatibility: legacy detail routes remain readable. New NDA launch uses only
  published canonical versions after controlled activation; legacy evidence is
  never reinterpreted as version-bound.
* Rollback: before activation use a reversible default-off launch flag and
  retain legacy reads. After real evidence exists, rollback is forward-only:
  disable new launches, preserve facts and use audited compensation, never
  delete/remap records.

## Authorization and audit events

Authorization must be explicit for version edit/publication; launch; intake
edit; material-change acknowledgement; review/approval; signature dispatch and
status ingest; final-record promotion; archive; view and export. Every denial
and cross-tenant attempt must not leak metadata.

Minimum final event keys (subject to approved ADR naming):

* workflow.definition.created, workflow.version.published,
  workflow.version.publication_blocked, workflow.instance.launched;
* nda.intake.submitted, document.version.created,
  document.version.material_change_recorded;
* approval.requirement.opened, approval.decision.recorded,
  approval.requirement.invalidated;
* signature.packet.created, signature.dispatch.succeeded or failed,
  signature.status.received, signature.evidence.recorded;
* contract.record.promoted, contract.record.archived,
  contract.record.exported, and corresponding blocked/failure events.

Events include organization, actor type, correlation/idempotency key, pinned
workflow version, document-version ID, reason/outcome, and no restricted
metadata in unauthorized surfaces.

## Required verification

Automated tests must prove:

1. publication cannot mutate; edit creates a new version; a live instance stays
   on launch version;
2. launches on either side of publication use distinct immutable versions;
3. final document version is immutable while authorized tombstone/audit writes
   work and audit (C-01 regression);
4. approval binds exact version and material revision invalidates/reblocks it;
5. signature/evidence bind exact version, duplicate provider delivery is
   idempotent, and failure/retry cannot execute it;
6. record provenance requires complete chain and cannot mutate;
7. owner/member/unauthorized/cross-tenant access and export do not leak;
8. E2E happy, material-change, provider-failure, unauthorized-export and
   archive/recovery paths; and
9. full suite is reclassified only for an intended documented contract change,
   never skipped/weakened merely to green it.

Manual verification in a named non-production environment follows one published
NDA version through launch, intake, review, material revision, reapproval,
signature evidence, final record, archive, audit inspection and authorized
export. Capture GitHub CI for reviewed SHA and operator/deploy records; do not
create manual approval tables or hand-enter timestamps.

## PR sequence and evidence gates

1. **Decision PR** — accept/supersede needed ADR/PDR. Gate: required
   governance review; no implementation attached.
2. **Canonical workflow + NDA execution PR** — one coherent implementation PR
   containing migration, publication/pinning, final document, approval
   binding/reset, signature evidence, record promotion, access, archive and
   audit. Gate: required checks green for unchanged SHA; migration/reversibility
   review; all automated cases; security/tenancy checks; no new finding.
3. **Controlled activation/evidence PR or release record** — only if approved
   authority permits. Gate: independent Product, Engineering and Security
   GitHub reviews, green CI, reversible default-off control, named-environment
   operator record and actual golden-journey evidence. This plan grants no
   activation authority.

## Closure evidence and stop conditions

Closure needs immutable reviewed/merged SHAs, passing applicable CI, migration
evidence, test outputs, required GitHub reviews, non-production operator/deploy
evidence, and exportable audit evidence for the complete NDA path. The audit
conclusion may change only after that evidence exists.

Stop implementation and return to governance if decision authority is missing;
a proposed record is treated as authority; migration cannot retain legacy
evidence; an unapproved role/permission/state is needed; published version
mutates; approval/signature crosses a material change; append-only/non-leakage
fails; or provider evidence cannot be reproduced. These are safety stops, not
reasons to weaken tests.
