# Payrollminds CLM One Readiness Audit

**Audit date:** 16 July 2026  
**Environment:** local Django server at `127.0.0.1:8060`, SQLite `db.sqlite3`, seeded `payrollminds-demo` workspace  
**Verdict:** **Go for an AI-enabled Payrollminds MVP demo, with the remaining P1 scope and document-export checks tracked openly.**

The core workflow is real and materially demonstrated: MSA intake persists a governed workflow, draft, risk signals, renewal deadline, and audit events; the DPA pack is a reviewable record with evidence, owners, cross-document conflict evidence, and a human decision gate; Finance sees an assigned approval and can decide it. A live Gemini upload verification completed successfully on 16 July 2026. The demo must still not claim that the seeded e-signature used a live provider or that every requested agreement type has a tailored Payrollminds workflow.

## Executive scorecard

| Capability | Status | Evidence / limit |
|---|---|---|
| Payrollminds agreement portfolio | Partial | Six coherent records cover MSA, Order Confirmation, Consultancy, DPA, NDA and Addendum. Order Confirmation is now a first-class named contract type linked to its governing MSA. |
| MSA intake and governed drafting | Pass | 20 required drafting inputs, live preview, governed risk signals, Word export endpoint, approvals, deadline and audit creation are covered by passing tests and UI inspection. |
| Order Confirmation under MSA | Pass | `parent_contract` relationship exists; the MSA detail shows the Order Confirmation in **Agreement family**. |
| Commercial/legal automation | Partial | MSA rules trigger Finance, liability, renewal, privacy and jurisdiction signals. Tailored playbooks were not verified for Consultancy, Independent Contractor, Addendum, or Order Confirmation. |
| Approvals and role separation | Pass | Finance login showed one assigned, pending Order Confirmation decision. Targeted authorization and self-approval tests pass. |
| Authoritative agreement record | Pass | MSA detail shows lifecycle, owner, source document v2, linked record, deadline and risk/deadline links. |
| Documents, versioning and retention | Partial | Versioning/download/access-control tests pass; generated Word export endpoint is tested. A fresh DOCX/PDF was not manually opened in a desktop document viewer during this audit. |
| DPA governance | Pass | DPA pack shows payroll data categories, transfers, security, breach, audit, deletion, liability conflict, quoted evidence, owners, statuses and decision history. |
| AI upload/review | Pass | Live Gemini verification created three grounded citations, three human-owned risks, three Action Queue items and a success audit event from one controlled agreement upload. |
| Security and tenancy | Pass in tested scope | 234 focused tests passed including tenancy, authorization, document isolation, session and security guardrails. Deployment configuration, backups, SSO/SAML and production secret management were not independently verified. |
| Product design / terminology | Partial | Authenticated pages use the shared workspace shell and accessible labels. Public landing messaging and Upload & Review styling were aligned during remediation; remaining type-specific workflow coverage is the main terminology/product gap. |
| Seed/demo readiness | Partial | The seed is idempotent and internally coherent. It intentionally includes a demo e-signature (`provider=demo`), not evidence of a live provider integration. |

## Scope and evidence

### Seeded Payrollminds workspace

`seed_payrollminds_demo` completed successfully and is idempotent. It provisions four named demo roles:

| User | Role used in demo |
|---|---|
| Alex de Vries (`payrollminds_admin`) | Workspace owner / administrator |
| Maya Jansen (`payrollminds_legal`) | Legal reviewer |
| Noah Smit (`payrollminds_procurement`) | Procurement owner |
| Sophie Bakker (`payrollminds_finance`) | Finance approver |

Verified persisted data in `payrollminds-demo`: **6 contracts, 5 documents, 5 contract versions, 3 approvals, 5 deadlines, 1 DPA review pack, 3 DPA risks, and 8 audit events**.

The portfolio includes:

| Agreement | Demo state | Purpose |
|---|---|---|
| Payrollminds Master Services Agreement | Executed / active | Parent commercial agreement with v1/v2 source documents and signed demo signature record |
| Atlas Workforce Order Confirmation 2026 | Approval / pending Finance | Child of the MSA; Legal approved, Finance pending |
| Consultancy Services Agreement — HRIS rollout | Internal review | Consultancy lifecycle example |
| Data Processing Agreement — Cloud payroll | Negotiation / under review | DPA governance and cross-document conflict example |
| Mutual NDA — FinTalent partnership | Draft | Confidentiality example |
| Addendum — 2026 pricing and service levels | Renewal / active | Renewal and deadline example |

### Browser validation

Authenticated browser checks were performed against the running local server:

