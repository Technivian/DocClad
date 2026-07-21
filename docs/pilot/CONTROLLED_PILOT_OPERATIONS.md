# Controlled Pilot Operations Pack

**Product:** CLM One  
**Authority:** `docs/governance/GOVERNANCE_CHARTER.md` v2.0, ADR-0009, PDR-0001 (finance threshold), PDR-0002, `docs/audits/PILOT_VERIFICATION_GATE_2026-07-20.md`  
**Mode:** Single-organisation controlled internal pilot  
**Production / enterprise readiness:** Not claimed

---

## 1. Pilot purpose

Prove that the verified CLM One core path works safely for one organisation under real operator use: MSA generate → Legal → Finance (≥ $100,000) → export; NDA/DPA generate → view → Activity; repository Stage/Status; Redis-backed login throttling — without exposing unfinished surfaces.

---

## 2. Approved scope

| Area | Allowed |
|---|---|
| Auth | Login, logout, session idle policy, Redis login throttling |
| MSA | Generate; Send to Legal; Send to Finance at/above $100,000; Export Word; View contract record; Governance/Audit details |
| NDA | Generate; View contract record; Activity / Audit rail (read) |
| DPA | Generate; View contract record; Activity / Audit rail (read) |
| Repository | List; Stage sort; Status filter; governed adjacent Stage transitions via bulk-update API |
| Shell | Command Center; New Contract (MSA/NDA/DPA builders + picker without blank create); Workflow Operations (approval queue) |

Runtime lock: `CONTROLLED_PILOT_ENABLED=true` plus `GEMINI_AI_ENABLED=false`, `BILLING_SELF_SERVE_ENABLED=false`, `TRUST_ACCOUNTING_ENABLED=false`.

---

## 3. Excluded scope

| Excluded | Enforcement |
|---|---|
| NDA signature / export / Legal CTAs | Removed from UI |
| DPA signature / export / Legal / memo CTAs | Removed from UI |
| Freeform `/contracts/new/` create | Middleware redirect + blank card hidden |
| Upload & Review | Nav hidden + route blocked |
| Unrestricted AI | Kill switch + route denylist + org `ai_features_enabled=false` |
| Billing / Stripe self-serve | Flag + route block |
| Law-firm clients / matters / invoices / trust | Nav absent + route block |
| Workflow Designer / approval-rule authoring / DPA review packs / Obligations | Nav hidden + route block |
| Dark theme | Light-first; no toggle in shell |
| Unfinished integrations (signatures module, etc.) | Route block |

Direct URL access to excluded paths redirects authenticated users to the dashboard with a warning.

---

## 4. Named roles and responsibilities

| Role | Username (seed) | Responsibility |
|---|---|---|
| Organisation owner | `pilot_owner` | Overall pilot accountability; suspend authority |
| Administrator | `pilot_admin` | Environment, flags, backups, daily health |
| Business requester | `pilot_requester` | Create MSA/NDA/DPA within scope |
| Legal reviewer | `pilot_legal` | MSA Legal queue / review |
| Finance approver | `pilot_finance` | MSA Finance when threshold met |
| Product/Engineering on-call | (named in launch brief) | Defect triage; suspension support |

Default seed password (change on first live use): `PilotPass123!`  
Organisation: `controlled-pilot-org` / **CLM One Controlled Pilot**

---

## 5. Environment start and reset

### Start (clean state)

```bash
# Local Redis required
redis-cli ping

export CONTROLLED_PILOT_ENABLED=true
export GEMINI_AI_ENABLED=false
export GEMINI_API_KEY=
export BILLING_SELF_SERVE_ENABLED=false
export TRUST_ACCOUNTING_ENABLED=false
export REDIS_URL=redis://127.0.0.1:6379/14

bash scripts/pilot_env_verify.sh
# or for an already-migrated DB:
.venv/bin/python manage.py seed_controlled_pilot --reset-samples
.venv/bin/python manage.py runserver 0.0.0.0:8000
```

### Reset

```bash
rm -f /tmp/clmone-pilot-env-verify.sqlite3   # or pilot DB path
redis-cli -n 14 FLUSHDB
bash scripts/pilot_env_verify.sh
```

### Health checks

```bash
.venv/bin/python manage.py check
curl -fsS http://127.0.0.1:8000/login/ >/dev/null
.venv/bin/python manage.py pilot_daily_health
```

---

## 6. User and role setup

```bash
.venv/bin/python manage.py seed_controlled_pilot --reset-samples
```

Creates one org, five users, Legal/Finance MSA approval rules, sample counterparties, three MSA values (99999 / 100000 / 100001), plus sample NDA and DPA. Does not grant cross-org access.

---

## 7. Approved workflow instructions

