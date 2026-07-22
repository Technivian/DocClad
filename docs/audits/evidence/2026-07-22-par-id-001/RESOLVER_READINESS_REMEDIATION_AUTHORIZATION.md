# Implementation authorization — PAR-ID-001 resolver-readiness remediation

**Programme:** PAR-ID-001  
**ADR:** ADR-0014 **Accepted**  
**Prerequisite:** PR [#58](https://github.com/Technivian/CLMOne/pull/58) merged to `main` @ `598b7a128cb8d0f5be0c7cd2fb1880f631ca9608`; staging evidence PR [#60](https://github.com/Technivian/CLMOne/pull/60)  
**Baseline staging evidence:** [`STAGING_RESOLVER_PARITY_RESULTS.md`](STAGING_RESOLVER_PARITY_RESULTS.md)  
**Review package timestamp:** 2026-07-22T15:13:34Z  
**Authorization complete timestamp:** 2026-07-22T15:29:09Z  
**Status:** **Authorized** — Product, Engineering, and Security-advisory votes recorded from direct user-provided text (timestamps below).

**Related evidence:**
- [`STAGING_RESOLVER_PARITY_RESULTS.md`](STAGING_RESOLVER_PARITY_RESULTS.md)
- [`PROCESS_ROLE_MAPPING_MATRIX.md`](PROCESS_ROLE_MAPPING_MATRIX.md)
- [`CANONICAL_RESOLVER_CUTOVER_AUTHORIZATION.md`](CANONICAL_RESOLVER_CUTOVER_AUTHORIZATION.md)

---

## Motion — Authorize staging-equivalent resolver-readiness remediation

**Text:** Authorize creation or activation of truthful canonical `ProcessRoleAssignment` rows for controlled-pilot organizations only; correction of seed and staging assignment gaps; companion-organization assignment setup; parity rerun; formal exclusion of profile-role ADMIN from the first cutover scope; and a focused threat review. Canonical resolver remains non-authoritative until a separately authorized authority flag is implemented and later activated. No privilege, permission, membership, navigation, approval, or signer behaviour changes. No automatic production repair.

| Approver | GitHub identity | Governance capacity | Authority basis | Vote | Consent |
|---|---|---|---|---|---|
| Haroon Wahed | @haroonwahed | Product governance | CODEOWNERS `/docs/`; Charter v2.0 | **Approve** | Recorded 2026-07-22T15:27:09Z |
| Technivian | @Technivian | Engineering governance | CODEOWNERS `/contracts/`; PDR-0003 | **Approve** | Recorded 2026-07-22T15:28:09Z |
| Security & privacy (advisory) | @Technivian | Security review capacity | SECURITY_PRIVACY_ACCESS_AND_AUDIT; Charter §7 | **Approve with conditions** | Recorded 2026-07-22T15:29:09Z |

**Result:** **Authorized** for remediation scope and (with the paired cutover package) default-off canonical authority **implementation**.  
**Does not authorize activation** of `PROCESS_ROLE_CANONICAL_RESOLVER_ENABLED` in staging or production.

### Implementation vs activation

| Decision | Status |
|---|---|
| Implementation authorization (default-off mechanism + remediation retention) | **Authorized** by votes below |
| Activation authorization (enable flag in any environment) | **Not authorized** — separate package/votes required |

---

## Verbatim recorded votes (authoritative)

Source: direct user-provided authorization text (2026-07-22). Combined motion covering this file and `CANONICAL_RESOLVER_CUTOVER_AUTHORIZATION.md`.

### Product — @haroonwahed (accepted)

```text
APPROVE — PAR-ID-001 Resolver Readiness Remediation and Canonical Resolver Implementation

Approver: @haroonwahed
Capacity: Product governance
Vote: Approve
Timestamp: 2026-07-22T15:27:09Z

I approve:

1. RESOLVER_READINESS_REMEDIATION_AUTHORIZATION.md
2. CANONICAL_RESOLVER_CUTOVER_AUTHORIZATION.md

Authorized scope:

- retain the completed staging readiness remediation;
- implement PROCESS_ROLE_CANONICAL_RESOLVER_ENABLED;
- keep the new authority flag default off;
- limit canonical authority to the approved non-ADMIN process roles and resolver paths;
- preserve the legacy resolver as fallback;
- preserve the recorded ADMIN exclusions;
- prepare the separate activation package.

This vote authorizes implementation of the default-off cutover mechanism only.

This vote does not authorize enabling canonical resolver authority in staging or production. Activation requires a separate governance vote after implementation, testing, rollback verification, and review.
```

### Engineering — @Technivian (accepted)

```text
APPROVE — PAR-ID-001 Resolver Readiness Remediation and Canonical Resolver Implementation

Approver: @Technivian
Capacity: Engineering governance
Vote: Approve
Timestamp: 2026-07-22T15:28:09Z

Engineering approves:

1. RESOLVER_READINESS_REMEDIATION_AUTHORIZATION.md
2. CANONICAL_RESOLVER_CUTOVER_AUTHORIZATION.md

Authorized implementation:

- add PROCESS_ROLE_CANONICAL_RESOLVER_ENABLED with default false;
- implement canonical resolution only for approved resolver paths;
- retain legacy resolution when the flag is off;
- retain legacy fallback for missing, inactive, excluded, ambiguous, or failed canonical resolution;
- keep profile ADMIN and workspace OWNER, ADMIN, and MEMBER outside the first cutover;
- retain diagnostic, audit, monitoring, and rollback controls.

Conditions:

- no permission or membership-authority changes;
- no UserProfile.role removal;
- no unrelated workflow, approval, signer, navigation, or privilege changes;
- no migration of ambiguous ADMIN semantics;
- no activation during this implementation slice;
- disabling the authority flag must restore legacy resolution immediately.

This vote authorizes implementation only. Activation requires a separate recorded vote.
```

### Security advisory — @Technivian (accepted)

```text
APPROVE WITH CONDITIONS — PAR-ID-001 Resolver Readiness Remediation and Canonical Resolver Implementation

Approver: @Technivian
Capacity: Security advisory
Vote: Approve with conditions
Timestamp: 2026-07-22T15:29:09Z

Security approves:

1. RESOLVER_READINESS_REMEDIATION_AUTHORIZATION.md
2. CANONICAL_RESOLVER_CUTOVER_AUTHORIZATION.md

Binding conditions:

- PROCESS_ROLE_CANONICAL_RESOLVER_ENABLED defaults off;
- canonical authority is limited to explicitly approved non-ADMIN process roles;
- profile ADMIN remains excluded and legacy-authoritative;
- workspace OWNER, ADMIN, and MEMBER must never become process-role targets;
- organization and active-assignment consistency must be verified before canonical use;
- cross-tenant anomalies fail closed and emit a security event;
- fallback must never cross tenant boundaries;
- diagnostic and authority evidence must not expose restricted identities, role payloads, credentials, or contract content;
- legacy fallback remains available;
- rollback by disabling the flag must be tested;
- no automatic repair or privilege expansion;
- activation requires a separate Product, Engineering, and Security decision.

This vote authorizes default-off implementation only. It does not authorize staging or production activation.
```

---

## Exact approved remediation scope

1. Create or **activate** truthful canonical `ProcessRoleAssignment` rows for controlled-pilot orgs.
2. Correct CERTAIN seed / staging gaps (`INACTIVE_ASSIGNMENT` / `LEGACY_ONLY`).
3. Companion-organization assignment setup (targeted).
4. Parity rerun with diagnostic flags in staging-equivalent only.
5. ADMIN first-cutover exclusion (accepted exclusion; not MATCH).
6. Focused threat review.

## Explicitly excluded from remediation-only authority

- Enabling `PROCESS_ROLE_CANONICAL_RESOLVER_ENABLED` (activation)
- Permission / privilege / membership / navigation changes
- `UserProfile.role` removal
- Automatic production repair
- PAR-APR-002 / PAR-WF-010
