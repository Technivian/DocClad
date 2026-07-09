from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from contracts.models import Organization
from contracts.services.demo_command_center import seed_demo_command_center_workflows


class Command(BaseCommand):
    help = 'Seed the demo-ready DPA, MSA, and NDA workflow rows for the Command Center.'

    def add_arguments(self, parser):
        parser.add_argument('--organization-slug', required=True, help='Organization slug that should receive the demo workflow rows.')
        parser.add_argument('--username', required=True, help='Username that will own the seeded demo workflow rows.')

    def handle(self, *args, **options):
        organization = Organization.objects.filter(slug=options['organization_slug']).first()
        if organization is None:
            raise CommandError(f"Organization '{options['organization_slug']}' was not found.")

        User = get_user_model()
        user = User.objects.filter(username=options['username']).first()
        if user is None:
            raise CommandError(f"User '{options['username']}' was not found.")

        seeded = seed_demo_command_center_workflows(organization=organization, user=user)
        self.stdout.write(self.style.SUCCESS(
            'Seeded demo Command Center workflows: '
            + ', '.join(f'{row.key}#{row.workflow_id}' for row in seeded)
        ))