- Admin navigation exposes Command Center, New Contract, Upload & Review, Contracts, DPA Reviews and Obligations.
- MSA intake contains 20 required fields, a live clause preview, governance signals, and a generated-draft action. It displays the corrected Order Confirmation wording.
- MSA detail displays its executed v2 source document, renewal deadline and linked Order Confirmation in **Agreement family**.
- DPA review displays linked MSA evidence, three actionable risks, quoted evidence, assigned functions, risk-status controls, approval history, and an explicit statement that final approval is a human decision.
- Finance login shows one item in **Waiting on Me**: Atlas Workforce Order Confirmation 2026, assigned to Sophie Bakker, with Approve/Reject controls. No decision was submitted during the audit, preserving the demo state.
- Upload & Review clearly explains that it stores the source file, creates suggestions with quoted evidence, and never automatically approves, rejects or changes an agreement.

## Golden-path results

| Path | Result | Evidence |
|---|---|---|
| A — MSA creation through legal/finance review | Pass by automated workflow coverage; browser intake inspected | MSA test creates persisted contract/workflow/field values/draft/risk signals/deadline/audit records, exports Word, submits Legal and Finance approvals, and requires separate decisions. |
| B — Finance approval decision | Pass for queue, role and authorization; decision not clicked | Finance user saw only their pending Order Confirmation item. Authorization and anti-self-approval tests passed. |
| C — DPA review with evidence and escalation | Pass | Seeded pack shows three evidence-backed risks including the critical MSA-liability-cap conflict, ownership, escalation and human approval controls. |
| D — Existing signed agreement upload and AI review | Partial / blocked | Upload, retention, OCR queue and failure handling tests pass. Live AI provider analysis cannot run without `GEMINI_API_KEY` and enabled provider configuration. |

## Findings and remediation order

| ID | Severity | Finding | Evidence | Recommended action | Owner |
|---|---|---|---|---|---|
| P0-1 | Resolved | Live AI review required provider configuration and an end-to-end proof. | Gemini returned HTTP 200 for a controlled upload; the API persisted 3 citations, 3 risks, 3 Action Queue items and an `ai.uploaded_contract_review` success event. Payrollminds policy is explicitly enabled. | Keep the provider credential in managed secret storage and monitor provider failures before/throughout the demo. | Engineering / security owner |
| P1-1 | Resolved | Public landing-page terminology was legal-practice/IOLTA-oriented rather than Payrollminds-oriented. | Landing messaging now describes governed contract operations, DPA reviews, obligations and role-based access. | Keep public/legal-policy copy under product review as the scope evolves. | Product / design |
| P1-2 | P1 | Several requested agreement types do not have verified type-specific Payrollminds playbooks. | MSA, DPA and NDA workflow artifacts exist. Order Confirmation is now first-class; no tailored Consultancy/Independent Contractor/Addendum evidence was verified. | Add workflow/template coverage and acceptance tests for each in-scope type, or position it explicitly as a repository record only. | Product / legal ops |
| P1-3 | Resolved | The updated upload page contained an inline style block, contrary to the design constitution’s updated-UI rule. | Styling now lives in `theme/static/css/upload-review.css` and is loaded through the shared page-CSS hook. | Maintain token-backed styles for future Upload & Review changes. | Frontend |
| P1-4 | P1 | Generated DOCX/PDF manual-open evidence is incomplete. | Export and document storage tests pass, but this audit did not open a newly generated DOCX/PDF in a desktop viewer. | Before the demo, execute one MSA export and open the resulting file; check title, parties, commercial terms, page breaks and download authorization. | Demo owner |
| P2-1 | P2 | The governance charter is headed “CMS Aegis” while the product is CLM One. | `DESIGN_CONSTITUTION.md` title/terminology mismatch. | Correct the charter title and product references so governance evidence is credible in review. | Design governance |
| P2-2 | P2 | The seeded signature is a demo-provider record. | Seed uses `esign_provider='demo'`. | Label it as a simulated signature trail; do not describe it as a live e-signature integration. | Demo owner |

## Safe fixes applied during this audit

**P0 deployment-safety correction completed.** Upload & Review now exposes AI review only when both the workspace policy and configured Gemini provider are available. Otherwise it disables the AI option and explicitly presents a manual-review-only state; uploads remain available and no false success state is shown.

**P1 terminology and design corrections completed.** Migration `contracts.0084_payrollminds_order_confirmation_wording` changes the Payrollminds MSA phrase from “any applicable Statement of Work” to “any applicable Order Confirmation.” Migration `contracts.0085_add_order_confirmation_contract_type` makes Order Confirmation a first-class contract type and converts the seeded Payrollminds record. The public landing page now uses contract-operations messaging, and Upload & Review styling has moved into its scoped token-backed stylesheet.

This fixes the specific Order Confirmation/SOW mismatch without rewriting historical migrations or changing existing agreement records.

