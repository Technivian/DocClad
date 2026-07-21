"""Phase 6 — amplifiers: work health, saved views, rule-based priority."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from contracts.models import (
    ApprovalRequest,
    Contract,
    MyWorkSavedView,
    Organization,
    OrganizationMembership,
    WorkInteractionEvent,
)
from contracts.services.assignments import _base_row, _sort_key
from contracts.services.work_instrumentation import measured_priority_boost

User = get_user_model()


class Phase6AmplifierTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Amp Org', slug='amp-org')
        self.owner = User.objects.create_user('amp_owner', password='x')
        self.member = User.objects.create_user('amp_member', password='x')
        for user, role in (
            (self.owner, OrganizationMembership.Role.OWNER),
            (self.member, OrganizationMembership.Role.MEMBER),
        ):
            OrganizationMembership.objects.create(
                organization=self.org, user=user, role=role, is_active=True,
            )
        self.contract = Contract.objects.create(
            organization=self.org,
            title='Amp Contract',
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
            assigned_to=self.member,
            due_date=timezone.now() - timedelta(days=1),
        )

    def test_work_health_admin_only(self):
        url = reverse('contracts:work_health_report')
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.owner)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Work health')
        self.assertContains(response, 'Bottlenecks')

    def test_saved_views_crud(self):
        self.client.force_login(self.member)
        list_url = reverse('contracts:my_work_saved_views_api')
        create = self.client.post(
            list_url,
            data='{"name":"Overdue approvals","filters":{"due":"overdue","workType":"approval"},"is_default":true}',
            content_type='application/json',
        )
        self.assertEqual(create.status_code, 200)
        payload = create.json()
        self.assertTrue(payload['ok'])
        view_id = payload['view']['id']
        self.assertTrue(
            MyWorkSavedView.objects.filter(
                pk=view_id, user=self.member, organization=self.org, is_default=True,
            ).exists()
        )

        listed = self.client.get(list_url)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.json()['views']), 1)

        detail_url = reverse('contracts:my_work_saved_view_detail_api', kwargs={'view_id': view_id})
        deleted = self.client.delete(detail_url)
        self.assertEqual(deleted.status_code, 200)
        self.assertFalse(MyWorkSavedView.objects.filter(pk=view_id).exists())

    def test_my_work_loads_default_saved_view(self):
        MyWorkSavedView.objects.create(
            organization=self.org,
            user=self.member,
            name='Defaults',
            filters={'due': 'overdue', 'workType': 'approval'},
            is_default=True,
        )
        self.client.force_login(self.member)
        response = self.client.get(reverse('contracts:my_work'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-saved-views-url')
        self.assertContains(response, 'Saved views')
        self.assertEqual(response.context['my_work_default_filters']['due'], 'overdue')
        soft = self.client.get(reverse('contracts:my_work') + '?format=json')
        self.assertEqual(soft.status_code, 200)
        body = soft.json()
        self.assertIn('signature', body)
        self.assertIn('count', body)

    def test_overdue_priority_boost_rule(self):
        today = timezone.localdate()
        row = _base_row(
            row_id=f'approval:{self.approval.pk}',
            title='Approve legal',
            work_kind='approval',
            work_type_key='approval',
            work_type_label='Approval',
            contract=self.contract,
            user=self.member,
            assigned_date=today,
            due_date=today - timedelta(days=2),
            priority_value='LOW',
            action_label='Review',
            action_href='/x',
            today=today,
        )
        self.assertEqual(row['priority_label'], 'High')
        self.assertIn('Overdue', row['priority_reason'] or '')

        boost = measured_priority_boost(
            work_kind='approval',
            org_overdue_rates={'approval': {'overdue_rate': 0.5}},
        )
        self.assertEqual(boost, 1)
        low = measured_priority_boost(
            work_kind='approval',
            org_overdue_rates={'approval': {'overdue_rate': 0.1}},
        )
        self.assertEqual(low, 0)

        # Measured overdue-rate nudge applies to non-overdue due-soon work.
        soon_row = _base_row(
            row_id=f'approval:{self.approval.pk}:soon',
            title='Approve soon',
            work_kind='approval',
            work_type_key='approval',
            work_type_label='Approval',
            contract=self.contract,
            user=self.member,
            assigned_date=today,
            due_date=today + timedelta(days=2),
            priority_value='MEDIUM',
            action_label='Review',
            action_href='/x',
            today=today,
        )
        soon_row['work_kind'] = 'approval'
        with_boost = _sort_key(
            soon_row, today, org_overdue_rates={'approval': {'overdue_rate': 0.5}},
        )
        without = _sort_key(soon_row, today, org_overdue_rates=None)
        self.assertLess(with_boost[0], without[0])

    def test_settings_hub_links_work_health_for_admin(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse('settings_hub'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('contracts:work_health_report'))
        self.assertContains(response, 'Work health')
