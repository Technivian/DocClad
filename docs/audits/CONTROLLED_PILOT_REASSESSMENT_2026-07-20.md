# CLM One Controlled Pilot Reassessment Gate

**Date:** 2026-07-20  
**Scope:** Verification and remediation of remaining Sprint 0 evidence gaps only.  
**Authority:** `docs/governance/GOVERNANCE_CHARTER.md` v2.0, ADR-0009, PDR-0001 (finance threshold), PDR-0002, application audit 2026-07-20, Sprint 0 report.  
**Production / enterprise readiness:** Not claimed.

---

## 1. Executive decision

### **NO-GO**

CLM One must **not** start a controlled internal pilot yet.

Several Sprint 0 defects are fixed and evidenced (DPA CTA honesty, full Django suite green, Redis multi-client rate-limit proof, governance amendment checks, a critical Playwright subset green twice). The gate still fails because **required critical Playwright journeys remain unexecuted** (decision rule: any unexecuted critical journey ⇒ NO-GO). This is not a production-readiness claim and not a percentage-complete score.

---

## 2. Gate-by-gate result

| Gate | Result | Summary |
|---|---|---|
| 1 DPA deceptive actions | **PASS** | Unsupported DPA CTAs removed from workspace; remaining actions are navigational or wired; Django + browser coverage. |
| 2 Eight full-suite failures | **PASS** | All eight classified and resolved; full suite green with zero unexplained failures. |
| 3 Critical Playwright journeys | **FAIL** | Governed subset (MSA/NDA/DPA/pilot-gate) passed **twice** consecutively (10/10 × 2). Required journeys still missing: logout/session expiry, Finance threshold matrix in-browser ($100k / below / above), semantic provider shape/timeout/cross-tenant browser matrix, invalid Stage/Status transition browser proof, legacy `critical-flows` create/edit path. |
| 4 Redis rate limiting | **PASS** | Local Redis (`redis://127.0.0.1:6379/15`); sequential + concurrent shared-counter evidence; unrelated IP isolation; success path; atomic incr fix in middleware. |
| 5 Governance amendment integrity | **PASS** | Canonical charter, historical retention, ADR-0009 approval metadata, `scripts/check_governance_authority.sh` OK, light-first approved not inferred. |
| 6 Pilot environment reproducibility | **PARTIAL** | E2E seed/server scripts + local Redis path documented below; developer `.env` remote Redis footgun mitigated for e2e via empty `REDIS_URL`; full multi-worker gunicorn pilot compose still not packaged as a one-command pilot stack. |

---

## 3. Exact test commands

### Django full suite
```bash
cd /Users/haroonwahed/Documents/Projects/CLMOne
DJANGO_SETTINGS_MODULE=config.settings_test .venv/bin/python manage.py test
```

### Governance authority
```bash
scripts/check_governance_authority.sh
```

### Redis multi-worker / multi-client rate limit
```bash
# Local Redis (example)
/opt/homebrew/opt/redis/bin/redis-server --daemonize yes --port 6379 --dir /tmp --dbfilename clmone-pilot-redis.rdb

DATABASE_URL=sqlite:////tmp/clmone-pilot-rl.sqlite3 \
REDIS_URL=redis://127.0.0.1:6379/15 \
DJANGO_SETTINGS_MODULE=config.settings_development \
DJANGO_DEBUG=false \
.venv/bin/python manage.py migrate --noinput

DATABASE_URL=sqlite:////tmp/clmone-pilot-rl.sqlite3 \
REDIS_URL=redis://127.0.0.1:6379/15 \
DJANGO_SETTINGS_MODULE=config.settings_development \
DJANGO_DEBUG=false \
.venv/bin/python scripts/verify_redis_login_rate_limit.py
```

