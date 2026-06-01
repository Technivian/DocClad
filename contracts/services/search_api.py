"""Search & Analytics API service layer."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from django.db.models import Count, Q

from contracts.models import Contract, ClauseTemplate, SearchTelemetryEvent

_SearchTelemetryEventDoesNotExist = SearchTelemetryEvent.DoesNotExist


@dataclass
class PaginatedResult:
    results: list[dict[str, Any]]
    total: int
    page: int
    page_size: int
    total_pages: int


class ContractSearchAPIService:
    def search_contracts(
        self,
        org,
        q: str = '',
        filters: dict | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResult:
        filters = filters or {}
        qs = Contract.objects.filter(organization=org)

        if q:
            qs = qs.filter(
                Q(title__icontains=q) | Q(content__icontains=q) | Q(counterparty__icontains=q)
            )

        status = filters.get('status')
        if status:
            qs = qs.filter(status=status)

        contract_type = filters.get('contract_type')
        if contract_type:
            qs = qs.filter(contract_type=contract_type)

        jurisdiction = filters.get('jurisdiction')
        if jurisdiction:
            qs = qs.filter(jurisdiction__icontains=jurisdiction)

        date_from = filters.get('date_from')
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)

        date_to = filters.get('date_to')
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        total = qs.count()
        offset = (page - 1) * page_size
        contracts = qs.order_by('-updated_at')[offset: offset + page_size]

        results = [
            {
                'id': c.id,
                'title': c.title,
                'status': c.status,
                'contract_type': c.contract_type,
                'counterparty': c.counterparty,
                'created_at': c.created_at.isoformat() if c.created_at else None,
            }
            for c in contracts
        ]

        total_pages = math.ceil(total / page_size) if page_size else 0
        return PaginatedResult(
            results=results,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    def get_contract_facets(self, org) -> dict:
        base_qs = Contract.objects.filter(organization=org)

        statuses = list(
            base_qs.values('status').annotate(count=Count('status')).order_by('-count')
        )
        contract_types = list(
            base_qs.values('contract_type').annotate(count=Count('contract_type')).order_by('-count')
        )
        jurisdictions = list(
            base_qs.exclude(jurisdiction='').values('jurisdiction').annotate(count=Count('jurisdiction')).order_by('-count')
        )

        return {
            'statuses': [{'value': r['status'], 'count': r['count']} for r in statuses],
            'contract_types': [{'value': r['contract_type'], 'count': r['count']} for r in contract_types],
            'jurisdictions': [{'value': r['jurisdiction'], 'count': r['count']} for r in jurisdictions],
        }

    def record_search_event(self, org, query: str, result_count: int, user) -> None:
        SearchTelemetryEvent.objects.create(
            organization=org,
            query=query,
            result_count=result_count,
            performed_by=user,
            search_type='contract',
        )


class ClauseSearchAPIService:
    def search_clauses(
        self,
        org,
        q: str = '',
        filters: dict | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResult:
        from contracts.services.semantic_search import rank_clause_templates_semantic

        filters = filters or {}
        qs = ClauseTemplate.objects.filter(organization=org)

        category_id = filters.get('category_id')
        if category_id:
            qs = qs.filter(category_id=category_id)

        jurisdiction = filters.get('jurisdiction')
        if jurisdiction:
            qs = qs.filter(jurisdiction__icontains=jurisdiction)

        is_mandatory = filters.get('is_mandatory')
        if is_mandatory is not None:
            qs = qs.filter(is_mandatory=is_mandatory)

        if q:
            qs = rank_clause_templates_semantic(q, qs)

        total = qs.count()
        offset = (page - 1) * page_size
        clauses = qs[offset: offset + page_size]

        results = [
            {
                'id': c.id,
                'title': c.title,
                'category_id': getattr(c, 'category_id', None),
                'jurisdiction': getattr(c, 'jurisdiction', ''),
                'is_mandatory': getattr(c, 'is_mandatory', False),
            }
            for c in clauses
        ]

        total_pages = math.ceil(total / page_size) if page_size else 0
        return PaginatedResult(
            results=results,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    def record_search_event(self, org, query: str, result_count: int, user) -> None:
        SearchTelemetryEvent.objects.create(
            organization=org,
            query=query,
            result_count=result_count,
            performed_by=user,
            search_type='clause',
        )


def get_contract_search_service() -> ContractSearchAPIService:
    return ContractSearchAPIService()


def get_clause_search_service() -> ClauseSearchAPIService:
    return ClauseSearchAPIService()
