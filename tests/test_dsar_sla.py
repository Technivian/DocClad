"""Tests for DSAR SLA service, evidence bundle, management command, and API endpoints."""
from __future__ import annotations

import json
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_dsar_req(
    id=1,
    reference_number='DSAR-00001',
    request_type='ACCESS',
    status='RECEIVED',
    requester_name='Alice',
    requester_email='alice@example.com',
    description='Please provide my data.',
    received_date=None,
    due_date=None,
    extended=False,
    completed_date=None,
    assigned_to_id=None,
    assigned_to=None,
    organization_id=1,
    organization=None,
    requester_id_verified=False,
    response='',
    denial_reason='',
):
    m = MagicMock()
    m.id = id
    m.reference_number = reference_number
    m.request_type = request_type
    m.status = status
    m.requester_name = requester_name
    m.requester_email = requester_email
    m.description = description
    m.received_date = received_date or date.today() - timedelta(days=5)
    m.due_date = due_date or date.today() + timedelta(days=25)
    m.extended = extended
    m.completed_date = completed_date
    m.assigned_to_id = assigned_to_id
    m.assigned_to = assigned_to
    m.organization_id = organization_id
    m.organization = organization or MagicMock()
    m.requester_id_verified = requester_id_verified
    m.response = response
    m.denial_reason = denial_reason
    m.get_request_type_display.return_value = 'Right of Access'
    return m


# ---------------------------------------------------------------------------
# DSARService — SLA status
# ---------------------------------------------------------------------------

class TestDsarSlaStatus(SimpleTestCase):

    def _to_dto(self, req):
        from contracts.services.dsar import _to_dto
        return _to_dto(req)

    def test_on_track_with_days_remaining(self):
        req = _make_dsar_req(due_date=date.today() + timedelta(days=20))
        dto = self._to_dto(req)
        self.assertEqual(dto.sla_label, 'ON_TRACK')
        self.assertEqual(dto.days_remaining, 20)
        self.assertFalse(dto.is_overdue)

    def test_at_risk_within_7_days(self):
        req = _make_dsar_req(due_date=date.today() + timedelta(days=5))
        dto = self._to_dto(req)
        self.assertEqual(dto.sla_label, 'AT_RISK')
        self.assertFalse(dto.is_overdue)

    def test_overdue_past_due_date(self):
        req = _make_dsar_req(due_date=date.today() - timedelta(days=3))
        dto = self._to_dto(req)
        self.assertEqual(dto.sla_label, 'OVERDUE')
        self.assertTrue(dto.is_overdue)
        self.assertLess(dto.days_remaining, 0)

    def test_completed_not_overdue(self):
        req = _make_dsar_req(
            status='COMPLETED',
            due_date=date.today() - timedelta(days=2),
            completed_date=date.today() - timedelta(days=5),
        )
        dto = self._to_dto(req)
        self.assertEqual(dto.sla_label, 'COMPLETED')
        self.assertFalse(dto.is_overdue)

    def test_denied_not_overdue(self):
        req = _make_dsar_req(status='DENIED', due_date=date.today() - timedelta(days=10))
        dto = self._to_dto(req)
        self.assertEqual(dto.sla_label, 'DENIED')
        self.assertFalse(dto.is_overdue)

    def test_extended_flag_preserved(self):
        req = _make_dsar_req(extended=True)
        dto = self._to_dto(req)
        self.assertTrue(dto.is_extended)

    def test_assigned_to_is_none_when_no_user(self):
        req = _make_dsar_req(assigned_to_id=None)
        dto = self._to_dto(req)
        self.assertIsNone(dto.assigned_to)


# ---------------------------------------------------------------------------
# DSARService — create_request
# ---------------------------------------------------------------------------

