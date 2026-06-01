"""Tests for contract versioning service and API."""
import json
from unittest.mock import MagicMock, patch
from django.test import SimpleTestCase


def _make_contract(id=1, title='Test Contract', status='DRAFT', content='Initial content.', org=None):
    c = MagicMock()
    c.pk = id
    c.title = title
    c.status = status
    c.content = content
    c.organization = org or MagicMock()
    return c


def _make_version(id=1, version_number=1, title='T', status='DRAFT',
                  content='text', content_hash='abc', change_summary='', changed_by=None,
                  created_at=None):
    v = MagicMock()
    v.pk = id
    v.version_number = version_number
    v.title_snapshot = title
    v.status_snapshot = status
    v.content_snapshot = content
    v.content_hash = content_hash
    v.change_summary = change_summary
    v.changed_by = changed_by
    v.created_at = created_at
    return v


# ---------------------------------------------------------------------------
# Service tests
# ---------------------------------------------------------------------------

class TestContractVersionService(SimpleTestCase):

    @patch('contracts.services.contract_versions.ContractVersion')
    def test_create_first_version(self, MockCV):
        MockCV.objects.filter.return_value.order_by.return_value.first.return_value = None
        MockCV.objects.create.return_value = _make_version(version_number=1)
        from contracts.services.contract_versions import ContractVersionService
        svc = ContractVersionService()
        contract = _make_contract(content='Hello')
        ver = svc.create_version(contract, changed_by=None, change_summary='initial')
        MockCV.objects.create.assert_called_once()
        call_kwargs = MockCV.objects.create.call_args.kwargs
        self.assertEqual(call_kwargs['version_number'], 1)
        self.assertEqual(call_kwargs['content_snapshot'], 'Hello')
        self.assertEqual(call_kwargs['change_summary'], 'initial')

    @patch('contracts.services.contract_versions.ContractVersion')
    def test_create_second_version_increments(self, MockCV):
        last = _make_version(version_number=3)
        MockCV.objects.filter.return_value.order_by.return_value.first.return_value = last
        MockCV.objects.create.return_value = _make_version(version_number=4)
        from contracts.services.contract_versions import ContractVersionService
        svc = ContractVersionService()
        svc.create_version(_make_contract(), changed_by=None)
        call_kwargs = MockCV.objects.create.call_args.kwargs
        self.assertEqual(call_kwargs['version_number'], 4)

    @patch('contracts.services.contract_versions.ContractVersion')
    def test_create_version_hashes_content(self, MockCV):
        import hashlib
        MockCV.objects.filter.return_value.order_by.return_value.first.return_value = None
        MockCV.objects.create.return_value = _make_version()
        from contracts.services.contract_versions import ContractVersionService
        svc = ContractVersionService()
        contract = _make_contract(content='Some content here')
        svc.create_version(contract)
        call_kwargs = MockCV.objects.create.call_args.kwargs
        expected_hash = hashlib.sha256('Some content here'.encode()).hexdigest()
        self.assertEqual(call_kwargs['content_hash'], expected_hash)

    @patch('contracts.services.contract_versions.ContractVersion')
    def test_list_versions_scoped_to_org(self, MockCV):
        org = MagicMock()
        versions = [_make_version(version_number=2), _make_version(version_number=1)]
        MockCV.objects.filter.return_value.select_related.return_value.order_by.return_value = versions
        from contracts.services.contract_versions import ContractVersionService
        svc = ContractVersionService()
        result = svc.list_versions(1, org)
        MockCV.objects.filter.assert_called_once_with(contract_id=1, contract__organization=org)
        self.assertEqual(result, versions)

    @patch('contracts.services.contract_versions.ContractVersion')
    def test_get_version(self, MockCV):
        ver = _make_version(version_number=2)
        org = MagicMock()
        MockCV.objects.get.return_value = ver
        from contracts.services.contract_versions import ContractVersionService
        svc = ContractVersionService()
        result = svc.get_version(1, 2, org)
        MockCV.objects.get.assert_called_once_with(contract_id=1, contract__organization=org, version_number=2)
        self.assertEqual(result, ver)

    @patch('contracts.services.contract_versions.ContractVersion')
    def test_diff_versions_counts_lines(self, MockCV):
        v1 = _make_version(version_number=1, content='line1\nline2\nline3\n')
        v2 = _make_version(version_number=2, content='line1\nline2 modified\nline3\nnew line\n')
        org = MagicMock()
        MockCV.objects.get.side_effect = [v1, v2]
        from contracts.services.contract_versions import ContractVersionService
        svc = ContractVersionService()
        diff = svc.diff_versions(1, 1, 2, org)
        self.assertEqual(diff.v1, 1)
        self.assertEqual(diff.v2, 2)
        self.assertGreater(diff.added_lines, 0)
        self.assertGreater(diff.removed_lines, 0)
        self.assertIsInstance(diff.unified_diff, list)

    @patch('contracts.services.contract_versions.ContractVersion')
    def test_diff_identical_versions_zero_changes(self, MockCV):
        v1 = _make_version(version_number=1, content='same\n')
        v2 = _make_version(version_number=2, content='same\n')
        MockCV.objects.get.side_effect = [v1, v2]
        from contracts.services.contract_versions import ContractVersionService
        svc = ContractVersionService()
        diff = svc.diff_versions(1, 1, 2, MagicMock())
        self.assertEqual(diff.added_lines, 0)
        self.assertEqual(diff.removed_lines, 0)


