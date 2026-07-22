# PAR-ID-001 R5 exit report — controlled canonical authority cutover

**Authorization:** [`CANONICAL_RESOLVER_AUTHORITY_CUTOVER_AUTHORIZATION.md`](CANONICAL_RESOLVER_AUTHORITY_CUTOVER_AUTHORIZATION.md)  
**Motions 1–4:** Carried (`2026-07-22T20:38:16Z` / `20:38:17Z` / `20:38:18Z`; Security conditions 1–10 acknowledged: yes)  
**Package baseline:** `198ed13c93e56fdabb3d0e72246225284a619fc3`  
**Deployed HEAD:** `058c5ed09cb79b9460cb875e80a9d5ad0cc9367d` (exact match)  
**Named environment:** `par-id-001-r5-staging-equivalent`  
**Environment path:** `staging_env/` (ephemeral SQLite; DB gitignored)  
**Activation:** `2026-07-22T20:46:15Z`  
**Observation end / flag-off:** `2026-07-22T20:48:20Z`  
**Verdict:** **Completed, PASS**  
**Incident rollback (Motion 3 abort):** **Not required**  
**PAR-ID-001:** **Completed**

**Do not use** `CANONICAL_RESOLVER_ACTIVATION_AUTHORIZATION.md` for this gate.

---

## Operators

| Role | Identity |
|---|---|
| Cutover operator | Engineering (@Technivian) |
| Rollback operator | Engineering (@Technivian) |
| Monitoring owner | Engineering (@Technivian) |

---

## Flag state

| Phase | SHADOW | PARITY_REPORTING | RESOLVER_PARITY | CANONICAL | ALLOWLIST |
|---|---|---|---|---|---|
| Before | false | false | false | false | empty |
| During (authorized) | false | false | **true** | **true** | `controlled-pilot-org` |
| After successful observation | false | false | false | false | empty |
| Committed defaults | false | false | false | false | empty |

Sources: `pending/flag_state_before.txt`, `pending/flag_state_during.txt`, `pending/flag_state_after.txt`, `pending/committed_defaults_check.txt`.

---

## Assignment parity (during)

| Metric | Count |
|---|---:|
| Total rows | 20 |
| CERTAIN missing | **0** |
| CERTAIN MATCH_ACTIVE | **12** |
| AMBIGUOUS ADMIN rows | **8** |

Source: `pending/assignment_parity_during.json` / `pending/scenarios_executed.json`.

---

## Resolver parity (authoritative during)

| Metric | Count |
|---|---:|
| total_comparisons | **94** |
| MATCH | **89** |
| AMBIGUOUS | **5** |
| LEGACY_ONLY | **0** |
| CANONICAL_ONLY | **0** |
| DIFFERENT_USER | **0** |
| DIFFERENT_ROLE | **0** |
| INACTIVE_ASSIGNMENT | **0** |
| CROSS_TENANT_ANOMALY | **0** |
| RESOLUTION_ERROR | **0** |
| critical_drift_count | **0** |

Source: `pending/resolver_parity_during.json`.

---

## Authority path observations

- Allowlisted CERTAIN `ASSOCIATE` rule on `controlled-pilot-org` → `pilot_legal`; `role.resolver.canonical_used` with `authoritative_for_runtime=true`  
- Non-allowlisted orgs → legacy path (`organization_not_allowlisted` / no canonical_used delta after flag-off)  
- ADMIN / AMBIGUOUS → cutover excluded; legacy returned  
- Inactive PRA → legacy fallback  
- Cross-tenant → fail closed (`None`) + `role.resolver.cross_tenant_anomaly`  
- Canonical failure → legacy fail-open + `role.resolver.canonical_failure`  

Source: `pending/authority_path_probes.json`, `pending/fail_open_probe.json`, `pending/monitoring.txt`.

---

## Scenarios

All required scenarios **EXERCISED** (plus allowlist authority probe). See `pending/scenarios_executed.json`.

---

## Tests / check

- `manage.py check` — no issues (`pending/django-check.txt`)  
- Targeted PAR-ID-001 suites — OK (canonical authority 17, resolver parity 18, shadow 10, R1 10, assignment 17, characterization 19, role definition 17)  
- `scripts/check_governance_authority.sh` — OK  

---

## Disclosure

- Local staging-equivalent only; no remote shared staging URL  
- Observation window covers required scenario/parity/authority matrix; not a 60-minute remote ops watch  
- Intentional fail-open / inactive probes produce expected stderr ERROR logs  
- Pilot org has ApprovalRule paths (no WorkflowTemplateSteps); both approved resolver paths exercised across corpus  

---

## Separately blocked (not authorized by R5 PASS)

- Production activation  
- Legacy retirement  
- ADMIN authority / automatic ADMIN mapping (PAR-ID-002 / P2)  
- Sustainment of `PROCESS_ROLE_CANONICAL_RESOLVER_ENABLED=true` outside a newly voted window  
- Permission / privilege / membership / navigation changes  

---

## Final runtime authority

After observation flag-off: **legacy resolver authoritative**; committed defaults remain **false**.
