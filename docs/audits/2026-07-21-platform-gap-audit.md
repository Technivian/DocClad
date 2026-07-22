# Platform Gap Audit — Documentation Operating Model Alignment

**Date:** 2026-07-21  
**Repository:** technivian/clmone  
**Branch at audit start:** `cursor/feat-platform-documentation-alignment-d7f1` (from clean `cursor/cloud-agent-…` / main lineage)  
**Governing authority:** `docs/governance/GOVERNANCE_CHARTER.md` (active) · **PDR-0003** Accepted · supporting docs under PDR-0003  
**Non-authority:** `GOVERNANCE_CHARTER_V3_PROPOSED.md` (not active)  
**Prior audit (superseded for governance framing):** `docs/audits/CLM_ONE_APPLICATION_AUDIT_2026-07-20.md` (pre–PDR-0003 framing; still useful for UI inventory)

---

## 1. Executive summary

### Current maturity (honest)

| Lens | Grade | Notes |
|---|---|---|
| Controlled pilot product | **Pilot-ready with limitations** | NDA/MSA/DPA paths, tenancy middleware, designer, My Work, obligations workspace exist |
| Canonical domain fidelity | **Skeletal → Partial** | Objects collapsed/aliased; Definition/Version not first-class |
| Workflow engine vs WORKFLOW_ENGINE doc | **Partial** | Publish validation + mutate gate exist; published row still mutable via unpublish/admin/UpdateView gaps; instance migration rebinds FK |
| Security / tenant isolation | **Operational with defects** | Strong isolation suite culture; some list-endpoint auth/redirect failures observed in baseline |
| Enterprise readiness | **Not ready** | Missing Data Manager, Entities surface, Property Definition, generic Integration Connection, full AI provenance |

### Strongest areas

1. Append-only `AuditLog` with hash-chain patterns and workflow publish toggle audit.
2. `can_mutate_workflow_template` + canvas FBV guards for published templates.
3. Simulation service is dry-run (does not create live Workflow/Contract data).
4. PDR-0002 lifecycle service and dual status/stage vocabulary are partially enforced in code.
5. Modular Django app with substantial automated tests (~190 test modules under `tests/`).

### Highest-risk gaps

| ID | Risk | Severity |
|---|---|---|
| G-WF-01 | Published templates editable via `WorkflowTemplateUpdateView` / Admin without mutate gate | **Critical** |
| G-WF-02 | `migrate_workflows_to_template` rebinds live instance FKs (breaks version pin invariant) | **Critical** |
| G-WF-03 | `WorkflowTemplate.is_active` defaults `True` (publish-by-default) | **High** |
| G-DOM-01 | No Workflow Definition entity; Version = template row only | **High** |
| G-DOM-02 | Dual `Contract.ContractType` enum vs `ContractType` model | **High** → **Resolved (PAR-CORE-002)** — catalogue canonical; char mirror transitional; ADR-0011 Proposed for removal gate |
| G-DOM-03 | Obligations = `Deadline` alias; no Reminder/Exception first-class objects | **High** |
| G-NAV-01 | Data Manager and Entities missing from canonical nav | **High** |
| G-AI-01 | `ClauseRecommendation` lacks model/provider/prompt provenance | **Medium** |
| G-SEC-01 | Cross-tenant / unauthenticated list redirect failures in baseline suite | **High** (pre-existing) |

### Architectural conflicts

- Canonical chain **Definition → Version → Instance → Record** implemented as **Template(+version fields) → Workflow → Contract**.
- Pages sometimes act as module boundaries (law-firm clients/matters still in URLconf).
- Work Item is a projection in My Work but a persisted `CommandCenterWorkItem` in Command Center (dual semantics).

### Governance conflicts

- Domain Model §5 status vocabulary vs **PDR-0002** binding enums — treat **PDR-0002** as implementation authority until a reconciling PDR.
- Stage 0 roadmap text still mentions Charter v3 approval; **PDR-0003** forbids treating v3 as active.

### Security concerns

- Client-side UI hiding is not authorization (guardrails already state this; must keep server checks).
- Admin can mutate published workflow templates.
- Nullable `organization` on many core FKs — app-layer scoping, not schema-hard isolation.

### Realistic path forward

1. Harden published immutability, defaults, admin, and instance migration governance (**Foundation**).
2. Add invariant tests for pin/simulation/publish blockers.
3. Align nav stubs for Data Manager / Entities without inventing full Property/Entity graphs prematurely (**Pilot hardening** + Proposed ADR/PDR where needed).
4. Plan Definition/Version split and Obligation model as Core product with explicit migrations.
5. Defer enterprise IdP depth, generic integrations, and full AI orchestration provenance to **Enterprise / Future**.

---

## 2. Traceability matrix (material rules)

Status key: Compliant · Partially compliant · Missing · Conflicting · Not implemented · N/A · Deferred · Blocked

