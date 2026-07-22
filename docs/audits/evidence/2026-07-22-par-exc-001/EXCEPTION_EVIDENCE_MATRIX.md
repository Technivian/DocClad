# PAR-EXC-001 — Exception evidence matrix

**Date:** 2026-07-22  
**Gap:** G-DOM-03 / CANONICAL_DOMAIN_MODEL §2.33  
**Legend:** Y = present · P = partial/weak · N = absent  

Columns: Src=source · R=reason · Sc=scope · Obj=affected object · Req=requester · Apr=approver · Auth=authority basis · Own=owner · SE=start/expiry · CC=compensating controls · St=status · Ren=renewal · Cl=closure · AE=audit evidence · TB=tenant boundary

## Central finding

| Question | Answer |
|---|---|
| Unified Exception/Waiver model before this slice? | **No** |
| Central exception service before this slice? | **No** |
| Governance doc template only? | `docs/governance/decisions/exceptions/EXCEPTION_TEMPLATE.md` (process; not runtime) |

---

## Product / policy exceptions

| ID | Source | Behavior | R | Sc | Obj | Req | Apr | Auth | Own | SE | CC | St | Ren | Cl | AE | TB | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| EXC-POL-001 | `drafting_workspace_actions.drafting_exception_action` `keep_exception` | Keeps RiskSignal open; audits reason+owner; **no Exception object** | Y | N | Y | Y | N | N | Y | N | N | N | N | N | Y | Y | Soft acceptance; no expiry |
| EXC-POL-002 | same `use_approved_wording` / `accept_fallback` | Resolves RiskSignal | P | N | Y | Y | N | N | N | N | N | Y | N | Y | Y | Y | Resolution ≠ Exception |
| EXC-POL-003 | same `request_approval` | Audits approval request; **no ApprovalRequest** | P | N | Y | Y | N | N | N | N | N | N | N | N | Y | Y | Illusory route |
| EXC-POL-004 | same `add_comment` | Comment on exception trail | P | N | Y | Y | N | N | N | N | N | N | N | N | Y | Y | Commentary |
| EXC-POL-005 | `dpa_review.dpa_risk_item_set_status` → `ACCEPTED_RISK` | Accepted risk disposition | P | N | Y | Y | N | N | P | N | N | Y | N | P | Y | Y | Primary accepted-risk path |
| EXC-POL-006 | DPA dispositions FP/RESOLVED/NEEDS_*/ESCALATED | Non-exception dispositions | P | N | Y | Y | N | N | P | N | N | Y | N | P | Y | Y | |
| EXC-POL-007 | `documents_ai` `create_exception` | Finding → `EXCEPTION_REQUESTED` + ApprovalRequest to **owner** | P | N | Y | Y | P | N | N | N | N | Y | N | N | Y | Y | SoD risk (owner assignee) |
| EXC-POL-008 | finding dismiss `ACCEPTED_BUSINESS_RISK` / `APPROVED_EXCEPTION` | Dismiss citing exception/risk | Y* | N | Y | Y | N | N | N | N | N | Y | N | Y | Y | Y | *reason for HIGH/CRITICAL |
| EXC-POL-009 | `ConflictCheck.Status.WAIVED` | Conflict waiver status | P | N | Y | P | P | N | N | N | N | Y | N | P | P | P | Real waiver vocab; weak fields |
| EXC-POL-010 | `DPAPlaybookPosition` org override | Org playbook overrides global | N | Y | Y | N | N | N | P | N | N | N | N | N | N | Y | Config, not time-boxed |
| EXC-POL-011 | UX “document accepted risk” copy | Guidance only | N | N | N | N | N | N | N | N | N | N | N | N | N | N | Maps to keep/accept |

## Workflow / approval

