# CLM One Pilot Verification Gate

**Date:** 2026-07-20  
**Scope:** Close remaining Sprint 0 verification gaps only. No new features, unrelated redesign, module expansion, or production-readiness work.  
**Authority:** `docs/governance/GOVERNANCE_CHARTER.md` v2.0, ADR-0009, PDR-0001 (finance threshold), PDR-0002, `CLM_ONE_APPLICATION_AUDIT_2026-07-20.md`, `PILOT_STABILISATION_SPRINT_0_REPORT_2026-07-20.md`, canonical design-system docs.  
**Production / enterprise readiness:** Not claimed.

---

## 1. Executive decision

### **CONTROLLED PILOT GO**

CLM One may start a **controlled internal pilot** under the allowed workflows and exclusions in §12–§13.

This decision is based on completed gate evidence below. It is **not** a production, external-customer, or enterprise readiness claim.

---

## 2. Gate-by-gate result

| Gate | Result | Summary |
|---|---|---|
| 1 DPA deceptive / inert CTAs | **PASS** | Unsupported DPA Legal/DPO/memo/export CTAs removed; deceptive “Review next action” primary CTA removed; remaining actions are navigational tabs, clause anchors, View contract record, or builder POST. |
| 2 Eight Django suite failures | **PASS** | All eight Sprint 0 failures classified and resolved; full hermetic suite green with zero unexplained failures. |
| 3 Critical Playwright journeys | **PASS** | Critical suite **27 passed** on two consecutive runs (1.1m / 1.0m). Journeys include auth, MSA Legal/Finance/export, NDA/DPA honesty, search fixtures + cross-tenant exclusion, lifecycle Stage/Status + illegal skip rejection + valid transition. |
| 4 Redis multi-worker rate limiting | **PASS** | Local Redis `redis://127.0.0.1:6379/15`; sequential + concurrent shared counter; unrelated IP isolation; success path; credentials redacted. |
| 5 Pilot environment reproducibility | **PASS** | `scripts/pilot_env_verify.sh` clean-state migrate + seed + threshold + Redis checks **PASS**. |
| Governance amendment integrity | **PASS** | `scripts/check_governance_authority.sh` → OK. |

---

## 3. Exact commands used

### Django full suite
```bash
DJANGO_SETTINGS_MODULE=config.settings_test .venv/bin/python manage.py test
```

### Redis shared rate-limit proof
```bash
DATABASE_URL=sqlite:////tmp/clmone-pilot-rl.sqlite3 \
REDIS_URL=redis://127.0.0.1:6379/15 \
DJANGO_SETTINGS_MODULE=config.settings_development \
DJANGO_DEBUG=false \
.venv/bin/python scripts/verify_redis_login_rate_limit.py
```

### Pilot environment clean-state
```bash
bash scripts/pilot_env_verify.sh
```

### Critical Playwright suite (run twice; kill :8010 between runs)
```bash
cd client
for run in 1 2; do
  pids=$(lsof -tiTCP:8010 -sTCP:LISTEN 2>/dev/null || true)
  [ -n "$pids" ] && kill $pids && sleep 2
  npm run test:e2e -- \
    tests/e2e/msa-workflow.spec.js \
    tests/e2e/nda-workflow.spec.js \
    tests/e2e/dpa-workflow.spec.js \
    tests/e2e/pilot-gate.spec.js \
    tests/e2e/pilot-verification.spec.js \
    --reporter=list
done
```

Evidence: `docs/audits/evidence/2026-07-20-pilot-verification/`.

---

## 4. Exact test totals

| Suite | Result |
|---|---|
| Django (`config.settings_test`) | **Ran 2076 tests in 147.211s — OK (skipped=32)** |
| Governance authority check | **OK** |
| Redis verify script | **ALL REDIS RATE-LIMIT CHECKS PASSED** |
| Pilot env clean-state | **PASS** (`finance_threshold=100000`) |
| Playwright critical run 1 | **27 passed (1.1m)** |
| Playwright critical run 2 | **27 passed (1.0m)** |

No implementation-percentage scoring is used for this decision.

---

## 5. DPA CTA inventory

Workspace: `theme/templates/contracts/dpa_contract_workspace.html`  
Builder: DPA four-step generate path (server create + redirect).

