# AGENTS.md

## CLM One mandatory documentation

Before performing material product, architecture, design, database,
security, workflow, AI, integration, or engineering work, read:

1. `docs/governance/GOVERNANCE_CHARTER.md`
2. `docs/product/MASTER_BLUEPRINT.md`
3. `docs/product/CANONICAL_DOMAIN_MODEL.md`
4. `docs/architecture/PLATFORM_AND_MODULE_ARCHITECTURE.md`
5. `docs/engineering/ENGINEERING_GUARDRAILS.md`

Then read the domain-specific documentation relevant to the task.

For workflow work, also read:

- `docs/architecture/WORKFLOW_ENGINE_AND_DESIGNER.md`

For UI, navigation, terminology, or design work, also read:

- `docs/product/UX_NAVIGATION_AND_WORK_SURFACES.md`

For data, AI, extraction, search, or analytics work, also read:

- `docs/architecture/DATA_AI_AND_INTELLIGENCE.md`

For authentication, authorization, privacy, audit, exports, or security work, also read:

- `docs/architecture/SECURITY_PRIVACY_ACCESS_AND_AUDIT.md`

For roadmap or release-readiness work, also read:

- `docs/roadmap/DELIVERY_ROADMAP_AND_RELEASE_GATES.md`

Documentation index: `docs/README.md`.

The current approved Governance Charter remains authoritative:

- Active: `docs/governance/GOVERNANCE_CHARTER.md`
- Proposed (not approved): `docs/governance/GOVERNANCE_CHARTER_V3_PROPOSED.md`

Accepted supporting documentation (PDR-0003) does not amend the constitution.
Proposed documents (including Charter v3) do not supersede approved governance until formally approved.

Current code does not override approved governance documentation.

If implementation conflicts with the approved Charter or an approved decision record:

1. stop;
2. identify the conflict;
3. do not silently work around it;
4. propose the required PDR, ADR, Charter amendment, or exception.

Do not silently introduce new:

- domain objects;
- modules;
- roles;
- statuses;
- permissions;
- lifecycle stages;
- terminology;
- architecture patterns.

Decision records live under `docs/governance/decisions/`. See `docs/governance/decisions/README.md`.

## GitHub review and release evidence

For new authorization and release work, use GitHub submitted PR reviews, CI
results, immutable reviewed and merged SHAs, and deployment or operator logs
as evidence. Do not create or rely on manual vote tables, copied approval
statements, or manually entered approval timestamps. Historical evidence is
preserved and must not be rewritten.

- Low-risk default-off work: green CI and normal review.
- Non-production canonical authority: an approved GitHub review by the named
  Release Authority (`@haroonwahed`), green CI for the unchanged reviewed SHA,
  reversible default-off flags, documented abort/rollback controls, and a
  named-environment operator record.
- Single-maintainer exception: only when GitHub shows exactly one direct human
  collaborator with push or admin access, a repository-owner GitHub attestation
  may replace independent review for a non-production, reversible, default-off
  change. It must name the exact SHA, have green CI and unchanged scope, retain
  documented abort/rollback and an operator record, and restore flags off after
  observation. It never applies to the actions in the next bullet.
- Production activation, permission or privilege changes, automatic repair,
  ADMIN authority, and legacy retirement: approved Product, Engineering, and
  Security GitHub reviews that are independent of one another, plus green CI
  and a release record.

A feature flag does not grant authority. Never enable one before the
applicable gate is satisfied.

## Cursor Cloud specific instructions

CLM One is a single Django 5.2 app (project `config`, main domain app `contracts`, Tailwind theme app `theme`). Dev runs on SQLite with all third-party integrations (Redis, Stripe, Gemini AI, S3, OIDC/SAML SSO, Salesforce, NetSuite, e-sign) feature-flagged off, so no external services are needed to run or test it.

### Environment
- Python 3.12 virtualenv lives at `.venv/`. Always invoke it explicitly (e.g. `.venv/bin/python manage.py ...`); the repo's `Makefile` and helper scripts assume `.venv`.
- The repo's `scripts/bootstrap_python312.sh` uses `uv`, but `uv` is not installed here. The environment is set up with a plain `python3 -m venv .venv` + `pip install -r requirements.txt` (which pulls `requirements/dev.txt` → `requirements/runtime.txt`). The update script handles this refresh automatically.
- `.env` (gitignored) is required and already created from `.env.example` with a dev `DJANGO_SECRET_KEY`. Settings auto-load `.env` via `config/settings_base.py`. Keep `DATABASE_URL` empty so dev uses SQLite; a dev safety guard refuses to start against a non-local `DATABASE_URL`.

### Run
- Dev server (foreground): `bash scripts/dev_server.sh`
- Dev server (background, supervised autoreload): `bash scripts/dev_up.sh` / `bash scripts/dev_restart.sh` (foreground, port 8060, forces `DJANGO_SETTINGS_MODULE=config.settings_development` and empty `DATABASE_URL`). App at `http://127.0.0.1:8060/`, health at `/_health/`, auth at `/login/` and `/register/`.
- Registering at `/register/` auto-provisions an organization and logs you in (lands on `/dashboard/`).
- After changing models, run `.venv/bin/python manage.py migrate` manually (migrations are intentionally not in the update script). The dev `db.sqlite3` persists across sessions.

### Lint / test / build
- Tests: `make test` (full suite, forces `config.settings_test` = in-memory SQLite). Subset: `make test-fast APP=tests.<module>`. Django checks: `make check`.
- Known pre-existing test drift (NOT caused by environment setup): the suite currently has failures/errors from an in-progress Contract status/`lifecycle_stage` refactor (e.g. `'ContractForm' has no field named 'status'`, status/stage combination validation, `Document.Status`/lifecycle choices set mismatches). Additionally 3 test modules (`tests/test_canonical_url_builder.py`, `tests/test_5i_document_durability.py`, `tests/conftest.py`) import `pytest`, which is not a declared dependency and is skipped by the Django test runner. Do not treat these as regressions from setup.
- Static assets: compiled Tailwind CSS is committed under `theme/static/`, so no Node build is needed to run the app. Only rebuild styles when editing them: `cd theme/static_src && npm install && npm run dev`.
