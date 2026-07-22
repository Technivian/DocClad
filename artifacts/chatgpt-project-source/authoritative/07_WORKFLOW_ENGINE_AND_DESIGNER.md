# CLM One Workflow Engine and Designer

**Status:** Accepted  
**Purpose:** Define the workflow configuration and execution model.

**Authority:** Accepted supporting documentation ([PDR-0003](../governance/decisions/pdr/PDR-0003-documentation-operating-model.md)). Does not supersede the active Governance Charter at [`../governance/GOVERNANCE_CHARTER.md`](../governance/GOVERNANCE_CHARTER.md). Charter v3 remains separately proposed.

## 1. Workflow Designer is a configuration engine

The visual canvas is only one representation.

Workflow Designer must configure:

- intake forms;
- internal forms;
- external forms;
- documents;
- participants;
- roles;
- access;
- conditions;
- review steps;
- approvals;
- privacy reviews;
- signatures;
- archival;
- obligations;
- integration actions;
- notifications;
- SLAs;
- escalations.

## 2. Version model

### Workflow Definition

Stable identity and metadata.

### Draft Workflow Version

Editable, testable, and unpublished.

### Published Workflow Version

Immutable and available for launch.

### Superseded Workflow Version

No longer default for new launches, but still authoritative for existing instances.

### Archived Workflow Version

Retained for audit but not launchable.

## 3. Publication lifecycle

1. Create draft.
2. Configure.
3. Run validation.
4. Resolve blocking issues.
5. Test required scenarios.
6. Review change summary.
7. Approve publication if policy requires it.
8. Publish immutable version.
9. Record audit events.
10. Make version available according to effective-date rules.

## 4. Validation

### Blocking

Prevents publication.

Examples:

- missing required assignee;
- missing signer;
- unreachable completion;
- invalid condition;
- missing document mapping;
- missing approval authority;
- deleted property reference;
- invalid integration dependency.

### Warning

Allows publication with acknowledgement.

Examples:

- no fallback branch;
- unusually long SLA;
- no reminder;
- optional metadata not mapped.

### Information

Improvement or explanation only.

## 5. Step model

Supported step categories:

- Start
- Intake
- Document generation
- Upload
- Task
- Directed question
- Review
- Privacy review
- Approval
- Condition
- Parallel branch
- Wait
- Integration action
- Signature
- Archive
- Obligation creation
- Completion
- Cancellation

Each step must define:

- stable step ID;
- type;
- name;
- description;
- entry condition;
- assignment;
- SLA;
- escalation;
- access implications;
- output;
- validation rules;
- audit behavior.

## 6. Conditions

Conditions may evaluate approved canonical properties and runtime facts.

Conditions must be:

- deterministic;
- testable;
- versioned;
- explainable;
- auditable.

Avoid arbitrary code expressions in customer configuration.

## 7. Assignment resolution

Assignments may resolve to:

- named user;
- group;
- workflow role;
- property-selected person;
- entity contact;
- manager chain;
- delegated user;
- fallback group.

Every resolution must record why that assignee was selected.

## 8. Approval validity

An Approval Decision must reference:

- document version or contract state;
- approval requirement;
- approver;
- authority basis;
- timestamp;
- decision;
- comments;
- delegation if used.

Material changes may reset approval according to policy.

## 9. Testing and simulation

Workflow testing must support:

- named scenarios;
- draft and historical versions;
- form input;
- property input;
- assignment resolution;
- branch trace;
- skipped steps;
- SLA outcome;
- issue detection;
- mocked integrations;
- expected versus actual result.

Simulation must never create live contracts.

Required pre-publication test packs may be configured per workflow.

## 10. Runtime safety

A live Workflow Instance always continues against the version it launched from unless an explicit governed migration is approved.

New workflow versions affect only new launches by default.

## 11. Restoration

Restoring a historical version creates a new draft derived from that version.

The platform must record:

- source version;
- reason;
- actor;
- timestamp;
- migration impact;
- resulting draft.

## 12. Designer UX

The Designer should expose:

- Design
- Test
- Versions
- Activity

The interface must always make visible:

- version;
- lifecycle state;
- validation state;
- read-only or editable state;
- active issue count;
- primary next action.

## 13. Minimum audit events

- definition created;
- draft created;
- step added;
- step changed;
- condition changed;
- assignment changed;
- validation run;
- simulation run;
- version published;
- version superseded;
- restoration initiated;
- archive performed;
- export performed.
