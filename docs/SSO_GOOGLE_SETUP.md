# Google SSO Setup (OIDC)

This project uses **mozilla-django-oidc** for Google OAuth 2.0 / OIDC sign-in.

---

## 1. Google Cloud Console setup

1. Go to https://console.cloud.google.com/ → **APIs & Services → Credentials**
2. Click **+ Create Credentials → OAuth 2.0 Client ID**
3. Application type: **Web application**
4. Under **Authorized redirect URIs** add **all** of the following:

   | Environment | Redirect URI |
   |-------------|--------------|
   | Local dev   | `http://127.0.0.1:8000/oidc/callback/` |
   | Staging     | `https://staging.yourdomain.com/oidc/callback/` |
   | Production  | `https://yourdomain.com/oidc/callback/` |

5. Under **Authorized JavaScript origins** add your base URLs (no trailing slash):
   - `http://127.0.0.1:8000`
   - `https://yourdomain.com`

6. Configure the **OAuth consent screen**:
   - User type: **Internal** (recommended — limits logins to your Google Workspace domain)
   - Scopes needed: `openid`, `email`, `profile`

7. Note down the **Client ID** and **Client Secret** — you will need them below.

> ⚠️ **Security reminder**: The `OIDC_RP_CLIENT_SECRET` is currently flagged as
> **OVERDUE for rotation** in `docs/SECRET_INVENTORY.md`. Rotate it before
> deploying to a shared or production environment.

---

## 2. Environment variables

Set these in `.env` (never commit this file):

```env
# Enable SSO login button and OIDC flow
SSO_ENABLED=true

# Credentials from Google Cloud Console (keep secret)
OIDC_RP_CLIENT_ID=<GOOGLE_CLIENT_ID>
OIDC_RP_CLIENT_SECRET=<GOOGLE_CLIENT_SECRET>

# Scopes
OIDC_RP_SCOPES=openid email profile

# Google OIDC endpoints (these are stable Google-published values)
OIDC_OP_DISCOVERY_ENDPOINT=https://accounts.google.com/.well-known/openid-configuration
OIDC_OP_AUTHORIZATION_ENDPOINT=https://accounts.google.com/o/oauth2/v2/auth
OIDC_OP_TOKEN_ENDPOINT=https://oauth2.googleapis.com/token
OIDC_OP_USER_ENDPOINT=https://openidconnect.googleapis.com/v1/userinfo
OIDC_OP_JWKS_ENDPOINT=https://www.googleapis.com/oauth2/v3/certs

# Optional: restrict login to specific email domains (comma-separated)
# If unset, any Google account can sign in.
# SSO_ALLOWED_EMAIL_DOMAINS=yourcompany.com,partner.com
```

---

## 3. Install dependency

```bash
.venv/bin/pip install mozilla-django-oidc
```

The package is already in `requirements.txt`. This step is only needed for a
fresh venv.

---

## 4. Run and test

```bash
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

1. Open `http://127.0.0.1:8000/login/`
2. Click **Sign in with SSO**
3. Complete the Google OAuth flow
4. You should land on `/dashboard/`

If the button is missing, verify `SSO_ENABLED=true` is present in `.env` and
that `mozilla_django_oidc` is in `INSTALLED_APPS` (it is added automatically
when the package is installed and `SSO_ENABLED` is set).

---

## 5. OIDC routes

When `SSO_ENABLED=true`, Django mounts these URLs under `/oidc/`:

| URL | Purpose |
|-----|---------|
| `/oidc/authenticate/` | Initiates the Google login flow |
| `/oidc/callback/` | Google redirects here after login |
| `/oidc/logout/` | OIDC-aware logout |

---

## 6. Behaviour notes

- **Password login** remains available for users who don't use SSO.
- **Auto-provisioning**: users are created on first SSO login and matched by
  email address on subsequent logins.
- **Domain restriction**: if `SSO_ALLOWED_EMAIL_DOMAINS` is set, any Google
  account whose email domain is not in the list is denied with a 403.
- **Signing algorithm**: RS256 (Google default, matches `OIDC_RP_SIGN_ALGO`).

---

## 7. Rotating the client secret

See `docs/SECRET_INVENTORY.md` → row 3 (`OIDC_RP_CLIENT_SECRET`) for the
step-by-step rotation procedure including updating the GitHub Actions secret.
