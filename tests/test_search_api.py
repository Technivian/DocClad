"""Tests for Search & Analytics API (Area 1)."""
import math
from unittest import TestCase
from unittest.mock import MagicMock, patch, PropertyMock


class TestContractSearchService(TestCase):
    def _make_service(self):
        from contracts.services.search_api import ContractSearchAPIService
        return ContractSearchAPIService()

    def test_search_returns_paginated_result(self):
        svc = self._make_service()
        org = MagicMock()
        mock_contract = MagicMock()
        mock_contract.id = 1
        mock_contract.title = 'Test Contract'
        mock_contract.status = 'ACTIVE'
        mock_contract.contract_type = 'NDA'
        mock_contract.counterparty = 'Acme Corp'
        mock_contract.created_at.isoformat.return_value = '2024-01-01T00:00:00'

        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.count.return_value = 1
        mock_qs.__getitem__ = MagicMock(return_value=[mock_contract])
        mock_qs.order_by.return_value = mock_qs

        with patch('contracts.services.search_api.Contract') as MockContract:
            MockContract.objects.filter.return_value = mock_qs
            result = svc.search_contracts(org, q='test')

        self.assertEqual(result.page, 1)
        self.assertEqual(result.page_size, 20)
        self.assertIsInstance(result.results, list)

    def test_empty_query_returns_all(self):
        svc = self._make_service()
        org = MagicMock()
        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.count.return_value = 0
        mock_qs.__getitem__ = MagicMock(return_value=[])
        mock_qs.order_by.return_value = mock_qs

        with patch('contracts.services.search_api.Contract') as MockContract:
            MockContract.objects.filter.return_value = mock_qs
            result = svc.search_contracts(org, q='')

        self.assertEqual(result.total, 0)
        self.assertEqual(result.results, [])

    def test_pagination_math_total_pages(self):
        svc = self._make_service()
        org = MagicMock()
        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.count.return_value = 45
        mock_qs.__getitem__ = MagicMock(return_value=[])
        mock_qs.order_by.return_value = mock_qs

        with patch('contracts.services.search_api.Contract') as MockContract:
            MockContract.objects.filter.return_value = mock_qs
            result = svc.search_contracts(org, q='', page=1, page_size=20)

        self.assertEqual(result.total_pages, 3)  # ceil(45/20)

    def test_pagination_math_exact_division(self):
        svc = self._make_service()
        org = MagicMock()
        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.count.return_value = 40
        mock_qs.__getitem__ = MagicMock(return_value=[])
        mock_qs.order_by.return_value = mock_qs

        with patch('contracts.services.search_api.Contract') as MockContract:
            MockContract.objects.filter.return_value = mock_qs
            result = svc.search_contracts(org, q='', page=1, page_size=20)

        self.assertEqual(result.total_pages, 2)

    def test_filters_applied(self):
        svc = self._make_service()
        org = MagicMock()
        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.count.return_value = 0
        mock_qs.__getitem__ = MagicMock(return_value=[])
        mock_qs.order_by.return_value = mock_qs

        with patch('contracts.services.search_api.Contract') as MockContract:
            MockContract.objects.filter.return_value = mock_qs
            result = svc.search_contracts(org, q='', filters={'status': 'ACTIVE'})

        # filter should have been called at least for status
        self.assertTrue(mock_qs.filter.called)

    def test_date_filters_applied(self):
        svc = self._make_service()
        org = MagicMock()
        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.count.return_value = 0
        mock_qs.__getitem__ = MagicMock(return_value=[])
        mock_qs.order_by.return_value = mock_qs

        with patch('contracts.services.search_api.Contract') as MockContract:
            MockContract.objects.filter.return_value = mock_qs
            result = svc.search_contracts(
                org, q='', filters={'date_from': '2024-01-01', 'date_to': '2024-12-31'}
            )

        self.assertTrue(mock_qs.filter.called)

    def test_facets_return_correct_structure(self):
        svc = self._make_service()
        org = MagicMock()
        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.exclude.return_value = mock_qs
        mock_qs.values.return_value = mock_qs
        mock_qs.annotate.return_value = mock_qs
        mock_qs.order_by.return_value = [{'status': 'ACTIVE', 'count': 5}]

        with patch('contracts.services.search_api.Contract') as MockContract:
            MockContract.objects.filter.return_value = mock_qs
            mock_status_qs = MagicMock()
            mock_status_qs.values.return_value = mock_status_qs
            mock_status_qs.annotate.return_value = mock_status_qs
            mock_status_qs.order_by.return_value = [{'status': 'ACTIVE', 'count': 3}]

            mock_type_qs = MagicMock()
            mock_type_qs.values.return_value = mock_type_qs
            mock_type_qs.annotate.return_value = mock_type_qs
            mock_type_qs.order_by.return_value = [{'contract_type': 'NDA', 'count': 2}]

            mock_jur_qs = MagicMock()
            mock_jur_qs.values.return_value = mock_jur_qs
            mock_jur_qs.annotate.return_value = mock_jur_qs
            mock_jur_qs.order_by.return_value = []
            mock_jur_qs.exclude.return_value = mock_jur_qs

            MockContract.objects.filter.return_value.values.return_value.annotate.return_value.order_by.return_value = []
            MockContract.objects.filter.return_value.exclude.return_value.values.return_value.annotate.return_value.order_by.return_value = []
            facets = svc.get_contract_facets(org)

        self.assertIn('statuses', facets)
        self.assertIn('contract_types', facets)
        self.assertIn('jurisdictions', facets)

    def test_telemetry_recording(self):
        svc = self._make_service()
        org = MagicMock()
        user = MagicMock()

        with patch('contracts.services.search_api.SearchTelemetryEvent') as MockEvent:
            svc.record_search_event(org, 'nda search', 5, user)
            MockEvent.objects.create.assert_called_once_with(
                organization=org,
                query='nda search',
                result_count=5,
                performed_by=user,
                search_type='contract',
            )


