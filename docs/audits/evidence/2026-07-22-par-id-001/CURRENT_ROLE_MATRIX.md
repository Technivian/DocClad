# PAR-ID-001 — Current role model matrix

**Date:** 2026-07-22  
**Scope:** Discovery only — dual `OrganizationMembership.Role` vs `UserProfile.Role`

## Legend

| Column | Meaning |
|---|---|
| **Layer** | Workspace permission vs process responsibility |
| **Consumers** | Runtime readers/writers |
| **Tenant** | Org scoping rule |
| **Risk** | Reconciliation impact |

---

## `OrganizationMembership.Role`

| Attribute | Value |
|---|---|
| **Layer** | Workspace / org permission |
| **Values** | `OWNER`, `ADMIN`, `MEMBER` |
| **Model** | `OrganizationMembership.role` |
| **Primary consumers** | Org admin surfaces, invitation role, billing, configuration gates |
| **Typical checks** | `role__in=[OWNER, ADMIN]` for admin actions |
| **Tenant** | Per `(organization, user)` membership |
| **Pilot seeds** | `seed_controlled_pilot`, `seed_demo`, `seed_data`, `seed_payrollminds_demo` |
| **Risk** | **High** if conflated with process roles — admin escalation |

---

## `UserProfile.Role`

| Attribute | Value |
|---|---|
| **Layer** | Process / professional role (Role Definition interim storage) |
| **Values** | `PARTNER`, `SENIOR_ASSOCIATE`, `ASSOCIATE`, `PARALEGAL`, `LEGAL_ASSISTANT`, `ADMIN`, `CLIENT` |
| **Model** | `UserProfile.role` (OneToOne per user) |
| **Primary consumers** | Workflow step `assignee_role`, `ApprovalRoute.approver_role`, approval matching |
| **Typical checks** | Equality match on `UserProfile.role` for task/approval routing |
| **Tenant** | User-global (not org-scoped) — **reconciliation risk** for multi-org users |
| **Pilot seeds** | All demo seeds set explicit profile role alongside membership role |
| **Risk** | **High** — `ADMIN` name collision; user-global scope vs org membership |

---

## Name collision matrix

| Value | `OrganizationMembership` | `UserProfile` | Reconciliation note |
|---|---|---|---|
| `ADMIN` | Org admin permission | Administrator process role | **Must not conflate** — different semantics |
| `OWNER` | Org owner | — | Workspace only |
| `MEMBER` | Org member | — | Workspace only |
| `ASSOCIATE` | — | Legal associate | Process only |
| `PARTNER` | — | Partner | Process only |

---

## Seed patterns (intentional dual-set)

| Seed | Example pattern |
|---|---|
| `seed_controlled_pilot` | `MEMBER` + `PARALEGAL` / `ASSOCIATE` |
| `seed_demo` | `OWNER` + `ADMIN` (profile) / `MEMBER` + `PARALEGAL` |
| `seed_payrollminds_demo` | Mixed `OWNER`/`MEMBER` + various profile roles |

---

## Canonical target (ADR-0014 proposed)

| Concept | Canonical name | Interim storage |
|---|---|---|
| Workspace permission | Organization role | `OrganizationMembership.role` |
| Process responsibility | Role Definition | `UserProfile.role` |

Mapping registry required before cutover. No destructive enum drop in foundation slice.
