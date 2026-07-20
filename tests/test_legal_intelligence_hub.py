"""Phase 4 of the Product Coherence Redesign: Legal Intelligence Hub.

Cross-matter Risk Review for in_house_clm tenants — normalizes RiskLog,
DPARiskItem (including DPA cross-document conflicts), pending/blocking
ApprovalRequest items, and upcoming/overdue Deadlines into one consistent
signal list via contracts/services/legal_signals.py. Reuses the existing
`contracts:risk_log_list` route — law_firm_ops keeps the original Risk
Register unchanged.

Covers: section/KPI/tab presence, per-source signal surfacing, filter tabs,
source-link resolution, law_firm_ops preservation, no DPA analysis/mutation
at render time, org scoping, query-count guardrail, and empty state.
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


class _HubFixtureMixin:
    def _make_org(self, workspace_mode=None):
        kwargs = {}
        if workspace_mode:
            kwargs['workspace_mode'] = workspace_mode
        return Organization.objects.create(
            name=f'Hub Org {workspace_mode or "default"} {id(self)}',
            slug=f'hub-org-{workspace_mode or "default"}-{id(self)}',
            **kwargs,
        )

    def _make_user_and_login(self, org, username):
        user = User.objects.create_user(username=username, password='testpass123!')
        OrganizationMembership.objects.create(
            organization=org, user=user, role=OrganizationMembership.Role.OWNER, is_active=True,
        )
        client_ = TestClient()
        client_.login(username=username, password='testpass123!')
        return user, client_


class LegalIntelligenceHubFramingTests(_HubFixtureMixin, TestCase):
    def setUp(self):
        self.org = self._make_org('in_house_clm')
        self.user, self.client_ = self._make_user_and_login(self.org, 'hub_framing_user')

    def _get(self, **params):
        return self.client_.get(reverse('contracts:risk_log_list'), params)

    def test_heading_is_legal_intelligence_hub(self):
        response = self._get()
        self.assertContains(response, 'Legal Intelligence Hub')

    def test_ops_list_shell_present(self):
        response = self._get()
        self.assertContains(response, 'clm-list-shell')
        self.assertContains(response, 'clm-list-summary')
        self.assertContains(response, 'legal-hub-filter-toggle')
        self.assertContains(response, 'id="legal-hub-table"')
        self.assertContains(response, 'Search legal signals')

    def test_kpi_strip_present(self):
        response = self._get()
        self.assertContains(response, 'Critical/High Signals')
        self.assertContains(response, 'Cross-Document Conflicts')
        self.assertContains(response, 'Pending Approvals/Blockers')
        self.assertContains(response, 'Upcoming Deadlines')

    def test_filter_tabs_present(self):
        response = self._get()
        for tab in ('All', 'Conflicts', 'DPA Risks', 'Contract Risks', 'Approvals', 'Deadlines'):
            self.assertContains(response, tab)

    def test_empty_state_renders_with_no_signals(self):
        response = self._get()
        self.assertContains(response, 'No open legal signals')


class LegalIntelligenceHubDataTests(_HubFixtureMixin, TestCase):
    def setUp(self):
        self.org = self._make_org('in_house_clm')
        self.other_org = self._make_org(None)
        self.user, self.client_ = self._make_user_and_login(self.org, 'hub_data_user')

        client_obj = ClientModel.objects.create(organization=self.org, name='Acme Client', created_by=self.user)
        self.matter = Matter.objects.create(
            organization=self.org, matter_number='M-HUB-001', title='Acme Engagement',
            client=client_obj, created_by=self.user,
        )
        self.counterparty = Counterparty.objects.create(organization=self.org, name='Acme Corp')
        self.msa = Contract.objects.create(
            organization=self.org, title='Acme MSA', content='x', status='ACTIVE',
            counterparty='Acme Corp', matter=self.matter, created_by=self.user,
        )
        self.dpa = Contract.objects.create(
            organization=self.org, title='Acme DPA', content='x', status='ACTIVE',
            counterparty='Acme Corp', matter=self.matter, created_by=self.user,
        )

    def _get(self, **params):
        return self.client_.get(reverse('contracts:risk_log_list'), params)

    def test_risk_log_signal_shown(self):
        RiskLog.objects.create(
            contract=self.msa, matter=self.matter, title='Uncapped indemnity clause',
            description='...', risk_level='HIGH', status='OPEN', assigned_to=self.user,
        )
        response = self._get()
        self.assertContains(response, 'Uncapped indemnity clause')
        self.assertContains(response, 'Contract Risk')

    def test_resolved_risk_log_excluded(self):
        RiskLog.objects.create(
            contract=self.msa, matter=self.matter, title='Old resolved risk',
            description='...', risk_level='HIGH', status='RESOLVED',
        )
        response = self._get()
        self.assertNotContains(response, 'Old resolved risk')

    def test_dpa_risk_signal_shown(self):
        pack = DPAReviewPack.objects.create(
            organization=self.org, contract=self.dpa, counterparty=self.counterparty, matter=self.matter,
        )
        DPARiskItem.objects.create(
            review_pack=pack, category='TRANSFER', title='Non-EEA transfer, no mechanism',
            description='...', severity='CRITICAL', owners='DPO_SECURITY',
            is_cross_document_conflict=False, status='OPEN',
        )
        response = self._get()
        self.assertContains(response, 'Non-EEA transfer, no mechanism')
        self.assertContains(response, 'DPA Risk')

    def test_dpa_cross_document_conflict_signal_shown(self):
        pack = DPAReviewPack.objects.create(
            organization=self.org, contract=self.dpa, counterparty=self.counterparty, matter=self.matter,
        )
        pack.related_contracts.add(self.msa)
        DPARiskItem.objects.create(
            review_pack=pack, category='LIABILITY', title='DPA liability overrides MSA cap',
            description='...', severity='HIGH', owners='LEGAL', is_cross_document_conflict=True,
            status='OPEN', detection_rule='x', conflict_type='dpa_liability_vs_msa_cap',
        )
        response = self._get()
        self.assertContains(response, 'DPA liability overrides MSA cap')
        self.assertContains(response, 'Cross-doc conflict')
        self.assertEqual(response.context['legal_signal_counts']['conflict_count'], 1)

    def test_resolved_and_false_positive_dpa_risks_excluded(self):
        pack = DPAReviewPack.objects.create(
            organization=self.org, contract=self.dpa, counterparty=self.counterparty, matter=self.matter,
        )
        DPARiskItem.objects.create(
            review_pack=pack, category='SECURITY', title='Resolved DPA finding',
            description='...', severity='HIGH', owners='LEGAL', status='RESOLVED',
        )
        DPARiskItem.objects.create(
            review_pack=pack, category='SECURITY', title='False positive DPA finding',
            description='...', severity='HIGH', owners='LEGAL', status='FALSE_POSITIVE',
        )
        response = self._get()
        self.assertNotContains(response, 'Resolved DPA finding')
        self.assertNotContains(response, 'False positive DPA finding')

    def test_pending_approval_signal_derived_through_contract_matter(self):
        ApprovalRequest.objects.create(
            organization=self.org, contract=self.msa, approval_step='Legal',
            status='PENDING', assigned_to=self.user, due_date=timezone.now() + timedelta(days=5),
        )
        response = self._get()
        self.assertContains(response, 'Legal approval')
        self.assertContains(response, 'Acme Engagement')  # matter shown via contract__matter

    def test_approved_approval_excluded(self):
        ApprovalRequest.objects.create(
            organization=self.org, contract=self.msa, approval_step='Finance',
            status='APPROVED', assigned_to=self.user,
        )
        response = self._get()
        self.assertNotContains(response, 'Finance approval')

    def test_deadline_signal_shown(self):
        Deadline.objects.create(
            matter=self.matter, title='DSAR response window',
            due_date=_today() + timedelta(days=10), is_completed=False,
        )
        response = self._get()
        self.assertContains(response, 'DSAR response window')
        self.assertContains(response, 'Deadline')

    def test_completed_deadline_excluded(self):
        Deadline.objects.create(
            matter=self.matter, title='Done deadline', due_date=_today() - timedelta(days=1), is_completed=True,
        )
        response = self._get()
        self.assertNotContains(response, 'Done deadline')

    def test_far_future_deadline_excluded_from_window(self):
        Deadline.objects.create(
            matter=self.matter, title='Far future deadline',
            due_date=_today() + timedelta(days=200), is_completed=False,
        )
        response = self._get()
        self.assertNotContains(response, 'Far future deadline')

    def test_other_org_signals_not_shown(self):
        other_client = ClientModel.objects.create(organization=self.other_org, name='Other Client', created_by=self.user)
        other_matter = Matter.objects.create(
            organization=self.other_org, matter_number='M-OTHER-001', title='Other Org Matter',
            client=other_client, created_by=self.user,
        )
        other_contract = Contract.objects.create(
            organization=self.other_org, title='Other Org Contract', content='x', status='ACTIVE',
            matter=other_matter, created_by=self.user,
        )
        RiskLog.objects.create(
            contract=other_contract, matter=other_matter, title='Other org risk',
            description='...', risk_level='CRITICAL', status='OPEN',
        )
        response = self._get()
        self.assertNotContains(response, 'Other org risk')


class LegalIntelligenceHubFilterTests(_HubFixtureMixin, TestCase):
    def setUp(self):
        self.org = self._make_org('in_house_clm')
        self.user, self.client_ = self._make_user_and_login(self.org, 'hub_filter_user')
        client_obj = ClientModel.objects.create(organization=self.org, name='Acme Client', created_by=self.user)
        self.matter = Matter.objects.create(
            organization=self.org, matter_number='M-HUB-002', title='Filter Engagement',
            client=client_obj, created_by=self.user,
        )
        self.counterparty = Counterparty.objects.create(organization=self.org, name='Acme Corp')
        self.contract = Contract.objects.create(
            organization=self.org, title='Filter Contract', content='x', status='ACTIVE',
            matter=self.matter, created_by=self.user,
        )
        RiskLog.objects.create(
            contract=self.contract, matter=self.matter, title='Contract-side risk',
            description='...', risk_level='HIGH', status='OPEN',
        )
        pack = DPAReviewPack.objects.create(
            organization=self.org, contract=self.contract, counterparty=self.counterparty, matter=self.matter,
        )
        DPARiskItem.objects.create(
            review_pack=pack, category='SECURITY', title='DPA-side risk',
            description='...', severity='HIGH', owners='LEGAL', status='OPEN',
        )
        ApprovalRequest.objects.create(
            organization=self.org, contract=self.contract, approval_step='Legal',
            status='PENDING', assigned_to=self.user,
        )
        Deadline.objects.create(
            matter=self.matter, title='Filter deadline', due_date=_today() + timedelta(days=5), is_completed=False,
        )

    def _get(self, **params):
        return self.client_.get(reverse('contracts:risk_log_list'), params)

    def test_filter_contract_risks_shows_only_risk_log(self):
        response = self._get(type='contract_risk')
        self.assertContains(response, 'Contract-side risk')
        self.assertNotContains(response, 'DPA-side risk')
        self.assertNotContains(response, 'Legal approval')
        self.assertNotContains(response, 'Filter deadline')

    def test_filter_dpa_risks_shows_only_dpa_risk_item(self):
        response = self._get(type='dpa_risk')
        self.assertContains(response, 'DPA-side risk')
        self.assertNotContains(response, 'Contract-side risk')

    def test_filter_approvals_shows_only_approval(self):
        response = self._get(type='approval')
        self.assertContains(response, 'Legal approval')
        self.assertNotContains(response, 'Contract-side risk')
        self.assertNotContains(response, 'DPA-side risk')

    def test_filter_deadlines_shows_only_deadline(self):
        response = self._get(type='deadline')
        self.assertContains(response, 'Filter deadline')
        self.assertNotContains(response, 'Contract-side risk')

    def test_all_shows_everything(self):
        response = self._get()
        for text in ('Contract-side risk', 'DPA-side risk', 'Legal approval', 'Filter deadline'):
            self.assertContains(response, text)

    def test_search_query_filters_by_title(self):
        response = self._get(q='Contract-side')
        self.assertContains(response, 'Contract-side risk')
        self.assertNotContains(response, 'DPA-side risk')
        self.assertNotContains(response, 'Filter deadline')

    def test_severity_filter_excludes_non_matching(self):
        RiskLog.objects.create(
            contract=self.contract, matter=self.matter, title='Low severity risk',
            description='...', risk_level='LOW', status='OPEN',
        )
        response = self._get(severity='LOW')
        self.assertContains(response, 'Low severity risk')
        self.assertNotContains(response, 'Contract-side risk')
        self.assertNotContains(response, 'DPA-side risk')


class LegalIntelligenceHubLinkTests(_HubFixtureMixin, TestCase):
    def setUp(self):
        self.org = self._make_org('in_house_clm')
        self.user, self.client_ = self._make_user_and_login(self.org, 'hub_link_user')
        client_obj = ClientModel.objects.create(organization=self.org, name='Acme Client', created_by=self.user)
        self.matter = Matter.objects.create(
            organization=self.org, matter_number='M-HUB-003', title='Link Engagement',
            client=client_obj, created_by=self.user,
        )
        self.counterparty = Counterparty.objects.create(organization=self.org, name='Acme Corp')
        self.contract = Contract.objects.create(
            organization=self.org, title='Link Contract', content='x', status='ACTIVE',
            matter=self.matter, created_by=self.user,
        )
        self.risk = RiskLog.objects.create(
            contract=self.contract, matter=self.matter, title='Linked risk',
            description='...', risk_level='HIGH', status='OPEN',
        )
        self.pack = DPAReviewPack.objects.create(
            organization=self.org, contract=self.contract, counterparty=self.counterparty, matter=self.matter,
        )
        self.dpa_item = DPARiskItem.objects.create(
            review_pack=self.pack, category='SECURITY', title='Linked DPA risk',
            description='...', severity='HIGH', owners='LEGAL', status='OPEN',
        )
        self.approval = ApprovalRequest.objects.create(
            organization=self.org, contract=self.contract, approval_step='Legal',
            status='PENDING', assigned_to=self.user,
        )
        self.deadline = Deadline.objects.create(
            matter=self.matter, title='Linked deadline', due_date=_today() + timedelta(days=5), is_completed=False,
        )

    def test_source_links_resolve(self):
        response = self.client_.get(reverse('contracts:risk_log_list'))
        for name, kwargs in [
            ('contracts:risk_log_update', {'pk': self.risk.pk}),
            ('contracts:dpa_review_pack_detail', {'pk': self.pack.pk}),
            ('contracts:approval_request_update', {'pk': self.approval.pk}),
            ('contracts:deadline_update', {'pk': self.deadline.pk}),
        ]:
            url = reverse(name, kwargs=kwargs)
            self.assertContains(response, url)
            self.assertEqual(self.client_.get(url).status_code, 200)


class LawFirmOpsRiskRegisterPreservedTests(_HubFixtureMixin, TestCase):
    """law_firm_ops must keep the original Risk
    Register — the Legal Intelligence Hub is in_house_clm-only."""

    def setUp(self):
        self.org = self._make_org('law_firm_ops')
        self.user, self.client_ = self._make_user_and_login(self.org, 'hub_lawfirm_user')

    def _get(self, **params):
        return self.client_.get(reverse('contracts:risk_log_list'), params)

    def test_heading_is_still_risk_register(self):
        response = self._get()
        content = response.content.decode()
        self.assertIn('Risk Register', content)
        self.assertNotIn('Legal Intelligence Hub', content)

    def test_original_kpi_labels_preserved(self):
        response = self._get()
        self.assertContains(response, 'Open')
        self.assertContains(response, 'High Severity')
        self.assertContains(response, 'In Progress')
        self.assertContains(response, 'Resolved')

    def test_original_context_keys_preserved(self):
        response = self._get()
        self.assertIn('risk_logs', response.context)
        self.assertIn('total_risks', response.context)
        self.assertIn('high_severity_count', response.context)

    def test_hub_only_kpis_absent(self):
        response = self._get()
        content = response.content.decode()
        self.assertNotIn('Cross-Document Conflicts', content)
        self.assertNotIn('Pending Approvals/Blockers', content)


class LegalIntelligenceHubNoMutationTests(_HubFixtureMixin, TestCase):
    def setUp(self):
        self.org = self._make_org('in_house_clm')
        self.user, self.client_ = self._make_user_and_login(self.org, 'hub_nomutate_user')
        client_obj = ClientModel.objects.create(organization=self.org, name='Acme Client', created_by=self.user)
        self.matter = Matter.objects.create(
            organization=self.org, matter_number='M-HUB-004', title='NoMutate Engagement',
            client=client_obj, created_by=self.user,
        )
        self.counterparty = Counterparty.objects.create(organization=self.org, name='Acme Corp')
        self.contract = Contract.objects.create(
            organization=self.org, title='NoMutate Contract', content='x', status='ACTIVE',
            matter=self.matter, created_by=self.user,
        )
        self.review_pack = DPAReviewPack.objects.create(
            organization=self.org, contract=self.contract, counterparty=self.counterparty, matter=self.matter,
        )

    def _get(self):
        return self.client_.get(reverse('contracts:risk_log_list'))

    def test_does_not_call_conflict_detection(self):
        import contracts.services.dpa_conflict as dpa_conflict

        def _boom(*args, **kwargs):
            raise AssertionError('Legal Intelligence Hub must not call check_cross_document_conflicts')

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
            raise AssertionError('Legal Intelligence Hub must not call run_dpa_analysis')

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
            organization=self.org, contract=self.contract, approval_step='Legal',
            status='PENDING', assigned_to=self.user,
        )
        self._get()
        approval.refresh_from_db()
        self.assertEqual(approval.status, 'PENDING')


class LegalIntelligenceHubQueryCountTests(_HubFixtureMixin, TestCase):
    def setUp(self):
        self.org = self._make_org('in_house_clm')
        self.user, self.client_ = self._make_user_and_login(self.org, 'hub_perf_user')
        self.counterparty = Counterparty.objects.create(organization=self.org, name='Perf Counterparty')
        client_obj = ClientModel.objects.create(organization=self.org, name='Perf Client', created_by=self.user)
        self.matter = Matter.objects.create(
            organization=self.org, matter_number='M-HUB-PERF', title='Perf Engagement',
            client=client_obj, created_by=self.user,
        )

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
                due_date=_today() + timedelta(days=idx % 20 + 1), is_completed=False,
            )

    def _query_count(self):
        with CaptureQueriesContext(connection) as ctx:
            response = self.client_.get(reverse('contracts:risk_log_list'))
        self.assertEqual(response.status_code, 200)
        return len(ctx)

    def test_query_count_does_not_scale_linearly(self):
        self._seed(3)
        baseline = self._query_count()

        self._seed(25)
        expanded = self._query_count()

        self.assertLessEqual(expanded, baseline + 8)
