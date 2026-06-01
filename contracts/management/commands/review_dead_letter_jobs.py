"""Review, retry, and purge dead-lettered background jobs."""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand
from django.utils import timezone

from contracts.models import BackgroundJob


class Command(BaseCommand):
    help = 'Review, retry, or purge dead-lettered background jobs.'

    def add_arguments(self, parser):
        parser.add_argument(
            'action', choices=['list', 'retry', 'purge'],
            help='list — show dead-lettered jobs; retry — re-queue them; purge — delete them',
        )
        parser.add_argument(
            '--job-type', type=str, default='',
            help='Filter by job_type',
        )
        parser.add_argument(
            '--job-id', type=int, default=0,
            help='Target a single job by primary key',
        )
        parser.add_argument(
            '--limit', type=int, default=100,
            help='Max jobs to process (default: 100)',
        )
        parser.add_argument(
            '--output', type=str, default='',
            help='Optional path to write list output as JSON',
        )

    def handle(self, *args, **options):
        action = options['action']
        job_type = options['job_type']
        job_id = options['job_id']
        limit = options['limit']

        qs = BackgroundJob.objects.filter(status=BackgroundJob.Status.FAILED)
        if job_type:
            qs = qs.filter(job_type=job_type)
        if job_id:
            qs = qs.filter(id=job_id)
        qs = qs.order_by('dead_lettered_at')[:limit]

        if action == 'list':
            jobs = list(qs)
            rows = [
                {
                    'id': j.id,
                    'job_type': j.job_type,
                    'organization_id': j.organization_id,
                    'attempt_count': j.attempt_count,
                    'error_message': j.error_message[:200] if j.error_message else '',
                    'dead_lettered_at': j.dead_lettered_at.isoformat() if j.dead_lettered_at else None,
                    'payload': j.payload,
                }
                for j in jobs
            ]
            self.stdout.write(f'Dead-lettered jobs: {len(rows)}')
            for row in rows:
                self.stdout.write(
                    f"  [{row['id']}] {row['job_type']} "
                    f"attempts={row['attempt_count']} "
                    f"error={row['error_message'][:80]}"
                )
            if options['output']:
                from pathlib import Path
                out = Path(options['output'])
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(json.dumps(rows, indent=2, default=str), encoding='utf-8')
                self.stdout.write(self.style.SUCCESS(f'Written to {out}'))
            return

        if action == 'retry':
            count = 0
            for job in qs:
                job.status = BackgroundJob.Status.PENDING
                job.attempt_count = 0
                job.error_message = ''
                job.dead_lettered_at = None
                job.scheduled_at = timezone.now()
                job.save(update_fields=[
                    'status', 'attempt_count', 'error_message',
                    'dead_lettered_at', 'scheduled_at',
                ])
                count += 1
            self.stdout.write(self.style.SUCCESS(f'Re-queued {count} dead-lettered job(s).'))
            return

        if action == 'purge':
            ids = list(qs.values_list('id', flat=True))
            BackgroundJob.objects.filter(id__in=ids).delete()
            self.stdout.write(self.style.SUCCESS(f'Purged {len(ids)} dead-lettered job(s).'))
