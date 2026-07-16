# CLM One — Pre-Demo Readiness Report

**Audience:** Payrollminds demo team  
**Audit date:** 15 July 2026  
**Verdict:** **NO-GO for the planned end-to-end demo**

## Executive decision

CLM One has a credible governed-contract foundation: authenticated workspace access, contract selection, detailed MSA intake, conditional risk signals, generated-draft persistence, a DPA cockpit, and manual obligations. Targeted desktop and responsive-layout checks also passed.

The core demo promise breaks after MSA generation. Visible MSA actions for Legal review, Finance review, summary generation, and Word export are non-functional. The generated MSA has no approval requests, no downloadable document, and only one persisted audit record despite a richer on-screen audit preview. The full automated suite is materially red: 20 failures and 6 errors; browser E2E is 8 of 15 red.

Do not present this as a complete contract-to-approval-to-execution workflow. A tightly guided draft-generation preview is possible only if the audience is explicitly told that review, approval, and export are not being demonstrated.

## Scope and method

The audit covered functionality, governance, UX, permissions, auditability, security posture, operational readiness, and test evidence. I read the governing charter, DESIGN_CONSTITUTION.md v1.5, and inspected routes, permissions, models, services, templates, tests, scripts, and dependency configuration.

Destructive browser steps used only the isolated E2E server at http://127.0.0.1:8010 with e2e_owner. The sample was MSA — Payrollminds Demo Client B.V., a high-value Netherlands agreement with privacy, non-standard liability, auto-renewal, IP, and non-preferred-law flags.

The normal local server is not a safe disposable demo environment: its database URL resolves to remote Supabase. During tests, an external Upstash Redis quota was exhausted and a health check returned 503.

## Golden-path evidence

| Step | Result | Evidence |
|---|---|---|
| Sign in and Command Center | Confirmed | Owner login redirects to /dashboard/. |
| Select contract type | Confirmed | New Contract shows MSA, DPA, NDA, SOW, Supplier Agreement, Addendum, and SaaS. |
| Create non-standard MSA | Confirmed | Required fields are enforced and server-side validation messages appear. |
| Commercial/legal intake | Confirmed | Counterparty, term, value, payment, law, liability, IP, privacy, and renewal inputs persist. |
| Risk/routing display | Confirmed | Finance, Legal, DPA/privacy, renewal, and escalation signals appear with Contract Owner → Finance → Legal → Signature. |
| Persist generated draft | Confirmed | Reload retained the draft. Database: 1 draft document, 27 field values, 6 risk signals. |
| Template provenance | Confirmed | Workspace cites Enterprise Services MSA · Netherlands · B2B, approved template, and clause library. |
| Send to Legal or Finance | **Failed** | Buttons are inert; no navigation, state change, or approval record. |
| Approve/reject/request changes | **Failed** | Generated workflow has zero ApprovalRequest records. |
| Generate/download document | **Failed** | Summary and Export Word buttons are inert; draft is not downloadable. |
| Trustworthy audit history | **Failed** | One persisted audit record only; workspace preview is synthetic context. |
| Track obligations | Partially confirmed | Manual deadline creation/list works; auto-renewal created no deadline. |

Generated-workflow database evidence:

    workflow: 23
    contract status: DRAFT
    draft documents: 1
    field values: 27
    risk signals: 6
    approval requests: 0
    audit events: 1
    deadlines: 0

## Release blockers

