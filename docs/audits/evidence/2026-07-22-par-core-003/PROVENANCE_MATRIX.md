# PAR-CORE-003 — Contract Record provenance matrix

## Paths inspected

| Path | Location | Create? | Mutate? |
|---|---|---|---|
| Manual UI create | `contracts/views_domains/contracts.py` `ContractCreateView` | Yes | — |
| DPA workflow | `contracts/services/dpa_workflow.py` | Yes | parent link |
| MSA workflow | `contracts/services/msa_workflow.py` | Yes | — |
| NDA workflow | `contracts/services/nda_workflow.py` | Yes | — |
| AI / document upload | `contracts/api/documents_ai.py` | Yes | — |
| Salesforce upsert | `contracts/services/salesforce.py` | Yes | Yes |
| NetSuite upsert | `contracts/services/netsuite.py` | Yes | Yes |
| CSV import | `contracts/management/commands/import_contracts_csv.py` | Yes | Yes |
| Inbound import | `contracts/services/inbound_import.py` | Yes | — |
| Import lifecycle helper | `contracts/services/contract_import_lifecycle.py` | Shared | Shared |
| Django admin | `contracts/admin.py` `ContractAdmin` | Yes | Fields readonly |
| Seeds / demos | `seed_demo`, `seed_payrollminds_demo`, `seed_data` | Yes | update_or_create |
| Load / profile cmds | `run_core_load_test`, `profile_authenticated_routes` | Yes (test) | — |
| Sprint evidence seed | `seed_sprint3_evidence` | Yes | — |
| Renewals / amendments | Manual create with `parent_contract` | Via UI | No clone API |
| Lifecycle jobs | `run_contract_lifecycle_jobs` | No | Status/stage only |
| Approval `QuerySet.update` | `approval_workflow.py` | No | Approval fields only |
| `Contract.objects.bulk_create` | Manager override | Guarded | — |
| `QuerySet.update` provenance | Manager override | Blocked | Blocked |
| Migrations | `0106_…` backfill | Classify only | — |
| Fixtures | None shipping Contract fixtures found | — | — |

## Provenance matrix (post PAR-CORE-003)

| Path | origin_kind | Workflow pin | Source identity | Actor | Reason / correlation | Locked | Audit |
|---|---|---|---|---|---|---|---|
| Manual UI | `MANUAL` | — | — | request user | `Created via contract form` | Yes | `contract_created` ≡ record.created + `provenance_assigned` |
| DPA/MSA/NDA | `WORKFLOW` | Instance + template + version | — | workflow user | channel `*_workflow` | Yes after pin | `record.created` / `provenance_assigned` |
| Upload | `UPLOAD` | — | — | request user | channel `documents_ai_upload` | Yes | `contract.uploaded` ≡ + `provenance_assigned` |
| Salesforce / NetSuite | `INTEGRATION` | — | `source_system` + id | system/actor | channel salesforce/netsuite | Yes | via import helper |
| CSV | `IMPORT_CSV` | — | optional | optional | `provenance_correlation_id` | Yes | via import helper |
| Inbound | `IMPORT_INBOUND` | — | — | import user | channel inbound | Yes | via import helper |
| Admin | `ADMIN` | — | — | admin user | `Created via Django admin` | Yes | record.created + assigned |
| Seeds | `SEED` | — | — | seed user | seed reason | Yes | seed audits where present |
| Unclassified create / bulk | `LEGACY_UNKNOWN` | — | — | — | — | Yes | none claimed |
| Historical backfill | `WORKFLOW` / `INTEGRATION` / `LEGACY_UNKNOWN` | when Workflow exists | when source ids exist | never invented | never invented | Yes | migration only |

## Gaps closed

| Gap | Resolution |
|---|---|
| No origin classification | `origin_kind` + `origin_channel` |
| Workflow lineage not pinned on Contract | `origin_workflow` + template FK + denormalized version |
| Import creates without provenance audit | import helper emits created + assigned |
| Provenance editable in admin / save | readonly admin; `Contract.save` immutability; QuerySet.update blocklist |
| Silent repair | `repair_contract_provenance` requires OWNER/ADMIN/staff + reason + `provenance_repaired` |
| Cross-tenant repair | organization mismatch → `PermissionDenied` |
| bulk_create bypass | stamps `LEGACY_UNKNOWN` + lock |

## Residual (honest)

- UI provenance panel not added (server-side completeness is the vertical slice).
- `seed_sprint3_evidence` / load-test creates still classify as `LEGACY_UNKNOWN` unless updated later.
- No DB NOT NULL / CHECK yet — deferred until production distributions prove safe.
- DPA/MSA/NDA suite currently errors on unrelated `WorkflowLaunchBlocked` assignee gating (pre-existing vs this change); provenance pin is covered by unit tests.
