# CLM One Product Roadmap

**Product thesis:** CLM One is a governed work system with contracts underneath — not a contract repository with work features attached.

**North-star outcome:** A user opens CLM One and immediately knows what needs action, what is most urgent, why it matters, what to do next, and when it is due — without hunting across five screens.

**Last updated:** 2026-07-21 (Phases 3–13 complete)  
**Companion docs:** Engineering delivery waves live in [`ROADMAP.md`](../ROADMAP.md). Canonical boundaries live in [`PRODUCT_MAP.md`](PRODUCT_MAP.md). This document owns product boundaries, sequencing, and acceptance outcomes.

---

## Product map (non-negotiable)

| Surface | Means | Does not mean |
|--------|--------|----------------|
| **My Work** | What requires action from the signed-in user | Repository, reporting, org-wide ops |
| **Command Center** | Organization-wide operational visibility | Personal inbox |
| **Contracts** | Complete contract repository | Personal action queue |
| **Reviews & Approvals** | Specialist review / approval workspace | Full obligation or privacy workspace |
| **Privacy Reviews** | Specialist privacy workspace | General contract list |
| **Obligations** | Complete obligation workspace | Personal “everything assigned to me” hub |

Anything that duplicates another surface is removed, hidden, or redirected. Naming drift is treated as a product bug.

### Core operating loop

```text
Intake → Review → Approve → Sign → Track obligations → Renew / Close
```

Each step must pass four checks:

1. Can the user discover the work?
2. Can they understand why it matters?
3. Can they complete the next action in context?
4. Is the outcome recorded in audit / history?

---

## Persona lens (ship by role, not by module)

| Persona | Must-have jobs |
|--------|----------------|
| **Legal counsel** | My Work, contract detail workspace, reviews / redlines / findings, approvals |
| **Privacy / DPO** | Privacy Reviews, cross-document conflicts, questionnaires / assessments |
| **Commercial owner / requestor** | New Contract, returned / rejected correction flow, status visibility without admin clutter |
| **Legal ops / admin** | Command Center, Workflow Designer, templates / policies, bottleneck and SLA reporting |

If a module does not serve one of these jobs clearly, demote, merge, or cut it from the default experience.

---

## Phase 0 — Foundation (complete)

**Goal:** Establish the personal hub and stop fake product surfaces.

| Outcome | Status | Notes |
|--------|--------|-------|
| My Work as personal action hub | ✅ Done | Unified queue for assigned approvals, tasks, obligations, privacy, reviews, returned / rejected work |
| Remove My Work placeholder / duplicate nav CTAs | ✅ Done | No “future functionality” copy; no sidebar-duplicate buttons |
| Empty / error / refresh states on My Work | ✅ Done | Caught up, no filter matches, load failure, refresh + last updated |

**Exit criteria:** Opening `/contracts/my-work/` answers “What requires my attention now?” for the signed-in user.

---

## Phase 1 — Lock boundaries and one work model (complete)

**Goal:** Stop the app from arguing with itself. Make “work” one concept with many views.

### 1.1 Product-map audit ✅

- [x] Audit every destination against the product map above
- [x] Remove or redirect duplicate personal queues (dashboard “Waiting on Me”, Command Center “My Queue” as personal inbox)
- [x] Fix naming drift (e.g. dashboard / hub labels that still say “My work”)
- [x] Document the canonical route for each job-to-be-done ([`PRODUCT_MAP.md`](PRODUCT_MAP.md))

### 1.2 Canonical assignment model ✅

- [x] My Work is a **view** over `contracts/services/assignments.py`
- [x] Specialist personal tabs read shared assignment querysets (approvals, tasks, obligations, privacy)
- [x] Command Center saved views are org-wide only (“Blocked work” replaces “My Queue”)

### 1.3 Queue honesty baseline ✅

- [x] Shared empty states for specialist personal tabs (`_work_queue_empty_state.html` → My Work)
- [x] Removed undated “Coming soon” from Legal Front Door (legal questions route to task create)
- [x] Command Center KPIs and copy use org-wide framing, not personal inbox language