| ID | Severity | Finding | Evidence and impact | Required action |
|---|---|---|---|---|
| P0-01 | P0 | MSA review, summary, and export controls do nothing. | The MSA workspace renders plain buttons for Legal review, Finance review, summary, and export; its only script handles clause links. Browser clicks changed neither URL nor state. | Implement authenticated server actions, wire controls, create approvals, persist a downloadable document, and add E2E lifecycle coverage. |
| P0-02 | P0 — fixed | Invalid generic-contract preview raised a 500. | Custom ContractCreateView POST bypassed normal initialization and invalid rendering accessed missing self.object. | Fixed during audit; focused regression passes. Full suite must be re-run. |
| P1-01 | P1 | No demo-ready approval authority or separation of duties. | Dashboard showed Pending approvals — Setup required and Approval authority Missing. Seed had owner only; MSA created no approvals. | Provision Owner, Legal, Finance, and read-only accounts; configure rules and test allowed/denied actions. |
| P1-02 | P1 | Test baseline is not release-ready. | Django: 1,857 tests, 20 failures, 6 errors, 32 skipped. Playwright: 7 passed, 8 failed. | Triage and resolve all critical-flow failures before demo. |
| P1-03 | P1 | Operational dependencies are unsafe for a reliable demo. | Default configuration uses remote Supabase; test run hit Upstash quota and health returned 503. | Use isolated database and Redis with pinned demo settings and green health. |
| P1-04 | P1 | MSA audit display can overstate history. | Audit preview is constructed from workflow context; sample had only creation audit event. | Render persisted AuditLog events, label projections, record all lifecycle actions. |
| P1-05 | P1 | Approval edit path has unhandled transition. | Full suite recorded InvalidContractTransition from ACTIVE to APPROVED at /contracts/approvals/1/edit/. | Define idempotent edit/completed-approval semantics and add regression test. |
| P1-06 | P1 | Terminology does not fit Payrollminds. | Picker uses generic SOW and Supplier Agreement labels/copy. | Use Order Confirmation and approved Payrollminds consulting/contractor/professional-services terms. |

## Important non-blocking issues

| ID | Severity | Finding | Recommendation |
|---|---|---|---|
| P2-01 | P2 | Auto-renewal does not create a renewal obligation. | Extract a deadline, assign it, notify owner, and test reminders. |
| P2-02 | P2 | Generic approvals and generated MSA workflows are disconnected. | MSA creation should invoke configured approval routing. |
| P2-03 | P2 | Browser E2E expectations are stale/inconsistent. | Failures include old Privacy reviews text, old redirects, picker heading, and selectors. Validate UX before updating tests. |
| P2-04 | P2 | Workspace roles are only Owner/Admin/Member. | Legal/Finance profile roles route work but are not clear least-privilege workspace roles. |
| P2-05 | P2 | Frontend supply-chain findings remain. | Theme static source has one moderate tar advisory; client has one low esbuild dev-server advisory. |
| P2-06 | P2 | mypy executable points to removed CMS-Aegis environment. | Repair virtual-environment entry point; module invocation works. |
| P2-07 | P2 | Charter is branded CMS Aegis rather than CLM One. | Align governance artifact names before using them as evidence. |

## Functional readiness

### Demonstrated

- Authentication and organization-scoped Command Center.
- MSA selection, detailed intake, validation, conditional risk signals, and persisted draft.
- Approved template/clause-library provenance display.
- DPA cockpit coverage in browser E2E.
- Manual deadline/obligation creation and listing.
- Targeted desktop and narrow-mobile no-overflow checks.

### Not adequately demonstrated

- DPA creation/review/routing/sign-off and NDA lifecycle end to end.
- Repository/search, template administration, workflow/rule management.
- Contract negotiation, execution, termination, notifications, and reporting.

### Not ready in the MSA route

- Legal/Finance handoff, review queues, and actionable decisions.
- Document file, download, or Word export.
- Complete persistent audit history.
- Automatic renewal/notice obligation extraction.
- Verified execution/signature lifecycle.

## Governance, RBAC, audit, and security

The mandatory charter requires semantic primitives, accessible feedback/focus, consistent navigation, token-based visual language, and UI-change evidence. The tested MSA has labels, validation feedback, conditional feedback, and coherent desktop layout. The codebase also has organization scoping, permission helpers, immutable audit-log protections, and generic approval services.

That is insufficient for the planned governance claim:

- Generated MSA creation records one immutable creation event, not the lifecycle implied by the UI.
- Generic approval permissions are not connected to generated MSA workflows.
- One owner login does not prove Legal/Finance separation of duties.
- Several templates contain inline style blocks/raw values, requiring charter-compliance remediation.
- No customer-facing DocClad, Docclad, or ModuClad string was found in scanned Django/template source.

Repository patterns support server-side permissions and tenant scoping, but browser testing did not prove cross-tenant or role-denial behavior for MSA. Those remain required pre-demo evidence.

## Payrollminds terminology and fit

| Current term | Recommended direction |
|---|---|
| SOW | Order Confirmation, with services, rates, acceptance, and change control. |
| Supplier Agreement | Consulting Agreement, Independent Contractor Agreement, or Professional Services Agreement. |
| Generic MSA | Payrollminds Master Services Agreement with approved Netherlands/B.V. entity, payroll, privacy, liability, IP, and renewal language. |
| Generic counterparty fields | Add legal entity, company number, address, signatory capacity, supplier/contractor classification, and policy controls. |