### Critical Playwright subset (run twice)
```bash
cd client
npx playwright install chromium
# Kill any stale listener on 8010 between runs
for run in 1 2; do
  pids=$(lsof -tiTCP:8010 -sTCP:LISTEN 2>/dev/null || true)
  [ -n "$pids" ] && kill $pids && sleep 2
  npm run test:e2e -- \
    tests/e2e/msa-workflow.spec.js \
    tests/e2e/nda-workflow.spec.js \
    tests/e2e/dpa-workflow.spec.js \
    tests/e2e/pilot-gate.spec.js \
    --reporter=list
done
```

Evidence archived under `docs/audits/evidence/2026-07-20-pilot-reassessment/`.

---

## 4. Exact test totals

| Suite | Result |
|---|---|
| Django (`config.settings_test`) | **Ran 2069 tests in 57.714s — OK (skipped=32)** |
| Governance check | **OK** |
| Redis verify script | **ALL REDIS RATE-LIMIT CHECKS PASSED** |
| Playwright run 1 | **10 passed (32.5s)** |
| Playwright run 2 | **10 passed (38.9s)** |

No implementation percentages are used for the go/no-go decision.

---

## 5. Eight-failure classification

Sprint 0 left eight full-suite failures. Gate 2 classified and resolved them. Product code changed only where current UI still required it; otherwise tests were updated to approved current behaviour (charter / PDR / design-system).

| # | Test | Failure (Sprint 0) | Product behaviour | Root cause | Classification | Resolution | Evidence | Changed |
|---|---|---|---|---|---|---|---|---|
| 1 | `test_contract_workspace_exposes_governed_review_state` | Asserted obsolete review tab/copy | Review workspace uses `?tab=review` + current governed copy | Stale expectations vs intentional UI | intentional product change / stale test | Assertions updated to current review entrypoints | Django suite green | test |
| 2 | `test_contract_documents_tab_shows_a_completed_clear_upload_review` | Missing expected upload-review copy | Upload review surfaces under review tab | Stale expectations | stale test | Assert `?tab=review` + “Latest review evidence” | Django suite green | test |
| 3 | `test_create_audit_records_derived_risk_and_routing` | Missing “Preliminary Low risk” on detail | Intake risk label expected on overview Progress meta | Product regression in detail template | real defect | Restored risk label on contract detail overview | Django suite green | product |
| 4 | `test_case_flow_semantics_on_high_traffic_pages` | Expected legacy labels | Shell uses “View workflow” / “Activity” | intentional product change | intentional product change | Assertions updated | Django suite green | test |
| 5 | `test_canonical_assets_are_exact_approved_files` | Brand hash / path drift | Landing preview lived under wrong static path | real defect (asset placement) | real defect | Moved preview to `theme/static/marketing/`; landing path updated | Django suite green | product + test path |
| 6–8 | `test_phase_three_b_standard_lists_use_the_shell_header_and_scaffold` (×3) | Expected pre–Workflow Ops list shell | Lists use Workflow Ops toolbar shell | intentional product change | intentional product change | Expectations updated to current shell | Django suite green | test |

**Acceptance:** Zero unexplained failures. Real defects fixed. Stale expectations updated with documented justification. No assertions deleted merely to go green.

---

## 6. Playwright results

### Executed twice consecutively (PASS)

Specs:

- `client/tests/e2e/msa-workflow.spec.js`
- `client/tests/e2e/nda-workflow.spec.js`
- `client/tests/e2e/dpa-workflow.spec.js`
- `client/tests/e2e/pilot-gate.spec.js`

| Run | Totals |
|---|---|
| 1 | 10 passed (32.5s) |
| 2 | 10 passed (38.9s) |

Covered in-browser (non-exhaustive vs Gate 3 checklist):

- Successful login; failed-login 429; success clears counter
- MSA generate → Legal submit → Finance submit → Export Word → View contract record (persisted workspace)
- NDA generate; unsupported CTAs absent; View contract record + reload
- DPA builder path; launcher reachable; unsupported CTAs absent (with Django assert companions)
- Search page usable; repository Stage sort control present (Status sort control absent)

