"""Tests for the DPA Review Pack module.

Covers: model creation, the heuristic dpa_review analyzer detecting planted
issues in realistic DPA text (role qualification, payroll data categories,
subprocessor authorization conflicts, international transfer risk, vague
security language, unrealistic breach notification deadlines, chargeable
DSAR assistance, unbounded audit rights, statutory-retention deletion
conflicts, and DPA liability overriding the MSA cap), risk item
persistence via the analysis endpoint, human-only approval routing (the
analyzer must never set approval_status to APPROVED), audit logging,
cross-tenant isolation, the playbook reference list, and copy quality.
"""
import json
import re

from django.contrib.auth.models import User
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse

from contracts.models import (
    AuditLog,
    Contract,
    DPAApprovalHistoryEntry,
    DPAPlaybookPosition,
    DPAReviewPack,
    DPARiskItem,
    DPARiskItemNote,
    Organization,
    OrganizationMembership,
)
from contracts.services.dpa_conflict import check_cross_document_conflicts
from contracts.services.dpa_review import run_dpa_analysis

ISO_TIMESTAMP_RE = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}')

RISKY_DPA_TEXT = """DATA PROCESSING AGREEMENT

Client is the Controller of Personal Data processed under this DPA.
Payrollminds is the Processor and shall process Personal Data only on
Client's documented instructions.

Categories of Personal Data include employee name, salary and wage data,
tax ID and income tax withholding data, national insurance number and
social security data, bank account and IBAN details, pension and
retirement benefit enrollment data, sick leave and annual leave records,
employment contract terms, national identification number, payroll
correction history, and payslip data.

Payrollminds may engage subprocessors under a general authorization
without case-by-case approval. Notwithstanding the foregoing, Client's
prior written approval is also required before any new subprocessor is
engaged.

Payrollminds uses a payroll calculation subprocessor located in the
United States for overflow processing capacity.

Payrollminds shall implement encryption of data at rest and regular
backup of payroll records.

Payrollminds shall notify Client within 4 hours of becoming aware of a
Personal Data Breach.

Payrollminds shall assist Client with data subject requests at
Payrollminds' reasonable costs where the request requires substantial
effort.

Client may conduct an on-site audit of Payrollminds' processing
facilities upon reasonable notice.

Upon termination, Payrollminds shall delete or return all Personal Data
within 30 days, except that payroll and tax records subject to statutory
retention requirements shall be retained for the applicable statutory
period.

Notwithstanding the limitation of liability in the Agreement,
Payrollminds' liability for any breach of this DPA shall be uncapped.
Payrollminds shall indemnify Client for losses arising from a Personal
Data Breach.
"""

CLEAN_DPA_TEXT = """DATA PROCESSING AGREEMENT

Client is the Controller of Personal Data. Payrollminds is the Processor
and shall process Personal Data only on Client's documented instructions.

Payrollminds may engage subprocessors under a general written
authorization, subject to 30 days' prior notice to Client.

Payrollminds shall implement encryption of data at rest, role-based
access control with least privilege, multi-factor authentication for all
administrative access, audit logging of all access, regular backup of
payroll records, a documented incident response plan, and logical data
segregation between client tenants.

Payrollminds shall notify Client without undue delay and in any event
within 72 hours after becoming aware of a Personal Data Breach.

Payrollminds shall provide reasonable assistance with data subject
requests at no additional fee.

Client may audit Payrollminds' compliance no more than once per year;
a current SOC 2 report shall satisfy this obligation.

Upon termination, Payrollminds shall delete all Personal Data within 90
days and provide a certificate of deletion.
"""


def _make_org_and_contract(text=RISKY_DPA_TEXT, org_slug='dpa-test-firm'):
    organization = Organization.objects.create(name=f'DPA Test Firm ({org_slug})', slug=org_slug)
    user = User.objects.create_user(username=f'{org_slug}-user', password='testpass123', email=f'{org_slug}@example.com')
    OrganizationMembership.objects.create(organization=organization, user=user, role=OrganizationMembership.Role.ADMIN, is_active=True)
    contract = Contract.objects.create(
        organization=organization, title='Payrollminds DPA', content=text,
        contract_type=Contract.ContractType.DPA, status='IN_PROGRESS', created_by=user,
    )
    return organization, user, contract


def _make_msa(organization, user, text=None, title='Payrollminds MSA'):
    return Contract.objects.create(
        organization=organization,
        title=title,
        content=text or 'MASTER SERVICE AGREEMENT. Limitation of liability: each party aggregate liability shall not exceed the fees paid in the twelve months before the claim.',
        contract_type=Contract.ContractType.MSA,
        status='IN_PROGRESS',
        created_by=user,
    )


def _run_cross_document_conflicts(review_pack):
    run_dpa_analysis(review_pack)
    return check_cross_document_conflicts(review_pack)


class DPAReviewPackModelTests(TestCase):
    def test_review_pack_creation_defaults_to_draft_and_ambiguous(self):
        organization, user, contract = _make_org_and_contract()
        review_pack = DPAReviewPack.objects.create(organization=organization, contract=contract, created_by=user)
        self.assertEqual(review_pack.approval_status, DPAReviewPack.ApprovalStatus.DRAFT)
        self.assertEqual(review_pack.role_qualification, DPAReviewPack.RoleQualification.AMBIGUOUS)


