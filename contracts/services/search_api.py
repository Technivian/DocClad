"""Search & Analytics API service layer."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from django.db.models import Count, Q

from contracts.models import Contract, ClauseTemplate, SearchTelemetryEvent

_SearchTelemetryEventDoesNotExist = SearchTelemetryEvent.DoesNotExist

# Upper bound on the ranked clause window used for pagination. Clause libraries
# are small (tens to low hundreds per org); this keeps pagination totals correct
# without an unbounded ranking pass.
_CLAUSE_SEARCH_MAX = 500


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

        lifecycle_stage = filters.get('lifecycle_stage')
        if lifecycle_stage:
            qs = qs.filter(lifecycle_stage=lifecycle_stage)

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
                'lifecycle_stage': c.lifecycle_stage,
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
        stages = list(
            base_qs.values('lifecycle_stage').annotate(count=Count('lifecycle_stage')).order_by('-count')
        )
        contract_types = list(
            base_qs.values('contract_type').annotate(count=Count('contract_type')).order_by('-count')
        )
        jurisdictions = list(
            base_qs.exclude(jurisdiction='').values('jurisdiction').annotate(count=Count('jurisdiction')).order_by('-count')
        )

        return {
            'statuses': [{'value': r['status'], 'count': r['count']} for r in statuses],
            'lifecycle_stages': [{'value': r['lifecycle_stage'], 'count': r['count']} for r in stages],
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
            # The model field is `jurisdiction_scope`; there is no `jurisdiction`
            # field, so the old lookup raised FieldError (500) on any filter.
            qs = qs.filter(jurisdiction_scope__icontains=jurisdiction)

        is_mandatory = filters.get('is_mandatory')
        if is_mandatory is not None:
            qs = qs.filter(is_mandatory=is_mandatory)

        # Coerce to a safe string: the API may pass None or a non-str value and
        # the ranker tokenizes with .lower(), which would 500 on bad input.
        q = (str(q) if q is not None else '').strip()

        offset = (page - 1) * page_size
        if q:
            # rank_clause_templates_semantic returns a *list* (ranked + filtered
            # by relevance), NOT a queryset — paginate the list, not the qs.
            # Cap the ranked window generously so pagination totals stay correct
            # for realistically-sized clause libraries.
            ranked = rank_clause_templates_semantic(qs, q, limit=_CLAUSE_SEARCH_MAX)
            total = len(ranked)
            clauses = ranked[offset: offset + page_size]
        else:
            qs = qs.order_by('-updated_at', 'pk')  # deterministic ordering
            total = qs.count()
            clauses = list(qs[offset: offset + page_size])

        results = [
            {
                'id': c.id,
                'title': c.title,
                'category_id': getattr(c, 'category_id', None),
                'jurisdiction': getattr(c, 'jurisdiction_scope', ''),
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
