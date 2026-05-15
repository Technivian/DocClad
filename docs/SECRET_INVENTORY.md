# CMS-Aegis Secret & Credential Inventory

> **Purpose** — Single source of truth for every secret, key, credential, and
> token the application depends on. Update this file whenever a secret is
> created, rotated, or revoked.
>
> **DO NOT** store actual secret values here. Record only metadata.

---

## Usage

1. Each row in the table below represents one secret.
2. `Stored In` must point to the exact location (vault path, env var name,
   secret manager key, etc.).
3. `Rotation Due` should be updated every time a secret is rotated.
4. `Owner` is the person/team responsible for rotating the secret.
5. When a secret is rotated, add a row to the [Rotation Log](#rotation-log)
   at the bottom of this file.

---

## Active Secrets

| # | Name | Purpose | Stored In | Format | Rotation Due | Owner | Status |
|---|------|---------|-----------|--------|--------------|-------|--------|
| 1 | `DJANGO_SECRET_KEY` | Django CSRF / session signing | `.env` → `SECRET_KEY` | 50-char random string | 2026-10-04 | DevOps | ✅ Active |
| 2 | `OIDC_RP_CLIENT_ID` | Google OAuth 2.0 client ID | `.env` → `OIDC_RP_CLIENT_ID` | Google OAuth client ID string | N/A (rotate if compromised) | DevOps | ✅ Active |
| 3 | `OIDC_RP_CLIENT_SECRET` | Google OAuth 2.0 client secret | `.env` → `OIDC_RP_CLIENT_SECRET` | Google OAuth client secret | **⚠️ OVERDUE — rotate before next deploy** | DevOps | ⚠️ Needs rotation |
| 4 | `DATABASE_URL` | Database connection string | `.env` → `DATABASE_URL` | DSN string | 2027-04-04 | DevOps | ✅ Active |
| 5 | `DEFAULT_FROM_EMAIL` | Outbound email identity | `.env` → `DEFAULT_FROM_EMAIL` | Email address | N/A | DevOps | ✅ Active |
| 6 | `EMAIL_HOST_PASSWORD` | SMTP authentication | `.env` → `EMAIL_HOST_PASSWORD` | SMTP password | 2026-10-04 | DevOps | ✅ Active |
| 7 | CI `DJANGO_SECRET_KEY` | GitHub Actions test suite | GitHub repo → Settings → Secrets → `DJANGO_SECRET_KEY` | Same as #1 | 2026-10-04 | DevOps | ✅ Active |
| 8 | CI `OIDC_RP_CLIENT_SECRET` | GitHub Actions OIDC tests | GitHub repo → Settings → Secrets → `OIDC_RP_CLIENT_SECRET` | Same as #3 | **⚠️ OVERDUE — rotate before next deploy** | DevOps | ⚠️ Needs rotation |

---

## Rotation Procedures

### `DJANGO_SECRET_KEY` (row 1 & 7)

```bash
# Generate new key
python -c "
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
"
# 1. Update .env SECRET_KEY with the new value
# 2. Update GitHub repo secret DJANGO_SECRET_KEY
# 3. Restart the application server
# 4. All active sessions are invalidated (users must re-login — expected)
```

### `OIDC_RP_CLIENT_SECRET` (row 3 & 8) — ⚠️ ROTATE NOW

```
1. Go to: https://console.cloud.google.com/
   → APIs & Services → Credentials → OAuth 2.0 Client IDs
   → Select the CMS-Aegis client
   → "Reset Secret" (or "Add Secret")

2. Copy the new secret value.

3. Update local .env:
   OIDC_RP_CLIENT_SECRET=<new-value>

4. Update GitHub Actions secret:
   gh secret set OIDC_RP_CLIENT_SECRET --body "<new-value>"

5. Restart the application server:
   sudo systemctl restart gunicorn-cms-aegis

6. Test SSO login end-to-end in staging before deploying to production.

7. Record the rotation in the log below.
```

### `EMAIL_HOST_PASSWORD` (row 6)

```
1. Rotate in your SMTP provider (Mailgun / SendGrid / Google Workspace)
2. Update .env EMAIL_HOST_PASSWORD
3. Restart the application
4. Send a test email via Django shell:
   python manage.py shell -c "
   from django.core.mail import send_mail
   send_mail('Test', 'body', None, ['admin@example.com'])
   "
```

---

## Environment File Template

Copy this to `.env` and populate all values. Never commit the populated file.

```env
# Django
SECRET_KEY=<50-char-random-string>
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database
DATABASE_URL=postgres://user:password@host:5432/cms_aegis

# Google SSO (mozilla-django-oidc)
OIDC_RP_CLIENT_ID=<google-oauth-client-id>
OIDC_RP_CLIENT_SECRET=<google-oauth-client-secret>
SSO_ENABLED=true

# Email
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.mailgun.org
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=<smtp-user>
EMAIL_HOST_PASSWORD=<smtp-password>
DEFAULT_FROM_EMAIL=noreply@yourdomain.com
```

---

## .env Security Checklist

- [ ] `.env` is listed in `.gitignore`
- [ ] `.env` is not committed to the repository (confirm with `git log -- .env`)
- [ ] Production `.env` is only readable by the deploy user (`chmod 600 .env`)
- [ ] CI secrets are stored in GitHub repo Secrets (never in YAML files)
- [ ] `OIDC_RP_CLIENT_SECRET` was rotated after the April 2026 exposure (still pending as of 2026-05-15)

---

## Rotation Log

| Date | Secret | Rotated By | Reason | Notes |
|------|--------|------------|--------|-------|
| 2026-04-04 | (baseline) | DevOps | Initial inventory created | No secrets rotated yet |
| _(pending)_ | `OIDC_RP_CLIENT_SECRET` | DevOps | Exposed in local chat session (2026-04-05) | Rotate via Google Cloud Console — see row 3 procedure above |

---

*Last updated: 2026-05-15*