| ID | Source | Behavior | R | Sc | Obj | Req | Apr | Auth | Own | SE | CC | St | Ren | Cl | AE | TB | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| EXC-WF-001 | RiskSignal open exceptions gate submit | Open signals block submit | N | N | Y | N | N | N | N | N | N | Y | N | Y | P | Y | Exception = open signal |
| EXC-WF-002 | drafting submit `enforce_review_readiness=False` | Skips readiness assert | N | Y | Y | Y | N | N | N | N | N | N | N | N | Y | Y | Builder bypass |
| EXC-WF-003 | repository `exception_only` filter | Title-heuristic filter | N | N | P | N | N | N | N | N | N | N | N | N | N | Y | Display only |
| EXC-APR-001 | `dpa_review_set_approval_status` | Can APPROVE with open blockers | P | N | Y | Y | Y | N | N | N | N | Y | N | Y | Y | Y | **Approve-with-blockers** |
| EXC-APR-002 | SoD `authorize_approval_actor` | Blocks self-approval | — | — | — | — | — | — | — | — | — | — | — | — | Y | Y | Control (not exception) |
| EXC-APR-003 | `ApprovalWorkflowService.delegate` | Temporary delegate + optional end | Y | P | Y | Y | Y | N | Y | P | N | Y | N | P | Y | Y | Delegation ≠ Exception |
| EXC-APR-004 | `FINANCE_APPROVAL_THRESHOLD` | Global threshold override | N | Y | N | N | N | N | N | N | N | N | N | N | N | N | Settings override |

## Deadlines

| ID | Source | Behavior | R | Sc | Obj | Req | Apr | Auth | Own | SE | CC | St | Ren | Cl | AE | TB | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| EXC-DL-001 | `deadlines.deadline_defer` | +7 days; **no reason required** | N | N | Y | Y | N | N | N | N | N | N | N | N | Y | Y | Unlimited loops |

## Security / platform break-glass

| ID | Source | Behavior | R | Sc | Obj | Req | Apr | Auth | Own | SE | CC | St | Ren | Cl | AE | TB | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| EXC-SEC-001 | `ALLOW_SQLITE_IN_PRODUCTION` | Emergency non-Postgres | N* | Y | N | N | N* | N* | N* | N* | N | N | N | N | P | N | **Critical**; process not code-gated |
| EXC-SEC-002 | `ALLOW_EPHEMERAL_MEDIA_IN_PRODUCTION` | Historical media bypass | — | — | — | — | — | — | — | — | — | — | — | — | — | — | **Removed** from code |
| EXC-SEC-003 | `ALLOW_REMOTE_DATABASE` | Non-local DB opt-in | N | Y | N | N | N | N | N | N | N | N | N | N | P | N | Footgun |
| EXC-SEC-004 | `ALLOW_REMOTE_TEST_DB` | Test DB safety bypass | N | Y | N | N | N | N | N | N | N | N | N | N | N | N | |
| EXC-SEC-005 | `RATELIMIT_ENABLED=false` / trusted IPs | Auth rate-limit bypass | N | Y | N | N | N | N | N | N | N | N | N | N | N | N | |
| EXC-SEC-006 | `SECURITY_HEADERS_ENABLED=false` | Headers off | N | Y | N | N | N | N | N | N | N | N | N | N | N | N | |
| EXC-SEC-007 | cache `IGNORE_EXCEPTIONS=True` | Swallows Redis errors | N | Y | N | N | N | N | N | N | N | N | N | N | N | N | |
| EXC-SEC-008 | MFA route exemptions | Narrow MFA exemptions | N | Y | N | N | N | N | N | N | N | N | N | N | N | N | Necessary |
| EXC-SEC-009 | MFA recovery codes | Break-glass MFA | N | N | Y | Y | N | N | N | N | N | N | N | Y | Y | Y | Single-use |
| EXC-SEC-010 | `@csrf_exempt` webhooks | CSRF bypass | N | Y | N | N | N | N | N | N | N | N | N | N | N | N | Expected for providers |
| EXC-SEC-011 | historical `cms.audit_bypass` | Would allow audit mutate | — | — | — | — | — | — | — | — | — | — | — | — | — | — | Removed; reverse migrates Critical |

## Administrative / repair / flags