| Screen | CTA | Previous behaviour | Final behaviour | Permission rule | Audit event | Test coverage |
|---|---|---|---|---|---|---|
| DPA workspace | Send to Legal Review | Visible, inert | **Removed** | n/a | n/a | `tests/test_dpa_workflow.py`; `dpa-workflow.spec.js`; `pilot-gate` / `pilot-verification` |
| DPA workspace | Send to DPO | Visible, inert | **Removed** | n/a | n/a | same |
| DPA workspace | Generate DPA review memo | Visible, inert | **Removed** | n/a | n/a | same |
| DPA workspace | Export Word | Visible, inert | **Removed** | n/a | n/a | same |
| DPA workspace | Review next action (primary) | Deceptive / non-action | **Removed** | n/a | n/a | design-system phase1 allows DPA without primary button; browser honesty checks |
| DPA workspace | View contract record | Link | **Kept** — real GET to org-scoped contract detail | Auth + tenant contract access | Prior generate AuditLog; navigation only | Django + Playwright DPA specs |
| DPA workspace | Rail tabs Review / Properties / Activity | UI chrome | **Kept** — client tab switch; Activity shows Audit history surface | Workspace view | Displays real AuditLog helper / empty state | Playwright clicks Activity |
| DPA workspace | Clause / risk section links | In-page anchors | **Kept** — fragment navigation | Workspace view | none (UI) | Present in template; generate path exercises workspace |
| DPA builder | Generate / continue | Server create | **Kept** — CSRF POST, persist, redirect | Login + org membership | Workflow/contract create audit path | `dpa-workflow.spec.js`, Django DPA tests |

**Acceptance:** No visible DPA action remains inert. Unsupported workflow CTAs are absent from the pilot interface rather than partially implemented.

---

## 6. Eight-failure classification

Sprint 0 left eight full-suite failures. Each was classified; product defects were fixed; stale tests were updated only when current behaviour matches charter / ADR / PDR / design-system authority.

| # | Exact test | Failure output (Sprint 0 class) | Affected behaviour | Root cause | Classification | Change made | Evidence correct |
|---|---|---|---|---|---|---|---|
| 1 | `test_contract_workspace_exposes_governed_review_state` | Missing obsolete review tab/copy | Contract review workspace entry | Stale UI expectations vs intentional review tab (`?tab=review`) | **stale test** / intentional approved UI | Assertions updated to current review entrypoints | Suite green; matches current templates |
| 2 | `test_contract_documents_tab_shows_a_completed_clear_upload_review` | Missing upload-review copy | Documents / upload review surfacing | Stale expectations | **stale test** | Assert review tab + “Latest review evidence” | Suite green |
| 3 | `test_create_audit_records_derived_risk_and_routing` | Missing “Preliminary Low risk” on detail | Intake risk visibility on contract detail | Product regression in overview | **product defect** | Restored risk label on detail overview | Suite green; label present again |
| 4 | `test_case_flow_semantics_on_high_traffic_pages` | Expected legacy shell labels | High-traffic page chrome | Intentional shell copy (“View workflow” / “Activity”) | **intentional approved change** | Assertions updated | Suite green; charter/shell |
| 5 | `test_canonical_assets_are_exact_approved_files` | Brand hash / path mismatch | Landing preview asset | Asset placed under wrong static path | **product defect** | Moved preview to approved static path; path/hash expectations aligned | Suite green |
| 6–8 | `test_phase_three_b_standard_lists_use_the_shell_header_and_scaffold` (×3) | Expected pre–Workflow Ops list shell | List page scaffold | Intentional Workflow Ops toolbar shell | **intentional approved change** | Expectations updated to current shell | Suite green; design-system |

Additional suite hygiene during this gate (not part of the original eight, but required for green totals): Workflow Ops tests updated where Active workflows / Approval requests are the supported Ops surface and templates/routing live under Workflow Designer (`tests/test_workflow_operations.py`, `tests/test_workflow_routing.py`) — **intentional approved change** / **stale test**, justified by current shell.

**Acceptance:** Zero unexplained failures. No assertions weakened solely to obtain green output.

---

## 7. Critical Playwright coverage map

Specs executed twice:

- `client/tests/e2e/msa-workflow.spec.js`
- `client/tests/e2e/nda-workflow.spec.js`
- `client/tests/e2e/dpa-workflow.spec.js`
- `client/tests/e2e/pilot-gate.spec.js`
- `client/tests/e2e/pilot-verification.spec.js`