class TestDsarServiceCreate(SimpleTestCase):

    def test_creates_with_default_due_date(self):
        mock_req = _make_dsar_req(
            received_date=date.today(),
            due_date=date.today() + timedelta(days=30),
        )
        with patch('contracts.services.dsar.DSARRequest') as MockModel:
            MockModel.objects.create.return_value = mock_req
            from contracts.services.dsar import get_dsar_service
            svc = get_dsar_service()
            dto = svc.create_request(
                organization=MagicMock(),
                request_type='ACCESS',
                requester_name='Alice',
                requester_email='alice@example.com',
                description='Data request.',
            )
        self.assertEqual(dto.request_type, 'ACCESS')
        self.assertEqual(dto.days_remaining, 30)
        MockModel.objects.create.assert_called_once()
        call_kwargs = MockModel.objects.create.call_args.kwargs
        self.assertEqual(call_kwargs['request_type'], 'ACCESS')

    def test_uses_provided_received_date(self):
        received = date.today() - timedelta(days=10)
        expected_due = received + timedelta(days=30)
        mock_req = _make_dsar_req(received_date=received, due_date=expected_due)
        with patch('contracts.services.dsar.DSARRequest') as MockModel:
            MockModel.objects.create.return_value = mock_req
            from contracts.services.dsar import get_dsar_service
            svc = get_dsar_service()
            svc.create_request(
                organization=MagicMock(),
                request_type='ERASURE',
                requester_name='Bob',
                requester_email='bob@example.com',
                description='Delete my data.',
                received_date=received,
            )
        call_kwargs = MockModel.objects.create.call_args.kwargs
        self.assertEqual(call_kwargs['received_date'], received)
        self.assertEqual(call_kwargs['due_date'], expected_due)


# ---------------------------------------------------------------------------
# DSARService — list_requests
# ---------------------------------------------------------------------------

class TestDsarServiceList(SimpleTestCase):

    def _list(self, reqs, status_filter=None, overdue_only=False):
        with patch('contracts.services.dsar.DSARRequest') as MockModel:
            MockModel.objects.filter.return_value.filter.return_value.order_by.return_value = reqs
            MockModel.objects.filter.return_value.order_by.return_value = reqs
            from contracts.services.dsar import get_dsar_service
            svc = get_dsar_service()
            return svc.list_requests(MagicMock(), status_filter=status_filter, overdue_only=overdue_only)

    def test_returns_all_requests(self):
        reqs = [_make_dsar_req(id=i) for i in range(3)]
        result = self._list(reqs)
        self.assertEqual(result.total, 3)

    def test_overdue_count(self):
        overdue = _make_dsar_req(id=1, due_date=date.today() - timedelta(days=5))
        on_track = _make_dsar_req(id=2, due_date=date.today() + timedelta(days=20))
        result = self._list([overdue, on_track])
        self.assertEqual(result.overdue_count, 1)
        self.assertEqual(result.at_risk_count, 0)

    def test_overdue_only_filter(self):
        overdue = _make_dsar_req(id=1, due_date=date.today() - timedelta(days=5))
        on_track = _make_dsar_req(id=2, due_date=date.today() + timedelta(days=20))
        result = self._list([overdue, on_track], overdue_only=True)
        self.assertEqual(result.total, 1)
        self.assertEqual(result.requests[0].id, 1)

    def test_at_risk_count(self):
        at_risk = _make_dsar_req(id=1, due_date=date.today() + timedelta(days=3))
        result = self._list([at_risk])
        self.assertEqual(result.at_risk_count, 1)


# ---------------------------------------------------------------------------
# DSARService — get_request / update_request
# ---------------------------------------------------------------------------

