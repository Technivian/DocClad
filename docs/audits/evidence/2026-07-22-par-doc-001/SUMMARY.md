# PAR-DOC-001 evidence summary — 2026-07-22

## Status: Completed

### Canonical choice
**`Document`** row remains the version carrier (`parent_document` + `version` int); **`DocumentVersion`** is the immutable canonical record (CANONICAL_DOMAIN_MODEL §2.16) with OneToOne `document_row`, logical identity via `logical_document`, and governed creation through `create_document_version()`.

### Suites
- `django-tests.txt` — 14 OK (`tests/test_par_doc_001_document_version.py`)
- `tests/test_document_versioning.py` — 5 OK (regression)
- `migrate-rollback.txt` / `migrate-reforward.txt` — 0107 ↔ 0109 round-trip on test settings

### New / changed modules
- `contracts/models.py` — `DocumentVersion`, `logical_document`, immutability guards, `DocumentVersionQuerySet`
- `contracts/services/document_version_service.py` — `create_document_version`, `allocate_version_number`, `ensure_canonical_version_for_document`
- Wired paths: `client_matter_document.py`, `contracts.py`, `documents_ai.py`, `counterparty_collaboration.py`, `msa_workflow.py`, `dpa_workflow.py`
- `SignatureRequest.document_version` FK + auto-bind on save

### Migrations
- `0108_document_version_entity` — create `DocumentVersion`; backfill legacy rows with `source=legacy_unknown`, `checksum_missing` when no hash
- `0109_signature_request_document_version` — bind existing signature packets to canonical versions

### Audit events
- `document.version.created` (legacy equivalent: `document_version_created`)
- `document.version.marked_final` (FINAL/EXECUTED versions)
- `document.superseded` — **reused** (no duplicate semantics)

### Residual (explicit)
- **`DraftDocument`** — workflow scratch text model; not a file Document Version (by design).
- **`ApprovalRequest`** — no document-version FK yet (**PAR-APR-001**).
- **Seeds/admin/direct `Document.objects.create`** — backfilled via `ensure_canonical_version_for_document` with `legacy_unknown` source; not blocked to avoid breaking fixtures.
- **No `document.version.merged` event** — no production path creates merged file versions (redline findings are text drafts only).
- **Contract Record executed-version pin** — identifiable via `Document`/`DocumentVersion` + signature binding; dedicated record FK deferred.

### Next roadmap item
**PAR-WF-010** (discovery/design only until Accepted ADR; **do not start production cutover**)
