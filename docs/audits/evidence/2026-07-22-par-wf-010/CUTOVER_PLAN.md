# PAR-WF-010 — Cutover plan

**Date:** 2026-07-22  
**Status:** Plan only — **no production execution**  
**Blocked by:** Accepted ADR-0012 (Proposed) + ops migration window

---

## Principles

1. **Additive first** — no destructive drops until removal criteria met.
2. **Truthful backfill** — never invent definition lineage; mark `legacy_unknown` families explicitly.
3. **Dual-read before single-write** — feature flag default off.
4. **Pilot protection** — DPA/MSA/NDA seeded workflows unchanged until ops sign-off.
5. **Rollback checkpoints** — each phase reversible without data loss.

---

## Phase 0 — Discovery (this PAR slice) ✅

| Deliverable | Status |
|---|---|
| CURRENT_MODEL_MATRIX.md | Done |
| TARGET_AGGREGATE.md | Done |
| CUTOVER_PLAN.md | Done |
| RISK_REGISTER.md | Done |
| CHARACTERIZATION_TESTS.md | Done |
| Proposed ADR-0012 | Done |
| Characterization tests | `test_par_wf_010_characterization.py` |

**No schema changes.**

---

## Phase 1 — Additive schema (blocked until ADR Accepted)

### Migration sequence (planned)

| # | Migration | Operations |
|---|---|---|
| 1 | `0110_workflow_definition_entity` | Create `WorkflowDefinition`; indexes; org + contract_type FK |
| 2 | `0111_workflow_version_entity` | Create `WorkflowVersion`; FK definition; lifecycle status; publish metadata; unique `(definition, version_number)` |
| 3 | `0112_workflow_template_backlink` | Add nullable `WorkflowTemplate.workflow_version_id` (OneToOne or FK) |
| 4 | `0113_workflow_instance_version_pin` | Add nullable `Workflow.workflow_version_id`; `Contract.origin_workflow_version_id` |
| 5 | `0114_child_config_version_fk` | Add nullable `workflow_version_id` on steps/fields/routes/scenarios (parallel to template FK) |
| 6 | `0115_backfill_definitions` | RunPython: group templates by `(name, category, organization)` → Definition; each row → Version |

### Backfill rules

| Source | Target rule |
|---|---|
| Template family | One `WorkflowDefinition` per distinct `(name, category, organization)` |
| Each `WorkflowTemplate` row | One `WorkflowVersion` with same `version_number`, `is_active` → status mapping |
| `parent_template` chain | `WorkflowVersion.derived_from` optional FK |
| Global seeds (org NULL) | Definition `organization=NULL`, stable slug from name |
| Ambiguous families (name collision across categories) | **Do not merge** — separate definitions |
| Missing org on tenant template | Flag for manual repair; do not guess tenant |
| Active instances | `Workflow.workflow_version_id` = backfilled version for pinned `template_id` |
| Contract provenance | `origin_workflow_version_id` from pinned template's version row |
| Unmappable rows | `legacy_unknown_definition_key` audit report row |

### Rollback (phase 1)

- Reverse migrations 0115→0110
- Nullable FKs dropped; `WorkflowTemplate` remains authoritative
- No data loss on `WorkflowTemplate` rows

---

## Phase 2 — Dual-read compatibility layer (flag: `WORKFLOW_DEFINITION_DUAL_READ`)

| Component | Behavior |
|---|---|
| **Read path** | Services resolve version via `workflow_version_id` if set, else `template_id` |
| **Write path** | Still writes **only** `WorkflowTemplate` (no behavior change) |
| **Audit** | Optional debug logging of read divergence |
| **Tests** | Prove read equivalence for all launch/materialize paths |

**Rollback:** Disable flag; reads use template only.

---

## Phase 3 — Dual-write (flag: `WORKFLOW_DEFINITION_DUAL_WRITE`)

