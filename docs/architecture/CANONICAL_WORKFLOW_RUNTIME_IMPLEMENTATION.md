# Canonical Workflow Runtime Implementation Note

**Status:** Implemented, default-off; not activation authority.
**Authority:** The active Governance Charter, accepted supporting documentation,
and approved PDR-0006. This note records the implemented boundary; it does not
grant release, provider, migration, or legacy-retirement authority.

## Implemented chain

Migration `0116_canonical_workflow_nda_runtime` is additive and contains no
historical backfill. It adds the following new canonical objects alongside the
legacy workflow path:

`WorkflowDefinition → WorkflowVersion → WorkflowInstance → DocumentVersion →
ApprovalRequirement/ApprovalDecision → SignaturePacket/SignatureEvidence →
ContractRecord`.

`WorkflowVersion` owns its JSON configuration snapshot and SHA-256 checksum.
Draft configuration can be validated; a successful governed publication freezes
the snapshot. Later publication supersedes only the default for future launches.
Every `WorkflowInstance` stores the exact published version and never follows a
replacement version automatically.

The implementation deliberately does not wire `WorkflowTemplate`, the existing
NDA builder, or any legacy workflow to this runtime. Existing data is neither
converted nor reclassified. The legacy builder remains readable and unchanged.

## Authorization and controlled exposure

The publication service has a testable policy boundary. Its default policy denies
publication. `ExistingWorkspacePublicationPolicy` is a narrow adapter to the
existing organization-management access rule; it does not create a role, change
the process-role resolver, or widen permissions.

Launch is fail-closed and requires both settings below:

```text
CANONICAL_NDA_RUNTIME_ENABLED=false
CANONICAL_NDA_RUNTIME_ORG_ALLOWLIST=
```

The committed defaults are off and an empty allowlist permits no workspace. An
allowlisted, named non-production workspace still requires the Charter's review,
CI, operator, abort, and rollback evidence before any activation. A flag never
authorizes activation by itself.

## Execution invariants

- Final execution authority is an immutable `DocumentVersion`, never a
  `DraftDocument`.
- Canonical approval requirements and immutable decisions bind the same workflow
  instance and final document version. A material final-document revision
  appends revocation facts, invalidates active requirements, and requires a new
  requirement/decision.
- `SignaturePacket` and append-only `SignatureEvidence` bind the exact final
  document version. Dispatch records a provider-neutral intent only; no provider
  is selected, credentialed, or contacted by this path. A material change
  cancels unsent or active packets.
- `ContractRecord` can be promoted only after version-bound approvals, a signed
  packet, and retained evidence exist. Its chain provenance is immutable.
- Export rechecks contract object access and records an allow/deny audit event.
  The service returns no record metadata on denial.
- Locked document artifacts remain immutable while tombstone metadata can be
  changed through the existing narrow non-artifact path.

All material actions use the append-only tenant audit service with instance,
version, document, or packet correlations as applicable.

## Migration and rollback

`0116` only creates new tables and adds a nullable `ApprovalRequirement`
reference. It does not alter, copy, delete, or infer historic workflow,
approval, signature, document, or Contract provenance. Before any canonical
row is created in an activated environment, the migration can be reversed by
Django in the normal way after confirming the new tables are empty.

After canonical evidence exists, rollback is **forward-only**: disable
`CANONICAL_NDA_RUNTIME_ENABLED`, clear its allowlist, stop new canonical
launches, and retain all immutable facts. Do not reverse the migration or delete
canonical evidence as an operational rollback. Any later legacy cutover,
historical mapping, or production migration requires its own approved plan and
evidence.

## Verification included in this implementation

`tests/test_canonical_workflow_nda_runtime.py` proves the default-off gate,
published configuration immutability, launch pinning, final-document binding,
approval reset, signature evidence idempotency, ContractRecord promotion,
archival/export authorization, cross-tenant denial, and the locked-document
tombstone regression. It is implementation evidence only, not an activation or
production-execution claim.
