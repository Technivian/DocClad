# CLM One Delivery Roadmap

Last updated: 2026-07-21

> **Product sequencing:** See [`docs/PRODUCT_ROADMAP.md`](docs/PRODUCT_ROADMAP.md) for the governed work-system product map, persona lens, and phased outcomes (My Work → canonical assignment model → core loop → governance → instrumentation). This file remains the engineering delivery / readiness tracker.

## Audit Baseline (measured before Wave 0-1 work)

| Dimension | Score |
|---|---|
| Production Readiness | 22 / 100 |
| Product Maturity | 40 / 100 |
| Enterprise Readiness | 24 / 100 |

Test suite at audit time: ~728 tests, 14 pre-existing failures.

---

## Wave 0-1 — Completed (June 2026)

All items below are merged to `main` as of 2026-06-21. Test suite: **762 tests, 0 failures** (Wave 2) → **784 tests, 0 failures** (Wave 3).

| ID | Item | Notes |
|---|---|---|
| B3 / C2 | Approval IDOR + self-approval guard | Object-level permission check; users can no longer approve their own requests |
| B4 / C11 | Traceback leak + branded error pages | `DEBUG=False` enforced in production settings; custom 404/500 templates wired |
| 0.2 | Pilot scope flags | `ENABLE_AI`, `ENABLE_BILLING`, `ENABLE_TRUST` default `False`; safe to deploy without live keys |
| C16 | Hermetic test suite | `settings_test.py` strips debug toolbar (was injecting CSRF-less forms and SQL panel HTML into test responses); all 742 tests pass in isolation |
| B1 *(code)* | S3 object storage wiring | Django Storages + `boto3` configured; `DEFAULT_FILE_STORAGE` switches on `AWS_STORAGE_BUCKET_NAME` presence |
| B7 *(code)* | Automated pg_dump backup + GitHub Action | `scripts/backup.sh`, `scripts/restore.sh`, `.github/workflows/db_backup.yml`; passphrase-encrypted, age-verified |
| D1 | Design-system template fixes (14 failures) | KPI strip, tab variables, nav Tasks link, Record Summary / Case Flow / Action Cockpit tabs, contract list columns, debug toolbar stripped from test config |

### Operator steps still outstanding (no code changes needed)

These require infra/secrets work in the Render dashboard or GitHub Actions secrets UI — not code.

