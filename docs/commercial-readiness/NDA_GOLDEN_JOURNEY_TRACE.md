# NDA Golden-Journey Trace

## Authority and trace boundary

This trace is against e413da6b669b9d405f0ceac4488f2c8b2eff8890. The active
Charter v2.3 and accepted product, domain, workflow, security/audit and
engineering documents govern it. ADR-0010, ADR-0012, PDR-0004 and Charter v3
are proposed and do not supply implementation authority. PDR-0005 is accepted
planning context only.

The journey cannot truthfully be marked complete. Its **first broken step is
step 1/2: canonical workflow definition and immutable published workflow
version**. WorkflowTemplate is selected by is_active and version; it combines
configuration and version identity, and the NDA seeder can activate/update it
at runtime. A live Workflow points to that mutable row. This fails the
approved requirement that a launch pin a published immutable configuration.

The deepest shared root cause is the same architectural shortcut: specialist
builders are vertical feature flows over a mutable WorkflowTemplate, rather
than one canonical Definition → immutable Version → pinned Instance runtime.
Useful component models are consequently not bound into an authoritative NDA
execution chain.

## Lifecycle trace

| # | Step / canonical object | Owner, service and persistence | Authorization and audit | Test, surface and recovery | Gap / verdict |
| ---: | --- | --- | --- | --- | --- |
| 1 | Workflow definition; required WorkflowDefinition, current substitute WorkflowTemplate | contracts.models.WorkflowTemplate; contracts.services.nda_workflow._ensure_nda_seed_data | No definition-specific authorization/event is evidenced. | Workflow Designer; test_workflow_template_versioning covers legacy behaviour. Recovery is manual template edit/clone. | **Broken.** No canonical Definition aggregate separates identity from configuration. |
| 2 | Published workflow version; required immutable WorkflowVersion, current WorkflowTemplate(version, is_active) | WorkflowTemplate, WorkflowTemplateStep, FieldDefinition, ApprovalRoute; get_nda_workflow_template selects active latest version. | Publish/audit surface exists, but is_active is mutable; NDA seed activates and updates template content. | Workflow Designer; legacy tests do not prove immutable snapshots. | **Broken.** No published configuration immutability or authoritative Version object. |
| 3 | Workflow launch; required pinned WorkflowInstance, current Workflow | create_nda_workflow_instance; Workflow(template, contract, status) and WorkflowStep. | Organization context; generic nda_workflow_created audit. | /contracts/new/nda/; builder creates workflow. Recovery is workspace redirect. | **Partial.** Points to mutable template; no immutable version/snapshot identifier. |
| 4 | Intake; FieldValue bound to instance/version | FieldDefinition / FieldValue. | Membership protections; generic creation audit. | NDA builder; all except dashboard literal pass. | **Partial.** Values reference mutable template field IDs, not immutable version. |
| 5 | Document creation; required Document + immutable DocumentVersion, current DraftDocument | DraftDocument(workflow, contract, content, version, is_current); canonical document service exists separately. | Canonical service has tenant check and version audit. | Workspace preview; document-version tests pass. | **Broken.** NDA writes mutable DraftDocument, not approval/signature artifact. |
| 6 | Review; version-bound review work | WorkflowStep, risk signals, optional legacy route. | Generic workflow action/audit. | Workspace review controls; risk tests pass. | **Partial.** No version-bound NDA review aggregate or material-revision recovery. |
| 7 | Approval; ApprovalRequirement/immutable ApprovalDecision bound to DocumentVersion | approval_canonical.record_approval_decision and invalidate_open_requirements_for_contract. | Assigned/delegated actor and decision/invalidation audit recorded. | Approval, authorization and PAR-APR-001 tests pass. | **Broken composition.** NDA route does not demonstrate requirements against actual final NDA version; reset not wired to NDA material change. |
| 8 | Signature; SignatureRequest + execution evidence bound to DocumentVersion | SignatureRequest, provider adapters, evidence fields. | Signer/manager transition checks; development provider flags off. | Signature workspace tests pass; outbound tests hit C-01 first. | **Broken.** No demonstrated final-NDA packet, provider evidence ingest, retry/idempotency or executed promotion. |
| 9 | Contract-record creation; Contract with immutable workflow provenance | Contract then pin_workflow_provenance. | Provenance repair is authorization-gated and audited. | PAR-CORE-003 passes. | **Partial.** Builder creates Contract first and pins a mutable template number; no final-record promotion after approval/signature evidence. |
| 10 | Archival; retained terminal Contract/final document | contract_lifecycle and deletion/retention service. | Organization access and lifecycle/deletion audit required. | Retention components exist; 25 deletion tests hit C-01. | **Broken evidence path.** Locked-document tombstone path errors; no proven executed-NDA archive route. |
| 11 | Audit history; append-only per-tenant AuditLog chain | AuditLog and audit service. | Audit rows cannot update/delete; tenant scoped. | audit_integrity and workflow audit tests pass. | **Partial.** No one E2E audit chain covers every NDA transition/correlation/version ID. |
| 12 | Access/export; object-level final artifact access with non-leakage | permissions.can_access_contract_action; document sharing fields and export views. | Membership gate; canonical document service asserts tenant access; export must audit. | Cross-tenant/permission matrix passes. | **Partial.** Final NDA object/document evidence access, restricted metadata and governed export are not proven. |

