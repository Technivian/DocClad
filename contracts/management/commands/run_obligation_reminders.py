"""Management command: run_obligation_reminders

Finds all obligation deadlines within their reminder window and dispatches
reminder notifications (currently logs to stdout; pluggable via signals).

Usage:
    python manage.py run_obligation_reminders [--organization-slug SLUG] [--dry-run]
"""
import json

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from contracts.models import Organization
from contracts.services.obligations import get_obligation_service


class Command(BaseCommand):
    help = 'Dispatch reminders for obligations that are within their reminder window.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--organization-slug',
            dest='organization_slug',
            default=None,
            help='Limit to a specific organization slug. If omitted, runs for all organizations.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Compute which reminders would be sent without actually dispatching them.',
        )
        parser.add_argument(
            '--output',
            dest='output',
            default=None,
            help='Path to write a JSON summary artifact.',
        )

    def handle(self, *args, **options):
        slug = options['organization_slug']
        dry_run = options['dry_run']

        if slug:
            orgs = list(Organization.objects.filter(slug=slug))
            if not orgs:
                raise CommandError(f'Organization with slug {slug!r} not found.')
        else:
            orgs = list(Organization.objects.all())

        total_dispatched = 0
        org_results = []

        for org in orgs:
            svc = get_obligation_service(org)
            result = svc.dispatch_reminders(dry_run=dry_run)
            total_dispatched += result['dispatched']
            org_results.append({
                'organization': org.slug,
                'dispatched': result['dispatched'],
                'dry_run': result['dry_run'],
            })
            if result['dispatched'] > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f'[{org.slug}] {result["dispatched"]} reminder(s) {"would be sent" if dry_run else "dispatched"}.'
                    )
                )

        summary = {
            'generated_at': timezone.now().isoformat(),
            'dry_run': dry_run,
            'organizations_processed': len(org_results),
            'total_dispatched': total_dispatched,
            'org_results': org_results,
        }

        if options.get('output'):
            import os
            os.makedirs(os.path.dirname(options['output']), exist_ok=True)
            with open(options['output'], 'w') as fh:
                json.dump(summary, fh, indent=2)
            self.stdout.write(self.style.SUCCESS(f'Summary written to {options["output"]}'))

        self.stdout.write(
            self.style.SUCCESS(
                f'Done. {total_dispatched} total reminder(s) {"(dry-run)" if dry_run else "dispatched"} '
                f'across {len(org_results)} organization(s).'
            )
        )
        return json.dumps(summary)