| ID | Source | Behavior | R | Sc | Obj | Req | Apr | Auth | Own | SE | CC | St | Ren | Cl | AE | TB | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| EXC-ADM-001 | lifecycle `system=True` | Skips authz + transition graph | P | N | Y | N/P | N | N | N | N | N | Y | N | N | Y | P | **Critical** lifecycle skip |
| EXC-ADM-002 | AI review state applicator `system=True` | Privileged lifecycle writes | P | N | Y | Y | N | N | N | N | N | Y | N | N | Y | Y | |
| EXC-ADM-003 | `Contract.save(skip_lifecycle_validation=True)` | Skips status/stage pair check | N | N | Y | N | N | N | N | N | N | N | N | N | N | N | Repair/migration |
| EXC-ADM-004 | `CONTROLLED_PILOT_ENABLED` | Scope lock / unlock | N | Y | N | N | N | N | N | N | N | N | N | N | P | N | |
| EXC-ADM-005 | billing/trust/AI feature flags | Domain kill-switches | N | Y | N | N | N | N | N | N | N | N | N | N | N | N | |
| EXC-FLG-001 | `PROCESS_ROLE_CANONICAL_RESOLVER_*` | Org-allowlisted resolver cutover | N | Y | Y | N | N | P | N | N | N | N | N | N | Y | Y | Default off |
| EXC-FLG-002 | shadow/parity diagnostics flags | Non-authoritative diagnostics | N | Y | N | N | N | N | N | N | N | N | N | N | Y | Y | |
| EXC-REP-001 | `repair_contract_provenance` | Staff/admin provenance repair | Y | N | Y | Y | N | P | N | N | N | N | N | Y | Y | Y | Staff cross-tenant risk |
| EXC-REP-002 | `allow_provenance_mutation` | Unlock for assign/repair | Y | N | Y | Y | N | N | N | N | N | N | N | N | Y | Y | |
| EXC-REP-003 | `repair_contract_type_catalogue` | Type binding repair | Y | N | Y | Y | N | P | N | N | N | N | N | Y | Y | Y | |
| EXC-REP-004 | role/PRA repair | System-managed row repair | Y | N | Y | Y | N | P | N | N | N | Y | N | P | Y | Y | |
| EXC-REP-005 | `skip_authz=True` identity services | Authz skip for seeds/sync | N | N | Y | N | N | N | N | N | N | N | N | N | Y | P | Dangerous if leaked |
| EXC-REP-006 | `skip_version_immutability` | Document version unlock | N | N | Y | N | N | N | N | N | N | N | N | N | P | Y | |
| EXC-REP-007 | role immutability skips | Create-time only | N | N | Y | N | N | N | N | N | N | N | N | N | Y | Y | |

## Signature / other

| ID | Source | Behavior | R | Sc | Obj | Req | Apr | Auth | Own | SE | CC | St | Ren | Cl | AE | TB | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| EXC-SIG-001 | signature transition `enforce_actor=False` | Provider/webhook skip actor | N | N | Y | N | N | N | N | N | N | Y | N | N | Y | Y | Must stay non-user |
| EXC-SIG-002 | signature packet cancel | Operational void | P | N | Y | Y | N | N | N | N | N | Y | N | Y | Y | Y | Not policy Exception |
| EXC-OTH-001 | design-system script exceptions | CSS enforcement skips | N | Y | N | N | N | N | N | N | N | N | N | N | N | N | Tooling |
| EXC-OTH-002 | `EXCEPTION_TEMPLATE.md` | Markdown exception record | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Process-only |
| EXC-OTH-003 | work-health “reopen deferred” UX | Ops language only | N | N | N | N | N | N | N | N | N | N | N | N | N | N | |

---

## Priority cutover candidates (product Exception §2.33)

1. EXC-POL-001 / EXC-POL-005 / EXC-POL-007 / EXC-POL-008 / EXC-POL-009  
2. EXC-DL-001  
3. EXC-APR-001 (approve-with-blockers → require ExceptionDecision)

## Platform break-glass (document; do not collapse into product Exception without Security ADR)

EXC-ADM-*, EXC-SEC-*, EXC-REP-*, EXC-FLG-* — may use the same schema with `category=SECURITY|ADMINISTRATIVE|REPAIR|FEATURE_FLAG` and `bypasses_critical_security_control=True` where applicable, but production wiring requires separate Security approval.
