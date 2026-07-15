# Operator Runbook — Durable Document Storage (A6)

## Backends

| Environment | Backend | Notes |
|---|---|---|
| Development / tests | `FileSystemStorage` (`MEDIA_STORAGE_BACKEND=filesystem`, default) | Local `media/`; **not durable** — never use in production. |
| Production | `S3Storage` (`MEDIA_STORAGE_BACKEND=s3`) | AWS S3 or any S3-compatible endpoint (e.g. Supabase Storage). |

## Startup guards (fail loud, no silent ephemeral storage)

Production settings (`config.settings_production`) reject unsafe storage at boot:

- `MEDIA_STORAGE_BACKEND` must be `s3`, else `ImproperlyConfigured`
  ("Production requires durable object storage…"). Escape hatch:
  `ALLOW_EPHEMERAL_MEDIA_IN_PRODUCTION=true` (temporary emergency only).
- `s3` requires `AWS_STORAGE_BUCKET_NAME`, else `ImproperlyConfigured`.
- Error messages never include secret values.

## Required production configuration

Set on the web + worker + cron services (shared env group — see render.yaml):

| Variable | Required | Purpose |
|---|---|---|
| `MEDIA_STORAGE_BACKEND` | yes (`s3`) | Selects durable object storage |
| `AWS_STORAGE_BUCKET_NAME` | yes | Target bucket |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | yes (unless instance role) | Credentials |
| `AWS_S3_REGION_NAME` | provider-dependent | Region |
| `AWS_S3_ENDPOINT_URL` | for non-AWS (Supabase) | S3-compatible endpoint |
| `AWS_DEFAULT_ACL` | optional (`private` default) | Object ACL |
| `AWS_SIGNED_URL_EXPIRE` | optional (`3600` default) | Signed-URL lifetime (seconds) |

> Do not invent bucket names, endpoints, regions or credentials — provision them
> in your own cloud account and supply the values as Render secrets.

## Access model

- Objects are **private** (`default_acl=private`, `querystring_auth=True`): no
  world-readable URLs.
- Users never receive raw object URLs. Downloads go through the authenticated
  endpoint `GET /contracts/documents/<id>/download/`, which:
  1. requires login;
  2. enforces tenant scope (cross-tenant → 404, audited as blocked on the
     actor's org);
  3. enforces document permission (VIEW on the linked contract);
  4. honors (soft-)deletion state;
  5. audits `document.downloaded`;
  6. redirects to a short-lived **signed** URL (S3) — the URL is never stored.
- Signed-URL lifetime defaults to 3600s; lower via `AWS_SIGNED_URL_EXPIRE` if
  policy requires.

## Bucket security checklist (operator responsibility)

- **Encryption at rest:** enable SSE (SSE-S3 or SSE-KMS) on the bucket.
- **Private access:** block all public access; no public bucket policy/ACLs.
- **Versioning:** enable object versioning so an overwrite/delete is recoverable
  (CLM One sets `file_overwrite=False`, but versioning protects against
  out-of-band changes).
- **Lifecycle/retention:** configure object-lock or lifecycle rules consistent
  with the organization's contract retention period; coordinate with CLM One
  retention policies (legal hold prevents application-level deletion — see 4E).
- **Backups:** enable cross-region replication or periodic backup of the bucket.
- **Restore validation:** after any restore, confirm a sample of object keys
  resolve via the download endpoint and that `file_hash` matches the DB record.

## Object key stability

Existing object keys and uploaded files are preserved (`document_upload_path`
unchanged; no bucket rename). Do not rename buckets without a documented copy +
re-point migration.
