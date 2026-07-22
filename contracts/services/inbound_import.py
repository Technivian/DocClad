"""Inbound import service for integrations."""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date

from contracts.models import Contract
from contracts.services.contract_import_lifecycle import (
    ImportLifecycleError,
    persist_contract_with_imported_lifecycle,
)


@dataclass
class ImportResult:
    imported_count: int
    skipped_count: int
    errors: list[dict]
    dry_run: bool


class InboundImportService:
    VALID_STATUSES = {
        'IN_PROGRESS', 'ACTIVE', 'EXPIRED', 'TERMINATED', 'CANCELLED', 'ARCHIVED',
        # Legacy aliases accepted on import and mapped below
        'DRAFT', 'PENDING', 'IN_REVIEW', 'APPROVED', 'COMPLETED',
    }
    VALID_CONTRACT_TYPES = None  # deprecated — use contract_type_catalogue.validate_import_contract_type
    VALID_STAGES = {
        'INTAKE', 'DRAFTING', 'INTERNAL_REVIEW', 'NEGOTIATION', 'APPROVAL',
        'SIGNATURE', 'EXECUTED', 'OBLIGATION_TRACKING', 'RENEWAL',
    }

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
                    raw_status = (row.get('status') or 'IN_PROGRESS').strip().upper() or 'IN_PROGRESS'
                    raw_stage = (row.get('lifecycle_stage') or '').strip().upper() or None
                    contract = Contract(
                        organization=org,
                        title=row.get('title', '').strip(),
                        counterparty=row.get('counterparty', '').strip(),
                        start_date=self._parse_date(row.get('start_date')),
                        end_date=self._parse_date(row.get('end_date')),
                        created_by=user,
                    )
                    from contracts.services.contract_type_catalogue import assign_contract_type
                    assign_contract_type(
                        contract,
                        code=(row.get('contract_type') or 'OTHER').strip(),
                    )
                    persist_contract_with_imported_lifecycle(
                        contract,
                        desired_status=raw_status,
                        desired_lifecycle_stage=raw_stage,
                        actor=user,
                        reason='inbound import',
                        source='inbound_import',
                    )
                    imported += 1
                except (ImportLifecycleError, Exception) as e:
                    errors.append({'row': i + 1, 'message': str(e)})
                    skipped += 1
            else:
                # Dry-run still rejects illegal status/stage pairs.
                try:
                    from contracts.services.contract_import_lifecycle import resolve_import_status_stage
                    raw_status = (row.get('status') or 'IN_PROGRESS').strip().upper() or 'IN_PROGRESS'
                    raw_stage = (row.get('lifecycle_stage') or '').strip().upper() or None
                    resolve_import_status_stage(status=raw_status, lifecycle_stage=raw_stage)
                    imported += 1
                except ImportLifecycleError as e:
                    errors.append({'row': i + 1, 'message': str(e)})
                    skipped += 1

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

        stage = row.get('lifecycle_stage', '').strip().upper()
        if stage and stage not in self.VALID_STAGES:
            errors.append(f'invalid lifecycle_stage "{stage}"')

        if status and stage:
            try:
                from contracts.services.contract_import_lifecycle import resolve_import_status_stage
                resolve_import_status_stage(status=status, lifecycle_stage=stage)
            except ImportLifecycleError as exc:
                errors.append(str(exc))

        contract_type = row.get('contract_type', '').strip().upper()
        if contract_type:
            from contracts.services.contract_type_catalogue import validate_import_contract_type
            errors.extend(validate_import_contract_type(contract_type))

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
