# Manual Smoke Signoff

Date: 2026-06-01

## Environment

- Local development environment
- Django dev server: `http://127.0.0.1:8060`
- Database: shared local SQLite (`db.sqlite3`)
- Commit: current workspace HEAD

## Test Accounts Used

- `smoke-owner` / `smoke-pass-123`
- `admin` / `admin123`

## Checks Performed

- Anonymous `/dashboard/` redirected to `/login/`
- SAML selector listed a SAML-enabled organization
- Identity settings showed SCIM users, SCIM groups, and approval-routing links
- MFA profile page showed the MFA-required banner
- Recovery-code generation flow rendered successfully
- Organization security page showed MFA policy controls
- Workflow dashboard showed approval-rules and approval-requests actions
- Workflow detail showed conditional routing and approval request panels

## Result

- PASS

## Notes

- This is a local rehearsal signoff, not a production cutover signoff.
- The browser smoke used a seeded local `smoke-owner` org/user and the seeded `admin` account.