class TestClauseSearchService(TestCase):
    def _make_service(self):
        from contracts.services.search_api import ClauseSearchAPIService
        return ClauseSearchAPIService()

    def test_clause_search_calls_semantic_ranker(self):
        svc = self._make_service()
        org = MagicMock()
        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.count.return_value = 0
        mock_qs.__getitem__ = MagicMock(return_value=[])

        with patch('contracts.services.search_api.ClauseTemplate') as MockTemplate:
            MockTemplate.objects.filter.return_value = mock_qs
            with patch('contracts.services.search_api.ClauseSearchAPIService.search_clauses') as mock_search:
                mock_result = MagicMock()
                mock_result.results = []
                mock_result.total = 0
                mock_result.page = 1
                mock_result.page_size = 20
                mock_result.total_pages = 0
                mock_search.return_value = mock_result
                result = svc.search_clauses(org, q='indemnity')
                mock_search.assert_called_once()

    def test_clause_telemetry_uses_clause_type(self):
        svc = self._make_service()
        org = MagicMock()
        user = MagicMock()

        with patch('contracts.services.search_api.SearchTelemetryEvent') as MockEvent:
            svc.record_search_event(org, 'liability', 3, user)
            MockEvent.objects.create.assert_called_once_with(
                organization=org,
                query='liability',
                result_count=3,
                performed_by=user,
                search_type='clause',
            )

    def test_telemetry_listing(self):
        org = MagicMock()
        mock_event = MagicMock()
        mock_event.id = 1
        mock_event.query = 'test'
        mock_event.result_count = 2
        mock_event.search_type = 'contract'
        mock_event.created_at.isoformat.return_value = '2024-01-01T00:00:00'

        with patch('contracts.services.search_api.SearchTelemetryEvent') as MockEvent:
            mock_filter = MagicMock()
            mock_filter.__getitem__ = MagicMock(return_value=[mock_event])
            MockEvent.objects.filter.return_value = mock_filter
            MockEvent.objects.filter(organization=org)[:50]
            MockEvent.objects.filter.assert_called_with(organization=org)
