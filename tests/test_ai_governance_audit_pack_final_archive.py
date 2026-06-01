import json
import tarfile
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase


class AIGovernanceAuditPackFinalArchiveTests(SimpleTestCase):
    def test_generate_and_verify_final_archive(self):
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            release_index = tmp / 'release-index.json'
            signoff_receipt = tmp / 'signoff-receipt.json'
            release_index.write_text(json.dumps({'release': '2026.06.01', 'items': ['a', 'b']}), encoding='utf-8')
            signoff_receipt.write_text(json.dumps({'signed_off_by': 'qa', 'approved': True}), encoding='utf-8')

            out = StringIO()
            call_command(
                'generate_ai_governance_audit_pack_final_archive',
                f'--release-index-path={release_index}',
                f'--signoff-receipt-path={signoff_receipt}',
                f'--output-dir={tmpdir}',
                stdout=out,
            )
            payload = json.loads(out.getvalue())
            self.assertEqual(payload['status'], 'generated')

            archive_path = Path(payload['archive_path'])
            self.assertTrue(archive_path.exists())
            with tarfile.open(archive_path, 'r:gz') as tar:
                self.assertEqual(sorted(member.name for member in tar.getmembers() if member.isfile()), [
                    'release-index.json',
                    'signoff-receipt.json',
                ])

            verify_out = StringIO()
            call_command(
                'verify_ai_governance_audit_pack_final_archive',
                f"--archive-path={payload['archive_path']}",
                f"--sha256-path={payload['sha256_path']}",
                stdout=verify_out,
            )
            verify_payload = json.loads(verify_out.getvalue())
            self.assertEqual(verify_payload['status'], 'verified')
            self.assertEqual(verify_payload['files_verified'], 2)

    def test_verify_final_archive_fails_when_tampered(self):
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            release_index = tmp / 'release-index.json'
            signoff_receipt = tmp / 'signoff-receipt.json'
            release_index.write_text(json.dumps({'release': '2026.06.01'}), encoding='utf-8')
            signoff_receipt.write_text(json.dumps({'signed_off_by': 'qa'}), encoding='utf-8')

            out = StringIO()
            call_command(
                'generate_ai_governance_audit_pack_final_archive',
                f'--release-index-path={release_index}',
                f'--signoff-receipt-path={signoff_receipt}',
                f'--output-dir={tmpdir}',
                stdout=out,
            )
            payload = json.loads(out.getvalue())
            archive_path = Path(payload['archive_path'])
            with archive_path.open('ab') as handle:
                handle.write(b'tampered')

            with self.assertRaises(CommandError):
                call_command(
                    'verify_ai_governance_audit_pack_final_archive',
                    f"--archive-path={payload['archive_path']}",
                    f"--sha256-path={payload['sha256_path']}",
                )
