# PAR-EXC-001 — Migration and cutover plan

## Migration `0114_exception_request_decision`

| Item | Detail |
|---|---|
| Type | Additive CreateModel only |
| Tables | `contracts_exceptionrequest`, `contracts_exceptiondecision` |
| Backfill | **None** — inventing authority/owner/expiry for legacy rows would falsify governance |
| Rollback | Reverse migration drops both tables (safe while no production writers depend on them) |
| Depends on | `0113_process_role_assignment` |

### Forward verification

```bash
.venv/bin/python manage.py migrate contracts 0114
.venv/bin/python manage.py migrate contracts 0113  # rollback proof
.venv/bin/python manage.py migrate contracts 0114  # re-forward
```

### Data verification

- Row counts start at 0.
- No FK from legacy RiskSignal / DPARiskItem / Deadline / ConflictCheck yet.

## Dual-path cutover (future authorized slices)

Do **not** execute without Accepted ADR-0015 + per-path authorization.

| Phase | Behavior | Rollback |
|---|---|---|
| 0 Foundation (this slice) | Schema + service exist; legacy paths unchanged | Drop tables via reverse `0114` |
| 1 Dual-write (flagged) | Selected legacy actions also create ExceptionRequest | Disable flag; leave orphan rows |
| 2 Dual-read | Enforcement consults canonical when present | Ignore canonical; legacy wins |
| 3 Canonical authority | Legacy status becomes mirror / residual | Re-enable legacy authority flag |
| 4 Backfill (optional) | Best-effort historical projection with `authority_basis=legacy_unknown` and explicit non-applicability unless expiry reconstructed | Document incompleteness; do not invent Security approval |

## Path priority for Phase 1

1. EXC-POL-001 keep_exception  
2. EXC-POL-005 ACCEPTED_RISK  
3. EXC-POL-007/008 AI exception / accepted risk dismiss  
4. EXC-POL-009 ConflictCheck WAIVED  
5. EXC-DL-001 deadline_defer (require reason + ExceptionRequest)  
6. EXC-APR-001 DPA approve-with-blockers (require ExceptionDecision)

Platform break-glass (EXC-SEC/ADM/REP) stays Phase 1+ under Security review.

## Feature-flag posture

No production cutover flag in this slice. When dual-write begins, add default-**off** flags analogous to PAR-ID-001 resolver flags; settings_test must force them off.

## Non-goals

- Silent privilege expansion during backfill  
- Cross-tenant exception rows  
- Marking ADR-0015 Accepted in this package  
- Starting PAR-APR-002 / PAR-WF-010 / PAR-ID-002
