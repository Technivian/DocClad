# Governance authorization template

**Status:** Not ready | Ready | Executed | Rolled back
**Authorizing PR:**
**Scope:**
**Runtime / migration / permission / authority change:** None unless the
applicable GitHub review-and-release gate is satisfied.

## Required evidence

State the applicable gate from Governance Charter v2.1. Link the authorizing
PR, its required GitHub reviews, CI results, and immutable reviewed SHA. Do
not add a manual approval table, copied approval text, or manually entered
approval timestamp.

## Scope and exclusions

State the exact environment, data/tenant allowlist, paths, conditions,
exclusions, and non-starts. A feature flag does not grant authority.

## Preconditions

List the conditions that must be satisfied before implementation or execution.
For canonical authority, include default-off/reversible flags, an operator
record, and the exact rollback check.

## Operator or release record

Link the operator or release record. It must identify the reviewed/deployed
SHA and CI run, record the environment, relevant flag state, validation and
counter results, abort events, and rollback result.

## Rollback

Describe how to reverse the authorized change. For a documentation-only
change, use a follow-up documentation PR and preserve historical evidence.
