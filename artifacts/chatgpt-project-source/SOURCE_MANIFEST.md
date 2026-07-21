# CLM One ChatGPT Project — source manifest

Package built from repository commit `aca20a0c`.  
Canonical filenames in the repository are unchanged; numeric prefixes below are for ChatGPT upload ordering only.

## Authoritative sources

| Upload filename | Canonical repository path | Status | Authority level | Purpose | When ChatGPT should consult it |
|---|---|---|---|---|---|
| `authoritative/00_GOVERNANCE_CHARTER_ACTIVE.md` | `docs/governance/GOVERNANCE_CHARTER.md` | Mandatory / active | Highest internal authority | Active Governance Charter | Always, before any material product, architecture, domain, security, workflow, AI, or engineering recommendation |
| `authoritative/01_DOCUMENTATION_INDEX.md` | `docs/README.md` | Index | Navigation / authority map | Documentation operating model index and hierarchy | To locate which document governs a topic and confirm active vs proposed authority |
| `authoritative/02_DOCUMENTATION_OPERATING_MODEL_PDR.md` | `docs/governance/decisions/pdr/PDR-0003-documentation-operating-model.md` | Accepted | Accepted PDR (adopts supporting docs; does not amend Charter) | Formal adoption of the documentation operating model and supporting specifications | When asked what adopted the supporting docs, or whether supporting docs are binding |
| `authoritative/03_PRODUCT_OPERATING_MODEL.md` | `docs/governance/PRODUCT_OPERATING_MODEL.md` | Accepted | Accepted supporting (subordinate to active Charter) | Product thesis, users, lifecycle, operating principles | Product scope, user model, lifecycle, and operating-model questions |
| `authoritative/04_MASTER_BLUEPRINT.md` | `docs/product/MASTER_BLUEPRINT.md` | Accepted | Accepted supporting (subordinate to active Charter) | Product spine and platform intent | Overall product direction and platform spine |
| `authoritative/05_CANONICAL_DOMAIN_MODEL.md` | `docs/product/CANONICAL_DOMAIN_MODEL.md` | Accepted | Accepted supporting (subordinate to active Charter) | Authoritative objects, relationships, invariants | Domain modeling, object definitions, terminology, ownership boundaries |
| `authoritative/06_PLATFORM_AND_MODULE_ARCHITECTURE.md` | `docs/architecture/PLATFORM_AND_MODULE_ARCHITECTURE.md` | Accepted | Accepted supporting (subordinate to active Charter) | Modules, responsibilities, dependency direction | Architecture, module ownership, integration boundaries |
| `authoritative/07_WORKFLOW_ENGINE_AND_DESIGNER.md` | `docs/architecture/WORKFLOW_ENGINE_AND_DESIGNER.md` | Accepted | Accepted supporting (subordinate to active Charter) | Workflow configuration and execution model | Workflow Designer, versions, publication, simulation, instances |
| `authoritative/08_UX_NAVIGATION_AND_WORK_SURFACES.md` | `docs/product/UX_NAVIGATION_AND_WORK_SURFACES.md` | Accepted | Accepted supporting (subordinate to active Charter) | Navigation, work surfaces, UX principles | UI, IA, destinations, empty/loading/error states, terminology in surfaces |
| `authoritative/09_SECURITY_PRIVACY_ACCESS_AND_AUDIT.md` | `docs/architecture/SECURITY_PRIVACY_ACCESS_AND_AUDIT.md` | Accepted | Accepted supporting (subordinate to active Charter) | Security, privacy, access, audit controls | AuthN/Z, privacy, permissions, audit, exports |
| `authoritative/10_DATA_AI_AND_INTELLIGENCE.md` | `docs/architecture/DATA_AI_AND_INTELLIGENCE.md` | Accepted | Accepted supporting (subordinate to active Charter) | Data foundation and AI operating model | Data Manager, extraction, search, analytics, AI authority and provenance |
| `authoritative/11_ENGINEERING_GUARDRAILS.md` | `docs/engineering/ENGINEERING_GUARDRAILS.md` | Accepted | Accepted supporting (subordinate to active Charter) | Non-negotiable implementation rules | Code review, engineering design, anti-duplication, server-side controls |
| `authoritative/12_DELIVERY_ROADMAP_AND_RELEASE_GATES.md` | `docs/roadmap/DELIVERY_ROADMAP_AND_RELEASE_GATES.md` | Accepted | Accepted supporting (subordinate to active Charter) | Build sequence and release gates | Roadmap sequencing, release readiness, stage gates |

## Proposed source

| Upload filename | Canonical repository path | Status | Authority level | Purpose | When ChatGPT should consult it |
|---|---|---|---|---|---|
| `proposed/GOVERNANCE_CHARTER_V3_PROPOSED.md` | `docs/governance/GOVERNANCE_CHARTER_V3_PROPOSED.md` | Proposed amendment | **Non-authoritative** | Future constitutional direction only | Only when discussing possible future Charter changes; must never override the active Charter |

`proposed/GOVERNANCE_CHARTER_V3_PROPOSED.md` is included only for discussion of future constitutional direction and must not be used as active authority.

## Packaging notes

- Relative Markdown links inside exported copies still point at repository paths (for example `../governance/...`). Treat those as repository-relative, not as paths inside this package.
- Decision templates, archives, audits, pilot packs, ZIPs, and source code are intentionally excluded.
- No packaging authority banners were added: supporting documents already carry **Status: Accepted** under PDR-0003.
