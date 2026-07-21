# CLM One UX, Navigation, and Work Surfaces

**Status:** Accepted  
**Purpose:** Define the canonical information architecture and user experience principles.

**Authority:** Accepted supporting documentation ([PDR-0003](../governance/decisions/pdr/PDR-0003-documentation-operating-model.md)). Does not supersede the active Governance Charter at [`../governance/GOVERNANCE_CHARTER.md`](../governance/GOVERNANCE_CHARTER.md). Charter v3 remains separately proposed.

## 1. Navigation model

### Workspace

- Command Center
- My Work
- Contracts

### Create

- New Contract

### Governance

- Reviews & Approvals
- Privacy Reviews
- Obligations

### Configuration

- Templates & Playbooks
- Workflow Designer
- Data Manager
- Entities
- Settings

Visibility is role-aware.

## 2. Surface responsibilities

### My Work

Only personal actionable work.

Must answer:

- what needs me;
- why;
- when;
- what action to take.

### Contracts

Complete accessible inventory.

Must distinguish:

- active workflow;
- completed workflow;
- imported record;
- active contract;
- expired or terminated contract.

### Command Center

Organization-wide operational and risk overview.

Must not become a personal queue.

### Specialist workspaces

Provide discipline-specific depth:

- review and approval;
- privacy;
- obligations.

### Settings

Configures workspace behavior.

Must not duplicate normal content-management navigation unless the card opens configuration, permissions, publishing rules, ownership, or defaults.

## 3. Contract Workspace

Recommended tabs:

- Overview
- Documents
- Review
- Approvals
- Privacy
- Signatures
- Obligations
- Relationships
- Activity

Tabs appear only when relevant and permitted.

The workspace must keep visible:

- contract identity;
- lifecycle state;
- owner;
- counterparty;
- due or effective date;
- blocking issues;
- next action.

## 4. Templates and Playbooks

Top-level areas:

- Clause Library
- Document Templates
- Workflow Templates
- Negotiation Playbooks
- Approval Policies

Each area must show operational metadata, not only a navigation card.

## 5. Workflow Designer

Canonical tabs:

- Design
- Test
- Versions
- Activity

Avoid duplicate actions and ambiguous state.

## 6. Status language

Use precise, action-oriented statuses.

Prefer:

- Awaiting your review
- Awaiting approval
- Returned for correction
- Blocked by missing signer
- Due today
- Overdue by 3 days

Avoid generic:

- Open
- Pending
- In progress

when a more specific state exists.

## 7. Page hierarchy

Each page should have:

1. clear title;
2. concise purpose or context;
3. state and status;
4. one primary action per context;
5. relevant content;
6. intentional empty, loading, and error states.

## 8. Empty states

An empty state must explain:

- what is empty;
- whether that is good, expected, or problematic;
- what the user can do next.

Do not use blank white space or duplicate sidebar buttons.

## 9. Enterprise visual principles

The product should feel:

- calm;
- dense enough to be useful;
- restrained;
- operational;
- trustworthy;
- consistent.

Avoid:

- decorative dashboard clutter;
- oversized cards with little information;
- unnecessary gradients;
- competing primary buttons;
- inconsistent avatars;
- terminology drift;
- native controls that visually break the system.

## 10. Accessibility

All core surfaces require:

- semantic structure;
- keyboard operation;
- visible focus;
- accessible labels;
- WCAG AA contrast;
- non-color status communication;
- minimum target sizes;
- screen-reader announcements for dynamic changes.

## 11. Responsive behavior

Desktop may use tables, side panels, and split views.

Tablet may collapse secondary detail.

Mobile must preserve the same task order and core actions, not simply shrink desktop layouts.
