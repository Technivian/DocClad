# CLM One Legal Work Engine — Product/Design Plan

Status: **PLAN ONLY — not approved, not implemented.** No template, view, service, or model has been touched to produce this document. Wait for explicit sign-off before any of Phase B onward begins (see §7).

Companion documents:
- [`CLMONE_CONTRACT_LAUNCHER_MAPPING.md`](./CLMONE_CONTRACT_LAUNCHER_MAPPING.md) — the contract-type-by-contract-type mapping table (§3 of the brief).
- [`CLMONE_GOLDEN_SCREEN_REDESIGN_PLAN.md`](./CLMONE_GOLDEN_SCREEN_REDESIGN_PLAN.md) — cockpit redesign detail and the code-impact classification (§4 and §6 of the brief).

This plan builds on, and does not restate, three living documents already in the repo — cite them rather than duplicate them:
- [`CLMONE_VISUAL_STANDARD.md`](./CLMONE_VISUAL_STANDARD.md) — North Star, core objects (Contract Type, Workflow Template/Instance, Draft Document, Risk Signal, Approval Route, Clause Library), user types, navigation model, AI wording rules, visual system rules. Everything below assumes this vocabulary.
- [`../WORKFLOW_COCKPIT_REFERENCE_PATTERN.md`](../WORKFLOW_COCKPIT_REFERENCE_PATTERN.md) — the actual current implementation pattern behind the DPA/MSA/NDA cockpits (routes, models created, risk-signal pattern, approval-route pattern, clause-id/source-label vocabulary).
- [`../WORKSPACE_MODE_CONTAINMENT.md`](../WORKSPACE_MODE_CONTAINMENT.md) — the policy that governs what `Organization.workspace_mode` is and isn't allowed to change (UI emphasis only, never permissions/routes). "Preserve workspace-mode containment" in this plan means: stay inside that policy's two legal shapes.

## 0. What's already true today (don't re-propose this)

A prior redesign round already shipped real visual work on 6 of the screens this brief targets: Command Center, contract type picker, generic New Contract form, and all three DPA/MSA/NDA cockpits. Concretely, as of today:

- The contract type picker (`contract_template_picker.html`) already is the "What are you creating?" screen with 6 tone-consistent entry cards (MSA, DPA, NDA, SOW, Supplier Agreement, Addendum), each showing template/workflow/draft-time/typical-approvals and a "Start governed draft" CTA — this is materially what §2 below asks for at the entry step.
- DPA/MSA/NDA cockpits already have: a bounded document canvas with numbered clause badges, per-clause source-label pills (*Approved template* / *AI-assisted suggestion* / *Approved clause library* / *Risk-triggered fallback*), a sticky draft header, and a right rail grouped into **Template & Playbook / Risk & Compliance / Approval & Audit** with icon medallions.
- The generic New Contract form already has numbered section badges and the same grouped governance rail pattern.
- The Command Center already has tone-colored KPI card icon medallions and icon medallions on the right-rail cards.

So this plan is **not** "build the legal work engine from zero." It's: (a) add the Legal Front Door, which doesn't exist yet in any form, (b) close real gaps the code research below surfaced in the launcher/cockpit/command-center logic, and (c) extend contract-type coverage (SaaS, Supplier, Amendment) toward the same governed pattern DPA/MSA/NDA already have. §4–§6 in the companion doc lays out exactly what's shipped vs. what's a genuine gap, screen by screen.

## 0.1 A blocking precondition to flag now

Independent of this brief, `theme/templates/base.html` and three design-system CSS files currently have **uncommitted, in-progress changes** (not made by this planning work) that strip dark-mode support and switch the sidebar shell from deep navy to a flat light theme ("CLM One is intentionally light-only"). That directly contradicts this brief's explicit visual identity ("deep navy shell... teal for workflow/compliance/readiness/trust"). This isn't something this plan can resolve — it needs a decision from you on which direction is current before any shell-adjacent work (nav additions for the Front Door, Command Center rail changes) starts, or the work will be built against a shell that's about to change under it. Flagging it here so it isn't silently inherited into Phase B.

## 1. Legal Front Door proposal

### Recommended entry screen

