"""Tests for the Contract Detail Record Shell + Tabs block.

Covers: shared shell/header rhythm, the enhanced metadata header (StageDots,
AssigneeChip for the derived owner, risk badge, key dates), approved tab
labels with banned jargon removed, Documents/Workflow/Activity tab content
reusing existing data only, real (non-fake) primary actions, and copy free
of raw enums/ISO timestamps/model names.
"""
import re

from django.contrib.auth.models import User
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from contracts.models import (
    ApprovalRequest,
    Contract,
    Deadline,
    Document,
    LegalTask,
    Organization,
    OrganizationMembership,
    RiskLog,
    SignatureRequest,
)

ISO_TIMESTAMP_RE = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}')
BANNED_JARGON = ('Action Cockpit', 'Case Flow', 'Target Stage', 'Operational scan', 'Packet command center')


def page_body(html):
    """Slice out Django Debug Toolbar's panel — DEBUG=True dumps the full
    template context, so raw values can appear there even when the real
    page body never renders them."""
    end = html.find('id="djDebug"')
    return html[:end] if end != -1 else html


class ContractDetailShellTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Shell Firm', slug='cdetail-shell-firm')
        self.user = User.objects.create_user(username='cdetail_user', password='testpass123', email='shell@example.com')
        OrganizationMembership.objects.create(organization=self.organization, user=self.user, role=OrganizationMembership.Role.MEMBER, is_active=True)
        self.client = TestClient()
        self.client.login(username='cdetail_user', password='testpass123')
        self.contract = Contract.objects.create(
            organization=self.organization, title='Shell Contract', content='Seed',
            status=Contract.Status.ACTIVE, created_by=self.user,
        )

    def test_renders_for_member(self):
        response = self.client.get(reverse('contracts:contract_detail', kwargs={'pk': self.contract.pk}))
        self.assertEqual(response.status_code, 200)

    def test_uses_shared_page_wrap_shell(self):
        response = self.client.get(reverse('contracts:contract_detail', kwargs={'pk': self.contract.pk}))
        self.assertContains(response, 'page-wrap')

    def test_uses_shared_page_header_pattern(self):
        response = self.client.get(reverse('contracts:contract_detail', kwargs={'pk': self.contract.pk}))
        self.assertContains(response, 'arch-header')
        self.assertContains(response, 'arch-title')

    def test_approved_tab_labels_present(self):
        response = self.client.get(reverse('contracts:contract_detail', kwargs={'pk': self.contract.pk}))
        body = page_body(response.content.decode())
        for label in ('Overview', 'Documents', 'Workflow', 'Activity'):
            self.assertIn(label, body)

    def test_banned_jargon_is_absent(self):
        response = self.client.get(reverse('contracts:contract_detail', kwargs={'pk': self.contract.pk}))
        body = page_body(response.content.decode())
        for phrase in BANNED_JARGON:
            self.assertNotIn(phrase, body, f'Found banned jargon "{phrase}" in Contract Detail body')

    def test_compliance_tab_absent_when_no_risks_exist(self):
        response = self.client.get(reverse('contracts:contract_detail', kwargs={'pk': self.contract.pk}))
        body = page_body(response.content.decode())
        self.assertNotIn('data-tab="compliance"', body)

    def test_compliance_tab_present_when_risks_exist(self):
        RiskLog.objects.create(title='Linked risk', description='d', contract=self.contract, created_by=self.user)
        response = self.client.get(reverse('contracts:contract_detail', kwargs={'pk': self.contract.pk}))
        body = page_body(response.content.decode())
        self.assertIn('data-tab="compliance"', body)
        self.assertIn('Compliance', body)


class ContractDetailMetadataHeaderTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Header Firm', slug='cdetail-header-firm')
        self.owner = User.objects.create_user(username='cdetail_owner', password='testpass123', email='owner@example.com', first_name='Rowan')
        OrganizationMembership.objects.create(organization=self.organization, user=self.owner, role=OrganizationMembership.Role.MEMBER, is_active=True)
        self.client = TestClient()
        self.client.login(username='cdetail_owner', password='testpass123')
        self.contract = Contract.objects.create(
            organization=self.organization, title='Header Contract', content='Seed',
            status=Contract.Status.ACTIVE, counterparty='Northwind Logistics LLC', value=125000,
            currency='USD', start_date=timezone.localdate(), end_date=timezone.localdate(),
            risk_level=Contract.RiskLevel.HIGH, lifecycle_stage='NEGOTIATION', created_by=self.owner,
        )

    def test_header_shows_key_metadata_fields(self):
        response = self.client.get(reverse('contracts:contract_detail', kwargs={'pk': self.contract.pk}))
        body = page_body(response.content.decode())
        self.assertIn('Header Contract', body)
        self.assertIn('Active', body)
        self.assertIn('Northwind Logistics LLC', body)
        self.assertIn('$125,000.00', body)
        self.assertIn('High risk', body)
        self.assertIn('stage-dot-current', body)
        self.assertIn('Negotiation', body)

    def test_header_shows_owner_via_assignee_chip(self):
        Deadline.objects.create(
            title='Follow up', deadline_type='CONTRACT', contract=self.contract,
            assigned_to=self.owner, due_date=timezone.localdate(), is_completed=False,
        )
        response = self.client.get(reverse('contracts:contract_detail', kwargs={'pk': self.contract.pk}))
        body = page_body(response.content.decode())
        self.assertIn('Rowan', body)

    def test_no_owner_renders_unassigned_not_a_crash(self):
        response = self.client.get(reverse('contracts:contract_detail', kwargs={'pk': self.contract.pk}))
        body = page_body(response.content.decode())
        self.assertIn('Unassigned', body)


class ContractDetailActionsTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Action Firm', slug='cdetail-action-firm')
        self.user = User.objects.create_user(username='cdetail_action_user', password='testpass123', email='action@example.com')
        OrganizationMembership.objects.create(organization=self.organization, user=self.user, role=OrganizationMembership.Role.MEMBER, is_active=True)
        self.client = TestClient()
        self.client.login(username='cdetail_action_user', password='testpass123')
        self.contract = Contract.objects.create(
            organization=self.organization, title='Action Contract', content='Seed',
            status=Contract.Status.DRAFT, created_by=self.user,
        )

    def test_primary_actions_link_to_real_working_endpoints(self):
        response = self.client.get(reverse('contracts:contract_detail', kwargs={'pk': self.contract.pk}))
        body = page_body(response.content.decode())
        self.assertIn(reverse('contracts:contract_update', kwargs={'pk': self.contract.pk}), body)
        self.assertIn(reverse('contracts:approval_request_create'), body)
        self.assertIn(reverse('contracts:signature_request_create'), body)
        self.assertIn('Run grounded check', body)

    def test_grounded_check_endpoint_still_wired(self):
        response = self.client.get(reverse('contracts:contract_detail', kwargs={'pk': self.contract.pk}))
        body = page_body(response.content.decode())
        self.assertIn(reverse('contracts:contract_ai_assistant', kwargs={'pk': self.contract.pk}), body)


class ContractDetailDocumentsTabTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Docs Firm', slug='cdetail-docs-firm')
        self.uploader = User.objects.create_user(username='cdetail_uploader', password='testpass123', email='uploader@example.com', first_name='Casey')
        OrganizationMembership.objects.create(organization=self.organization, user=self.uploader, role=OrganizationMembership.Role.MEMBER, is_active=True)
        self.client = TestClient()
        self.client.login(username='cdetail_uploader', password='testpass123')
        self.contract = Contract.objects.create(
            organization=self.organization, title='Docs Contract', content='Seed',
            status=Contract.Status.ACTIVE, created_by=self.uploader,
        )

    def test_documents_tab_shows_empty_state_without_giant_panel(self):
        response = self.client.get(reverse('contracts:contract_detail', kwargs={'pk': self.contract.pk}))
        body = page_body(response.content.decode())
        self.assertIn('No documents attached yet.', body)

    def test_documents_tab_shows_uploaded_document_fields(self):
        Document.objects.create(
            organization=self.organization, title='MSA Final', document_type=Document.DocType.CONTRACT,
            version=2, contract=self.contract, uploaded_by=self.uploader,
        )
        response = self.client.get(reverse('contracts:contract_detail', kwargs={'pk': self.contract.pk}))
        body = page_body(response.content.decode())
        self.assertIn('MSA Final', body)
        self.assertIn('Contract Document', body)
        self.assertIn('v2', body)
        self.assertIn('Casey', body)


class ContractDetailWorkflowTabTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Workflow Firm', slug='cdetail-workflow-firm')
        self.assignee = User.objects.create_user(username='cdetail_wf_assignee', password='testpass123', email='wf@example.com', first_name='Jordan')
        self.creator = User.objects.create_user(username='cdetail_wf_creator', password='testpass123', email='wfcreator@example.com')
        OrganizationMembership.objects.create(organization=self.organization, user=self.assignee, role=OrganizationMembership.Role.MEMBER, is_active=True)
        OrganizationMembership.objects.create(organization=self.organization, user=self.creator, role=OrganizationMembership.Role.MEMBER, is_active=True)
        self.client = TestClient()
        self.client.login(username='cdetail_wf_assignee', password='testpass123')
        self.contract = Contract.objects.create(
            organization=self.organization, title='Workflow Contract', content='Seed',
            status=Contract.Status.PENDING, created_by=self.creator,
        )

    def test_workflow_tab_shows_empty_states_when_nothing_exists(self):
        response = self.client.get(reverse('contracts:contract_detail', kwargs={'pk': self.contract.pk}))
        body = page_body(response.content.decode())
        self.assertIn('No approvals requested for this contract yet.', body)
        self.assertIn('No signature requests for this contract yet.', body)
        self.assertIn('No tasks linked to this contract yet.', body)

    def test_workflow_tab_shows_existing_approval_signature_and_task(self):
        ApprovalRequest.objects.create(
            organization=self.organization, contract=self.contract, approval_step='LEGAL',
            status='PENDING', assigned_to=self.assignee,
        )
        SignatureRequest.objects.create(
            organization=self.organization, contract=self.contract, signer_name='Alex Signer',
            signer_email='alex@example.com', status=SignatureRequest.Status.SENT,
        )
        LegalTask.objects.create(
            title='Review indemnification', description='d', contract=self.contract,
            assigned_to=self.assignee, due_date=timezone.localdate(), status=LegalTask.Status.PENDING,
        )
        response = self.client.get(reverse('contracts:contract_detail', kwargs={'pk': self.contract.pk}))
        body = page_body(response.content.decode())
        self.assertIn('Legal Review', body)
        self.assertIn('Alex Signer', body)
        self.assertIn('Review indemnification', body)
        self.assertIn('Jordan', body)


class ContractDetailActivityTabTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Activity Firm', slug='cdetail-activity-firm')
        self.user = User.objects.create_user(username='cdetail_activity_user', password='testpass123', email='activity@example.com', first_name='Sam')
        OrganizationMembership.objects.create(organization=self.organization, user=self.user, role=OrganizationMembership.Role.MEMBER, is_active=True)
        self.client = TestClient()
        self.client.login(username='cdetail_activity_user', password='testpass123')
        self.contract = Contract.objects.create(
            organization=self.organization, title='Activity Contract', content='Seed',
            status=Contract.Status.ACTIVE, created_by=self.user,
        )

    def test_activity_tab_shows_empty_state(self):
        response = self.client.get(reverse('contracts:contract_detail', kwargs={'pk': self.contract.pk}))
        body = page_body(response.content.decode())
        self.assertIn('No recent activity recorded for this contract.', body)

    def test_activity_tab_shows_human_readable_entry(self):
        from contracts.middleware import log_action
        log_action(
            self.user, 'UPDATE', 'Contract', self.contract.id, str(self.contract),
            changes={'event': 'contract_updated'}, organization=self.organization,
        )
        response = self.client.get(reverse('contracts:contract_detail', kwargs={'pk': self.contract.pk}))
        body = page_body(response.content.decode())
        self.assertIn('Sam', body)
        self.assertNotIn('UPDATE', body)
        self.assertIsNone(ISO_TIMESTAMP_RE.search(body), 'Found a raw ISO timestamp in the Contract Detail response')


class ContractDetailCopyQualityTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Copy Firm', slug='cdetail-copy-firm')
        self.user = User.objects.create_user(username='cdetail_copy_user', password='testpass123', email='copy@example.com')
        OrganizationMembership.objects.create(organization=self.organization, user=self.user, role=OrganizationMembership.Role.MEMBER, is_active=True)
        self.client = TestClient()
        self.client.login(username='cdetail_copy_user', password='testpass123')

    def test_no_raw_internals_leak_into_the_page(self):
        contract = Contract.objects.create(
            organization=self.organization, title='Copy Quality Contract', content='Seed',
            status=Contract.Status.IN_REVIEW, lifecycle_stage='INTERNAL_REVIEW', created_by=self.user,
        )
        RiskLog.objects.create(title='Risk', description='d', contract=contract, status=RiskLog.Status.IN_PROGRESS, created_by=self.user)
        response = self.client.get(reverse('contracts:contract_detail', kwargs={'pk': contract.pk}))
        body = page_body(response.content.decode())

        self.assertNotIn('Contract object', body)
        self.assertNotIn('IN_REVIEW', body)
        self.assertIn('In Review', body)
        self.assertNotIn('INTERNAL_REVIEW', body)
        self.assertIn('Internal Review', body)
        self.assertNotIn('In opvolging', body)
        self.assertIsNone(ISO_TIMESTAMP_RE.search(body), 'Found a raw ISO timestamp in the Contract Detail response')


class ContractDetailCrossTenantIsolationTests(TestCase):
    def setUp(self):
        self.org_a = Organization.objects.create(name='CDetail Org A', slug='cdetail-org-a')
        self.org_b = Organization.objects.create(name='CDetail Org B', slug='cdetail-org-b')
        self.user_a = User.objects.create_user(username='cdetail_iso_a', password='testpass123', email='a@example.com')
        self.user_b = User.objects.create_user(username='cdetail_iso_b', password='testpass123', email='b@example.com')
        OrganizationMembership.objects.create(organization=self.org_a, user=self.user_a, role=OrganizationMembership.Role.MEMBER, is_active=True)
        OrganizationMembership.objects.create(organization=self.org_b, user=self.user_b, role=OrganizationMembership.Role.MEMBER, is_active=True)
        self.contract_a = Contract.objects.create(
            organization=self.org_a, title='Org A Contract', content='Seed', status=Contract.Status.ACTIVE, created_by=self.user_a,
        )

    def test_other_org_member_gets_404(self):
        client = TestClient()
        client.login(username='cdetail_iso_b', password='testpass123')
        response = client.get(reverse('contracts:contract_detail', kwargs={'pk': self.contract_a.pk}))
        self.assertEqual(response.status_code, 404)
