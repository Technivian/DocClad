# CLM One documentation

This directory is the repository documentation operating model for **CLM One**.

## Authority hierarchy

1. **Active Governance Charter** — [`governance/GOVERNANCE_CHARTER.md`](governance/GOVERNANCE_CHARTER.md)  
   The approved, authoritative Charter. Agents and contributors must follow it.

2. **Accepted decision records** — ADRs and PDRs under [`governance/decisions/`](governance/decisions/) with status **Accepted** / **Approved**.  
   Binding for their approved scope. Includes [`PDR-0003`](governance/decisions/pdr/PDR-0003-documentation-operating-model.md) (documentation operating model).

3. **Accepted supporting documentation** — product, architecture, engineering, and roadmap documents marked **Accepted** under PDR-0003.  
   Binding guidance for their scope, but **subordinate** to the active Charter and accepted decision records. They do not amend the constitution.

4. **Proposed documentation** — [`governance/GOVERNANCE_CHARTER_V3_PROPOSED.md`](governance/GOVERNANCE_CHARTER_V3_PROPOSED.md).  
   Constitutional amendment under separate review. It does **not** supersede the active Charter until formally approved.

5. **Archive** — [`governance/archive/`](governance/archive/)  
   Historical documents retained for traceability. Do not implement when they conflict with the active Charter.

**Current code does not override approved governance documentation.** If implementation conflicts with the active Charter or an accepted decision record, stop, identify the conflict, and propose a PDR, ADR, Charter amendment, or exception — do not silently work around it.

## Which Charter is active?

| Document | Status | Role |
|---|---|---|
| [`governance/GOVERNANCE_CHARTER.md`](governance/GOVERNANCE_CHARTER.md) | **Active / approved** | Sole authoritative Charter today |
| [`governance/GOVERNANCE_CHARTER_V3_PROPOSED.md`](governance/GOVERNANCE_CHARTER_V3_PROPOSED.md) | **Proposed** | Broader constitutional amendment; requires a separate deliberate approval before it supersedes the active Charter |

## Documentation areas

### Governance — [`governance/`](governance/)

Operating authority, product operating model, decision records, and archive.

| Document | Purpose | Status |
|---|---|---|
| [GOVERNANCE_CHARTER.md](governance/GOVERNANCE_CHARTER.md) | Active constitutional governance | Approved |
| [GOVERNANCE_CHARTER_V3_PROPOSED.md](governance/GOVERNANCE_CHARTER_V3_PROPOSED.md) | Proposed Charter amendment | Proposed |
| [PRODUCT_OPERATING_MODEL.md](governance/PRODUCT_OPERATING_MODEL.md) | Product thesis, users, lifecycle | Accepted |
| [decisions/](governance/decisions/) | ADRs, PDRs, exceptions | Mixed |
| [archive/DESIGN_CONSTITUTION.md](governance/archive/DESIGN_CONSTITUTION.md) | Historical CMS Aegis constitution | Superseded |

### Product — [`product/`](product/)

Domain model, master blueprint, and UX / navigation surfaces.

| Document | Purpose | Status |
|---|---|---|
| [MASTER_BLUEPRINT.md](product/MASTER_BLUEPRINT.md) | Product spine and platform intent | Accepted |
| [CANONICAL_DOMAIN_MODEL.md](product/CANONICAL_DOMAIN_MODEL.md) | Authoritative objects and boundaries | Accepted |
| [UX_NAVIGATION_AND_WORK_SURFACES.md](product/UX_NAVIGATION_AND_WORK_SURFACES.md) | Navigation, work surfaces, terminology | Accepted |

### Architecture — [`architecture/`](architecture/)

Platform modules, workflow engine, data/AI, and security.

| Document | Purpose | Status |
|---|---|---|
| [PLATFORM_AND_MODULE_ARCHITECTURE.md](architecture/PLATFORM_AND_MODULE_ARCHITECTURE.md) | Modules and dependency direction | Accepted |
| [WORKFLOW_ENGINE_AND_DESIGNER.md](architecture/WORKFLOW_ENGINE_AND_DESIGNER.md) | Workflow configuration and execution | Accepted |
| [DATA_AI_AND_INTELLIGENCE.md](architecture/DATA_AI_AND_INTELLIGENCE.md) | Data foundation and AI operating model | Accepted |
| [SECURITY_PRIVACY_ACCESS_AND_AUDIT.md](architecture/SECURITY_PRIVACY_ACCESS_AND_AUDIT.md) | Security, privacy, access, audit | Accepted |

