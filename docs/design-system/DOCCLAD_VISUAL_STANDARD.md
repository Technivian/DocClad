# DocClad Visual & Product Standard

Converted from `DocClad UI Redesign Blueprint v1.docx` so agents and contributors can diff, cite, update, and follow it without parsing a Word file. This is the standard — the `.docx` (archived alongside this file) is not a source of truth.

This document is the product/UX blueprint: North Star, core objects, user types, navigation, flagship screens, component system, and directional rules. For exact color tokens, hex values, and the most current button/badge decisions, defer to the actively-maintained [`/DOCCLAD_DESIGN_SYSTEM.md`](../../DOCCLAD_DESIGN_SYSTEM.md) — §9 below reflects this blueprint's original color *roles*, which that doc has since refined at the token level. For the implementation pattern (routes, records, risk signal codes) behind the workflow-first cockpits described here, see [`WORKFLOW_COCKPIT_REFERENCE_PATTERN.md`](./WORKFLOW_COCKPIT_REFERENCE_PATTERN.md).

## 1. North Star

DocClad should not feel like a document storage tool with forms attached.

It should feel like: a governed contract workflow system where AI helps draft, review, route, and monitor contracts inside approved templates, playbooks, risk rules, and audit trails.

The emotional target: **calm pressure, executive clarity, legal control, AI acceleration.**

Not flashy. Not generic SaaS. Not "AI magic." More like a legal operations cockpit with a brain under the glass.

This blueprint should guide product, design, and engineering decisions so the redesign does not drift into random screens or isolated UI improvements. That matters especially because DocClad's own governance model treats its Charter as the source of truth for product/design/engineering alignment.

## 2. Core Product Model

DocClad is workflow-first. The main product spine is:

```
Contract Type → Governed Workflow → AI-Assisted Draft → Risk Checks
→ Approvals → Signature → Repository → Obligations
```

**What this means:** a user does not simply "create a contract." They start a governed workflow based on a contract type.

Example:

```
User selects DPA
→ DocClad starts DPA Privacy Review Workflow
→ Applies GDPR Processor DPA template
→ Uses DPA playbook and clause library
→ Asks smart privacy questions
→ Generates live draft
→ Checks SCC/subprocessor/data transfer risks
→ Routes to Legal and DPO if needed
→ Stores final agreement and obligations
```

This is the foundation. Everything in the UI should orbit around this model.

## 3. Core Objects

The product objects the UI should be designed around.

### 3.1 Contract Type

The user-friendly starting point. Examples: MSA, DPA, NDA, SOW, Supplier Agreement, Addendum.

The user thinks: *"I need a DPA."*
The system thinks: *"Start DPA Privacy Review Workflow using the approved GDPR Processor template."*

### 3.2 Workflow Template

The reusable process behind each contract type.

Example — DPA Privacy Review Workflow stages:

```
Intake → AI Draft → Privacy Questions → Risk Checks
→ Legal Review → DPO Review → Signature → Repository → Obligation Tracking
```

The workflow template controls: required fields, template selection, clause logic, risk checks, approval routing, statuses, audit events.

### 3.3 Workflow Instance

One live running process. Example: *Northwind DPA - May 2026*.

A workflow instance contains: contract draft, metadata, current stage, owner, approvals, tasks, risk signals, comments, audit trail, final signed document.

### 3.4 Draft Document

The live contract draft, generated from: approved template, clause library, playbook rules, user field values, AI-assisted suggestions, fallback clauses.

**Wording — use:** "AI-assisted drafting from approved templates and playbooks."
**Wording — avoid:** "AI generated this contract from scratch."

### 3.5 Risk Signal

A detected issue requiring attention. Examples: missing SCC clause, liability cap outside standard position, subprocessors involved, data transfer outside EEA, auto-renewal notice window approaching, approval bottleneck, clause conflicts with playbook.

Each risk signal needs: severity, reason, source, recommended action, owner, status, audit log.

### 3.6 Approval Route

The required approval path. Example:

```
Contract Owner → Legal → Finance → DPO
```

Approvals should explain why they are triggered. Examples:
- "DPO approval required because personal data processing is selected."
- "Finance approval required because contract value exceeds €50,000."
- "Legal approval required because liability cap exceeds standard playbook position."

### 3.7 Clause Library

Approved reusable language. Contains: preferred clauses, fallback clauses, non-standard clauses, jurisdiction variants, contract-type variants, risk labels, approval triggers.

AI can suggest language, but the UI should show whether it came from: approved clause library, fallback position, AI suggestion requiring legal review, or external counterparty text.

## 4. User Types

The UI should not treat every user the same.