class TestDsarServiceGetUpdate(SimpleTestCase):

    def test_get_returns_dto(self):
        req = _make_dsar_req()
        with patch('contracts.services.dsar.DSARRequest') as MockModel:
            MockModel.objects.get.return_value = req
            from contracts.services.dsar import get_dsar_service
            dto = get_dsar_service().get_request(1, MagicMock())
        self.assertEqual(dto.reference_number, 'DSAR-00001')

    def test_get_returns_none_when_not_found(self):
        from contracts.models import DSARRequest as RealModel
        with patch('contracts.services.dsar.DSARRequest') as MockModel:
            MockModel.DoesNotExist = Exception
            MockModel.objects.get.side_effect = MockModel.DoesNotExist
            from contracts.services.dsar import get_dsar_service
            dto = get_dsar_service().get_request(999, MagicMock())
        self.assertIsNone(dto)

    def test_update_status_to_completed_sets_completed_date(self):
        req = _make_dsar_req(completed_date=None)
        with patch('contracts.services.dsar.DSARRequest') as MockModel:
            MockModel.objects.get.return_value = req
            from contracts.services.dsar import get_dsar_service
            dto = get_dsar_service().update_request(1, MagicMock(), status='COMPLETED')
        self.assertIsNotNone(dto)
        # completed_date set on model object
        self.assertEqual(req.completed_date, date.today())

    def test_update_returns_none_when_not_found(self):
        with patch('contracts.services.dsar.DSARRequest') as MockModel:
            MockModel.DoesNotExist = Exception
            MockModel.objects.get.side_effect = MockModel.DoesNotExist
            from contracts.services.dsar import get_dsar_service
            dto = get_dsar_service().update_request(999, MagicMock(), status='DENIED')
        self.assertIsNone(dto)


# ---------------------------------------------------------------------------
# DSARService — generate_evidence_bundle
# ---------------------------------------------------------------------------

class TestDsarEvidenceBundle(SimpleTestCase):

    def _bundle(self, req=None):
        req = req or _make_dsar_req()
        with patch('contracts.services.dsar.DSARRequest') as MockModel:
            MockModel.objects.get.return_value = req
            from contracts.services.dsar import get_dsar_service
            return get_dsar_service().generate_evidence_bundle(1, MagicMock())

    def test_bundle_has_schema_version(self):
        bundle = self._bundle()
        self.assertEqual(bundle['schema_version'], '1.0')

    def test_bundle_has_sla_block(self):
        bundle = self._bundle()
        self.assertIn('sla', bundle)
        sla = bundle['sla']
        self.assertIn('days_remaining', sla)
        self.assertIn('is_overdue', sla)
        self.assertIn('is_extended', sla)
        self.assertEqual(sla['sla_days'], 30)

    def test_bundle_has_requester_block(self):
        bundle = self._bundle()
        self.assertIn('requester', bundle)
        self.assertEqual(bundle['requester']['name'], 'Alice')
        self.assertEqual(bundle['requester']['email'], 'alice@example.com')

    def test_bundle_returns_none_when_not_found(self):
        with patch('contracts.services.dsar.DSARRequest') as MockModel:
            MockModel.DoesNotExist = Exception
            MockModel.objects.get.side_effect = MockModel.DoesNotExist
            from contracts.services.dsar import get_dsar_service
            result = get_dsar_service().generate_evidence_bundle(999, MagicMock())
        self.assertIsNone(result)

    def test_bundle_sla_label_overdue(self):
        req = _make_dsar_req(due_date=date.today() - timedelta(days=5))
        bundle = self._bundle(req)
        self.assertEqual(bundle['sla_label'], 'OVERDUE')

    def test_bundle_extended_adds_extension_days(self):
        req = _make_dsar_req(extended=True)
        bundle = self._bundle(req)
        self.assertEqual(bundle['sla']['extension_days'], 60)


# ---------------------------------------------------------------------------
# DSAR API — list / create
# ---------------------------------------------------------------------------