| ID | Action | Who |
|---|---|---|
| B1 *(infra)* | Create S3 bucket; set `AWS_STORAGE_BUCKET_NAME`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_S3_REGION_NAME` in Render env | Operator |
| B7 *(infra)* | Set `BACKUP_PASSPHRASE` + `DB_SUPERUSER_URL` in GitHub Actions secrets; run first restore drill against staging | Operator |

---

## Wave 2 — DONE (2026-06-21)

| ID | Task | Status |
|---|---|---|
| B9 | Contract activation ↔ approval coupling | ✅ `ContractUpdateView` rejects ACTIVE status without an approved `ApprovalRequest` |
| B2-lite | Real task scheduler (django-rq + Upstash Redis) | ✅ `django-rq==2.10.2`; `BackgroundJob` model is source of truth; `ASYNC=False` in tests |
| B5 | Retention hold check before deletion | ✅ `Document.delete()` raises `PermissionError` if matter/client is under an active hold |
| B6 | Privacy policy / AI data controls page | ✅ `/privacy/data-controls/` + `OrgPolicy.ai_features_enabled` per-org AI killswitch |
| C14 | CSP violation reporting | ✅ `report-uri /csp-report/` added to CSP header; violations forwarded to Sentry |

---

## Wave 3 — DONE (2026-06-21)

| ID | Task | Status |
|---|---|---|
| C15 | Invite acceptance flow | ✅ Branded GET preview page → POST accept; email mismatch redirects to `/login/` |
| C1 | ALLOWED_HOSTS lockdown | ✅ Already done — `_csv_env('ALLOWED_HOSTS')` in base; production raises `ImproperlyConfigured` if unset |
| SEC-1 | MFA enforcement | ✅ Login flow checks `OrgPolicy.mfa_required`; redirects to `/mfa/enroll/` or `/mfa/challenge/`; `mfa_verified` session flag; `MfaRequiredMixin` for admin views |
| SEC-2 | API key expiry | ✅ `OrganizationAPIToken.expires_at` (migration 0048); `is_expired` property; `_resolve_api_organization()` rejects expired tokens |
| SEC-3 | Audit log tamper detection | ✅ `AuditLog.entry_hash` (migration 0049); SHA-256 stamped in `log_action()`; nightly chain digest GitHub Action (`.github/workflows/audit-log-digest.yml`) |
| C10/D15 | `next` URL open-redirect prevention | ✅ `_safe_next()` helper using `url_has_allowed_host_and_scheme()`; applied to LoginView, mfa_challenge, mfa_challenge_resend |

---

## Wave 4 — Business Features

Can run in parallel with Wave 3. Required for a credible product demo.

| Task | Why It Matters | Complexity | Acceptance Criteria |
|---|---|---|---|
| Stripe billing live | Plan limits are tracked in code but no payment processor collects money | Large | Stripe Checkout + webhook reconciles plan tier; `ENABLE_BILLING=True` gates the flow; test covers failed-payment downgrade |
| Onboarding wire-up (D2) | New orgs see a blank dashboard with no guidance | Medium | First-login wizard: org name → invite team → create first contract → done; dismissible; progress tracked in org settings |
| Reporting exports | Decision-makers need PDF/CSV evidence, not just dashboards | Medium | Contract list, deadline list, and audit log each have an "Export CSV" button; report page exports to PDF via `weasyprint` |
| Saved searches + advanced filters | Power users need faster recall of complex filter combinations | Medium | Users can save a named filter set from any list view; reloaded on return; shareable URL |
| AI drafting quality | AI output can include hallucinated clause text | Medium | AI clause drafts include a `confidence` score; low-confidence suggestions are visually flagged; all AI output is citeable to source text |
| Health check endpoint (D6) | Render health checks call `/` which logs auth errors on every check | Small | `GET /healthz/` returns `{"status":"ok"}` with no auth; checks DB connection and Redis ping; Render health-check URL updated |

---

## Production Readiness Checklist

Items needed before general availability. Some overlap with Wave 3-4.

| Item | Status |
|---|---|
| All 788 tests pass, 0 failures | ✅ Done |
| `DEBUG=False` enforced in production | ✅ Done |
| Branded 404/500 pages | ✅ Done |
| Approval IDOR guard | ✅ Done |
| Object storage wired (code) | ✅ Done |
| Automated backup (code) | ✅ Done |
| Pilot scope flags (`ENABLE_*`) | ✅ Done |
| `ALLOWED_HOSTS` locked to real domain | ✅ Done (Wave 3 / C1) |
| MFA enforcement + enrollment flow | ✅ Done (Wave 3 / SEC-1) |
| API key expiry + rejection | ✅ Done (Wave 3 / SEC-2) |
| Audit log SHA-256 hash stamping | ✅ Done (Wave 3 / SEC-3) |
| Nightly audit digest GitHub Action | ✅ Done (Wave 3 / SEC-3) |
| S3 bucket created + env vars set | ⬜ Operator |
| First backup restore drill completed | ⬜ Operator |
| Custom domain email (`@yourdomain.com`) | ⬜ Needs domain config |
| Stripe collecting live payments | ⬜ Wave 4 |
| Health check endpoint | ⬜ Wave 4 |
| Live smoke test (signup → contract → search) | ⬜ Pre-launch |

---

## Practical Ordering

1. **Operator tasks now** — B1 bucket + B7 backup secrets take 30 minutes; unblock the infra baseline.
2. **Wave 2 sprint** — B9 and B5 are small and close safety gaps; B2-lite and C14 are the bigger investments.
3. **Wave 3 parallel track** — C15 (invite flow) and C1 (ALLOWED_HOSTS) are one-day items; start them early in Wave 2.
4. **Wave 4** — Stripe and onboarding are the pilot-readiness gates; health check is a quick win to do alongside.
5. **Pre-launch** — Live smoke test on Render after Wave 3 merges; restore drill before announcing GA.

---

## Deferred / Dropped Items from Prior Roadmap

The following items from the 2026-04-25 roadmap are deferred because they depended on third-party credentials that are not yet available, or are superseded by the new ordering:

| Item | Disposition |
|---|---|
| Live Salesforce sync evidence | Deferred — no Salesforce org available; revisit if enterprise pilot requires it |
| Live webhook delivery evidence | Deferred — covered by integration observability in Wave 4 |
| PostCSS moderate advisory | Deferred — non-blocking; address in next `npm audit` pass |
| Rollback rehearsal | Merged into the B7 restore drill operator step |
| Signature packet routing hardening | Backlog — Documenso integration already wired; revisit after pilot feedback |
| Workflow builder UX | Backlog — execution model is stable; authoring UX is a Wave 4+ item |
