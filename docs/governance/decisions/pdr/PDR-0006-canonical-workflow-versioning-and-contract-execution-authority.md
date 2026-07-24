# PDR-0006: Canonical Workflow Versioning and Contract Execution Authority

**Status:** Proposed
**Date:** 2026-07-24
**Decision type:** Combined Product Decision Record / Architecture Decision Record
**Scope:** Canonical workflow runtime and the minimum NDA execution authority

**Related authority:** [Governance Charter](../../GOVERNANCE_CHARTER.md),
[Master Blueprint](../../../product/MASTER_BLUEPRINT.md),
[Canonical Domain Model](../../../product/CANONICAL_DOMAIN_MODEL.md),
[Workflow Engine and Designer](../../../architecture/WORKFLOW_ENGINE_AND_DESIGNER.md),
[Security, Privacy, Access and Audit](../../../architecture/SECURITY_PRIVACY_ACCESS_AND_AUDIT.md),
[Engineering Guardrails](../../../engineering/ENGINEERING_GUARDRAILS.md),
[Delivery Roadmap](../../../roadmap/DELIVERY_ROADMAP_AND_RELEASE_GATES.md),
[PDR-0002](PDR-0002-contract-stage-and-status.md),
[PDR-0003](PDR-0003-documentation-operating-model.md),
[PDR-0005](PDR-0005-dpa-specialist-workflow-gate.md),
[ADR-0013](../adr/0013-approval-requirement-decision-split.md),
[ADR-0014](../adr/0014-role-definition-reconciliation.md), and
[ADR-0015](../adr/0015-exception-request-decision-model.md).

## Status and authority boundary

This record is **Proposed**. It is implementation-ready for review, but does not
authorize a migration, permission change, provider activation, pilot, or production
behaviour. Those actions require the applicable accepted authority, reviewed pull
request, CI evidence, and release gate under the active Charter.

The active Charter and accepted supporting documents above remain authoritative.
Charter v3, PDR-0004, ADR-0010, ADR-0011 and ADR-0012 are proposed and do not
supply implementation authority. If accepted, this record becomes the single
decision for this scope and supersedes the proposed workflow-runtime direction in
ADR-0010 and ADR-0012. Until acceptance, neither those records nor this record
authorizes implementation by implication.

## Context and problem statement

The accepted product and architecture documents require this canonical chain:

    Workflow Definition -> immutable Workflow Version -> pinned Workflow Instance
                                         |
                                         v
                 final Document Version -> approvals -> signature evidence
                                         |
                                         v
                        Contract Record + append-only audit history

The commercial-readiness and NDA baseline evidence show that the current NDA path
does not establish that chain. It selects a mutable WorkflowTemplate, and its live
workflow references that mutable configuration. The NDA path also does not compose
the existing document-version, approval, signature, provenance and access components
into one version-bound execution path. The first broken journey step is therefore
definition/publication, not a UI assertion.

The three NDA/DPA UI assertions classified in the baseline are stale assertions,
not product defects or environment discrepancies. They do not resolve the runtime
break. The document-lock writer failure (C-01) is a genuine Commercial v1 blocker:
immutable evidence must coexist with tightly limited, auditable archival/tombstone
operations.

## Decision

Adopt the canonical **Definition -> immutable Version -> pinned Instance** runtime
as the only target authority for new governed workflow launches. Retain specialist
builders, including the NDA builder, as authoring and launch façades over that
runtime during an incremental controlled cutover. They must not be an alternative
runtime or a source of mutable published configuration.

The target NDA execution chain is one coherent vertical slice: a launch pins a
published workflow version; intake and work state are bound to that instance; the
final NDA is an immutable DocumentVersion; approvals and signature evidence bind
that exact version; and a final Contract Record is created only with complete,
immutable provenance. A later material change creates a new document version and
reopens the governed execution path.

No historical workflow, approval, signature, or record may be represented as having
canonical evidence that cannot be proved from retained data.

## Canonical objects, ownership, and lifecycle