class TestDsarListApi(SimpleTestCase):

    def _get(self, mock_result):
        with (
            patch('contracts.api.views.get_user_organization') as mock_org,
            patch('contracts.api.views.get_dsar_service') as mock_svc_fn,
        ):
            mock_org.return_value = MagicMock()
            mock_svc = MagicMock()
            mock_svc.list_requests.return_value = mock_result
            mock_svc_fn.return_value = mock_svc
            from contracts.api.views import dsar_list_api
            req = MagicMock()
            req.method = 'GET'
            req.GET = {}
            req.user = MagicMock()
            return dsar_list_api(req)

    def test_get_returns_200(self):
        from contracts.services.dsar import DSARListResult
        result = DSARListResult(requests=[], total=0, overdue_count=0, at_risk_count=0)
        resp = self._get(result)
        self.assertEqual(resp.status_code, 200)

    def test_get_response_has_counts(self):
        from contracts.services.dsar import DSARListResult
        result = DSARListResult(requests=[], total=5, overdue_count=2, at_risk_count=1)
        resp = self._get(result)
        data = json.loads(resp.content)
        self.assertEqual(data['total'], 5)
        self.assertEqual(data['overdue_count'], 2)
        self.assertEqual(data['at_risk_count'], 1)

    def test_post_creates_dsar(self):
        mock_dto = MagicMock()
        mock_dto.id = 1
        mock_dto.reference_number = 'DSAR-00001'
        mock_dto.request_type = 'ACCESS'
        mock_dto.status = 'RECEIVED'
        mock_dto.sla_label = 'ON_TRACK'
        mock_dto.days_remaining = 30
        mock_dto.is_overdue = False
        mock_dto.is_extended = False
        mock_dto.received_date = str(date.today())
        mock_dto.due_date = str(date.today() + timedelta(days=30))
        mock_dto.completed_date = None
        mock_dto.requester_name = 'Alice'
        mock_dto.requester_email = 'alice@example.com'
        mock_dto.assigned_to = None

        body = json.dumps({
            'request_type': 'ACCESS',
            'requester_name': 'Alice',
            'requester_email': 'alice@example.com',
            'description': 'Test request',
        }).encode()

        with (
            patch('contracts.api.views.get_user_organization') as mock_org,
            patch('contracts.api.views.get_dsar_service') as mock_svc_fn,
        ):
            mock_org.return_value = MagicMock()
            mock_svc = MagicMock()
            mock_svc.create_request.return_value = mock_dto
            mock_svc_fn.return_value = mock_svc
            from contracts.api.views import dsar_list_api
            req = MagicMock()
            req.method = 'POST'
            req.body = body
            req.user = MagicMock()
            resp = dsar_list_api(req)

        self.assertEqual(resp.status_code, 201)
        data = json.loads(resp.content)
        self.assertTrue(data['ok'])
        self.assertEqual(data['dsar']['reference_number'], 'DSAR-00001')

    def test_post_missing_fields_returns_400(self):
        with (
            patch('contracts.api.views.get_user_organization') as mock_org,
            patch('contracts.api.views.get_dsar_service'),
        ):
            mock_org.return_value = MagicMock()
            from contracts.api.views import dsar_list_api
            req = MagicMock()
            req.method = 'POST'
            req.body = json.dumps({'request_type': 'ACCESS'}).encode()
            req.user = MagicMock()
            resp = dsar_list_api(req)
        self.assertEqual(resp.status_code, 400)


# ---------------------------------------------------------------------------
# DSAR API — detail
# ---------------------------------------------------------------------------

