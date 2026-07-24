# PAR-EXC-001 — Canonical read authority authorization

**Programme:** PAR-EXC-001  
**ADR:** ADR-0015 **Accepted**
**Prerequisites:** Default-off dual-write and its controlled-pilot observation
are complete; PR #78 monitoring remains read-only; legacy remains authoritative.
**Package type:** Non-production canonical-read authority
**Authorizing PR:** [#81](https://github.com/Technivian/CLMOne/pull/81)
**Flags enabled by this package:** **No**
**Production:** **OUT OF SCOPE**

## Evidence model

This package uses the repository evidence model in Governance Charter v2.3.
Its immutable reviewed SHA is the exact PR #81 head SHA bound to the approved
GitHub reviews and green CI; GitHub records that SHA with the reviews and merge
event. The operator record must repeat that deployed SHA. Do not copy approval
text, construct a vote table, or manually enter approval timestamps here.

Historical approval comments and historical vote records remain preserved in
GitHub and prior immutable commits; they are not rewritten by this package.

## Authorization readiness

Canonical authority is **not ready** until all of the following are true:

1. PR #81 has an approved GitHub review by the named Release Authority,
   `@haroonwahed`, or the single-maintainer bootstrap exception below is met.
2. CI is green for the reviewed PR #81 head SHA.
3. The default-off canonical-read implementation has merged to `main` and its
   immutable merge SHA is recorded by GitHub.
4. The implementation keeps all committed canonical-read defaults `false` and
   its allowlist empty.
5. The rollback drill is recorded for the named environment before enablement.
6. A named-environment operator record is ready to capture deployed SHA, CI
   run, flag values, counters, isolation/authorization results, abort events,
   and rollback outcome.

### PR #81 bootstrap exception

GitHub shows `@haroonwahed` as the sole direct human collaborator with
write/admin access and as PR #81's author, so independent GitHub approval is
unavailable. For this documentation-and-authorization PR only,
`@haroonwahed` may submit a GitHub owner attestation naming the exact final
PR #81 SHA and merge only while CI is green for that same SHA. The scope must
remain unchanged, rollback controls and audit evidence remain mandatory, and
this bootstrap exception expires when PR #81 merges. It authorizes neither
runtime canonical authority nor a feature-flag activation.

PR #81 must not be used to authorize enablement until all applicable readiness
gates above are met.

## Exact environment

| Field | Value |
|---|---|
| Named environment | `par-exc-001-canonical-read-authority` |
| Class | Non-production **staging-equivalent** only (local/controlled SQLite recreate) |
| Path | `docs/audits/evidence/2026-07-22-par-exc-001/canonical_read_env/` (DB gitignored; not committed) |
| Seed / corpus basis | Recreate from Motion 3 activation evidence patterns (`controlled-pilot-org` + non-allowlisted `demo-firm` negatives) |
| Production | **OUT OF SCOPE** |
| Remote shared staging URL | **Not identified** — not inferred |

## Exact scope

| In scope | Out of scope (hard) |
|---|---|
| Six Motion-2/3 source paths only: `KEEP_EXCEPTION`, `ACCEPTED_RISK`, `AI_EXCEPTION`, `CONFLICT_CHECK_WAIVER`, `DEADLINE_DEFER`, `DPA_APPROVE_WITH_BLOCKERS` | Any other exception-like path (break-glass, signature-provider, residuals) |
| Default-off dual-read / canonical-read flags + adapters (implementation gate before enablement) | Changing committed flag defaults in repo settings |
| For allowlisted org only: enforcement **may consult** canonical `ExceptionRequest` / `ExceptionDecision` applicability (`exception_is_applicable` / `privilege_granted`) as the **authoritative applicability read** when a correlated canonical row exists | Production activation |
| Legacy write paths remain in place; dual-write may remain enabled in the same named env for the same allowlist | Automatic repair / deletion / historical invention |
| Fail-closed on cross-tenant and Critical bypass without Security approval | Permission, privilege, membership, signer, approval, or navigation changes |
| Monitoring via existing `pilot_daily_health` `exception_dual_write` block + any additive metadata-only counters required for this window | ADMIN authority / ADMIN mapping |
| | Legacy retirement / removal of legacy fallback |
| | PAR-APR-002 / PAR-WF-010 / PAR-ID-002 |

## Exact allowlist and committed defaults

| Flag | Permitted operational value |
|---|---|
| `EXCEPTION_CANONICAL_READ_ENABLED` | `true` **only** in `par-exc-001-canonical-read-authority` after every readiness gate is met |
| `EXCEPTION_CANONICAL_READ_ORG_ALLOWLIST` | `controlled-pilot-org` **only** |
| `EXCEPTION_DUAL_WRITE_ENABLED` (prerequisite during observation) | `true` in the same named env only |
| `EXCEPTION_DUAL_WRITE_ORG_ALLOWLIST` | `controlled-pilot-org` **only** |

Committed defaults in `config/settings_base.py` and `config/settings_test.py`
remain **false** / empty. Global enablement without the allowlist is prohibited.

## Authority model

| Phase | Authority |
|---|---|
| Before enablement | Legacy remains authoritative; canonical rows non-authoritative |
| During authorized observation (allowlisted org + correlated canonical present) | Canonical applicability / privilege-token checks are **authoritative for read**; on canonical miss/failure → **legacy fallback** (fail-open to legacy product path except cross-tenant / Critical-gate fail-closed) |
| AI_EXCEPTION without decision | Remains **SUBMITTED**; must **not** become applicable via invented decision |
| After observation (default plan) | Return all canonical-read flags to **false** / empty; legacy resumes sole authority |
| Abort / rollback | Immediate flag-off; legacy sole authority; leave canonical rows in place (no repair) |

## Observation and operator record

The observation window is a single controlled named-environment session: the
six-path matrix, negative scenarios, monitoring stop-condition scan, and
rollback check. It is not a production watch.

The operator record must link to the GitHub-reviewed SHA and CI run, identify
the named environment, capture the four flag values before/during/after,
include the six-path, tenant-isolation, authorization, fallback and AI
`SUBMITTED` results, record metadata-only counters, and show the flag-off
restoration of legacy authority. Security may order an immediate stop.

## Abort conditions (immediate stop)

Disable `EXCEPTION_CANONICAL_READ_ENABLED` and clear
`EXCEPTION_CANONICAL_READ_ORG_ALLOWLIST` (and, if dual-write stop conditions
also fire, disable dual-write) on any of:

1. Cross-tenant anomaly or data exposure.
2. Unauthorized Critical bypass / Security-gate failure.
3. Invented historical decision or AI_EXCEPTION becoming applicable without authorized decision.
4. Duplicate canonical decision / duplicate correlation creating conflicting authority.
5. Missing owner or expiry on an approved/active temporary exception relied on for authority.
6. Privilege or permission expansion attributable to canonical read.
7. ADMIN authority or automatic ADMIN mapping.
8. User-visible regression attributable to canonical read.
9. Inability to restore legacy authority immediately via flag-off.
10. Material difference between reviewed and deployed HEAD.
11. Restricted content (credentials, contract body, unrestricted identity) appearing in monitoring evidence.
12. Security reviewer stop instruction.

A single tenant-isolation, Critical-control, or invented-authority violation is
a stop; aggregate percentages do not override it.

## Rollback

```bash
# In par-exc-001-canonical-read-authority only
export EXCEPTION_CANONICAL_READ_ENABLED=false
export EXCEPTION_CANONICAL_READ_ORG_ALLOWLIST=
# If dual-write stop also required:
export EXCEPTION_DUAL_WRITE_ENABLED=false
export EXCEPTION_DUAL_WRITE_ORG_ALLOWLIST=
```

1. Flag-off is non-destructive.
2. Leave canonical rows in place — **no** automatic repair or deletion.
3. Legacy paths become sole authority again.
4. Capture the stop-event audit evidence; do not invent remediation decisions.
5. Committed repository defaults remain unchanged.

## Completion and failure disposition

After a PASS, switch the canonical-read flags off, restore legacy authority,
and record the operator evidence before marking PAR-EXC-001 **Completed**. On
any failure, roll back immediately, retain PAR-EXC-001 as **In progress**, and
record the blocker. Neither outcome authorizes production, automatic repair,
permission changes, ADMIN authority, legacy retirement, or another PAR item.
