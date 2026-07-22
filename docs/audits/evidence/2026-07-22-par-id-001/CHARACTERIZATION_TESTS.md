# PAR-ID-001 — Characterization tests

**Module:** `tests/test_par_id_001_characterization.py`  
**Purpose:** Lock interim dual-role semantics before Role Definition reconciliation

## Tests

| Test | Assertion |
|---|---|
| `test_organization_membership_role_is_independent_of_user_profile_role` | `MEMBER` org + `ASSOCIATE` profile is valid pilot pattern |
| `test_admin_exists_in_both_enums_with_different_meaning` | `ADMIN` in both enums must not be conflated |
| `test_organization_membership_role_choices_are_workspace_scoped` | Exactly `OWNER`, `ADMIN`, `MEMBER` |
| `test_user_profile_role_choices_are_process_scoped` | Seven process role values |
| `test_membership_role_does_not_auto_sync_to_profile_role` | No automatic sync; profile uses model default |

## Run command

```bash
.venv/bin/python manage.py test tests.test_par_id_001_characterization --settings=config.settings_test
```

## Cutover invariant

Any future reconciliation MUST either:

1. Preserve these interim behaviours during dual-read, or
2. Explicitly migrate with backfill + characterization test updates + Accepted ADR-0014
