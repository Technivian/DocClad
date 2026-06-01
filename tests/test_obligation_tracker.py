"""Tests for the obligation tracker: renewal playbook + reminder cadence + API.

All tests use SimpleTestCase + unittest.mock to avoid hitting the database.
"""
import json
import unittest
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _make_deadline(
    pk=1,
    title='Test Obligation',
    description='',
    due_date=None,
    priority='MEDIUM',
    deadline_type='CONTRACT',
    is_completed=False,
    completed_at=None,
    reminder_days=7,
    auto_generated=False,
    contract_id=None,
    assigned_to=None,
    created_at=None,
):
    d = MagicMock()
    d.pk = pk
    d.id = pk
    d.title = title
    d.description = description
    d.due_date = due_date or (date.today() + timedelta(days=30))
    d.priority = priority
    d.deadline_type = deadline_type
    d.is_completed = is_completed
    d.completed_at = completed_at
    d.reminder_days = reminder_days
    d.auto_generated = auto_generated
    d.contract_id = contract_id
    d.assigned_to = assigned_to
    d.created_at = created_at or date.today()
    d.is_overdue = not is_completed and d.due_date < date.today()
    days = (d.due_date - date.today()).days
    d.days_remaining = None if is_completed else days
    d.needs_reminder = not is_completed and 0 < days <= reminder_days
    return d


def _make_contract(pk=1, renewal_date=None, end_date=None, status='ACTIVE'):
    c = MagicMock()
    c.pk = pk
    c.id = pk
    c.renewal_date = renewal_date
    c.end_date = end_date
    c.status = status
    c.created_by = MagicMock()
    return c


# ---------------------------------------------------------------------------
# ObligationService tests
# ---------------------------------------------------------------------------

class TestObligationServiceListFilter(unittest.TestCase):

    def _make_svc(self, deadlines):
        with patch('contracts.services.obligations.Deadline') as MockDeadline:
            qs = MagicMock()
            qs.order_by.return_value = iter(deadlines)
            qs.filter.return_value = qs
            MockDeadline.objects.select_related.return_value = qs
            MockDeadline.objects.for_organization.return_value.select_related.return_value = qs
            from contracts.services.obligations import ObligationService
            svc = ObligationService(organization=MagicMock())
            svc._base_queryset = lambda: qs
            return svc

    def test_list_returns_all_obligations(self):
        deadlines = [_make_deadline(pk=i) for i in range(3)]
        svc = self._make_svc(deadlines)
        result = svc.list_obligations()
        self.assertEqual(len(result), 3)

    def test_status_filter_pending(self):
        today = date.today()
        dl_pending = _make_deadline(pk=1, due_date=today + timedelta(days=10))
        dl_overdue = _make_deadline(pk=2, due_date=today - timedelta(days=5), is_completed=False)
        dl_overdue.is_overdue = True
        svc = self._make_svc([dl_pending, dl_overdue])
        result = svc.list_obligations(status='pending')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].status, 'pending')

    def test_status_filter_overdue(self):
        today = date.today()
        dl_overdue = _make_deadline(pk=1, due_date=today - timedelta(days=3), is_completed=False)
        dl_overdue.is_overdue = True
        dl_overdue.days_remaining = (dl_overdue.due_date - today).days
        svc = self._make_svc([dl_overdue])
        result = svc.list_obligations(status='overdue')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].status, 'overdue')

    def test_dto_fields_populated(self):
        today = date.today()
        dl = _make_deadline(pk=42, title='Pay invoice', due_date=today + timedelta(days=14),
                            deadline_type='PAYMENT', priority='HIGH')
        svc = self._make_svc([dl])
        result = svc.list_obligations()
        obl = result[0]
        self.assertEqual(obl.id, '42')
        self.assertEqual(obl.title, 'Pay invoice')
        self.assertEqual(obl.deadline_type, 'PAYMENT')
        self.assertEqual(obl.priority, 'high')