## Explicit invariant verdicts

| Invariant | Verdict | Evidence / gap |
| --- | --- | --- |
| Workflow-version pinning | **Fail** | Workflow.template points to mutable WorkflowTemplate, not immutable Version/snapshot. |
| Published configuration immutability | **Fail** | is_active toggle and seed-time update permit change. |
| Document-version immutability | Component pass; journey fail | Canonical service tests pass; NDA produces DraftDocument and C-01 blocks permitted locked-row writes. |
| Approval binding | Component pass; journey fail | Canonical models support DocumentVersion; NDA does not demonstrate it. |
| Approval reset after material change | Component pass; journey fail | Invalidation service passes but lacks NDA material-change integration. |
| Signature evidence | **Fail** | Fields exist; no final packet/evidence lifecycle is demonstrated. |
| Contract-record provenance | Partial | Immutability passes; current pin uses mutable template/version number and precedes execution. |
| Object-level access | Partial | Tenant/member checks pass; final-document policy is not proven. |
| Restricted metadata non-leakage | Partial | No final-NDA export/access matrix evidence. |
| Append-only audit history | Component pass; journey fail | Chain tests pass; complete journey assertion absent. |

## Required recovery semantics

A failed provider call or exception must not advance lifecycle state. Preserve the
pinned version and prior immutable artifacts; audit the blocked/failed event;
keep requirement/signature state recoverable; require fresh approval after a
material change; permit authorized retry only with idempotency/correlation
evidence. A new version affects new launches only; live instances remain pinned.

## Implementation follow-up (default-off; not an activation result)

The baseline above remains an historical classification of `e413da6`; it is not
rewritten as a release claim. The additive implementation in migration `0116`
adds the canonical chain and focused invariant coverage described in
[the implementation note](../architecture/CANONICAL_WORKFLOW_RUNTIME_IMPLEMENTATION.md).
It is disabled by default, leaves the existing `WorkflowTemplate` NDA builder
unchanged, and creates no historical mapping. The focused automated evidence
covers immutable publication, live-instance pinning, final `DocumentVersion`,
approval reset, provider-neutral signature-evidence idempotency, record
promotion, archival/export authorization, cross-tenant denial, and C-01's
locked-document permitted-write boundary.

This does **not** close Commercial v1 readiness: publication-role authority,
named-environment controlled activation, external-provider evidence, final-NDA
export/non-leakage verification beyond the service boundary, and legacy mapping
remain separately required.
