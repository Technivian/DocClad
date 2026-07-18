# Contract-detail visual-baseline drift decision

Date: 2026-07-18  
Decision: **non-reproducible harness variance; baseline retained unchanged.**

## Evidence

An earlier full-suite run reported 6,053 changed pixels (1%) for the detail
baseline. No snapshot was updated. Replaying only the same detail test against
the deterministic fresh E2E server at `127.0.0.1:8010` passed twice in
succession, using the unchanged snapshot and the same 1440 × 1000 viewport.

The failure therefore does not reproduce as a stable rendering change. It is
not classified as an intended change, defect, or product regression. The
likely source is non-deterministic test/harness state during the earlier
multi-page run; this is an evidence-based operational classification, not a
claim of pixel equivalence under arbitrary fixture state.

## Follow-up

- Keep the existing detail snapshot; it was not regenerated or overwritten.
- Run the detail visual test against the fresh E2E seed path in CI.
- Reopen triage if two deterministic replays fail or if a component change
  produces a stable image delta.
