import json

from django.core.management import BaseCommand, CommandError

from contracts.services.final_archive import create_final_archive


class Command(BaseCommand):
    help = 'Generate the AI governance audit pack final archive and SHA256 sidecar.'

    def add_arguments(self, parser):
        parser.add_argument('--release-index-path', required=True)
        parser.add_argument('--signoff-receipt-path', required=True)
        parser.add_argument('--output-dir', default='docs/evidence/final-archive')

    def handle(self, *args, **options):
        try:
            result = create_final_archive(
                release_index_path=options['release_index_path'],
                signoff_receipt_path=options['signoff_receipt_path'],
                output_dir=options['output_dir'],
            )
        except ValueError as exc:
            raise CommandError(str(exc))

        payload = {
            'status': 'generated',
            'archive_path': str(result.archive_path),
            'sha256_path': str(result.sha256_path),
            'files_included': result.file_count,
        }
        self.stdout.write(json.dumps(payload, indent=2, sort_keys=True))
