"""Long-running background job worker with configurable poll interval and graceful shutdown."""
from __future__ import annotations

import signal
import time

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from contracts.models import BackgroundJob
from contracts.services.background_jobs import process_background_job


class Command(BaseCommand):
    help = (
        'Run a continuous background job worker. Polls the queue every '
        '--poll-interval seconds and processes pending jobs. Shuts down '
        'gracefully on SIGTERM/SIGINT after completing the current batch.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--poll-interval', type=int, default=10,
            help='Seconds between queue polls (default: 10)',
        )
        parser.add_argument(
            '--batch-size', type=int, default=10,
            help='Max jobs to process per poll cycle (default: 10)',
        )
        parser.add_argument(
            '--max-cycles', type=int, default=0,
            help='Stop after N cycles (0 = run forever; useful for testing)',
        )
        parser.add_argument(
            '--job-types', type=str, default='',
            help='Comma-separated list of job_type values to process (default: all)',
        )

    def handle(self, *args, **options):
        poll_interval = max(1, options['poll_interval'])
        batch_size = max(1, options['batch_size'])
        max_cycles = options['max_cycles']
        job_types = [t.strip() for t in options['job_types'].split(',') if t.strip()]

        self._shutdown = False

        def _handle_signal(signum, frame):
            self.stdout.write(self.style.WARNING(
                f'\n[worker] Signal {signum} received — finishing current batch then stopping.'
            ))
            self._shutdown = True

        signal.signal(signal.SIGTERM, _handle_signal)
        signal.signal(signal.SIGINT, _handle_signal)

        self.stdout.write(self.style.SUCCESS(
            f'[worker] Starting — poll_interval={poll_interval}s batch_size={batch_size}'
            + (f' job_types={job_types}' if job_types else ' job_types=all')
        ))

        cycles = 0
        total_processed = 0
        total_failures = 0

        while not self._shutdown:
            processed, failures = self._run_batch(batch_size, job_types)
            total_processed += processed
            total_failures += failures
            cycles += 1

            if processed:
                self.stdout.write(
                    f'[worker] cycle={cycles} processed={processed} failures={failures} '
                    f'total={total_processed}'
                )

            if max_cycles and cycles >= max_cycles:
                self.stdout.write(self.style.WARNING(
                    f'[worker] Reached max_cycles={max_cycles}, stopping.'
                ))
                break

            if not self._shutdown:
                time.sleep(poll_interval)

        self.stdout.write(self.style.SUCCESS(
            f'[worker] Stopped. total_processed={total_processed} total_failures={total_failures}'
        ))

    def _run_batch(self, batch_size: int, job_types: list[str]) -> tuple[int, int]:
        qs = (
            BackgroundJob.objects
            .filter(status=BackgroundJob.Status.PENDING)
            .filter(Q(scheduled_at__isnull=True) | Q(scheduled_at__lte=timezone.now()))
        )
        if job_types:
            qs = qs.filter(job_type__in=job_types)

        jobs = qs.order_by('scheduled_at', 'created_at')[:batch_size]
        processed = failures = 0
        for job in jobs:
            try:
                process_background_job(job)
            except Exception as exc:
                self.stderr.write(
                    f'[worker] job_id={job.id} job_type={job.job_type} error={exc}'
                )
                failures += 1
            processed += 1
        return processed, failures