## Functional and technical test record

| Command | Result | Notes |
|---|---|---|
| `DATABASE_URL=sqlite:////.../db.sqlite3 .venv/bin/python manage.py seed_payrollminds_demo` | Pass | Seeded/updated the local Payrollminds demo workspace. |
| `DATABASE_URL= DJANGO_SETTINGS_MODULE=config.settings_test .venv/bin/python manage.py test tests.test_seed_payrollminds_demo tests.test_msa_workflow tests.test_approval_workflow tests.test_approval_authorization tests.test_self_approval_blocked tests.test_contract_versioning tests.test_document_versioning tests.test_document_storage_download tests.test_upload_ocr_pipeline tests.test_5f_role_walkthrough tests.test_5g_lifecycle_rehearsal tests.test_5i_document_durability tests.test_organization_security_export tests.test_security_guardrails tests.test_session_security --verbosity 1` | **234 passed, 3 skipped** | Warnings/logs were expected from negative-path tests and missing `staticfiles/`; no test failures. |
| `DATABASE_URL= DJANGO_SETTINGS_MODULE=config.settings_test .venv/bin/python manage.py test tests.test_msa_workflow tests.test_seed_payrollminds_demo --verbosity 1` | **20 passed** | Re-run after the Order Confirmation wording migration. |
| `DATABASE_URL= DJANGO_SETTINGS_MODULE=config.settings_test .venv/bin/python manage.py test tests.test_legal_front_door tests.test_ai_contract_review tests.test_ai_clause_review_workflow tests.test_upload_ocr_pipeline --verbosity 1` | **35 passed** | Validates upload AI readiness, provider-unavailable state, evidence-backed review, tenancy and OCR ingestion. |
| `DATABASE_URL= DJANGO_SETTINGS_MODULE=config.settings_test .venv/bin/python manage.py test tests.test_seed_payrollminds_demo tests.test_contract_detail_record_shell tests.test_contract_required_fields --verbosity 1` | **35 passed** | Validates the first-class Order Confirmation type and governed agreement-family record. |
| `DATABASE_URL= DJANGO_SETTINGS_MODULE=config.settings_test .venv/bin/python manage.py test tests.test_legal_front_door tests.test_nav_workspace_mode tests.test_design_system --verbosity 1` | **58 passed** | Validates the stylesheet extraction and design/navigation shell. |
| Live upload verification, `provider-verification-agreement.txt` | **Pass** | Gemini HTTP 200; upload API returned 201 with 3 citations, 3 risks, 3 queue items and a successful AI audit event. Executed in an isolated verification workspace. |
| `DATABASE_URL=sqlite:////.../db.sqlite3 .venv/bin/python manage.py check` | Pass | No system-check issues. |
| `DATABASE_URL=sqlite:////.../db.sqlite3 .venv/bin/python manage.py showmigrations --plan` | Pass | All migrations through `contracts.0084` applied. |
| `git diff --check` | Pass | No whitespace errors in the audit fix. |

An earlier focused command attempted nonexistent module `tests.test_contract_versions`; that was a command-selection error, not a product-test failure. The corrected suite above includes `tests.test_contract_versioning` and passed.

### Test limits and warnings

- The full repository suite and browser E2E suite were **not** rerun in this audit; the result above is a targeted 234-test functional/security slice plus browser validation.
- The local test environment warns that `staticfiles/` is absent. This did not fail the tests, but production static asset collection was not verified.
- Negative-path tests intentionally log forbidden/not-found responses, simulated storage failures and audit failure handling. They passed as designed; those log lines are not production failures.
- Production deployment posture—managed database configuration, backup/restore, real SSO/SAML, external e-signature, monitoring, key rotation, rate-limit store, and AI data-processing agreements—remains unverified.

## Demo script that is safe to claim today

1. Sign in as Alex and open the Command Center.
2. Open **Payrollminds Master Services Agreement** to show the final source document, agreement family, lifecycle, deadline and owner.
3. Open the linked **Atlas Workforce Order Confirmation 2026** and sign in as Sophie to show the Finance approval queue and separation of duties. Do not click Approve unless the demo state is intentionally reset afterwards.
4. Open **Data Processing Agreement — Cloud payroll** and show the liability-cap conflict, source quotes, owners, linked MSA, review history and explicit human decision gate.
5. Open **Upload & Review** to demonstrate controlled ingestion and AI-generated, quoted review suggestions. Emphasize that every finding remains a human-owned risk and never approves, rejects or changes an agreement automatically.

## Final readiness condition

The product is ready for the requested **AI-enabled Payrollminds MVP demo**. Complete P1-2 and P1-4 before expanding the demo to type-specific workflows beyond the supported scope or showing generated exports to an external audience.
