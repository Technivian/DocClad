"""Tests for Restore Drill service (Area 4)."""
from datetime import date, timedelta
from unittest import TestCase
from unittest.mock import MagicMock, patch


class TestRestoreDrillService(TestCase):
    def _make_service(self):
        from contracts.services.restore_drill import RestoreDrillService
        return RestoreDrillService()

    def test_schedule_drill_creates_instance(self):
        svc = self._make_service()
        org = MagicMock()
        user = MagicMock()
        drill_date = date.today() + timedelta(days=7)
        mock_drill = MagicMock()
        mock_drill.id = 1
        mock_drill.drill_date = drill_date

        with patch('contracts.services.restore_drill.RestoreDrill') as MockDrill:
            MockDrill.objects.create.return_value = mock_drill
            drill = svc.schedule_drill(org, drill_date, 4.0, 1.0, user)

        MockDrill.objects.create.assert_called_once_with(
            organization=org,
            drill_date=drill_date,
            rto_target_hours=4.0,
            rpo_target_hours=1.0,
            performed_by=user,
        )
        self.assertEqual(drill.id, 1)

    def test_record_result_updates_drill(self):
        svc = self._make_service()
        mock_drill = MagicMock()
        mock_drill.id = 1

        with patch('contracts.services.restore_drill.RestoreDrill') as MockDrill:
            MockDrill.objects.get.return_value = mock_drill
            MockDrill.DoesNotExist = Exception
            updated = svc.record_result(
                drill_id=1,
                actual_rto_minutes=240,
                actual_rpo_minutes=60,
                passed=True,
                notes='Went well',
            )

        self.assertEqual(mock_drill.actual_rto_minutes, 240)
        self.assertEqual(mock_drill.actual_rpo_minutes, 60)
        self.assertTrue(mock_drill.passed)
        mock_drill.save.assert_called_once()

    def test_record_result_raises_on_not_found(self):
        svc = self._make_service()

        with patch('contracts.services.restore_drill.RestoreDrill') as MockDrill:
            from contracts.services.restore_drill import _RestoreDrillDoesNotExist
            MockDrill.objects.get.side_effect = _RestoreDrillDoesNotExist()
            with self.assertRaises(ValueError):
                svc.record_result(999, 60, 30, True)

    def test_list_drills_returns_list(self):
        svc = self._make_service()
        org = MagicMock()
        mock_drill = MagicMock()
        mock_drill.id = 1
        mock_drill.drill_date = date.today()
        mock_drill.rto_target_hours = 4.0
        mock_drill.rpo_target_hours = 1.0
        mock_drill.actual_rto_minutes = None
        mock_drill.actual_rpo_minutes = None
        mock_drill.passed = None
        mock_drill.notes = ''
        mock_drill.completed_at = None
        mock_drill.created_at.isoformat.return_value = '2024-01-01T00:00:00'

        with patch('contracts.services.restore_drill.RestoreDrill') as MockDrill:
            mock_qs = MagicMock()
            mock_qs.filter.return_value = mock_qs
            mock_qs.__getitem__ = MagicMock(return_value=[mock_drill])
            MockDrill.objects.filter.return_value = mock_qs
            result = svc.list_drills(org)

        self.assertIsInstance(result, list)

    def test_get_drill_summary_structure(self):
        svc = self._make_service()
        org = MagicMock()

        with patch('contracts.services.restore_drill.RestoreDrill') as MockDrill:
            mock_qs = MagicMock()
            mock_qs.filter.return_value = mock_qs
            mock_qs.count.return_value = 5
            mock_qs.exists.return_value = False
            MockDrill.objects.filter.return_value = mock_qs
            result = svc.get_drill_summary(org)

        self.assertIn('total_drills', result)
        self.assertIn('passed', result)
        self.assertIn('failed', result)
        self.assertIn('last_drill_at', result)
        self.assertIn('avg_rto_minutes', result)
        self.assertIn('avg_rpo_minutes', result)

    def test_drill_to_dict_format(self):
        svc = self._make_service()
        mock_drill = MagicMock()
        mock_drill.id = 1
        mock_drill.drill_date = date.today()
        mock_drill.rto_target_hours = 4.0
        mock_drill.rpo_target_hours = 1.0
        mock_drill.actual_rto_minutes = 200
        mock_drill.actual_rpo_minutes = 50
        mock_drill.passed = True
        mock_drill.notes = 'OK'
        mock_drill.completed_at = None
        mock_drill.created_at.isoformat.return_value = '2024-01-01T00:00:00'

        d = svc._drill_to_dict(mock_drill)
        self.assertIn('id', d)
        self.assertIn('drill_date', d)
        self.assertIn('passed', d)
        self.assertTrue(d['passed'])

    def test_schedule_drill_with_defaults(self):
        svc = self._make_service()
        org = MagicMock()
        drill_date = date.today()
        mock_drill = MagicMock()
        mock_drill.id = 99

        with patch('contracts.services.restore_drill.RestoreDrill') as MockDrill:
            MockDrill.objects.create.return_value = mock_drill
            svc.schedule_drill(org, drill_date, 4.0, 1.0)

        call_kwargs = MockDrill.objects.create.call_args[1]
        self.assertEqual(call_kwargs['rto_target_hours'], 4.0)
        self.assertEqual(call_kwargs['rpo_target_hours'], 1.0)

    def test_record_result_sets_completed_at(self):
        svc = self._make_service()
        mock_drill = MagicMock()

        with patch('contracts.services.restore_drill.RestoreDrill') as MockDrill:
            with patch('contracts.services.restore_drill.timezone') as mock_tz:
                MockDrill.objects.get.return_value = mock_drill
                MockDrill.DoesNotExist = Exception
                now = MagicMock()
                mock_tz.now.return_value = now
                svc.record_result(1, 120, 30, True)

        self.assertEqual(mock_drill.completed_at, now)
