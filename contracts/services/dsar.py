"""DSAR SLA service — countdown tracking + evidence bundle generation."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from contracts.models import DSARRequest

GDPR_SLA_DAYS = 30
GDPR_EXTENSION_DAYS = 60  # additional days when extended


@dataclass
class DSARSlaStatus:
    reference_number: str
    request_type: str
    status: str
    received_date: str
    due_date: str
    days_remaining: int
    is_overdue: bool
    is_extended: bool
    sla_label: str  # ON_TRACK | AT_RISK | OVERDUE | COMPLETED | DENIED
    completed_date: Optional[str] = None
    requester_name: str = ''
    requester_email: str = ''
    assigned_to: Optional[str] = None
    id: Optional[int] = None


@dataclass
class DSARListResult:
    requests: list[DSARSlaStatus] = field(default_factory=list)
    total: int = 0
    overdue_count: int = 0
    at_risk_count: int = 0


def _sla_label(status: str, is_overdue: bool, days_remaining: int) -> str:
    if status in ('COMPLETED', 'DENIED'):
        return status
    if is_overdue:
        return 'OVERDUE'
    if days_remaining <= 7:
        return 'AT_RISK'
    return 'ON_TRACK'


def _to_dto(req) -> DSARSlaStatus:
    today = date.today()
    due = req.due_date
    if isinstance(due, str):
        from datetime import datetime
        due = datetime.strptime(due, '%Y-%m-%d').date()

    is_overdue = req.status not in ('COMPLETED', 'DENIED') and today > due
    days_remaining = (due - today).days

    assigned_str = None
    if req.assigned_to_id:
        try:
            u = req.assigned_to
            assigned_str = u.get_full_name() or u.username
        except Exception:
            pass

    completed_str = str(req.completed_date) if req.completed_date else None

    return DSARSlaStatus(
        id=req.id,
        reference_number=req.reference_number,
        request_type=req.request_type,
        status=req.status,
        received_date=str(req.received_date),
        due_date=str(req.due_date),
        days_remaining=days_remaining,
        is_overdue=is_overdue,
        is_extended=req.extended,
        sla_label=_sla_label(req.status, is_overdue, days_remaining),
        completed_date=completed_str,
        requester_name=req.requester_name,
        requester_email=req.requester_email,
        assigned_to=assigned_str,
    )


class DSARService:
    def create_request(
        self,
        organization,
        request_type: str,
        requester_name: str,
        requester_email: str,
        description: str,
        received_date: Optional[date] = None,
        assigned_to=None,
        client=None,
        created_by=None,
    ) -> DSARSlaStatus:

        received = received_date or date.today()
        due = received + timedelta(days=GDPR_SLA_DAYS)

        req = DSARRequest.objects.create(
            organization=organization,
            request_type=request_type,
            requester_name=requester_name,
            requester_email=requester_email,
            description=description,
            received_date=received,
            due_date=due,
            assigned_to=assigned_to,
            client=client,
            created_by=created_by,
        )
        return _to_dto(req)

    def list_requests(
        self,
        organization,
        status_filter: Optional[str] = None,
        overdue_only: bool = False,
    ) -> DSARListResult:

        qs = DSARRequest.objects.filter(organization=organization).order_by('due_date')
        if status_filter:
            qs = qs.filter(status=status_filter)

        dtos = [_to_dto(r) for r in qs]

        if overdue_only:
            dtos = [d for d in dtos if d.is_overdue]

        overdue = sum(1 for d in dtos if d.is_overdue)
        at_risk = sum(1 for d in dtos if d.sla_label == 'AT_RISK')

        return DSARListResult(
            requests=dtos,
            total=len(dtos),
            overdue_count=overdue,
            at_risk_count=at_risk,
        )

    def get_request(self, request_id: int, organization) -> Optional[DSARSlaStatus]:

        try:
            req = DSARRequest.objects.get(id=request_id, organization=organization)
        except DSARRequest.DoesNotExist:
            return None
        return _to_dto(req)

    def update_request(self, request_id: int, organization, **kwargs) -> Optional[DSARSlaStatus]:

        try:
            req = DSARRequest.objects.get(id=request_id, organization=organization)
        except DSARRequest.DoesNotExist:
            return None

        allowed = {
            'status', 'response', 'denial_reason', 'extended',
            'assigned_to', 'requester_id_verified', 'completed_date',
        }
        for key, val in kwargs.items():
            if key in allowed:
                setattr(req, key, val)

        # Auto-extend due_date when extended flag is toggled on
        if kwargs.get('extended') and not req.extended:
            req.due_date = req.due_date + timedelta(days=GDPR_EXTENSION_DAYS)
            req.status = 'EXTENDED'

        # Auto-set completed_date when marking completed/denied
        if kwargs.get('status') in ('COMPLETED', 'DENIED') and not req.completed_date:
            req.completed_date = date.today()

        req.save()
        return _to_dto(req)

    def generate_evidence_bundle(self, request_id: int, organization) -> Optional[dict]:

        try:
            req = DSARRequest.objects.get(id=request_id, organization=organization)
        except DSARRequest.DoesNotExist:
            return None

        dto = _to_dto(req)
        today = date.today()

        return {
            'schema_version': '1.0',
            'generated_at': today.isoformat(),
            'reference_number': dto.reference_number,
            'request_type': dto.request_type,
            'request_type_label': req.get_request_type_display(),
            'status': dto.status,
            'sla_label': dto.sla_label,
            'requester': {
                'name': req.requester_name,
                'email': req.requester_email,
                'identity_verified': req.requester_id_verified,
            },
            'sla': {
                'received_date': dto.received_date,
                'due_date': dto.due_date,
                'completed_date': dto.completed_date,
                'days_remaining': dto.days_remaining,
                'is_overdue': dto.is_overdue,
                'is_extended': dto.is_extended,
                'sla_days': GDPR_SLA_DAYS,
                'extension_days': GDPR_EXTENSION_DAYS if dto.is_extended else 0,
            },
            'description': req.description,
            'response': req.response,
            'denial_reason': req.denial_reason,
            'assigned_to': dto.assigned_to,
            'organization_id': req.organization_id,
        }


def get_dsar_service() -> DSARService:
    return DSARService()
