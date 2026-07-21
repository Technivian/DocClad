"""Phase 5 — work operating-loop instrumentation tests."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from contracts.models import (
    ApprovalRequest,
    Contract,
    Organization,
    OrganizationMembership,
    WorkInteractionEvent,
)
from contracts.services.approval_workflow import get_approval_workflow_service
from contracts.services.work_instrumentation import (
    build_operating_metrics,
    record_outcome,
    record_rows_surfaced,
    record_work_event,
)

User = get_user_model()


class WorkInstrumentationTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Instr Org', slug='instr-org')
        self.owner = User.objects.create_user('instr_owner', password='x')
        self.reviewer = User.objects.create_user('instr_reviewer', password='x')
        for user, role in (
            (self.owner, OrganizationMembership.Role.OWNER),
            (self.reviewer, OrganizationMembership.Role.MEMBER),
        ):
            OrganizationMembership.objects.create(
                organization=self.org, user=user, role=role, is_active=True,
            )
        self.contract = Contract.objects.create(
            organization=self.org,
            title='Instrument Contract',
            counterparty='Acme',
            content='Body',
            status=Contract.Status.IN_PROGRESS,
            contract_type='MSA',
            created_by=self.owner,
        )
        self.approval = ApprovalRequest.objects.create(
            organization=self.org,
            contract=self.contract,
            approval_step='LEGAL',
            status=ApprovalRequest.Status.PENDING,
            assigned_to=self.reviewer,
            due_date=timezone.now() + timedelta(days=2),
        )

    def test_record_surfaced_dedupes_same_day(self):
        rows = [{
            'id': f'approval:{self.approval.pk}',
            'work_kind': 'approval',
            'contract': self.contract,
            'contract_type': 'MSA',
            'is_restricted': False,
            'is_blocked': False,
            'due_context': {'due_overdue': False},
        }]
        record_rows_surfaced(self.org, self.reviewer, rows, surface='my_work')
        record_rows_surfaced(self.org, self.reviewer, rows, surface='my_work')
        self.assertEqual(
            WorkInteractionEvent.objects.filter(
                organization=self.org, event='surfaced', work_item_id=f'approval:{self.approval.pk}',
            ).count(),
            1,
        )

    def test_my_work_view_records_surfaced(self):
        self.client.force_login(self.reviewer)
        response = self.client.get(reverse('contracts:my_work'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            WorkInteractionEvent.objects.filter(
                organization=self.org,
                event='surfaced',
                work_item_id=f'approval:{self.approval.pk}',
                surface='my_work',
            ).exists()
        )

    def test_opened_beacon_api(self):
        self.client.force_login(self.reviewer)
        response = self.client.post(
            reverse('contracts:work_interaction_api'),
            data='{"event":"opened","work_item_id":"approval:%d","surface":"my_work","work_kind":"approval"}'
            % self.approval.pk,
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            WorkInteractionEvent.objects.filter(
                event='opened', work_item_id=f'approval:{self.approval.pk}', surface='my_work',
            ).exists()
        )

    def test_approval_outcome_records_completed_with_surface(self):
        self.client.force_login(self.reviewer)
        response = self.client.post(
            reverse('contracts:approval_approve_api', kwargs={'approval_id': self.approval.pk}),
            data='{"comments":"ok","surface":"my_work"}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            WorkInteractionEvent.objects.filter(
                event='completed',
                work_item_id=f'approval:{self.approval.pk}',
                surface='my_work',
                work_kind='approval',
            ).exists()
        )

    def test_operating_metrics_api_for_managers(self):
        record_work_event(
            organization=self.org, user=self.reviewer, event='surfaced',
            work_item_id='approval:1', work_kind='approval', surface='my_work',
            is_blocked=True, contract_type='MSA',
        )
        record_outcome(
            organization=self.org, user=self.reviewer, event='completed',
            work_item_id='approval:1', work_kind='approval', surface='my_work',
            contract=self.contract,
        )
        metrics = build_operating_metrics(self.org, days=30)
        self.assertIn('completed_from_my_work_pct', metrics['metrics'])
        self.assertEqual(metrics['metrics']['completed_from_my_work'], 1)
        self.assertEqual(metrics['metrics']['restricted_blocked_frequency']['blocked'], 1)

        self.client.force_login(self.owner)
        response = self.client.get(reverse('contracts:work_operating_metrics_api'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('metrics', response.json())

        self.client.force_login(self.reviewer)
        forbidden = self.client.get(reverse('contracts:work_operating_metrics_api'))
        self.assertEqual(forbidden.status_code, 403)

    def test_sla_breach_records_work_event(self):
        self.approval.due_date = timezone.now() - timedelta(hours=2)
        self.approval.save(update_fields=['due_date'])
        svc = get_approval_workflow_service()
        svc.escalate(self.approval.pk)
        self.assertTrue(
            WorkInteractionEvent.objects.filter(
                event='sla_breached',
                work_item_id=f'approval:{self.approval.pk}',
                surface='job',
            ).exists()
        )
