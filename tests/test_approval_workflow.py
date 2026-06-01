"""Tests for approval workflow service."""
import unittest
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.utils import timezone

from contracts.models import ApprovalRequest
from contracts.services.approval_workflow import ApprovalWorkflowService, _to_dto


def _make_ar(
    pk=1, contract_id=10, approval_step='LEGAL', status='PENDING',
    assigned_to_id=None, delegated_to_id=None, due_date=None,
    rule=None, comments='', escalated_at=None, decided_at=None,
):
    ar = MagicMock(spec=ApprovalRequest)
    ar.pk = pk
    ar.contract_id = contract_id
    ar.contract = MagicMock()
    ar.contract.title = 'Test Contract'
    ar.approval_step = approval_step
    ar.status = status
    ar.assigned_to_id = assigned_to_id
    ar.assigned_to = MagicMock() if assigned_to_id else None
    if assigned_to_id:
        ar.assigned_to.username = 'alice'
    ar.delegated_to_id = delegated_to_id
    ar.delegated_to = None
    ar.rule_id = rule.pk if rule else None
    ar.rule = rule
    ar.due_date = due_date
    ar.comments = comments
    ar.escalated_at = escalated_at
    ar.decided_at = decided_at
    ar.created_at = timezone.now()
    ar.save = MagicMock()
    return ar


def _make_rule(pk=1, approval_step='LEGAL', sla_hours=48, escalation_after_hours=72):
    r = MagicMock()
    r.pk = pk
    r.approval_step = approval_step
    r.sla_hours = sla_hours
    r.escalation_after_hours = escalation_after_hours
    return r