### 4.1 Business Requester
Job: *"I need a contract quickly and correctly."*
Needs: simple contract type selection, minimal required fields, clear progress, status visibility, easy responses to Legal, no legal complexity unless needed.
Primary screens: New Contract, My Queue, Contract Workspace, Approvals / Tasks.

### 4.2 Legal User
Job: *"I need to review risk, protect the company, and keep contracts moving."*
Needs: priority queue, risk signals, clause comparison, playbook position, fallback clauses, approval decisions, review memo, audit trail.
Primary screens: Command Center, Contract Workspace, DPA / Risk Review, Approvals, Risk Register.

### 4.3 Legal Ops / Admin
Job: *"I need to configure the machine."*
Needs: workflow templates, clause library, playbooks, approval rules, permissions, audit controls, template mapping.
Primary screens: Workflow Designer, Clause Library, Playbooks, Audit Trail, Admin settings.

### 4.4 Executive / Business Owner
Job: *"I need visibility into contract risk and bottlenecks."*
Needs: exposure under review, blocked signatures, renewal deadlines, risk movement, approval delays, business impact.
Primary screens: Command Center, Reports, Portfolio view, Renewals, Obligations.

## 5. Navigation Model

Recommended sidebar structure:

```
COMMAND
- Command Center
- My Queue
- Approvals

CREATE
- New Contract
- Drafts
- Workflow Templates

CONTRACTS
- Contract Workspace
- Repository
- Renewals
- Obligations

RISK & COMPLIANCE
- Risk Register
- DPA Reviews
- Compliance
- Audit Trail

ADMIN
- Workflow Designer
- Clause Library
- Playbooks
- Permissions
```

**Navigation principle:** use user jobs, not database labels.

| Bad | Better |
|---|---|
| Documents | New Contract |
| Metadata | Approvals |
| Requests | Risk Register |
| Tables | Renewals / Workflow Designer |

The UI should always answer: *"What can I do here?"*

## 6. Flagship Screens

Do not redesign every page equally. Start with the five screens that define the whole product.

### 6.1 Command Center

**Purpose:** the operational cockpit. It should answer: What needs attention? What is blocked? What risk is moving? What should I do next?

**Primary content:** active workflow instances, legal queue, blocking approvals, risk signals, upcoming deadlines, renewal notice windows, recommended actions, exposure under review.

**Suggested layout:** top bar → page header → AI signal strip → KPI cards → priority queue → right intelligence rail.

Header copy example: *"Command Center — 23 contracts need legal action across approvals, DPA reviews, renewals, and risk exceptions."*

KPI cards example: Legal Queue: 23 · Exposure Under Review: €4.7M · Blocked Signatures: 4 · Deadlines Next 30 Days: 18.

Priority Queue columns: Workflow/Contract, Type, Stage, Owner, Risk, Due date, Blocking issue, Next action.

Right rail cards: Risk Intelligence, Recommended Actions, Command Rail.

**Design feeling:** this screen should feel like DocClad knows what needs attention before the user does.

### 6.2 New Contract

**Purpose:** the flagship creation experience. It should not be a form — it should be an AI-powered governed drafting cockpit.

Flow:

```
Select contract type → Start governed workflow → Fill required fields
→ Live draft updates → AI suggests clauses → Risk checks run
→ Approval route appears → Generate governed draft
```

**Stage 1 — Contract Type Selection**

Header: *"What are you creating?"* / *"Select a contract type. DocClad will apply the right approved template, playbook, clause logic, and approval route."*

Badge: "AI-powered drafting · Approved templates · Full audit trail"

Cards: MSA, DPA, NDA, SOW, Supplier Agreement, Addendum. Each card shows: template, workflow, estimated draft time, typical approvals, "Start draft" CTA.

Example card — DPA / Data Processing Agreement: "Generate processor terms with privacy, SCC, and subprocessor checks." Template: GDPR Processor. Workflow: DPA Privacy Review. Draft time: 4 min. Approvals: Legal, DPO. CTA: "Start governed draft."

**Stage 2 — AI Draft Builder**

Split-screen layout: left = required fields + smart questions; right = live contract draft preview; right/bottom = governance panel.

Top title: "New DPA Draft" / "Generated from approved template: GDPR Processor DPA · Netherlands · B2B"

Badges: AI-assisted · Approved template · Governance controls active · Audit trail enabled

Left panel sections: Basic Details, Commercial Terms, Privacy Details, Legal Position, AI Smart Questions.

Right panel — Live Contract Draft. Document preview should show highlighted placeholders, e.g.:

> This Data Processing Agreement is entered into between DocClad B.V. and **[Counterparty Name]** as of **[Effective Date]**. The Processor shall process personal data only for the purposes described in **[Processing Purpose]**. Data transfers outside the EEA: **[Data Transfer Position]**.

