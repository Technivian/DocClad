# ChatGPT Project upload instructions

This folder is an export package for the **CLM One** ChatGPT Project. It is not the canonical documentation tree. Canonical sources remain under `docs/` in the repository (commit `aca20a0c`).

## Upload these as ChatGPT Project sources

Upload every file under `authoritative/`:

1. `authoritative/00_GOVERNANCE_CHARTER_ACTIVE.md`
2. `authoritative/01_DOCUMENTATION_INDEX.md`
3. `authoritative/02_DOCUMENTATION_OPERATING_MODEL_PDR.md`
4. `authoritative/03_PRODUCT_OPERATING_MODEL.md`
5. `authoritative/04_MASTER_BLUEPRINT.md`
6. `authoritative/05_CANONICAL_DOMAIN_MODEL.md`
7. `authoritative/06_PLATFORM_AND_MODULE_ARCHITECTURE.md`
8. `authoritative/07_WORKFLOW_ENGINE_AND_DESIGNER.md`
9. `authoritative/08_UX_NAVIGATION_AND_WORK_SURFACES.md`
10. `authoritative/09_SECURITY_PRIVACY_ACCESS_AND_AUDIT.md`
11. `authoritative/10_DATA_AI_AND_INTELLIGENCE.md`
12. `authoritative/11_ENGINEERING_GUARDRAILS.md`
13. `authoritative/12_DELIVERY_ROADMAP_AND_RELEASE_GATES.md`

## Optional proposed source

Upload only when future Charter discussions are needed:

- `proposed/GOVERNANCE_CHARTER_V3_PROPOSED.md`

Do **not** treat this file as active authority. Prefer omitting it from day-to-day project sources unless you are deliberately reviewing Charter v3.

## Paste this into Project Instructions

Copy the **full contents** of `PROJECT_INSTRUCTIONS.md` into the ChatGPT Project instructions field.

## Remove stale Project sources

Remove old or duplicate uploads so ChatGPT cannot retrieve stale sources. In particular remove names such as:

- `00_GOVERNANCE_CHARTER_V2.md`
- `CLM_ONE_GOVERNANCE_CHARTER_v2_PROPOSED*.md`
- `CLM_ONE_MASTER_BLUEPRINT*.md`
- the old package `README.md`
- numbered package files `01_...` through `09_...` from earlier documentation packages
- duplicate Charter PDFs where the current active Markdown Charter is available
- ZIP files uploaded as project sources
- ADR, PDR, and exception templates
- archived governance documents (for example Design Constitution)

Old and new versions should not coexist. ChatGPT may retrieve the stale source if both remain uploaded.

## Recommended upload order

Use the numeric order in `authoritative/` (00 → 12). Upload the optional proposed Charter only after the authoritative set, if at all.

## Verification after upload

Ask ChatGPT:

1. Which Governance Charter is active?
2. Is Charter v3 approved?
3. What document formally adopted the supporting documentation?
4. What is the canonical contract object chain?
5. Can a workflow with blocking issues be published?
6. What is the difference between My Work and Command Center?

### Expected answers

1. Active Charter: `00_GOVERNANCE_CHARTER_ACTIVE.md` (repository: `docs/governance/GOVERNANCE_CHARTER.md`)
2. Charter v3: **Proposed, not approved**
3. Adoption record: **PDR-0003** (`02_DOCUMENTATION_OPERATING_MODEL_PDR.md`)
4. Object chain: `Workflow Definition → Workflow Version → Workflow Instance → Contract Record`
5. Blocking issues prevent normal publication
6. My Work is personal action; Command Center is organization-wide visibility

## Package contents reference

| Path | Role |
|---|---|
| `PROJECT_INSTRUCTIONS.md` | Paste into Project Instructions |
| `SOURCE_MANIFEST.md` | Authority and purpose of each upload |
| `CHECKSUMS.sha256` | SHA-256 checksums for exported sources |
| `authoritative/` | Required project sources |
| `proposed/` | Optional non-authoritative Charter v3 |

A convenience ZIP may also exist at `artifacts/CLM_One_ChatGPT_Project_Sources.zip`. Prefer uploading the individual Markdown files listed above rather than the ZIP as a project source.