# ---------------------------------------------------------------------------
# API tests
# ---------------------------------------------------------------------------

class TestContractVersionsApi(SimpleTestCase):

    def _req(self, method='GET', body=None):
        req = MagicMock()
        req.method = method
        req.body = json.dumps(body).encode() if body else b''
        req.GET = {}
        req.user = MagicMock()
        req.user.is_authenticated = True
        return req

    @patch('contracts.api.views.get_user_organization')
    @patch('contracts.api.views.get_version_service')
    @patch('contracts.api.views.Contract')
    def test_get_versions_list(self, MockContract, mock_svc_factory, mock_org):
        mock_org.return_value = MagicMock()
        ver = _make_version(created_at=None)
        ver.changed_by = None
        mock_svc = MagicMock()
        mock_svc.list_versions.return_value = [ver]
        mock_svc_factory.return_value = mock_svc
        from contracts.api.views import contract_versions_api
        resp = contract_versions_api(self._req(), contract_id=1)
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertIn('versions', data)

    @patch('contracts.api.views.get_user_organization')
    @patch('contracts.api.views.get_version_service')
    @patch('contracts.api.views.Contract')
    def test_post_creates_version(self, MockContract, mock_svc_factory, mock_org):
        mock_org.return_value = MagicMock()
        MockContract.objects.get.return_value = _make_contract()
        ver = _make_version(created_at=None)
        ver.changed_by = None
        mock_svc = MagicMock()
        mock_svc.create_version.return_value = ver
        mock_svc_factory.return_value = mock_svc
        from contracts.api.views import contract_versions_api
        req = self._req(method='POST', body={'change_summary': 'draft v2'})
        resp = contract_versions_api(req, contract_id=1)
        self.assertEqual(resp.status_code, 201)
        data = json.loads(resp.content)
        self.assertTrue(data['ok'])

    @patch('contracts.api.views.get_user_organization')
    @patch('contracts.api.views.get_version_service')
    @patch('contracts.api.views.ContractVersion')
    def test_get_version_detail(self, MockCV, mock_svc_factory, mock_org):
        mock_org.return_value = MagicMock()
        ver = _make_version(created_at=None)
        ver.changed_by = None
        mock_svc = MagicMock()
        mock_svc.get_version.return_value = ver
        mock_svc_factory.return_value = mock_svc
        from contracts.api.views import contract_version_detail_api
        resp = contract_version_detail_api(self._req(), contract_id=1, version_number=1)
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertIn('version', data)

    @patch('contracts.api.views.get_user_organization')
    @patch('contracts.api.views.get_version_service')
    def test_get_version_detail_not_found(self, mock_svc_factory, mock_org):
        mock_org.return_value = MagicMock()
        from contracts.models import ContractVersion
        mock_svc = MagicMock()
        mock_svc.get_version.side_effect = ContractVersion.DoesNotExist()
        mock_svc_factory.return_value = mock_svc
        from contracts.api.views import contract_version_detail_api
        resp = contract_version_detail_api(self._req(), contract_id=1, version_number=99)
        self.assertEqual(resp.status_code, 404)

    @patch('contracts.api.views.get_user_organization')
    @patch('contracts.api.views.get_version_service')
    def test_diff_missing_params_returns_400(self, mock_svc_factory, mock_org):
        mock_org.return_value = MagicMock()
        from contracts.api.views import contract_version_diff_api
        req = self._req()
        req.GET = {}
        resp = contract_version_diff_api(req, contract_id=1)
        self.assertEqual(resp.status_code, 400)

    @patch('contracts.api.views.get_user_organization')
    @patch('contracts.api.views.get_version_service')
    def test_diff_returns_diff(self, mock_svc_factory, mock_org):
        mock_org.return_value = MagicMock()
        from contracts.services.contract_versions import VersionDiff
        mock_svc = MagicMock()
        mock_svc.diff_versions.return_value = VersionDiff(
            contract_id=1, v1=1, v2=2, unified_diff=['-old', '+new'], added_lines=1, removed_lines=1
        )
        mock_svc_factory.return_value = mock_svc
        from contracts.api.views import contract_version_diff_api
        req = self._req()
        req.GET = {'v1': '1', 'v2': '2'}
        resp = contract_version_diff_api(req, contract_id=1)
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data['added_lines'], 1)
        self.assertEqual(data['removed_lines'], 1)
        self.assertEqual(data['unified_diff'], ['-old', '+new'])