| Object | Responsibility and owner | Lifecycle / mutability |
| --- | --- | --- |
| **Workflow Definition** | Stable workspace-scoped identity for a workflow purpose; owned by Workflow Configuration. | Long-lived identity; does not contain mutable published configuration. |
| **Workflow Version** | Complete configuration snapshot for one Definition: steps, transitions, fields, routing, approvals, document generation and publication metadata; owned by Workflow Configuration. | Draft -> Validating -> Ready -> Published -> Superseded -> Archived. Only draft authoring state is mutable. Published snapshots are immutable; restoration creates a new draft. |
| **Workflow Instance** | Runtime execution of one launched Version; owned by Workflow Runtime. | Created from one eligible published Version and permanently stores that Version identifier/snapshot reference. Runtime state evolves without changing the Version. |
| **Logical Document / DocumentVersion** | Documents owns the logical document and immutable versions. | Working content may be drafted; each final/revised execution artifact is a new immutable DocumentVersion. |
| **ApprovalRequirement / ApprovalDecision** | Approvals owns requirements and immutable decisions, as established by ADR-0013. | Decision binds requirement, authority basis, contract state and exact DocumentVersion. |
| **Signature packet and evidence** | Signatures owns dispatch, provider interaction and retained evidence. | Packet binds one final DocumentVersion; terminal evidence is retained, never rewritten. |
| **Contract Record** | Contract Records owns the durable executed agreement and provenance. | Created/promoted only with complete execution evidence; provenance is immutable. |
| **Audit Event** | Audit owns tenant-scoped history. | Facts append; a correction is a later fact, never alteration. |

### Version-owned configuration and instance state

Version-owned configuration is frozen on publication: configuration identity/checksum,
ordered steps and transition graph, field definitions/validation, assignment and
routing rules, approval-rule definitions, document-generation configuration,
signature policy, publication/effective metadata, and compatibility/schema version.

Instance state never modifies the published version: launch actor/time, current work
state, entered values, derived assignments, work-item completion, selected final
document version, generated approval requirements/decisions, signature
packets/evidence, record promotion, recovery attempts, and audit correlations.
Execution projections or caches must remain attributable to the immutable Version
and must not be independently editable configuration.

## Publication, effective use, and retirement

Publication is a distinct server-side authorization decision. Configuration edit
authority never implies publication authority. Before enabling it, the implementation
must define the existing Access Control resolver and policy that authorizes
publication. It must not infer authority from legacy WorkflowTemplate editors or UI
visibility. This decision creates no role and grants no permission; a resolver or
role mapping needs its own approved authority, consistent with ADR-0014.

Before a Version becomes Published, server-side validation must verify a complete
snapshot: reachable start and terminal paths, deterministic transitions and
assignments, versioned fields, required approval/signature configuration,
document-generation references, tenant ownership and runtime compatibility.
Failure preserves the draft, records a non-leaking audit fact, and allows correction
only through draft editing. Publication records actor, time, immutable
checksum/snapshot and validation result in append-only history.

A published Version is eligible for new launches at publication unless it has a
prospective effective time. A future-effective Version is not selectable before that
time. Launch eligibility is a server-side decision over immutable Version and
publication/effective metadata, not a mutable template flag.

If a published Version is discovered invalid or unsafe, new launches must stop through
an auditable launch-eligibility control without altering its snapshot or silently
changing instances. A corrected replacement is authored and published as a new
Version; the defective Version can then be superseded or archived. Supersession
changes only new-launch selection. Archival retains addressability where retention
and access policy permit. Restoration always creates a new draft and never edits a
published Version.

## Launch pinning and live-instance migration

At launch, a Workflow Instance must persist exactly one immutable published Workflow
Version identifier and sufficient immutable snapshot/checksum evidence to prove the
configuration used. Every later workflow step, document, approval, signature and
record-provenance lookup resolves through that pin. A live instance never follows a
newly published default automatically.

Live-instance migration is prohibited by default. It is exceptional, per instance,
and only possible through a later approved implementation and release procedure that
records source/target Versions, reason, state mapping, tenant/access impact,
validation or simulation, actor/authorization, audit correlation, and reversible
compensation. It must not erase or reinterpret prior document, approval, signature,
provenance or audit evidence. This record authorizes neither a blanket migration nor
a new migration privilege.

## Fate of WorkflowTemplate and specialist builders

WorkflowTemplate remains during coexistence as a legacy compatibility object and,
where useful, a specialist authoring façade. It is not a canonical published Version
and cannot be the runtime authority for a new governed launch after cutover.

Specialist builders remain valuable for constrained authoring, seed data and
experience composition. They must create or select a canonical Definition and
eligible immutable Version, then call the shared launch service. They may not
activate or mutate published configuration at runtime, select a mutable template as
authoritative launch identity, or bypass canonical document, approval, signature,
access and audit services.

Legacy instances remain readable through an adapter. A legacy template may map to a
canonical historical Version only where an exact, tenant-correct immutable snapshot
and linkage can be demonstrated. Otherwise it is explicitly legacy/unresolved;
migration must not invent version, approval, signature or provenance facts.

