"""Tests for CVE Gate service (Area 4)."""
import os
from unittest import TestCase
from unittest.mock import MagicMock, patch, mock_open


class TestCVEGateService(TestCase):
    def _make_service(self):
        from contracts.services.cve_gate import CVEGateService
        return CVEGateService()

    def test_scan_requirements_parses_packages(self):
        svc = self._make_service()
        fake_reqs = 'django==4.2.0\nrequests==2.31.0\n# a comment\n-r other.txt\n'

        with patch('builtins.open', mock_open(read_data=fake_reqs)):
            result = svc.scan_requirements('requirements.txt')

        self.assertEqual(len(result.packages), 2)
        names = [p['name'] for p in result.packages]
        self.assertIn('django', names)
        self.assertIn('requests', names)

    def test_scan_requirements_missing_file(self):
        svc = self._make_service()

        with patch('builtins.open', side_effect=FileNotFoundError):
            result = svc.scan_requirements('nonexistent.txt')

        self.assertEqual(result.packages, [])
        self.assertIn('pip-audit', result.note)

    def test_get_gate_status_returns_correct_keys(self):
        svc = self._make_service()

        with patch('contracts.services.cve_gate.CVEScanRecord') as MockRecord:
            MockRecord.objects.order_by.return_value.first.return_value = None
            result = svc.get_gate_status()

        self.assertIn('gate_passed', result)
        self.assertIn('last_scan', result)
        self.assertIn('packages_checked', result)
        self.assertIn('note', result)
        self.assertTrue(result['gate_passed'])

    def test_get_gate_status_with_previous_scan(self):
        svc = self._make_service()
        mock_record = MagicMock()
        mock_record.packages_checked = 42
        mock_record.created_at.isoformat.return_value = '2024-01-01T00:00:00'

        with patch('contracts.services.cve_gate.CVEScanRecord') as MockRecord:
            MockRecord.objects.order_by.return_value.first.return_value = mock_record
            result = svc.get_gate_status()

        self.assertEqual(result['packages_checked'], 42)

    def test_record_scan_result_creates_record(self):
        svc = self._make_service()
        mock_record = MagicMock()
        user = MagicMock()

        with patch('contracts.services.cve_gate.CVEScanRecord') as MockRecord:
            MockRecord.objects.create.return_value = mock_record
            result = svc.record_scan_result(10, 0, performed_by=user)

        MockRecord.objects.create.assert_called_once_with(
            packages_checked=10,
            issues_found=0,
            performed_by=user,
            notes=svc.NOTE,
        )
