# Controlled Pilot Launch Readiness

**Date:** 2026-07-20  
**Authority:** `docs/governance/GOVERNANCE_CHARTER.md` v2.0, ADR-0009, PDR-0001 (finance threshold), PDR-0002, `docs/audits/PILOT_VERIFICATION_GATE_2026-07-20.md`, `docs/pilot/CONTROLLED_PILOT_OPERATIONS.md`  
**Production / enterprise readiness:** Not claimed

---

## Decision

# **READY**

CLM One is ready to execute the **approved single-organisation controlled pilot** under the locked scope below. This is not production or enterprise readiness.

---

## Allowed workflows

- Authentication with Redis-backed login throttling  
- MSA generate → Legal submit → Finance submit (≥ $100,000) → Export Word → View record  
- NDA generate → View record → Activity  
- DPA generate → View record → Activity  
- Contracts repository (Stage sort / Status filter / governed Stage transitions)  
- Workflow Operations queue (approval visibility for Legal/Finance)  
- Command Center / New Contract picker (MSA/NDA/DPA builders only; blank create hidden)

---

## Excluded workflows

- NDA/DPA signature, export, Legal/memo CTAs (absent from UI)  
- Freeform `/contracts/new/` create (blocked + blank card hidden)  
- Upload & Review  
- Unrestricted AI (`GEMINI_AI_ENABLED=false`, org AI policy off, AI routes denied)  
- Billing / Stripe self-serve  
- Law-firm clients, matters, invoices, trust accounting  
- Workflow Designer / approval-rule authoring / DPA review packs / Obligations  
- Dark theme  
- Signature module and other unfinished integrations  

Direct URL access to excluded paths redirects to dashboard (authenticated) or login.

---

## Environment details

| Item | Value |
|---|---|
| Org | `controlled-pilot-org` / CLM One Controlled Pilot |
| Seed | `manage.py seed_controlled_pilot` |
| Bootstrap | `scripts/pilot_env_verify.sh` |
| DB (verify) | `/tmp/clmone-pilot-env-verify.sqlite3` (+ baseline backup copy) |
| Redis | `redis://127.0.0.1:6379/14` (verify) / pilot host Redis for live throttle |
| Ops pack | `docs/pilot/CONTROLLED_PILOT_OPERATIONS.md` |
| Daily health | `manage.py pilot_daily_health` |

---

## Participating roles

| Username | Membership | Pilot duty |
|---|---|---|
| `pilot_owner` | OWNER | Accountability / suspension |
| `pilot_admin` | ADMIN | Ops, flags, backups, health |
| `pilot_requester` | MEMBER | Create MSA/NDA/DPA |
| `pilot_legal` | MEMBER | Legal review |
| `pilot_finance` | MEMBER | Finance approval |

Seed password (change on live start): `PilotPass123!`  
Evidence: `docs/audits/evidence/2026-07-20-controlled-pilot-baseline/roles-and-flags.txt`

---

## Test results

| Suite | Result | Evidence |
|---|---|---|
| Django full suite | **Ran 2093 tests — OK (skipped=32)** | `.../django-suite.txt` |
| Pilot scope unit tests | **PASS** (blocked + allowed routes) | `.../excluded-route-checks.txt` |
| Critical Playwright run 1 | **27 passed** | `.../playwright-run1.txt` |
| Critical Playwright run 2 | **27 passed** | `.../playwright-run2.txt` |
| Baseline screenshots | **1 passed** (8 PNGs) | `.../screenshots/` |
| `pilot_env_verify.sh` | **PASS** | `.../pilot-env-setup.log` |
| Governance authority | **OK** (prior gate; charter unchanged) | `scripts/check_governance_authority.sh` |

---

## Feature-flag state (pilot lock)

```
CONTROLLED_PILOT_ENABLED=true
GEMINI_AI_ENABLED=false
BILLING_SELF_SERVE_ENABLED=false
TRUST_ACCOUNTING_ENABLED=false
FINANCE_APPROVAL_THRESHOLD=100000
```

Captured in `feature-flags.txt` and `pilot-daily-health-sample.json`.

---

## Monitoring status

- Request metrics via existing middleware / `request_metrics_snapshot`  
- Daily JSON summary: `manage.py pilot_daily_health` (no contract content/credentials)  
- Tracks: login failures, HTTP status buckets, failed actions, Legal/Finance/export approximations, lifecycle/authz/audit/AI denial signals  
- Operator checklist in operations pack §12  

---

## Backup confirmation

- Snapshot copied to `docs/audits/evidence/2026-07-20-controlled-pilot-baseline/pilot-db-backup.sqlite3`  
- Size recorded in `backup-confirmation.txt`  
- Reset procedure documented in operations pack  

---

## Rollback readiness

Documented in `CONTROLLED_PILOT_OPERATIONS.md` §§10–11:

1. Stop workers  
2. Restore DB snapshot  
3. Optional Redis FLUSHDB for throttle corruption only  
4. Redeploy last known-good commit  
5. Smoke login + MSA generate + repository  

Emergency suspension criteria match verification gate stop rules.

---

## Known limitations

- Single organisation only  
- Search AI uses kill-switch-safe fallback (no live Gemini in pilot)  
- IP-keyed login throttle may couple users behind shared NAT  
- Workflow Designer / Obligations / Upload intentionally unavailable  
- No docker-compose pilot appliance; scripts are the bootstrap path  
- Not production or enterprise hardened  

---

## Baseline evidence index

`docs/audits/evidence/2026-07-20-controlled-pilot-baseline/`

- `django-suite.txt`  
- `playwright-run1.txt` / `playwright-run2.txt`  
- `playwright-screenshots.txt` + `screenshots/*.png`  
- `pilot-env-setup.log`  
- `pilot-daily-health-sample.json`  
- `feature-flags.txt` / `roles-and-flags.txt`  
- `excluded-route-checks.txt`  
- `health-check.txt`  
- `backup-confirmation.txt` / `pilot-db-backup.sqlite3`  

---

## Final decision

| Question | Answer |
|---|---|
| Ready for controlled pilot execution? | **YES — READY** |
| Production ready? | **No** |
| Enterprise ready? | **No** |
| Scope expandable without new gate? | **No** |
