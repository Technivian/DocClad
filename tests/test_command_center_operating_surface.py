from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from contracts.models import (
    ApprovalRequest,
    CommandCenterWorkItem,
    Contract,
    Deadline,
    Organization,
    OrganizationMembership,
    RiskLog,
)
from contracts.services.command_center import (
    build_upcoming_deadlines,
    explainable_risk_score,
    format_deadline_status,
    get_persisted_command_center_rows,
    group_recommended_actions,
    rank_command_center_rows,
)

User = get_user_model()


def work_row(title, **overrides):
    now = timezone.now()
    row = {
        'title': title,
        'workspace_href': f'/work/{title.lower().replace(" ", "-")}/',
        'status_label': 'Open',
        'priority': 50,
        'risk_level': 'MEDIUM',
        'risk_label': 'Medium',
        'due_date': None,
        'due_overdue': False,
        'updated_at': now,
        'blocking_issue': 'Open operational review item.',
        'next_action': 'Open review',
        'counterparty': 'Counterparty',
        'owner_label': 'Owner',
        'recommendation_reason': 'Action required',
        'due_label': 'No due date',
    }
    row.update(overrides)
    return row


class CommandCenterServiceTests(TestCase):
    def test_priority_ranking_is_urgent_and_deterministic(self):
        today = timezone.localdate()
        rows = [
            work_row('Normal', priority=90, risk_level='CRITICAL'),
            work_row('Blocked', status_label='Blocked', priority=70, risk_level='HIGH'),
            work_row('Overdue', due_date=today - timedelta(days=1), due_overdue=True),
        ]
        first = [row['title'] for row in rank_command_center_rows(rows, today=today)]
        second = [row['title'] for row in rank_command_center_rows(list(reversed(rows)), today=today)]
        self.assertEqual(first, ['Overdue', 'Blocked', 'Normal'])
        self.assertEqual(first, second)

    def test_score_composition_and_missing_history(self):
        result = explainable_risk_score('HIGH', {
            'high_risk_deviations': 1,
            'unresolved_blockers': 1,
            'missing_approval_authority': 1,
        })
        self.assertEqual(result['score'], 72)
        self.assertEqual(result['history_label'], 'No prior snapshot')
        self.assertFalse(result['has_history'])
        with_history = explainable_risk_score('HIGH', {}, history=[{'score': 60}])
        self.assertTrue(with_history['has_history'])

    def test_high_risk_finding_cannot_render_as_low_attention(self):
        result = explainable_risk_score('LOW', {'high_risk_deviations': 1})
        self.assertEqual(result['score'], 65)
        self.assertEqual(result['band'], 'High attention')

    def test_duplicate_recommendations_group_and_order(self):
        now = timezone.now()
        finance_issue = 'Contract value exceeds the finance approval threshold of 250,000.'
        rows = [
            work_row('Finance B', status_label='Blocked', blocking_issue=finance_issue, counterparty='Beta', updated_at=now - timedelta(hours=3)),
            work_row('Finance A', status_label='Blocked', blocking_issue=finance_issue, counterparty='Alpha', updated_at=now - timedelta(hours=5)),
            work_row('Transfer', blocking_issue='SCC transfer position requires DPO approval.', risk_level='HIGH'),
        ]
        actions = group_recommended_actions(rows)
        self.assertEqual(actions[0]['title'], 'Finance approval required')
        self.assertEqual(actions[0]['count'], 2)
        self.assertIn('+1 more', actions[0]['counterparty_text'])
        self.assertEqual(actions[1]['title'], 'Confirm SCC transfer position')

    def test_deadline_states_and_unconfigured_sort_last(self):
        today = timezone.localdate()
        self.assertEqual(format_deadline_status(today), 'Due today')
        self.assertEqual(format_deadline_status(today + timedelta(days=1)), 'Due tomorrow')
        self.assertEqual(format_deadline_status(today - timedelta(days=2)), 'Overdue by 2 days')
        self.assertEqual(format_deadline_status(None), 'Date not configured')
        items = build_upcoming_deadlines([
            {'title': 'Undated', 'due_date': None, 'href': '/u/'},
            {'title': 'Tomorrow', 'due_date': today + timedelta(days=1), 'href': '/t/'},
            {'title': 'Overdue', 'due_date': today - timedelta(days=1), 'href': '/o/'},
        ], today=today)
        self.assertEqual([item['title'] for item in items], ['Overdue', 'Tomorrow', 'Undated'])


class CommandCenterProductionSurfaceTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            name='Operating Surface Org', slug='operating-surface-org',
            workspace_mode=Organization.WorkspaceMode.IN_HOUSE_CLM,
        )
        self.user = User.objects.create_user(username='surface_owner', password='testpass123!')
        OrganizationMembership.objects.create(
            organization=self.org, user=self.user,
            role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        self.client_ = TestClient()
        self.client_.login(username='surface_owner', password='testpass123!')

    def test_workspace_and_role_visibility(self):
        contract = Contract.objects.create(
            organization=self.org, title='Visible Contract', content='x', created_by=self.user,
        )
        CommandCenterWorkItem.objects.create(
            organization=self.org, source_type=CommandCenterWorkItem.SourceType.CONTRACT,
            title='Visible Work', contract=contract, owner=self.user,
        )
        outsider = User.objects.create_user(username='outsider', password='testpass123!')
        self.assertEqual(get_persisted_command_center_rows(self.org, current_user=outsider), [])
        rows = get_persisted_command_center_rows(self.org, current_user=self.user)
        self.assertEqual([row['title'] for row in rows], ['Visible Work'])

    def test_projection_read_avoids_related_object_n_plus_one(self):
        contract = Contract.objects.create(
            organization=self.org, title='Query Contract', content='x', created_by=self.user,
        )
        for index in range(4):
            CommandCenterWorkItem.objects.create(
                organization=self.org, source_type=CommandCenterWorkItem.SourceType.CONTRACT,
                title=f'Query Work {index}', contract=contract, owner=self.user,
            )
        with self.assertNumQueries(2):
            rows = get_persisted_command_center_rows(self.org, current_user=self.user)
            self.assertEqual(len(rows), 4)

    def test_dashboard_empty_state_governance_links_and_long_content(self):
        long_title = 'Long governed agreement ' + ('title ' * 35)
        long_counterparty = 'Counterparty ' + ('International Holdings ' * 15)
        contract = Contract.objects.create(
            organization=self.org, title=long_title, counterparty=long_counterparty,
            content='x', status='ACTIVE', created_by=self.user,
        )
        response = self.client_.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, long_title)
        self.assertContains(response, long_counterparty)
        self.assertContains(response, 'dc-ds-metric__value--clear')
        self.assertContains(response, 'Approval authority')
        self.assertContains(response, reverse('contracts:approval_rule_list'))
        self.assertContains(response, reverse('contracts:audit_log_list'))

    def test_empty_command_center_state_is_intentional(self):
        response = self.client_.get(reverse('dashboard'))
        self.assertFalse(response.context['portfolio_health_available'])
        self.assertIsNone(response.context['portfolio_health_score'])
        self.assertContains(response, 'Establish your contract portfolio')
        self.assertContains(response, 'Add your first contract to begin monitoring approvals, risks, deadlines, obligations and policy exceptions.')
        self.assertContains(response, 'Health score unavailable')
        self.assertContains(response, 'No contracts monitored yet')
        self.assertContains(response, 'Add first contract')
        self.assertContains(response, 'Upload &amp; review agreement')
        self.assertNotContains(response, 'Getting started')
        self.assertContains(response, 'No active issues')
        self.assertContains(response, 'Monitored queues are clear.')
        action_queue_header = response.content.decode().split('id="recommended-actions-title"', 1)[1].split('</div>', 1)[0]
        self.assertNotIn('View all', action_queue_header)
        self.assertContains(response, 'Setup required')
        self.assertContains(response, 'Configure DPA reviews')
        self.assertContains(response, 'None open')
        self.assertContains(response, 'No policy exceptions')
        self.assertNotContains(response, 'No intervention required')
        self.assertNotContains(response, 'Start DPA review')

    def test_portfolio_score_requires_contract_data_and_uses_open_signals(self):
        contract = Contract.objects.create(
            organization=self.org, title='Measured Contract', content='x', created_by=self.user,
        )
        RiskLog.objects.create(
            contract=contract,
            title='High-risk term',
            description='A material term needs review.',
            risk_level=RiskLog.RiskLevel.HIGH,
            created_by=self.user,
        )
        ApprovalRequest.objects.create(
            organization=self.org,
            contract=contract,
            approval_step='Finance',
            status=ApprovalRequest.Status.PENDING,
            assigned_to=self.user,
        )

        response = self.client_.get(reverse('dashboard'))

        self.assertTrue(response.context['portfolio_health_available'])
        self.assertEqual(response.context['portfolio_health_score'], 83)
        self.assertContains(response, 'Portfolio health score 83 out of 100, Needs attention')
        self.assertContains(response, 'Review priority actions')

    def test_deadline_status_distinguishes_setup_from_clear(self):
        response = self.client_.get(reverse('dashboard'))
        self.assertFalse(response.context['deadline_tracking_configured'])
        self.assertContains(response, 'Configure tracking')
        self.assertContains(response, 'Deadline tracking')
        self.assertContains(response, 'Not configured')
        self.assertContains(response, 'Configure deadlines')
        self.assertNotContains(response, 'See all deadlines')
        self.assertNotContains(response, 'View calendar')

        contract = Contract.objects.create(
            organization=self.org, title='Tracked Contract', content='x', created_by=self.user,
        )
        Deadline.objects.create(
            contract=contract,
            title='Long-range renewal',
            deadline_type=Deadline.DeadlineType.RENEWAL,
            due_date=timezone.localdate() + timedelta(days=90),
            created_by=self.user,
        )
        response = self.client_.get(reverse('dashboard'))
        self.assertTrue(response.context['deadline_tracking_configured'])
        self.assertContains(response, 'dc-ds-metric__value--clear')
        self.assertContains(response, 'View calendar')
        self.assertNotContains(response, 'Configure deadlines')
        self.assertNotContains(response, 'See all deadlines')

    def test_kpi_counts_use_org_wide_pending_approvals(self):
        contract = Contract.objects.create(
            organization=self.org, title='Approval Contract', content='x', created_by=self.user,
        )
        ApprovalRequest.objects.create(
            organization=self.org, contract=contract, approval_step='Legal',
            status=ApprovalRequest.Status.PENDING, assigned_to=self.user,
        )
        response = self.client_.get(reverse('dashboard'))
        self.assertEqual(response.context['clm_pending_approvals_count'], 1)
        self.assertContains(response, '1 open across the organization')