| Required journey | Evidence |
|---|---|
| Auth: successful login | `pilot-gate` |
| Auth: failed logins → 429 | `pilot-gate` (`LOGIN_RATE_LIMIT_REQUESTS=3` in e2e server) |
| Auth: unrelated counter isolation | `pilot-verification` (unrelated IP remains 200) |
| Auth: success clears counter | `pilot-gate` |
| Auth: logout + session idle expiry | `pilot-verification` (`?e2e_force_idle=1` under `DJANGO_E2E`) |
| MSA: Legal submit + refresh + audit | `msa-workflow` + `pilot-verification` |
| MSA: Finance below / exactly $100k / above | `pilot-verification` (absent below; submit + audit at $100k; submit above) |
| MSA: export DOCX download | `msa-workflow` (`download` event, `.docx` filename) |
| NDA: unsupported absent; supported clicked; persist + Activity | `nda-workflow`, `pilot-gate`, `pilot-verification` |
| DPA: unsupported absent; supported clicked; persist + Activity | `dpa-workflow`, `pilot-gate`, `pilot-verification` |
| Search: valid/list/malformed/empty/error/timeout/keyword | `pilot-verification` via `e2e_fixture:*` hooks (not live Gemini) |
| Search: cross-tenant exclusion | `pilot-verification` (foreign clause title absent from result body) |
| Lifecycle: Stage sort + Status filter | `pilot-gate`, `pilot-verification` |
| Lifecycle: illegal stage skip rejected | `pilot-verification` → `POST /contracts/api/contracts/bulk-update/` → **400** |
| Lifecycle: valid transition + persisted Stage | same test → **200** to `INTERNAL_REVIEW`, refresh shows Stage |

**Note on search provider shapes:** Browser matrix uses deterministic `DJANGO_E2E` fixtures in `semantic_search.py`. Live Gemini is disabled in e2e (`GEMINI_AI_ENABLED=false`). Django unit coverage remains the primary provider-shape proof; browser proves no-500 + fallback UX + tenant exclusion.

**Consecutive results:**

| Run | Totals | Log |
|---|---|---|
| 1 | 27 passed (1.1m) | `docs/audits/evidence/2026-07-20-pilot-verification/pilot-verify-gate-run1.txt` |
| 2 | 27 passed (1.0m) | `docs/audits/evidence/2026-07-20-pilot-verification/pilot-verify-gate-run2.txt` |

Visibility-only checks were not counted as sole verification for mutating journeys.

---

## 8. Redis multi-worker evidence

**Config:** `REDIS_URL=redis://127.0.0.1:6379/15` with `django_redis.cache.RedisCache` (not LocMem).  
**Log:** `docs/audits/evidence/2026-07-20-pilot-verification/redis-rate-limit.txt`

Verified:

| Check | Result |
|---|---|
| Shared counter across sequential multi-client failures | **PASS** → 429 |
| Concurrent multi-client posts under limit=3 | **PASS** statuses `[200, 200, 200, 429, 429, 429]` |
| Unrelated IP isolation | **PASS** |
| Successful login | **PASS** (302) |
| Redis remains healthy | **PASS** |
| Credentials in script output | **Redacted** (`REDIS_URL present: yes (value redacted)`) |

**Policy:**

| Dimension | Behaviour |
|---|---|
| Keying | IP-based (`auth-rl:/login/:<ip>`) |
| Account | Not separately keyed |
| Success | Clears counter keys |
| Failures | Increment on failed login responses only |
| Redis unavailable (`DEBUG=false`) | Fail closed (503); no credential logging on exception path |
| LocMem | Single-process only — **not** used as multi-worker proof |

**Product note:** Middleware uses atomic `cache.incr` with LocMem-safe fallback so shared Redis counters do not under-count across workers.

**E2E isolation:** `scripts/start_e2e_server.sh` forces empty `REDIS_URL` so developer `.env` remote Redis cannot silently attach to browser tests. Gate 4 proof always uses an explicit local Redis URL.

---

## 9. Pilot environment reproducibility evidence

**Script:** `scripts/pilot_env_verify.sh`  
**Log:** `docs/audits/evidence/2026-07-20-pilot-verification/pilot-env-setup.log`  
**Result:** `=== PASS: pilot environment clean-state verification complete ===`

Includes:

- Isolated SQLite DB (`/tmp/clmone-pilot-env-verify.sqlite3`)
- Local Redis DB index 14
- Migrate + seed (`pilot_owner` / `pilot_legal` / `pilot_finance`)
- Approval rules seeded
- Finance threshold **100000** asserted
- Django system check
- Redis rate-limit verify embedded
- Reset procedure printed in log (`rm` DB + `FLUSHDB` + re-run)

Browser E2E path (separate but documented): `scripts/start_e2e_server.sh` + Playwright `webServer` on `127.0.0.1:8010` with deterministic `e2e_*` users, AI kill switch off, LocMem rate limit for hermetic auth tests.

**Remaining packaging gap (accepted risk, not a decision-rule fail):** no single docker-compose packing Postgres + Redis + multi-gunicorn as one checked-in pilot appliance. Clean-state scripts + Redis verify are sufficient for this gate’s reproducibility bar.

---

## 10. Screenshots, videos, and traces

Final green×2 runs produced **no** failure artifacts (expected).

Retained intermediate failure artifacts from assertion hardening (required retention policy):