class DPAAnalyzerDetectionTests(TestCase):
    """The heuristic scanner must actually detect what's in the text —
    not just render fields, but populate them correctly."""

    def setUp(self):
        self.organization, self.user, self.contract = _make_org_and_contract()
        self.review_pack = DPAReviewPack.objects.create(organization=self.organization, contract=self.contract, created_by=self.user)

    def test_detects_controller_processor_roles(self):
        run_dpa_analysis(self.review_pack)
        self.assertEqual(self.review_pack.role_qualification, DPAReviewPack.RoleQualification.CONTROLLER_PROCESSOR)

    def test_detects_all_planted_payroll_data_categories(self):
        run_dpa_analysis(self.review_pack)
        for field_name in (
            'has_salary_wage_data', 'has_tax_data', 'has_social_security_data', 'has_bank_account_data',
            'has_pension_benefits_data', 'has_absence_leave_data', 'has_employment_contract_data',
            'has_national_identifiers', 'has_payroll_corrections', 'has_payslip_data',
        ):
            self.assertTrue(getattr(self.review_pack, field_name), f'{field_name} should be detected')

    def test_detects_contradictory_subprocessor_authorization_model(self):
        run_dpa_analysis(self.review_pack)
        self.assertTrue(self.review_pack.subprocessor_prior_approval_required)
        self.assertTrue(self.review_pack.subprocessor_general_authorization_allowed)

    def test_detects_transfer_without_mechanism_as_critical(self):
        suggestions = run_dpa_analysis(self.review_pack)
        self.assertTrue(self.review_pack.transfers_outside_eea)
        self.assertFalse(self.review_pack.transfer_mechanism_present)
        critical_transfer = [s for s in suggestions if s.category == DPARiskItem.Category.TRANSFER and s.severity == DPARiskItem.Severity.CRITICAL]
        self.assertEqual(len(critical_transfer), 1)
        self.assertIn('united states', critical_transfer[0].evidence_text.lower())
        self.assertEqual(critical_transfer[0].confidence, DPARiskItem.Confidence.HIGH)
        self.assertEqual(critical_transfer[0].detection_rule, 'non_eea_transfer_missing_mechanism')

    def test_detects_vague_security_measures(self):
        suggestions = run_dpa_analysis(self.review_pack)
        self.assertFalse(self.review_pack.security_measures_specific)
        vague_security = [s for s in suggestions if s.detection_rule == 'security_measures_vague_or_incomplete']
        self.assertEqual(len(vague_security), 1)
        self.assertEqual(vague_security[0].evidence_text, 'Evidence requires manual verification')
        self.assertEqual(vague_security[0].confidence, DPARiskItem.Confidence.MEDIUM)

    def test_specific_security_measures_do_not_flag_as_vague(self):
        organization, user, contract = _make_org_and_contract(text=CLEAN_DPA_TEXT, org_slug='dpa-clean-firm')
        review_pack = DPAReviewPack.objects.create(organization=organization, contract=contract, created_by=user)
        run_dpa_analysis(review_pack)
        self.assertTrue(review_pack.security_measures_specific)

    def test_detects_unrealistic_breach_notification_deadline(self):
        suggestions = run_dpa_analysis(self.review_pack)
        self.assertEqual(self.review_pack.breach_notification_deadline_hours, 4)
        self.assertFalse(self.review_pack.breach_notification_realistic)
        breach = [s for s in suggestions if s.detection_rule == 'breach_notification_short_deadline'][0]
        self.assertIn('within 4 hours', breach.evidence_text.lower())
        self.assertEqual(breach.confidence, DPARiskItem.Confidence.HIGH)

    def test_realistic_breach_deadline_not_flagged(self):
        organization, user, contract = _make_org_and_contract(text=CLEAN_DPA_TEXT, org_slug='dpa-clean-firm2')
        review_pack = DPAReviewPack.objects.create(organization=organization, contract=contract, created_by=user)
        run_dpa_analysis(review_pack)
        self.assertEqual(review_pack.breach_notification_deadline_hours, 72)
        self.assertTrue(review_pack.breach_notification_realistic)

    def test_detects_chargeable_dsar_assistance(self):
        run_dpa_analysis(self.review_pack)
        self.assertTrue(self.review_pack.dsar_assistance_chargeable)

    def test_detects_onsite_audit_and_unbounded_frequency(self):
        suggestions = run_dpa_analysis(self.review_pack)
        self.assertTrue(self.review_pack.audit_rights_onsite_allowed)
        self.assertFalse(self.review_pack.audit_rights_frequency_limited)
        onsite = [s for s in suggestions if s.detection_rule == 'audit_rights_onsite_allowed'][0]
        self.assertIn('on-site audit', onsite.evidence_text.lower())
        frequency = [s for s in suggestions if s.detection_rule == 'audit_frequency_not_limited'][0]
        self.assertEqual(frequency.confidence, DPARiskItem.Confidence.NEEDS_HUMAN_CHECK)

    def test_detects_deletion_deadline_conflict_with_statutory_retention(self):
        suggestions = run_dpa_analysis(self.review_pack)
        self.assertEqual(self.review_pack.deletion_return_deadline_days, 30)
        self.assertTrue(self.review_pack.deletion_legal_retention_conflict)
        deletion = [s for s in suggestions if s.detection_rule == 'deletion_deadline_statutory_retention_conflict'][0]
        self.assertIn('30 days', deletion.evidence_text.lower())
        self.assertIn('statutory', deletion.evidence_text.lower())

    def test_detects_uncapped_liability_and_msa_override(self):
        suggestions = run_dpa_analysis(self.review_pack)
        self.assertTrue(self.review_pack.liability_uncapped)
        self.assertTrue(self.review_pack.liability_overrides_msa_cap)
        liability = [s for s in suggestions if s.detection_rule == 'dpa_uncapped_liability'][0]
        self.assertIn('uncapped', liability.evidence_text.lower())
        self.assertEqual(liability.confidence, DPARiskItem.Confidence.HIGH)

    def test_role_ambiguity_uses_human_check_confidence(self):
        organization, user, contract = _make_org_and_contract(text='DATA PROCESSING AGREEMENT. Personal data will be processed.', org_slug='dpa-ambiguous-role')
        review_pack = DPAReviewPack.objects.create(organization=organization, contract=contract, created_by=user)
        suggestions = run_dpa_analysis(review_pack)
        role = [s for s in suggestions if s.detection_rule == 'role_ambiguous_missing_controller_processor'][0]
        self.assertEqual(role.confidence, DPARiskItem.Confidence.NEEDS_HUMAN_CHECK)
        self.assertEqual(role.evidence_text, 'Evidence requires manual verification')

    def test_detects_dpa_uncapped_liability_against_linked_msa_cap(self):
        msa = _make_msa(self.organization, self.user)
        self.review_pack.related_contracts.add(msa)
        suggestions = _run_cross_document_conflicts(self.review_pack)
        conflict = [s for s in suggestions if s.conflict_type == 'dpa_liability_vs_msa_cap']
        self.assertEqual(len(conflict), 1)
        self.assertEqual(conflict[0].owners, 'LEGAL,HEAD_LEGAL')
        self.assertTrue(conflict[0].is_cross_document_conflict)
        self.assertIn('uncapped', conflict[0].evidence_text.lower())
        self.assertIn('liability', conflict[0].related_contract_evidence_text.lower())

    def test_no_dpa_msa_conflict_when_no_linked_msa_exists(self):
        suggestions = _run_cross_document_conflicts(self.review_pack)
        self.assertFalse([s for s in suggestions if s.conflict_type == 'dpa_liability_vs_msa_cap'])

    def test_no_dpa_msa_conflict_when_dpa_liability_is_capped_consistently(self):
        organization, user, contract = _make_org_and_contract(
            text=CLEAN_DPA_TEXT + '\nNothing in this DPA increases or removes the limitation of liability in the Agreement.',
            org_slug='dpa-capped-consistent',
        )
        review_pack = DPAReviewPack.objects.create(organization=organization, contract=contract, created_by=user)
        review_pack.related_contracts.add(_make_msa(organization, user))
        suggestions = _run_cross_document_conflicts(review_pack)
        self.assertFalse([s for s in suggestions if s.conflict_type == 'dpa_liability_vs_msa_cap'])

    def test_detects_dpa_audit_rights_against_linked_contract_audit_limits(self):
        msa = _make_msa(
            self.organization,
            self.user,
            text='Audit rights are limited to once per year upon 30 days prior notice. A current SOC 2 report shall satisfy audit obligations.',
        )
        self.review_pack.related_contracts.add(msa)
        suggestions = _run_cross_document_conflicts(self.review_pack)
        conflict = [s for s in suggestions if s.conflict_type == 'dpa_audit_vs_contract_audit_limit']
        self.assertEqual(len(conflict), 1)
        self.assertEqual(conflict[0].owners, 'LEGAL,DPO_SECURITY')
        self.assertIn('on-site audit', conflict[0].evidence_text.lower())
        self.assertIn('once per year', conflict[0].related_contract_evidence_text.lower())

    def test_detects_dpa_breach_notice_against_linked_contract_notice_standard(self):
        msa = _make_msa(
            self.organization,
            self.user,
            text='Security incidents will be notified without undue delay and in any event within 72 hours following confirmation.',
        )
        self.review_pack.related_contracts.add(msa)
        suggestions = _run_cross_document_conflicts(self.review_pack)
        conflict = [s for s in suggestions if s.conflict_type == 'dpa_breach_notice_vs_contract_notice']
        self.assertEqual(len(conflict), 1)
        self.assertEqual(conflict[0].owners, 'LEGAL,DPO_SECURITY,DELIVERY')
        self.assertIn('within 4 hours', conflict[0].evidence_text.lower())
        self.assertIn('72 hours', conflict[0].related_contract_evidence_text.lower())

    def test_detects_dpa_deletion_deadline_against_retention_obligation(self):
        msa = _make_msa(
            self.organization,
            self.user,
            text='Supplier may retain payroll records, tax records, and legal recordkeeping archives for the applicable statutory retention period.',
        )
        self.review_pack.related_contracts.add(msa)
        suggestions = _run_cross_document_conflicts(self.review_pack)
        conflict = [s for s in suggestions if s.conflict_type == 'dpa_deletion_vs_retention_obligation']
        self.assertEqual(len(conflict), 1)
        self.assertEqual(conflict[0].owners, 'LEGAL,DELIVERY')
        self.assertIn('30 days', conflict[0].evidence_text.lower())
        self.assertIn('retain payroll', conflict[0].related_contract_evidence_text.lower())

    def test_detects_subprocessor_approval_against_delivery_model(self):
        sow = _make_msa(
            self.organization,
            self.user,
            title='Payrollminds SOW',
            text='Services may use payroll vendors, SaaS tools, hosting providers, cloud providers, affiliates, and other third-party subprocessors.',
        )
        sow.contract_type = Contract.ContractType.SOW
        sow.save()
        self.review_pack.related_contracts.add(sow)
        suggestions = _run_cross_document_conflicts(self.review_pack)
        conflict = [s for s in suggestions if s.conflict_type == 'dpa_subprocessor_approval_vs_delivery_model']
        self.assertEqual(len(conflict), 1)
        self.assertEqual(conflict[0].owners, 'LEGAL,DPO_SECURITY,BUSINESS,DELIVERY')
        self.assertIn('prior written approval', conflict[0].evidence_text.lower())
        self.assertIn('payroll vendors', conflict[0].related_contract_evidence_text.lower())

    def test_detects_assistance_obligations_against_scope_or_fees(self):
        dpa_text = CLEAN_DPA_TEXT + '\nPayrollminds shall provide unlimited assistance with data subject requests, audits, investigations, and controller obligations at no cost.'
        organization, user, contract = _make_org_and_contract(text=dpa_text, org_slug='dpa-assistance-conflict')
        review_pack = DPAReviewPack.objects.create(organization=organization, contract=contract, created_by=user)
        review_pack.related_contracts.add(_make_msa(
            organization,
            user,
            text='Assistance beyond scope is chargeable, subject to additional fees and change control under the statement of work.',
        ))
        suggestions = _run_cross_document_conflicts(review_pack)
        conflict = [s for s in suggestions if s.conflict_type == 'dpa_assistance_vs_scope_or_fees']
        self.assertEqual(len(conflict), 1)
        self.assertEqual(conflict[0].owners, 'LEGAL,BUSINESS,FINANCE')
        self.assertIn('unlimited assistance', conflict[0].evidence_text.lower())
        self.assertIn('chargeable', conflict[0].related_contract_evidence_text.lower())

    def test_detects_specific_security_obligations_against_vague_contract_security(self):
        organization, user, contract = _make_org_and_contract(text=CLEAN_DPA_TEXT, org_slug='dpa-security-conflict')
        review_pack = DPAReviewPack.objects.create(organization=organization, contract=contract, created_by=user)
        review_pack.related_contracts.add(_make_msa(
            organization,
            user,
            text='Supplier will maintain commercially reasonable security measures and reasonable safeguards.',
        ))
        suggestions = _run_cross_document_conflicts(review_pack)
        conflict = [s for s in suggestions if s.conflict_type == 'dpa_security_obligations_vs_contract_security']
        self.assertEqual(len(conflict), 1)
        self.assertEqual(conflict[0].owners, 'DPO_SECURITY,LEGAL')
        self.assertIn('encryption', conflict[0].evidence_text.lower())
        self.assertIn('commercially reasonable security', conflict[0].related_contract_evidence_text.lower())

    def test_cross_document_conflicts_are_deduplicated_by_conflict_type(self):
        self.review_pack.related_contracts.add(
            _make_msa(self.organization, self.user, text='Audit no more than once per year with reasonable notice.', title='Payrollminds MSA 1'),
            _make_msa(self.organization, self.user, text='Audit no more than once per year with reasonable notice.', title='Payrollminds MSA 2'),
        )
        suggestions = _run_cross_document_conflicts(self.review_pack)
        conflicts = [s for s in suggestions if s.conflict_type == 'dpa_audit_vs_contract_audit_limit']
        self.assertEqual(len(conflicts), 1)

    def test_no_cross_document_conflict_without_linked_contract_evidence(self):
        self.review_pack.related_contracts.add(_make_msa(
            self.organization,
            self.user,
            text='This master services agreement governs payroll services.',
        ))
        suggestions = _run_cross_document_conflicts(self.review_pack)
        self.assertFalse(suggestions)

    def test_analysis_never_touches_approval_status(self):
        """The analyzer must never approve a DPA — that is exclusively a
        human action via the approval-status endpoint."""
        self.review_pack.approval_status = DPAReviewPack.ApprovalStatus.UNDER_REVIEW
        self.review_pack.save()
        run_dpa_analysis(self.review_pack)
        self.assertEqual(self.review_pack.approval_status, DPAReviewPack.ApprovalStatus.UNDER_REVIEW)

    def test_clean_dpa_produces_far_fewer_suggestions_than_risky_one(self):
        organization, user, contract = _make_org_and_contract(text=CLEAN_DPA_TEXT, org_slug='dpa-clean-firm3')
        clean_pack = DPAReviewPack.objects.create(organization=organization, contract=contract, created_by=user)
        clean_suggestions = run_dpa_analysis(clean_pack)
        risky_suggestions = run_dpa_analysis(self.review_pack)
        self.assertLess(len(clean_suggestions), len(risky_suggestions))