## Final document, approvals, signatures, and record provenance

### Final NDA document and locked-document behaviour

A working DraftDocument may support authoring, but it is not the final approval or
execution authority. The final NDA must be an immutable DocumentVersion with
artifact checksum, source/provenance, logical-document link, and pinned Workflow
Instance/Version correlation. A semantic or content revision creates a new document
version; it never edits a locked version.

After lock, artifact bytes, content/checksum, version identity, source provenance and
finalization facts are immutable. Only distinct governed, audited operations may
occur without changing those facts: access-policy revocation, retention/legal-hold
association, append-only evidence association, and an authorized tombstone/archive
marker. Tombstone/archive must be a narrow allowlist of non-artifact fields and
preserve access-controlled historical evidence. Any correction changing legal or
commercial meaning, content, source or provenance creates a new DocumentVersion.

This resolves C-01's required boundary: the lock guard rejects artifact mutation
while permitting only the listed authorized post-lock operations. It must not become
a general mutable locked document.

### Approval binding and material change

Every generated ApprovalRequirement and immutable ApprovalDecision binds the exact
final DocumentVersion, relevant contract lifecycle/state, requirement/routing
snapshot and evaluated authority basis. ADR-0013 remains authoritative for the
requirement/decision split.

A deterministic, versioned materiality policy invalidates open requirements and
blocks execution when the final content/checksum, term/clause, party, signer,
commercial value, effective date, approval routing, authority basis, or another
policy-defined decision condition changes. The invalidation/reopen is audited and a
replacement decision binds the replacement version. Comments, notifications and
derived read-only projections do not reset approval only where they alter none of
the bound version, contract state, routing or authority basis.

Rejection, revocation, expiration, failed authority resolution and material change
block signature dispatch and record promotion. Delegation must be explicitly
authorized, bind the requirement and version, and retain authority evidence. This
decision adds no delegation role or authorization bypass.

### Signature packet and execution evidence

A signature packet binds one exact final DocumentVersion, intended signers/order,
Workflow Instance/Version and approvals required at dispatch. Retained evidence
proves packet identity, provider or governed alternative channel, exact artifact/hash,
signer identity evidence available to the channel, timestamps, outcome, and provider
receipt/certificate or equivalent execution artifact. Sensitive payload is retained
and exposed only under privacy, retention and object-access policy.

Provider events are idempotent and correlated to the packet. Send failure, expiry,
cancellation, provider disagreement or incomplete evidence leaves the agreement
unexecuted, preserves history, audits outcome and permits governed
retry/reconciliation without fabricating execution. Material document change
invalidates the packet and invokes approval reset before any new dispatch. Provider
activation, credentials and manual/paper alternatives require separate approved
security, data-handling and release authority; this decision claims no current
provider evidence.

### Contract Record creation and provenance

The target executed Contract Record is created or promoted only after required final
document, approvals and signature evidence are complete for the same pinned chain.
It retains immutable provenance to workspace, Definition, exact Version, Instance,
logical Document and DocumentVersion, approval requirements/decisions, signature
packet/evidence, source/correlation identifiers and promoting actor/time.

Missing, mismatched or unauthorized provenance blocks promotion and records a
non-leaking audit fact. Contract data created earlier for intake or working context
is not evidence of an executed record until promotion succeeds. Future import paths
need explicit provenance policy and cannot be presented as workflow-executed NDA
records without equivalent evidence.

## Access, export, and audit

Every operation is subject to explicit server-side workspace, membership, object,
relationship, confidentiality, lifecycle and purpose checks where applicable. The
same decision governs detail pages, direct routes, work queues, search, counts,
autocomplete, notifications, exports, attachments, audit viewers and errors. Denial
must not reveal existence or restricted metadata.

Final-NDA export is a request over an exact authorized artifact and permitted
evidence scope. It re-evaluates object-level access, applies retention/redaction
restrictions, avoids leakage and appends an audit fact with actor, purpose/outcome,
scope and correlation. Export never weakens immutability or makes hidden objects
discoverable.

Minimum audit facts are Definition creation; validation outcome; publication,
eligibility, supersession/archive; instance launch/transition/recovery/migration;
final version and material-change determination/lock/tombstone; approval
requirement/authority/decision/invalidation; signature packet/dispatch/receipt/
reconciliation/evidence/failure; record promotion/block/archive; and authorized
export or safely recorded denial. Facts carry tenant scope, actor/system actor,
time, correlation/idempotency identifier, immutable object/version IDs and a
non-leaking outcome/reason.

