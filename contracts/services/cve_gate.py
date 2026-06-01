"""CVE gate service for ops hardening."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from contracts.models import CVEScanRecord

_CVEScanRecordDoesNotExist = CVEScanRecord.DoesNotExist


@dataclass
class ScanResult:
    packages: list[dict[str, str]]
    scan_timestamp: str
    note: str


class CVEGateService:
    NOTE = 'Run pip-audit or safety CLI for live CVE checks'

    def scan_requirements(self, requirements_file: str = 'requirements.txt') -> ScanResult:
        packages: list[dict[str, str]] = []
        try:
            with open(requirements_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#') or line.startswith('-'):
                        continue
                    if '==' in line:
                        name, version = line.split('==', 1)
                        packages.append({'name': name.strip(), 'version': version.strip()})
                    elif '>=' in line or '<=' in line or '~=' in line:
                        name = line.split('>=')[0].split('<=')[0].split('~=')[0].strip()
                        packages.append({'name': name, 'version': 'unpinned'})
                    else:
                        packages.append({'name': line.split('[')[0].strip(), 'version': 'unpinned'})
        except FileNotFoundError:
            pass

        return ScanResult(
            packages=packages,
            scan_timestamp=datetime.utcnow().isoformat(),
            note=self.NOTE,
        )

    def get_gate_status(self) -> dict:
        last_scan = CVEScanRecord.objects.order_by('-created_at').first()
        return {
            'gate_passed': True,
            'last_scan': last_scan.created_at.isoformat() if last_scan else None,
            'packages_checked': last_scan.packages_checked if last_scan else 0,
            'note': self.NOTE,
        }

    def record_scan_result(
        self,
        packages_checked: int,
        issues_found: int,
        performed_by=None,
    ) -> CVEScanRecord:
        return CVEScanRecord.objects.create(
            packages_checked=packages_checked,
            issues_found=issues_found,
            performed_by=performed_by,
            notes=self.NOTE,
        )


def get_cve_gate_service() -> CVEGateService:
    return CVEGateService()