class DPAReviewPackViewTests(TestCase):
    def setUp(self):
        self.organization, self.admin, self.contract = _make_org_and_contract()
        self.review_pack = DPAReviewPack.objects.create(organization=self.organization, contract=self.contract, created_by=self.admin)
        self.member = User.objects.create_user(username='dpa_member', password='testpass123', email='member@example.com')
        OrganizationMembership.objects.create(organization=self.organization, user=self.member, role=OrganizationMembership.Role.MEMBER, is_active=True)

    def test_list_view_renders_for_member(self):
        client = TestClient()
        client.login(username='dpa_member', password='testpass123')
        response = client.get(reverse('contracts:dpa_review_pack_list'))
        self.assertEqual(response.status_code, 200)

    def test_list_uses_canonical_design_system_primitives(self):
        client = TestClient()
        client.login(username='dpa_member', password='testpass123')
        response = client.get(reverse('contracts:dpa_review_pack_list'))
        body = response.content.decode()
        self.assertIn('dc-ds-page dc-ds-page--wide dc-ds-page-flow dc-ds-list-page clm-list-page dpa-review-page', body)
        self.assertIn('topbar-page-title', body)
        self.assertIn('Privacy Reviews', body)
        self.assertNotIn('<header class="dc-ds-page-hero', body)
        self.assertNotIn('dc-ds-scaffold--with-rail', body)
        self.assertIn('dc-ds-summary clm-list-summary dpa-review-summary', body)
        self.assertNotIn('dc-ds-summary--vertical', body)
        self.assertIn('Needs decision', body)
        self.assertIn('Open risks', body)
        self.assertIn('Critical risks', body)
        self.assertIn('Start DPA review', body)
        self.assertNotIn('Open DPA playbook', body)
        self.assertIn('clm-list-shell', body)
        self.assertIn('clm-list-filter-drawer', body)
        self.assertIn('dc-ds-list-toolbar', body)
        self.assertIn('dc-ds-table', body)
        self.assertIn('Next action', body)
        self.assertNotIn('Active reviews', body)
        self.assertNotIn('class="kpi-card', body)
        self.assertNotIn('class="panel overflow-hidden"', body)

    def test_list_hides_manage_playbook_from_members(self):
        client = TestClient()
        client.login(username='dpa_member', password='testpass123')
        response = client.get(reverse('contracts:dpa_review_pack_list'))
        body = response.content.decode()
        self.assertFalse(response.context['can_manage_playbook'])
        self.assertNotIn('Manage playbook', body)

    def test_list_shows_manage_playbook_to_admins(self):
        client = TestClient()
        client.login(username=self.admin.username, password='testpass123')
        response = client.get(reverse('contracts:dpa_review_pack_list'))
        body = response.content.decode()
        self.assertTrue(response.context['can_manage_playbook'])
        self.assertIn('Manage playbook', body)

    def test_list_exposes_semantic_row_counts_and_badges(self):
        DPARiskItem.objects.create(
            review_pack=self.review_pack,
            category=DPARiskItem.Category.TRANSFER,
            title='Transfer mechanism missing',
            description='Needs review',
            severity=DPARiskItem.Severity.CRITICAL,
            owners='LEGAL',
            status=DPARiskItem.Status.OPEN,
        )
        DPARiskItem.objects.create(
            review_pack=self.review_pack,
            category=DPARiskItem.Category.SECURITY,
            title='Resolved security item',
            description='Resolved',
            severity=DPARiskItem.Severity.HIGH,
            owners='LEGAL',
            status=DPARiskItem.Status.RESOLVED,
        )
        client = TestClient()
        client.login(username='dpa_member', password='testpass123')
        response = client.get(reverse('contracts:dpa_review_pack_list'))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        row = response.context['review_pack_rows'][0]
        self.assertEqual(row['unresolved_risk_count'], 1)
        self.assertEqual(row['critical_risk_count'], 1)
        self.assertEqual(row['risk_tone'], 'danger')
        self.assertEqual(row['approval_tone'], 'neutral')
        self.assertEqual(row['next_action'], 'Resolve role qualification')
        self.assertEqual(row['review_status_label'], 'Draft')
        self.assertIn('dc-ds-badge--attention', body)
        self.assertIn('Role unclear', body)
        self.assertIn('dc-ds-badge--attention">Role unclear</span>', body)
        self.assertEqual(response.context['needs_decision_count'], 1)
        self.assertEqual(response.context['open_risk_count'], 1)
        self.assertEqual(response.context['open_critical_risk_count'], 1)
        self.assertIn('1 open', body)
        self.assertEqual(row['role_label'], 'Role unclear')
        self.assertEqual(row['review_status_label'], 'Draft')
        self.assertIn('data-col="agreement"', body)
        self.assertIn('>Agreement</th>', body)
        self.assertIn('>Review</th>', body)
        self.assertIn('>Next action</th>', body)
        self.assertNotIn('>DPA / contract</th>', body)
        self.assertNotIn('>Counterparty</th>', body)
        self.assertNotIn('>Open risks</th>', body)
        self.assertNotIn('>Review status</th>', body)
        self.assertIn('id="dpa-col-toggle"', body)
        self.assertIn('Open review', body)
        self.assertIn('View memo', body)
        self.assertIn('View contract record', body)
        self.assertIn('wq-kebab', body)
        self.assertIn('min-width: 1080px', body)
        self.assertIn('position: sticky; left: 0', body)

    def test_list_filters_by_review_status_and_role(self):
        other = DPAReviewPack.objects.create(
            organization=self.organization,
            contract=self.contract,
            created_by=self.admin,
            approval_status=DPAReviewPack.ApprovalStatus.APPROVED,
            role_qualification=DPAReviewPack.RoleQualification.CONTROLLER_PROCESSOR,
        )
        client = TestClient()
        client.login(username='dpa_member', password='testpass123')
        response = client.get(
            reverse('contracts:dpa_review_pack_list'),
            {'status': 'DRAFT', 'role': 'AMBIGUOUS'},
        )
        self.assertEqual(response.status_code, 200)
        ids = [row['pack'].id for row in response.context['review_pack_rows']]
        self.assertIn(self.review_pack.id, ids)
        self.assertNotIn(other.id, ids)

    def test_detail_view_renders_for_member(self):
        client = TestClient()
        client.login(username='dpa_member', password='testpass123')
        response = client.get(reverse('contracts:dpa_review_pack_detail', kwargs={'pk': self.review_pack.pk}))
        self.assertEqual(response.status_code, 200)

    def test_detail_workspace_shell_and_tabs(self):
        client = TestClient()
        client.login(username='dpa_member', password='testpass123')
        url = reverse('contracts:dpa_review_pack_detail', kwargs={'pk': self.review_pack.pk})
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        body = response.content.decode().split('<div id="djDebug"', 1)[0]
        self.assertIn('dc-ds-workspace--dpa', body)
        self.assertIn('dc-ds-workspace--record', body)
        self.assertIn('role="tablist"', body)
        self.assertIn('Overview', body)
        self.assertIn('Findings', body)
        self.assertIn('Risks', body)
        self.assertIn('Documents', body)
        self.assertIn('Decision history', body)
        self.assertIn('Actions', body)
        self.assertIn('Decision required', body)
        self.assertIn('Related actions', body)
        self.assertNotIn('Quick links', body)
        self.assertIn('Risk summary', body)
        self.assertIn('dc-ds-workspace__rail--sticky', body)
        self.assertIn('View memo', body)
        self.assertIn('View contract', body)
        self.assertIn('Actions', body)
        self.assertNotIn('Generate Review Memo', body)

        admin_client = TestClient()
        admin_client.login(username=self.admin.username, password='testpass123')
        admin_body = admin_client.get(url).content.decode().split('<div id="djDebug"', 1)[0]
        self.assertIn('Generate memo', admin_body)
        self.assertIn('Run analysis', admin_body)

        findings = client.get(f'{url}?tab=findings')
        self.assertEqual(findings.status_code, 200)
        findings_body = findings.content.decode().split('<div id="djDebug"', 1)[0]
        self.assertIn('Role Qualification', findings_body)
        self.assertIn('Processing Description', findings_body)
        self.assertIn('Liability Conflict Detection', findings_body)
        self.assertIn('dpa-category-row', findings_body)
        self.assertTrue(
            any(label in findings_body for label in (
                'Confirmed', 'Needs input', 'Risk', 'Not applicable', 'Not reviewed',
            ))
        )

        history = client.get(f'{url}?tab=history')
        self.assertEqual(history.status_code, 200)
        self.assertContains(history, 'Decision history')

    def test_detail_decision_bar_for_reviewer(self):
        self.review_pack.reviewer = self.member
        self.review_pack.approval_status = DPAReviewPack.ApprovalStatus.UNDER_REVIEW
        self.review_pack.save(update_fields=['reviewer', 'approval_status'])
        client = TestClient()
        client.login(username='dpa_member', password='testpass123')
        response = client.get(reverse('contracts:dpa_review_pack_detail', kwargs={'pk': self.review_pack.pk}))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode().split('<div id="djDebug"', 1)[0]
        self.assertIn('dpa-decision-bar', body)
        self.assertIn('Submit decision', body)
        self.assertIn('Decision note', body)

    def test_run_analysis_persists_risk_items(self):
        client = TestClient()
        client.login(username=self.admin.username, password='testpass123')
        response = client.post(
            reverse('contracts:dpa_review_run_analysis', kwargs={'pk': self.review_pack.pk}),
            data=json.dumps({}), content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertGreater(self.review_pack.risk_items.count(), 0)
        risk = self.review_pack.risk_items.exclude(evidence_text='').first()
        self.assertIsNotNone(risk)
        self.assertTrue(risk.detection_rule)
        self.assertTrue(risk.source_section)
        self.assertIn(risk.confidence, {DPARiskItem.Confidence.HIGH, DPARiskItem.Confidence.MEDIUM, DPARiskItem.Confidence.NEEDS_HUMAN_CHECK})

    def test_run_analysis_persists_cross_document_conflict_and_memo_evidence(self):
        self.review_pack.related_contracts.add(_make_msa(self.organization, self.admin))
        client = TestClient()
        client.login(username=self.admin.username, password='testpass123')
        response = client.post(
            reverse('contracts:dpa_review_run_analysis', kwargs={'pk': self.review_pack.pk}),
            data=json.dumps({}), content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        conflict = self.review_pack.risk_items.get(conflict_type='dpa_liability_vs_msa_cap')
        self.assertTrue(conflict.is_cross_document_conflict)
        self.assertIn('uncapped', conflict.evidence_text.lower())
        self.assertIn('liability', conflict.related_contract_evidence_text.lower())

        response = client.post(reverse('contracts:dpa_review_generate_memo', kwargs={'pk': self.review_pack.pk}))
        self.assertEqual(response.status_code, 200)
        self.review_pack.refresh_from_db()
        self.assertIn('[CROSS-DOCUMENT]', self.review_pack.review_memo)
        self.assertIn('DPA liability conflicts with "Payrollminds MSA" liability cap', self.review_pack.review_memo)
        self.assertIn('Linked MSA evidence:', self.review_pack.review_memo)

    def test_rerunning_analysis_does_not_duplicate_open_auto_detected_items(self):
        client = TestClient()
        client.login(username=self.admin.username, password='testpass123')
        client.post(reverse('contracts:dpa_review_run_analysis', kwargs={'pk': self.review_pack.pk}), data=json.dumps({}), content_type='application/json')
        first_count = self.review_pack.risk_items.count()
        client.post(reverse('contracts:dpa_review_run_analysis', kwargs={'pk': self.review_pack.pk}), data=json.dumps({}), content_type='application/json')
        second_count = self.review_pack.risk_items.count()
        self.assertEqual(first_count, second_count)

    def test_rerunning_analysis_preserves_resolved_items(self):
        client = TestClient()
        client.login(username=self.admin.username, password='testpass123')
        client.post(reverse('contracts:dpa_review_run_analysis', kwargs={'pk': self.review_pack.pk}), data=json.dumps({}), content_type='application/json')
        risk = self.review_pack.risk_items.first()
        risk.status = DPARiskItem.Status.RESOLVED
        risk.save()
        client.post(reverse('contracts:dpa_review_run_analysis', kwargs={'pk': self.review_pack.pk}), data=json.dumps({}), content_type='application/json')
        risk.refresh_from_db()
        self.assertEqual(risk.status, DPARiskItem.Status.RESOLVED)

    def test_only_admin_can_set_approval_status(self):
        client = TestClient()
        client.login(username='dpa_member', password='testpass123')
        response = client.post(
            reverse('contracts:dpa_review_set_approval_status', kwargs={'pk': self.review_pack.pk}),
            data=json.dumps({'status': 'APPROVED'}), content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        self.review_pack.refresh_from_db()
        self.assertEqual(self.review_pack.approval_status, DPAReviewPack.ApprovalStatus.DRAFT)

    def test_admin_can_set_approval_status_and_it_is_audit_logged(self):
        client = TestClient()
        client.login(username=self.admin.username, password='testpass123')
        response = client.post(
            reverse('contracts:dpa_review_set_approval_status', kwargs={'pk': self.review_pack.pk}),
            data=json.dumps({'status': 'APPROVED'}), content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.review_pack.refresh_from_db()
        self.assertEqual(self.review_pack.approval_status, DPAReviewPack.ApprovalStatus.APPROVED)
        self.assertEqual(self.review_pack.approved_by_id, self.admin.id)
        history = DPAApprovalHistoryEntry.objects.get(review_pack=self.review_pack)
        self.assertEqual(history.from_status, DPAReviewPack.ApprovalStatus.DRAFT)
        self.assertEqual(history.to_status, DPAReviewPack.ApprovalStatus.APPROVED)
        self.assertIsInstance(history.risk_counts_by_severity, dict)
        self.assertGreaterEqual(history.unresolved_blocker_count, 0)
        entry = AuditLog.objects.filter(model_name='DPAReviewPack', object_id=self.review_pack.pk).order_by('-timestamp').first()
        self.assertIsNotNone(entry)
        self.assertEqual((entry.changes or {}).get('event'), 'dpa_approval_status_changed')
        self.assertEqual((entry.changes or {}).get('new_status'), DPAReviewPack.ApprovalStatus.APPROVED)

    def test_invalid_approval_status_rejected(self):
        client = TestClient()
        client.login(username=self.admin.username, password='testpass123')
        response = client.post(
            reverse('contracts:dpa_review_set_approval_status', kwargs={'pk': self.review_pack.pk}),
            data=json.dumps({'status': 'NOT_A_REAL_STATUS'}), content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_risk_status_transition_is_logged_and_does_not_change_pack_approval(self):
        risk = DPARiskItem.objects.create(
            review_pack=self.review_pack,
            category=DPARiskItem.Category.BREACH_NOTIFICATION,
            title='Short breach notice',
            description='Needs review',
            severity=DPARiskItem.Severity.HIGH,
            owners='LEGAL',
        )
        client = TestClient()
        client.login(username=self.admin.username, password='testpass123')
        response = client.post(
            reverse('contracts:dpa_risk_item_set_status', kwargs={'pk': risk.pk}),
            data=json.dumps({'status': DPARiskItem.Status.NEEDS_DPO_SECURITY_INPUT}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        risk.refresh_from_db()
        self.review_pack.refresh_from_db()
        self.assertEqual(risk.status, DPARiskItem.Status.NEEDS_DPO_SECURITY_INPUT)
        self.assertEqual(self.review_pack.approval_status, DPAReviewPack.ApprovalStatus.DRAFT)
        entry = AuditLog.objects.filter(model_name='DPARiskItem', object_id=risk.pk).order_by('-timestamp').first()
        self.assertEqual((entry.changes or {}).get('event'), 'dpa_risk_item_status_changed')

    def test_reviewer_note_is_timestamped_and_available_for_memo(self):
        risk = DPARiskItem.objects.create(
            review_pack=self.review_pack,
            category=DPARiskItem.Category.SECURITY,
            title='Vague security',
            description='Needs DPO input',
            severity=DPARiskItem.Severity.MEDIUM,
            owners='DPO_SECURITY',
        )
        client = TestClient()
        client.login(username=self.admin.username, password='testpass123')
        response = client.post(
            reverse('contracts:dpa_risk_item_add_note', kwargs={'pk': risk.pk}),
            data=json.dumps({'note': 'Confirm TOM annex with security before approval.'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        note = DPARiskItemNote.objects.get(risk_item=risk)
        self.assertEqual(note.author, self.admin)
        self.assertIsNotNone(note.created_at)

        response = client.post(reverse('contracts:dpa_review_generate_memo', kwargs={'pk': self.review_pack.pk}))
        self.assertEqual(response.status_code, 200)
        self.review_pack.refresh_from_db()
        self.assertIn('Confirm TOM annex with security before approval.', self.review_pack.review_memo)


class DPACrossTenantIsolationTests(TestCase):
    def setUp(self):
        self.org_a, self.user_a, self.contract_a = _make_org_and_contract(org_slug='dpa-iso-a')
        self.org_b, self.user_b, _ = _make_org_and_contract(org_slug='dpa-iso-b')
        self.review_pack_a = DPAReviewPack.objects.create(organization=self.org_a, contract=self.contract_a, created_by=self.user_a)

    def test_other_org_member_does_not_see_review_pack(self):
        client = TestClient()
        client.login(username=self.user_b.username, password='testpass123')
        response = client.get(reverse('contracts:dpa_review_pack_list'))
        ids = [p.id for p in response.context['review_packs']]
        self.assertNotIn(self.review_pack_a.id, ids)

    def test_other_org_member_gets_404_on_detail(self):
        client = TestClient()
        client.login(username=self.user_b.username, password='testpass123')
        response = client.get(reverse('contracts:dpa_review_pack_detail', kwargs={'pk': self.review_pack_a.pk}))
        self.assertEqual(response.status_code, 404)

    def test_other_org_member_cannot_run_analysis(self):
        client = TestClient()
        client.login(username=self.user_b.username, password='testpass123')
        response = client.post(
            reverse('contracts:dpa_review_run_analysis', kwargs={'pk': self.review_pack_a.pk}),
            data=json.dumps({}), content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)

    def test_other_org_member_cannot_set_approval_status(self):
        client = TestClient()
        client.login(username=self.user_b.username, password='testpass123')
        response = client.post(
            reverse('contracts:dpa_review_set_approval_status', kwargs={'pk': self.review_pack_a.pk}),
            data=json.dumps({'status': 'APPROVED'}), content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)


class DPAPlaybookListViewTests(TestCase):
    def setUp(self):
        self.organization, self.user, _ = _make_org_and_contract(org_slug='dpa-playbook-firm')
        DPAPlaybookPosition.objects.get_or_create(
            organization=None, topic=DPAPlaybookPosition.Topic.LIABILITY,
            defaults={'our_position': 'Stay within the MSA cap.', 'owner': 'LEGAL'},
        )

    def test_playbook_list_renders_global_positions(self):
        client = TestClient()
        client.login(username=self.user.username, password='testpass123')
        response = client.get(reverse('contracts:dpa_playbook_list'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('Stay within the MSA cap.', response.content.decode())

    def test_org_specific_position_overrides_global_default(self):
        DPAPlaybookPosition.objects.create(
            organization=self.organization, topic=DPAPlaybookPosition.Topic.LIABILITY,
            our_position='Org-specific override position.', owner='LEGAL',
        )
        client = TestClient()
        client.login(username=self.user.username, password='testpass123')
        response = client.get(reverse('contracts:dpa_playbook_list'))
        body = response.content.decode()
        self.assertIn('Org-specific override position.', body)
        self.assertNotIn('Stay within the MSA cap.', body)


class DPACopyQualityTests(TestCase):
    def setUp(self):
        self.organization, self.user, self.contract = _make_org_and_contract(org_slug='dpa-copy-firm')
        self.review_pack = DPAReviewPack.objects.create(organization=self.organization, contract=self.contract, created_by=self.user)
        run_dpa_analysis(self.review_pack)
        self.review_pack.save()

    def test_no_raw_internals_on_detail_page(self):
        client = TestClient()
        client.login(username=self.user.username, password='testpass123')
        url = reverse('contracts:dpa_review_pack_detail', kwargs={'pk': self.review_pack.pk})
        response = client.get(f'{url}?tab=findings')
        self.assertEqual(response.status_code, 200)
        body = response.content.decode().split('<div id="djDebug"', 1)[0]
        self.assertNotIn('DPAReviewPack', body)
        self.assertNotIn('DPO_SECURITY', body)
        self.assertIn('DPO/Security', body)
        self.assertIsNone(ISO_TIMESTAMP_RE.search(body), 'Found a raw ISO timestamp in the DPA review detail response')

    def test_approval_status_shows_human_label_not_raw_enum(self):
        client = TestClient()
        client.login(username=self.user.username, password='testpass123')
        response = client.get(reverse('contracts:dpa_review_pack_list'))
        body = response.content.decode()
        self.assertIn('Draft', body)