**Phase 1 exit:** ✅ Boundaries are clear, work is one model, and personal vs org-wide queues no longer overlap.

---

## Phase 2 — Finish the core loop in context (complete)

**Goal:** Make Intake → Close undeniable before expanding breadth.

### 2.1 Action-context deep links ✅

- [x] Review findings and returned/rejected work open contract workflow context (`?tab=workflow&section=…`)
- [x] Approvals, tasks, obligations, privacy packs, and workflow steps deep-link to action surfaces
- [x] My Work row click / Enter opens the primary action context; details stay in overflow
- [x] Secondary actions stay in overflow menus (My Work, Approvals Edit, Privacy risks, Obligations)

### 2.2 Specialist depth ✅

| Surface | Focus | Status |
|--------|--------|--------|
| Reviews & Approvals | Approve / Reject / Return with required reason; audit via existing APIs | ✅ Done |
| Privacy Reviews | Conflict-aware next action; Resolve conflicts path on list kebab → Risks tab | ✅ Done |
| Obligations | Complete / Defer 7 days / Escalate priority with audit trail | ✅ Done |
| Contract detail | Next required action strip on every tab; overview Action required card | ✅ Done |

### 2.3 Command Center as org ops ✅

- [x] Command Center subtitle and approval KPIs are explicitly organization-wide
- [x] Personal-inbox framing removed from attention banner and rail copy
- [x] Recommended actions tagged Blocked / Overdue / Waiting / Open; blocked-work summary in Action queue

**Phase 2 exit:** ✅ A counsel can discover, understand, act, and leave an audit trail for the full loop without relying on tribal knowledge of which queue is “real.”

---

## Phase 3 — Governance as visible product value (complete)

**Goal:** Make CLM One’s edge obvious in the UI, not only in backend rules.

### Visible product promises

| Promise | Product expression |
|--------|--------------------|
| You only see work you are allowed to act on | Restricted / ethical-wall safe rows; no metadata leaks |
| Every reassignment and return is auditable | Audit events for assign, reassign, complete, approve, reject, return, SLA breach |
| Blocked work explains who must act next | Blocker copy + next actor on row detail |
| High-risk and overdue rise by rule | Priority from workflow / SLA / risk / assignment config — not decorative urgency |

### Delivery items

- [x] Blocked-state pattern across all queues (My Work, Approvals, Obligations, Privacy)
- [x] Delegation / absence coverage in UI (original assignee, acting assignee, period, reason, audit)
- [x] SLA / priority reason tooltips and expandable detail wherever priority is shown
- [x] Manager reassignment controls for authorized roles (audited `approval.reassigned`; no silent ownership transfer)

**Phase 3 exit:** ✅ Governance is a user-visible operating advantage, not an implementation detail.

---

## Phase 4 — Navigation cleanup and legacy retirement (complete)

**Goal:** A smaller nav with complete destinations.

### Keep

- **Workspace:** Command Center, My Work, Contracts, New Contract
- **Governance:** Reviews & Approvals, Privacy Reviews, Obligations
- **Configuration:** Templates & Playbooks, Workflow Designer

### Retire or demote

- [x] Parallel repository / list routes where a canonical route exists (`contract_list` → repository; `deadline_list` → Obligations)
- [x] Half-migrated law-firm modules without an in-house CLM job-to-be-done (clients/invoices redirect for `in_house_clm`; matters stay deep-linkable but out of nav)
- [x] Dashboard widgets that merely repeat specialist workspaces (Recent Matters demoted to deep links; deadlines CTA → Obligations)

**Phase 4 exit:** ✅ Default navigation only exposes destinations that are complete enough to trust.

---

## Phase 5 — Instrument the operating system (complete)

**Goal:** Prove whether My Work is the hub or just another list.

### Instrument these events

