"""Contract versioning service — immutable snapshots with diff comparison."""
from __future__ import annotations

import difflib
import hashlib
from dataclasses import dataclass
from typing import Optional

from contracts.models import Contract, ContractVersion


@dataclass
class VersionDiff:
    contract_id: int
    v1: int
    v2: int
    unified_diff: list[str]
    added_lines: int
    removed_lines: int


class ContractVersionService:
    def create_version(
        self,
        contract: Contract,
        changed_by=None,
        change_summary: str = '',
    ) -> ContractVersion:
        last = (
            ContractVersion.objects.filter(contract=contract)
            .order_by('-version_number')
            .first()
        )
        next_number = (last.version_number + 1) if last else 1
        content = contract.content or ''
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        return ContractVersion.objects.create(
            contract=contract,
            version_number=next_number,
            title_snapshot=contract.title,
            status_snapshot=contract.status,
            content_snapshot=content,
            content_hash=content_hash,
            change_summary=change_summary,
            changed_by=changed_by,
        )

    def list_versions(self, contract_id: int, org) -> list[ContractVersion]:
        return list(
            ContractVersion.objects.filter(
                contract_id=contract_id,
                contract__organization=org,
            ).select_related('changed_by').order_by('-version_number')
        )

    def get_version(self, contract_id: int, version_number: int, org) -> ContractVersion:
        return ContractVersion.objects.get(
            contract_id=contract_id,
            contract__organization=org,
            version_number=version_number,
        )

    def diff_versions(self, contract_id: int, v1: int, v2: int, org) -> VersionDiff:
        ver1 = self.get_version(contract_id, v1, org)
        ver2 = self.get_version(contract_id, v2, org)
        lines1 = ver1.content_snapshot.splitlines(keepends=True)
        lines2 = ver2.content_snapshot.splitlines(keepends=True)
        diff = list(
            difflib.unified_diff(
                lines1,
                lines2,
                fromfile=f'v{v1}',
                tofile=f'v{v2}',
                lineterm='',
            )
        )
        added = sum(1 for l in diff if l.startswith('+') and not l.startswith('+++'))
        removed = sum(1 for l in diff if l.startswith('-') and not l.startswith('---'))
        return VersionDiff(
            contract_id=contract_id,
            v1=v1,
            v2=v2,
            unified_diff=diff,
            added_lines=added,
            removed_lines=removed,
        )


def get_version_service() -> ContractVersionService:
    return ContractVersionService()
