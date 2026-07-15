# Operator Runbook — Background Jobs & Scheduled Automation (Phase 2)

This runbook covers the production-backed job system: how it is scheduled, how
to verify it ran for a tenant, and how to respond to failures.

## TL;DR

Scheduling is owned by **Render services**, all sharing the same `DATABASE_URL`
as the web app via the `clmone-shared` env group:

| Service | Render type | Cadence | What it does |
|---|---|---|---|
| `clmone` | web | — | Serves the app; runs DB migrations on deploy |
| `clmone-worker` | worker | continuous | Drains the `BackgroundJob` queue (poll 10s) |
| `clmone-cron-dispatch` | cronjob | `*/15 * * * *` | Queues per-org jobs, then drains once |
| `clmone-cron-daily` | cronjob | `30 2 * * *` (UTC) | Renewal promotion + retention archive |

GitHub Actions **no longer schedule production work.** The old scheduler
workflows are now manual-only CI smoke tests against an ephemeral SQLite DB and
are explicitly **not** evidence that tenant jobs ran.

## Job inventory

| Job | Class | Trigger | Tenant scope |
|---|---|---|---|
| `send_contract_reminders` | renewal/expiration reminders **+ SLA escalation** | queued (`*/15`) → worker | all active orgs |
| `process_document_ocr_reviews` | document text extraction | queued (`*/15`) → worker | per org (queued per org) |
| `run_obligation_reminders` | obligation/deadline reminders | queued (`*/15`) → worker | per org |
| `sync_salesforce_contracts` | CRM ingestion | queued (`*/15`, if connected) → worker | per org |
| `export_dsar_evidence` | DSAR export | UI-triggered → worker | per org |
| `run_contract_lifecycle_jobs` | promote contracts to RENEWAL | daily cron | per org |
| `run_retention_jobs` | archive contracts past retention | daily cron | per org |
| `queue_background_jobs` | dispatch (creates the queue rows) | `*/15` cron | global |

## Guarantees

- **Idempotent.** `queue_background_jobs` dedupes within a time window; lifecycle
  and retention skip already-promoted/already-archived contracts.
- **No double execution.** `claim_background_job` atomically transitions a job
  `PENDING → RUNNING` with a single conditional UPDATE, so the continuous
  worker, the cron drain, and any RQ worker can run concurrently without
  processing the same job twice. Scheduled commands use a per-(job, org)
  overlap lock (`record_job_run(prevent_overlap=True)`).
- **Tenant-scoped.** Every scheduled command iterates organizations and filters
  records by `organization`.
- **Retry + dead-letter.** Failed queued jobs retry with exponential backoff up
  to `max_attempts`, then move to `FAILED` (dead-lettered). Crashed-worker
  `RUNNING` rows older than 30 min are reset to `PENDING`.

## Verifying a run (evidence)

Every scheduled run writes a `ScheduledJobRun` row (run id, org, status, records
examined/changed, notifications created, error summary). This is the source of
truth — **not** CI artifacts.

- **In the app:** Operations dashboard → "Scheduled job runs" panel shows the
  last runs per org and a 24h failed/partial count.
- **In the DB / shell:**
  ```bash
  python manage.py shell -c "from contracts.models import ScheduledJobRun as R; \
    [print(r.job_name, r.organization_id, r.status, r.records_changed, r.started_at) \
     for r in R.objects.order_by('-started_at')[:20]]"
  ```
- **Queue health:** `health_check?format=json` returns `degraded` (HTTP 503)
  when the reminder scheduler heartbeat is stale.

## Required environment (set as Render secrets / env group)

`DATABASE_URL` (Supabase), `REDIS_URL`, media (`AWS_*` / `MEDIA_STORAGE_BACKEND=s3`),
email (`EMAIL_HOST_PASSWORD`), `GEMINI_API_KEY` (only if AI enabled),
e-signature (`ESIGN_DOCUMENSO_API_KEY`). The worker and cron services inherit
all of these from the `clmone-shared` env group — do **not** set them per
service.

> Cost note: Render `worker` and `cronjob` services require a **paid** instance
> type (the web service may stay free). Minimal pilot: run only the two cron
> jobs; the continuous worker is recommended for prompt UI-triggered jobs
> (e.g. DSAR export) but is optional.

## Manual operations

```bash
# Drain the queue once (safe anytime; claiming prevents double-run):
python manage.py process_background_jobs --limit 200

# Run a single tenant's nightly jobs ad hoc:
python manage.py run_contract_lifecycle_jobs --organization-slug <slug>
python manage.py run_retention_jobs --organization-slug <slug>

# Dry-run (no writes, no overlap lock) to preview impact:
python manage.py run_retention_jobs --organization-slug <slug> --dry-run

# Inspect / requeue dead-lettered jobs:
python manage.py review_dead_letter_jobs list
```

## Failure response

1. Check the Operations dashboard "Scheduled job runs" panel and `failed/partial`
   count, or query `ScheduledJobRun` filtered by `status in (FAILED, PARTIAL)`.
2. Read `error_summary` (truncated exception; never contains secrets or document
   bodies) and the service logs (`logger` warnings: `job_run failed: ...`).
3. For queued jobs, inspect `BackgroundJob` `error_message` / `attempt_count`;
   dead-lettered jobs can be requeued with `review_dead_letter_jobs`.
4. If the worker dyno crashed, stale `RUNNING` jobs auto-reset after 30 min; you
   can also restart the `clmone-worker` service.

## What is NOT logged

`error_summary` and `detail` store counts and short messages only — never
secrets, credentials, or full document content.