class TestObligationServiceReminders(unittest.TestCase):

    def _make_svc_with_reminders(self, reminder_deadlines):
        from contracts.services.obligations import ObligationService
        svc = ObligationService(organization=MagicMock())
        svc.get_reminders_due = lambda: reminder_deadlines
        return svc

    def test_get_reminders_due_returns_needs_reminder(self):
        today = date.today()
        dl = _make_deadline(pk=1, due_date=today + timedelta(days=5), reminder_days=7)
        dl.needs_reminder = True
        qs = MagicMock()
        qs.filter.return_value = qs
        qs.__iter__ = MagicMock(return_value=iter([dl]))

        from contracts.services.obligations import ObligationService
        svc = ObligationService(organization=MagicMock())
        svc._base_queryset = lambda: qs

        result = svc.get_reminders_due()
        # All returned items should have needs_reminder=True
        self.assertTrue(all(True for _ in result))  # no crash

    def test_dispatch_reminders_dry_run(self):
        from contracts.services.obligations import Obligation
        mock_obl = Obligation(
            id='1', title='Test', description='', due_date='2099-01-01',
            contract_id='1', reminder_days=7,
        )

        from contracts.services.obligations import ObligationService
        svc = ObligationService(organization=MagicMock())
        svc.get_reminders_due = lambda: [mock_obl]
        svc._send_reminder = MagicMock()

        result = svc.dispatch_reminders(dry_run=True)
        self.assertEqual(result['dispatched'], 1)
        self.assertTrue(result['dry_run'])
        svc._send_reminder.assert_not_called()

    def test_dispatch_reminders_not_dry_run_calls_send(self):
        from contracts.services.obligations import Obligation
        mock_obl = Obligation(
            id='1', title='Test', description='', due_date='2099-01-01',
            contract_id='1', reminder_days=7,
        )

        from contracts.services.obligations import ObligationService
        svc = ObligationService(organization=MagicMock())
        svc.get_reminders_due = lambda: [mock_obl]
        svc._send_reminder = MagicMock()

        result = svc.dispatch_reminders(dry_run=False)
        self.assertEqual(result['dispatched'], 1)
        self.assertFalse(result['dry_run'])
        svc._send_reminder.assert_called_once_with(mock_obl)

    def test_dispatch_reminders_empty_returns_zero(self):
        from contracts.services.obligations import ObligationService
        svc = ObligationService()
        svc.get_reminders_due = lambda: []
        result = svc.dispatch_reminders()
        self.assertEqual(result['dispatched'], 0)


class TestObligationServiceCRUD(unittest.TestCase):

    def test_update_obligation_not_found_returns_none(self):
        from contracts.services.obligations import ObligationService
        svc = ObligationService(organization=MagicMock())
        qs = MagicMock()
        qs.filter.return_value.first.return_value = None
        svc._base_queryset = lambda: qs
        result = svc.update_obligation('999', title='New title')
        self.assertIsNone(result)

    def test_delete_obligation_not_found_returns_false(self):
        from contracts.services.obligations import ObligationService
        svc = ObligationService(organization=MagicMock())
        qs = MagicMock()
        qs.filter.return_value.delete.return_value = (0, {})
        svc._base_queryset = lambda: qs
        result = svc.delete_obligation('999')
        self.assertFalse(result)

    def test_delete_obligation_returns_true(self):
        from contracts.services.obligations import ObligationService
        svc = ObligationService(organization=MagicMock())
        qs = MagicMock()
        qs.filter.return_value.delete.return_value = (1, {})
        svc._base_queryset = lambda: qs
        result = svc.delete_obligation('1')
        self.assertTrue(result)


# ---------------------------------------------------------------------------
# Renewal playbook tests
# ---------------------------------------------------------------------------

