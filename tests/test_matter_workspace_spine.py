"""Phase 3 of the Product Coherence Redesign: Matter Workspace Spine.

Strengthens the existing Matter detail page into the central workspace for
a Payrollminds engagement — linked contracts, DPA review packs, risks,
approvals, deadlines/obligations, documents, and review memos — for
in_house_clm tenants, while preserving law_firm_ops behavior untouched.

Covers: section presence/empty-states, org scoping, no DPA analysis or
approval mutation at render time, query-count guardrail, and that every
link resolves to a pre-existing route (no new routes added).
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client as TestClient
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from contracts.models import (
    ApprovalRequest,
    Client as ClientModel,
    Contract,
    Counterparty,
    Deadline,
    Document,
    DPAReviewPack,
    DPARiskItem,
    Matter,
    Organization,
    OrganizationMembership,
    RiskLog,
)

User = get_user_model()


def _today():
    return timezone.now().date()


class _MatterFixtureMixin:
    def _make_org(self, workspace_mode=None):
        kwargs = {}
        if workspace_mode:
            kwargs['workspace_mode'] = workspace_mode
        return Organization.objects.create(
            name=f'Org {workspace_mode or "default"} {id(self)}',
            slug=f'org-{workspace_mode or "default"}-{id(self)}',
            **kwargs,
        )

    def _make_matter(self, org, user, title='Acme Engagement', number='M-001'):
        client_obj = ClientModel.objects.create(organization=org, name='Acme Client', created_by=user)
        return Matter.objects.create(
            organization=org, matter_number=number, title=title,
            client=client_obj, created_by=user,
        )


class MatterWorkspaceFramingTests(_MatterFixtureMixin, TestCase):
    """in_house_clm matter detail shows the legal-control spine sections."""

    def setUp(self):
        self.org = self._make_org('in_house_clm')
        self.user = User.objects.create_user(username='clm_matter_user', password='testpass123!')
        OrganizationMembership.objects.create(
            organization=self.org, user=self.user, role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        self.client_ = TestClient()
        self.client_.login(username='clm_matter_user', password='testpass123!')
        self.matter = self._make_matter(self.org, self.user)

    def _get(self):
        return self.client_.get(reverse('contracts:matter_detail', kwargs={'pk': self.matter.pk}))

    def test_overview_header_present(self):
        response = self._get()
        self.assertContains(response, 'Open Risks')
        self.assertContains(response, 'Open Approvals')
        self.assertContains(response, 'Upcoming Deadlines')
        self.assertContains(response, 'Last Activity')
        self.assertContains(response, self.matter.title)
        self.assertContains(response, self.matter.matter_number)

    def test_section_headings_present(self):
        response = self._get()
        for heading in (
            'Linked Contracts', 'DPA Review Packs', 'Risks', 'Approvals',
            'Deadlines &amp; Obligations', 'Documents', 'Review Memos',
        ):
            self.assertContains(response, heading)

    def test_empty_states_render_with_no_linked_data(self):
        response = self._get()
        self.assertContains(response, 'No contracts linked to this matter yet.')
        self.assertContains(response, 'No DPA review packs linked to this matter yet.')
        self.assertContains(response, 'No open risks for this matter.')
        self.assertContains(response, 'No open approvals for this matter.')
        self.assertContains(response, 'No documents linked to this matter yet.')
        self.assertContains(response, 'No review memos generated yet.')


class MatterWorkspaceDataTests(_MatterFixtureMixin, TestCase):
    """Every section reflects persisted, organization-scoped rows."""

    def setUp(self):
        self.org = self._make_org('in_house_clm')
        self.other_org = self._make_org(None)

        self.user = User.objects.create_user(username='clm_wsdata_user', password='testpass123!')
        OrganizationMembership.objects.create(
            organization=self.org, user=self.user, role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        self.client_ = TestClient()
        self.client_.login(username='clm_wsdata_user', password='testpass123!')

        self.matter = self._make_matter(self.org, self.user)
        self.other_matter = self._make_matter(self.other_org, self.user, title='Other Org Engagement', number='M-999')

        self.counterparty = Counterparty.objects.create(organization=self.org, name='Acme Corp')
        self.msa = Contract.objects.create(
            organization=self.org, title='Acme MSA', content='x', status='ACTIVE',
            contract_type='MSA', counterparty='Acme Corp', matter=self.matter, created_by=self.user,
        )
        self.dpa = Contract.objects.create(
            organization=self.org, title='Acme DPA', content='x', status='ACTIVE',
            contract_type='DPA', counterparty='Acme Corp', matter=self.matter, created_by=self.user,
        )

    def _get(self):
        return self.client_.get(reverse('contracts:matter_detail', kwargs={'pk': self.matter.pk}))

    def test_linked_contracts_shown(self):
        response = self._get()
        self.assertContains(response, 'Acme MSA')
        self.assertContains(response, 'Acme DPA')

    def test_linked_dpa_review_packs_shown(self):
        review_pack = DPAReviewPack.objects.create(
            organization=self.org, contract=self.dpa, counterparty=self.counterparty, matter=self.matter,
        )
        review_pack.related_contracts.add(self.msa)
        response = self._get()
        self.assertContains(response, 'Acme DPA')
        self.assertContains(response, reverse('contracts:dpa_review_pack_detail', kwargs={'pk': review_pack.pk}))

    def test_dpa_cross_document_conflict_and_risk_counts_shown(self):
        review_pack = DPAReviewPack.objects.create(
            organization=self.org, contract=self.dpa, counterparty=self.counterparty, matter=self.matter,
        )
        review_pack.related_contracts.add(self.msa)
        DPARiskItem.objects.create(
            review_pack=review_pack, category='LIABILITY', title='DPA liability overrides MSA cap',
            description='...', severity='HIGH', owners='LEGAL', is_cross_document_conflict=True,
            status='OPEN', detection_rule='dpa_liability_vs_msa_cap', conflict_type='dpa_liability_vs_msa_cap',
        )
        DPARiskItem.objects.create(
            review_pack=review_pack, category='SECURITY', title='Resolved finding',
            description='...', severity='HIGH', owners='LEGAL', is_cross_document_conflict=True,
            status='RESOLVED',
        )
        response = self._get()
        content = response.content.decode()
        idx = content.index('Acme DPA', content.index('DPA Review Packs'))
        window = content[idx:idx + 600]
        self.assertIn('1 high/critical risk', window)
        self.assertIn('1 cross-doc conflict', window)

    def test_open_risklog_items_shown(self):
        RiskLog.objects.create(
            contract=self.msa, matter=self.matter, title='High commercial risk',
            description='...', risk_level='HIGH', status='OPEN',
        )
        RiskLog.objects.create(
            contract=self.msa, matter=self.matter, title='Resolved risk',
            description='...', risk_level='HIGH', status='RESOLVED',
        )
        response = self._get()
        self.assertContains(response, 'High commercial risk')
        self.assertNotContains(response, 'Resolved risk')

    def test_dpa_risk_items_appear_in_unified_risk_section(self):
        review_pack = DPAReviewPack.objects.create(
            organization=self.org, contract=self.dpa, counterparty=self.counterparty, matter=self.matter,
        )
        DPARiskItem.objects.create(
            review_pack=review_pack, category='TRANSFER', title='Non-EEA transfer, no mechanism',
            description='...', severity='CRITICAL', owners='DPO_SECURITY',
            is_cross_document_conflict=False, status='OPEN',
        )
        response = self._get()
        self.assertContains(response, 'Non-EEA transfer, no mechanism')
        self.assertContains(response, 'DPA Risk')

    def test_approvals_shown_via_linked_contract(self):
        approval = ApprovalRequest.objects.create(
            organization=self.org, contract=self.msa, approval_step='Legal',
            status='PENDING', assigned_to=self.user,
        )
        response = self._get()
        self.assertContains(response, reverse('contracts:approval_request_update', kwargs={'pk': approval.pk}))

    def test_deadlines_obligation_stopgap_shown(self):
        deadline = Deadline.objects.create(
            matter=self.matter, title='DSAR window', due_date=_today() + timedelta(days=10), is_completed=False,
        )
        response = self._get()
        self.assertContains(response, 'DSAR window')
        self.assertContains(response, reverse('contracts:deadline_update', kwargs={'pk': deadline.pk}))

    def test_documents_shown(self):
        Document.objects.create(
            organization=self.org, title='Signed MSA PDF', document_type='CONTRACT',
            status='FINAL', matter=self.matter, uploaded_by=self.user,
        )
        response = self._get()
        self.assertContains(response, 'Signed MSA PDF')

    def test_soft_deleted_documents_excluded(self):
        Document.objects.create(
            organization=self.org, title='Deleted Doc', document_type='CONTRACT',
            status='FINAL', matter=self.matter, uploaded_by=self.user, is_deleted=True,
        )
        response = self._get()
        self.assertNotContains(response, 'Deleted Doc')

    def test_review_memo_link_shown_when_memo_exists(self):
        review_pack = DPAReviewPack.objects.create(
            organization=self.org, contract=self.dpa, counterparty=self.counterparty, matter=self.matter,
            review_memo='Memo body', review_memo_generated_at=timezone.now(),
        )
        response = self._get()
        self.assertContains(response, reverse('contracts:dpa_review_pack_memo', kwargs={'pk': review_pack.pk}))

    def test_other_org_matter_not_reachable(self):
        response = self.client_.get(reverse('contracts:matter_detail', kwargs={'pk': self.other_matter.pk}))
        self.assertEqual(response.status_code, 404)

    def test_other_org_contract_not_shown(self):
        other_contract = Contract.objects.create(
            organization=self.other_org, title='Other Org Contract', content='x',
            status='ACTIVE', matter=self.other_matter, created_by=self.user,
        )
        response = self._get()
        self.assertNotContains(response, 'Other Org Contract')
        self.assertNotIn(other_contract.pk, [c.pk for c in response.context['clm_contracts']])


class LawFirmOpsMatterPreservedTests(_MatterFixtureMixin, TestCase):
    """law_firm_ops preserves prior matter detail
    behavior — billing/time-entry sections must not disappear."""

    def setUp(self):
        self.org = self._make_org('law_firm_ops')
        self.user = User.objects.create_user(username='firm_matter_user', password='testpass123!')
        OrganizationMembership.objects.create(
            organization=self.org, user=self.user, role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        self.client_ = TestClient()
        self.client_.login(username='firm_matter_user', password='testpass123!')
        self.matter = self._make_matter(self.org, self.user)

    def _get(self):
        return self.client_.get(reverse('contracts:matter_detail', kwargs={'pk': self.matter.pk}))

    def test_billing_and_time_entry_sections_preserved(self):
        response = self._get()
        self.assertContains(response, 'Billing Summary')
        self.assertContains(response, 'Recent Time Entries')
        self.assertContains(response, 'Details')
        self.assertContains(response, 'Team')

    def test_clm_only_sections_absent(self):
        response = self._get()
        content = response.content.decode()
        for forbidden in ('Linked Contracts', 'DPA Review Packs', 'Open Approvals', 'Review Memos'):
            self.assertNotIn(forbidden, content)

    def test_deadlines_panel_still_present(self):
        deadline = Deadline.objects.create(
            matter=self.matter, title='Old-style deadline', due_date=_today() + timedelta(days=5),
            is_completed=False,
        )
        response = self._get()
        self.assertContains(response, 'Old-style deadline')
        self.assertNotContains(response, reverse('contracts:deadline_update', kwargs={'pk': deadline.pk}))


class MatterWorkspaceNoMutationTests(_MatterFixtureMixin, TestCase):
    """Rendering the matter workspace must never run DPA analysis/conflict
    detection or change approval/DPA status."""

    def setUp(self):
        self.org = self._make_org('in_house_clm')
        self.user = User.objects.create_user(username='clm_nomutate_user', password='testpass123!')
        OrganizationMembership.objects.create(
            organization=self.org, user=self.user, role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        self.client_ = TestClient()
        self.client_.login(username='clm_nomutate_user', password='testpass123!')
        self.matter = self._make_matter(self.org, self.user)
        self.counterparty = Counterparty.objects.create(organization=self.org, name='Acme Corp')
        self.msa = Contract.objects.create(
            organization=self.org, title='Acme MSA', content='x', status='ACTIVE',
            matter=self.matter, created_by=self.user,
        )
        self.dpa = Contract.objects.create(
            organization=self.org, title='Acme DPA', content='x', status='ACTIVE',
            matter=self.matter, created_by=self.user,
        )
        self.review_pack = DPAReviewPack.objects.create(
            organization=self.org, contract=self.dpa, counterparty=self.counterparty, matter=self.matter,
        )

    def _get(self):
        return self.client_.get(reverse('contracts:matter_detail', kwargs={'pk': self.matter.pk}))

    def test_does_not_call_conflict_detection(self):
        import contracts.services.dpa_conflict as dpa_conflict

        def _boom(*args, **kwargs):
            raise AssertionError('Matter detail must not call check_cross_document_conflicts')

        original = dpa_conflict.check_cross_document_conflicts
        dpa_conflict.check_cross_document_conflicts = _boom
        try:
            response = self._get()
            self.assertEqual(response.status_code, 200)
        finally:
            dpa_conflict.check_cross_document_conflicts = original

    def test_does_not_call_dpa_analysis(self):
        import contracts.services.dpa_review as dpa_review

        def _boom(*args, **kwargs):
            raise AssertionError('Matter detail must not call run_dpa_analysis')

        original = dpa_review.run_dpa_analysis
        dpa_review.run_dpa_analysis = _boom
        try:
            response = self._get()
            self.assertEqual(response.status_code, 200)
        finally:
            dpa_review.run_dpa_analysis = original

    def test_does_not_change_dpa_approval_status(self):
        before = self.review_pack.approval_status
        self._get()
        self.review_pack.refresh_from_db()
        self.assertEqual(self.review_pack.approval_status, before)

    def test_does_not_change_approval_request_status(self):
        approval = ApprovalRequest.objects.create(
            organization=self.org, contract=self.msa, approval_step='Legal',
            status='PENDING', assigned_to=self.user,
        )
        self._get()
        approval.refresh_from_db()
        self.assertEqual(approval.status, 'PENDING')


class MatterWorkspaceRouteAndLinkTests(_MatterFixtureMixin, TestCase):
    """Every link the workspace renders resolves to a pre-existing route —
    Phase 3 adds zero new routes."""

    def setUp(self):
        self.org = self._make_org('in_house_clm')
        self.user = User.objects.create_user(username='clm_route_user', password='testpass123!')
        OrganizationMembership.objects.create(
            organization=self.org, user=self.user, role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        self.client_ = TestClient()
        self.client_.login(username='clm_route_user', password='testpass123!')
        self.matter = self._make_matter(self.org, self.user)
        self.counterparty = Counterparty.objects.create(organization=self.org, name='Acme Corp')
        self.msa = Contract.objects.create(
            organization=self.org, title='Acme MSA', content='x', status='ACTIVE',
            matter=self.matter, created_by=self.user,
        )
        self.dpa = Contract.objects.create(
            organization=self.org, title='Acme DPA', content='x', status='ACTIVE',
            matter=self.matter, created_by=self.user,
        )
        self.review_pack = DPAReviewPack.objects.create(
            organization=self.org, contract=self.dpa, counterparty=self.counterparty, matter=self.matter,
            review_memo='Memo body', review_memo_generated_at=timezone.now(),
        )
        self.risk = RiskLog.objects.create(
            contract=self.msa, matter=self.matter, title='High commercial risk',
            description='...', risk_level='HIGH', status='OPEN',
        )
        self.approval = ApprovalRequest.objects.create(
            organization=self.org, contract=self.msa, approval_step='Legal',
            status='PENDING', assigned_to=self.user,
        )
        self.deadline = Deadline.objects.create(
            matter=self.matter, title='DSAR window', due_date=_today() + timedelta(days=10), is_completed=False,
        )
        self.document = Document.objects.create(
            organization=self.org, title='Signed MSA PDF', document_type='CONTRACT',
            status='FINAL', matter=self.matter, uploaded_by=self.user,
        )

    def test_no_new_routes_needed(self):
        for name, kwargs in [
            ('contracts:matter_detail', {'pk': self.matter.pk}),
            ('contracts:contract_detail', {'pk': self.msa.pk}),
            ('contracts:dpa_review_pack_detail', {'pk': self.review_pack.pk}),
            ('contracts:dpa_review_pack_memo', {'pk': self.review_pack.pk}),
            ('contracts:risk_log_update', {'pk': self.risk.pk}),
            ('contracts:approval_request_update', {'pk': self.approval.pk}),
            ('contracts:deadline_update', {'pk': self.deadline.pk}),
            ('contracts:document_detail', {'pk': self.document.pk}),
        ]:
            reverse(name, kwargs=kwargs)

    def test_rendered_links_are_reachable(self):
        response = self.client_.get(reverse('contracts:matter_detail', kwargs={'pk': self.matter.pk}))
        for name, kwargs in [
            ('contracts:contract_detail', {'pk': self.msa.pk}),
            ('contracts:dpa_review_pack_detail', {'pk': self.review_pack.pk}),
            ('contracts:document_detail', {'pk': self.document.pk}),
        ]:
            self.assertContains(response, reverse(name, kwargs=kwargs))
            self.assertEqual(self.client_.get(reverse(name, kwargs=kwargs)).status_code, 200)


class MatterWorkspaceQueryCountTests(_MatterFixtureMixin, TestCase):
    """Query-count protection matching the Phase 2 dashboard pattern: more
    linked rows must not scale query count linearly (no N+1)."""

    def setUp(self):
        self.org = self._make_org('in_house_clm')
        self.user = User.objects.create_user(username='clm_perf_matter_user', password='testpass123!')
        OrganizationMembership.objects.create(
            organization=self.org, user=self.user, role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        self.client_ = TestClient()
        self.client_.login(username='clm_perf_matter_user', password='testpass123!')
        self.matter = self._make_matter(self.org, self.user)
        self.counterparty = Counterparty.objects.create(organization=self.org, name='Perf Counterparty')

    def _seed(self, count):
        for idx in range(count):
            contract = Contract.objects.create(
                organization=self.org, title=f'Perf Contract {idx}', content='x',
                status='ACTIVE', matter=self.matter, created_by=self.user,
            )
            pack = DPAReviewPack.objects.create(
                organization=self.org, contract=contract, counterparty=self.counterparty, matter=self.matter,
            )
            DPARiskItem.objects.create(
                review_pack=pack, category='LIABILITY', title=f'Conflict {idx}',
                description='...', severity='HIGH', owners='LEGAL',
                is_cross_document_conflict=True, status='OPEN',
            )
            RiskLog.objects.create(
                contract=contract, matter=self.matter, title=f'Risk {idx}',
                description='...', risk_level='HIGH', status='OPEN',
            )
            ApprovalRequest.objects.create(
                organization=self.org, contract=contract, approval_step='Legal',
                status='PENDING', assigned_to=self.user,
            )
            Deadline.objects.create(
                contract=contract, matter=self.matter, title=f'Deadline {idx}',
                due_date=_today() + timedelta(days=idx + 1), is_completed=False,
            )
            Document.objects.create(
                organization=self.org, title=f'Doc {idx}', document_type='CONTRACT',
                status='FINAL', matter=self.matter, uploaded_by=self.user,
            )

    def _query_count_for_matter_detail(self):
        with CaptureQueriesContext(connection) as ctx:
            response = self.client_.get(reverse('contracts:matter_detail', kwargs={'pk': self.matter.pk}))
        self.assertEqual(response.status_code, 200)
        return len(ctx)

    def test_matter_detail_query_count_does_not_scale_linearly(self):
        self._seed(3)
        baseline = self._query_count_for_matter_detail()

        self._seed(25)
        expanded = self._query_count_for_matter_detail()

        self.assertLessEqual(expanded, baseline + 8)