| Component | Behavior |
|---|---|
| **Create definition/version** | Write both legacy template row AND new version row (linked) |
| **Clone/restore/publish** | Dual-write both sides in one transaction |
| **Launch** | Set both `template_id` and `workflow_version_id` |
| **Provenance** | Set both template and version FKs on contract |

**Pilot gate:** Flag enabled only for non-pilot orgs OR explicit pilot opt-in after regression suite.

**Rollback:** Disable dual-write; new version rows become stale but harmless; template remains source of truth.

---

## Phase 4 — Single-write transition (flag: `WORKFLOW_DEFINITION_SINGLE_WRITE`)

| Component | Behavior |
|---|---|
| **Designer** | Operates on `WorkflowVersion` drafts; template rows created as compatibility mirror (read-only) |
| **Launch** | Resolves published version by definition; sets `workflow_version_id` primary |
| **Cockpits** | `get_*_workflow_template()` → `get_published_version(definition)` |
| **Admin** | Template admin read-only / deprecated banner |

**Rollback checkpoint:** Re-enable dual-write; freeze single-write migrations.

---

## Phase 5 — Legacy removal (criteria below)

| Action | Criteria |
|---|---|
| Drop `Workflow.template_id` | Zero reads for 2 release cycles; all instances have `workflow_version_id` |
| Drop `WorkflowTemplate` table | All child FKs migrated; seeds re-homed to definitions |
| Drop compatibility flags | Single-write stable in production ≥ 1 release |

---

## Feature flags (planned)

| Flag | Default | Purpose |
|---|---|---|
| `WORKFLOW_DEFINITION_DUAL_READ` | `False` | Read new model, write old |
| `WORKFLOW_DEFINITION_DUAL_WRITE` | `False` | Write both models |
| `WORKFLOW_DEFINITION_SINGLE_WRITE` | `False` | Write new model only |
| `WORKFLOW_DEFINITION_DESIGNER_V2` | `False` | Definition-centric designer UI |

Flags live in Django settings / org feature table — **not implemented in this slice**.

---

## Pilot protection

| Pilot asset | Protection |
|---|---|
| DPA template (migration 0071) | No re-seed; backfill maps to definition by name+contract_type |
| MSA template (0075) | Same |
| NDA template (0077) | Same |
| PayrollMinds demo | `seed_payrollminds_demo.py` — verify after phase 3 in staging only |
| Controlled-pilot nav gates | `nav_config.py` — designer access unchanged until flag |

---

## Forward / rollback / re-forward proof (required before phase 3)

| Step | Command / test |
|---|---|
| Forward | `migrate contracts 0115` on staging copy |
| Rollback | `migrate contracts 0109` (pre-definition) |
| Re-forward | `migrate contracts 0115` |
| Data check | Count definitions == distinct template families; instances pinned |
| Test suite | Full workflow + provenance + characterization tests green |

Evidence filenames (to capture at execution time): `migrate-forward.txt`, `migrate-rollback.txt`, `migrate-reforward.txt`, `django-tests.txt`

---

## Safe preparatory work (allowed now, without ADR Acceptance)

- Characterization tests (`test_par_wf_010_characterization.py`)
- Evidence documentation (this folder)
- Proposed ADR-0012
- NDA `pin_workflow_provenance` alignment (behavior fix, not schema)
- Compatibility layer **design stubs** behind unexported modules (optional — not in this commit unless minimal)

## Blocked until Accepted ADR

- Migrations 0110+
- Production feature flags enabled
- Launch path redirect
- Designer UI cutover
- `WorkflowTemplate` field removal

---

## Removal criteria for legacy `WorkflowTemplate` semantics

1. Accepted ADR-0012 (or successor) recorded.
2. All production instances have `workflow_version_id` populated.
3. All contract provenance rows have `origin_workflow_version_id` or explicit `legacy_unknown`.
4. Dual-read divergence zero for 30 days in staging.
5. Pilot workflows verified in staging.
6. Ops runbook signed off.
7. Rollback drill completed once.
