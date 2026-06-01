"""Inbound import service for integrations."""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date

from contracts.models import Contract

_ContractDoesNotExist = Contract.DoesNotExist


@dataclass
class ImportResult:
    imported_count: int
    skipped_count: int
    errors: list[dict]
    dry_run: bool


class InboundImportService:
    VALID_STATUSES = {'DRAFT', 'ACTIVE', 'EXPIRED', 'TERMINATED', 'ARCHIVED'}
    VALID_CONTRACT_TYPES = {'NDA', 'SERVICE', 'EMPLOYMENT', 'VENDOR', 'PARTNERSHIP', 'LEASE', 'OTHER'}

    def import_contracts_from_csv(self, org, csv_text: str, user, dry_run: bool = False) -> ImportResult:
        reader = csv.DictReader(io.StringIO(csv_text))
        rows = list(reader)
        return self._process_rows(org, rows, user, dry_run)

    def import_contracts_from_json(self, org, data: list[dict], user, dry_run: bool = False) -> ImportResult:
        return self._process_rows(org, data, user, dry_run)

    def _process_rows(self, org, rows: list[dict], user, dry_run: bool) -> ImportResult:
        imported = 0
        skipped = 0
        errors: list[dict] = []

        for i, row in enumerate(rows):
            row_errors = self.validate_import_row(row)
            if row_errors:
                errors.append({'row': i + 1, 'message': '; '.join(row_errors)})
                skipped += 1
                continue

            if not dry_run:
                try:
                    Contract.objects.create(
                        organization=org,
                        title=row.get('title', '').strip(),
                        counterparty=row.get('counterparty', '').strip(),
                        contract_type=row.get('contract_type', 'OTHER').strip().upper() or 'OTHER',
                        status=row.get('status', 'DRAFT').strip().upper() or 'DRAFT',
                        start_date=self._parse_date(row.get('start_date')),
                        end_date=self._parse_date(row.get('end_date')),
                        created_by=user,
                    )
                    imported += 1
                except Exception as e:
                    errors.append({'row': i + 1, 'message': str(e)})
                    skipped += 1
            else:
                imported += 1

        return ImportResult(
            imported_count=imported,
            skipped_count=skipped,
            errors=errors,
            dry_run=dry_run,
        )

    def validate_import_row(self, row: dict) -> list[str]:
        errors: list[str] = []

        title = row.get('title', '').strip()
        if not title:
            errors.append('title is required')

        status = row.get('status', '').strip().upper()
        if status and status not in self.VALID_STATUSES:
            errors.append(f'invalid status "{status}"')

        contract_type = row.get('contract_type', '').strip().upper()
        if contract_type and contract_type not in self.VALID_CONTRACT_TYPES:
            errors.append(f'invalid contract_type "{contract_type}"')

        for date_field in ('start_date', 'end_date'):
            val = row.get(date_field, '').strip()
            if val:
                try:
                    date.fromisoformat(val)
                except ValueError:
                    errors.append(f'{date_field} must be YYYY-MM-DD format')

        return errors

    @staticmethod
    def _parse_date(val: str | None) -> date | None:
        if not val or not val.strip():
            return None
        try:
            return date.fromisoformat(val.strip())
        except ValueError:
            return None


def get_inbound_import_service() -> InboundImportService:
    return InboundImportService()
