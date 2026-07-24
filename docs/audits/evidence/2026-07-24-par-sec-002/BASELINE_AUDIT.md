# PAR-SEC-002 baseline audit — uniform authorization for search, analytics, and AI

**Baseline:** `main` at `9378ca21ffe71cf78f89f8c0bbfb9ebb164f1b3a`  
**Programme:** Pilot Hardening  
**PAR status:** In progress — verified baseline; implementation unstarted  
**Scope:** Documentation and evidence only. No runtime code, migration, flag,
permission, authority, repair, production, canonical-cutover, or
legacy-retirement change is authorized by this audit.

## Objective and release boundary

PAR-SEC-002 closes the gap-audit findings that search, analytics, and AI must
apply the same server-side tenant and permission rules as primary contract
access, and that hidden controls must never be relied on as authorization.

The active governance and security architecture require workspace membership,
role/permission checks, object-level access, and no restricted metadata leakage
through search, analytics, notifications, exports, or AI. This baseline does
not assert that a new authorization model has been selected or approved.

Named programme, Product, Engineering, and Security owners are **not recorded
for this PAR** in the current roadmap or accepted governance records examined.
They remain a delivery blocker; no owner is inferred from repository access,
historic PRs, or the named Release Authority.

For a future default-off, reversible implementation, normal review and green
CI are required. Any non-production canonical authority, production activation,
permission/privilege change, automatic repair, ADMIN authority, or legacy
retirement remains governed by its applicable separate gate; no feature flag
grants that authority.

## Verified route and control inventory

| Surface | Current server-side control | Classification | Evidence / residual |
|---|---|---|---|
| Global repository search (`/contracts/search/`) | Login plus `get_scoped_queryset_for_request`, which scopes to the active organization | Partial | Cross-tenant contract/client and semantic-clause tests pass. The scope helper is tenant-only; it does not evaluate `EthicalWall` or a restricted-record policy. |
| Contract search, clause search, and facets APIs | Login plus `get_user_organization`; service query filters by `organization` | Partial | Tenant filtering is explicit in `contracts/services/search_api.py`; no object-level filter is applied before records or facet counts are returned. |
| Search telemetry API | Login plus active-organization filter | Partial | Any active organization member can receive the latest 50 raw query strings for that organization. There is no verified minimization, actor restriction, or role gate. |
| Executive analytics API | Login plus active-organization snapshot | Partial | Tenant-scoped aggregation is tested. The read endpoint has no `can_manage_organization` or object-policy check; preset mutation does require owner/admin. |
| Clause analytics APIs | Login plus active-organization service queries | Partial | Tenant filters are present; object-level and low-privilege response tests are absent. |
| Work operating metrics API | Login, active organization, and `can_manage_organization` | Completed for its manager gate | This is a useful comparison path; it does not establish the policy for other analytics endpoints. |
| Contract AI extraction, suggestions, drafts, and recommendations | Contract lookup scoped to organization; `can_access_contract_action`; organization AI policy; provider check when needed | Partial | `ContractAction.AI` currently returns true for every active organization member. Cross-tenant extraction is tested; restricted-record/ethical-wall context exclusion is not. |
| Internal contract AI assistant | Login, organization-scoped contract lookup, `can_access_contract_action(..., COMMENT)`, prompt policy, and audit/activity records | Partial | Cross-tenant and action-execution member-denial tests exist. `COMMENT` currently permits every active organization member; no Ethical-Wall check is applied. |
| AI provider containment | `GEMINI_AI_ENABLED` defaults false without a key; controlled-pilot middleware blocks listed AI paths when pilot mode is enabled and AI is off | Completed as containment, not authorization | This is a kill switch and provider safeguard only. It neither selects an object-level policy nor grants authority. |
| Ethical Wall domain data | `EthicalWall` stores organization, client/matter, restricted users, active state, and expiry | Missing enforcement | The inventoried search, analytics, and AI paths do not reference `EthicalWall`; behavior for contract/client/matter overlap requires a separate policy decision. |

`contracts/permissions.py` verifies active organization membership. Its current
`VIEW`, `COMMENT`, and `AI` actions return true for any active member; only
`EDIT` differentiates owner/admin from the accountable user. That is sufficient
for the verified tenant boundary, but not evidence of the required uniform
object-level restriction boundary.

## Requirement classification

