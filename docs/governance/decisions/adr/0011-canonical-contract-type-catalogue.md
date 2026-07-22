# ADR-0011: Canonical Contract Type catalogue (G-DOM-02)

**Status:** Proposed  
**Date:** 2026-07-22  
**Owner:** Platform engineering  
**Affected Charter sections:** Domain model integrity; configuration governance  
**Related PDRs:** PDR-0003 (documentation operating model)  
**Related exceptions:** None  

## Context

CLM One currently maintains two competing Contract Type definitions:

1. **`Contract.ContractType` TextChoices** on `Contract.contract_type` (21 values) — used by repository filters, forms, imports, integrations, policies, and launch metadata.
2. **`ContractType` model** — global catalogue rows; only DPA/MSA/NDA were seeded; bound to `WorkflowTemplate.contract_type`.

This violates CANONICAL_DOMAIN_MODEL §2.6 (“Contract Type — a governed classification”) and gap audit **G-DOM-02**. Values can drift (e.g. inbound import validator stale; display maps missing `ORDER_CONFIRMATION`).

PAR-CORE-002 must complete **before** PAR-WF-010 production cutover so workflow Definition work does not encode the dual-type trap.

## Decision

**The `ContractType` model catalogue is canonical.** Each catalogue row has a stable `code` aligned with the existing enum vocabulary.

- **`Contract.contract_type_catalogue`** FK is the authoritative write/read binding for Contract Records.
- **`Contract.contract_type`** CharField remains a **transitional denormalized code mirror** synced on `Contract.save()` for filters, integrations, and legacy readers until a follow-on removal ADR.
- All production writers route through `contracts.services.contract_type_catalogue` (`assign_contract_type`, `sync_contract_type_catalogue_fields`).
- Unknown import strings map to **`OTHER`** explicitly; legacy aliases (`SERVICE` → `SOW`, etc.) are documented — never silently merged into semantically different types.
- Catalogue mutations are admin-governed with audit event `contract_type.catalogue.updated`.
- Contract type repairs emit `contract.type.catalogue.repaired`.

### Removal criteria for transitional CharField

The CharField may be removed only when:

1. All repository/search/analytics/integration readers use the FK or catalogue service.
2. `ContractTemplate.contract_type` and clause/approval string fields are migrated or validated against the catalogue.
3. Migration evidence shows zero unmappable production rows without explicit `OTHER` classification.
4. A follow-on **Accepted** ADR authorizes enum/CharField removal.

## Alternatives considered

### Alternative 1 — Keep TextChoices as canonical

Rejected: cannot bind workflow templates, cannot govern lifecycle of type metadata, contradicts CANONICAL_DOMAIN_MODEL §2.6.

### Alternative 2 — Org-scoped type catalogue immediately

Deferred: current pilot uses a global catalogue; tenant-scoped catalogue requires product decision on shared vs workspace types.

### Alternative 3 — Big-bang enum removal in PAR-CORE-002

Rejected: high blast radius (~53 enum consumer files); expand-contract with dual-sync is safer.

## Consequences

### Positive

- Single write path via catalogue service and `Contract.save` sync.
- Workflow templates and contract rows share catalogue rows.
- Truthful backfill for historical contracts.

### Negative

- Temporary dual-field storage until CharField removal.
- Satellite dicts (`LAUNCH_SETUP_CONFIG`, `_CONTRACT_TYPE_SHORT`) still keyed by code strings.

### Risks

- Drift if a writer bypasses `Contract.save` — mitigated by `bulk_create` hook and import helpers.
- Global catalogue may need org scope later.

### Migration

- `0107_contract_type_catalogue_fk`: seed 21 catalogue rows; backfill FK; map legacy aliases; unmappable → `OTHER`.

### Rollback

- Reverse migration clears FK; CharField remains authoritative for readers.

## Security and privacy impact

- Catalogue is global configuration; contract rows remain tenant-isolated via `Contract.organization`.
- Type repair requires workspace OWNER/ADMIN/staff (reuses provenance repair authorization).

## Data and audit impact

- Events: `contract.type.catalogue.assigned`, `contract.type.catalogue.repaired`, `contract_type.catalogue.updated`.
- No invented historical types; unmappable values explicitly `OTHER`.

## Test evidence required

- Catalogue seed completeness (21 codes).
- Contract create/import/workflow paths set FK.
- Legacy alias mapping.
- Tenant-isolated repair authorization.
- Migration forward / rollback / re-forward.

## Approval

**Proposed — not Accepted.** Implementation in PAR-CORE-002 follows Accepted CANONICAL_DOMAIN_MODEL §2.6 and expand-contract pattern; irreversible CharField removal awaits Acceptance of this ADR (or successor) and removal criteria above.
