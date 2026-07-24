# PDR-0004: GitHub review and release evidence

**Status:** Proposed
**Date:** 2026-07-23
**Owner:** Repository steward
**Affected Charter sections:** Charter §16
**Related ADRs:** ADR-0015 (unchanged authority scope)

## Problem

Editable vote tables and copied approval statements duplicate, rather than
preserve, the immutable evidence available on GitHub. They are susceptible to
drift and do not bind an approval to the final reviewed commit.

## Decision

Use GitHub submitted PR reviews, CI results, immutable reviewed and merged
SHAs, and operator or release records as repository authorization evidence.
Active templates link to that evidence and do not contain manual approval
tables or manually entered approval timestamps.

The gate is proportional to risk:

- low-risk default-off work requires green CI and normal PR review;
- non-production canonical authority requires the named GitHub Release
  Authority (`@haroonwahed`) to approve the current PR SHA, green CI,
  reversible default-off flags, documented abort/rollback controls, and an
  operator record;
- production activation, permission or privilege changes, automatic repair,
  ADMIN authority, and legacy retirement require Product, Engineering, and
  Security PR approval that is independent across the three capacities, plus
  green CI and a release record.

This decision does not change runtime authorization, product permissions,
domain authority, or the requirement that feature flags are exposure controls
only.

## Historical record handling

Preserve existing historical records, including the PR #78 premature-merge
incident and correction trail. Do not retroactively create approval evidence
or edit historical records to match the new prospective model.

## Consequences and trade-offs

Auditors consult the linked GitHub PR and release/operator record rather than
a copied approval block. A head change can invalidate stale reviews, making
the reviewed SHA explicit and reducing evidence drift.

## Acceptance criteria

- Active governance and agent instructions identify GitHub review-and-release
  evidence as authoritative.
- New templates have no manual approval table or approval timestamp field.
- Canonical-authority and production gates are explicit and testable.
- Historical evidence is retained unchanged.

## Approval

The Governance Charter v2.1 supplies the active rule. This proposed PDR
documents the operating model and does not independently authorize a runtime
or release action.
