# Golden Journey Report

**Baseline:** `308d63f462be546efef0b1794f1268cf2443cd2f`  
**Assessment rule:** a journey is `PASS` only if the complete result is supported by implementation and sufficient automated/operational evidence without developer intervention. No journey meets that bar.

## GJ-01 — NDA using CLM One paper

| Item | Finding |
|---|---|
| Starting conditions | Authenticated member in a tenant with the governed NDA template/configuration available; requester has the required intake values. |
| Steps | Start contract → complete NDA intake → generate CLM One paper → resolve/review approvals → collect execution evidence → create durable record → create any post-signature date/obligation items. |
| Expected result | A versioned, approved, executed NDA is searchable as a provenance-backed record with immutable history and correct tenant access. |
| Actual result | NDA factory and workflow routes exist: [service](../../contracts/services/nda_workflow.py#L353), [routes](../../contracts/urls.py#L315). The focused suite fails the Command Center generated-workspace projection test, so the complete user path is not demonstrated as passing. |
| Relevant tests | [NDA workflow tests](../../tests/test_nda_workflow.py), [document version tests](../../tests/test_document_versioning.py), [audit tests](../../tests/test_audit_integrity.py). |
| Manual intervention required | Unproven. Template configuration and e-signature-provider activation are outside the verified local path. |
| Defects/gaps | Failing Command Center assertion; no complete evidence through signature and durable record; no production provider evidence. |
| Final classification | **PARTIAL** |

## GJ-02 — MSA plus SOW or Order Confirmation

| Item | Finding |
|---|---|
| Starting conditions | Authenticated requester; MSA workflow/template and linked SOW or Order Confirmation configuration available. |
| Steps | Launch MSA → generate MSA and package artifact → complete legal/commercial/finance review → link or create SOW/Order Confirmation → approve exact state → execute → record relationship and renewal/notice obligations. |
| Expected result | Related records preserve relationship, artifact versions, approvals, execution evidence, provenance, and post-signature ownership. |
| Actual result | MSA factory and document artifact service exist: [factory](../../contracts/services/msa_workflow.py#L490), [artifact service](../../contracts/services/msa_workflow.py#L146). Tests cover submissions, exports, and exception handling, but no single test proves full package relationship through execution/record. |
| Relevant tests | [MSA workflow tests](../../tests/test_msa_workflow.py), [obligation tests](../../tests/test_obligation_tracker.py). |
| Manual intervention required | Unproven; contract linkage, signer/provider configuration, and record finalisation are not proven as a no-developer path. |
| Defects/gaps | No end-to-end relationship/provenance test; execution provider evidence absent; canonical obligation-model mismatch. |
| Final classification | **PARTIAL** |

## GJ-03 — Third-party MSA requiring review and approval

| Item | Finding |
|---|---|
| Starting conditions | Authenticated requester/reviewer; tenant-authorized third-party file and an approved MSA workflow configuration. |
| Steps | Upload counterparty paper → create immutable version → assign reviewer(s) → record comments/findings → resolve exceptions → route approvals → reset when material change occurs → sign/retain execution evidence → record. |
| Expected result | The final state is auditable, bound to the exact document/version, and inaccessible to unauthorised users. |
| Actual result | Document-version controls and review models exist: [version service](../../contracts/services/document_version_service.py#L140), [review model](../../contracts/models.py#L1741). No comprehensive third-party-paper acceptance journey was found. |
| Relevant tests | [document tests](../../tests/test_document_versioning.py), [upload/OCR tests](../../tests/test_upload_ocr_pipeline.py), [approval tests](../../tests/test_approval_workflow.py), [tenant suite](../../tests/test_cross_tenant_isolation.py). |
| Manual intervention required | Likely for provider and workflow configuration; the no-developer condition is not evidenced. |
| Defects/gaps | Missing upload-to-final-record acceptance test; approval-reset proof incomplete; restricted metadata non-leakage is not proven across collaboration/export channels. |
| Final classification | **PARTIAL** |

## GJ-04 — DPA requiring privacy review

| Item | Finding |
|---|---|
| Starting conditions | Authenticated requester; DPA workflow available; privacy reviewer and legal/commercial approver assignment resolves. |
| Steps | Launch DPA → collect processing/transfer inputs → generate or ingest DPA → open privacy pack → review/resolve risks → approve exact version → sign → record → track obligations/renewal dates. |
| Expected result | An unresolved privacy risk or missing privacy approval blocks progression; the final DPA record preserves specialist review and execution provenance. |
| Actual result | DPA workflow factory and review-pack routes exist: [factory](../../contracts/services/dpa_workflow.py#L334), [model](../../contracts/models.py#L3992), [routes](../../contracts/urls.py#L253). Two DPA-focused UI assertions fail in the focused suite. |
| Relevant tests | [DPA workflow tests](../../tests/test_dpa_workflow.py), [privacy evidence export test](../../tests/test_identity_telemetry_and_exports.py#L47), [approval tests](../../tests/test_approval_workflow.py). |
| Manual intervention required | Unproven; live signature/provider and complete privacy approver setup were not verified. |
| Defects/gaps | Failing UI evidence; no end-to-end block/recovery proof through execution/record; no live privacy operational evidence. |
| Final classification | **PARTIAL** |

## Cross-journey invariant result

| Invariant | Result |
|---|---|
| Immutable document versions | Strong implementation/test evidence; see CR-10. |
| Approval tied to exact document/contract state | PARTIAL; canonical service exists but journey coverage and reset proof are incomplete. |
| Durable record provenance | PARTIAL; implemented but not demonstrated for every journey. |
| Tenant isolation | PARTIAL; broad tests but incomplete all-channel object-policy proof. |
| Immutable audit history | PARTIAL; strong implementation tests, insufficient complete-action/production evidence. |
| Failure and recovery | PARTIAL; selected failure paths exist but not all journey stages and provider failures. |
