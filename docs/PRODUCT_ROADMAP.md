# CLM One Product Roadmap

**Product thesis:** CLM One is a governed work system with contracts underneath — not a contract repository with work features attached.

**North-star outcome:** A user opens CLM One and immediately knows what needs action, what is most urgent, why it matters, what to do next, and when it is due — without hunting across five screens.

**Last updated:** 2026-07-21 (Phase 1 in progress)  
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

## Phase 1 — Lock boundaries and one work model

**Goal:** Stop the app from arguing with itself. Make “work” one concept with many views.

### 1.1 Product-map audit

- [x] Audit every destination against the product map above
- [x] Remove or redirect duplicate personal queues (dashboard “Waiting on Me”, Command Center “My Queue” as personal inbox)
- [x] Fix naming drift (e.g. dashboard / hub labels that still say “My work”)
- [x] Document the canonical route for each job-to-be-done ([`PRODUCT_MAP.md`](PRODUCT_MAP.md))

**Acceptance:** No two primary nav destinations answer the same question with different data shapes.

### 1.2 Canonical assignment model

Fund one assignment / work-item model with:

- Owner and acting assignee (delegation-aware)
- Source type (approval, review, privacy, task, obligation, workflow step, …)
- Priority + SLA / priority reason
- Status in user language (not vague “Open / Pending”)
- Deep link to the correct action context
- Permission-safe rendering (restricted / ethical-wall safe states)

Then:

- [x] My Work becomes a **view** over that model (`contracts/services/assignments.py`)
- [ ] Command Center becomes an **org-wide view** over the same model (saved views updated; full projection reuse is Phase 2)
- [ ] Specialist inboxes keep depth, but read the same underlying assignments / events

**Acceptance:** Adding a new work type does not require a new bespoke ETL per page.

### 1.3 Queue honesty baseline

- [ ] Shared empty / error / loading patterns across My Work, Command Center, Approvals, Privacy, Obligations
- [ ] No “coming soon” cards without a dated delivery path
- [ ] No duplicate CTAs already present in the sidebar

**Acceptance:** Every queue either shows real work, a truthful empty state, or a recoverable error — never fake product.

**Phase 1 exit:** Boundaries are clear, work is one model, and personal vs org-wide queues no longer overlap.

**Phase 1 status (2026-07-21):** Boundary fixes shipped — canonical `assignments` service, My Work reads from it, Command Center “My Queue” replaced with org-wide “Blocked work”, dashboard “Waiting on Me” tab removed, contract hub tab links to My Work. Remaining: specialist inbox consolidation (1.2) and shared queue patterns (1.3).

---

## Phase 2 — Finish the core loop in context

**Goal:** Make Intake → Close undeniable before expanding breadth.

### 2.1 Action-context deep links

- [ ] Every work row opens the correct task context, not only the general contract page
- [ ] Primary action labels stay singular: Review / Approve / Respond / Complete / Correct / Open
- [ ] Secondary actions stay in overflow menus

### 2.2 Specialist depth (not alternate lists)

Score and harden each specialist surface against the four loop checks:

| Surface | Focus |
|--------|--------|
| Reviews & Approvals | Decision in place, return / reject with reason, audit outcome |
| Privacy Reviews | Questionnaire / assessment completion, conflict resolution path |
| Obligations | Complete / defer / escalate with due and owner clarity |
| Contract detail | Next required action visible without leaving the record |

### 2.3 Command Center as org ops

- [ ] Command Center is explicitly organization-wide
- [ ] Remove personal-inbox framing from Command Center
- [ ] Surface blockers, overdue risk, and cross-team wait states

**Phase 2 exit:** A counsel can discover, understand, act, and leave an audit trail for the full loop without relying on tribal knowledge of which queue is “real.”

---

## Phase 3 — Governance as visible product value

**Goal:** Make CLM One’s edge obvious in the UI, not only in backend rules.

### Visible product promises

| Promise | Product expression |
|--------|--------------------|
| You only see work you are allowed to act on | Restricted / ethical-wall safe rows; no metadata leaks |
| Every reassignment and return is auditable | Audit events for assign, reassign, complete, approve, reject, return, SLA breach |
| Blocked work explains who must act next | Blocker copy + next actor on row detail |
| High-risk and overdue rise by rule | Priority from workflow / SLA / risk / assignment config — not decorative urgency |

### Delivery items

- [ ] Blocked-state pattern across all queues
- [ ] Delegation / absence coverage in UI (original assignee, acting assignee, period, reason, audit)
- [ ] SLA / priority reason tooltips and expandable detail everywhere priority is shown
- [ ] Manager reassignment controls for authorized roles (no silent ownership transfer)

**Phase 3 exit:** Governance is a user-visible operating advantage, not an implementation detail.

---

## Phase 4 — Navigation cleanup and legacy retirement

**Goal:** A smaller nav with complete destinations.

### Keep

- **Workspace:** Command Center, My Work, Contracts, New Contract
- **Governance:** Reviews & Approvals, Privacy Reviews, Obligations
- **Configuration:** Templates & Playbooks, Workflow Designer

### Retire or demote

- [ ] Parallel repository / list routes where a canonical route exists
- [ ] Half-migrated law-firm modules without an in-house CLM job-to-be-done
- [ ] Dashboard widgets that merely repeat specialist workspaces

**Phase 4 exit:** Default navigation only exposes destinations that are complete enough to trust.

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

| Phase | Theme | Primary outcome |
|------|--------|-----------------|
| **0** | Personal hub | My Work answers “what needs me now?” |
| **1** | Boundaries + one work model | App stops arguing with itself |
| **2** | Core loop in context | Intake → Close is completable |
| **3** | Governance visible | Trust and control are product features |
| **4** | Nav / legacy cleanup | Smaller, complete IA |
| **5** | Instrumentation | Operating metrics guide the roadmap |
| **6** | Amplifiers | Reporting, prediction, AI on a trusted base |

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

Ordered for maximum product clarity:

1. **Canonical assignment model** + migrate My Work onto it
2. **Command Center boundary fix** (org-wide only; remove personal-queue overlap)
3. **Naming / IA audit** across dashboard, hubs, and sidebar labels
4. **Shared queue honesty** (empty / error / loading) on Approvals, Privacy, Obligations, Command Center
5. **Action-context deep links** for every My Work / Command Center row
6. **Delegation + blocked-state UX** across queues
7. **Work-event instrumentation** and first operating dashboard for legal ops

---

## Success definition

CLM One is succeeding when:

1. Personal work is discovered in **My Work**
2. Org risk and blockers are triaged in **Command Center**
3. Specialist work is completed in specialist workspaces without duplicating the hub
4. Every assignment respects permissions and leaves an audit trail
5. Users stop asking “which screen is the real one?”
