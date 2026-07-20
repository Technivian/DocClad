"""Tests for the Repository consolidation block (reusing StageDots /
AssigneeChip / ActivityLine on the Repository table).

Covers: role rendering, enterprise-safe search/filter controls,
the contracts API payload carrying WorkQueue-aligned fields, no raw
enums/ISO timestamps/model names/Dutch case_phase labels, empty state,
cross-tenant isolation, and the legacy contract_list migration banner.
"""
import json
import re
from datetime import date

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from contracts.middleware import log_action
from contracts.models import ApprovalRequest, Contract, Organization, OrganizationMembership
from contracts.tenancy import get_user_organization

ISO_TIMESTAMP_RE = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}')
DUTCH_CASE_PHASE_WORDS = ('beoordeling', 'plaatsing', 'afgerond')


class RepositoryRoleRenderingTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Repo Role Firm', slug='repo-role-firm')

    def _client_for_role(self, role, username):
        user = User.objects.create_user(username=username, password='testpass123', email=f'{username}@example.com')
        OrganizationMembership.objects.create(organization=self.organization, user=user, role=role, is_active=True)
        client = Client()
        client.login(username=username, password='testpass123')
        return client

    def test_repository_renders_for_owner(self):
        client = self._client_for_role(OrganizationMembership.Role.OWNER, 'repo_owner')
        response = client.get(reverse('contracts:repository'))
        self.assertEqual(response.status_code, 200)

    def test_repository_renders_for_admin(self):
        client = self._client_for_role(OrganizationMembership.Role.ADMIN, 'repo_admin')
        response = client.get(reverse('contracts:repository'))
        self.assertEqual(response.status_code, 200)

    def test_repository_renders_for_member(self):
        client = self._client_for_role(OrganizationMembership.Role.MEMBER, 'repo_member')
        response = client.get(reverse('contracts:repository'))
        self.assertEqual(response.status_code, 200)


class RepositoryControlsPreservedTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Repo Controls Firm', slug='repo-controls-firm')
        self.user = User.objects.create_user(username='repo_controls', password='testpass123', email='repo_controls@example.com')
        OrganizationMembership.objects.create(
            organization=self.organization, user=self.user,
            role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        self.client.login(username='repo_controls', password='testpass123')

    def test_filter_controls_render_without_browser_local_saved_views(self):
        Contract.objects.create(
            organization=self.organization,
            title='Repository filter contract',
            counterparty='Atlas Workforce B.V.',
            owner=self.user,
            risk_level=Contract.RiskLevel.HIGH,
            status=Contract.Status.IN_PROGRESS,
            created_by=self.user,
        )
        response = self.client.get(reverse('contracts:repository'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="saved-views"')
        self.assertNotContains(response, 'saved in this browser')
        self.assertContains(response, 'id="filter-chips"')
        self.assertContains(response, 'id="search-input"')
        self.assertContains(response, 'id="sort-select"')
        self.assertContains(response, 'id="contracts-table"')
        self.assertContains(response, 'id="details-drawer"')
        self.assertContains(response, 'id="bulk-action-bar"')
        self.assertContains(response, 'id="repo-bulk-status"')
        self.assertContains(response, 'id="repo-bulk-export"')
        self.assertContains(response, 'id="owner-filter-select"')
        self.assertContains(response, 'id="counterparty-filter-select"')
        self.assertContains(response, 'id="risk-filter-select"')
        self.assertContains(response, 'id="approval-filter-select"')
        self.assertContains(response, f'value="{self.user.pk}"')
        self.assertContains(response, 'Atlas Workforce B.V.')
        self.assertContains(response, 'High')
        self.assertContains(response, 'Pending')
        self.assertContains(response, reverse('contracts:repository'))
        self.assertContains(response, reverse('dashboard'))
        self.assertContains(response, reverse('contracts:approval_request_list'))
        self.assertContains(response, reverse('contracts:signature_request_list'))
        self.assertContains(response, reverse('contracts:risk_log_list'))

    def test_new_stage_assignee_activity_columns_present(self):
        response = self.client.get(reverse('contracts:repository'))
        self.assertContains(response, 'Stage')
        self.assertContains(response, 'Owner')
        self.assertContains(response, 'Latest activity')
        self.assertContains(response, 'Key date')
        self.assertNotContains(response, 'Assigned owner')
        self.assertContains(response, '>Type</')


class RepositoryApiRowShapeTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Repo Api Firm', slug='repo-api-firm')
        self.user = User.objects.create_user(username='repo_api', password='testpass123', email='repo_api@example.com')
        OrganizationMembership.objects.create(
            organization=self.organization, user=self.user,
            role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        self.client.login(username='repo_api', password='testpass123')

    def test_contracts_api_includes_workqueue_fields_without_raw_internals(self):
        contract = Contract.objects.create(
            organization=self.organization,
            title='Api Row Contract',
            content='Seed content',
            status=Contract.Status.IN_PROGRESS,
            lifecycle_stage=Contract.LifecycleStage.NEGOTIATION,
            created_by=self.user,
        )
        ApprovalRequest.objects.create(
            organization=self.organization,
            contract=contract,
            approval_step='LEGAL',
            status='PENDING',
            assigned_to=self.user,
        )
        log_action(
            self.user, 'UPDATE', 'Contract', contract.id, str(contract),
            changes={'event': 'contract_updated'}, organization=self.organization,
        )

        response = self.client.get(reverse('contracts:contracts_api'))
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        row = next(c for c in payload['contracts'] if c['id'] == str(contract.id))

        # WorkQueue-aligned fields are present and server-computed. Badge
        # presentation is expressed through canonical semantic tones.
        self.assertIn('stage_steps', row)
        self.assertTrue(row['stage_steps'])
        self.assertEqual(row['status_badge_tone'], 'progress')
        self.assertEqual(row['stage_badge_tone'], 'progress')
        self.assertNotIn('status_badge_class', row)
        self.assertEqual(row['assignee_name'], self.user.get_full_name() or self.user.username)
        self.assertIsNotNone(row['latest_activity_text'])
        self.assertIn('updated', row['latest_activity_text'].lower())
        self.assertIn('contract', row['latest_activity_text'].lower())

        # The human-facing fields — the only ones the JS renderer prints —
        # never carry the raw enum, a raw ORM class name, or an ISO
        # timestamp. (`status` itself is a legitimate internal identifier,
        # same as `id`; the JS only ever displays `status_display`.)
        self.assertIn('In progress', row['status_display'])
        human_facing = json.dumps({
            'status_display': row['status_display'],
            'stage_steps': row['stage_steps'],
            'assignee_name': row['assignee_name'],
            'latest_activity_text': row['latest_activity_text'],
            'latest_activity_time': row['latest_activity_time'],
            'value_display': row['value_display'],
            'end_date_display': row['end_date_display'],
        })
        self.assertNotIn('IN_PROGRESS', human_facing)
        for raw_name in ('ApprovalRequest', 'WorkflowStep', 'DSARRequest', 'CaseSignal'):
            self.assertNotIn(raw_name, human_facing)
        self.assertIsNone(ISO_TIMESTAMP_RE.search(row['latest_activity_text'] or ''))
        self.assertIsNone(ISO_TIMESTAMP_RE.search(row['end_date_display'] or ''))
        for word in DUTCH_CASE_PHASE_WORDS:
            self.assertNotIn(word, human_facing.lower())

    def test_exception_marker_becomes_badge_fields_not_embedded_name(self):
        Contract.objects.create(
            organization=self.organization,
            title='MSA — Northstar Consulting B.V. - Exception',
            counterparty='Northstar Consulting B.V. - Exception',
            contract_type=Contract.ContractType.MSA,
            status=Contract.Status.IN_PROGRESS,
            lifecycle_stage='DRAFTING',
            created_by=self.user,
            end_date=date(2027, 7, 16),
            value=120000,
            currency='EUR',
        )
        response = self.client.get(reverse('contracts:contracts_api'))
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        row = next(c for c in payload['contracts'] if 'Northstar' in c['title'])
        self.assertEqual(row['title'], 'MSA — Northstar Consulting B.V.')
        self.assertEqual(row['counterparty'], 'Northstar Consulting B.V.')
        self.assertTrue(row['has_exception'])
        self.assertEqual(row['contract_type_short'], 'MSA')
        self.assertEqual(row['contract_type_display'], 'Master Service Agreement')
        self.assertEqual(row['end_date_display'], '16 Jul 2027')
        self.assertNotIn('Exception', row['title'])
        self.assertNotIn('Exception', row['counterparty'])

    def test_obligation_tracking_stage_uses_short_badge_label(self):
        Contract.objects.create(
            organization=self.organization,
            title='Active obligations contract',
            status='ACTIVE',
            lifecycle_stage='OBLIGATION_TRACKING',
            created_by=self.user,
        )
        response = self.client.get(reverse('contracts:contracts_api'))
        payload = json.loads(response.content)
        row = next(c for c in payload['contracts'] if c['title'] == 'Active obligations contract')
        self.assertEqual(row['stage_display'], 'Obligations')
        self.assertEqual(row['stage_display_full'], 'Obligation tracking')

    def test_unassigned_contract_has_no_assignee(self):
        Contract.objects.create(
            organization=self.organization,
            title='Unassigned Api Contract',
            content='Seed content',
            status='IN_PROGRESS',
            created_by=self.user,
        )
        response = self.client.get(reverse('contracts:contracts_api'))
        payload = json.loads(response.content)
        row = next(c for c in payload['contracts'] if c['title'] == 'Unassigned Api Contract')
        self.assertIsNone(row['assignee_name'])
        self.assertIsNone(row['latest_activity_text'])

    def test_empty_repository_returns_no_contracts(self):
        response = self.client.get(reverse('contracts:contracts_api'))
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual(payload['contracts'], [])
        self.assertEqual(payload['total_count'], 0)

        page_response = self.client.get(reverse('contracts:repository'))
        self.assertEqual(page_response.status_code, 200)


class RepositoryCrossTenantIsolationTests(TestCase):
    def setUp(self):
        self.org_a = Organization.objects.create(name='Repo Tenant A', slug='repo-tenant-a')
        self.org_b = Organization.objects.create(name='Repo Tenant B', slug='repo-tenant-b')
        self.user_a = User.objects.create_user(username='repo_tenant_a', password='testpass123', email='a@example.com')
        self.user_b = User.objects.create_user(username='repo_tenant_b', password='testpass123', email='b@example.com')
        OrganizationMembership.objects.create(organization=self.org_a, user=self.user_a, role=OrganizationMembership.Role.OWNER, is_active=True)
        OrganizationMembership.objects.create(organization=self.org_b, user=self.user_b, role=OrganizationMembership.Role.OWNER, is_active=True)
        Contract.objects.create(
            organization=self.org_b, title='Tenant B Only Contract', content='secret',
            status='ACTIVE', created_by=self.user_b,
        )

    def test_other_tenants_contract_never_appears(self):
        self.client.login(username='repo_tenant_a', password='testpass123')
        response = self.client.get(reverse('contracts:contracts_api'))
        payload = json.loads(response.content)
        titles = [c['title'] for c in payload['contracts']]
        self.assertNotIn('Tenant B Only Contract', titles)
        self.assertEqual(payload['total_count'], 0)


class LegacyContractListMigrationTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Legacy List Firm', slug='legacy-list-firm')
        self.user = User.objects.create_user(username='legacy_user', password='testpass123', email='legacy@example.com')
        OrganizationMembership.objects.create(
            organization=self.organization, user=self.user,
            role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        self.client.login(username='legacy_user', password='testpass123')

    def test_legacy_list_still_works_and_links_to_repository(self):
        Contract.objects.create(
            organization=self.organization, title='Legacy List Contract', content='seed',
            status='ACTIVE', created_by=self.user,
        )
        response = self.client.get(reverse('contracts:contract_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Legacy List Contract')
        self.assertContains(response, 'Repository is now the canonical contract list')
        self.assertContains(response, reverse('contracts:repository'))
