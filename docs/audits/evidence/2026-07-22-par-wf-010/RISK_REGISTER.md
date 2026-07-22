# PAR-WF-010 — Risk register

**Date:** 2026-07-22  
**Review cadence:** Before each cutover phase gate

| ID | Risk | Likelihood | Impact | Mitigation | Owner phase |
|---|---|---|---|---|---|
| R-01 | **Incorrect instance pinning** — instance bound to wrong version after migrate | M | H | Characterization tests; dual-read divergence logging; governed migrate requires reason + audit; re-forward proof | Phase 2–3 |
| R-02 | **Active workflow disruption** — in-flight instances break on cutover | M | H | No in-place published edits; migrate optional; prefer new launches; pilot flag gating | Phase 3–4 |
| R-03 | **Broken FK graph** — child config orphaned when template split | M | H | Additive nullable FKs first; backfill script with row counts; rollback migrations tested | Phase 1 |
| R-04 | **Duplicate published versions** — multiple `is_active=True` in one family today | L | M | Today UI discourages; target DB partial unique on `PUBLISHED`; backfill normalizes to single published | Phase 1 backfill |
| R-05 | **Launch routing drift** — cockpits resolve different version than generic create | M | H | Unify on `get_published_version(definition)`; routing tests for DPA/MSA/NDA | Phase 4 |
| R-06 | **Audit history loss** — events reference template IDs that disappear | L | H | Never delete template rows in phase 1–4; audit payload includes both IDs during dual-write | All phases |
| R-07 | **Contract provenance drift** — `origin_workflow_template_*` out of sync with instance pin | M | H | `pin_workflow_provenance` sets both during dual-write; provenance immutability locks; repair command | Phase 3 |
| R-08 | **Cross-tenant leakage** — definition/version queries miss org scope | L | H | Port `scope_workflow_templates_for_organization` to definition scope; isolation tests | Phase 2+ |
| R-09 | **Rollback failure** — irreversible migration applied too early | L | H | No irreversible constraints until phase 5; checkpoint at 0115; ops drill | Phase 1 |
| R-10 | **WorkflowStep.template_step stale after instance migrate** — step FK points to old version's steps | M | M | Document current behavior; cutover policy: rematerialize steps or block migrate if topology differs | Phase 4 |
| R-11 | **Seed migration brittleness** — DPA/MSA/NDA seeds located by name string | M | H | Backfill assigns stable definition slugs; seeds add slug lookup; staging verify | Phase 1 |
| R-12 | **NDA provenance gap** — launch without `pin_workflow_provenance` | H | M | Safe fix: add pin call (preparatory, not cutover) | Phase 0 |
| R-13 | **Feature flag misconfiguration** — single-write enabled globally by mistake | L | H | Default off; org-level opt-in; deploy checklist | Phase 3–4 |
| R-14 | **Performance regression** — extra joins on definition/version reads | M | L | Indexes on `(organization, definition)`, `(definition, status)`; query audit in dual-read | Phase 2 |
| R-15 | **ADR authority confusion** — team treats ADR-0010 as cutover approval | M | H | Roadmap + ADR-0012 explicit: 0010 interim only; 0012 required for schema | Governance |

---

## Risk acceptance (discovery phase)

All production cutover risks are **not accepted** — PAR-WF-010 remains blocked pending architecture approval.

## Escalation triggers

- Any dual-read divergence in staging
- Instance migrate without audit event
- Published version mutated in place
- Cross-tenant template/version visible in list/detail