## Migration, coexistence, activation, and rollback

Implementation must use additive, reversible-at-rest schema evolution for canonical
objects and pins; preserve legacy identifiers and reads; backfill only provable
facts; mark unmappable history legacy instead of inventing an execution chain; and
retain audit history without rewriting it. The migration plan must define
constraints, batching, tenant isolation, validation, rollback and reconciliation
before execution.

Compatibility adapters may serve legacy details while the new runtime is introduced.
New NDA launches use the canonical path only after controlled activation. Existing
workflows and records must not gain execution claims, access, metadata exposure or
altered history merely by adapter reads.

The feature is default-off until the applicable Charter gate is satisfied. Pilot use
is limited to approved, named workspace(s) and an exact published NDA Version
recorded in release/operator evidence. A feature flag is a safety control, not
authority. Before activation, rollback disables new canonical launches and preserves
legacy reads. After immutable facts exist, rollback is forward-only: disable new
launches or dispatch, preserve instances/documents/evidence, append compensation,
and never delete, remap or alter history.

## Commercial v1 boundary

The first implementation is the NDA vertical slice only. It includes reusable
foundation needed to launch and finish an NDA with pinned configuration, final
DocumentVersion, approval reset, signature evidence, record provenance,
access/export and audit. It excludes an immediate generic Workflow Designer rewrite;
DPA, MSA and SOW conversion; broad legacy migration; new provider activation; new
roles, permissions or lifecycle terms without authority; AI, analytics, billing, OCR
and unrelated test cleanup.

The foundation is reusable, but no other contract type is commercially or
operationally complete merely because it may later use the runtime.

## Alternatives considered

| Alternative | Decision | Rationale |
| --- | --- | --- |
| Retain mutable WorkflowTemplate runtime | Rejected | Cannot prove published immutability, configuration identity, launch pinning or safe recovery. |
| Canonical Definition/immutable Version; specialist builders as façades | **Selected target** | Meets accepted domain invariants while retaining specialist authoring and launch experiences. |
| Immediate universal Workflow Designer rewrite | Rejected | Expands scope, migration risk and proof burden before the NDA blocker is resolved. |
| Incremental controlled activation | **Selected delivery strategy** | Preserves legacy reads, confines evidence to an approved pilot and avoids inferred backfills. |

## Required implementation proof and acceptance criteria

No implementation may claim the NDA journey complete until the reviewed
implementation SHA proves:

1. published configuration cannot mutate and restoration creates a new draft/version;
2. launch pins exactly one eligible immutable Version and later publication leaves
   live instances unchanged;
3. final NDA DocumentVersion immutability holds while the narrow C-01
   tombstone/archive path works and audits;
4. approvals bind exact final document version and deterministically reset on
   material change;
5. signature packet and retained execution evidence bind that version; duplicate
   provider delivery is idempotent and failure/retry cannot execute it;
6. Record promotion requires complete, matching immutable provenance;
7. owner, member, denied, cross-tenant and restricted-metadata access/export cases
   do not leak;
8. append-only audit history correlates every golden-journey and recovery step;
9. migration, legacy read compatibility, rollback and reconciliation do not
   fabricate historical evidence; and
10. happy, material-revision, provider-failure, unauthorized-export and
    archive/recovery paths work end to end.

Evidence uses GitHub reviews, CI, immutable SHA and operator/release mechanisms.
This record contains no copied approval statement, manual vote table or hand-entered
approval timestamp.

## Delivery sequence and stop conditions

1. Accept this combined decision (or an approved replacement) without attaching
   production implementation.
2. Deliver one coherent canonical-workflow/NDA-execution PR: additive migration,
   publication/pinning, final document, approval/reset, signature evidence, record
   promotion, access/export, archive/recovery and integrated tests.
3. Activate only after the applicable independent review, CI and named-environment
   evidence requirements are met.

Stop and return to governance rather than weaken tests or invent facts if a needed
role, permission, lifecycle state, provider channel, retention rule or migration
authority is not accepted; a published Version can mutate; a live instance loses
its pin; material change crosses an approval/signature; provenance or audit cannot
be preserved; or an access/export path leaks restricted metadata.

## Consequences

This creates a bounded path to a truthful NDA golden journey and avoids a
repository-wide rewrite. It also requires specialist flows to use shared canonical
services and legacy history to be treated honestly. The immediate consequence is
documentation-only: no production behaviour, schema, permission, workflow, route
or provider configuration changes in this record.
