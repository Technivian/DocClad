# CLM One Premium CLM Design Kit

Use this kit as the canonical design implementation brief for redesigning CLM One into a mature enterprise legal-tech / CLM platform.

The kit is meant to be pasted into the repository and used by a coding/design agent before touching page code.

Recommended repo location:

```text
/docs/design-system/clmone-premium-clm/
```

Core idea:

CLM One should feel like a legal operations command desk: calm, governed, precise, audit-ready, and production-grade. It should not feel like a flashy SaaS dashboard or generic admin template.

## Files

- `00_CANONICAL_AGENT_PROMPT.md` — paste this into the agent as the master instruction.
- `01_DESIGN_PRINCIPLES.md` — product feel, hierarchy, visual rules, anti-patterns.
- `02_DESIGN_TOKENS.css` — CSS variables for colors, spacing, radius, shadows, typography.
- `03_TAILWIND_THEME_SNIPPET.js` — optional Tailwind theme extension.
- `04_COMPONENT_SPECS.md` — shell, sidebar, top bar, cards, buttons, inputs, tables, workflow rail.
- `05_PAGE_BLUEPRINTS.md` — redesign instructions for Dashboard, New Contract, Contract Workspace, Repository, Tasks, Workflows, Approvals, Signature Requests, Risk Register, Compliance, Privacy, Audit Trail, DPA Reviews, Documents.
- `06_ROLLOUT_PLAN.md` — safe implementation order.
- `07_ACCEPTANCE_CHECKLIST.md` — page-level and system-level review checklist.
- `08_CODING_AGENT_TASK_PROMPT.md` — execution prompt for agents.

## Non-negotiable design posture

CLM One is not a colorful analytics cockpit. It is a serious CLM platform where legal, business, compliance, and audit work meet.

The work object is always the hero: contracts, approvals, signatures, reviews, risk, obligations, deadlines, and audit events.
