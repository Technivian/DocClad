# PAR-WF-010 evidence summary — 2026-07-22

## Status: Blocked pending architecture approval

Discovery and cutover **design** complete. **No production cutover** performed.

### Deliverables

| File | Purpose |
|---|---|
| `CURRENT_MODEL_MATRIX.md` | Every workflow model/path — current meaning, consumers, risks |
| `TARGET_AGGREGATE.md` | Canonical Definition → Version → Instance → Record design |
| `CUTOVER_PLAN.md` | Phased additive migration, dual-read/write, rollback checkpoints |
| `RISK_REGISTER.md` | 15 identified risks with mitigations |
| `CHARACTERIZATION_TESTS.md` | Existing + new test inventory |
| `django-tests.txt` | Characterization test run output |

### ADR conclusion

| ADR | Role | Status |
|---|---|---|
| **ADR-0010** | Interim instance pinning only (`Workflow.template` FK, governed migrate) | **Proposed — not authorizing cutover** |
| **ADR-0012** | Full Definition/Version aggregate + cutover phases | **Proposed — required for production cutover** |

ADR-0010 is **insufficient** for PAR-WF-010 production cutover. Do not expand its authority silently.

### Human approval required

1. **Accept ADR-0012** (or amended successor) per GOVERNANCE_CHARTER
2. **Ops migration window** sign-off before phase 3 (dual-write)
3. **Pilot workflow verification** sign-off (DPA/MSA/NDA seeds)

### Safe preparatory work completed

- Evidence package (this folder)
- Proposed ADR-0012
- Characterization tests: `tests/test_par_wf_010_characterization.py`

### Blocked work (not started)

- Production `WorkflowDefinition` / `WorkflowVersion` models
- Migrations 0110+
- Launch path redirect
- Dual-write / feature flags in production
- `WorkflowTemplate` field removal
- Controlled-pilot workflow changes

### Next unblocked roadmap item

**PAR-APR-001** — Approval Requirement/Decision split (Milestone 3, P1).  
Dependencies: PAR-DOC-001 complete ✅; no ADR blocker for discovery/design on approvals.

Parallel Milestone 1 hygiene remains: `M1-E2E-001`, `PAR-SEC-003`, `PAR-SEC-002`.

### Models and paths inspected

See `CURRENT_MODEL_MATRIX.md` — 10+ models, 50+ files, all launch/publish/clone/restore/simulate/migrate/provenance paths.

### Commits

Branch `cursor/feat-platform-documentation-alignment-d7f1` — docs + characterization tests only.
