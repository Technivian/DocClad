# Canonical Agent Prompt — CLM One Premium CLM Redesign

You are redesigning CLM One into a premium enterprise legal-tech / contract lifecycle management platform.

Use the existing product structure and domain model. Do not invent decorative dashboards or unrelated features. Redesign the UI around legal work objects: contract requests, contracts, approvals, signatures, repository records, DPA reviews, risks, compliance controls, privacy records, tasks, workflows, deadlines, and audit events.

## Product character

CLM One must feel:

- calm
- mature
- trustworthy
- production-ready
- enterprise-grade
- audit-ready
- precise
- legal-operational

CLM One must not feel:

- flashy
- startup-gimmicky
- dashboard-template-like
- overly colorful
- consumer-ish
- analytics-first
- visually crowded

## Visual system

Use:

- deep navy for the app shell and sidebar
- refined CLM One teal for active, workflow, trusted, compliance, focus, and completed states
- restrained burnt orange only for primary creation/action buttons
- off-white / cool light-gray page background
- white cards with subtle borders
- minimal shadow
- crisp enterprise typography
- thin consistent icons
- restrained status chips

Do not use:

- rainbow status colors
- loud gradients
- decorative charts
- fake analytics
- oversized KPI tiles
- dense admin-template boxes
- unnecessary icons
- marketing-style hero sections inside the app

## Structural baseline

Every core page should use the same app shell:

- dark navy left sidebar
- top bar with search, firm selector, utility icons, user/avatar menu, and primary action
- page header with title, subtitle, and contextual actions
- main work area
- optional right-side guidance column when it helps workflow clarity

## UX rule

Every screen must answer one of these questions:

1. What requires my attention?
2. What stage is this contract/work item in?
3. What is the risk or compliance state?
4. What action can I take next?
5. What evidence/audit trail supports this?

If a UI element does not help answer one of those questions, remove or demote it.

## Implementation instruction

Before editing pages, create or align reusable components:

- `AppShell`
- `SidebarNav`
- `TopBar`
- `PageHeader`
- `ActionButton`
- `SecondaryButton`
- `StatusChip`
- `WorkflowRail`
- `Card`
- `SectionHeader`
- `FormField`
- `SelectField`
- `DataTable`
- `RightRailCard`
- `EmptyState`
- `AuditEventList`

Then redesign pages using these components. Avoid one-off styles.
