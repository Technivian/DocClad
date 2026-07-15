# Production Configuration Gate (Phase 5D)

`config.settings_production` fails closed at boot on unsafe configuration. The
settings module is selected by the `config.settings` dispatcher when
`DJANGO_ENV=production` (set in the Render `clmone-shared` env group, so web,
worker and cron all run production settings against the shared `DATABASE_URL`).

## Enforced rejections (boot-time `ImproperlyConfigured`)

| Unsafe condition | Result |
|---|---|
| `DJANGO_DEBUG=true` | rejected |
| Missing `ALLOWED_HOSTS` | rejected |
| Missing `CSRF_TRUSTED_ORIGINS` | rejected |
| Default placeholder `DEFAULT_FROM_EMAIL` | rejected |
| Missing / weak `DJANGO_SECRET_KEY` (<32 chars or dev markers) | rejected |
| Non-PostgreSQL database (e.g. SQLite) | rejected unless `ALLOW_SQLITE_IN_PRODUCTION` |
| Ephemeral media (`MEDIA_STORAGE_BACKEND != s3`) | rejected unless `ALLOW_EPHEMERAL_MEDIA_IN_PRODUCTION` |
| `s3` backend without `AWS_STORAGE_BUCKET_NAME` | rejected |

Always-on hardening (not env-overridable): `SESSION_COOKIE_SECURE`,
`CSRF_COOKIE_SECURE`, `SECURE_CONTENT_TYPE_NOSNIFF` are forced `True`. HSTS and
SSL redirect default on. Secret values are never echoed in error messages.

All rejections are covered by executable tests in
`tests/test_production_config_gate.py`.

## Emergency bypass flags — temporary-exception process

Two bypass flags exist for emergencies only. Both default to **false/absent** and
are **absent from the pilot `render.yaml`**:

- `ALLOW_SQLITE_IN_PRODUCTION`
- `ALLOW_EPHEMERAL_MEDIA_IN_PRODUCTION`

When either is enabled, production boot emits a **HIGH SEVERITY** warning on every
start (Python warning + `clmone.production` logger `CRITICAL`). Enabling a bypass
requires, before it is set:

1. **Technical Owner** approval (named).
2. A written **rationale** (why the safety guard must be bypassed).
3. An **expiry date** — the flag must be removed by this date.
4. An entry in the operations log (who/why/when/expiry).

A bypass is never a steady-state configuration. The boot warning is intentional
and must not be suppressed. Removing the flag restores the fail-closed guard.

## Intended pilot configuration (must hold for GO)

- `DJANGO_ENV=production`, `DJANGO_DEBUG` unset/false
- `DATABASE_URL=postgresql://…` (durable PostgreSQL)
- `MEDIA_STORAGE_BACKEND=s3` + bucket/credentials (operator-provisioned)
- strong `DJANGO_SECRET_KEY`, real `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` / `DEFAULT_FROM_EMAIL`
- **no** `ALLOW_SQLITE_IN_PRODUCTION`, **no** `ALLOW_EPHEMERAL_MEDIA_IN_PRODUCTION`

> Operator-supplied secrets/resources are placeholders here and listed in the
> Phase 5 external-actions section — none are invented.