1. [x] Work item surfaced — My Work render → `WorkInteractionEvent(surfaced)` (deduped / day)
2. [x] Work item opened — My Work beacon → `opened` (+ `from=my_work` on navigation)
3. [x] Primary action taken — beacon + surface-stamped specialist mutations
4. [x] Work completed / returned / rejected — mirrored into `WorkInteractionEvent` with `source_surface`
5. [x] SLA breach or overdue transition — `approval.sla_breached` + `sla_breached` work event

### Measure

| Metric | Why it matters | Source |
|--------|----------------|--------|
| Time to first action after assignment | Discovery + urgency quality | Surfaced → opened/action lag; approval decide lag |
| Overdue rate by work type | SLA / prioritization health | Surfaced events `is_overdue` by `work_kind` |
| Return / reject rate by contract type | Intake and review quality | Outcome events by `contract_type` |
| % completed from My Work vs specialist workspace | Whether the hub is working | `completed` events by `surface` |
| Restricted / blocked item frequency | Governance load and access friction | Surfaced `is_restricted` / `is_blocked` rates |

**Read API (admins):** `GET /contracts/api/analytics/work-metrics/`  
**Beacon:** `POST /contracts/api/analytics/work-events/`

**Phase 5 exit:** ✅ Roadmap decisions can be driven by operating metrics, not guesswork.

---

## Phase 6 — Amplifiers (complete)

**Goal:** Add reporting, persistent views, and measured prioritization only after the loop is trustworthy.

### Shipped

- [x] Cross-workspace **Work health** report for legal ops (`/contracts/ops/work-health/`) — bottlenecks by work type, return/reject by contract type, SLA breach list, My Work completion share
- [x] Persistent **My Work saved views** (per-user filter presets + default) via `MyWorkSavedView` and `/contracts/my-work/saved-views/`
- [x] Soft refresh on My Work: poll uses row `signature`; shows “New work is available” banner only; never silently reorders mid-interaction; pauses while filters/menus/details are open or the tab is hidden
- [x] Rule-based priority: overdue / escalated / blocked elevation plus measured overdue-rate sort nudge (`measured_priority_boost`)

### Explicitly deferred

- AI assistance (only when it changes a decision or next action)
- Charts / decorative “insights” dashboards
- ML / predictive models beyond measured rules

**Phase 6 exit:** ✅ Amplifiers sit on a trusted operating loop without fake urgency or silent queue churn.

---

## Phase 7 — Priority reason everywhere (complete)

**Goal:** Wherever priority or urgency appears on a work queue, the user can see **why** — via tooltip and the shared “Why this priority” pattern — without hunting in a detail drawer.

### Shipped

- [x] Shared `_governance_priority.html` used on My Work (table + mobile cards), Approvals, Tasks, Obligations, and Privacy Reviews
- [x] Tasks queue rows carry `priority_reason` from `sla_priority_reason` (overdue / HIGH / URGENT)
- [x] Obligations and Approvals expose label + tone + expandable reason on the priority affordance
- [x] `priority_tone` plumbed on assignment rows and specialist queues via `priority_tone_for_label`

### Explicitly deferred

- Specialist-workspace inline action parity with My Work (backlog item 2)
- AI assistance and charts / insights dashboards

**Phase 7 exit:** ✅ Rule-based priority reasons are visible on every primary work queue.

---

## Phase 8 — My Work action parity (complete)

**Goal:** Finish common specialist mutations from My Work without leaving the hub, while keeping deep-link row click as the primary open-context path.

### Shipped

- [x] Approval Approve / Reject / Return from My Work kebab (same APIs as Approvals, `surface=my_work`)
- [x] Task Mark complete from My Work kebab (`legal_task_complete` + outcome instrumentation)
- [x] Obligation Mark complete / Defer / Escalate from My Work kebab (JSON mode on deadline mutations)
- [x] Mutation URLs + `can_decide` / `can_complete` on assignment rows (never on restricted rows)
- [x] Mobile cards mirror the same kebab mutations

