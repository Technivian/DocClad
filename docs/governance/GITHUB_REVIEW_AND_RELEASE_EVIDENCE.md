# GitHub review and release evidence

**Status:** Active — Governance Charter v2.4
**Scope:** New authorization packages, decision records, releases, and PRs.
**Historical evidence:** Preserved; this rule is prospective.

## Authoritative evidence

GitHub submitted PR reviews, CI results, immutable reviewed and merged SHAs,
and the required deployment or operator record are authoritative. Active
documents may link to that evidence but must not duplicate it in a manually
maintained approval table, copied approval statement, or manually entered
approval timestamp.

## Gates

- Low-risk default-off work requires green CI and normal PR review.
- Non-production canonical authority requires approval by the named GitHub
  Release Authority, **@haroonwahed**, green CI for the unchanged reviewed
  SHA, reversible default-off flags, documented abort and rollback controls,
  and a named-environment operator record.
- Where GitHub shows exactly one direct human collaborator with push or admin
  access, independent review is unavailable. For a non-production,
  reversible, default-off change only, the repository owner may submit a
  GitHub owner attestation naming the exact immutable head SHA instead. CI
  must be green for that SHA, the reviewed scope must be unchanged, abort and
  rollback controls and an operator record remain required, and all flags must
  return off after observation. This exception never authorizes production,
  permission or privilege changes, automatic repair, ADMIN authority, or
  legacy retirement; those actions still require independent Product,
  Engineering, and Security approvals.
- Production activation, permission or privilege changes, automatic repair,
  ADMIN authority, and legacy retirement require approved Product,
  Engineering, and Security GitHub reviews that are independent of one
  another, green CI, and a release record.

The required reviewer roles must be requested and verified through GitHub.
Every required review applies to the immutable PR head SHA shown by GitHub;
changing that head requires the required reviews and CI to be current again.
An owner attestation is likewise valid only for the exact SHA it names.

## Pilot Hardening bootstrap — PAR-SEC-002

`@haroonwahed` is the named Programme, Product, Engineering, and Security
owner for PAR-SEC-002. The repository owner declares this account to be the
sole direct human collaborator with admin access; GitHub confirms its admin
permission.

Until an independent direct human reviewer is available, an exact-SHA GitHub
owner attestation may be used for only these scopes:

- planning-only documentation;
- tests-and-evidence-only work; and
- committed-default-off, content-free observational instrumentation that is a
  pass-through while off.

The attestation must identify the immutable head SHA, required CI must be
green for that unchanged SHA, and the PR must remain within one of those
scopes. It cannot authorize any runtime authorization or result-visibility
change, permission or authority change, filtering, migration, production
change, repair, ADMIN authority, canonical-read cutover, or legacy retirement.
If observation is later executed, the applicable operator record, abort, and
rollback requirements still apply. Feature flags never grant authority.

## Operator and release records

An operator record links to the reviewed/deployed SHA and CI run, identifies
the environment, records relevant default-off flag values and rollback result,
and captures only the required test, counter, audit, and stop-condition
evidence. A release record provides the equivalent production evidence.

## Historical records

Do not rewrite historical approval records, timestamps, the PR #78
premature-merge incident, or its correction trail. The new model does not
retroactively validate, invalidate, or fill gaps in earlier evidence.

## Feature flags

Flags control exposure only. They never grant authority or replace a required
review, CI result, operator record, or release record.
