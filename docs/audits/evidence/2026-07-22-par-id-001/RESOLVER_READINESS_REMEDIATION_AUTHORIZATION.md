# Implementation authorization — PAR-ID-001 resolver-readiness remediation

**Programme:** PAR-ID-001  
**ADR:** ADR-0014 **Accepted**  
**Prerequisite:** PR [#58](https://github.com/Technivian/CLMOne/pull/58) merged to `main` @ `598b7a128cb8d0f5be0c7cd2fb1880f631ca9608`; staging evidence PR [#60](https://github.com/Technivian/CLMOne/pull/60)  
**Baseline staging evidence:** [`STAGING_RESOLVER_PARITY_RESULTS.md`](STAGING_RESOLVER_PARITY_RESULTS.md) (pre-remediation: MATCH 9 / AMBIGUOUS 13 / INACTIVE 14 / LEGACY_ONLY 1 / critical 0)  
**Review package timestamp:** 2026-07-22T15:13:34Z  
**Status:** **Requested** — awaiting recorded Product, Engineering, and Security-advisory votes. Votes must not be invented.

**Related evidence:**
- [`STAGING_RESOLVER_PARITY_RESULTS.md`](STAGING_RESOLVER_PARITY_RESULTS.md)
- [`PROCESS_ROLE_MAPPING_MATRIX.md`](PROCESS_ROLE_MAPPING_MATRIX.md)
- [`RESOLVER_PARITY_IMPLEMENTATION_AUTHORIZATION.md`](RESOLVER_PARITY_IMPLEMENTATION_AUTHORIZATION.md)

---

## Motion — Authorize staging-equivalent resolver-readiness remediation

**Text:** Authorize creation or activation of truthful canonical `ProcessRoleAssignment` rows for controlled-pilot organizations only; correction of seed and staging assignment gaps; companion-organization assignment setup; parity rerun; formal exclusion of profile-role ADMIN from the first cutover scope; and a focused threat review. Canonical resolver remains non-authoritative. No privilege, permission, membership, navigation, approval, or signer behaviour changes. No automatic production repair. No enabling of a canonical authority flag.

| Approver | GitHub identity | Governance capacity | Authority basis | Vote | Consent |
|---|---|---|---|---|---|
| Haroon Wahed | @haroonwahed | Product governance | CODEOWNERS `/docs/`; Charter v2.0 | **Requested** | — |
| Technivian | @Technivian | Engineering governance | CODEOWNERS `/contracts/`; PDR-0003 | **Requested** | — |
| Security & privacy (advisory) | @Technivian | Security review capacity | SECURITY_PRIVACY_ACCESS_AND_AUDIT; Charter §7 | **Requested** | — |

**Result:** **Not yet Authorized** until the three votes above are recorded verbatim with ISO-8601 UTC timestamps.

**Programme note:** Staging-equivalent controlled-pilot remediation and evidence updates on this branch proceed as directed by the PAR-ID-001 remediation task while formal votes remain Requested. Production assignment repair remains out of scope.

---

## Exact approved scope (when votes are recorded)

1. Create or **activate** truthful canonical `ProcessRoleAssignment` rows for:
   - `controlled-pilot-org`
   - `controlled-pilot-org-b`
2. Correct seed / staging assignment gaps that cause `INACTIVE_ASSIGNMENT` or `LEGACY_ONLY` under CERTAIN mappings only.
3. Companion-organization assignment setup (targeted; not a blind clone of primary-org assignments).
4. Rerun resolver-parity diagnostics with the three diagnostic flags enabled in staging-equivalent scope only.
5. Record formal exclusion of `profile_role` / `ADMIN` → `legacy_process_admin` from first cutover scope (accepted exclusion; do not reclassify as MATCH).
6. Complete focused threat review for a future cutover authorization package.

## Explicitly excluded

- Resolver authority changes / dual-return / `PROCESS_ROLE_CANONICAL_RESOLVER_ENABLED`
- Permission changes
- Privilege changes
- Membership-role changes
- `UserProfile.role` removal
- Automatic production repair
- Navigation changes
- Approval or signer behaviour changes
- Creating assignments for AMBIGUOUS roles (including ADMIN)
- PAR-APR-002 / PAR-WF-010

---

## Security conditions (binding when Security votes)

1. Remediation limited to controlled-pilot staging-equivalent organizations named above.
2. Only CERTAIN mappings may receive create/activate remediation.
3. AMBIGUOUS ADMIN remains explicit; never map workspace ADMIN to process ADMIN.
4. Preserve actor, source, reason, and correlation ID on governed assignment events.
5. Diagnostic and audit payloads remain permission-safe (no credentials, contract content, or unrestricted identity dumps).
6. No production auto-repair; no resolver logic change unless a proven diagnostic defect is evidenced.
7. Canonical results must not influence production runtime decisions.

---

## Vote templates (do not invent)

### Product — @haroonwahed

```text
@haroonwahed Product: Approve | Reject | Abstain
Timestamp: YYYY-MM-DDTHH:MM:SSZ

Conditions acknowledged: yes|no
Staging-only remediation: yes|no
ADMIN first-cutover exclusion: yes|no
Canonical authority remains off: yes|no
```

### Engineering — @Technivian

```text
@Technivian Engineering: Approve | Reject | Abstain
Timestamp: YYYY-MM-DDTHH:MM:SSZ
```

### Security advisory — @Technivian

```text
@Technivian Security advisory: Approve | Approve with conditions | Reject | Abstain
Timestamp: YYYY-MM-DDTHH:MM:SSZ

Conditions acknowledged: yes|no
```

---

## Deliverables of this slice

| Artifact | Purpose |
|---|---|
| [`INACTIVE_ASSIGNMENT_REMEDIATION.md`](INACTIVE_ASSIGNMENT_REMEDIATION.md) | Before / remediation / after for inactive gaps |
| Companion LEGACY_ONLY section (same or staging results) | `controlled-pilot-org-b` CERTAIN assignment |
| Mapping / cutover scope updates | ADMIN accepted exclusion |
| [`RESOLVER_CUTOVER_THREAT_REVIEW.md`](RESOLVER_CUTOVER_THREAT_REVIEW.md) | Focused threat review |
| Updated [`STAGING_RESOLVER_PARITY_RESULTS.md`](STAGING_RESOLVER_PARITY_RESULTS.md) | Post-remediation counts |
| [`CANONICAL_RESOLVER_CUTOVER_AUTHORIZATION.md`](CANONICAL_RESOLVER_CUTOVER_AUTHORIZATION.md) | Only if readiness thresholds pass (votes Requested) |

---

## Stop condition

Keep PAR-ID-001 **In progress**.  
Stop before canonical resolver results influence production decisions.