| Rule | Source | Section | Implementation | Evidence | Status | Severity | Action | Decision needed | Roadmap |
|---|---|---|---|---|---|---|---|---|---|
| Published configuration immutable | MASTER_BLUEPRINT / WORKFLOW_ENGINE | Invariants | `can_mutate_*` on FBVs; UpdateView/Admin gaps | `workflow_designer.py:179`; `workflow_management.py:278` | Conflicting | Critical | Gate UpdateView + Admin | — | PAR-WF-001 |
| Blocking validation prevents publish | WORKFLOW_ENGINE | Publish path | `validate_template_for_publish` | `workflow_designer.py` | Partially compliant | High | Keep; expand invariant tests | — | PAR-WF-005 |
| Live instance pinned to immutable version | CANONICAL_DOMAIN / WORKFLOW | Chain | FK to template row; migrate rebinds | `models.Workflow.template`; `migrate_workflows_to_template` | Conflicting | Critical | Govern migration + audit; pin policy ADR | Proposed ADR | PAR-WF-002 |
| Restore → new draft only | WORKFLOW_ENGINE | Restore | Clone path exists | `clone_template_version` | Partially compliant | Medium | Verify audit + tests | — | PAR-WF-005 |
| Simulation never creates live data | WORKFLOW_ENGINE | Simulation | Dry-run service | `workflow_simulation.py` | Compliant | — | Maintain tests | — | PAR-WF-005 |
| Contract Record provenance | DOMAIN | Invariants | Contract has creator/org; workflow optional | `models.Contract` | Partially compliant | High | Strengthen provenance fields/events | — | PAR-CORE-003 |
| Approval bound to approved state/doc | DOMAIN / PDR-0002 | Approvals | `ApprovalRequirement` + `ApprovalDecision` | `approval_canonical.py` | Compliant (DPAReviewPack residual) | — | Maintain | ADR-0013 | PAR-APR-001 **Resolved** |
| Material actions → Audit Event | SECURITY / DOMAIN | Audit | AuditLog + workflow_audit | services | Partially compliant | High | Close Admin/publish/migration gaps | — | PAR-AUD-001 |
| AI non-authoritative until verified | DATA_AI | Suggestions | ClauseRecommendation accept flags | models | Partially compliant | Medium | Add provenance fields | — | PAR-AI-001 |
| Same access rules for search/analytics/AI | SECURITY | Authz | Mixed | tenancy helpers | Partially compliant | High | Permission tests | — | PAR-SEC-002 |
| Property Definitions centrally governed | DATA_AI | Data Manager | FieldDefinition per template only | models | Missing | High | Data Manager surface + model plan | PDR/ADR | PAR-DATA-001 |
| My Work = Work Item projection | UX / DOMAIN | My Work | assignments aggregation | `my_work.py` | Partially compliant | Medium | Document; avoid Command Center merge | — | PAR-WORK-001 |
| Pages are views not modules | PLATFORM | Architecture | Mostly OK; some legacy modules | urls/nav | Partially compliant | Low | Avoid new page-owned logic | — | continuous |
| Canonical nav includes Data Manager & Entities | UX_NAVIGATION | IA | Absent from `_STANDARD_NAV` | `nav_config.py` | Missing | High | Add surfaces | — | PAR-NAV-001 |
| Tenant isolation | SECURITY / GUARDRAILS | Authz | Middleware + tests; baseline failures | test_cross_tenant_isolation | Partially compliant | High | Fix redirect/auth failures | — | PAR-SEC-001 |
| Client hide ≠ authorization | GUARDRAILS §6 | Security | Server checks present on many paths | views | Partially compliant | Medium | Audit remaining CBVs | — | PAR-SEC-002 |
| PDR-0002 status/stage vocabulary | PDR-0002 | Binding | Lifecycle service | services | Partially compliant | High | Align remaining UI/tests | — | PAR-CORE-001 |
| Finance threshold single entry | PDR-0001 | Finance | `get_finance_approval_threshold` | services | Compliant | — | Keep | — | — |
| Charter v3 not active | PDR-0003 | Authority | Proposed file present | governance | Compliant | — | Do not implement v3 | — | — |
| Workflow Definition first-class | DOMAIN | Objects | `WorkflowTemplate` collapse (interim) | ADR-0012 proposed; evidence `2026-07-22-par-wf-010` | **Blocked** — discovery complete | High | Accept ADR-0012 + cutover | ADR-0012 | PAR-WF-010 |
| Obligation first-class | DOMAIN | Objects | Deadline alias | obligations.py | Conflicting | High | Model + migration plan | ADR/PDR | PAR-OBL-001 |
| Reminder first-class | DOMAIN | Objects | Fields/jobs only | Deadline.reminder_days | Missing | Medium | Model later | — | PAR-OBL-002 |
| Exception first-class | DOMAIN | Objects | RiskSignal / actions | — | Missing | Medium | Governed Exception | PDR | PAR-EXC-001 |
| Document Version immutable entity | DOMAIN | Documents | `DocumentVersion` + service | `document_version_service` | Compliant (residual: DraftDocument, approval FK) | — | Maintain | — | PAR-DOC-001 **Resolved** |
| Role Definition process roles | DOMAIN | Identity | Dual role systems | Membership vs Profile | Conflicting | High | Terminology ADR | ADR | PAR-ID-001 |

