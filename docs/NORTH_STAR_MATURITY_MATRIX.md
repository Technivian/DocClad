# CMS Aegis North-Star Maturity Matrix

Last updated: 2026-05-16

This matrix grades the product by domain against a north-star target: a production-ready, enterprise CLM platform with proven integrations, repeatable release evidence, strong operability, and polished UX.

## Score Scale

- 5.0 = production-complete and operationally proven
- 4.0 = strong product surface with a few high-value gaps
- 3.0 = usable, but still missing live proof, polish, or hardening
- 2.0 = partial implementation or thin enterprise depth
- 1.0 = mostly planned or experimental

## Executive View

| Area | Maturity | State | What exists now | What is left for 100% |
|---|---:|---|---|---|
| Identity, tenancy, access | 4.5 | Strong | Multi-tenant org model, auth, SSO, SAML, SCIM, MFA, session controls | Live IdP/SCIM proof, richer device/session policy, better permission transparency |
| Contract core lifecycle | 4.0 | Strong | Contract CRUD, search, notes, deadlines, document versions, compare UI, lifecycle guardrails | Fully automated draft-to-archive / renewal flow and richer immutable history UX |
| Workflow, approvals, signatures | 3.8 | Good | Workflow templates, approvals, routing guards, signature requests, reconciliation hooks | More advanced builder UX, live e-sign provider proof, clearer execution visibility |
| Clause library and playbooks | 4.5 | Strong | Clause variants, playbooks, mandatory fallback policy, compare/versioning, semantic ranking | Clause analytics, better compare/navigation polish, more explainable fallback behavior |
| Search, repository, saved views | 4.0 | Strong | Global search, repository views, semantic modes, saved presets | Deeper faceting, relevance telemetry, better explainability and ranking controls |
| Privacy and compliance ops | 4.2 | Strong | DSAR, retention, subprocessors, transfers, legal holds, evidence tooling | More export polish, deadline automation, customer-facing compliance artifacts |
| Reporting and analytics | 3.8 | Good | Executive analytics APIs, reports dashboard, presets, export paths | More KPIs, more export formats, live multi-org evidence, stronger drill-downs |
| Integrations | 3.2 | Partial | Salesforce, NetSuite, webhooks, e-sign, evidence commands/workflows | Real target-env proof, stronger diagnostics, rollback-linked live evidence |
| AI governance and assistant | 3.2 | Partial | Tenant-scoped assistant, policy controls, action planning/execution scaffolding | Stronger citations, model governance, review UX, red-team coverage |
| Frontend/UI system | 3.6 | Good | Multiple shells, redesign toggle, styleguide, component demo, server-rendered templates | Consolidate shells, complete responsive polish, remove placeholder/demo noise |
| QA and release operations | 3.5 | Good | Large test suite, smoke/evidence commands, cutover checks, release gate workflow | Full live smoke in target env, recurring rollback evidence, artifact discipline |
| Infrastructure and production readiness | 3.0 | Partial | Postgres support, dependency scanning, observability hooks, drill evidence | Backup/restore proof, rollback rehearsal, production cutover evidence, remaining advisories |
| Commercial readiness | 2.8 | Partial | Core enterprise workflows exist | Billing/subscription controls, self-serve onboarding, support/trust portal surfaces |

## Gap Analysis

### 1. What is already near the finish line

- Core CLM flows are implemented and usable.
- The test suite is healthy, and major release-evidence commands exist.
- Identity, tenancy, workflow, clause governance, privacy/compliance, and reporting are all well beyond MVP.
- The product already looks and behaves like a real enterprise app rather than a prototype.

### 2. What still blocks true 100%

| Blocker class | Why it matters | Current status |
|---|---|---|
| Live integration evidence | Production signoff needs proof in the target environment, not just local tests | Salesforce, webhook, NetSuite, and e-sign still need real target-env runs |
| Release gate completion | North-star readiness requires a repeatable go/no-go path | SPR3-001/002/003 are still the top gate items |
| Backup / restore / rollback proof | This is the difference between “works locally” and “safe to operate” | Rehearsals exist, but the full production-target proof remains incomplete |
| UI consolidation | Too many shells and demo surfaces dilute product clarity | Some experimental/demonstration surfaces still remain |
| Enterprise polish | Customers will feel gaps in onboarding, support, billing, and diagnostics | Those surfaces are still thinner than the core product |

### 3. What to finish first

1. Close release-gate items `SPR3-001`, `SPR3-002`, and `SPR3-003`.
2. Capture real Salesforce, webhook, NetSuite, and e-sign evidence in a target environment.
3. Complete a real backup / restore / rollback rehearsal and attach artifacts.
4. Remove placeholder actions and consolidate remaining experimental UI shells.
5. Add the missing commercial and support surfaces needed for enterprise rollout.

## Domain Detail

### Identity and access

Current: strong. The app already has organization tenancy, enterprise SSO, SAML, SCIM, MFA, and session controls. The remaining gap is proving those flows against live IdPs and making session/device policy easier to inspect and manage.

### Contract core

Current: strong. Core contract CRUD, document versioning, compare views, and lifecycle guardrails are in place. The final work is to make archive, renewal, and document history feel fully automated and unmistakably production-grade.

### Workflow and signatures

Current: good. Routing, approvals, and signatures exist and are guarded. The missing piece is more builder depth and live e-sign provider evidence.

### Clause governance

Current: strong. Clause variants, playbooks, compare/versioning, and fallback policy are mature. The last mile is analytics and UX refinement around explainability and navigation.

### Search and reporting

Current: strong to good. Search and analytics are useful already, but the north-star version needs deeper filtering, relevance controls, and stronger export/reporting options.

### Privacy and compliance

Current: strong. The app already covers many compliance workflows. The remaining work is mostly evidence packaging, automation, and clearer customer-facing compliance outputs.

### Integrations

Current: partial. The code paths are there, but production readiness depends on live proof from Salesforce, webhook, NetSuite, and e-sign in a real environment.

### AI governance

Current: partial. There is useful AI scaffolding, but the app still needs more rigorous citations, review controls, and governance artifacts before it is truly enterprise-safe.

### UI and design system

Current: good. The app is visually credible, but it still has too many alternate shells and demo surfaces. The north-star state should feel smaller, clearer, and more unified.

### QA, release, and operations

Current: good. The automation and tests are real, but the release path still needs live smoke evidence, rollback proof, and repeatable artifact capture in the target environment.

### Infrastructure and production readiness

Current: partial. The app is operationally serious, but the production story is not finished until backup, restore, rollback, and cutover are proven end to end.

### Commercial readiness

Current: partial. The core product exists, but a complete enterprise package still needs onboarding, billing, support, and trust/compliance portal surfaces.

## Bottom Line

CMS Aegis is already a real enterprise CLM platform, not a toy. The remaining gap to “100%” is mostly about proving and packaging the system for production: live integration evidence, cutover/rollback confidence, UI consolidation, and enterprise support/commercial surfaces.