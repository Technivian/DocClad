# PAR-CORE-002 evidence summary — 2026-07-22

## Status: Completed

### Canonical choice
**`ContractType` model catalogue** is canonical (CANONICAL_DOMAIN_MODEL §2.6).  
`Contract.contract_type` CharField is a transitional denormalized code mirror synced on save.

### Decision record
- **Proposed ADR-0011** (`docs/governance/decisions/adr/0011-canonical-contract-type-catalogue.md`) — documents expand-contract pattern and CharField removal criteria. **Not Accepted** (removal gate only; implementation follows Accepted domain model).

### Suites
- `django-tests.txt` — 48 OK (CORE-002 + CORE-003 + CORE-001 ownership)

### New / changed modules
- `contracts/services/contract_type_catalogue.py`
- `Contract.contract_type_catalogue` FK
- `ContractTypeAdmin` with governed catalogue audit

### Migrations
- `0107_contract_type_catalogue_fk` — seed 21 catalogue rows; backfill FK; legacy alias `SERVICE`→`SOW`; unmappable→`OTHER`

### Audit events
- `contract.type.catalogue.assigned`
- `contract.type.catalogue.repaired`
- `contract_type.catalogue.updated`

### Residual (explicit)
- CharField `contract_type` not removed (await ADR-0011 Acceptance + removal criteria).
- `ContractTemplate.contract_type` still enum CharField (read via synced codes).
- Satellite display maps (`_CONTRACT_TYPE_SHORT`) not fully reconciled in this slice.

### Next roadmap item
**PAR-DOC-001**