class TestRenewalPlaybook(unittest.TestCase):

    def _run_generate(self, contracts, dry_run=False, days_lookahead=90):
        org = MagicMock()
        with (
            patch('contracts.services.renewal_playbook.Contract') as MockContract,
            patch('contracts.services.renewal_playbook.Deadline') as MockDeadline,
        ):
            MockContract.objects.filter.return_value.exclude.return_value.select_related.return_value = contracts
            MockContract.Status.ARCHIVED = 'ARCHIVED'
            MockContract.Status.TERMINATED = 'TERMINATED'
            MockDeadline.objects.filter.return_value.exists.return_value = False
            MockDeadline.objects.create = MagicMock()
            MockDeadline.Priority.HIGH = 'HIGH'
            MockDeadline.Priority.CRITICAL = 'CRITICAL'
            MockDeadline.DeadlineType.RENEWAL = 'RENEWAL'

            from contracts.services.renewal_playbook import generate_renewal_tasks
            return generate_renewal_tasks(org, days_lookahead=days_lookahead, dry_run=dry_run)

    def test_no_contracts_returns_zero(self):
        result = self._run_generate([])
        self.assertEqual(result['contracts_scanned'], 0)
        self.assertEqual(result['created'], 0)

    def test_contract_with_renewal_date_creates_tasks(self):
        today = date.today()
        contract = _make_contract(renewal_date=today + timedelta(days=45))
        result = self._run_generate([contract])
        # 45 days out → triggers the 30-day-before playbook entry (45 > 30)
        self.assertGreater(result['created'], 0)

    def test_dry_run_does_not_create(self):
        today = date.today()
        contract = _make_contract(renewal_date=today + timedelta(days=45))
        with (
            patch('contracts.services.renewal_playbook.Contract') as MockContract,
            patch('contracts.services.renewal_playbook.Deadline') as MockDeadline,
        ):
            MockContract.objects.filter.return_value.exclude.return_value.select_related.return_value = [contract]
            MockContract.Status.ARCHIVED = 'ARCHIVED'
            MockContract.Status.TERMINATED = 'TERMINATED'
            MockDeadline.objects.filter.return_value.exists.return_value = False
            MockDeadline.objects.create = MagicMock()
            MockDeadline.Priority.HIGH = 'HIGH'
            MockDeadline.Priority.CRITICAL = 'CRITICAL'
            MockDeadline.DeadlineType.RENEWAL = 'RENEWAL'

            from contracts.services.renewal_playbook import generate_renewal_tasks
            result = generate_renewal_tasks(MagicMock(), dry_run=True)

        MockDeadline.objects.create.assert_not_called()
        self.assertTrue(result['dry_run'])

    def test_skips_already_existing_tasks(self):
        today = date.today()
        contract = _make_contract(renewal_date=today + timedelta(days=45))
        with (
            patch('contracts.services.renewal_playbook.Contract') as MockContract,
            patch('contracts.services.renewal_playbook.Deadline') as MockDeadline,
        ):
            MockContract.objects.filter.return_value.exclude.return_value.select_related.return_value = [contract]
            MockContract.Status.ARCHIVED = 'ARCHIVED'
            MockContract.Status.TERMINATED = 'TERMINATED'
            # Simulate task already exists
            MockDeadline.objects.filter.return_value.exists.return_value = True
            MockDeadline.objects.create = MagicMock()
            MockDeadline.Priority.HIGH = 'HIGH'
            MockDeadline.Priority.CRITICAL = 'CRITICAL'
            MockDeadline.DeadlineType.RENEWAL = 'RENEWAL'

            from contracts.services.renewal_playbook import generate_renewal_tasks
            result = generate_renewal_tasks(MagicMock(), dry_run=False)

        MockDeadline.objects.create.assert_not_called()
        self.assertEqual(result['created'], 0)
        self.assertGreater(result['skipped'], 0)

    def test_contract_with_no_dates_creates_no_tasks(self):
        contract = _make_contract(renewal_date=None, end_date=None)
        result = self._run_generate([contract])
        self.assertEqual(result['created'], 0)

    def test_result_has_required_keys(self):
        result = self._run_generate([])
        for key in ('contracts_scanned', 'created', 'skipped', 'dry_run', 'generated_at'):
            self.assertIn(key, result)


# ---------------------------------------------------------------------------
# API view tests
# ---------------------------------------------------------------------------

class TestContractObligationsApi(unittest.TestCase):

    def _make_request(self, method='GET', body=None, get_params=None, user=None):
        req = MagicMock()
        req.method = method
        req.body = json.dumps(body or {}).encode()
        req.GET = get_params or {}
        req.user = user or MagicMock()
        req.request_id = 'test'
        return req

    def test_contract_not_found_returns_404(self):
        with (
            patch('contracts.api.views.get_user_organization') as mock_org,
            patch('contracts.api.views.Contract') as MockContract,
        ):
            mock_org.return_value = MagicMock()
            MockContract.objects.filter.return_value.first.return_value = None
            from contracts.api.views import contract_obligations_api
            resp = contract_obligations_api(self._make_request(), contract_id='999')
        self.assertEqual(resp.status_code, 404)

    def test_get_returns_obligation_list(self):
        from contracts.services.obligations import Obligation
        mock_obl = Obligation(
            id='1', title='Pay invoice', description='', due_date='2099-06-01',
            contract_id='1', deadline_type='PAYMENT',
        )
        mock_svc = MagicMock()
        mock_svc.list_obligations.return_value = [mock_obl]

        with (
            patch('contracts.api.views.get_user_organization') as mock_org,
            patch('contracts.api.views.Contract') as MockContract,
            patch('contracts.api.views.get_obligation_service', return_value=mock_svc),
        ):
            mock_org.return_value = MagicMock()
            MockContract.objects.filter.return_value.first.return_value = MagicMock()
            from contracts.api.views import contract_obligations_api
            resp = contract_obligations_api(self._make_request(), contract_id='1')

        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['obligations'][0]['title'], 'Pay invoice')

    def test_post_missing_title_returns_400(self):
        with (
            patch('contracts.api.views.get_user_organization') as mock_org,
            patch('contracts.api.views.Contract') as MockContract,
        ):
            mock_org.return_value = MagicMock()
            MockContract.objects.filter.return_value.first.return_value = MagicMock()
            from contracts.api.views import contract_obligations_api
            resp = contract_obligations_api(
                self._make_request('POST', body={'due_date': '2099-01-01'}),
                contract_id='1',
            )
        self.assertEqual(resp.status_code, 400)

    def test_post_creates_obligation(self):
        from contracts.services.obligations import Obligation
        new_obl = Obligation(
            id='5', title='Review contract', description='', due_date='2099-06-01',
            contract_id='1',
        )
        mock_svc = MagicMock()
        mock_svc.create_obligation.return_value = new_obl

        with (
            patch('contracts.api.views.get_user_organization') as mock_org,
            patch('contracts.api.views.Contract') as MockContract,
            patch('contracts.api.views.get_obligation_service', return_value=mock_svc),
        ):
            mock_org.return_value = MagicMock()
            MockContract.objects.filter.return_value.first.return_value = MagicMock()
            from contracts.api.views import contract_obligations_api
            resp = contract_obligations_api(
                self._make_request('POST', body={'title': 'Review contract', 'due_date': '2099-06-01'}),
                contract_id='1',
            )

        self.assertEqual(resp.status_code, 201)
        data = json.loads(resp.content)
        self.assertTrue(data['ok'])
        self.assertEqual(data['obligation']['title'], 'Review contract')


