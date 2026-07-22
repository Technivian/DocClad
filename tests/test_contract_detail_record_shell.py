"""Tests for the Contract Detail workspace.

Covers: persistent header, ?tab= routing, action gating, blocker split,
Contract review terminology, single-column overview, and duplicate-state removal.
"""
import re

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from contracts.middleware import log_action
from contracts.models import (
    ApprovalRequest,
    AuditLog,
    ClauseTemplate,
    ClauseUsageEvent,
    Contract,
    CounterpartyCollaborationItem,
    CounterpartyCollaborationParticipant,
    Deadline,
    Document,
    LegalTask,
    Organization,
    OrganizationMembership,
    NegotiationThread,
    RiskLog,
    SignatureRequest,
)
from contracts.services.contract_detail_workspace import contract_detail_tab_url

ISO_TIMESTAMP_RE = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}')
BANNED_JARGON = ('Action Cockpit', 'Case Flow', 'Target Stage', 'Operational scan', 'Packet command center')
LEGACY_REVIEW_LABELS = (
    'AI review summary',
    'AI review complete',
    'Manual review required',
    'Review refresh required',
    'No document to review',
    'AI review:',
)


def page_body(html):
    """Slice out Django Debug Toolbar's panel — DEBUG=True dumps the full
    template context, so raw values can appear there even when the real
    page body never renders them."""
    end = html.find('id="djDebug"')
    return html[:end] if end != -1 else html


def detail_url(pk, tab=None):
    url = reverse('contracts:contract_detail', kwargs={'pk': pk})
    if tab and tab != 'overview':
        return f'{url}?tab={tab}'
    return url


class ContractDetailShellTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Shell Firm', slug='cdetail-shell-firm')
        self.user = User.objects.create_user(username='cdetail_user', password='testpass123', email='shell@example.com')
        OrganizationMembership.objects.create(organization=self.organization, user=self.user, role=OrganizationMembership.Role.MEMBER, is_active=True)
        self.client = TestClient()
        self.client.login(username='cdetail_user', password='testpass123')
        self.contract = Contract.objects.create(
            organization=self.organization, title='Shell Contract', content='Seed',
            status=Contract.Status.ACTIVE,
            lifecycle_stage=Contract.LifecycleStage.OBLIGATION_TRACKING,
            created_by=self.user,
        )

    def test_renders_for_member(self):
        response = self.client.get(detail_url(self.contract.pk))
        self.assertEqual(response.status_code, 200)

    def test_uses_shared_page_wrap_shell(self):
        response = self.client.get(detail_url(self.contract.pk))
        self.assertContains(response, 'dc-ds-shell')
        self.assertContains(response, 'dc-ds-workspace--record')

    def test_uses_shared_page_header_pattern(self):
        response = self.client.get(detail_url(self.contract.pk))
        self.assertContains(response, 'arch-header')
        self.assertContains(response, 'arch-title')

    def test_uses_document_workspace_surface_and_inline_note_composer(self):
        Document.objects.create(
            organization=self.organization,
            title='Shell Agreement',
            document_type=Document.DocType.CONTRACT,
            version=1,
            contract=self.contract,
            uploaded_by=self.user,
        )
        docs = self.client.get(detail_url(self.contract.pk, 'documents'))
        self.assertContains(docs, 'dc-ds-workspace--record')
        self.assertContains(docs, 'contract-document-hero')
        activity = self.client.get(detail_url(self.contract.pk, 'activity'))
        self.assertContains(activity, 'data-open-note-dialog')
        self.assertContains(activity, 'id="contract-note-dialog"')

    def test_contract_workspace_tabs_and_overview_sections_present(self):
        response = self.client.get(detail_url(self.contract.pk))
        body = page_body(response.content.decode())
        # Multi-line {# #} comments are not stripped by Django and leak as text.
        self.assertNotIn('{#', body)
        self.assertNotIn('Canonical CLM One workspace navigation tabs', body)
        self.assertIn('role="tablist"', body)
        self.assertIn('data-workspace-tabs', body)
        for label in ('Overview', 'Documents', 'Workflow', 'Risks', 'Obligations', 'Audit trail'):
            self.assertIn(label, body)
        tab_labels = [tab['label'] for tab in response.context['workspace_tabs']]
        self.assertEqual(
            tab_labels,
            ['Overview', 'Documents', 'Workflow', 'Risks', 'Obligations', 'Audit trail'],
        )
        self.assertNotIn('Review', tab_labels)
        self.assertNotIn('Activity', tab_labels)
        self.assertIn('Contract lifecycle', body)
        self.assertNotIn('View full workflow', body)
        self.assertNotIn('View workflow</', body)
        self.assertNotIn('contract-workflow-reveal', body)
        self.assertNotIn('contract-lifecycle-stepper', body)
        for label in ('Contract details', 'Progress', 'Action required'):
            self.assertIn(label, body)
        self.assertIn('contract-overview-grid', body)
        self.assertIn('dc-ds-workspace__rail--sticky', body)
        self.assertNotIn('Status:', body)
        self.assertNotIn('Stage:', body)
        self.assertIn('Active', body)
        self.assertIn('Obligation tracking', body)
        self.assertIn('contract-command-position', body)
        self.assertIn('Upcoming milestone', body)
        self.assertNotIn('View all details', body)
        self.assertIn('contract-next-steps__action', body)
        self.assertNotIn('>Contracts</h1>', body)
        self.assertIn('data-suppress-title-promotion', body)
        self.assertIn(f'topbar-page-title">{self.contract.title}', response.content.decode())
        self.assertIn('class="topbar-back-link"', response.content.decode())
        self.assertIn('border-bottom: 1px solid var(--hairline, var(--line));', open('theme/static_src/src/global-shell/workspaces.css').read())
        snapshot = response.context['overview_risk_snapshot']
        self.assertIn(snapshot['tone'], ('attention', 'neutral', 'danger', 'progress', 'success'))
        if 'not assessed' in str(snapshot['label']).casefold() or 'reassessment' in str(snapshot['label']).casefold():
            self.assertNotEqual(snapshot['tone'], 'success')
        workflow = self.client.get(detail_url(self.contract.pk, 'workflow'))
        workflow_body = page_body(workflow.content.decode())
        self.assertIn('Full workflow', workflow_body)
        self.assertIn('contract-progress-track', workflow_body)
        self.assertIn('Upcoming milestone', workflow_body)
        self.assertIn('Review findings', workflow_body)
        self.assertIn('Contract lifecycle', body)
        self.assertNotIn('Quick links', body)

    def test_banned_jargon_is_absent(self):
        response = self.client.get(detail_url(self.contract.pk))
        body = page_body(response.content.decode())
        for phrase in BANNED_JARGON:
            self.assertNotIn(phrase, body, f'Found banned jargon "{phrase}" in Contract Detail body')

    def test_open_findings_section_uses_empty_state_when_no_risks_exist(self):
        response = self.client.get(detail_url(self.contract.pk, 'risks'))
        body = page_body(response.content.decode())
        self.assertIn('No unresolved risk findings are recorded', body)

    def test_open_findings_section_shows_linked_risks(self):
        RiskLog.objects.create(title='Linked risk', description='d', contract=self.contract, created_by=self.user)
        response = self.client.get(detail_url(self.contract.pk, 'risks'))
        body = page_body(response.content.decode())
        self.assertIn('Risks', body)
        self.assertIn('Linked risk', body)

    def test_agreement_family_shows_governing_and_linked_contract_records(self):
        order_confirmation = Contract.objects.create(
            organization=self.organization,
            title='Order Confirmation 2026',
            contract_type=Contract.ContractType.PURCHASE_ORDER,
            status=Contract.Status.IN_PROGRESS,
            parent_contract=self.contract,
            created_by=self.user,
        )

        parent_response = self.client.get(detail_url(self.contract.pk))
        parent_body = page_body(parent_response.content.decode())
        self.assertIn('Related records', parent_body)
        self.assertIn(order_confirmation.title, parent_body)
        self.assertIn('Purchase Order', parent_body)

        child_response = self.client.get(detail_url(order_confirmation.pk))
        child_body = page_body(child_response.content.decode())
        self.assertIn('Governing agreement', child_body)
        self.assertIn(self.contract.title, child_body)


class ContractDetailMetadataHeaderTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Header Firm', slug='cdetail-header-firm')
        self.owner = User.objects.create_user(username='cdetail_owner', password='testpass123', email='owner@example.com', first_name='Rowan')
        OrganizationMembership.objects.create(organization=self.organization, user=self.owner, role=OrganizationMembership.Role.MEMBER, is_active=True)
        self.client = TestClient()
        self.client.login(username='cdetail_owner', password='testpass123')
        self.contract = Contract.objects.create(
            organization=self.organization, title='Header Contract', content='Seed',
            status=Contract.Status.IN_PROGRESS, counterparty='Northwind Logistics LLC', value=125000,
            currency='USD', start_date=timezone.localdate(), end_date=timezone.localdate(),
            risk_level=Contract.RiskLevel.HIGH, lifecycle_stage=Contract.LifecycleStage.NEGOTIATION, created_by=self.owner,
        )

    def test_header_shows_key_metadata_fields(self):
        response = self.client.get(detail_url(self.contract.pk))
        body = page_body(response.content.decode())
        self.assertIn('Header Contract', body)
        self.assertIn('In progress', body)
        self.assertIn('Negotiation', body)
        self.assertIn('contract-command-position', body)
        self.assertNotIn('Status:', body)
        self.assertNotIn('Stage:', body)
        self.assertIn('Northwind Logistics LLC', body)
        self.assertIn('contract-command-owner__avatar', body)
        self.assertIn('Rowan', body)
        self.assertIn('Updated', body)
        self.assertIn('v1', body)
        self.assertIn('contract-command-meta__value', body)
        self.assertRegex(body, r'contract-command-meta__value[^>]*>\$125,000<')
        self.assertNotIn('dc-ds-workspace__metadata-grid', body)

    def test_header_omits_duplicate_command_summary_grid(self):
        response = self.client.get(detail_url(self.contract.pk))
        body = page_body(response.content.decode())
        self.assertNotIn('aria-label="Contract command summary"', body)
        self.assertNotIn('dc-ds-workspace__metadata-grid', body)
        self.assertIn('aria-label="Contract identity"', body)

    def test_phase_one_summary_shows_paper_source_and_workflow_checklist(self):
        reviewer = User.objects.create_user(username='cdetail_route_reviewer', password='testpass123')
        OrganizationMembership.objects.create(
            organization=self.organization, user=reviewer, role=OrganizationMembership.Role.MEMBER, is_active=True,
        )
        self.contract.paper_source = Contract.PaperSource.OUR_PAPER
        self.contract.save(update_fields=['paper_source', 'updated_at'])
        ApprovalRequest.objects.create(
            organization=self.organization,
            contract=self.contract,
            approval_step='LEGAL',
            status=ApprovalRequest.Status.PENDING,
            assigned_to=reviewer,
        )

        overview = self.client.get(detail_url(self.contract.pk))
        overview_body = page_body(overview.content.decode())
        self.assertIn('Progress', overview_body)
        self.assertIn('Contract lifecycle', overview_body)
        self.assertNotIn('View full workflow', overview_body)
        self.assertIn('Paper source', overview_body)
        self.assertIn('Our paper', overview_body)
        self.assertNotIn('Workflow checklist', overview_body)

        approvals = self.client.get(detail_url(self.contract.pk, 'approvals'))
        approvals_body = page_body(approvals.content.decode())
        self.assertIn('Approvals', approvals_body)
        self.assertIn('0 of 1 approved', approvals_body)
        self.assertIn('Add approver', approvals_body)
        self.assertIn(reverse('contracts:approval_request_create') + f'?contract={self.contract.pk}', approvals_body)

    def test_phase_one_summary_shows_playbook_usage_summary(self):
        clause = ClauseTemplate.objects.create(
            organization=self.organization,
            title='Confidentiality',
            content='Approved confidentiality text.',
            is_approved=True,
            created_by=self.owner,
        )
        ClauseUsageEvent.objects.create(
            organization=self.organization,
            clause=clause,
            contract=self.contract,
            action=ClauseUsageEvent.Action.ADDED,
            performed_by=self.owner,
        )
        ClauseUsageEvent.objects.create(
            organization=self.organization,
            clause=clause,
            contract=self.contract,
            action=ClauseUsageEvent.Action.ACCEPTED,
            performed_by=self.owner,
        )

        response = self.client.get(detail_url(self.contract.pk, 'review'))
        body = page_body(response.content.decode())
        self.assertIn('Playbook usage', body)
        self.assertIn('1 approved clause used across 2 recorded events.', body)
        self.assertIn('Approved clauses used', body)
        self.assertIn('Confidentiality', body)
        self.assertIn('2 uses', body)

    def test_header_shows_owner_via_assignee_chip(self):
        Deadline.objects.create(
            title='Follow up', deadline_type='CONTRACT', contract=self.contract,
            assigned_to=self.owner, due_date=timezone.localdate(), is_completed=False,
        )
        response = self.client.get(detail_url(self.contract.pk))
        body = page_body(response.content.decode())
        self.assertIn('Rowan', body)

    def test_no_owner_renders_unassigned_not_a_crash(self):
        self.contract.owner = None
        self.contract.created_by = None
        self.contract.save(update_fields=['owner', 'created_by', 'updated_at'])
        response = self.client.get(detail_url(self.contract.pk))
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
            status=Contract.Status.IN_PROGRESS, created_by=self.user,
        )

    def test_draft_without_document_uses_attach_primary_not_submit(self):
        response = self.client.get(detail_url(self.contract.pk))
        body = page_body(response.content.decode())
        self.assertIn(reverse('contracts:contract_update', kwargs={'pk': self.contract.pk}), body)
        self.assertIn('Attach source document', body)
        actions_idx = body.index('dc-ds-workspace__actions')
        banner_idx = body.index('contract-action-card')
        header_actions = body[actions_idx:banner_idx]
        self.assertNotIn('Attach source document', header_actions)
        # Actions menu removed: it duplicated workspace tabs and sat under the
        # tab strip (lower items like Approvals were unclickable).
        self.assertNotIn('contract-command-overflow', header_actions)
        self.assertNotIn('aria-label="Contract actions"', header_actions)
        self.assertIn('Attach source document', body[banner_idx:banner_idx + 1200])
        self.assertNotIn(reverse('contracts:signature_request_create'), body)
        approvals = self.client.get(detail_url(self.contract.pk, 'approvals'))
        approvals_body = page_body(approvals.content.decode())
        self.assertNotIn('id="contract-submit-review-form"', approvals_body)
        self.assertIn('Attach a source document.', approvals_body)

    def test_signature_action_appears_only_after_all_approvals(self):
        reviewer = User.objects.create_user(username='cdetail_reviewer', password='testpass123')
        OrganizationMembership.objects.create(
            organization=self.organization, user=reviewer,
            role=OrganizationMembership.Role.MEMBER, is_active=True,
        )
        Document.objects.create(
            organization=self.organization, title='Signed path source', document_type=Document.DocType.CONTRACT,
            version=1, contract=self.contract, uploaded_by=self.user,
        )
        self.contract.status = Contract.Status.IN_PROGRESS
        self.contract.lifecycle_stage = Contract.LifecycleStage.SIGNATURE
        self.contract.save(update_fields=['status', 'lifecycle_stage', 'updated_at'])
        ApprovalRequest.objects.create(
            organization=self.organization, contract=self.contract,
            approval_step='LEGAL', status=ApprovalRequest.Status.APPROVED,
            assigned_to=reviewer,
        )

        response = self.client.get(detail_url(self.contract.pk))
        body = page_body(response.content.decode())
        self.assertIn(reverse('contracts:signature_request_create'), body)
        self.assertIn('Prepare signature request', body)

    def test_add_approver_link_prefills_the_contract(self):
        response = self.client.get(
            reverse('contracts:approval_request_create'),
            {'contract': self.contract.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['form'].initial.get('contract'), self.contract.pk)

    def test_grounded_check_endpoint_still_wired(self):
        Document.objects.create(
            organization=self.organization, title='Review source', document_type=Document.DocType.CONTRACT,
            version=1, contract=self.contract, uploaded_by=self.user,
        )
        response = self.client.get(detail_url(self.contract.pk, 'review'))
        body = page_body(response.content.decode())
        self.assertIn(reverse('contracts:contract_ai_assistant', kwargs={'pk': self.contract.pk}), body)
        self.assertIn('Run review', body)

    def test_manual_grounded_check_persists_freshness_evidence(self):
        response = self.client.post(
            reverse('contracts:contract_ai_assistant', kwargs={'pk': self.contract.pk}),
            data='{"prompt": "check this contract"}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(AuditLog.objects.filter(
            organization=self.organization,
            model_name='Contract',
            object_id=self.contract.pk,
            event_type='contract.grounded_check_completed',
        ).exists())
        detail = self.client.get(detail_url(self.contract.pk))
        self.assertEqual(detail.context['grounded_check']['label'], 'Complete')


class CounterpartyCollaborationTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='External Firm', slug='external-firm')
        self.owner = User.objects.create_user(
            username='external_owner', password='testpass123', email='owner@firm.test',
        )
        OrganizationMembership.objects.create(
            organization=self.organization, user=self.owner,
            role=OrganizationMembership.Role.MEMBER, is_active=True,
        )
        self.contract = Contract.objects.create(
            organization=self.organization, title='External Collaboration Agreement',
            counterparty='Northwind', created_by=self.owner,
        )
        self.client = TestClient()
        self.client.login(username='external_owner', password='testpass123')

    def test_invitation_is_contract_scoped_and_visible_in_record_shell(self):
        response = self.client.post(
            reverse('contracts:counterparty_collaboration_invite', kwargs={'pk': self.contract.pk}),
            {
                'name': 'Taylor Counterparty', 'email': 'taylor@northwind.test',
                'can_view_documents': 'on', 'can_comment': 'on',
            },
        )
        self.assertRedirects(response, reverse('contracts:contract_detail', kwargs={'pk': self.contract.pk}))
        participant = CounterpartyCollaborationParticipant.objects.get(contract=self.contract)
        self.assertEqual(participant.organization, self.organization)
        self.assertTrue(participant.can_view_documents)
        self.assertTrue(participant.can_comment)
        self.assertFalse(participant.can_upload_revisions)
        detail = self.client.get(detail_url(self.contract.pk, 'documents'))
        self.assertContains(detail, 'Counterparty collaboration')
        self.assertContains(detail, participant.email)
        self.assertContains(detail, 'Invite counterparty')
        self.assertTrue(AuditLog.objects.filter(
            organization=self.organization,
            event_type='counterparty_collaboration.invited', object_id=participant.pk,
        ).exists())

    def test_portal_requires_invited_email_then_shows_only_explicitly_shared_documents(self):
        participant = CounterpartyCollaborationParticipant.objects.create(
            organization=self.organization, contract=self.contract, email='taylor@northwind.test',
            can_view_documents=True, can_comment=True,
        )
        shared = Document.objects.create(
            organization=self.organization, contract=self.contract, title='Shared draft',
            share_with_counterparty=True,
        )
        Document.objects.create(
            organization=self.organization, contract=self.contract, title='Internal legal memo',
            share_with_counterparty=False,
        )
        Document.objects.create(
            organization=self.organization, contract=self.contract, title='Privileged negotiation strategy',
            share_with_counterparty=True, is_privileged=True,
        )
        portal_url = reverse('contracts:counterparty_collaboration_portal', kwargs={'token': participant.token})
        access = self.client.get(portal_url)
        self.assertContains(access, 'Confirm your email')
        denied = self.client.post(portal_url, {'email': 'wrong@northwind.test'})
        self.assertEqual(denied.status_code, 403)
        entered = self.client.post(portal_url, {'email': participant.email})
        self.assertRedirects(entered, portal_url)
        portal = self.client.get(portal_url)
        self.assertContains(portal, shared.title)
        self.assertNotContains(portal, 'Internal legal memo')
        self.assertNotContains(portal, 'Privileged negotiation strategy')
        participant.refresh_from_db()
        self.assertEqual(participant.status, CounterpartyCollaborationParticipant.Status.ACTIVE)
        self.assertIsNotNone(participant.accepted_at)

    def test_portal_comment_and_revocation_are_audited_and_revocation_ends_access(self):
        participant = CounterpartyCollaborationParticipant.objects.create(
            organization=self.organization, contract=self.contract, email='taylor@northwind.test',
            can_comment=True,
        )
        portal_url = reverse('contracts:counterparty_collaboration_portal', kwargs={'token': participant.token})
        self.client.post(portal_url, {'email': participant.email})
        comment_response = self.client.post(
            reverse('contracts:counterparty_collaboration_add_comment', kwargs={'token': participant.token}),
            {'content': 'Please clarify the limitation of liability.'},
        )
        self.assertRedirects(comment_response, portal_url)
        item = CounterpartyCollaborationItem.objects.get(contract=self.contract)
        self.assertEqual(item.kind, CounterpartyCollaborationItem.Kind.COMMENT)
        self.assertEqual(item.participant, participant)
        self.assertTrue(AuditLog.objects.filter(
            organization=self.organization,
            event_type='counterparty_collaboration.comment_added',
        ).exists())

        revoke_response = self.client.post(
            reverse('contracts:counterparty_collaboration_revoke', kwargs={
                'pk': self.contract.pk, 'participant_id': participant.pk,
            }),
        )
        self.assertRedirects(revoke_response, reverse('contracts:contract_detail', kwargs={'pk': self.contract.pk}))
        participant.refresh_from_db()
        self.assertEqual(participant.status, CounterpartyCollaborationParticipant.Status.REVOKED)
        self.assertEqual(self.client.get(portal_url).status_code, 404)


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

    def test_documents_surface_shows_empty_state_without_giant_panel(self):
        response = self.client.get(detail_url(self.contract.pk, 'documents'))
        body = page_body(response.content.decode())
        self.assertIn('No document is attached.', body)
        self.assertIn('Attach the source document', body)

    def test_attach_document_is_an_in_page_dialog(self):
        response = self.client.get(detail_url(self.contract.pk, 'documents'))
        body = page_body(response.content.decode())

        self.assertIn('id="contract-attach-dialog"', body)
        self.assertIn('data-open-attach-dialog', body)
        self.assertNotIn(reverse('contracts:document_create'), body)

    def test_attaching_a_document_returns_to_this_contract(self):
        response = self.client.post(
            reverse('contracts:contract_detail', kwargs={'pk': self.contract.pk}),
            {
                'title': 'Attached agreement',
                'document_type': Document.DocType.CONTRACT,
                'file': SimpleUploadedFile('attached-agreement.txt', b'contract text', content_type='text/plain'),
            },
        )

        self.assertRedirects(response, contract_detail_tab_url(self.contract.pk, 'documents'))
        document = Document.objects.get(title='Attached agreement')
        self.assertEqual(document.contract, self.contract)
        self.assertEqual(document.uploaded_by, self.uploader)

    def test_documents_tab_shows_uploaded_document_fields(self):
        Document.objects.create(
            organization=self.organization, title='MSA Final', document_type=Document.DocType.CONTRACT,
            version=2, contract=self.contract, uploaded_by=self.uploader,
        )
        response = self.client.get(detail_url(self.contract.pk, 'documents'))
        body = page_body(response.content.decode())
        self.assertIn('MSA Final', body)
        self.assertIn('Contract Document', body)
        self.assertIn('Version 2', body)
        self.assertIn('Casey', body)

    def test_workspace_uses_tabs_and_document_surface(self):
        Document.objects.create(
            organization=self.organization,
            title='Primary Agreement',
            document_type=Document.DocType.CONTRACT,
            version=1,
            contract=self.contract,
            uploaded_by=self.uploader,
        )
        overview = self.client.get(detail_url(self.contract.pk))
        overview_body = page_body(overview.content.decode())
        self.assertIn('role="tablist"', overview_body)
        self.assertIn('data-workspace-tabs', overview_body)
        self.assertIn('dc-ds-workspace__rail--sticky', overview_body)
        self.assertIn('Contract details', overview_body)
        self.assertIn('Progress', overview_body)
        self.assertNotIn('Quick links', overview_body)
        self.assertNotIn('dc-ds-workspace__metadata-grid', overview_body)
        docs = self.client.get(detail_url(self.contract.pk, 'documents'))
        docs_body = page_body(docs.content.decode())
        self.assertIn('contract-document-hero', docs_body)
        self.assertIn('dc-ds-workspace--record', docs_body)


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
            status=Contract.Status.IN_PROGRESS, created_by=self.creator,
        )

    def test_required_approvals_shows_empty_state_when_nothing_exists(self):
        response = self.client.get(detail_url(self.contract.pk, 'approvals'))
        body = page_body(response.content.decode())
        self.assertIn('Approvals', body)
        self.assertIn('No approvers have been added yet.', body)
        self.assertIn('Add approver', body)

    def test_approval_chain_can_be_reordered(self):
        editor = User.objects.create_user(username='cdetail_wf_editor', password='testpass123')
        reviewer_b = User.objects.create_user(username='cdetail_wf_reviewer_b', password='testpass123')
        reviewer_c = User.objects.create_user(username='cdetail_wf_reviewer_c', password='testpass123')
        OrganizationMembership.objects.create(organization=self.organization, user=editor, role=OrganizationMembership.Role.OWNER, is_active=True)
        OrganizationMembership.objects.create(organization=self.organization, user=reviewer_b, role=OrganizationMembership.Role.MEMBER, is_active=True)
        OrganizationMembership.objects.create(organization=self.organization, user=reviewer_c, role=OrganizationMembership.Role.MEMBER, is_active=True)
        approval_a = ApprovalRequest.objects.create(
            organization=self.organization, contract=self.contract, approval_step='LEGAL',
            status=ApprovalRequest.Status.PENDING, assigned_to=self.assignee, sort_order=10,
        )
        approval_b = ApprovalRequest.objects.create(
            organization=self.organization, contract=self.contract, approval_step='FINANCE',
            status=ApprovalRequest.Status.PENDING, assigned_to=reviewer_b, sort_order=20,
        )
        approval_c = ApprovalRequest.objects.create(
            organization=self.organization, contract=self.contract, approval_step='EXECUTIVE',
            status=ApprovalRequest.Status.PENDING, assigned_to=reviewer_c, sort_order=30,
        )

        editor_client = TestClient()
        self.assertTrue(editor_client.login(username='cdetail_wf_editor', password='testpass123'))

        response = editor_client.post(
            reverse('contracts:contract_approval_chain_reorder', kwargs={'pk': self.contract.pk, 'approval_id': approval_c.pk}),
            {'direction': 'up'},
        )
        self.assertRedirects(response, reverse('contracts:contract_detail', kwargs={'pk': self.contract.pk}))
        ordered_steps = list(
            ApprovalRequest.objects.filter(contract=self.contract).order_by('sort_order', 'created_at', 'pk').values_list('approval_step', flat=True)
        )
        self.assertEqual(ordered_steps, ['LEGAL', 'EXECUTIVE', 'FINANCE'])
        self.assertEqual(ApprovalRequest.objects.get(pk=approval_c.pk).sort_order, 20)

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
        approvals = self.client.get(detail_url(self.contract.pk, 'approvals'))
        approvals_body = page_body(approvals.content.decode())
        self.assertIn('Legal Review', approvals_body)
        self.assertIn('Jordan', approvals_body)
        overview = self.client.get(detail_url(self.contract.pk))
        overview_body = page_body(overview.content.decode())
        self.assertIn('Alex Signer', overview_body)
        self.assertIn('Review indemnification', overview_body)


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
        response = self.client.get(detail_url(self.contract.pk, 'activity'))
        body = page_body(response.content.decode())
        self.assertIn('No internal activity recorded for this contract.', body)

    def test_activity_tab_shows_human_readable_entry(self):
        log_action(
            self.user, 'UPDATE', 'Contract', self.contract.id, str(self.contract),
            changes={'event': 'contract_updated'}, organization=self.organization,
        )
        response = self.client.get(detail_url(self.contract.pk, 'activity'))
        body = page_body(response.content.decode())
        self.assertIn('Sam', body)
        self.assertNotIn('UPDATE', body)
        self.assertIsNone(ISO_TIMESTAMP_RE.search(body), 'Found a raw ISO timestamp in the Contract Detail response')

    def test_activity_tab_unifies_audit_log_and_internal_notes(self):
        NegotiationThread.objects.create(
            contract=self.contract,
            title='Redline note',
            content='Keep this internal and merge into the same feed.',
            created_by=self.user,
        )
        log_action(
            self.user, 'UPDATE', 'Contract', self.contract.id, str(self.contract),
            changes={'event': 'contract_updated'}, organization=self.organization,
        )
        response = self.client.get(detail_url(self.contract.pk, 'activity'))
        body = page_body(response.content.decode())
        self.assertIn('Audit trail', body)
        self.assertIn('Redline note', body)
        self.assertIn('Internal note', body)
        self.assertIn('Audit', body)


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
            status=Contract.Status.IN_PROGRESS, lifecycle_stage='INTERNAL_REVIEW', created_by=self.user,
        )
        RiskLog.objects.create(title='Risk', description='d', contract=contract, status=RiskLog.Status.IN_PROGRESS, created_by=self.user)
        response = self.client.get(reverse('contracts:contract_detail', kwargs={'pk': contract.pk}))
        body = page_body(response.content.decode())

        self.assertNotIn('Contract object', body)
        self.assertNotIn('IN_PROGRESS', body)
        self.assertIn('In progress', body)
        self.assertNotIn('INTERNAL_REVIEW', body)
        self.assertIn('Internal review', body)
        self.assertNotIn('In opvolging', body)
        self.assertIsNone(ISO_TIMESTAMP_RE.search(body), 'Found a raw ISO timestamp in the Contract Detail response')


class ContractDetailStateConsistencyTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='State Firm', slug='cdetail-state-firm')
        self.user = User.objects.create_user(username='cdetail_state_user', password='testpass123')
        OrganizationMembership.objects.create(organization=self.organization, user=self.user, role=OrganizationMembership.Role.MEMBER, is_active=True)
        self.client = TestClient()
        self.client.login(username='cdetail_state_user', password='testpass123')
        self.contract = Contract.objects.create(
            organization=self.organization, title='State Contract', content='Seed',
            status=Contract.Status.IN_PROGRESS,
            lifecycle_stage=Contract.LifecycleStage.SIGNATURE,
            risk_level=Contract.RiskLevel.LOW, created_by=self.user,
        )

    def test_open_high_risk_overrides_low_record_badge_and_blocks_signature(self):
        Document.objects.create(
            organization=self.organization, title='State source', document_type=Document.DocType.CONTRACT,
            version=1, contract=self.contract, uploaded_by=self.user,
        )
        RiskLog.objects.create(
            title='Unresolved indemnity exposure', description='d', contract=self.contract,
            risk_level=RiskLog.RiskLevel.HIGH, status=RiskLog.Status.OPEN, created_by=self.user,
        )
        response = self.client.get(detail_url(self.contract.pk))
        body = page_body(response.content.decode())
        self.assertIn('Resolve blockers', body)
        self.assertIn('Unresolved indemnity exposure', body)
        self.assertNotIn('Signature requirement', body)
        workflow = self.client.get(detail_url(self.contract.pk, 'workflow'))
        workflow_body = page_body(workflow.content.decode())
        self.assertIn('Signature requirement', workflow_body)
        self.assertIn('At least one approval is required before signature routing.', workflow_body)
        risks = self.client.get(detail_url(self.contract.pk, 'risks'))
        risks_body = page_body(risks.content.decode())
        self.assertIn('Unresolved indemnity exposure', risks_body)


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
        response = client.get(detail_url(self.contract_a.pk))
        self.assertEqual(response.status_code, 404)


class ContractDetailWorkspaceGatingTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Gate Firm', slug='cdetail-gate-firm')
        self.owner = User.objects.create_user(username='cdetail_gate_owner', password='testpass123')
        self.reviewer = User.objects.create_user(username='cdetail_gate_reviewer', password='testpass123')
        OrganizationMembership.objects.create(organization=self.organization, user=self.owner, role=OrganizationMembership.Role.MEMBER, is_active=True)
        OrganizationMembership.objects.create(organization=self.organization, user=self.reviewer, role=OrganizationMembership.Role.MEMBER, is_active=True)
        self.client = TestClient()
        self.client.login(username='cdetail_gate_owner', password='testpass123')
        self.contract = Contract.objects.create(
            organization=self.organization, title='Gate Contract', content='Seed',
            status=Contract.Status.IN_PROGRESS, created_by=self.owner, owner=self.owner,
        )

    def test_submit_post_rejected_without_document_and_review(self):
        response = self.client.post(
            reverse('contracts:contract_submit_for_review', kwargs={'pk': self.contract.pk}),
            {'reviewer_id': self.reviewer.pk, 'comment': 'Please review'},
        )
        self.assertRedirects(response, contract_detail_tab_url(self.contract.pk, 'approvals'))
        self.assertFalse(ApprovalRequest.objects.filter(contract=self.contract).exists())
        follow = self.client.get(contract_detail_tab_url(self.contract.pk, 'approvals'))
        body = page_body(follow.content.decode())
        self.assertIn('Attach a source document', body)

    def test_submit_form_appears_only_when_review_is_complete(self):
        Document.objects.create(
            organization=self.organization, title='Gate source', document_type=Document.DocType.CONTRACT,
            version=1, contract=self.contract, uploaded_by=self.owner,
        )
        blocked = self.client.get(detail_url(self.contract.pk, 'approvals'))
        blocked_body = page_body(blocked.content.decode())
        self.assertNotIn('id="contract-submit-review-form"', blocked_body)
        self.assertIn('Run contract review.', blocked_body)

        self.client.post(
            reverse('contracts:contract_ai_assistant', kwargs={'pk': self.contract.pk}),
            data='{"prompt": "ready"}',
            content_type='application/json',
        )
        ready = self.client.get(detail_url(self.contract.pk, 'approvals'))
        ready_body = page_body(ready.content.decode())
        self.assertIn('id="contract-submit-review-form"', ready_body)
        overview = self.client.get(detail_url(self.contract.pk))
        self.assertEqual(overview.context['contract_command']['primary_action']['label'], 'Submit for review')


class ContractDetailTabRoutingTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Tab Firm', slug='cdetail-tab-firm')
        self.user = User.objects.create_user(username='cdetail_tab_user', password='testpass123')
        OrganizationMembership.objects.create(organization=self.organization, user=self.user, role=OrganizationMembership.Role.MEMBER, is_active=True)
        self.client = TestClient()
        self.client.login(username='cdetail_tab_user', password='testpass123')
        self.contract = Contract.objects.create(
            organization=self.organization, title='Tab Contract', content='Seed',
            status=Contract.Status.IN_PROGRESS, created_by=self.user,
        )

    def test_each_tab_renders_its_panel(self):
        expectations = {
            'overview': ('overview', 'Contract details'),
            'documents': ('documents', 'Documents &amp; versions'),
            'workflow': ('workflow', 'Review findings'),
            'risks': ('risks', 'Risks'),
            'obligations': ('obligations', 'Obligations'),
            'activity': ('activity', 'Audit trail'),
        }
        for tab, (active, heading) in expectations.items():
            response = self.client.get(detail_url(self.contract.pk, tab))
            body = page_body(response.content.decode())
            self.assertEqual(response.context['active_tab'], active)
            self.assertIn(heading, body)
            self.assertIn(f'id="contract-tab-{active}"', body)

    def test_legacy_review_and_approvals_tabs_alias_to_workflow(self):
        for legacy, section in (('review', 'review'), ('approvals', 'approvals')):
            response = self.client.get(detail_url(self.contract.pk, legacy))
            body = page_body(response.content.decode())
            self.assertEqual(response.context['active_tab'], 'workflow')
            self.assertEqual(response.context['workflow_section'], section)
            self.assertIn('id="contract-tab-workflow"', body)

    def test_invalid_tab_falls_back_to_overview(self):
        response = self.client.get(detail_url(self.contract.pk) + '?tab=not-a-tab')
        self.assertEqual(response.context['active_tab'], 'overview')
        body = page_body(response.content.decode())
        self.assertIn('id="contract-tab-overview"', body)


class ContractDetailTerminologyAndBlockerTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Term Firm', slug='cdetail-term-firm')
        self.user = User.objects.create_user(username='cdetail_term_user', password='testpass123')
        OrganizationMembership.objects.create(organization=self.organization, user=self.user, role=OrganizationMembership.Role.MEMBER, is_active=True)
        self.client = TestClient()
        self.client.login(username='cdetail_term_user', password='testpass123')
        self.contract = Contract.objects.create(
            organization=self.organization, title='Term Contract', content='Seed',
            status=Contract.Status.IN_PROGRESS, created_by=self.user,
        )

    def test_contract_review_terminology_and_legacy_labels_absent(self):
        Document.objects.create(
            organization=self.organization, title='Term source', document_type=Document.DocType.CONTRACT,
            version=1, contract=self.contract, uploaded_by=self.user,
        )
        response = self.client.get(detail_url(self.contract.pk, 'review'))
        body = page_body(response.content.decode())
        self.assertIn('Review findings', body)
        self.assertIn('Not started', body)
        self.assertIn('Run review', body)
        for legacy in LEGACY_REVIEW_LABELS:
            self.assertNotIn(legacy, body)

    def test_signature_blockers_live_under_later_while_attach_is_next(self):
        response = self.client.get(detail_url(self.contract.pk))
        body = page_body(response.content.decode())
        self.assertIn('Attach source document', body)
        self.assertIn('Action required', body)
        self.assertIn('contract-action-card', body)
        self.assertIn('Contract lifecycle', body)
        self.assertNotIn('View full workflow', body)
        self.assertNotIn('Signature requirement', body)
        self.assertEqual(response.context['contract_command']['primary_action']['label'], 'Attach source document')
        self.assertEqual(response.context['contract_command']['lifecycle_label'], 'In progress · Drafting')
        self.assertTrue(any('approval' in item.lower() for item in response.context['later_workflow_requirements']))
        self.assertNotIn('contract-action-summary', body)
        self.assertIn('dc-ds-workspace__rail--sticky', body)
        workflow = self.client.get(detail_url(self.contract.pk, 'workflow'))
        workflow_body = page_body(workflow.content.decode())
        self.assertIn('Signature requirement', workflow_body)
        self.assertTrue(
            'signature' in workflow_body.casefold() and 'approv' in workflow_body.casefold(),
            'Expected signature/approval routing guidance on the workflow tab',
        )
        self.assertIn('Upcoming milestone', workflow_body)

    def test_duplicate_state_labels_removed_from_header_and_overview(self):
        response = self.client.get(detail_url(self.contract.pk))
        body = page_body(response.content.decode())
        self.assertNotIn('dc-ds-workspace__metadata-grid', body)
        self.assertNotIn('>Lifecycle</dt>', body)
        self.assertNotIn('Workflow checklist', body)
        self.assertIn('dc-ds-workspace__rail--sticky', body)
        self.assertIn('>Status</dt>', body)
        self.assertIn('>Stage</dt>', body)
        self.assertNotIn('Quick links', body)
        self.assertIn('data-workspace-tabs', body)
        self.assertIn('contract-overview-grid', body)
        self.assertIn('contract-progress-track', body)
        self.assertNotIn('View full workflow', body)
        # Stage/next/blocking meta removed from overview lifecycle card (redundant with track + Action required).
        self.assertNotIn('<dt>Current stage</dt>', body)
        self.assertNotIn('<dt>Next step</dt>', body)
        self.assertNotIn('<dt>Blocking item</dt>', body)
        self.assertIn('Upcoming milestone', body)
        self.assertNotIn('>Next milestone</dt>', body)
        css = open('theme/static_src/src/global-shell/workspaces.css').read()
        self.assertIn('--page-max-width', css)
        self.assertIn('dc-ds-workspace__rail--sticky', css)
        self.assertIn('contract-action-card', css)
        self.assertIn('contract-progress-track', css)
        self.assertIn('font: var(--text-heading)', css)
        self.assertIn('gap: var(--space-24)', css)


class ContractDetailLifecycleCommandLabelTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Lifecycle Firm', slug='cdetail-lifecycle-firm')
        self.user = User.objects.create_user(username='cdetail_lifecycle_user', password='testpass123')
        OrganizationMembership.objects.create(
            organization=self.organization, user=self.user, role=OrganizationMembership.Role.MEMBER, is_active=True,
        )
        self.client = TestClient()
        self.client.login(username='cdetail_lifecycle_user', password='testpass123')

    def test_in_progress_without_document_uses_pdr_status_stage_label(self):
        contract = Contract.objects.create(
            organization=self.organization, title='Intake Contract', content='Seed',
            status=Contract.Status.IN_PROGRESS, created_by=self.user,
        )
        response = self.client.get(detail_url(contract.pk))
        body = page_body(response.content.decode())
        self.assertIn('In progress', body)
        self.assertEqual(response.context['contract_command']['lifecycle_label'], 'In progress · Drafting')
        self.assertIn('Action required', body)

    def test_approved_obligation_tracking_shows_active_label(self):
        contract = Contract.objects.create(
            organization=self.organization, title='Active Obligation Contract', content='Seed',
            status=Contract.Status.ACTIVE, lifecycle_stage=Contract.LifecycleStage.OBLIGATION_TRACKING, created_by=self.user,
        )
        Document.objects.create(
            organization=self.organization, title='Executed source', document_type=Document.DocType.CONTRACT,
            version=1, contract=contract, uploaded_by=self.user,
        )
        response = self.client.get(detail_url(contract.pk))
        body = page_body(response.content.decode())
        self.assertIn('Active', body)
        self.assertIn('Obligation tracking', body)
        self.assertEqual(response.context['contract_command']['lifecycle_label'], 'Active · Obligation tracking')
        self.assertIn('Progress', body)

class ContractDetailActivityDetailTests(TestCase):
    def test_audit_detail_names_changed_fields(self):
        from contracts.services.contract_detail_workspace import format_contract_audit_activity_detail

        detail = format_contract_audit_activity_detail({
            'status': {'before': 'IN_PROGRESS', 'after': 'ACTIVE'},
            'counterparty': {'before': '', 'after': 'Acme'},
        })
        self.assertIn('Status changed from IN_PROGRESS to ACTIVE', detail)
        self.assertIn('Counterparty changed from — to Acme', detail)

    def test_audit_detail_names_workflow_and_document_events(self):
        from contracts.services.contract_detail_workspace import format_contract_audit_activity_detail

        self.assertEqual(
            format_contract_audit_activity_detail({'event': 'contract.approval_chain_reordered'}),
            'Approval chain order updated.',
        )
        self.assertIn(
            'Document affected',
            format_contract_audit_activity_detail({'document_title': 'MSA v2'}),
        )
        self.assertIn(
            'Decision recorded',
            format_contract_audit_activity_detail({'decision': 'approve'}),
        )
