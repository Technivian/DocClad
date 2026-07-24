# GitHub governance vote evidence guidance

**Status:** Active — accepted through
[`PDR-0004`](decisions/pdr/PDR-0004-github-vote-evidence.md)

**Scope:** New governance motions, authorization packages, decision records,
and PR reviews.

**Out of scope:** Runtime audit timestamps, platform audit events, historical
record rewriting, and any authorization or execution decision.

For the separate low-risk merge path while the repository has one active
maintainer, see
[`SOLO_MAINTAINER_STANDING_AUTHORIZATION.md`](SOLO_MAINTAINER_STANDING_AUTHORIZATION.md).
That authorization does not validate a missing vote or reduce the stronger
controls required for authority, activation, privilege, migration, or security
control changes.

## Rule

PDR-0004 discontinues manual UTC timestamp entry for governance votes. The
genuine GitHub comment or review that contains the vote is the authoritative
evidence; GitHub's system-generated `created_at` is
the authoritative audit timestamp. It may be retrieved for audit, but
approvers must not type or calculate it.

Vote tables use this form:

| Approver | Capacity | Vote | Evidence |
|---|---|---|---|
| | | | |

Each Evidence cell links directly to the genuine GitHub comment or review.

## Valid vote requirements

A valid vote contains:

1. approver identity, established by the GitHub author of the evidence;
2. governance capacity;
3. an explicit vote;
4. a reviewed commit, merge SHA, motion, ADR, PDR, or decision reference; and
5. explicit conditions when applicable.

Do not accept timestamps supplied without a genuine vote, proxy votes,
generated timestamps, inferred votes, or a vote copied by another person
without direct approver evidence.

## Vote text for a GitHub comment or review

~~~
APPROVE — <motion name>

Capacity: <Product governance | Engineering governance | Security advisory>
Reviewed reference: <commit SHA, merge SHA, ADR, PDR, or motion>
Vote: <Approve | Approve with conditions | Reject>
Conditions: <conditions or None>
~~~

Do not include a timestamp field. A motion may add a required acknowledgement
line (for example, a Security condition list) without changing this rule.

## Historical record handling

- Do not rewrite genuine historical GitHub timestamps.
- Preserve the PR #78 premature-merge incident and its correction trail.
- Keep invented Engineering and Security timestamps retracted.
- Do not retroactively validate missing votes.
- Existing historical records may retain genuine timestamps already recorded;
  all new votes use the evidence-link model.

## Charter and audit alignment

This guidance preserves intentional, traceable material decisions and
immutable audit evidence. It does not remove approval dates or effective dates
where a Charter amendment or accepted decision requires them; those dates must
be traceable to authoritative evidence. It changes manual vote-timestamp
administration only, not platform audit timestamps.

## Rollback

If PDR-0004 is superseded, restore or replace the applicable template language
in a follow-up docs-only change; do not alter historical records.
