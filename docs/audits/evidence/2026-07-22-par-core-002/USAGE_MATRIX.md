# PAR-CORE-002 — Contract Type usage matrix (G-DOM-02)

## Definitions found

| Record | Module | Meaning | Identifiers | Classification |
|---|---|---|---|---|
| `Contract.ContractType` TextChoices | `contracts/models.py` | 21-value vocabulary on Contract row | `NDA`, `MSA`, `DPA`, … | **Legacy / transitional mirror** (denormalized code) |
| `ContractType` model | `contracts/models.py` | Governed catalogue row | `code` (unique), `name`, `is_active` | **Canonical** |
| `Contract.contract_type` CharField | `contracts/models.py` | Stored code on Contract Record | enum string | **Duplicate / transitional** (synced from catalogue) |
| `Contract.contract_type_catalogue` FK | `contracts/models.py` | Canonical binding | FK → `ContractType` | **Canonical write path** |
| `WorkflowTemplate.contract_type` FK | `contracts/models.py` | Template type binding | FK → `ContractType` | **Canonical** |
| `ContractTemplate.contract_type` CharField | `contracts/models.py` | Template shelf lookup | enum string | **Legacy** (not migrated this slice) |
| `ClauseTemplate.applicable_contract_types` | `contracts/models.py` | Comma-separated codes | free string | **Legacy / presentation** |
| `ClauseVariant.contract_type` | `contracts/models.py` | Variant scope | free string | **Legacy** |
| `ApprovalRule.trigger_value` | `contracts/models.py` | Rule match when CONTRACT_TYPE | string code | **Legacy** (must match catalogue codes) |
| `WorkInteractionEvent.contract_type` | `contracts/models.py` | Denormalized snapshot | string | **Presentation-only** |
| `ListParams.contract_type` | `contracts/domain/contracts.py` | Repository filter transport | list[str] | **Presentation-only** |
| `LAUNCH_SETUP_CONFIG` / `CARD_META` | `contract_launch_setup.py` | Launch UI metadata | enum-keyed dict | **Presentation-only** |
| `VALID_CONTRACT_TYPES` (removed) | `inbound_import.py` | Stale validator | — | **Removed** → catalogue service |
| `_CONTRACT_TYPE_SHORT` | `clmone_format.py` | Display abbreviations | dict | **Presentation-only** (drift residual) |

## Consumer summary

| Category | Approx. files | Write path post PAR-CORE-002 |
|---|---:|---|
| Contract create/edit | 12 | `Contract.save` → `sync_contract_type_catalogue_fields` |
| Workflow DPA/MSA/NDA | 3 | enum on create + save sync + template FK |
| Imports (CSV/inbound/SF/NS) | 5 | `assign_contract_type` / save sync |
| Repository/search/API | 8 | Read `contract_type` mirror (FK filter available) |
| Forms | 1 | Choices from catalogue; posts code |
| Admin | 2 | `ContractTypeAdmin` governed; Contract unchanged |
| Seeds | 9 | save sync on create |
| Tests | 57+ | enum strings still valid via mirror |

## Data volume / tenant

| Artefact | Scope | Volume (dev DB) |
|---|---|---|
| `ContractType` rows | Global | 21 (all enum codes seeded) |
| `Contract.contract_type_catalogue` | Per contract | Backfilled on migrate |
| Workflow template FK | Global/org templates | DPA/MSA/NDA (+ any designer-created) |

Tenant boundary: catalogue is global configuration; contract rows isolated by `organization`. Repairs require OWNER/ADMIN/staff in contract workspace.

## Migration risk (per path)

| Path | Risk | Mitigation |
|---|---|---|
| Historical contracts | Medium | Backfill FK; unmappable → `OTHER` |
| Import alias `SERVICE` | Low | Explicit map to `SOW` |
| Workflow template FK | Low | Existing DPA/MSA/NDA rows preserved |
| Filter/report on char field | Low | Mirror kept in sync |
| CharField removal | High | Deferred; ADR-0011 removal criteria |

## PAR-CORE-002 resolution

| Before | After |
|---|---|
| 3 catalogue rows; 21 enum values; dual write | 21 catalogue rows; FK canonical; char mirror synced |
| Inbound validator stale | `validate_import_contract_type` + alias map |
| No admin for catalogue | `ContractTypeAdmin` + audit |
| Workflow/contract drift possible | Shared catalogue codes |

## Blockers removed

G-DOM-02 dual definition **resolved for production writes** with explicit transitional char mirror. Irreversible enum removal remains gated on **Accepted ADR-0011**.