### Explicitly deferred

- Manager reassign from My Work
- Privacy conflict resolve / returned-work Correct in place
- AI assistance and charts / insights dashboards

**Phase 8 exit:** ✅ Approvals, tasks, and obligations can be completed from My Work without losing audit or surface attribution.

---

## Phase 9 — My Work governance actions (complete)

**Goal:** Finish the Phase 8 deferred governance mutations from My Work — reassign and privacy conflict disposition — without inventing new permission models.

### Shipped

- [x] Manager **Reassign…** on My Work approval rows (`approval_reassign_api`, admin/owner only)
- [x] Privacy conflict rows deep-link to `?tab=risks` and support **Mark resolved** / **Mark false positive** via `dpa_risk_item_set_status`
- [x] Pack rows with open conflicts expose kebab **Resolve conflicts** deep-link
- [x] Returned / rejected rows expose kebab **Correct on contract** (same workflow deep-link; no fake in-place Correct)

### Explicitly deferred

- AI assistance only where it changes a decision or next action
- Charts / insights dashboards after measured completion rates stay healthy
- Org-wide manager queue inside My Work
- Richer assignee picker UX (searchable combobox / workload ranking) beyond the Approvals-style user-id prompt

**Phase 9 exit:** ✅ Governance handoffs and privacy conflict disposition are available from My Work with the same APIs specialists use.

---

## Phase 10 — Reassign assignee picker (complete)

**Goal:** Replace numeric user-id `prompt()` reassignment with a named teammate picker and required reason on My Work and Approvals.

### Shipped

- [x] Shared `reassign_member_options` helper + org member list in My Work / Approvals context
- [x] Shared `_reassign_dialog.html` (select + reason) used by My Work and Approvals
- [x] Reassign no longer asks for a raw user id; current owner is shown and excluded from the picker
- [x] Same `approval_reassign_api` contract (`to_user_id` + reason)
- [x] Tests: `tests/test_phase10_reassign_picker.py`

### Explicitly deferred (completed in Phase 11)

- ~~AI assistance only where it changes a decision or next action~~ → Phase 11
- ~~Charts / insights dashboards~~ → Phase 11
- ~~Org-wide manager queue in My Work~~ → Phase 11
- ~~Searchable combobox / workload ranking~~ → Phase 11

**Phase 10 exit:** ✅ Managers reassign by teammate name with an explicit reason from My Work and Approvals.

---

## Phase 11 — Backlog amplifiers (complete)

**Goal:** Ship the four near-term backlog items without inventing new product surfaces: richer reassign UX, decision-changing AI assist, work-health charts, and an admin team queue on My Work.

### Shipped

- [x] Searchable assignee combobox with open-work workload ranking (My Work + Approvals)
- [x] Decision comment dialog with **Suggest reason** for reject/return (`approval_suggest_decision_api`; AI when enabled, template fallback otherwise — never auto-submits)
- [x] Work Health CSS charts: hub completion meter, bottleneck/return bars, daily activity series
- [x] Admin-only My Work **Team queue** (`?scope=team`) with assignee column + filter; members stay personal-scoped
- [x] Tests: `tests/test_phase11_backlog_amplifiers.py` (+ Phase 10 picker coverage extended)

### Explicitly deferred

- Org-wide manager queue as the default My Work view (team remains opt-in)
- Freeform AI assistant outside the decision loop
- Third-party chart libraries (Chart.js / Recharts)
- Live SSE workload streams (HTTP typeahead is enough for now)

**Phase 11 exit:** ✅ Backlog amplifiers are available on existing My Work, Approvals, and Work Health surfaces.

---

## Phase 12 — Backlog polish (complete)

**Goal:** Finish the remaining near-term polish without new product surfaces: live people search, prior-window work-health trends, and suggest-reason on more decision-changing actions.

### Shipped