### Not executed (blocks Gate 3)

| Required journey | Status |
|---|---|
| Logout + session expiry | **UNEXECUTED** |
| Unrelated user not incorrectly blocked (browser, multi-account) | **PARTIAL** (Django + Redis script only) |
| MSA Finance exactly $100,000 / below / above in browser | **UNEXECUTED** (unit/policy covered; not this browser matrix) |
| Semantic: list-shaped / malformed / timeout / keyword fallback / cross-tenant exclusion in browser | **UNEXECUTED** (Django `test_semantic_search_responses` covers provider shapes; browser only hits live search page) |
| Lifecycle invalid Stage/Status transitions in browser + AuditLog | **UNEXECUTED** (service/PDR covered in unit tests) |
| `critical-flows.spec.js` freeform create/edit + redesigned workflow path | **UNEXECUTED** this gate (selectors partially updated; not green×2) |

**Screenshots / traces:** Passing consecutive runs left no failure artifacts under `client/test-results/` (only `.last-run.json`). Earlier failing attempts produced Playwright error contexts; retained command logs are in `docs/audits/evidence/2026-07-20-pilot-reassessment/`.

---

## 7. DPA action inventory

Workspace: `theme/templates/contracts/dpa_contract_workspace.html`  
Builder: DPA four-step generate path (server-side create + redirect).

| Screen | CTA | Previous behaviour | Final behaviour | Permission rule | Audit event | Automated test |
|---|---|---|---|---|---|---|
| DPA workspace | Send to Legal Review | Visible, inert | **Removed** | n/a | n/a | `tests/test_dpa_workflow.py` (`assertNotContains`); `dpa-workflow.spec.js` |
| DPA workspace | Send to DPO | Visible, inert | **Removed** | n/a | n/a | same |
| DPA workspace | Generate DPA review memo | Visible, inert | **Removed** | n/a | n/a | same |
| DPA workspace | Export Word | Visible, inert | **Removed** | n/a | n/a | same |
| DPA workspace | View contract record | Link to contract detail | **Kept** — real GET to contract record | Auth + org-scoped contract access | Prior workflow generate AuditLog; navigation only | Django + `dpa-workflow` / pilot-gate |
| DPA workspace | Review next action | Anchor to `#risk-signals` | **Kept** — in-page navigation | Authenticated workspace view | none (UI only) | Template present; browser generate path |
| DPA workspace | Rail tabs Review / Properties / Activity | UI chrome | **Kept** — client tab switch; Activity uses real AuditLog history helper | Workspace view | Displays `_workflow_audit_history()` | Sprint 0 honest-audit work + DPA tests |
| DPA builder | Generate / continue | Server create | **Kept** — POST builder, CSRF, persistence, redirect | Login + org membership | Workflow/contract create audit path | `dpa-workflow.spec.js`, Django DPA tests |

**Acceptance checked for remaining visible actions:** no inert primary workflow CTAs; unsupported actions absent; generate + view-record persist across reload; unauthorized paths remain covered by existing auth tests (not re-litigated here).

---

## 8. Redis multi-worker evidence

**Command / result:** see §3 and `docs/audits/evidence/2026-07-20-pilot-reassessment/redis-rate-limit.txt`.

Verified:

- Cache backend `django_redis.cache.RedisCache` with local `REDIS_URL`
- Sequential multi-client failures share counter → 429 + `Retry-After`
- Concurrent posts observe shared throttle (`[200,200,200,429,429,429]` under limit=3)
- Unrelated IP remains unblocked
- Successful login returns 302 and clears counter keys
- Credentials are not printed by the verify script

**Product fix during gate:** `contracts/middleware.py` now uses atomic `cache.incr` (with LocMem-safe fallback) so multi-worker counters do not silently under-count. Fail-closed on cache errors remains (503 when `DEBUG` is false).

**Policy documentation:**