AI action bar: Complete missing fields · Suggest fallback clause · Explain clause · Generate summary · Compare to playbook.

**Stage 3 — Review & Route**

Panel title: "Draft Readiness"

Checklist example:
- Required fields completed: 11/14
- Approved template applied
- 2 fallback clauses suggested
- 1 DPO review required
- 1 Legal approval required
- 0 blocking errors
- Audit trail active

Risk summary example: Risk level: Medium. Reasons: personal data processing selected; data may leave the EEA; subprocessors involved.

Approval route: `Contract Owner → Legal → DPO → Signature`

CTAs: Generate governed draft · Save draft · Send for approval · Export Word · Open in workspace.

### 6.3 Contract Workspace

**Purpose:** the single source of truth for one contract/workflow. It should answer: What is this contract? Where is it in the workflow? What risks exist? Who needs to act? What changed? What obligations matter after signature?

**Layout:** header (contract title, type, counterparty, status, owner) → main left (document preview/editor) → right rail (workflow status, approvals, risk signals, key metadata, next action) → tabs (Overview, Document, Tasks, Approvals, Risks, Obligations, Comments, Audit Trail).

**Key components:** workflow stepper, document preview, metadata panel, approval timeline, risk signal list, clause suggestions, comments, audit log.

**Design feeling:** everything about one contract lives here. No hunting. No tab labyrinth.

### 6.4 DPA / Risk Review

**Purpose:** the legal intelligence screen — where DocClad proves it is more than drafting. It should answer: What risks did we find? What does the playbook say? What clause is problematic? What fallback should we use? Who needs to approve? Can we generate a memo?

**Layout:** header ("DPA Review: Northwind DPA") → left (issue list/risk signals) → center (clause comparison/document excerpt) → right (playbook position, suggested fallback clause, approval impact, reviewer notes, memo generation).

Risk item example:
- **Missing SCC fallback clause** — Severity: Medium
- Source: DPA clause 8.2
- Playbook position: SCCs required for non-EEA transfers
- Recommended action: Insert approved SCC fallback clause
- Approval impact: DPO required

CTAs: Accept fallback · Mark as accepted risk · Request business input · Escalate to DPO · Generate review memo.

**Design feeling:** structured legal review. Explainable, auditable, calm.

### 6.5 Workflow Designer

**Purpose:** the admin power tool — where legal ops configures the machine.

**Layout:** workflow list (select workflow template) → main canvas (workflow stages) → right config panel (stage rules, required fields, approval triggers, template mapping, risk checks).

Example workflow — DPA Privacy Review Workflow stages: Intake, AI Draft, Privacy Review, Legal Review, DPO Approval, Signature, Repository.

Configurable rules:
- If personal data involved = yes → add DPA clause, trigger DPO approval
- If data leaves EEA = yes → run SCC check, add risk signal
- If contract value > €50,000 → trigger Finance approval

**Design feeling:** powerful but controlled. More legal operating system than drag-and-drop toy.

## 7. First Killer Demo Flow

Build one excellent end-to-end flow before expanding. **Recommended: the DPA workflow.**

Why DPA first? Because it demonstrates: AI-assisted drafting, approved templates, privacy logic, SCC checks, subprocessor checks, risk detection, DPO approval, legal review, audit trail, Command Center visibility.

NDA is too simple. MSA is valuable but broad. DPA is the perfect sharp demo flow.

DPA demo flow:

1. User clicks New Contract
2. User selects DPA
3. DocClad starts DPA Privacy Review Workflow
4. User fills required fields
5. User answers privacy smart questions
6. Live DPA draft updates
7. DocClad detects: personal data involved, subprocessors involved, possible EEA transfer
8. Risk signals appear
9. Approval route updates: Legal, DPO
10. User generates governed draft
11. Workflow instance appears in Command Center Priority Queue
12. User opens Contract Workspace
13. Legal reviews risks
14. DPO approval is routed
15. Contract moves toward signature

## 8. Component System

Build reusable components from the flagship screens.

**App shell:** sidebar, top bar, workspace switcher, user menu, global search, notification icons.

**Page structure:** page header, breadcrumbs, status chips, action bar, section cards.

**Workflow components:** workflow stepper, workflow stage badge, workflow instance row, workflow timeline, stage config panel.

**Contract creation components:** contract type card, selected workflow summary, required field group, smart question block, field-to-document mapping indicator, draft readiness checklist.

**Document components:** live contract preview, highlighted placeholder, clause block, clause status badge, AI suggestion bar, compare-to-playbook panel.

