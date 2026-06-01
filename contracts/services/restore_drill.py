"""Restore drill service for ops hardening."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from django.utils import timezone

from contracts.models import RestoreDrill

_RestoreDrillDoesNotExist = RestoreDrill.DoesNotExist


class RestoreDrillService:
    def schedule_drill(
        self,
        org,
        drill_date: date,
        rto_hours: float,
        rpo_hours: float,
        performed_by=None,
    ) -> RestoreDrill:
        return RestoreDrill.objects.create(
            organization=org,
            drill_date=drill_date,
            rto_target_hours=rto_hours,
            rpo_target_hours=rpo_hours,
            performed_by=performed_by,
        )

    def record_result(
        self,
        drill_id: int,
        actual_rto_minutes: int,
        actual_rpo_minutes: int,
        passed: bool,
        notes: str = '',
        performed_by=None,
    ) -> RestoreDrill:
        try:
            drill = RestoreDrill.objects.get(pk=drill_id)
        except _RestoreDrillDoesNotExist:
            raise ValueError(f'Drill {drill_id} not found')

        drill.actual_rto_minutes = actual_rto_minutes
        drill.actual_rpo_minutes = actual_rpo_minutes
        drill.passed = passed
        drill.notes = notes
        drill.completed_at = timezone.now()
        if performed_by:
            drill.performed_by = performed_by
        drill.save()
        return drill

    def list_drills(self, org, limit: int = 20) -> list[dict]:
        drills = RestoreDrill.objects.filter(organization=org)[:limit]
        return [self._drill_to_dict(d) for d in drills]

    def get_drill_summary(self, org) -> dict:
        drills = RestoreDrill.objects.filter(organization=org)
        total = drills.count()
        passed = drills.filter(passed=True).count()
        failed = drills.filter(passed=False).count()
        last = drills.filter(completed_at__isnull=False).order_by('-completed_at').first()

        completed = drills.filter(
            actual_rto_minutes__isnull=False,
            actual_rpo_minutes__isnull=False,
        )
        avg_rto = None
        avg_rpo = None
        if completed.exists():
            from django.db.models import Avg
            stats = completed.aggregate(avg_rto=Avg('actual_rto_minutes'), avg_rpo=Avg('actual_rpo_minutes'))
            avg_rto = round(stats['avg_rto'], 1) if stats['avg_rto'] is not None else None
            avg_rpo = round(stats['avg_rpo'], 1) if stats['avg_rpo'] is not None else None

        return {
            'total_drills': total,
            'passed': passed,
            'failed': failed,
            'last_drill_at': last.completed_at.isoformat() if last and last.completed_at else None,
            'avg_rto_minutes': avg_rto,
            'avg_rpo_minutes': avg_rpo,
        }

    @staticmethod
    def _drill_to_dict(d: RestoreDrill) -> dict:
        return {
            'id': d.id,
            'drill_date': d.drill_date.isoformat() if d.drill_date else None,
            'rto_target_hours': d.rto_target_hours,
            'rpo_target_hours': d.rpo_target_hours,
            'actual_rto_minutes': d.actual_rto_minutes,
            'actual_rpo_minutes': d.actual_rpo_minutes,
            'passed': d.passed,
            'notes': d.notes,
            'completed_at': d.completed_at.isoformat() if d.completed_at else None,
            'created_at': d.created_at.isoformat(),
        }


def get_restore_drill_service() -> RestoreDrillService:
    return RestoreDrillService()
