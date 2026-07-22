# Implementation authorization — PAR-ID-001 Slice 3 shadow role sync

**Programme:** PAR-ID-001  
**ADR:** ADR-0014 **Accepted**  
**Prerequisite:** PR [#54](https://github.com/Technivian/CLMOne/pull/54) merged to `main` @ `58966de7`  
**Request timestamp:** 2026-07-22T11:40:00Z  
**Status:** **Partial** — Product Approve recorded; Engineering and Security advisory votes still pending

---

## Motion — Authorize feature-flagged shadow synchronization

**Text:** Authorize feature-flagged shadow synchronization from selected legacy process-role writes into `ProcessRoleAssignment`, deterministic parity reporting, drift detection and audit evidence, management-command diagnostics, and staging activation — **without** making canonical assignments authoritative for permissions or runtime routing.

| Approver | GitHub identity | Governance capacity | Authority basis | Vote | Consent |
|---|---|---|---|---|---|
| Haroon Wahed | @haroonwahed | Product governance | CODEOWNERS `/docs/`; Charter v2.0 | **Approve** | Recorded 2026-07-22T13:02:57Z (verbatim below) |
| Technivian | @Technivian | Engineering governance | CODEOWNERS `/contracts/`; PDR-0003 | **Requested** | Pending |
| Security & privacy (advisory) | @Technivian | Security review capacity | SECURITY_PRIVACY_ACCESS_AND_AUDIT; Charter §7 | **Requested (advisory, with conditions)** | Pending |

**Result:** **Not yet authorized** — Engineering and Security advisory votes remain pending. Do not mark ready or merge until all required votes are recorded.

---

## Verbatim vote evidence

### Product — @haroonwahed (accepted)

Source: direct user-provided authorization text  
Received and recorded as provided:

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

Engineering and Security advisory votes from @Technivian remain pending and must be provided directly with their own ISO-8601 UTC timestamps and conditions.

After all required votes are recorded, the agent is authorized to:
1. Record the votes verbatim in SHADOW_ROLE_SYNC_IMPLEMENTATION_AUTHORIZATION.md.
2. Fix the pr-release-evidence checklist.
3. Re-run required CI checks.
4. Mark PR #55 ready for review only when authorization is complete and all required checks are green.

A separate explicit authorization is required before merging PR #55.
```

### Engineering — @Technivian

**Pending.** Must be provided directly with ISO-8601 UTC timestamp.

### Security advisory — @Technivian

**Pending.** Must be provided directly with ISO-8601 UTC timestamp, conditions text, conditions acknowledged, and non-authoritative confirmation.

---

## Requested scope

| Item | Requested |
|---|---|
| Feature flags `PROCESS_ROLE_SHADOW_WRITE_ENABLED`, `PROCESS_ROLE_PARITY_REPORTING_ENABLED` (default off) | **Yes** |
| Shadow sync from `UserProfile.role` writes into org-scoped `ProcessRoleAssignment` | **Yes** |
| Deterministic parity reporting command | **Yes** |
| Drift detection + audit evidence | **Yes** |
| Staging activation of flags | **Yes** |
| Management-command diagnostics | **Yes** |

---

## Explicitly excluded

| Item | Authorized |
|---|---|
| Production resolver flip | **No** |
| Permission or privilege changes | **No** |
| `OrganizationMembership` authority changes | **No** |
| `UserProfile.role` removal | **No** |
| Authorization-gate changes | **No** |
| Approval or signer resolver changes | **No** |
| Navigation changes | **No** |
| Workflow assignment cutover | **No** |
| PAR-APR-002 / PAR-WF-010 | **No** |
| PAR-ID-001 resolver-parity implementation | **No** |
| PR #55 merge (requires separate authorization) | **No** |

---

## Security advisory conditions (proposed until advisory vote)

1. Legacy `UserProfile.role` remains authoritative while flags are off or on.
2. Shadow failure must not roll back or corrupt the legacy write; fail closed on cross-tenant violations; audit `role.assignment.shadow_sync_failed`.
3. `profile_role` ADMIN → `legacy_process_admin` only; workspace ADMIN/OWNER/MEMBER never shadow-written as process roles.
4. Parity output must not drive authorization, approval, signer, or workflow routing.
5. Flags default **off** in all environments until staging activation is deliberate.

---

## Next slice (not requested here)

Production resolver dual-read consumption / privilege cutover — requires new authorization.