| Requirement | Status | Verified basis or blocker |
|---|---|---|
| Authenticated entry to inventoried routes | Completed | `login_required` or equivalent is present on the inventoried endpoints. |
| Active-organization / cross-tenant isolation | Partial | Query scoping and 75-route cross-tenant suite exist; the focused baseline includes those tests. Inventory lacks coverage for every PAR-SEC-002 API. |
| Consistent object-level read authorization | Missing | No accepted/readable policy defines access to active Ethical Walls, confidential records, aggregates, facets, telemetry, or AI context. |
| Search-result and metadata non-leakage | Partial | Tenant-only filtering works; object-restricted rows, result counts, facets, autocomplete, and query telemetry are not covered by a common policy. |
| Analytics read authorization | Partial | Organization scoping exists. Executive and clause analytics have no verified role/object filter. |
| AI context authorization | Partial | Tenant lookup, organization AI policy, default-disabled provider, and prompt safeguards exist; membership-only `AI`/`COMMENT` gates do not prove restricted-context exclusion. |
| Client hiding never substitutes for server checks | Partial | Controlled-pilot middleware denies several direct paths. A route-by-route server-check matrix has not been established. |
| Content-free denied-attempt logging | Missing | Middleware logs path and reason without bodies/content, but no dedicated PAR-SEC-002 denial/audit evidence covers every surface. |
| Default-off and reversible first slice | Missing | No PAR-SEC-002 flag or observation seam exists; the proposed first slice below is deliberately non-authoritative. |
| Migration | Not required | The first safe slice is tests/evidence and, if needed, an in-process observational seam only. |
| Canonical read, production, repair, privilege, ADMIN, or legacy retirement | Not required | Explicitly outside this PAR initiation and unchanged. |

## Current risks and baseline defects

1. **High — restricted metadata exposure risk.** Tenant-scoped records,
   aggregates, facets, and raw telemetry are not yet shown to apply an
   object-level/ethical-wall policy. The evidence does not establish an actual
   cross-tenant leak; it establishes that required restricted-record behavior is
   unimplemented or unproven.
2. **High — policy ambiguity.** `EthicalWall` is a stored domain object but no
   accepted interpretation exists for a direct contract, related client, or
   matter in these read paths. Enforcing a guessed interpretation would be a
   privilege change and is not authorized.
3. **Medium — aggregate and telemetry disclosure.** Executive and clause
   analytics are organization-scoped but not consistently manager-gated;
   telemetry returns raw searches across the organization. Required audience,
   retention, minimization, and redaction rules need proof before any change.
4. **Medium — route coverage gap.** Current tests prove selected global-search,
   extraction, assistant, and tenant cases, not a full search/analytics/AI
   route-by-role matrix.
5. **Baseline test failure, unrelated to this audit.** Focused baseline run:
   159/160 passing. `AIClauseReviewWorkflowTests.test_incomplete_review_is_truthful_and_surfaces_resolvable_blockers` expects the text `Contract type` on the incomplete review page. The clean baseline response lacks it. This docs-only audit does not change that template or test and does not attribute the failure to PAR-SEC-002.

## Validation performed

| Check | Result |
|---|---|
| `python manage.py check` | Pass — no issues. |
| `python manage.py audit_null_organizations` (after local migrations) | Pass — no NULL organization rows. |
| Focused authorization baseline: cross-tenant, permission matrix, search, clause search, executive analytics, clause analytics, AI clause review, and AI assistant tests | 159/160 passed; the single unrelated baseline UI assertion is documented above. |
| Static route/control and Ethical Wall reference inventory | Completed; results recorded in this document. |

## Proposed phases and smallest safe slice

1. **Baseline characterization — completed in this record.** Inventory routes,
   gates, data returned, and missing policy tests without changing behavior.
2. **Policy decision — blocked.** Name the owners and accept a product/security
   decision defining object-level read eligibility, Ethical-Wall relation rules,
   aggregate/facet semantics, telemetry audience/minimization, and AI-context
   eligibility. This is required before enforcement.
3. **First implementation slice — proposed, default-off and reversible.** Add
   only a test/evidence authorization matrix and an optional internal
   observation seam that computes no new entitlement and does not filter,
   deny, expose, or persist contract content. With its control disabled it must
   be a strict pass-through; it must emit aggregate, content-free coverage
   counters only. Do not add a migration, change a permission, enable a flag,
   alter dual-write, or change authority. The slice is safe because it measures
   the gap rather than selecting a policy.
4. **Enforcement design and staging validation — blocked pending phase 2 and
   separate authorization.** Apply a shared policy before search results,
   facets, analytics, telemetry, or AI context; prove deny behavior, rollback,
   and content-free logs.
5. **Production release — out of scope.** Requires the applicable independent
   approvals, green CI, a release record, and operational evidence.

Likely first-slice files are
`tests/test_par_sec_002_authorization_baseline.py`, this evidence directory,
and the roadmap. If an observation seam is separately approved, its candidate
locations are `contracts/permissions.py` and narrowly scoped adapters in
`contracts/services/search_api.py`, `contracts/api/analytics.py`,
`contracts/api/documents_ai.py`, and
`contracts/views_domains/repository_management.py`; no such code is changed
by this audit.

Required first-slice evidence: authenticated, unauthenticated, cross-tenant,
low-privilege, restricted-user, aggregate/facet, telemetry, and AI-context
matrix results; content-free denial-log assertions; default-off proof;
rollback proof; `manage.py check`; null-organization audit; and the required
CI status for the exact reviewed SHA.

## Stop conditions

Stop rather than infer a policy if ownership remains unassigned; an Ethical
Wall relation cannot be evaluated deterministically; a proposed control changes
visible results, permissions, or authority while default-off; a test reveals
restricted metadata in a denial path; or the existing baseline failure changes
without a causal link to the proposed slice.