**Risk components:** risk badge, risk signal card, risk severity scale, risk reason block, recommended action panel, accepted risk state.

**Approval components:** approval route timeline, approval trigger explanation, approver card, approval status badge, blocking approval alert.

**AI components:** AI insight strip, AI suggestion card, AI governance panel, AI source badge, confidence/rationale block, "Based on approved playbook" label.

**Data components:** priority queue table, filter tabs, filter chips, view toggle, empty state, metric card, trend card, recommended action list.

## 9. Visual System Rules

### 9.1 Color Roles

| Color | Use for |
|---|---|
| Deep navy | Sidebar, main headings, structural authority, serious legal identity |
| Teal | AI intelligence, validated states, active workflow signals, safe/good status |
| Copper / orange | Primary CTA, creation actions, escalation action, important next step |
| Red / amber | **Only** risk, overdue items, missing required fields, exceptions |
| Off-white / light grey | Main workspace background, separation, calm enterprise breathing room |

### 9.2 Button Rules

**Primary button** — copper background, white text. Used for the main forward action only. Examples: New Contract, Generate governed draft, Send for approval, Start workflow.

**Secondary button** — white background, navy text, subtle border. Examples: Save draft, View details, Export Word.

**AI action button** — teal or teal-outline. Used for controlled AI assistance. Examples: Suggest fallback clause, Generate memo, Compare to playbook.

### 9.3 Badge Rules

**Risk badges:** High = red · Medium = amber · Low = teal/green

**Workflow badges:** Draft, Legal Review, DPO Review, Approval, Signature, Completed, Blocked

**AI badges:** AI-assisted, Approved template, Playbook applied, Audit trail enabled, Governance controls active

### 9.4 Empty State Rules

Empty states should never feel dead.

**Bad:** "No items found."
**Better:** "No priority legal work is blocking the business. DocClad is still monitoring approvals, renewals, DPA reviews, and risk exceptions."

For demos and design previews, avoid all-zero dashboards — show active data.

## 10. AI Design Rules

The AI layer must feel powerful but governed.

**Use these phrases:** AI-assisted drafting · Based on approved playbook · Generated from approved clause library · Fallback clause available · Requires legal approval · Outside standard position · Audit trail enabled · Governance controls active

**Avoid these phrases:** "AI wrote this contract" · "Let AI decide" · "Fully automated legal advice" · "Instant legal answer" · "No review needed"

Every AI suggestion should show: source, reason, risk impact, approval impact, action, audit status.

Example:

> **Suggested fallback clause**
> Source: Approved DPA Clause Library
> Reason: Data transfer outside the EEA was selected.
> Risk impact: Medium
> Approval impact: DPO review required
> Action: Insert fallback clause

## 11. Screen State Rules

Every major screen needs these states:

| State | Meaning |
|---|---|
| Empty | No data yet, but clear next action |
| Healthy | Everything is under control |
| Active | Work is happening |
| Risk | Something needs review |
| Blocked | A person, approval, clause, or deadline is stopping progress |
| Completed | Workflow is done and final artifact is stored |

For design previews and demos, use active and risk states — that is where the product feels alive.

## 12. Implementation Sequence

**Phase 1 — Static UI Prototype.** Goal: make the flagship experience feel right before backend work. Build: New Contract page, DPA selected state, split-screen builder, static live DPA preview, static governance panel, static risk checks, static approval route. No real AI yet, no complex backend yet — just the experience.

**Phase 2 — Field-to-Document Mapping.** Make form fields update placeholders in the draft. Examples: Counterparty name → [Counterparty Name]; Effective date → [Effective Date]; Processing purpose → [Processing Purpose]; Data outside EEA → SCC risk block appears; Subprocessors yes → Subprocessor clause appears.

**Phase 3 — Workflow Instance Creation.** When the user clicks Generate governed draft, create: WorkflowInstance, DraftDocument, FieldValues, RiskSignals, ApprovalRoute, AuditEvents. Then show it in: Command Center Priority Queue, Contract Workspace, DPA Reviews, Approvals.

**Phase 4 — Command Center Redesign.** Make the dashboard workflow-driven. Show: active workflow instances, blocking approvals, DPA risks, renewal notice windows, drafts needing completion, recommended actions. Avoid all-zero cards.

**Phase 5 — Contract Workspace.** Create the single-contract command room. Include: document preview, workflow timeline, metadata, risks, approvals, comments, obligations, audit trail.

**Phase 6 — AI Layer.** Add real AI after the governed workflow works. Features: suggest fallback clause, generate review memo, explain clause, compare to playbook, detect missing terms, summarize contract, draft counterparty email. AI should always be tied to: template, playbook, clause library, risk rules.