### Engineering — [`engineering/`](engineering/)

| Document | Purpose | Status |
|---|---|---|
| [ENGINEERING_GUARDRAILS.md](engineering/ENGINEERING_GUARDRAILS.md) | Non-negotiable implementation rules | Accepted |

### Roadmap — [`roadmap/`](roadmap/)

| Document | Purpose | Status |
|---|---|---|
| [DELIVERY_ROADMAP_AND_RELEASE_GATES.md](roadmap/DELIVERY_ROADMAP_AND_RELEASE_GATES.md) | Build sequence and release gates | Accepted |

## What agents should read

Before material product, architecture, design, database, security, workflow, AI, integration, or engineering work, read:

1. [`governance/GOVERNANCE_CHARTER.md`](governance/GOVERNANCE_CHARTER.md) *(active)*
2. [`product/MASTER_BLUEPRINT.md`](product/MASTER_BLUEPRINT.md)
3. [`product/CANONICAL_DOMAIN_MODEL.md`](product/CANONICAL_DOMAIN_MODEL.md)
4. [`architecture/PLATFORM_AND_MODULE_ARCHITECTURE.md`](architecture/PLATFORM_AND_MODULE_ARCHITECTURE.md)
5. [`engineering/ENGINEERING_GUARDRAILS.md`](engineering/ENGINEERING_GUARDRAILS.md)

Then read domain-specific documents:

| Work type | Also read |
|---|---|
| Workflow | [`architecture/WORKFLOW_ENGINE_AND_DESIGNER.md`](architecture/WORKFLOW_ENGINE_AND_DESIGNER.md) |
| UI, navigation, terminology, design | [`product/UX_NAVIGATION_AND_WORK_SURFACES.md`](product/UX_NAVIGATION_AND_WORK_SURFACES.md) |
| Data, AI, extraction, search, analytics | [`architecture/DATA_AI_AND_INTELLIGENCE.md`](architecture/DATA_AI_AND_INTELLIGENCE.md) |
| Auth, authorization, privacy, audit, exports, security | [`architecture/SECURITY_PRIVACY_ACCESS_AND_AUDIT.md`](architecture/SECURITY_PRIVACY_ACCESS_AND_AUDIT.md) |
| Roadmap or release readiness | [`roadmap/DELIVERY_ROADMAP_AND_RELEASE_GATES.md`](roadmap/DELIVERY_ROADMAP_AND_RELEASE_GATES.md) |

Root agent instructions: [`../AGENTS.md`](../AGENTS.md).

## How decisions are created

See [`governance/decisions/README.md`](governance/decisions/README.md) for when to use an ADR, PDR, combined record, temporary exception, or Charter amendment, including naming conventions:

- `ADR-0001-short-title.md`
- `PDR-0001-short-title.md`
- `EXC-0001-short-title.md`

Templates:

- [`governance/decisions/adr/ADR_TEMPLATE.md`](governance/decisions/adr/ADR_TEMPLATE.md)
- [`governance/decisions/pdr/PDR_TEMPLATE.md`](governance/decisions/pdr/PDR_TEMPLATE.md)
- [`governance/decisions/exceptions/EXCEPTION_TEMPLATE.md`](governance/decisions/exceptions/EXCEPTION_TEMPLATE.md)

Do not fabricate approved decisions. New records start as **Proposed**.

## How documents are approved and superseded

1. Draft under the correct area with status **Proposed**.
2. Open a PDR/ADR/exception (or Charter amendment proposal) as required.
3. Obtain formal approval through the repository governance process.
4. Update status to **Accepted** / **Approved** and record approval metadata.
5. When a document is superseded, move the prior version to [`governance/archive/`](governance/archive/) with a supersession banner and update links. Do not delete historical governance documents.

Documentation operating model adoption:

- [`governance/decisions/pdr/PDR-0003-documentation-operating-model.md`](governance/decisions/pdr/PDR-0003-documentation-operating-model.md) *(Accepted)*

Charter v3 remains under separate review and is **not** approved by PDR-0003.

## Other documentation in this repository

Operational, pilot, audit, and design-system materials remain under paths such as:

- [`audits/`](audits/)
- [`pilot/`](pilot/)
- [`design-system/`](design-system/)
- [`evidence/`](evidence/)

Those folders are not replaced by this operating model. Prefer the governance / product / architecture tree above for constitutional and platform authority.