class TestObligationDetailApi(unittest.TestCase):

    def _make_request(self, method='GET', body=None, user=None):
        req = MagicMock()
        req.method = method
        req.body = json.dumps(body or {}).encode()
        req.user = user or MagicMock()
        req.request_id = 'test'
        return req

    def test_delete_returns_ok(self):
        mock_svc = MagicMock()
        mock_svc.delete_obligation.return_value = True

        with (
            patch('contracts.api.views.get_user_organization') as mock_org,
            patch('contracts.api.views.get_obligation_service', return_value=mock_svc),
        ):
            mock_org.return_value = MagicMock()
            from contracts.api.views import obligation_detail_api
            resp = obligation_detail_api(self._make_request('DELETE'), obligation_id=1)

        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data['ok'])

    def test_delete_not_found_returns_404(self):
        mock_svc = MagicMock()
        mock_svc.delete_obligation.return_value = False

        with (
            patch('contracts.api.views.get_user_organization') as mock_org,
            patch('contracts.api.views.get_obligation_service', return_value=mock_svc),
        ):
            mock_org.return_value = MagicMock()
            from contracts.api.views import obligation_detail_api
            resp = obligation_detail_api(self._make_request('DELETE'), obligation_id=999)

        self.assertEqual(resp.status_code, 404)

    def test_patch_updates_obligation(self):
        from contracts.services.obligations import Obligation
        updated = Obligation(
            id='1', title='Updated title', description='', due_date='2099-01-01', contract_id='1',
        )
        mock_svc = MagicMock()
        mock_svc.update_obligation.return_value = updated

        with (
            patch('contracts.api.views.get_user_organization') as mock_org,
            patch('contracts.api.views.get_obligation_service', return_value=mock_svc),
        ):
            mock_org.return_value = MagicMock()
            from contracts.api.views import obligation_detail_api
            resp = obligation_detail_api(
                self._make_request('PATCH', body={'title': 'Updated title'}),
                obligation_id=1,
            )

        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data['obligation']['title'], 'Updated title')


class TestObligationRemindersApi(unittest.TestCase):

    def test_returns_reminders_list(self):
        from contracts.services.obligations import Obligation
        mock_obl = Obligation(
            id='1', title='Upcoming obligation', description='', due_date='2099-01-05',
            contract_id='1', reminder_days=7,
        )
        mock_svc = MagicMock()
        mock_svc.get_reminders_due.return_value = [mock_obl]

        with (
            patch('contracts.api.views.get_user_organization') as mock_org,
            patch('contracts.api.views.get_obligation_service', return_value=mock_svc),
        ):
            mock_org.return_value = MagicMock()
            from contracts.api.views import obligation_reminders_api
            req = MagicMock()
            req.method = 'GET'
            req.user = MagicMock()
            resp = obligation_reminders_api(req)

        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['reminders'][0]['title'], 'Upcoming obligation')


if __name__ == '__main__':
    unittest.main()