1. **MSA:** New Contract → MSA builder → complete required fields → Generate → Actions → Send to Legal → (if value ≥ $100,000) Send to Finance → Export Word → confirm download → View contract record. Confirm Audit/Governance details after submits.
2. **NDA / DPA:** New Contract → NDA or DPA builder → Generate → View contract record → open Activity. Do not expect signature/export/Legal buttons.
3. **Repository:** Contracts → sort Stage → filter Status. Do not skip Stage illegally (bulk API rejects).
4. **Auth:** Failed logins share Redis counters per IP; success clears. Do not share NAT without understanding shared throttle.

---

## 8. Support procedure

1. User reports issue to Administrator (channel agreed at launch).
2. Admin captures: time, username (not password), URL, request_id from UI/logs if available, reproduction steps. **No contract body in tickets.**
3. Classify severity (§9). P0/P1 → consider suspension (§11).
4. Engineering reproduces on pilot DB snapshot; fix only in-scope defects.
5. Record outcome in daily ops log.

---

## 9. Incident severity definitions

| Severity | Definition | Response |
|---|---|---|
| P0 | Tenant leak, auth bypass, data loss/corruption, wrong Finance routing, missing governed AuditLog, unsupported AI processing | Immediate suspend |
| P1 | Repeatable critical workflow failure; widespread 5xx on governed path | Suspend or freeze creates; fix within hours |
| P2 | Single-user blocker with workaround | Same-day triage |
| P3 | Cosmetic / docs / non-blocking | Backlog |

---

## 10. Rollback procedure

1. Stop app workers / `runserver`.
2. Restore DB from last confirmed backup (§13).
3. Flush Redis DB index used by pilot **only if** rate-limit state is corrupt (note: clears throttle counters).
4. Redeploy last known good commit from verification gate.
5. Re-run `manage.py check` + smoke: login, MSA generate, repository.
6. Record rollback in ops log; notify Owner.

---

## 11. Emergency pilot suspension

Owner or Admin may suspend immediately on any P0 criterion (§15 stop criteria).

Steps:

1. Announce suspension to all pilot users.
2. Set `CONTROLLED_PILOT_ENABLED=true` remains; optionally take app offline.
3. Revoke sessions (org MFA/session tools or password resets).
4. Preserve DB + logs; do not “clean up” evidence.
5. Run incident review before any resume.

---

## 12. Daily monitoring checklist

- [ ] `manage.py pilot_daily_health` reviewed
- [ ] Login failures / 429 / 503 rates acceptable
- [ ] HTTP 4xx/5xx not elevated on governed paths
- [ ] MSA Legal / Finance counts match expected activity
- [ ] Finance routing anomalies = 0
- [ ] Export failures = 0
- [ ] Lifecycle transition failures = 0
- [ ] Authorization failures investigated
- [ ] Audit anomalies = 0
- [ ] Background job failures (if RQ used) = 0
- [ ] AI usage/denials consistent with kill switch (expect denials only)
- [ ] Open support requests aged
- [ ] Backup completed / confirmed

---

## 13. Data backup expectations

- Before pilot start: full DB file/snapshot copy into evidence folder or secure backup store.
- Daily during pilot: snapshot before major resets; retain ≥ 14 days.
- Never commit live pilot DB with customer content to git.
- Evidence path for baseline: `docs/audits/evidence/2026-07-20-controlled-pilot-baseline/`

---

## 14. Evidence-retention locations

| Artifact | Location |
|---|---|
| Verification gate | `docs/audits/PILOT_VERIFICATION_GATE_2026-07-20.md` |
| Verification evidence | `docs/audits/evidence/2026-07-20-pilot-verification/` |
| Launch baseline | `docs/audits/evidence/2026-07-20-controlled-pilot-baseline/` |
| Launch readiness | `docs/pilot/CONTROLLED_PILOT_LAUNCH_READINESS.md` |
| Daily health JSON | operator-chosen path / evidence folder |

---

## 15. Success criteria (measurable)

- No tenant-isolation incidents
- No unauthorized actions succeeding
- No data loss or corruption
- Correct Finance routing in **100%** of tested cases (≥ $100,000 triggers Finance; below does not)
- Complete AuditLog history for all governed mutations (MSA Legal/Finance/export; Stage transitions)
- Core workflow completion without developer intervention
- Support-intervention rate **&lt; 10%** of workflow attempts
- No repeatable critical workflow failure

---

## 16. Immediate suspension criteria (stop)

- Cross-tenant data exposure
- Authorization bypass
- Incorrect Finance routing
- Missing audit records for governed mutations
- Contract data corruption or loss
- Unsupported AI processing of contract content
- Repeated critical workflow failure

---

## 17. End-of-pilot review procedure

1. Freeze creates; complete in-flight MSA approvals only if safe.
2. Export final `pilot_daily_health` + incident log.
3. Re-run Django suite + critical Playwright ×2.
4. Compare outcomes to §15 success criteria.
5. Decide: extend pilot / close / remediate before any wider use.
6. Do **not** auto-promote to production or enterprise claims.
