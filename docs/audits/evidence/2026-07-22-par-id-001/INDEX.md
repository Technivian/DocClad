# PAR-ID-001 evidence index

**Programme ID:** PAR-ID-001  
**Status:** **In progress** — discovery / characterization  
**ADR:** ADR-0014 **Proposed**  
**Branch:** `cursor/feat-par-apr-001-foundation-governance`

---

## Governance

| Artifact | Purpose |
|---|---|
| [`../../../governance/decisions/adr/0014-role-definition-reconciliation.md`](../../../governance/decisions/adr/0014-role-definition-reconciliation.md) | Proposed ADR |
| [`../../../product/CANONICAL_DOMAIN_MODEL.md`](../../../product/CANONICAL_DOMAIN_MODEL.md) §2.5 | Canonical Role Definition |
| [`../../../architecture/SECURITY_PRIVACY_ACCESS_AND_AUDIT.md`](../../../architecture/SECURITY_PRIVACY_ACCESS_AND_AUDIT.md) | Authz / least privilege |

---

## Discovery evidence

| Artifact | Purpose |
|---|---|
| [`SUMMARY.md`](SUMMARY.md) | Programme summary |
| [`CURRENT_ROLE_MATRIX.md`](CURRENT_ROLE_MATRIX.md) | Dual-role usage matrix |
| [`CHARACTERIZATION_TESTS.md`](CHARACTERIZATION_TESTS.md) | Test inventory |

---

## Test proof

| Artifact | Purpose |
|---|---|
| [`django-tests.txt`](django-tests.txt) | PAR-ID characterization test run |

---

## Scope boundary

- **In scope:** Discovery, terminology, mapping proposal, characterization tests
- **Out of scope:** SCIM sync, RBAC overhaul, enum removal, privilege changes

**Authorization:** ADR-0014 must be **Accepted** before mapping implementation or schema changes.
