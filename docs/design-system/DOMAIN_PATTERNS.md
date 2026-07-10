# Domain Patterns

DocClad components encode contract operations, not generic SaaS labels.

## Workflow State

Use one normalized lifecycle vocabulary in user-facing UI:

`Intake -> Draft -> Review -> Approval -> Signature -> Active -> Renewal -> Closed`

Product-specific stages may appear as supporting detail. Never expose raw enum
values, model names, or internal transition codes.

## Risk

Every risk signal needs:

- Severity: low, medium, high, or critical.
- Reason: the detected condition in plain language.
- Source: document clause, playbook rule, metadata, or deadline.
- Owner: person or team accountable for resolution.
- Recommended action.
- Status and audit history.

Risk colors: low/accepted uses neutral or forest, medium uses amber, high and
critical use oxide red. Red is reserved for a real exception or block.

## Approval

Approval cards show the decision, the approver, the trigger reason, the route,
and the time impact. Avoid unexplained `Approve` buttons. Example:
`Finance approval required because contract value exceeds EUR 250,000.`

## AI Assistance

AI output is always attributable and reviewable. Distinguish:

- Approved clause library language.
- Playbook fallback language.
- External counterparty text.
- AI suggestion requiring review.

Use `AI-assisted`, not `AI-generated from scratch`. Show evidence, confidence,
and the next review action when they affect a decision.

## Obligations And Dates

Dates show the absolute date and, where useful, a relative urgency label.
Obligations show owner, source clause, due date, recurrence, and health. Renewal
and notice windows are attention states, not destructive states.

## Audit

Audit history is chronological evidence. Each item identifies actor, action,
object, timestamp, and material change. Audit records are never styled as chat.