| Dimension | Behaviour |
|---|---|
| Keying | IP-based (`auth-rl:/login/:<ip>` + reset key) |
| Account | Not separately keyed; username alone does not isolate counters |
| Success | HTTP 302 clears counter keys |
| Failures only | Login increments only on HTTP 200 failed login responses |
| Redis unavailable | Fail closed (503), no credential logging in middleware exception path |
| LocMem | Single-process only — **not** used as multi-worker proof |

**Note:** Pilot e2e forces `REDIS_URL=` empty so developer `.env` remote Redis cannot silently attach to browser tests. Gate 4 proof used an explicit local Redis URL.

---

## 9. Governance amendment verification

| Check | Result |
|---|---|
| Previous CMS Aegis doc retained historical | **PASS** — `DESIGN_CONSTITUTION.md` banner + ADR-0009 |
| Canonical CLM One Charter identified | **PASS** — `GOVERNANCE_CHARTER.md` v2.0 |
| Altered rules have replacement wording | **PASS** — charter §4 light-first; Finance PDR-0001; Stage/Status PDR-0002 |
| ADR-0009 rationale + consequences | **PASS** |
| Approval authority + effective date | **PASS** — Approved by Product/Engineering governance; effective **2026-07-20** |
| Agent / docs reference canonical charter | **PASS** — README + design-system README + ADR |
| CI/docs check fails obsolete authority | **PASS** — `scripts/check_governance_authority.sh` |
| Light-first approved not inferred | **PASS** — explicit charter amendment + ADR-0009 item 4 |

No governance change lacking formal authority was found in this gate’s amendment set.

---

## 10. Pilot environment instructions

Goal: a new engineer can start an isolated stack and run the critical suite without hidden lore.

### A. Isolated E2E / browser gate (recommended for Gate 3)

```bash
# From repo root
# Optional: local Redis only if verifying Gate 4
# E2E server isolates from .env Redis by exporting REDIS_URL=

cd client
npx playwright install chromium
npm run test:e2e -- tests/e2e/msa-workflow.spec.js tests/e2e/nda-workflow.spec.js \
  tests/e2e/dpa-workflow.spec.js tests/e2e/pilot-gate.spec.js
```

`scripts/start_e2e_server.sh` (invoked by Playwright `webServer`):

- Isolated SQLite: `e2e.sqlite3` (deleted on each start unless `E2E_DATABASE_URL` set)
- Seeds `e2e_owner` / `e2e_pass_123`, `e2e_legal`, `e2e_finance`
- Seeds MSA Legal/Finance approval rules
- Forces `LOGIN_RATE_LIMIT_REQUESTS=3`, empty `REDIS_URL` (LocMem), `DJANGO_E2E=1`
- Listens on `127.0.0.1:8010`
- Health: `http://127.0.0.1:8010/login/`

Reset: kill port 8010; delete `e2e.sqlite3`; re-run Playwright (server script recreates DB).

### B. Local Redis rate-limit proof (Gate 4)

See §3. Use a disposable SQLite file and Redis DB index `15`.

### C. Dev server (non-e2e)

```bash
scripts/dev_up.sh          # or scripts/dev_server.sh
scripts/dev_status.sh
scripts/dev_down.sh
```

**Pilot policy knobs to confirm before any future GO:**

- Finance threshold `$100,000` via `contracts/services/finance_approval_policy.py` / PDR-0001
- AI kill switch / provider keys per org AI controls (do not enable unbounded AI in pilot)
- Logging via existing request middleware (`request_id`, no secrets)
- Do **not** point pilot at remote Supabase/`DATABASE_URL` without `ALLOW_REMOTE_DATABASE=true` explicit opt-in

### D. Gaps vs ideal pilot compose

- No checked-in docker-compose that boots Postgres + Redis + multi-gunicorn workers as a single pilot package
- Operator must still know to clear ambient `.env` remote Redis for local proofs (e2e now self-isolates)

---

## 11. Remaining restrictions

Even after a future GO, these must stay out of scope or explicitly hidden:

