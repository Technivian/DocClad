from django.core.management.base import BaseCommand, CommandError

from contracts.models import Organization
from contracts.services.command_center import refresh_command_center_projection


class Command(BaseCommand):
    help = 'Refresh persisted Command Center saved views, work items, rail items, and review memo projections.'

    def add_arguments(self, parser):
        parser.add_argument('--organization', help='Organization slug or id. Omit to refresh every active organization.')

    def handle(self, *args, **options):
        selector = options.get('organization')
        organizations = Organization.objects.filter(is_active=True).order_by('id')
        if selector:
            if selector.isdigit():
                organizations = organizations.filter(id=int(selector))
            else:
                organizations = organizations.filter(slug=selector)
            if not organizations.exists():
                raise CommandError(f'No active organization found for {selector!r}.')

        total = {'saved_views': 0, 'work_items': 0, 'rail_items': 0, 'review_memos': 0}
        for organization in organizations:
            result = refresh_command_center_projection(organization)
            for key in total:
                total[key] += result[key]
            self.stdout.write(
                f'{organization.slug}: '
                f'{result["work_items"]} work items, '
                f'{result["rail_items"]} rail items, '
                f'{result["review_memos"]} review memos'
            )

        self.stdout.write(self.style.SUCCESS(
            'Command Center projection refreshed: '
            f'{total["work_items"]} work items, '
            f'{total["rail_items"]} rail items, '
            f'{total["review_memos"]} review memos'
        ))