class TestApprovalWorkflowService(unittest.TestCase):
    def setUp(self):
        self.svc = ApprovalWorkflowService()
        self.org = MagicMock()
        self.org.pk = 1
        self.contract = MagicMock()
        self.contract.pk = 10
        self.contract.title = 'Test Contract'
        self.actor = MagicMock()
        self.actor.pk = 99

    @patch('contracts.services.approval_workflow.transaction')
    @patch('contracts.services.approval_workflow.build_approval_request_plan_for_contract')
    @patch('contracts.services.approval_workflow.ApprovalRequest')
    def test_initiate_creates_requests(self, MockAR, mock_plan, mock_txn):
        mock_txn.atomic.return_value.__enter__ = MagicMock(return_value=None)
        mock_txn.atomic.return_value.__exit__ = MagicMock(return_value=False)
        rule = _make_rule()
        plan = [{
            'organization': self.org,
            'contract': self.contract,
            'rule': rule,
            'approval_step': 'LEGAL',
            'assigned_to': None,
            'due_date': timezone.now() + timedelta(hours=48),
            'status': 'PENDING',
        }]
        mock_plan.return_value = plan
        MockAR.objects.filter.return_value.exists.return_value = False
        ar = _make_ar(rule=rule)
        MockAR.objects.create.return_value = ar
        dtos = self.svc.initiate_approval_workflow(self.contract)
        self.assertEqual(len(dtos), 1)
        self.assertEqual(dtos[0].approval_step, 'LEGAL')

    @patch('contracts.services.approval_workflow.build_approval_request_plan_for_contract')
    def test_initiate_returns_empty_when_no_rules_match(self, mock_plan):
        mock_plan.return_value = []
        dtos = self.svc.initiate_approval_workflow(self.contract)
        self.assertEqual(dtos, [])

    @patch('contracts.services.approval_workflow.transaction')
    @patch('contracts.services.approval_workflow.build_approval_request_plan_for_contract')
    @patch('contracts.services.approval_workflow.ApprovalRequest')
    def test_initiate_skips_duplicate_pending(self, MockAR, mock_plan, mock_txn):
        mock_txn.atomic.return_value.__enter__ = MagicMock(return_value=None)
        mock_txn.atomic.return_value.__exit__ = MagicMock(return_value=False)
        rule = _make_rule()
        plan = [{'organization': self.org, 'contract': self.contract, 'rule': rule,
                 'approval_step': 'LEGAL', 'assigned_to': None,
                 'due_date': timezone.now(), 'status': 'PENDING'}]
        mock_plan.return_value = plan
        MockAR.objects.filter.return_value.exists.return_value = True  # already exists
        dtos = self.svc.initiate_approval_workflow(self.contract)
        self.assertEqual(dtos, [])

    @patch('contracts.services.approval_workflow.ApprovalRequest')
    def test_approve_transitions_status(self, MockAR):
        ar = _make_ar(status='PENDING')
        MockAR.objects.select_related.return_value.get.return_value = ar
        dto = self.svc.approve(1, self.actor, comments='LGTM')
        self.assertEqual(ar.status, ApprovalRequest.Status.APPROVED)
        self.assertEqual(ar.comments, 'LGTM')
        ar.save.assert_called_once()

    @patch('contracts.services.approval_workflow.ApprovalRequest')
    def test_approve_invalid_from_rejected(self, MockAR):
        ar = _make_ar(status='REJECTED')
        MockAR.objects.select_related.return_value.get.return_value = ar
        with self.assertRaises(ValueError):
            self.svc.approve(1, self.actor)

    @patch('contracts.services.approval_workflow.ApprovalRequest')
    def test_reject_transitions_status(self, MockAR):
        ar = _make_ar(status='PENDING')
        MockAR.objects.select_related.return_value.get.return_value = ar
        dto = self.svc.reject(1, self.actor, comments='Needs revision')
        self.assertEqual(ar.status, ApprovalRequest.Status.REJECTED)
        ar.save.assert_called_once()

    @patch('contracts.services.approval_workflow.ApprovalRequest')
    def test_delegate_reassigns_user(self, MockAR):
        ar = _make_ar(status='PENDING', assigned_to_id=5)
        MockAR.objects.select_related.return_value.get.return_value = ar
        new_user = MagicMock()
        new_user.pk = 7
        dto = self.svc.delegate(1, new_user, self.actor)
        self.assertEqual(ar.delegated_to, new_user)
        self.assertEqual(ar.assigned_to, new_user)
        ar.save.assert_called_once()

    @patch('contracts.services.approval_workflow.ApprovalRequest')
    def test_delegate_fails_if_not_pending(self, MockAR):
        ar = _make_ar(status='APPROVED')
        MockAR.objects.select_related.return_value.get.return_value = ar
        with self.assertRaises(ValueError):
            self.svc.delegate(1, MagicMock(), self.actor)

    @patch('contracts.services.approval_workflow.ApprovalRequest')
    def test_escalate_transitions_to_escalated(self, MockAR):
        ar = _make_ar(status='PENDING')
        MockAR.objects.select_related.return_value.get.return_value = ar
        dto = self.svc.escalate(1)
        self.assertEqual(ar.status, ApprovalRequest.Status.ESCALATED)
        ar.save.assert_called_once()

    @patch('contracts.services.approval_workflow.ApprovalRequest')
    def test_get_overdue_approvals(self, MockAR):
        past_due = timezone.now() - timedelta(hours=1)
        ar = _make_ar(status='PENDING', due_date=past_due)
        MockAR.objects.filter.return_value.select_related.return_value.order_by.return_value = [ar]
        overdue = self.svc.get_overdue_approvals(self.org)
        self.assertEqual(len(overdue), 1)
        self.assertTrue(overdue[0].is_overdue)

    @patch('contracts.services.approval_workflow.ApprovalRequest')
    def test_get_overdue_empty(self, MockAR):
        MockAR.objects.filter.return_value.select_related.return_value.order_by.return_value = []
        overdue = self.svc.get_overdue_approvals(self.org)
        self.assertEqual(overdue, [])

    @patch('contracts.services.approval_workflow.ApprovalRequest')
    def test_list_approvals_no_filter(self, MockAR):
        ar = _make_ar(status='PENDING')
        MockAR.objects.filter.return_value.select_related.return_value.order_by.return_value = [ar]
        results = self.svc.list_approvals(self.org)
        self.assertEqual(len(results), 1)

    @patch('contracts.services.approval_workflow.ApprovalRequest')
    def test_list_approvals_with_status_filter(self, MockAR):
        ar = _make_ar(status='APPROVED')
        qs = MagicMock()
        MockAR.objects.filter.return_value.select_related.return_value.order_by.return_value = qs
        qs.filter.return_value = [ar]
        results = self.svc.list_approvals(self.org, status='APPROVED')
        self.assertEqual(len(results), 1)

    def test_dto_overdue_flag_set_for_past_due(self):
        ar = _make_ar(status='PENDING', due_date=timezone.now() - timedelta(hours=2))
        ar.can_transition_to = lambda s: True
        dto = _to_dto(ar)
        self.assertTrue(dto.is_overdue)

    def test_dto_not_overdue_for_future_due(self):
        ar = _make_ar(status='PENDING', due_date=timezone.now() + timedelta(hours=24))
        ar.can_transition_to = lambda s: True
        dto = _to_dto(ar)
        self.assertFalse(dto.is_overdue)


if __name__ == '__main__':
    unittest.main()
