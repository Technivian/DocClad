# Contract-form visual-baseline drift decision

Date: 2026-07-18  
Decision: **obsolete baseline** — replace the active form snapshot after this
decision is recorded; retain this document as the evidence trail.

## Evidence

1. The preserved Phase 1 form test was replayed on a fresh, deterministic E2E
   database at `127.0.0.1:8010`, with a 1440 × 1000 viewport. It differed by
   18,849 pixels (2%). The dashboard, repository-list, and workspace
   baselines passed in the same run.
2. The current form’s desktop geometry is correct and stable: the
   `.cform-stepper-head` computed to `781px 338px`, and
   `.cform-command-stats` occupied `x=1061…1399`, matching the intended
   right-aligned command-status block. The reported difference is primarily
   rendered text, not a layout displacement.
3. The current dirty working tree contains substantial post-baseline contract
   intake changes outside the Phase 2A button/badge work: governed intake
   fields, labels, copy, route/readiness content, and lifecycle presentation
   in `theme/templates/contracts/contract_form.html`, with corresponding form
   and model changes. The snapshot therefore represents a superseded contract
   intake state rather than the current route’s approved content.
4. The current detail baseline also differs (6,053 pixels / 1%) in the same
   replay. It is not part of this decision and remains preserved for separate
   triage; it was not updated here.

## Classification rationale

This is not an intended Phase 2A visual change: that phase added canonical
button/badge API classes and compatibility adapters only. It is not a
reproducible rendering defect: a fresh seeded server renders the command
header at the expected desktop geometry. It is also not attributable to the
button/badge adapter because the differences include current intake content
that predates and lies outside that work.

The active form baseline is therefore obsolete. It must be regenerated only
from the deterministic E2E server after this decision, while the Phase 1
snapshot and this record remain the historical comparison evidence.

## Follow-up

- Regenerate the active form snapshot now; do not change the form template or
  layout to satisfy an obsolete rendering.
- Keep the detail baseline failing and triage it separately before any
  replacement.
- Future visual snapshots must use the fresh E2E seed path, not a long-running
  development server with unknown fixture state.