---

## 3. Capability matrix

| Capability | Maturity |
|---|---|
| Contract operating core | pilot-ready |
| Workflow configuration | pilot-ready |
| Workflow runtime | skeletal → pilot-ready |
| Document management | pilot-ready |
| Templates and clauses | pilot-ready |
| Playbooks | skeletal |
| Review and collaboration | pilot-ready |
| Approvals | pilot-ready |
| Privacy review | pilot-ready |
| Signatures | skeletal → pilot-ready |
| Contract records | pilot-ready |
| Entities and relationships | skeletal |
| Obligations and renewals | skeletal → pilot-ready |
| Data Manager | absent |
| Search and repository intelligence | skeletal |
| My Work | pilot-ready |
| Command Center and Insights | pilot-ready |
| Audit and evidence | pilot-ready |
| Integrations | skeletal |
| AI orchestration | skeletal |
| Identity and access | pilot-ready (org RBAC) / skeletal (enterprise IdP depth) |

---

## 4. Domain conflict register

| Conflict | Type | Evidence |
|---|---|---|
| Workflow Definition missing; Version = `WorkflowTemplate` row | Missing / collapse | `models.WorkflowTemplate` |
| Dual ContractType enum vs model | Duplicate → transitional | `ContractType` catalogue + `contract_type_catalogue` FK (PAR-CORE-002); char mirror until ADR-0011 Accepted |
| Org Membership roles vs UserProfile process roles | Duplicate / ambiguous | models |
| Obligation as Deadline | Alias / terminology drift | `services/obligations.py` |
| Work Item ephemeral vs CommandCenterWorkItem persisted | Dual semantics | my_work vs command_center |
| ContractTemplate global vs org WorkflowTemplate | Naming / scoping | models |
| Domain Model §5 vs PDR-0002 statuses | Doc conflict | Prefer PDR-0002 |
| Published `is_active` flipped false to allow edit | Mutable history | publish_toggle |
| Instance migration `update(template=…)` | Pin violation | workflow_templates.py |

---

## 5. Risk register

| Risk | Likelihood | Impact | Objects | Mitigation | Owner | Roadmap | Release |
|---|---|---|---|---|---|---|---|
| Silent edit of published workflow | High | Critical | WorkflowTemplate | Mutate gates everywhere | Eng | PAR-WF-001 | Blocks pilot harden |
| Live workflows jump versions | Medium | Critical | Workflow | Governed migration + audit | Eng | PAR-WF-002 | Blocks core claim |
| Accidental publish-by-default | Medium | High | WorkflowTemplate | Default False | Eng | PAR-WF-003 | Pilot |
| Nav IA incomplete → wrong mental model | High | Medium | Nav | Add Data Manager / Entities | Product/Eng | PAR-NAV-001 | Pilot |
| Auth redirect / isolation test red | Medium | High | Lists | Fix aliases + login | Eng | PAR-SEC-001 | Pilot |
| AI suggestion without provenance | Medium | Medium | ClauseRecommendation | Schema + UI | Eng | PAR-AI-001 | Core |
| Obligation data loss on Deadline refactor | Medium | High | Deadline | ADR + migrate carefully | Eng | PAR-OBL-001 | Core |

---

## 6. Current versus target architecture

### Current (observed)

- Django modular monolith (`contracts` app heavy).
- Org tenancy via FK + `scope_queryset_for_organization` / mixins.
- Workflow authoring: `WorkflowTemplate` + steps; publish flag `is_active`.
- Runtime: `Workflow` / `WorkflowStep` materialized from template.
- Records: `Contract` with status + lifecycle_stage.
- Projections: My Work assignments; Command Center work items.
- Integrations: Salesforce-specific models; SCIM groups.
- AI: multiple models (`ClauseRecommendation`, extraction spans, findings) without unified orchestration boundary enforcement everywhere.

### Target (accepted docs — not yet fully present)

- Same modular monolith preference.
- First-class Workflow Definition + immutable Workflow Version.
- Workflow Instance pinned to Version; governed migration only.
- Contract Record with mandatory provenance.
- Central Property Definition (Data Manager); Entity + relationships.
- Work Item as authorized projection (one semantic).
- Append-only Audit Event covering all material actions.
- AI Suggestion with full provenance; non-authoritative until verified.
- Canonical nav including Data Manager and Entities.

---

## 7. Baseline evidence

See `docs/audits/evidence/2026-07-21-platform-alignment-baseline/SUMMARY.md`.

- Django check: **PASS**
- Workflow suite (62): **PASS**
- Broader isolation/lifecycle targeted suite: **FAIL** (pre-existing classification)

---

## 8. Gap severity totals (traceability material rules)

| Severity | Count (approx.) |
|---|---|
| Critical | 2 |
| High | 12 |
| Medium | 6 |
| Low | 1 |

Exact roadmap IDs follow in `docs/roadmap/PLATFORM_ALIGNMENT_ROADMAP.md`.
