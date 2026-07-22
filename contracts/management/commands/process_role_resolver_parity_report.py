"""Staging report for process-role resolver parity (PAR-ID-001).

Non-authoritative. Does not change resolver return values.
"""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from contracts.models import ApprovalRule, Contract, Organization, WorkflowTemplateStep
from contracts.services.process_role_resolver_parity import (
    CRITICAL_CLASSES,
    get_staging_counters,
    reset_staging_counters,
    resolver_parity_enabled,
)
from contracts.services.workflow_routing import resolve_rule_assignee


class Command(BaseCommand):
    help = 'Run diagnostic resolver-parity comparisons and emit staging counts (non-authoritative).'

    def add_arguments(self, parser):
        parser.add_argument('--organization-id', type=int, default=None)
        parser.add_argument('--json', action='store_true')
        parser.add_argument(
            '--require-flag',
            action='store_true',
            help='Exit 2 if PROCESS_ROLE_RESOLVER_PARITY_ENABLED is false',
        )

    def handle(self, *args, **options):
        if options['require_flag'] and not resolver_parity_enabled():
            self.stderr.write('PROCESS_ROLE_RESOLVER_PARITY_ENABLED is false')
            raise SystemExit(2)

        reset_staging_counters()
        orgs = Organization.objects.order_by('id')
        if options['organization_id']:
            orgs = orgs.filter(pk=options['organization_id'])

        for org in orgs:
            contracts = Contract.objects.filter(organization=org).order_by('id')[:20]
            for contract in contracts:
                for rule in ApprovalRule.objects.filter(organization=org, is_active=True).order_by('id')[:50]:
                    resolve_rule_assignee(rule, contract)
            for step in (
                WorkflowTemplateStep.objects.filter(template__organization=org)
                .select_related('template')
                .order_by('id')[:50]
            ):
                contract = contracts.first() if contracts else None
                step.resolve_assignee(contract)

        counters = get_staging_counters()
        summary = {
            'total_comparisons': counters.get('total_comparisons', 0),
            'counts_per_classification': {
                k: counters.get(k, 0)
                for k in (
                    'MATCH', 'LEGACY_ONLY', 'CANONICAL_ONLY', 'DIFFERENT_USER',
                    'DIFFERENT_ROLE', 'AMBIGUOUS', 'INACTIVE_ASSIGNMENT',
                    'CROSS_TENANT_ANOMALY', 'RESOLUTION_ERROR',
                )
            },
            'critical_drift_count': counters.get('critical_drift', 0),
            'CROSS_TENANT_ANOMALY_count': counters.get('CROSS_TENANT_ANOMALY', 0),
            'DIFFERENT_USER_count': counters.get('DIFFERENT_USER', 0),
            'RESOLUTION_ERROR_count': counters.get('RESOLUTION_ERROR', 0),
            'authoritative_for_runtime': False,
            'critical_classes': sorted(CRITICAL_CLASSES),
        }

        if options['json']:
            self.stdout.write(json.dumps(summary, sort_keys=True, indent=2))
        else:
            self.stdout.write(
                f"total={summary['total_comparisons']} critical={summary['critical_drift_count']} "
                f"cross_tenant={summary['CROSS_TENANT_ANOMALY_count']} "
                f"different_user={summary['DIFFERENT_USER_count']} "
                f"errors={summary['RESOLUTION_ERROR_count']}"
            )
            for cls, count in summary['counts_per_classification'].items():
                if count:
                    self.stdout.write(f'  {cls}={count}')

        if summary['critical_drift_count']:
            raise SystemExit(1)