The tested MSA covers value, payment, services, jurisdiction, liability, confidentiality, IP, privacy, and renewal. It does not prove the requested Payrollminds taxonomy or complete commercial/pricing/expenses/worker-classification model.

## Test and quality evidence

| Check | Result |
|---|---|
| Django full suite | 1,857 tests; **20 failures, 6 errors, 32 skipped**; 1,799 passed; 761.525 seconds. |
| Focused regression after fix | ContractDraftingTests: **6 passed**. |
| Browser E2E | **7 passed, 8 failed** of 15. DPA cockpit, desktop/mobile layout, login/shell, and critical invoice/time entry passed. |
| Migrations | makemigrations check: no changes detected. |
| Compilation | compileall application packages: passed. |
| Type checking | python module mypy invocation: passed for 7 source files; executable launcher is broken. |
| Dependency audit | Client: one low esbuild advisory. Theme static source: one moderate tar advisory. |
| Patch hygiene | git diff check: passed. |

## Change made during this audit

One safe, isolated P0 defect was corrected:

- contracts/views_domains/contracts.py now initializes self.object in custom contract-creation POST, so invalid preview renders validation errors rather than raising AttributeError.
- tests/test_contract_required_fields.py now covers an invalid draft preview and requires HTTP 200 plus validation feedback.

The focused regression test passes. These are the only intentional source/test edits from this audit; pre-existing user changes and generated artifacts were preserved.

## Required go/no-go checklist

- [ ] Wire MSA Legal, Finance, summary, and export controls to real authenticated actions.
- [ ] Make MSA submission create persisted approvals and predictable state transitions.
- [ ] Provision/test Owner, Legal, Finance, operations/read-only, and cross-tenant users.
- [ ] Demonstrate allowed and denied actions, including approval and audit access.
- [ ] Persist/display all material audit events and reconcile visible history to AuditLog.
- [ ] Generate a real document and prove download/Word export from a fresh workflow.
- [ ] Implement/verify auto-renewal obligation extraction, assignment, notifications, and reporting.
- [ ] Resolve P0/P1 test failures and run backend/E2E suites cleanly.
- [ ] Use isolated database/Redis and require green health with no quota dependence.
- [ ] Apply Payrollminds terminology and approved language throughout.
- [ ] Re-run responsive, focus/keyboard, empty/error/loading, and cross-browser checks.
- [ ] Freeze resettable demo data, backup artifacts, and role credentials.

## Constrained fallback script

If proceeding despite no-go, show only a clearly labelled draft-generation preview:

1. Sign in as owner and open Command Center.
2. Open New Contract and explain intended Payrollminds categories.
3. Select MSA and show validation.
4. Enter prepared high-value, privacy-sensitive, auto-renewing Netherlands scenario.
5. Generate draft; show persisted values, approved provenance, risks, and proposed route.
6. Open Obligations and show a prepared manually created renewal item.
7. Stop before review, approval, audit completion, summary, or export; state they are not included.

This fallback is unsuitable where the audience expects real Legal/Finance workflow, document output, or defensible audit trail.

## Demo reset and operational plan

Use only the disposable E2E database. Do not use the default server while it points at remote Supabase.

1. Start isolated environment with sh scripts/start_e2e_server.sh and confirm port 8010.
2. For clean disposable rehearsal data, remove only local e2e.sqlite3 and restart to reseed. Never do this to shared/remote database.
3. Pre-create/verify owner, Legal, Finance, and read-only accounts after workflow implementation.
4. Prepare named Payrollminds samples; remove ad-hoc audit records before customer session.
5. Check health, database, Redis, static assets, logout/login in fresh browser profile immediately before meeting.
6. Keep a pre-approved static document and recording only as explicit contingency, never as evidence of live export.

## Final recommendation

**NO-GO.** The build is suitable for an internal walkthrough of MSA intake and draft generation, not the requested Payrollminds end-to-end contract-lifecycle demonstration. First make visible workflow/document controls real; then prove them with clean tests, role-based browser evidence, isolated demo infrastructure, and corrected Payrollminds terminology.

