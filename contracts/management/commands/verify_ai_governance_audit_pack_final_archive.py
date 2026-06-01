import json

from django.core.management import BaseCommand, CommandError

from contracts.services.final_archive import verify_final_archive


class Command(BaseCommand):
    help = 'Verify the AI governance audit pack final archive hash and contents.'

    def add_arguments(self, parser):
        parser.add_argument('--archive-path', required=True)
        parser.add_argument('--sha256-path', default='')

    def handle(self, *args, **options):
        try:
            result = verify_final_archive(
                archive_path=options['archive_path'],
                sha256_path=options.get('sha256_path') or '',
            )
        except ValueError as exc:
            raise CommandError(str(exc))

        self.stdout.write(json.dumps(result, indent=2, sort_keys=True))
