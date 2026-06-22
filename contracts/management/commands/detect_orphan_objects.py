"""detect_orphan_objects — report S3/MinIO objects with no matching Document row.

Usage
-----
    python manage.py detect_orphan_objects
    python manage.py detect_orphan_objects --min-age-hours 2 --output json
    python manage.py detect_orphan_objects --prefix documents/ --min-age-hours 0

This command NEVER deletes.  It lists candidate orphaned objects so an operator
can review and act manually.  The output contains only:
  - a hash of the full object key (SHA-256, hex) for unambiguous identification
  - the last path component (filename, no directory) for human context
  - last-modified timestamp and size in bytes
  - the matching verdict (orphan / matched / too-young / error)

The command never logs bucket names, credentials, endpoint URLs, signed URLs,
or any document content.  Candidates are printed to stdout; operational messages
go to stderr via Django's management command machinery.

Exit codes
----------
  0   scan completed; zero orphans found
  1   scan completed; at least one orphan detected (useful for alerting)
  2   scan could not complete (storage backend error, mis-configuration)
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone as dt_timezone, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


class Command(BaseCommand):
    help = (
        'Report S3-compatible objects that have no matching Document DB row. '
        'Never deletes. Use the output as an operator review report.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--prefix', default='documents/',
            help='Object key prefix to scan (default: documents/).',
        )
        parser.add_argument(
            '--min-age-hours', type=float, default=1.0,
            dest='min_age_hours',
            help=(
                'Minimum object age in hours before an unmatched object is '
                'classified as an orphan candidate. Objects younger than this '
                'threshold may still be in-flight during an upload. '
                'Default: 1.0.'
            ),
        )
        parser.add_argument(
            '--output', choices=['text', 'json'], default='text',
            help='Output format (default: text).',
        )
        parser.add_argument(
            '--limit', type=int, default=500,
            help='Maximum number of objects to scan (default: 500).',
        )

    def handle(self, *args, **options):
        prefix = options['prefix']
        min_age_hours = options['min_age_hours']
        output_fmt = options['output']
        limit = options['limit']

        try:
            bucket, s3_client = self._get_storage_client()
        except Exception as exc:
            raise CommandError(f'Could not initialize storage client: {exc}') from exc

        self.stderr.write(
            f'Scanning (prefix={prefix!r}, min_age={min_age_hours}h, limit={limit}) …'
        )

        cutoff = datetime.now(dt_timezone.utc) - timedelta(hours=min_age_hours)
        results = []
        scan_errors = []

        try:
            paginator = s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(
                Bucket=bucket,
                Prefix=prefix,
                PaginationConfig={'MaxItems': limit},
            )
            for page in pages:
                for obj in page.get('Contents', []):
                    key = obj['Key']
                    last_modified = obj['LastModified']
                    size = obj['Size']
                    verdict, reason = self._classify(key, last_modified, cutoff)
                    results.append({
                        'key_hash': hashlib.sha256(key.encode()).hexdigest(),
                        'key_suffix': key.split('/')[-1],
                        'last_modified': last_modified.isoformat(),
                        'size_bytes': size,
                        'verdict': verdict,
                        'reason': reason,
                    })
        except Exception as exc:
            scan_errors.append(str(exc))
            self.stderr.write(self.style.ERROR(f'Scan error: {exc}'))

        orphans = [r for r in results if r['verdict'] == 'orphan']
        matched = [r for r in results if r['verdict'] == 'matched']
        too_young = [r for r in results if r['verdict'] == 'too-young']
        errors = [r for r in results if r['verdict'] == 'error']

        summary = {
            'scanned': len(results),
            'orphan_candidates': len(orphans),
            'matched': len(matched),
            'too_young': len(too_young),
            'errors': len(errors),
            'scan_errors': scan_errors,
            'min_age_hours': min_age_hours,
        }

        if output_fmt == 'json':
            self.stdout.write(json.dumps({'summary': summary, 'orphans': orphans}, indent=2))
        else:
            self.stdout.write(f'Scanned : {len(results)}')
            self.stdout.write(f'Matched : {len(matched)}')
            self.stdout.write(f'Too young: {len(too_young)}')
            self.stdout.write(f'Errors  : {len(errors)}')
            self.stdout.write(f'ORPHANS : {len(orphans)}')
            if orphans:
                self.stdout.write('\nOrphan candidates (key_hash / suffix / age / size):')
                for o in orphans:
                    self.stdout.write(
                        f"  {o['key_hash'][:16]}…  {o['key_suffix']!r:40s} "
                        f"  {o['last_modified']}  {o['size_bytes']}B"
                    )

        if scan_errors:
            sys.exit(2)
        if orphans:
            sys.exit(1)
        sys.exit(0)

    def _classify(self, key: str, last_modified: datetime, cutoff: datetime):
        """Return (verdict, reason) for a single object key."""
        from contracts.models import Document
        try:
            if last_modified > cutoff:
                return 'too-young', 'within min-age window; may be in-flight'
            exists = Document.objects.filter(file=key).exists()
            if exists:
                return 'matched', 'active Document row found'
            # Also check soft-deleted documents — object must be retained.
            deleted = Document.objects.filter(file=key, is_deleted=True).exists()
            if deleted:
                return 'matched', 'soft-deleted Document row found (object must be retained)'
            return 'orphan', 'no Document row (active or deleted) references this key'
        except Exception as exc:
            return 'error', str(exc)

    def _get_storage_client(self):
        """Return (bucket_name, boto3_client) from the current storage configuration.

        Raises if the default storage is not S3-compatible.  Never logs
        credentials or endpoint URLs.
        """
        import boto3

        storages_conf = getattr(settings, 'STORAGES', {})
        default_opts = storages_conf.get('default', {}).get('OPTIONS', {})
        backend = storages_conf.get('default', {}).get('BACKEND', '')

        if 's3' not in backend.lower():
            raise CommandError(
                'Default storage backend is not S3-compatible; '
                'detect_orphan_objects requires an S3/MinIO backend.'
            )

        bucket = default_opts.get('bucket_name') or ''
        if not bucket:
            raise CommandError('bucket_name is not configured in STORAGES default OPTIONS.')

        client_kwargs = {'region_name': default_opts.get('region_name') or 'us-east-1'}
        if default_opts.get('access_key'):
            client_kwargs['aws_access_key_id'] = default_opts['access_key']
        if default_opts.get('secret_key'):
            client_kwargs['aws_secret_access_key'] = default_opts['secret_key']
        if default_opts.get('endpoint_url'):
            client_kwargs['endpoint_url'] = default_opts['endpoint_url']

        s3 = boto3.client('s3', **client_kwargs)
        return bucket, s3
