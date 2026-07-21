"""Phase 1 boundary tests — personal vs org-wide work surfaces."""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from contracts.models import Contract, Organization, OrganizationMembership
from contracts.services.command_center import DEFAULT_SAVED_VIEWS
from contracts.services.contract_detail_workspace import contract_operations_hub_tabs

User = get_user_model()


class Phase1BoundaryTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            name='Boundary Org',
            slug='boundary-org',
            workspace_mode=Organization.WorkspaceMode.IN_HOUSE_CLM,
        )
        self.user = User.objects.create_user(username='boundary_user', password='testpass123!')
        OrganizationMembership.objects.create(
            organization=self.org,
            user=self.user,
            role=OrganizationMembership.Role.OWNER,
            is_active=True,
        )
        self.client = Client()
        self.client.login(username='boundary_user', password='testpass123!')

    def test_command_center_saved_views_exclude_personal_my_queue(self):
        keys = [view['key'] for view in DEFAULT_SAVED_VIEWS]
        self.assertNotIn('mine', keys)
        self.assertIn('blocked', keys)
        blocked = next(view for view in DEFAULT_SAVED_VIEWS if view['key'] == 'blocked')
        self.assertEqual(blocked['name'], 'Blocked work')

    def test_dashboard_queue_tabs_exclude_waiting_on_me(self):
        Contract.objects.create(
            organization=self.org,
            title='Boundary Contract',
            content='Seed',
            status=Contract.Status.IN_PROGRESS,
            created_by=self.user,
        )
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        tab_keys = [tab['key'] for tab in response.context['queue_tabs']]
        self.assertNotIn('waiting_on_me', tab_keys)

    def test_contract_operations_hub_links_my_work_not_dashboard(self):
        hub = contract_operations_hub_tabs(active='my_work')
        my_work_tab = next(tab for tab in hub if tab['key'] == 'my_work')
        self.assertTrue(my_work_tab['active'])
        self.assertEqual(my_work_tab['label'], 'My Work')
        self.assertEqual(my_work_tab['url'], reverse('contracts:my_work'))

    def test_privacy_reviews_has_my_reviews_tab(self):
        response = self.client.get(reverse('contracts:dpa_review_pack_list'), {'view': 'my_reviews'})
        self.assertEqual(response.status_code, 200)
        tab_keys = [tab['key'] for tab in response.context['view_tabs']]
        self.assertIn('my_reviews', tab_keys)

    def test_command_center_uses_org_wide_approval_framing(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Organization-wide view of portfolio health')
        self.assertNotContains(response, 'in your queue')