- NDA: Send for signature, Send to Legal, Generate summary, Export Word (**hidden**)
- DPA: Legal/DPO/memo/Export Word (**hidden**)
- Dark theme (**deferred** by charter)
- Freeform `/contracts/new/` legacy create UX not part of governed MSA/NDA/DPA path
- Remote AI provider behaviour beyond safe fallback (browser matrix incomplete)
- Multi-tenant production hardening beyond current org scoping tests
- `django_redis` `IGNORE_EXCEPTIONS=True` means cache read errors can degrade differently than middleware fail-closed path — pilot must keep Redis healthy and monitor 503/429 rates

---

## 12. Screenshots and traces

| Artifact | Location |
|---|---|
| Playwright run 1 log | `docs/audits/evidence/2026-07-20-pilot-reassessment/playwright-run1.txt` |
| Playwright run 2 log | `docs/audits/evidence/2026-07-20-pilot-reassessment/playwright-run2.txt` |
| Redis verify log | `docs/audits/evidence/2026-07-20-pilot-reassessment/redis-rate-limit.txt` |
| Django suite summary | `docs/audits/evidence/2026-07-20-pilot-reassessment/django-suite-summary.txt` |
| Failure traces | None retained for the final green×2 runs (no failures) |

Manual screenshot capture of MSA Actions / NDA-only CTA / DPA-only CTA is still recommended before any future Conditional GO.

---

## 13. Final decision

# **NO-GO**

### Decision-rule mapping

| Rule | Triggered? |
|---|---|
| Tenant-isolation / auth / data-integrity / deceptive-CTA / critical-lifecycle failure ⇒ NO-GO | Deceptive CTAs addressed; no new tenant-isolation failure in executed suites. Lifecycle browser invalid-transition journey **unexecuted**. |
| Unexecuted critical Playwright journey ⇒ NO-GO | **Yes — Gate 3 FAIL** |
| Unexplained full-suite failure ⇒ NO-GO | No — suite green |
| CONDITIONAL GO only for explicitly hidden/out-of-scope items | Not available while Gate 3 required journeys remain unexecuted |

---

## Closing checklist (required answers)

### Can the controlled pilot start?
**No.**

### Exactly which workflows are allowed?
**None for live pilot use under this gate.**  
(If this were Conditional GO later, the only candidates would be: seeded single-org **MSA** generate + Legal/Finance/export, **NDA** generate + view record, **DPA** generate + view record, repository Stage display/sort, login with Redis throttle — still excluding everything in §11.)

### Exactly which workflows are excluded?
All non-governed and unsupported paths, including: NDA/DPA signature & export actions, dark theme, unbounded AI features, legacy freeform create as the pilot path, Salesforce/webhook enterprise integrations as pilot-critical, multi-org production rollout.

### Which users and roles may participate?
**Nobody in a live pilot until Gate 3 is complete.** Seeded E2E roles for testing only: `e2e_owner` (Owner), `e2e_legal`, `e2e_finance`.

### What monitoring and rollback controls are required?
Before any future start: Redis health + 429/503 auth metrics; AuditLog append health; AI kill switch; ability to disable workflow launchers; restore from isolated DB snapshot; kill app workers; revoke sessions for pilot org.

### What evidence would immediately suspend the pilot?
Cross-tenant data leakage; auth bypass; inert CTA regression; Finance threshold misfire; AuditLog write failure; Redis fail-open brute-force; data loss/corruption on generate/submit/export; unexplained production-like 5xx on governed path.

---

## Remediation to re-enter reassessment

1. Execute every remaining Gate 3 browser journey with persistence assertions; pass **twice** consecutively.
2. Keep full Django suite green.
3. Re-run Redis verify against the approved shared Redis URL for the intended pilot host.
4. Capture screenshots/traces for any failure and for the MSA/NDA/DPA honesty surfaces.
5. Re-issue this report with an updated decision — do not claim Conditional GO while critical journeys are unexecuted.
