# PAR-WF-010 — Characterization tests

**Date:** 2026-07-22  
**Purpose:** Lock current interim behavior before Definition/Version cutover

---

## Principle

Characterization tests describe **what the system does today**, not what it should do after cutover. They must pass throughout dual-read and fail loudly if interim semantics regress.

---

## Existing test inventory (reuse — do not duplicate)

| Module | Behaviors locked |
|---|---|
| `tests/test_platform_workflow_invariants.py` | Default unpublished; published immutability; simulation no writes; migrate requires reason + audit; publish validation gate |
| `tests/test_workflow_template_versioning.py` | Clone, restore, compare, version list, tenant scope, stepless templates |
| `tests/test_workflow_designer_canvas.py` | Published read-only UI; create version; launch blocked; scenarios; audit tab |
| `tests/test_workflow_simulation.py` | Dry-run conditions; no DB records; cross-tenant block |
| `tests/test_workflow_execution.py` | Materialize steps; branch skip; completion; escalation |
| `tests/test_workflow_routing.py` | Template suggestion; auto-select on create |
| `tests/test_workflow_audit_trail.py` | All template/workflow audit events |
| `tests/test_par_core_003_provenance.py` | `origin_workflow_template_id` / version on contract |
| `tests/test_dpa_workflow.py` | Seeded DPA template lookup + instance create |
| `tests/test_msa_workflow.py` | Seeded MSA template |
| `tests/test_nda_workflow.py` | Seeded NDA template |
| `tests/test_cross_tenant_isolation.py` | `WorkflowIsolationTest` |
| `tests/test_migration_0105_gate_proof.py` | Unpublished default preserved |

---

## New tests added (PAR-WF-010 slice)

**File:** `tests/test_par_wf_010_characterization.py`

| Test | Behavior locked |
|---|---|
| `test_template_family_lineage_groups_by_name_category_org` | `list_template_versions()` implicit definition family |
| `test_workflow_instance_pins_specific_template_row_version` | `Workflow.template_id` is the version pin |
| `test_contract_provenance_pins_template_id_and_version_number` | `pin_workflow_provenance` sets template FK + int version |
| `test_materialized_steps_reference_pinned_version_not_latest_draft` | Materialize uses pinned template's steps, not newer draft |

---

## Recommended tests before phase 3 (not yet implemented)

| Test | Behavior to lock |
|---|---|
| NDA launch calls `pin_workflow_provenance` | Close R-12 gap |
| Dual-read equivalence | Same launch outcome from template vs version ID |
| Single published per family after backfill | Backfill normalization |
| `WorkflowStep.template_step` consistency after instance migrate | R-10 policy |
| Cockpit `get_*_workflow_template` matches routing suggestion | R-05 |

---

## Test execution

```bash
# PAR-WF-010 characterization only
make test-fast APP=tests.test_par_wf_010_characterization

# Full workflow regression bundle (recommended before any cutover phase)
make test-fast APP=tests.test_platform_workflow_invariants
make test-fast APP=tests.test_workflow_template_versioning
make test-fast APP=tests.test_par_wf_010_characterization
make test-fast APP=tests.test_par_core_003_provenance
```

---

## Results (2026-07-22)

| Suite | Result |
|---|---|
| `test_par_wf_010_characterization` | See `django-tests.txt` |
| `test_platform_workflow_invariants` | Existing — run in CI |
| `test_workflow_template_versioning` | Existing — run in CI |

**Note:** Cutover-phase tests (dual-read, backfill) are **documented only** — implemented when ADR Accepted and migrations land.