A new screen, **not** replacing the Command Center as the post-login landing (that's a separate product decision, called out below) — first ship it as a clearly-linked destination (new sidebar entry under a `START` section, e.g. "New Legal Work", plus keep "+ New Contract" going straight to the existing picker for muscle-memory continuity). New route, e.g. `contracts:legal_front_door` at `/start/`. Net-new template + thin view; no model changes.

Header: *"What legal work do you need?"* Subhead in the CLMONE_VISUAL_STANDARD voice: *"CLM One will route you to the right governed workflow, template, and approval path."*

### Available legal-work options and how each routes

| Option | Routes to | New backend? |
|---|---|---|
| **Create a contract** | Existing `contracts:contract_template_picker` (already the redesigned 6-card launcher) | None — direct reuse |
| **Review a contract** | Existing `contracts:contract_list` / `contracts:repository` → existing contract detail/workspace | None — direct reuse |
| **Upload signed contract** | New thin UI (upload form + confirmation) wired to the **existing** `document_upload_api` (`contracts/api/documents_ai.py:139-189`, already does hash → OCR queue → AI extraction ingest) | View/template only — the API already exists and is unused by any UI today |
| **Start DPA review** | Existing `contracts:dpa_review_pack_list` (DPA Reviews — reviewing an *existing* contract's DPA risk posture) | None — direct reuse. Keep this distinct from "Create a contract → DPA", which is *drafting* a new DPA via the DPA cockpit; the Front Door should visually separate "review an existing DPA" from "draft a new DPA" so users don't confuse the two |
| **Ask a legal question** | **No existing feature** (confirmed: zero matches for any legal-question/helpdesk pattern in the codebase) | See below — do not build an AI-answers-legal-questions feature; this needs an explicit, separately-approved decision |
| **Request approval** | Existing `contracts:approval_request_list` (the `ApprovalRule`/`ApprovalRequest` engine, already mode-neutral per workspace-mode containment) | None — direct reuse |
| **Start renewal/amendment** | Interim: existing generic contract form pre-typed to Amendment (`contract_create?type=AMENDMENT`) | None for the interim version. A dedicated Renewal/Amendment cockpit (parallel to DPA/MSA/NDA) is real net-new scope — no such workflow builder exists today, unlike DPA/MSA/NDA which do. Whether the generic form can link an amendment back to its parent contract needs a code check before promising that in copy — flag as **needs verification**, not assumed |

**On "Ask a legal question":** per the brief's own constraint ("do not invent legal advice"), this cannot be an AI answer box. Two honest options, neither implemented without approval:
1. **Interim, zero backend risk**: route to a static "Contact Legal" page or existing internal comms channel. Ships in Phase B with everything else.
2. **Proper version**: a short intake form that creates a routed request to the Legal team — likely reusing the existing `ApprovalRequest`-style engine or a comparably lightweight new record. This is a domain-model question (does a "question," as opposed to an approval, warrant its own model, or does it overload `ApprovalRequest`'s semantics?) that needs an explicit answer before any model change — surfaced here, not decided here.

### Design posture

Untitled-UI-grade card layout (spacing, elevation, empty-state quality), Carelane-grade urgency ordering (if the user has open legal work — pending approvals, blocked contracts — the Front Door should say so above the option grid, not bury it), CLM One's own restrained palette (teal governance chips, one copper primary action per card, no rainbow).

## 2. Guided Contract Launcher proposal

The launcher already exists in two tiers, confirmed from the codebase:

- **Tier 1 (has a dedicated cockpit today): NDA, MSA, DPA.** Type selected → dedicated workflow builder view (`DPAWorkflowBuilderView`/`MSAWorkflowBuilderView`/`NDAWorkflowBuilderView`) → seeded `WorkflowTemplate` + `FieldDefinition`s drive the guided fields → live draft renders from the approved template → rule-based `RiskSignal`s compute in the per-type service (`dpa_workflow.py` / `msa_workflow.py` / `nda_workflow.py`) → `ApprovalRoute` rows (seeded per template, **not** dynamically computed) render the approval preview → on submit, one `@transaction.atomic` service call creates `Contract`, `Workflow`, `WorkflowStep`s, `FieldValue`s, `DraftDocument`, `RiskSignal`s, and a `CommandCenterWorkItem`, then redirects to the Contract Workspace.
- **Tier 2 (generic form, still governed, no split-screen cockpit): SOW, Supplier/VENDOR, Amendment, and everything else.** Type selected → `contract_create?type=<ct>` → `ContractCreateView` builds `governance_panel` (template, clause count, approval-route preview, risk summary) and `launch_setup_map` (server-side required-field policy per type, from `contracts/services/contract_policies.py`) → required fields ARE already dynamic and server-enforced (in `ContractForm.clean()`, same policy source as the client hint — this is a real, working piece of governance, not a form dump).

Gaps against the brief's requested flow, each stated as a gap rather than assumed fixed:

1. **"Self-serve / legal-review route determined" is not a first-class, consistently-surfaced state.** Today: MSA and NDA set `Contract.risk_level` from their detected signals; **DPA does not** — its service computes signals but never writes `contract.risk_level`. NDA's cockpit shows a "Self-serve ready / Legal review required" chip, but it's computed client-side and not persisted as a field. Recommendation: define one explicit self-serve-eligibility rule per type (see mapping doc), surface it identically across all three cockpits and the generic form, and — this is the one place a small service-layer change is warranted — either persist it or compute it from `risk_level` consistently (requires DPA's service to actually set `contract.risk_level`, which it currently skips). Flagging why this is more than cosmetic: principle 3 of the brief ("self-serve only when rules allow it, otherwise route to legal") isn't reliably true today for DPA specifically.
2. **Approval-route "preview" is static, not risk-reactive, everywhere.** `ApprovalRoute` rows are seeded per `WorkflowTemplate` and rendered as-is; none of the three cockpits (or the generic form) recompute *which* steps appear based on the live risk signals — e.g. MSA's Finance-approval trigger is a documented risk signal, but the seeded approval route doesn't conditionally add/remove a Finance step from the visual route based on it (the route is a fixed 5-step list; only the *reasoning text* next to it reacts). This matches what's actually built (`ApprovalRoute.is_conditional`/`condition_note` fields exist and are already used for *labeling* a step as conditional — so partial support exists), but a fully dynamic route ("Finance step added because value exceeds threshold") is not there today. Worth deciding whether this is in scope for this round or explicitly deferred.
3. **"Obligations/deadlines prepared after creation" needs verification, not assumption.** `Deadline` is a real model feeding the Command Center's obligations rail and renewal-notice-window logic, but whether the DPA/MSA/NDA workflow-creation service functions actually create `Deadline` rows (vs. only `CommandCenterWorkItem`) was not confirmed in the code research behind this plan. Before promising this in product copy, this needs a direct code check — flagged, not asserted either way.
4. **Approval-route and risk-summary logic is duplicated three times, not shared.** `dpa_workflow.py`, `msa_workflow.py`, and `nda_workflow.py` each have their own near-identical `get_*_approval_route()` and clause-count helper, explicitly *not* sharing code with `draft_cockpit.py` (which serves the generic form) — a code comment in `dpa_workflow.py` states this is intentional ("no import dependency on draft_cockpit.py"). Unifying this into one shared service is a legitimate cleanup, but it's real service-layer surgery across three modules with their own test suites — not something to bundle into a visual redesign phase. Recommend leaving the duplication in place for this round and treating consolidation as its own, later, explicitly-scoped phase.

Everything else the brief asks for in §2 (contract type selected → template selected → playbook applied → dynamic required fields → risk checks activated) is already real, working behavior for Tier 1 types and partially real (governance panel, no split-screen) for Tier 2 types.

## 5. Command Center redesign plan

Current state (from the actual view, `contracts.py:658-1422`, and `contracts/services/command_center.py`):

- **Top signal cards** (4, already visually redesigned): Needs Legal Review (Case status PENDING/IN_REVIEW count), Exposure Review (sum of `.value` on workflow-type queue rows), Blocked (count of Blocked-status queue rows), Notice/Renewal Risk (deadlines in 30 days + expiring-soon case count). All four derive from the same underlying counts as the page's attention banner, so they can't visually disagree with each other — keep this invariant in any further change.
- **Priority Legal Work Queue**: reads persisted `CommandCenterWorkItem` rows (populated by the `refresh_command_center_projection` management-command job) with a fallback to a live-built queue when no persisted rows exist. **The 6 saved-view filter tabs (All/My Queue/DPA Conflicts/High Risk/Renewals/Waiting on Business) store their filter definitions but are not confirmed wired to actual queryset filtering in the view** — this needs a direct check before the redesign relies on them being functional; if they're currently decorative, that's a functional bug independent of this redesign and should be called out to you separately rather than silently inherited.
- **Right rail** (already has icon medallions): Upcoming Obligations (top 3 `Deadline`s, falls back to queue rows), High-Attention Records (high-risk count + two other static-ish counts), Recent Review Memos (`ReviewMemo` model, falls back to `DPAReviewPack`), **Repository Shortcuts — dead context.** `clm_repository_shortcuts` is built server-side (4 links: Templates Library, Workflow Templates, Clause Library, Counterparties) but the template never reads that context variable; what actually renders is a hardcoded duplicate of the same 4 links directly in the template. Low-risk cleanup either way (wire the context var or delete it), noted for Phase E rather than silently left as-is.
- **Secondary grid** (Lifecycle Status Overview, Top Review Blockers, Queue Health): these are operational stage/SLA counts tied to real filtered views, not vanity charts — they already satisfy "no decorative analytics" as long as rows stay clickable into a filtered queue (recommend confirming/adding that linkage where missing, visual-only change).

### Recommended shape (keeps the "no rainbow dashboard" restraint)

Don't grow the top strip past 4 cards — that's the brief's own "confident, not busy" bar. Instead:
- Fix the saved-view filter wiring if it's confirmed decorative (functional fix, not visual).
- Promote "Approvals waiting" and explicit DPA/MSA-conflict counts into the **right rail**, not a 5th KPI card — either as a new small card or folded into High-Attention Records, which is already a multi-metric card of exactly this shape.
- Resolve Repository Shortcuts (wire the real context var or drop the duplicate template markup — either way, one becomes the single source of truth).
- Everything the brief lists (contracts needing legal action, DPA/MSA conflicts, approvals waiting, renewals/deadlines, blocked work, risk exceptions, recent review memos, obligations) maps onto: the 4 KPI cards + the saved-view tabs (once confirmed wired) + the right rail. No new page section is needed; this is about closing wiring gaps and rebalancing what's already there.

## 7. Implementation phases

Small, sequential, each independently shippable and testable. **None of Phase B onward starts without explicit approval of this plan and the companion docs.**

- **Phase A — Reference board + component mapping.** No code. Confirm the precondition in §0.1 is resolved (dark-navy-shell direction decided). Confirm the two "needs verification" items (§2.3 obligations-on-create, §5 saved-view filter wiring) with direct code reads. Produce a short component inventory diff against what Round 2 already shipped, so Phase B doesn't rebuild existing work.
- **Phase B — Legal Front Door + Contract Launcher plan finalized.** New `legal_front_door` route/view/template only. Wire the 5 zero-new-backend options (Create, Review, DPA review, Request approval, and the interim Renewal/Amendment link) directly to existing routes. "Upload signed contract" UI wired to the existing upload API. "Ask a legal question" ships as the interim static/contact-Legal version only; the proper intake-model version is explicitly deferred pending a separate decision.
- **Phase C — New Contract flow redesign.** Close the self-serve-eligibility gap (§2.1): make DPA's service set `contract.risk_level` consistently with MSA/NDA, and surface one consistent self-serve/legal-review indicator across the generic form and all three cockpits. No new models.
- **Phase D — NDA/MSA/DPA cockpit redesign.** Mostly already shipped (see §0). Remaining scope: obligations-on-create verification and fix if needed (§2.3); optional dynamic approval-route step rendering (§2.2) — flag as stretch, not committed, pending your call on scope.
- **Phase E — Command Center redesign.** Saved-view filter wiring fix (if confirmed broken), Repository Shortcuts dedup, Approvals-waiting/DPA-conflict promotion into the right rail.
- **Phase F — Repository/Workflows/Approvals alignment + contract-type coverage expansion.** Extend the governed pattern (template/playbook/risk/approval preview) toward SaaS Agreement and Supplier Agreement (`VENDOR`) with the same rigor DPA/MSA/NDA have — decide then whether they get dedicated cockpits or stay on the generic-form tier with a stronger governance panel. Approval/risk service-logic consolidation (§2.4) considered here at the earliest, as its own explicitly-scoped sub-phase, not bundled with anything visual.

No phase after A begins without your explicit go-ahead. Nothing in Phase B–F changes an existing route, permission check, CSRF handling, or workspace-mode branch — new screens are additive; existing-screen changes are visual/wiring fixes called out individually above, each preserving current forms/validation/audit behavior.