- [x] Live assignee typeahead API (`assignee_options_api`) + debounced combobox search (initial embed capped)
- [x] Work Health prior-window **Period trends** (hub completion, time-to-action, decision lag, blocked rate)
- [x] Suggest reason for reassign, privacy conflict disposition, and obligation escalate (`work_suggest_comment_api`)
- [x] Conflict resolve/false-positive from My Work requires a note (stored on the risk item); escalate accepts a reason in audit
- [x] Tests: `tests/test_phase12_backlog_polish.py`

### Explicitly deferred

- Org-wide manager queue as the default My Work view
- Freeform AI assistant outside the decision loop
- Third-party chart libraries
- Push/SSE live workload feeds

**Phase 12 exit:** ✅ Remaining backlog polish is available on My Work, Approvals, and Work Health.

---

## Phase 13 — Ship readiness (complete)

**Goal:** Production-validation plumbing — adoption evidence, team-queue hardening — without shipping the deferred product bets (team-as-default, freeform AI, Chart.js, SSE).

### Shipped

- [x] Adoption evidence on Work Health (team queue views, assignee searches, suggest requested/applied) + reconsideration gates
- [x] Team queue row cap (250) with truncation banner; skip heavy activity fan-out on large team queues
- [x] 60s cache for assignee open-work workload counts
- [x] Evidence beacons from search/suggest APIs and client `suggest_applied`
- [x] Tests: `tests/test_phase13_ship_evidence_harden.py`

### Still deferred (evidence-gated)

- Team queue as My Work default
- Freeform AI outside the decision loop
- Chart.js / third-party charts
- SSE live workload feeds

**Phase 13 exit:** ✅ Ops can watch amplifier usage and only reopen deferred items when gates fire.

---

## Sequencing summary

| Phase | Theme | Primary outcome | Status |
|------|--------|-----------------|--------|
| **0** | Personal hub | My Work answers “what needs me now?” | ✅ Complete |
| **1** | Boundaries + one work model | App stops arguing with itself | ✅ Complete |
| **2** | Core loop in context | Intake → Close is completable | ✅ Complete |
| **3** | Governance visible | Trust and control are product features | ✅ Complete |
| **4** | Nav / legacy cleanup | Smaller, complete IA | ✅ Complete |
| **5** | Instrumentation | Operating metrics guide the roadmap | ✅ Complete |
| **6** | Amplifiers | Reporting, saved views, measured priority | ✅ Complete |
| **7** | Priority reason everywhere | Why urgency is shown is always answerable | ✅ Complete |
| **8** | My Work action parity | Hub completes common specialist mutations | ✅ Complete |
| **9** | My Work governance actions | Reassign + privacy conflict resolve from hub | ✅ Complete |
| **10** | Reassign assignee picker | Name select + reason replaces user-id prompt | ✅ Complete |
| **11** | Backlog amplifiers | Combobox, decision suggest, charts, team queue | ✅ Complete |
| **12** | Backlog polish | Live search, trends, more decision suggests | ✅ Complete |
| **13** | Ship readiness | Adoption evidence + team-queue hardening | ✅ Complete |

---

## Explicit non-goals

- Do **not** turn My Work into another repository
- Do **not** turn Command Center into a personal inbox
- Do **not** add nav items to compensate for unfinished workflows
- Do **not** ship fake urgency with red UI instead of rule-based priority
- Do **not** expand law-firm-era modules without a clear in-house CLM job-to-be-done
- Do **not** add decorative dashboards before the action loop is trustworthy
- Do **not** show pages that describe functionality that is not available

---

## Near-term backlog (recommended next builds)

_No open product-roadmap backlog items._ Watch Work Health **Adoption evidence** gates before inventing the next surface.

---

## Success definition

CLM One is succeeding when:

1. Personal work is discovered in **My Work**
2. Org risk and blockers are triaged in **Command Center**
3. Specialist work is completed in specialist workspaces without duplicating the hub
4. Every assignment respects permissions and leaves an audit trail
5. Users stop asking “which screen is the real one?”
