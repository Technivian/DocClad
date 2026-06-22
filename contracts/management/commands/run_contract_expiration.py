"""Expire ACTIVE contracts whose end date has passed (Phase 4C).

Expiration rule (documented):
  * Field: ``Contract.end_date``.
  * Eligible status: ``ACTIVE`` only (other statuses are never auto-expired;
    DRAFT/IN_REVIEW/PENDING/APPROVED have not started, and EXPIRED/TERMINATED/
    COMPLETED/CANCELLED are terminal).
  * Boundary: a contract is valid THROUGH its end_date; it expires once
    ``end_date < today`` in the server's local date (``timezone.localdate()``),
    i.e. end-of-day semantics, no grace period.
  * Exclusions: ``auto_renew=True`` contracts are skipped — they renew rather
    than expire (operators handle renewal via the lifecycle workflow).

The transition itself is delegated to ContractLifecycleService (idempotent,
locked, audited). Per-org ScheduledJobRun evidence; one tenant's failure does
not stop the others.
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand
from django.utils import timezone

from contracts.models import Contract, Organization
from contracts.services.contract_lifecycle import (
    ContractTransitionError,
    get_contract_lifecycle_service,
)
from contracts.services.job_runs import record_job_run

JOB_NAME = 'run_contract_expiration'


class Command(BaseCommand):
    help = 'Expire ACTIVE contracts whose end_date has passed (excludes auto-renew).'

    def add_arguments(self, parser):
        parser.add_argument('--organization-slug', default='')
        parser.add_argument('--dry-run', action='store_true', default=False)
        parser.add_argument('--limit', type=int, default=1000)

    def handle(self, *args, **options):
        dry_run = bool(options['dry_run'])
        limit = max(1, int(options['limit']))
        org_slug = (options.get('organization_slug') or '').strip()
        today = timezone.localdate()

        organizations = Organization.objects.filter(is_active=True).order_by('id')
        if org_slug:
            organizations = organizations.filter(slug=org_slug)

        lifecycle = get_contract_lifecycle_service()
        summary = {
            'captured_at': timezone.now().isoformat(),
            'dry_run': dry_run,
            'cutoff_date': today.isoformat(),
            'organizations_scanned': 0,
            'contracts_examined': 0,
            'contracts_expired': 0,
            'organization_failures': 0,
        }

        for organization in organizations:
            summary['organizations_scanned'] += 1
            try:
                with record_job_run(JOB_NAME, organization=organization,
                                    prevent_overlap=not dry_run) as run:
                    if run is None:
                        continue
                    run.detail = {'dry_run': dry_run, 'cutoff_date': today.isoformat()}
                    candidates = (
                        Contract.objects.filter(
                            organization=organization,
                            status=Contract.Status.ACTIVE,
                            end_date__isnull=False,
                            end_date__lt=today,
                            auto_renew=False,
                        )
                        .order_by('id')[:limit]
                    )
                    for contract in candidates:
                        summary['contracts_examined'] += 1
                        run.records_examined += 1
                        if dry_run:
                            continue
                        try:
                            lifecycle.transition(
                                contract, Contract.Status.EXPIRED, actor=None,
                                system=True, reason='auto-expired: end_date passed',
                                job_run_id=run.run_id,
                            )
                            summary['contracts_expired'] += 1
                            run.records_changed += 1
                        except ContractTransitionError as exc:
                            # Skip individual contracts that cannot transition;
                            # keep processing the rest of the tenant.
                            run.partial = True
                            run.detail.setdefault('skipped', []).append(
                                {'contract_id': contract.id, 'reason': str(exc)})
            except Exception as exc:  # noqa: BLE001
                # One tenant's failure must not stop the others.
                summary['organization_failures'] += 1
                self.stderr.write(f'[expiration] org={organization.slug} failed: {exc}')

        self.stdout.write(json.dumps(summary, indent=2, sort_keys=True))
