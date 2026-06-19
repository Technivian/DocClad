# Pilot Launch Checklist — CMS Aegis

Scope: take the current `main` into a **controlled pilot** (real tenants, real
data) on a single production environment. This is not a wide public launch —
see "Known caveats" at the end for what is intentionally still stubbed.

Owner: ______   Target date: ______   Sign-off: ______

---

## 0. Pre-flight (code is already here)

- [ ] On `main`, clean tree, CI green (see §7). Current tip should be the
      pushed release commit.
- [ ] `pip install -r requirements/dev.txt` locally; `.venv/bin/python manage.py check` clean.
- [ ] Tag the release: `git tag -a vX.Y.Z -m "pilot launch" && git push origin vX.Y.Z`.

## 1. Infrastructure

- [ ] **PostgreSQL provisioned** (managed instance preferred). Production
      settings *refuse to boot* on anything other than `django.db.backends.postgresql`
      (`config/settings_production.py`). Set `DATABASE_URL=postgresql://…`.
- [ ] Connection pooling / max-connections sized for the app + background workers.
- [ ] App served via **gunicorn** behind TLS (HTTPS terminates at the proxy;
      `SECURE_SSL_REDIRECT`, HSTS, secure cookies are already on in prod settings).
- [ ] Static files collected: `python manage.py collectstatic --noinput`
      (WhiteNoise serves them; confirm `css/dist/styles.css` and
      `js/csp-handlers.js` are present in `staticfiles/`).
- [ ] Background job workers running (see `.github/workflows/*-scheduler.yml`
      for the job types: contract-lifecycle, retention, reminders, bg-job-worker).

## 2. Secrets & configuration (production env vars)

- [ ] `DJANGO_ENV=production`
- [ ] `DJANGO_SECRET_KEY` — **50+ random chars** (the deploy check warns W009 on
      weak keys). Do not reuse the dev value.
- [ ] `ALLOWED_HOSTS` — real hostnames (prod refuses empty).
- [ ] `CSRF_TRUSTED_ORIGINS` — `https://<your-host>`.
- [ ] `DEFAULT_FROM_EMAIL` + SMTP/email backend configured.
- [ ] **Rotate the Google OAuth client secret** currently in the local `.env`
      if it is a real credential, and set `OIDC_RP_CLIENT_ID` /
      `OIDC_RP_CLIENT_SECRET` / OIDC endpoints in the prod env (never commit them).
- [ ] `ESIGN_*` — see §4.
- [ ] Confirm `.env` is **not** deployed; prod reads real env vars.
- [ ] `python manage.py check --deploy --fail-level WARNING` passes with the
      real SECRET_KEY (0 issues).

## 3. Data & migrations

- [ ] Apply migrations on the prod DB: `python manage.py migrate`.
- [ ] **Validate migration 0045 backfill against real data.** It assigns
      `WorkflowTemplate.organization` only when a template's workflows belong to
      exactly one org; multi-org / unused templates stay shared (null = visible
      to all tenants). Before/after a dry run, confirm no tenant-private template
      becomes globally shared:
      `SELECT id, name, organization_id FROM contracts_workflowtemplate;`
- [ ] Run the tenant integrity audit: `python manage.py audit_null_organizations`.
- [ ] Seed initial org(s)/owner accounts; verify first-login provisioning.

## 4. E-signature (functional decision required)

The outbound sender defaults to a **simulated** provider — it returns fake
references and never contacts a real service.

- [ ] Decide one:
  - [ ] **Wire a real provider** — set `ESIGN_PROVIDER=docusign` (or `http`) plus
        the provider creds (see `contracts/services/signature_providers.py`).
        Send one real test envelope end-to-end and confirm the inbound webhook
        reconciles status (PENDING→SENT→…→SIGNED).
  - [ ] **Disable e-sign for the pilot** — hide the "Send for signature" action /
        don't enable the feature for pilot tenants, so no one hits a no-op send.
- [ ] If using webhooks, set `ESIGN_WEBHOOK_SECRET` and register the callback URL.

## 5. Security verification

- [ ] CSP: confirm the response header on a live page has `nonce-…` and **no**
      `unsafe-inline`; check the browser console shows **no CSP violations**.
- [ ] Cross-tenant smoke: log in as two orgs, confirm neither sees the other's
      contracts/trust accounts/templates (the regression suite covers this, but
      re-verify on real data).
- [ ] Rate limiting active (`RATELIMIT_ENABLED=true`) and a shared cache backend
      configured (Redis/memcached) — per-process LocMem won't throttle across
      gunicorn workers. **Set `CACHES` to a shared backend.**
- [ ] MFA / SSO (SAML/OIDC/SCIM) configured for pilot tenants as needed.

## 6. Backup, restore & rollback (the project's stated gap — do not skip)

- [ ] Automated DB backups scheduled; retention set.
- [ ] **Restore drill**: restore a backup into a scratch DB and boot the app
      against it. Record the time-to-restore.
- [ ] **Rollback rehearsal**: document the exact steps to roll back the app
      release + (if needed) the DB, and test them on staging.
- [ ] Define rollback triggers (error-rate / 5xx / failed migration) before launch.

## 7. CI / observability

- [ ] GitHub Actions `Platform Guardrails` green on `main` (Django check,
      migrations committed, mypy, cross-tenant isolation, perf guardrails,
      security scans). See §c task.
- [ ] `pip-audit` / `bandit` / `npm audit` clean (security-sla-watch workflow).
- [ ] Health endpoint `/_health/` monitored; DB-latency thresholds wired.
- [ ] Request logging shipping (request_id/user_id/org_id are emitted); error
      tracking (Sentry or equiv) configured.
- [ ] SLO alerts on p95 latency / 5xx rate.

## 8. Go / No-Go

- [ ] All §1–§6 boxes checked, CI green, restore + rollback rehearsed.
- [ ] Pilot tenant list confirmed; support/escalation path agreed.
- [ ] Owner sign-off: ______

---

## Known caveats (intentionally stubbed for pilot)

These are **not** blockers for a scoped pilot but must not be marketed as
delivered:

- **AI features are deterministic stubs** — clause extraction (regex),
  drafting (template lookup), and "semantic" search (keyword + synonyms) are
  rule-based, not LLM-backed. Auditable, but not differentiated vs. Ironclad.
- **No redlining / Word round-trip.**
- **Integrations (Salesforce/NetSuite/webhooks) lack live end-to-end proof** —
  code paths exist; no production evidence captured yet.
