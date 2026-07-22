# Implementation authorization — PAR-ID-001 Slice 3 shadow role sync

**Programme:** PAR-ID-001  
**ADR:** ADR-0014 **Accepted**  
**Prerequisite:** PR [#54](https://github.com/Technivian/CLMOne/pull/54) merged to `main` @ `58966de7`  
**Request timestamp:** 2026-07-22T11:40:00Z  
**Authorization complete timestamp:** 2026-07-22T13:15:23Z  
**Status:** **Authorized and merged** — Product, Engineering, and Security advisory implementation votes recorded; merge votes recorded; merge commit `bb881ac2`

---

## Motion — Authorize feature-flagged shadow synchronization

**Text:** Authorize feature-flagged shadow synchronization from selected legacy process-role writes into `ProcessRoleAssignment`, deterministic parity reporting, drift detection and audit evidence, management-command diagnostics, and staging activation — **without** making canonical assignments authoritative for permissions or runtime routing.

| Approver | GitHub identity | Governance capacity | Authority basis | Vote | Consent |
|---|---|---|---|---|---|
| Haroon Wahed | @haroonwahed | Product governance | CODEOWNERS `/docs/`; Charter v2.0 | **Approve** | Recorded 2026-07-22T13:02:57Z (verbatim below) |
| Technivian | @Technivian | Engineering governance | CODEOWNERS `/contracts/`; PDR-0003 | **Approve** | Recorded 2026-07-22T13:13:23Z (verbatim below) |
| Security & privacy (advisory) | @Technivian | Security review capacity | SECURITY_PRIVACY_ACCESS_AND_AUDIT; Charter §7 | **Approve with conditions** | Recorded 2026-07-22T13:15:23Z (verbatim below) |

**Result:** **Authorized** for the requested non-authoritative shadow-sync slice. Merge authorization recorded below. **Does not authorize** resolver-parity implementation or flag activation.

---

## Merge authorization (PR #55)

**PR:** [#55](https://github.com/Technivian/CLMOne/pull/55)  
**Reviewed HEAD:** `432a55b1c2c12af7ae6fedf17a8b4bcfda61f525`  
**Merge commit:** `bb881ac233d2f499547d504bcd29f3d4d5e872db`  
**Merged at:** `2026-07-22T13:35:32Z`

| Approver | Vote | Timestamp |
|---|---|---|
| @haroonwahed Product | **Approve merge** | `2026-07-22T13:36:50Z` |
| @Technivian Engineering | **Approve merge** | `2026-07-22T15:15:23Z` |

### Verbatim Product merge authorization

```text
@haroonwahed Product: Approve merge
Timestamp: 2026-07-22T13:36:50Z

Merge authorization confirms:
- Implementation authorization remains in force
- Security conditions 1–9 remain binding
- Slice remains non-authoritative
- PROCESS_ROLE_SHADOW_WRITE_ENABLED remains default off after merge
- PROCESS_ROLE_PARITY_REPORTING_ENABLED remains default off after merge
- No production resolver cutover
- No permission, privilege, membership-authority, or navigation changes
- No PAR-ID-001 resolver-parity implementation in this merge
- Staging flag enablement requires separate explicit activation authorization
```

### Verbatim Engineering merge authorization

```text
@Technivian Engineering: Approve merge
Timestamp: 2026-07-22T15:15:23Z
```

**Post-merge constraints (binding):** flags remain default off; do not enable shadow/parity flags; do not start resolver-parity without new authorization.

---

## Verbatim vote evidence

### Product — @haroonwahed (accepted)

Source: direct user-provided authorization text  
Timestamp: `2026-07-22T13:02:57Z`

```text
SHADOW ROLE SYNC IMPLEMENTATION AUTHORIZATION — 2026-07-22

PR: #55
Branch: cursor/feat-par-id-001-shadow-role-sync
HEAD: ecf5cf3a

@haroonwahed Product: Approve
Timestamp: 2026-07-22T13:02:57Z

Approved scope:
- Shadow role synchronization
- Parity reporting
- Audit and evidence updates
- Tests
- Roadmap updates

Conditions acknowledged: yes
Slice remains non-authoritative: yes
Feature flags remain default off: yes

This approval does not authorize:
- Production resolver cutover
- Permission or privilege changes
- Membership-authority changes
- Navigation behaviour changes
- PAR-ID-001 resolver-parity implementation
- PR merge
```

### Engineering — @Technivian (accepted)

Source: direct user-provided authorization text  
Timestamp: `2026-07-22T13:13:23Z`

```text
@Technivian Engineering: Approve
Timestamp: 2026-07-22T13:13:23Z

Engineering confirms that the approved slice is limited to:
- Shadow role synchronization
- Parity reporting
- Audit and evidence updates
- Automated tests
- Roadmap updates

Engineering conditions acknowledged: yes
Slice remains non-authoritative: yes
Feature flags remain default off: yes
```

### Security advisory — @Technivian (accepted)

Source: direct user-provided authorization text  
Timestamp: `2026-07-22T13:15:23Z`

```text
@Technivian Security advisory: Approve with conditions
Timestamp: 2026-07-22T13:15:23Z

Security conditions:

1. Shadow role data must not influence production authorization, permissions, memberships, navigation, assignment resolution, or runtime behaviour.
2. PROCESS_ROLE_SHADOW_WRITE_ENABLED and PROCESS_ROLE_PARITY_REPORTING_ENABLED must remain disabled by default.
3. Shadow writes and parity reporting must remain tenant-scoped and permission-safe.
4. No restricted role, membership, or organization metadata may leak through logs, reports, exports, errors, metrics, or audit summaries.
5. Parity output must be diagnostic only and must not automatically repair or overwrite authoritative role data.
6. Enabling either feature flag must be explicit, reversible, auditable, and limited to an approved environment or workspace.
7. Any parity mismatch must be recorded without changing authoritative production state.
8. Resolver cutover requires a separate authorization, threat review, test matrix, and rollback plan.
9. This approval does not authorize merging PR #55.

Conditions acknowledged: yes
Slice remains non-authoritative: yes
Feature flags remain default off: yes
```

Combined closing exclusions from the Engineering/Security authorization package (also recorded):

```text
This authorization does not approve:
- Production resolver cutover
- Permission or privilege changes
- Membership-authority changes
- Navigation behaviour changes
- Automatic parity repair
- PAR-ID-001 resolver-parity implementation
- PR merge
```

---

## Authorized scope

| Item | Authorized |
|---|---|
| Feature flags `PROCESS_ROLE_SHADOW_WRITE_ENABLED`, `PROCESS_ROLE_PARITY_REPORTING_ENABLED` (default off) | **Yes** |
| Shadow sync from `UserProfile.role` writes into org-scoped `ProcessRoleAssignment` | **Yes** |
| Deterministic parity reporting command | **Yes** |
| Drift detection + audit evidence | **Yes** |
| Staging activation of flags (explicit, reversible, auditable) | **Yes** |
| Management-command diagnostics | **Yes** |
| Automated tests + roadmap updates | **Yes** |

---

## Explicitly excluded

| Item | Authorized |
|---|---|
| Production resolver flip / cutover | **No** |
| Permission or privilege changes | **No** |
| `OrganizationMembership` authority changes | **No** |
| `UserProfile.role` removal | **No** |
| Authorization-gate changes | **No** |
| Approval or signer resolver changes | **No** |
| Navigation changes | **No** |
| Workflow assignment cutover | **No** |
| Automatic parity repair | **No** |
| PAR-ID-001 resolver-parity implementation | **No** |
| PAR-APR-002 / PAR-WF-010 | **No** |
| Staging flag activation (requires separate activation authorization) | **No** |

---

## Security advisory conditions (binding)

1. Shadow role data must not influence production authorization, permissions, memberships, navigation, assignment resolution, or runtime behaviour.
2. `PROCESS_ROLE_SHADOW_WRITE_ENABLED` and `PROCESS_ROLE_PARITY_REPORTING_ENABLED` must remain disabled by default.
3. Shadow writes and parity reporting must remain tenant-scoped and permission-safe.
4. No restricted role, membership, or organization metadata may leak through logs, reports, exports, errors, metrics, or audit summaries.
5. Parity output must be diagnostic only and must not automatically repair or overwrite authoritative role data.
6. Enabling either feature flag must be explicit, reversible, auditable, and limited to an approved environment or workspace.
7. Any parity mismatch must be recorded without changing authoritative production state.
8. Resolver cutover requires a separate authorization, threat review, test matrix, and rollback plan.
9. This approval does not authorize merging PR #55.

---

## Next slice (not authorized here)

Feature-flagged production resolver dual-read comparison / privilege cutover — requires new authorization. Stop before canonical output influences any production decision.
