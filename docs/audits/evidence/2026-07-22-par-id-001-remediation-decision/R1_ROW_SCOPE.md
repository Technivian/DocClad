# R1 exact row scope — CERTAIN non-ADMIN missing assignments

**Source:** R0 `r0_inventory_raw.json` rem01 rows  
**Baseline:** `main` @ `0404e284`  
**Filter:** `inventory_class=MISSING_CANONICAL_SETUP` AND `mapping_confidence=CERTAIN`  
**Count:** **12**  
**Excluded:** 8 AMBIGUOUS ADMIN rows (listed at bottom for denial clarity)

---

## In-scope rows (authorize create)

| # | org_id | org_slug | user_id | username | profile_role | mapped_code | rule ID |
|---|---|---|---|---|---|---|---|
| 1 | 1 | demo-firm | 2 | jsmith | PARTNER | partner_reviewer | R1-MAP-01 |
| 2 | 1 | demo-firm | 3 | sjones | SENIOR_ASSOCIATE | senior_reviewer | R1-MAP-02 |
| 3 | 1 | demo-firm | 4 | mwilson | PARALEGAL | paralegal_reviewer | R1-MAP-04 |
| 4 | 2 | clmone-demo | 6 | demo_partner | PARTNER | partner_reviewer | R1-MAP-01 |
| 5 | 2 | clmone-demo | 7 | demo_associate | SENIOR_ASSOCIATE | senior_reviewer | R1-MAP-02 |
| 6 | 2 | clmone-demo | 8 | demo_paralegal | PARALEGAL | paralegal_reviewer | R1-MAP-04 |
| 7 | 3 | clmone-mvp | 10 | mvp_owner | ASSOCIATE | legal_reviewer | R1-MAP-03 |
| 8 | 3 | clmone-mvp | 11 | mvp_reviewer | SENIOR_ASSOCIATE | senior_reviewer | R1-MAP-02 |
| 9 | 4 | controlled-pilot-org | 14 | pilot_requester | PARALEGAL | paralegal_reviewer | R1-MAP-04 |
| 10 | 4 | controlled-pilot-org | 15 | pilot_legal | ASSOCIATE | legal_reviewer | R1-MAP-03 |
| 11 | 5 | payrollminds-demo | 18 | payrollminds_legal | SENIOR_ASSOCIATE | senior_reviewer | R1-MAP-02 |
| 12 | 5 | payrollminds-demo | 19 | payrollminds_procurement | ASSOCIATE | legal_reviewer | R1-MAP-03 |

**By canonical code:** `senior_reviewer` 4 · `paralegal_reviewer` 3 · `legal_reviewer` 3 · `partner_reviewer` 2  

**Note:** `org_id` / `user_id` are from the R0 disposable corpus. Apply against an equivalent regenerated staging-equivalent env must match on `(org_slug, username, profile_role, mapped_code)` — not raw ids from a different database.

---

## Explicitly out of scope (do not create)

| org_slug | username | profile_role | mapped_code | confidence |
|---|---|---|---|---|
| demo-firm | admin | ADMIN | legacy_process_admin | AMBIGUOUS |
| clmone-demo | demo_admin | ADMIN | legacy_process_admin | AMBIGUOUS |
| clmone-mvp | mvp_admin | ADMIN | legacy_process_admin | AMBIGUOUS |
| controlled-pilot-org | pilot_owner | ADMIN | legacy_process_admin | AMBIGUOUS |
| controlled-pilot-org | pilot_admin | ADMIN | legacy_process_admin | AMBIGUOUS |
| controlled-pilot-org | pilot_finance | ADMIN | legacy_process_admin | AMBIGUOUS |
| payrollminds-demo | payrollminds_admin | ADMIN | legacy_process_admin | AMBIGUOUS |
| payrollminds-demo | payrollminds_finance | ADMIN | legacy_process_admin | AMBIGUOUS |
