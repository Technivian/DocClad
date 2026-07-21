# CLM One Product Roadmap

**Product thesis:** CLM One is a governed work system with contracts underneath — not a contract repository with work features attached.

**North-star outcome:** A user opens CLM One and immediately knows what needs action, what is most urgent, why it matters, what to do next, and when it is due — without hunting across five screens.

**Last updated:** 2026-07-21 (Phases 3–4 complete)  
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

## Phase 5 — Instrument the operating system

**Goal:** Prove whether My Work is the hub or just another list.

### Instrument these events

1. Work item surfaced
2. Work item opened
3. Primary action taken
4. Work completed / returned / rejected
5. SLA breach or overdue transition

### Measure

| Metric | Why it matters |
|--------|----------------|
| Time to first action after assignment | Discovery + urgency quality |
| Overdue rate by work type | SLA / prioritization health |
| Return / reject rate by contract type | Intake and review quality |
| % completed from My Work vs specialist workspace | Whether the hub is working |
| Restricted / blocked item frequency | Governance load and access friction |

**Phase 5 exit:** Roadmap decisions are driven by operating metrics, not guesswork.

---

## Phase 6 — Amplifiers (only after the loop is trustworthy)

Do **not** start these until Phases 1–3 are solid.

- Cross-workspace reporting on bottlenecks and SLA breaches
- Persistent saved views / filters where users live daily
- Real-time refresh only where it improves trust (no silent reorder mid-interaction)
- Predictive prioritization based on measured rules
- AI assistance only where it changes a decision or next action
- Charts / “insights” dashboards only after action completion is reliable

---

## Sequencing summary

| Phase | Theme | Primary outcome | Status |
|------|--------|-----------------|--------|
| **0** | Personal hub | My Work answers “what needs me now?” | ✅ Complete |
| **1** | Boundaries + one work model | App stops arguing with itself | ✅ Complete |
| **2** | Core loop in context | Intake → Close is completable | ✅ Complete |
| **3** | Governance visible | Trust and control are product features | Planned |
| **4** | Nav / legacy cleanup | Smaller, complete IA | Planned |
| **5** | Instrumentation | Operating metrics guide the roadmap | Planned |
| **6** | Amplifiers | Reporting, prediction, AI on a trusted base | Planned |

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

1. **Delegation + blocked-state UX** across queues (Phase 3)
2. **SLA / priority reason tooltips** everywhere priority is shown
3. **Manager reassignment** for authorized roles
4. **Work-event instrumentation** and first operating dashboard for legal ops
5. **Nav / legacy retirement** of parallel list routes (Phase 4)

---

## Success definition

CLM One is succeeding when:

1. Personal work is discovered in **My Work**
2. Org risk and blockers are triaged in **Command Center**
3. Specialist work is completed in specialist workspaces without duplicating the hub
4. Every assignment respects permissions and leaves an audit trail
5. Users stop asking “which screen is the real one?”
