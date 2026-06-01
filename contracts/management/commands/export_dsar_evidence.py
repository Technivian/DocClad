"""Management command: export a DSAR evidence bundle as a JSON artifact."""
from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from contracts.models import Organization
from contracts.services.dsar import get_dsar_service


class Command(BaseCommand):
    help = 'Export a GDPR DSAR evidence bundle for a specific request.'

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--request-id', type=int, help='DSARRequest primary key')
        group.add_argument('--all', dest='export_all', action='store_true',
                           help='Export overdue/at-risk summary for org')
        parser.add_argument(
            '--organization-slug', type=str, default=None,
            help='Organization slug (required when using --all)',
        )
        parser.add_argument(
            '--output', type=str, default=None,
            help='Output JSON path (default: evidence/dsar-evidence-<id>.json)',
        )

    def handle(self, *args, **options):
        svc = get_dsar_service()
        request_id = options.get('request_id')
        export_all = options.get('export_all')
        org_slug = options.get('organization_slug')

        if export_all:
            if not org_slug:
                raise CommandError('--organization-slug is required with --all')
            try:
                org = Organization.objects.get(slug=org_slug)
            except Organization.DoesNotExist:
                raise CommandError(f'Organization not found: {org_slug}')

            result = svc.list_requests(org)
            payload = {
                'schema_version': '1.0',
                'organization': org_slug,
                'total': result.total,
                'overdue_count': result.overdue_count,
                'at_risk_count': result.at_risk_count,
                'requests': [
                    {
                        'id': r.id,
                        'reference_number': r.reference_number,
                        'request_type': r.request_type,
                        'status': r.status,
                        'sla_label': r.sla_label,
                        'days_remaining': r.days_remaining,
                        'due_date': r.due_date,
                        'requester_name': r.requester_name,
                    }
                    for r in result.requests
                ],
            }
            out_path = Path(options['output'] or f'evidence/dsar-org-{org_slug}.json')
        else:
            # Find org via request
            from contracts.models import DSARRequest
            try:
                req = DSARRequest.objects.get(id=request_id)
            except DSARRequest.DoesNotExist:
                raise CommandError(f'DSARRequest not found: {request_id}')

            org = req.organization
            if org is None and org_slug:
                try:
                    org = Organization.objects.get(slug=org_slug)
                except Organization.DoesNotExist:
                    raise CommandError(f'Organization not found: {org_slug}')

            payload = svc.generate_evidence_bundle(request_id, org)
            if payload is None:
                raise CommandError(f'Could not generate bundle for request {request_id}')

            out_path = Path(options['output'] or f'evidence/dsar-evidence-{request_id}.json')

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2, default=str), encoding='utf-8')

        self.stdout.write(self.style.SUCCESS(f'DSAR evidence exported → {out_path}'))
        if not export_all:
            self.stdout.write(f"  reference: {payload.get('reference_number')}")
            self.stdout.write(f"  sla_label: {payload.get('sla_label')}")
            self.stdout.write(f"  days_remaining: {payload['sla']['days_remaining']}")