| Artifact | Location |
|---|---|
| Intermediate Finance persistence assertion fail (screenshot/video/trace) | `docs/audits/evidence/2026-07-20-pilot-verification/failures/pilot-verification-Verific-01145--present-at-above-threshold/` |
| Intermediate lifecycle edit false-path fail (screenshot/video/trace) | `docs/audits/evidence/2026-07-20-pilot-verification/failures/pilot-verification-Verific-14bce-ge-skip-is-rejected-on-edit/` |
| Intermediate finance fail log | `docs/audits/evidence/2026-07-20-pilot-verification/playwright-intermediate-finance-fail.txt` |
| Final Playwright logs | `pilot-verify-gate-run1.txt`, `pilot-verify-gate-run2.txt` |
| Django / Redis / env | `django-suite-summary.txt`, `redis-rate-limit.txt`, `pilot-env-setup.log` |

Playwright config retains screenshot/video/trace **on failure** for future regressions.

---

## 11. Remaining risks

1. **Search live-provider behaviour** — browser matrix is fixture-driven; keep AI kill switch off unless a separate live-provider rehearsal is approved.
2. **IP-keyed login throttle** — unrelated users on a shared NAT share counters; document for pilot operators.
3. **`django_redis` IGNORE_EXCEPTIONS** vs middleware fail-closed — keep Redis healthy; monitor 429/503.
4. **NDA/DPA depth** — generate + view/activity only; signature/export/legal CTAs remain excluded.
5. **Single-org pilot assumption** — multi-tenant production hardening is out of scope.
6. **Edit form lifecycle fields** — intentionally omitted from `ContractForm`; stage mutations go through lifecycle services / bulk-update API (verified).

---

## 12. Allowed pilot workflows

Single seeded organization only.

| Workflow | Allowed actions |
|---|---|
| Authentication | Login, logout; Redis-backed failed-login throttle on the pilot host |
| MSA | Generate draft → Send to Legal → Send to Finance when threshold met (≥ $100,000) → Export Word → View contract record; inspect Audit/Governance details |
| NDA | Generate → View contract record → Activity/Audit rail (read) |
| DPA | Generate → View contract record → Activity/Audit rail (read) |
| Repository | View Stage/Status; sort by Stage; filter by Status; legal adjacent Stage transitions via governed bulk-update |
| Search | Keyword / safe semantic fallback with AI disabled or tightly controlled |

**Roles:** `pilot_owner` (Owner), `pilot_legal`, `pilot_finance` (or e2e equivalents in automated rehearsal).

---

## 13. Excluded workflows

- NDA: Send for signature, Send to Legal, Generate summary, Export Word (**hidden**)
- DPA: Legal / DPO / memo / Export Word / deceptive primary CTA (**hidden/removed**)
- Dark theme (**deferred** by charter)
- Freeform `/contracts/new/` as the governed pilot path
- Unbounded / live AI features beyond kill-switch-safe fallback
- Salesforce / webhook / IdP enterprise integrations as pilot-critical
- Multi-org production rollout
- Any CTA that is not wired with auth, CSRF, persistence, feedback, AuditLog, and browser proof

---

## 14. Decision-rule mapping

| Rule | Triggered? |
|---|---|
| Any inert visible CTA ⇒ NO-GO | **No** — DPA inventory clean |
| Any unexplained Django failure ⇒ NO-GO | **No** — 2076 OK |
| Any unexecuted critical browser journey ⇒ NO-GO | **No** — matrix executed ×2 |
| Tenant-isolation / auth / data-integrity / lifecycle failure ⇒ NO-GO | **No** — failures not observed in executed evidence |
| Unproven shared Redis rate-limit ⇒ NO-GO | **No** — Redis script PASS |

---

## 15. Final recommendation

# **CONTROLLED PILOT GO**

### Monitoring and rollback (required while pilot runs)

- Redis health + auth 429/503 rates  
- AuditLog append health on MSA Legal/Finance/export and Stage transitions  
- AI kill switch remains **off** unless separately approved  
- Ability to disable workflow launchers and revoke pilot sessions  
- Restore from isolated DB snapshot; kill app workers on suspend triggers  

### Immediate suspend triggers

Cross-tenant leakage; auth bypass; inert CTA regression; Finance threshold misfire; AuditLog write failure; Redis fail-open brute-force; data loss/corruption on generate/submit/export; unexplained production-like 5xx on governed path.

### Closing answers

| Question | Answer |
|---|---|
| Can the controlled pilot start? | **Yes**, under §12–§13 only. |
| Allowed workflows? | §12 |
| Excluded workflows? | §13 |
| Who may participate? | Seeded pilot org roles only |
| Production ready? | **No** |
| Enterprise ready? | **No** |

---

*Supersedes the NO-GO in `CONTROLLED_PILOT_REASSESSMENT_2026-07-20.md` for Gate 3 completeness. Does not supersede the Governance Charter or ADRs.*
