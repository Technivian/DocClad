
"""
Repository service layer for contracts
Provides abstraction between UI and data layer
"""
from datetime import date, timedelta

from django.contrib.auth.models import User
from contracts.models import Contract
from contracts.domain.contracts import ListParams, ContractData, ListResult
from django.core.paginator import Paginator
from django.db.models import Q, Case, When, Value, IntegerField
from django.template.defaultfilters import date as date_filter
from typing import List, Optional
from contracts.tenancy import get_user_organization, scope_queryset_for_organization
from contracts.services.queue_rows import (
    TERMINAL_STATUSES,
    activity_line_parts,
    assignee_map_for_contracts,
    latest_activity_map,
)
from contracts.templatetags.clmone_format import (
    contract_status_badge_tone,
    lifecycle_stage_badge_tone,
    lifecycle_steps,
    money,
)


class BulkUpdateValidationError(Exception):
    """Raised when bulk update payload fails validation."""


def get_repository_service(user: User):
    """Factory function for the Django-backed repository service."""
    return DjangoRepositoryService(user)

class DjangoRepositoryService:
    """Production repository service using Django ORM"""
    ALLOWED_BULK_UPDATE_FIELDS = {'status', 'lifecycle_stage'}
    
    def __init__(self, user: User):
        self.user = user
        self.organization = get_user_organization(user)

    def _to_contract_data(self, contract, assignee_map, activity_map, *, content=None):
        """Build a ContractData row, enriched with the same WorkQueue fields
        (stage/assignee/activity/status color) the Dashboard queue uses, so
        the JS-rendered Repository table draws from server-computed data
        instead of reimplementing stage ordering or status colors in JS."""
        assignee = assignee_map.get(contract.pk)
        assignee_name = None
        assignee_initial = None
        if assignee:
            assignee_name = assignee.get_full_name() or assignee.username
            assignee_initial = (assignee.first_name or assignee.username or '?')[:1].upper()

        activity_text, activity_time, activity_initial = activity_line_parts(activity_map.get(contract.pk))

        end_date = getattr(contract, 'end_date', None)
        due_overdue = bool(end_date and end_date < date.today() and contract.status not in TERMINAL_STATUSES)

        kwargs = dict(
            id=str(contract.id),
            title=contract.title,
            status=contract.status,
            status_display=contract.get_status_display(),
            counterparty=getattr(contract, 'counterparty', ''),
            value=float(contract.value) if hasattr(contract, 'value') and contract.value else None,
            start_date=contract.start_date.isoformat() if hasattr(contract, 'start_date') and contract.start_date else None,
            end_date=end_date.isoformat() if end_date else None,
            owner=(contract.owner or contract.created_by).get_full_name() or (contract.owner or contract.created_by).username
            if (contract.owner or contract.created_by) else 'Unassigned',
            updated_at=contract.updated_at.isoformat() if hasattr(contract, 'updated_at') and contract.updated_at else None,
            created_at=contract.created_at.isoformat() if contract.created_at else None,
            status_badge_tone=contract_status_badge_tone(contract.status),
            stage_badge_tone=lifecycle_stage_badge_tone(contract.lifecycle_stage),
            stage_steps=lifecycle_steps(contract),
            assignee_name=assignee_name,
            assignee_initial=assignee_initial,
            latest_activity_text=activity_text,
            latest_activity_time=activity_time,
            latest_activity_initial=activity_initial,
            value_display=money(contract.value, getattr(contract, 'currency', 'USD') or 'USD'),
            end_date_display=date_filter(end_date, 'd M Y') if end_date else None,
            due_overdue=due_overdue,
            contract_type_display=contract.get_contract_type_display(),
            stage_display=contract.get_lifecycle_stage_display(),
        )
        if content is not None:
            kwargs['content'] = content
        return ContractData(**kwargs)

    def list(self, params: ListParams) -> ListResult:
        """List contracts with filtering and pagination"""
        queryset = scope_queryset_for_organization(
            Contract.objects.select_related('created_by', 'owner').all(),
            self.organization,
        )
        
        # Apply search
        if params.q:
            queryset = queryset.filter(
                Q(title__icontains=params.q) |
                Q(counterparty__icontains=params.q) |
                Q(content__icontains=params.q)
            )
            queryset = queryset.annotate(
                search_rank=Case(
                    When(title__iexact=params.q, then=Value(0)),
                    When(title__istartswith=params.q, then=Value(1)),
                    default=Value(2),
                    output_field=IntegerField(),
                )
            )

        # Apply status filter
        if params.status:
            queryset = queryset.filter(status__in=params.status)

        # Apply the "30d attention" saved-view window — same ACTIVE +
        # end_date-within-N-days definition as the Dashboard Renewals queue
        # and the Repository "Expiring 30d" KPI, so the count and the rows
        # never disagree with each other.
        if params.expiring_within_days:
            today = date.today()
            queryset = queryset.filter(
                status='ACTIVE',
                end_date__gte=today,
                end_date__lte=today + timedelta(days=params.expiring_within_days),
            )

        # Apply type filter (if we had a contract_type field)
        if params.contract_type:
            if hasattr(Contract, 'contract_type'):
                queryset = queryset.filter(contract_type__in=params.contract_type)

        # Repository filters only expose fields that are backed by the
        # contract record or its approval route. Keep them server-side so
        # counts, pagination, and exported results all describe the same set.
        if params.owner:
            queryset = queryset.filter(owner_id__in=params.owner)
        if params.counterparty:
            queryset = queryset.filter(counterparty__in=params.counterparty)
        if params.risk_level:
            queryset = queryset.filter(risk_level__in=params.risk_level)
        if params.approval_state:
            queryset = queryset.filter(approval_requests__status__in=params.approval_state).distinct()
        
        # Apply sorting
        if params.sort == 'updated_desc':
            queryset = queryset.order_by('search_rank', '-updated_at') if params.q else queryset.order_by('-updated_at')
        elif params.sort == 'updated_asc':
            queryset = queryset.order_by('search_rank', 'updated_at') if params.q else queryset.order_by('updated_at')
        elif params.sort == 'title':
            queryset = queryset.order_by('search_rank', 'title') if params.q else queryset.order_by('title')
        elif params.sort == 'status':
            queryset = queryset.order_by('search_rank', 'status') if params.q else queryset.order_by('status')
        elif params.q:
            queryset = queryset.order_by('search_rank', '-updated_at')
            
        # Paginate
        paginator = Paginator(queryset, params.page_size)
        page_obj = paginator.get_page(params.page)
        page_contracts = list(page_obj)

        # Batch-resolve assignee/activity for just this page (mirrors the
        # Dashboard queue's per-tab batching) rather than one query per row.
        contract_ids = [c.pk for c in page_contracts]
        assignee_map = assignee_map_for_contracts(self.organization, contract_ids)
        activity_map = latest_activity_map(self.organization, contract_ids)

        # Convert to domain objects
        contracts = [
            self._to_contract_data(contract, assignee_map, activity_map)
            for contract in page_contracts
        ]

        return ListResult(
            contracts=contracts,
            total_count=paginator.count,
            page=params.page,
            page_size=params.page_size,
            total_pages=paginator.num_pages
        )
    
    def get_by_id(self, contract_id: str) -> Optional[ContractData]:
        """Get single contract by ID"""
        try:
            queryset = scope_queryset_for_organization(Contract.objects.all(), self.organization)
            contract = queryset.get(id=contract_id)
            assignee_map = assignee_map_for_contracts(self.organization, [contract.pk])
            activity_map = latest_activity_map(self.organization, [contract.pk])
            return self._to_contract_data(contract, assignee_map, activity_map, content=contract.content)
        except Contract.DoesNotExist:
            return None
    
    def bulk_update(self, contract_ids: List[str], updates: dict) -> int:
        """Bulk update contracts"""
        if not isinstance(updates, dict) or not updates:
            raise BulkUpdateValidationError('updates must be a non-empty object')

        disallowed_fields = set(updates.keys()) - self.ALLOWED_BULK_UPDATE_FIELDS
        if disallowed_fields:
            disallowed = ', '.join(sorted(disallowed_fields))
            raise BulkUpdateValidationError(f'updates contain unsupported fields: {disallowed}')

        if 'status' in updates:
            allowed_statuses = {value for value, _ in Contract.Status.choices}
            if updates['status'] not in allowed_statuses:
                raise BulkUpdateValidationError('status must be a valid contract status')

        if 'lifecycle_stage' in updates:
            allowed_stages = {
                value
                for value, _ in Contract._meta.get_field('lifecycle_stage').choices
            }
            if updates['lifecycle_stage'] not in allowed_stages:
                raise BulkUpdateValidationError('lifecycle_stage must be a valid lifecycle stage')

        from contracts.services.contract_lifecycle import (
            ContractTransitionError,
            get_contract_lifecycle_service,
        )
        lifecycle = get_contract_lifecycle_service()
        queryset = scope_queryset_for_organization(Contract.objects.filter(id__in=contract_ids), self.organization)
        updated_count = 0
        for contract in queryset.select_related('organization', 'created_by'):
            changed = False
            # Status changes go through the canonical lifecycle service so bulk
            # cannot bypass the transition graph / approval prerequisites.
            if 'status' in updates and contract.status != updates['status']:
                try:
                    lifecycle.transition(contract, updates['status'], self.user,
                                         reason='bulk_update')
                    changed = True
                except ContractTransitionError as exc:
                    raise BulkUpdateValidationError(
                        f'Contract {contract.id}: {exc}'
                    )
            if 'lifecycle_stage' in updates and contract.lifecycle_stage != updates['lifecycle_stage']:
                if not contract.can_transition_lifecycle_stage(updates['lifecycle_stage']):
                    raise BulkUpdateValidationError(
                        f'Contract {contract.id} cannot transition from {contract.lifecycle_stage} to {updates["lifecycle_stage"]}'
                    )
                contract.lifecycle_stage = updates['lifecycle_stage']
                contract.save(update_fields=['lifecycle_stage', 'updated_at'])
                changed = True
            if changed:
                updated_count += 1

        return updated_count
