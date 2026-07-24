# Platform Alignment tranche final closeout

**Verdict:** **PASS — Platform Alignment tranche closed with inherited full-suite residuals**

## Reviewed evidence and integration bases

- **Comparison baseline:** `620b7c5d2ae41b3939ed78d2b55b4ab6b4fbd10c`
- **Reviewed Platform Alignment evidence baseline:** `706f20b8b84833d97f85342c8182283c8d1fcfea`
- **PR integration base:** `8d721e5b981b1c4cbc34eced6709ed9a79dac040`

The integration base contains post-baseline PAR-APR-002 characterization and
planning evidence. It does not rewrite the reviewed Platform Alignment
evidence baseline or make PAR-APR-002 implementation part of this closed
tranche.

## Scope and completion boundary

This record closes the completed Platform Alignment tranche described by the
[roadmap](../../roadmap/PLATFORM_ALIGNMENT_ROADMAP.md). It records completed
foundation, hardening, canonical-core, approval-foundation, role-definition,
and governed-exception work, together with the associated reconciliation and
release evidence. It does **not** claim that every future roadmap item is
complete.

In particular:

- PAR-APR-002 remains separate characterization/planning work; no cutover or
  implementation is authorized by this closeout.
- PAR-WF-010 remains separately governed and blocked pending its required
  decision.
- PAR-ID-002 remains a future residual and has not started.

## Merge and historical-PR reconciliation

| Record | Disposition | Evidence |
|---|---|---|
| PR #86 | Merged | merge `620b7c5d2ae41b3939ed78d2b55b4ab6b4fbd10c` |
| PR #89 | Merged | merge `ecb00807f98df232547412585c533b532d3c8802` |
| PR #90 | Merged | merge `8e4c9144acc92757bcbcb198aa2405e65d0d1f1c` |
| PR #60 | Closed without merge; branch retained | [closure record](https://github.com/Technivian/CLMOne/pull/60#issuecomment-5070358966) |
| PR #64 | Closed without merge; branch retained | [closure record](https://github.com/Technivian/CLMOne/pull/64#issuecomment-5070359247) |
| PR #65 | Closed without merge; branch retained | [closure record](https://github.com/Technivian/CLMOne/pull/65#issuecomment-5070359518) |
| PR #67 | Previously closed without merge; branch retained | [closure record](https://github.com/Technivian/CLMOne/pull/67#issuecomment-5069229509) |
| PR #75 | Previously closed without merge; branch retained | [closure record](https://github.com/Technivian/CLMOne/pull/75#issuecomment-5069229627) |
| PR #82 | Previously closed without merge; branch retained | [closure record](https://github.com/Technivian/CLMOne/pull/82#issuecomment-5068872069) |

Charter §16 remains authoritative: GitHub reviews, checks, immutable SHAs, and
operator or release records are the active repository evidence model. The
closed historical branches are retained; none is merged or treated as current
authorization evidence.

## Validation evidence

At the reviewed baseline and integration base, the following checks completed
successfully in isolated local validation:

- `python manage.py migrate --noinput`
- `python manage.py migrate --check`
- `python manage.py makemigrations --check --dry-run`
- `python manage.py check`
- `python manage.py audit_null_organizations` — no NULL organization rows
- `npm --prefix client ci`
- `npm --prefix client audit --audit-level=high` — zero vulnerabilities
- `npm --prefix theme/static_src audit --audit-level=high` — zero
  vulnerabilities
- `git diff --check`

Required CI for [PR #89](https://github.com/Technivian/CLMOne/pull/89) and
[PR #90](https://github.com/Technivian/CLMOne/pull/90) was green, including
security scanning, quality and tenancy, release evidence, UI verification,
brand/design guardrails, and (for PR #90) redesigned E2E.

### Controlled full-suite differential

The complete Django suite was deliberately compared only at the controlled
historical revisions, and it was **not green**:

| Revision | Tests | Failures | Errors | Skipped |
|---|---:|---:|---:|---:|
| `620b7c5d2ae41b3939ed78d2b55b4ab6b4fbd10c` | 2,412 | 41 | 29 | 31 |
| `8e4c9144acc92757bcbcb198aa2405e65d0d1f1c` | 2,412 | 41 | 29 | 31 |

All 70 failure/error identifiers were identical. The differential therefore
found **70 inherited residuals, 0 new regressions, 0 resolved failures, and 0
inconclusive identifiers**. The non-green suite is recorded quality debt, not
silently waived and not attributed to PR #89 or PR #90.

Observed inherited categories are lifecycle/status expectation drift;
UI/template assertion drift; document-version immutability and fixture
conflicts; optional or undeclared-test dependency imports; and other reproduced
historical integration/test debt. No remediation is started by this record.

### Post-baseline PAR-APR-002 characterization

`tests/test_par_apr_002_cutover_baseline.py`, added after the reviewed baseline,
was assessed as **POST-BASELINE FUTURE-WORK CHARACTERIZATION —
non-invalidating**. It is additive and self-contained, creates only local test
data, changes no shared fixture, test settings, test discovery, migration, or
runtime behaviour, and asserts that the legacy/canonical boundary remains in
place.

- `python manage.py test tests.test_par_apr_002_cutover_baseline -v 2` — 3
  tests passed.
- The characterization module plus `tests.test_cross_tenant_isolation` and
  `tests.test_permission_matrix` completed successfully.

This result is separate from, and is not added to, the historical 2,412-test
totals. It does not assert a PAR-APR-002 cutover or implementation is complete.

## Safety, authority, and operations state

- No production activation occurred through this tranche closeout.
- No new canonical, privilege, permission, or ADMIN authority was granted.
- The controlled canonical-read observation ended with flags off, empty
  allowlists, and legacy authority restored.
- No automatic-repair authority or legacy retirement was authorized.
- Tenant-isolation required CI remained green.
- Dependency security audits are clean at the reviewed integration state.
- Migrations introduced no un-applied or model-drift condition in validation.
- Completed controlled work retains its documented rollback and operator
  evidence; this closeout itself is documentation-only and rolls back by
  reverting its documentation commit.

## Future-work boundary

PAR-APR-002 baseline characterization may continue under its own governance;
implementation and cutover remain outside this closeout. PAR-WF-010 and
PAR-ID-002 likewise remain separately governed. This PASS verdict does not
authorize any next programme item, flag activation, authority change, or
production action.
