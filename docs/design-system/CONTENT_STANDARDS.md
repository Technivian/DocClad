# Content Standards

## Voice

Calm, precise, and operational. Prefer direct verbs and concrete legal objects.
Do not use hype, jokes, or anthropomorphic AI language.

## Labels

- Buttons use verbs: `Import document`, `Send for approval`, `Resolve risk`.
- Pages and navigation use nouns: `Repository`, `Approvals`, `Obligations`.
- Status uses concise state: `Draft`, `Waiting on Finance`, `Signed`.
- Avoid database terminology such as `object`, `record type`, or raw enums.

## Dates And Numbers

- Display dates in a consistent localized format.
- Add relative urgency only when it helps prioritization.
- Use ISO dates in exports and machine-readable interfaces.
- Use tabular numerals and explicit currencies.
- Never abbreviate a financial value when precision affects a decision.

## Errors

Use: `The approval could not be submitted. Refresh the contract and try again.`

Avoid: `Something went wrong.` or raw exception details.

## AI

Use: `AI-assisted suggestion`, `Compare with playbook`, `Requires legal review`.

Avoid: `AI knows`, `magic`, `instant legal answer`, or claims that remove human
accountability.

## Empty States

State the condition and the next valid action. Do not describe the visual
layout or instruct users to locate controls by position.
