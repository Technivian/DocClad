"""Management command: generate_renewal_tasks

Scans contracts with approaching end_date or renewal_date and auto-creates
Deadline tasks from the renewal playbook templates.

Usage:
    python manage.py generate_renewal_tasks [--organization-slug SLUG]
                                            [--days-lookahead N]
                                            [--dry-run]
                                            [--output PATH]
"""
import json
import os

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from contracts.models import Organization
from contracts.services.renewal_playbook import generate_renewal_tasks


class Command(BaseCommand):
    help = 'Auto-generate renewal-playbook Deadline tasks for approaching contract milestones.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--organization-slug',
            dest='organization_slug',
            default=None,
            help='Limit to a specific organization slug. If omitted, runs for all organizations.',
        )
        parser.add_argument(
            '--days-lookahead',
            dest='days_lookahead',
            type=int,
            default=90,
            help='Number of days ahead to scan for approaching milestones (default: 90).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Show what would be created without writing to DB.',
        )
        parser.add_argument(
            '--output',
            dest='output',
            default=None,
            help='Path to write a JSON evidence artifact.',
        )

    def handle(self, *args, **options):
        slug = options['organization_slug']
        days_lookahead = options['days_lookahead']
        dry_run = options['dry_run']

        if slug:
            orgs = list(Organization.objects.filter(slug=slug))
            if not orgs:
                raise CommandError(f'Organization with slug {slug!r} not found.')
        else:
            orgs = list(Organization.objects.all())

        total_created = 0
        total_skipped = 0
        org_results = []

        for org in orgs:
            result = generate_renewal_tasks(
                organization=org,
                days_lookahead=days_lookahead,
                dry_run=dry_run,
            )
            total_created += result['created']
            total_skipped += result['skipped']
            org_results.append({
                'organization': org.slug,
                **result,
            })
            self.stdout.write(
                f'[{org.slug}] scanned={result["contracts_scanned"]} '
                f'created={result["created"]} skipped={result["skipped"]}'
                + (' (dry-run)' if dry_run else '')
            )

        summary = {
            'generated_at': timezone.now().isoformat(),
            'dry_run': dry_run,
            'days_lookahead': days_lookahead,
            'organizations_processed': len(org_results),
            'total_created': total_created,
            'total_skipped': total_skipped,
            'org_results': org_results,
        }

        if options.get('output'):
            os.makedirs(os.path.dirname(os.path.abspath(options['output'])), exist_ok=True)
            with open(options['output'], 'w') as fh:
                json.dump(summary, fh, indent=2)
            self.stdout.write(self.style.SUCCESS(f'Evidence artifact written to {options["output"]}'))

        self.stdout.write(
            self.style.SUCCESS(
                f'Done. Created {total_created} task(s), skipped {total_skipped} existing '
                f'across {len(org_results)} organization(s).'
            )
        )
        return json.dumps(summary)