class TestDsarDetailApi(SimpleTestCase):

    def _dto(self, **kwargs):
        d = MagicMock()
        d.id = kwargs.get('id', 1)
        d.reference_number = kwargs.get('reference_number', 'DSAR-00001')
        d.request_type = 'ACCESS'
        d.status = kwargs.get('status', 'RECEIVED')
        d.sla_label = 'ON_TRACK'
        d.days_remaining = 20
        d.is_overdue = False
        d.is_extended = False
        d.received_date = str(date.today())
        d.due_date = str(date.today() + timedelta(days=20))
        d.completed_date = None
        d.requester_name = 'Alice'
        d.requester_email = 'alice@example.com'
        d.assigned_to = None
        return d

    def test_get_returns_dsar(self):
        with (
            patch('contracts.api.views.get_user_organization') as mock_org,
            patch('contracts.api.views.get_dsar_service') as mock_svc_fn,
        ):
            mock_org.return_value = MagicMock()
            mock_svc = MagicMock()
            mock_svc.get_request.return_value = self._dto()
            mock_svc_fn.return_value = mock_svc
            from contracts.api.views import dsar_detail_api
            req = MagicMock()
            req.method = 'GET'
            req.user = MagicMock()
            resp = dsar_detail_api(req, dsar_id=1)
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertIn('dsar', data)

    def test_get_not_found_returns_404(self):
        with (
            patch('contracts.api.views.get_user_organization') as mock_org,
            patch('contracts.api.views.get_dsar_service') as mock_svc_fn,
        ):
            mock_org.return_value = MagicMock()
            mock_svc = MagicMock()
            mock_svc.get_request.return_value = None
            mock_svc_fn.return_value = mock_svc
            from contracts.api.views import dsar_detail_api
            req = MagicMock()
            req.method = 'GET'
            req.user = MagicMock()
            resp = dsar_detail_api(req, dsar_id=999)
        self.assertEqual(resp.status_code, 404)

    def test_patch_updates_dsar(self):
        with (
            patch('contracts.api.views.get_user_organization') as mock_org,
            patch('contracts.api.views.get_dsar_service') as mock_svc_fn,
        ):
            mock_org.return_value = MagicMock()
            mock_svc = MagicMock()
            mock_svc.update_request.return_value = self._dto(status='IN_PROGRESS')
            mock_svc_fn.return_value = mock_svc
            from contracts.api.views import dsar_detail_api
            req = MagicMock()
            req.method = 'PATCH'
            req.body = json.dumps({'status': 'IN_PROGRESS'}).encode()
            req.user = MagicMock()
            resp = dsar_detail_api(req, dsar_id=1)
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data['ok'])


# ---------------------------------------------------------------------------
# DSAR API — evidence
# ---------------------------------------------------------------------------

class TestDsarEvidenceApi(SimpleTestCase):

    def test_returns_bundle(self):
        bundle = {
            'schema_version': '1.0',
            'reference_number': 'DSAR-00001',
            'sla': {'days_remaining': 15, 'is_overdue': False, 'is_extended': False,
                    'sla_days': 30, 'extension_days': 0, 'received_date': '2026-01-01',
                    'due_date': '2026-01-31', 'completed_date': None},
            'sla_label': 'ON_TRACK',
            'request_type': 'ACCESS',
            'request_type_label': 'Right of Access',
            'status': 'RECEIVED',
            'requester': {'name': 'Alice', 'email': 'alice@example.com', 'identity_verified': False},
            'description': 'Test',
            'response': '',
            'denial_reason': '',
            'assigned_to': None,
            'organization_id': 1,
            'generated_at': '2026-06-01',
        }
        with (
            patch('contracts.api.views.get_user_organization') as mock_org,
            patch('contracts.api.views.get_dsar_service') as mock_svc_fn,
        ):
            mock_org.return_value = MagicMock()
            mock_svc = MagicMock()
            mock_svc.generate_evidence_bundle.return_value = bundle
            mock_svc_fn.return_value = mock_svc
            from contracts.api.views import dsar_evidence_api
            req = MagicMock()
            req.method = 'GET'
            req.user = MagicMock()
            resp = dsar_evidence_api(req, dsar_id=1)
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data['schema_version'], '1.0')
        self.assertIn('sla', data)

    def test_not_found_returns_404(self):
        with (
            patch('contracts.api.views.get_user_organization') as mock_org,
            patch('contracts.api.views.get_dsar_service') as mock_svc_fn,
        ):
            mock_org.return_value = MagicMock()
            mock_svc = MagicMock()
            mock_svc.generate_evidence_bundle.return_value = None
            mock_svc_fn.return_value = mock_svc
            from contracts.api.views import dsar_evidence_api
            req = MagicMock()
            req.method = 'GET'
            req.user = MagicMock()
            resp = dsar_evidence_api(req, dsar_id=999)
        self.assertEqual(resp.status_code, 404)
