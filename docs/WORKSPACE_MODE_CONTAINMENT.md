# Workspace-Mode Containment (Phase 5 of the Product Coherence Redesign)

`Organization.workspace_mode` (`law_firm_ops` / `in_house_clm`) changes only
the views where each operating model needs distinct content: Matter detail and
Risk Review. The Command Center and primary navigation are intentionally
shared. This note documents that boundary so future mode-aware changes do not
reintroduce incidental branching.

Enforced by [`tests/test_workspace_mode_containment.py`](../tests/test_workspace_mode_containment.py).
That file is the living contract — if a route's classification changes, the
test for it must change in the same commit.

## Policy: shared shell vs mode-specific content

Two, and only two, legitimate shapes for a mode-aware page:

1. **Shared / mode-neutral** — one route, one template, no branching at all.
   The content is equally correct for both tenant types (a document
   repository, a counterparty list). Default to this shape; only leave it
   if the content is genuinely tenant-type-specific.
2. **Shared shell, mode-specific content** — one route, one template,
   internally branching on `workspace_mode` (never on anything else — no
   plan tier, no feature flag, no org name heuristic). The gate must be a
   single `is_in_house_clm` boolean computed once (a `cached_property` on
   class-based views, a local at the top of function-based views) and
   passed to the template — never re-derived per section. `law_firm_ops`
   behavior in the `else` branch must be provably unchanged from before the
   branch was introduced (a preservation test is mandatory, see below).

What is **not** a legitimate shape: removing a mode gate so both tenant
types see identical content "for now." If a page's content should converge,
that's a product decision made explicitly, not a side effect of a
refactor — see the Bucket B correction below.

## Route classification

| Route | URL name | Classification | Notes |
|---|---|---|---|
| Nav sidebar | `nav_config.get_nav_for` | Shared / mode-neutral | One standard primary navigation for both modes. It exposes only the current core surface; secondary routes remain reachable by direct URL. |
| Dashboard | `dashboard` | Shared / mode-neutral | Command Center is the standard dashboard for every organization. It has no `workspace_mode` branch. |
| Matter detail | `contracts:matter_detail` | Shared shell, mode-specific content | `MatterDetailView.get_context_data` branches once; `matter_detail.html` renders the Matter Workspace Spine for `in_house_clm`, the original billing/time-entry layout otherwise. |
| Risk Review | `contracts:risk_log_list` / `risk_log_list_legacy` | Shared shell, mode-specific content | `RiskLogListView` picks `legal_intelligence_hub.html` vs `risk_log_list.html` via `get_template_names()`, short-circuiting the unused query path entirely rather than computing-then-discarding it. |
| Org security settings | `organization_security_settings` | Shared / mode-neutral, with a mode **selector** | Not content-per-mode — it's the admin control that sets `workspace_mode` itself (`actions.py::organization_security_settings`, the `save_workspace_mode` action). No change needed. |
| Repository | `contracts:repository` | Shared / mode-neutral | Tenant-scoped, domain-neutral. No workspace_mode reference anywhere in the view or template. |
| Counterparties | `contracts:counterparty_list` | Shared / mode-neutral | Same reasoning. |
| DPA Reviews | `contracts:dpa_review_pack_list` | Shared / mode-neutral | DPA review is a general compliance primitive, not law-firm-exclusive. |
| Approvals | `contracts:approval_request_list` | Shared / mode-neutral | Approval requests are a general legal-ops primitive. |
| Reports | `contracts:reports_dashboard` | Shared / mode-neutral | Generic aggregate reporting. |
| Obligations | `contracts:obligations_workspace` | Shared / mode-neutral | Dedicated obligations workspace; no longer a deadline-list stopgap. |
| Playbooks | `contracts:dpa_playbook_list` | Secondary / mode-neutral | The route remains directly reachable, but is deliberately absent from the standard primary navigation until its final product framing is defined. |

No route needs to be hidden or redirected for either mode. The primary
navigation deliberately favours a single, coherent information architecture;
secondary routes remain available by direct URL and command search.

## Explicit dashboard standardization

The Command Center is now a deliberate shared product decision, not an
accidental removal of a mode gate. The containment tests assert that both
workspace modes render the same governed dashboard and that law-firm billing
language does not reappear there.

## Testing expectations for future mode-aware changes

Any PR that adds or changes `workspace_mode` branching must:

1. Add this route (or confirm an existing entry) to the classification
   table above, in the same commit.
2. If it's **shared shell, mode-specific content**: add both a
   `law_firm_ops`-preservation test (existing behavior/copy unchanged) and
   an `in_house_clm`-content test, following the pattern in
   `tests/test_workspace_mode_containment.py`'s `DashboardContainmentTests` /
   `MatterDetailContainmentTests` / `RiskReviewContainmentTests` — assert the
   *other* mode's markers are **absent**, not just that the page returns 200.
2. If it's **shared / mode-neutral**: add an accessibility test (200 for
   both modes) and, if the route touches organization-scoped data, a
   tenant-scoping test proving cross-org data doesn't leak — `workspace_mode`
   must never become a backdoor around organization scoping.
3. If primary navigation changes: pin the resulting labels via
   `get_nav_for()` (not by scraping rendered HTML) for both modes.
4. Gate on a single `is_in_house_clm`/`workspace_mode` computation per
   request — never scatter `getattr(org, 'workspace_mode', ...)` calls
   throughout a view or template.
