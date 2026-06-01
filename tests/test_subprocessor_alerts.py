"""Tests for Subprocessor Alerts service (Area 2)."""
from datetime import date, timedelta
from unittest import TestCase
from unittest.mock import MagicMock, patch


class TestSubprocessorAlertService(TestCase):
    def _make_service(self):
        from contracts.services.subprocessor_alerts import SubprocessorAlertService
        return SubprocessorAlertService()

    def _make_subprocessor(self, **kwargs):
        sp = MagicMock()
        sp.id = kwargs.get('id', 1)
        sp.name = kwargs.get('name', 'Test SP')
        sp.country = kwargs.get('country', 'US')
        sp.dpa_in_place = kwargs.get('dpa_in_place', True)
        sp.scc_in_place = kwargs.get('scc_in_place', False)
        sp.dpf_certified = kwargs.get('dpf_certified', False)
        sp.is_eu_based = kwargs.get('is_eu_based', False)
        sp.risk_level = kwargs.get('risk_level', 'LOW')
        sp.contract_end_date = kwargs.get('contract_end_date', None)
        sp.last_audit_date = kwargs.get('last_audit_date', None)
        sp.is_active = True
        return sp

    def test_expired_dpa_raises_alert(self):
        svc = self._make_service()
        org = MagicMock()
        yesterday = date.today() - timedelta(days=1)
        sp = self._make_subprocessor(dpa_in_place=True, contract_end_date=yesterday)

        with patch('contracts.services.subprocessor_alerts.Subprocessor') as MockSP:
            MockSP.objects.filter.return_value = [sp]
            alerts = svc.get_alerts(org)

        alert_types = [a.alert_type for a in alerts]
        self.assertIn('EXPIRED_DPA', alert_types)

    def test_missing_dpa_raises_alert(self):
        svc = self._make_service()
        org = MagicMock()
        sp = self._make_subprocessor(dpa_in_place=False, is_eu_based=True)

        with patch('contracts.services.subprocessor_alerts.Subprocessor') as MockSP:
            MockSP.objects.filter.return_value = [sp]
            alerts = svc.get_alerts(org)

        alert_types = [a.alert_type for a in alerts]
        self.assertIn('MISSING_DPA', alert_types)

    def test_missing_dpa_high_severity_for_non_eu(self):
        svc = self._make_service()
        org = MagicMock()
        sp = self._make_subprocessor(dpa_in_place=False, is_eu_based=False, risk_level='LOW')

        with patch('contracts.services.subprocessor_alerts.Subprocessor') as MockSP:
            MockSP.objects.filter.return_value = [sp]
            alerts = svc.get_alerts(org)

        missing_dpa = [a for a in alerts if a.alert_type == 'MISSING_DPA']
        self.assertTrue(any(a.severity == 'HIGH' for a in missing_dpa))

    def test_overdue_audit_raises_alert(self):
        svc = self._make_service()
        org = MagicMock()
        old_audit = date.today() - timedelta(days=400)
        sp = self._make_subprocessor(dpa_in_place=True, last_audit_date=old_audit)

        with patch('contracts.services.subprocessor_alerts.Subprocessor') as MockSP:
            MockSP.objects.filter.return_value = [sp]
            alerts = svc.get_alerts(org)

        alert_types = [a.alert_type for a in alerts]
        self.assertIn('OVERDUE_AUDIT', alert_types)

    def test_missing_transfer_mechanism_non_eu(self):
        svc = self._make_service()
        org = MagicMock()
        sp = self._make_subprocessor(
            dpa_in_place=True, is_eu_based=False, scc_in_place=False, dpf_certified=False
        )

        with patch('contracts.services.subprocessor_alerts.Subprocessor') as MockSP:
            MockSP.objects.filter.return_value = [sp]
            alerts = svc.get_alerts(org)

        alert_types = [a.alert_type for a in alerts]
        self.assertIn('MISSING_TRANSFER_MECHANISM', alert_types)

    def test_no_alerts_for_compliant_eu_subprocessor(self):
        svc = self._make_service()
        org = MagicMock()
        future_date = date.today() + timedelta(days=365)
        recent_audit = date.today() - timedelta(days=100)
        sp = self._make_subprocessor(
            dpa_in_place=True,
            is_eu_based=True,
            scc_in_place=True,
            contract_end_date=future_date,
            last_audit_date=recent_audit,
        )

        with patch('contracts.services.subprocessor_alerts.Subprocessor') as MockSP:
            MockSP.objects.filter.return_value = [sp]
            alerts = svc.get_alerts(org)

        alert_types = [a.alert_type for a in alerts]
        self.assertNotIn('EXPIRED_DPA', alert_types)
        self.assertNotIn('MISSING_DPA', alert_types)
        self.assertNotIn('OVERDUE_AUDIT', alert_types)

    def test_transfer_risk_expired_review(self):
        svc = self._make_service()
        org = MagicMock()
        yesterday = date.today() - timedelta(days=1)
        tr = MagicMock()
        tr.id = 1
        tr.title = 'US Transfer'
        tr.review_date = yesterday
        tr.tia_completed = True
        tr.is_active = True

        with patch('contracts.services.subprocessor_alerts.TransferRecord') as MockTR:
            MockTR.objects.filter.return_value = [tr]
            flags = svc.get_transfer_risk_flags(org)

        flag_types = [f.flag_type for f in flags]
        self.assertIn('EXPIRED_REVIEW', flag_types)

    def test_transfer_risk_missing_tia(self):
        svc = self._make_service()
        org = MagicMock()
        future = date.today() + timedelta(days=30)
        tr = MagicMock()
        tr.id = 2
        tr.title = 'EU Transfer'
        tr.review_date = future
        tr.tia_completed = False
        tr.is_active = True

        with patch('contracts.services.subprocessor_alerts.TransferRecord') as MockTR:
            MockTR.objects.filter.return_value = [tr]
            flags = svc.get_transfer_risk_flags(org)

        flag_types = [f.flag_type for f in flags]
        self.assertIn('MISSING_TIA', flag_types)
