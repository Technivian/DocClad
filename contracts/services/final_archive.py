from __future__ import annotations

import hashlib
import json
import tarfile
from dataclasses import dataclass
from pathlib import Path

from django.utils import timezone


FINAL_ARCHIVE_MEMBER_NAMES = (
    'release-index.json',
    'signoff-receipt.json',
)


@dataclass
class FinalArchiveResult:
    archive_path: Path
    sha256_path: Path
    file_count: int


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def create_final_archive(release_index_path: str, signoff_receipt_path: str, output_dir: str) -> FinalArchiveResult:
    release_index = Path(release_index_path).expanduser().resolve()
    signoff_receipt = Path(signoff_receipt_path).expanduser().resolve()

    if not release_index.exists() or not release_index.is_file():
        raise ValueError(f'Release index not found: {release_index}')
    if not signoff_receipt.exists() or not signoff_receipt.is_file():
        raise ValueError(f'Signoff receipt not found: {signoff_receipt}')

    out_dir = Path(output_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    stamp = timezone.now().strftime('%Y%m%dT%H%M%SZ')
    base = f'ai-governance-audit-pack-final-archive-{stamp}'
    archive_path = out_dir / f'{base}.tar.gz'
    sha256_path = out_dir / f'{base}.sha256'

    with tarfile.open(archive_path, 'w:gz') as tar:
        tar.add(release_index, arcname=FINAL_ARCHIVE_MEMBER_NAMES[0])
        tar.add(signoff_receipt, arcname=FINAL_ARCHIVE_MEMBER_NAMES[1])

    archive_hash = _sha256_file(archive_path)
    sha256_path.write_text(f'{archive_hash}  {archive_path.name}\n', encoding='utf-8')
    return FinalArchiveResult(
        archive_path=archive_path,
        sha256_path=sha256_path,
        file_count=2,
    )


def verify_final_archive(archive_path: str, sha256_path: str = '') -> dict:
    archive = Path(archive_path).expanduser().resolve()
    sha_file = Path(sha256_path).expanduser().resolve() if sha256_path else archive.with_suffix('').with_suffix('.sha256')

    if not archive.exists():
        raise ValueError(f'Archive not found: {archive}')
    if not sha_file.exists():
        raise ValueError(f'SHA file not found: {sha_file}')

    expected_hash = sha_file.read_text(encoding='utf-8').strip().split()[0]
    computed_hash = _sha256_file(archive)
    if expected_hash != computed_hash:
        raise ValueError('Final archive SHA256 mismatch.')

    with tarfile.open(archive, 'r:gz') as tar:
        members = [member for member in tar.getmembers() if member.isfile()]
        member_names = [member.name for member in members]
        if sorted(member_names) != sorted(FINAL_ARCHIVE_MEMBER_NAMES):
            raise ValueError('Final archive contents mismatch.')

        for expected_name in FINAL_ARCHIVE_MEMBER_NAMES:
            member = tar.extractfile(expected_name)
            if member is None:
                raise ValueError(f'Missing final archive member: {expected_name}')
            json.loads(member.read().decode('utf-8'))

    return {
        'status': 'verified',
        'archive_path': str(archive),
        'sha256': computed_hash,
        'files_verified': len(FINAL_ARCHIVE_MEMBER_NAMES),
    }
