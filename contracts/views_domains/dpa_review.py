"""DPA Review Pack — first-class Data Processing Agreement review module.

Analysis (contracts.services.dpa_review.run_dpa_analysis,
contracts.services.dpa_conflict.check_cross_document_conflicts) only ever
produces suggestions: it updates the checklist fields on a DPAReviewPack
and returns candidate DPARiskItem specs. It never touches approval_status.
Final approval is a separate, explicit, permission-gated human action
(dpa_review_set_approval_status) — there is no code path that sets
DPAReviewPack.approval_status to APPROVED except that view, and every
change is recorded in both AuditLog and the DPA-scoped
DPAApprovalHistoryEntry.
"""
import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Exists, OuterRef, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView

from contracts.middleware import log_action
from contracts.models import (
    AuditLog,
    Contract,
    DPAApprovalHistoryEntry,
    DPAPlaybookPosition,
    DPAReviewPack,
    DPARiskItem,
    DPARiskItemNote,
)
from contracts.permissions import ContractAction, can_access_contract_action, can_manage_organization
from contracts.services.assignments import QUEUE_EMPTY_PERSONAL, reviewer_privacy_packs_queryset
from contracts.services.dpa_conflict import check_cross_document_conflicts
from contracts.services.dpa_review import generate_review_memo, run_dpa_analysis
from contracts.tenancy import get_user_organization
from contracts.view_support import TenantScopedQuerysetMixin


def _can_review_pack(user, review_pack):
    return can_manage_organization(user, review_pack.organization) or review_pack.reviewer_id == user.id


DPA_APPROVAL_TRANSITIONS = {
    DPAReviewPack.ApprovalStatus.DRAFT: {
        DPAReviewPack.ApprovalStatus.UNDER_REVIEW,
        DPAReviewPack.ApprovalStatus.APPROVED,
        DPAReviewPack.ApprovalStatus.REJECTED,
    },
    DPAReviewPack.ApprovalStatus.UNDER_REVIEW: {
        DPAReviewPack.ApprovalStatus.APPROVED,
        DPAReviewPack.ApprovalStatus.REJECTED,
        DPAReviewPack.ApprovalStatus.ESCALATED,
        DPAReviewPack.ApprovalStatus.DRAFT,
    },
    DPAReviewPack.ApprovalStatus.ESCALATED: {
        DPAReviewPack.ApprovalStatus.APPROVED,
        DPAReviewPack.ApprovalStatus.REJECTED,
        DPAReviewPack.ApprovalStatus.UNDER_REVIEW,
    },
    DPAReviewPack.ApprovalStatus.APPROVED: set(),
    DPAReviewPack.ApprovalStatus.REJECTED: {DPAReviewPack.ApprovalStatus.DRAFT},
}


_RESOLVED_RISK_STATUSES = frozenset({
    DPARiskItem.Status.RESOLVED,
    DPARiskItem.Status.ACCEPTED_RISK,
    DPARiskItem.Status.FALSE_POSITIVE,
})

_APPROVAL_GATE_STATUSES = frozenset({
    DPAReviewPack.ApprovalStatus.UNDER_REVIEW,
    DPAReviewPack.ApprovalStatus.ESCALATED,
})

_REVIEW_STATUS_TONES = {
    DPAReviewPack.ApprovalStatus.DRAFT: 'neutral',
    DPAReviewPack.ApprovalStatus.UNDER_REVIEW: 'progress',
    DPAReviewPack.ApprovalStatus.ESCALATED: 'danger',
    DPAReviewPack.ApprovalStatus.APPROVED: 'success',
    DPAReviewPack.ApprovalStatus.REJECTED: 'danger',
}


def _unresolved_risks(pack):
    return [risk for risk in pack.risk_items.all() if risk.status not in _RESOLVED_RISK_STATUSES]


def _next_action_for_pack(pack, unresolved_risks, critical_risk_count, conflict_count=0):
    """Surface the highest-priority unresolved work for the review queue."""
    if pack.role_qualification == DPAReviewPack.RoleQualification.AMBIGUOUS:
        return 'Resolve role qualification'
    if conflict_count:
        return 'Resolve cross-document conflicts'
    if critical_risk_count:
        return 'Address critical risks'
    if unresolved_risks:
        return 'Resolve open risks'
    if pack.approval_status == DPAReviewPack.ApprovalStatus.DRAFT:
        return 'Start review'
    if pack.approval_status == DPAReviewPack.ApprovalStatus.UNDER_REVIEW:
        return 'Complete approval decision'
    if pack.approval_status == DPAReviewPack.ApprovalStatus.ESCALATED:
        return 'Resolve escalation'
    if pack.approval_status == DPAReviewPack.ApprovalStatus.REJECTED:
        return 'Revise after rejection'
    return 'View review pack'


def _review_status_label(pack):
    """Use approval wording only when the pack is sitting at an approval gate."""
    if pack.approval_status == DPAReviewPack.ApprovalStatus.UNDER_REVIEW:
        return 'Awaiting approval'
    if pack.approval_status == DPAReviewPack.ApprovalStatus.ESCALATED:
        return 'Escalated for approval'
    return pack.get_approval_status_display()


# Short queue labels — long model displays wrap poorly in compact table cells.
_ROLE_LIST_LABELS = {
    DPAReviewPack.RoleQualification.AMBIGUOUS: 'Role unclear',
    DPAReviewPack.RoleQualification.CONTROLLER_PROCESSOR: 'Controller / Processor',
    DPAReviewPack.RoleQualification.JOINT_CONTROLLER: 'Joint controller',
    DPAReviewPack.RoleQualification.INDEPENDENT_CONTROLLER: 'Independent controller',
}

_REVIEW_STATUS_LIST_LABELS = {
    DPAReviewPack.ApprovalStatus.UNDER_REVIEW: 'Awaiting approval',
    DPAReviewPack.ApprovalStatus.ESCALATED: 'Escalated',
}


def _role_list_label(pack):
    return _ROLE_LIST_LABELS.get(
        pack.role_qualification,
        pack.get_role_qualification_display(),
    )


def _review_status_list_label(pack):
    return _REVIEW_STATUS_LIST_LABELS.get(
        pack.approval_status,
        _review_status_label(pack),
    )


_NEEDS_INPUT_STATUSES = {
    DPARiskItem.Status.NEEDS_BUSINESS_INPUT,
    DPARiskItem.Status.NEEDS_DPO_SECURITY_INPUT,
}
_OPENISH_RISK_STATUSES = {
    DPARiskItem.Status.OPEN,
    DPARiskItem.Status.IN_REVIEW,
    DPARiskItem.Status.NEEDS_BUSINESS_INPUT,
    DPARiskItem.Status.NEEDS_DPO_SECURITY_INPUT,
    DPARiskItem.Status.ESCALATED,
}
_CATEGORY_STATE_TONES = {
    'risk': 'danger',
    'needs_input': 'attention',
    'confirmed': 'success',
    'not_applicable': 'neutral',
    'not_reviewed': 'neutral',
}
_CATEGORY_STATE_LABELS = {
    'risk': 'Risk',
    'needs_input': 'Needs input',
    'confirmed': 'Confirmed',
    'not_applicable': 'Not applicable',
    'not_reviewed': 'Not reviewed',
}


def _risk_summary_for_pack(risk_items):
    unresolved = [r for r in risk_items if r.status not in _RESOLVED_RISK_STATUSES]
    by_severity = {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
    for risk in unresolved:
        by_severity[risk.severity] = by_severity.get(risk.severity, 0) + 1
    return {
        'total': len(risk_items),
        'open': len(unresolved),
        'critical': by_severity['CRITICAL'],
        'high': by_severity['HIGH'],
        'medium': by_severity['MEDIUM'],
        'low': by_severity['LOW'],
        'needs_input': sum(1 for r in unresolved if r.status in _NEEDS_INPUT_STATUSES),
    }


def _category_state(category_risks, reviewed, applicable=True):
    """Derive a compact review state — risk and decision over raw extraction."""
    if not applicable:
        return 'not_applicable'
    open_risks = [r for r in category_risks if r.status in _OPENISH_RISK_STATUSES]
    if any(r.severity in {DPARiskItem.Severity.CRITICAL, DPARiskItem.Severity.HIGH} for r in open_risks):
        return 'risk'
    if any(
        r.status in _NEEDS_INPUT_STATUSES or r.confidence == DPARiskItem.Confidence.NEEDS_HUMAN_CHECK
        for r in open_risks
    ):
        return 'needs_input'
    if open_risks:
        return 'risk'
    if not reviewed:
        return 'not_reviewed'
    return 'confirmed'


def _build_review_categories(pack, risk_items):
    """Numbered review categories as expandable rows with decision-first states."""
    by_category = {}
    for risk in risk_items:
        by_category.setdefault(risk.category, []).append(risk)

    analyzed = bool(pack.last_analyzed_at)
    payroll_flags = [
        pack.has_employee_identity_data,
        pack.has_salary_wage_data,
        pack.has_tax_data,
        pack.has_social_security_data,
        pack.has_bank_account_data,
        pack.has_pension_benefits_data,
        pack.has_absence_leave_data,
        pack.has_employment_contract_data,
        pack.has_national_identifiers,
        pack.has_payroll_corrections,
        pack.has_payslip_data,
        pack.has_cross_border_payroll_data,
    ]
    security_flags = [
        pack.security_encryption,
        pack.security_access_control,
        pack.security_mfa,
        pack.security_logging,
        pack.security_backup,
        pack.security_incident_response,
        pack.security_data_segregation,
    ]
    processing_filled = any(
        [
            pack.data_subject_categories,
            pack.personal_data_categories,
            pack.special_category_data,
            pack.processing_purposes,
            pack.processing_duration,
            pack.retention_obligations,
            pack.systems_tools_vendors,
        ]
    )

    specs = [
        {
            'number': 1,
            'key': 'role',
            'title': 'Role Qualification',
            'risk_category': DPARiskItem.Category.ROLE_QUALIFICATION,
            'summary': pack.get_role_qualification_display(),
            'details': [
                ('Qualification', pack.get_role_qualification_display()),
                ('Notes', pack.role_qualification_notes or '—'),
                ('Subprocessors involved', 'Yes' if pack.subprocessors_involved else 'No'),
            ],
            'reviewed': analyzed or pack.role_qualification != DPAReviewPack.RoleQualification.AMBIGUOUS,
            'applicable': True,
        },
        {
            'number': 2,
            'key': 'processing',
            'title': 'Processing Description',
            'risk_category': DPARiskItem.Category.PROCESSING_SCOPE,
            'summary': (
                (pack.processing_purposes or pack.data_subject_categories or 'Processing scope not yet captured')[:120]
            ),
            'details': [
                ('Data subjects', pack.data_subject_categories or '—'),
                ('Personal data', pack.personal_data_categories or '—'),
                ('Special category', pack.special_category_data or '—'),
                ('Purposes', pack.processing_purposes or '—'),
                ('Duration', pack.processing_duration or '—'),
                ('Retention', pack.retention_obligations or '—'),
                ('Systems / vendors', pack.systems_tools_vendors or '—'),
            ],
            'reviewed': analyzed or processing_filled,
            'applicable': True,
        },
        {
            'number': 3,
            'key': 'payroll',
            'title': 'Payroll-Specific Data Categories',
            'risk_category': DPARiskItem.Category.PROCESSING_SCOPE,
            'summary': (
                f'{sum(1 for flag in payroll_flags if flag)} of {len(payroll_flags)} payroll categories present'
            ),
            'details': [
                (label, 'Present' if getattr(pack, field) else 'Not present')
                for field, label in (
                    ('has_employee_identity_data', 'Employee identity data'),
                    ('has_salary_wage_data', 'Salary / wage data'),
                    ('has_tax_data', 'Tax data'),
                    ('has_social_security_data', 'Social security data'),
                    ('has_bank_account_data', 'Bank account details'),
                    ('has_pension_benefits_data', 'Pension / benefits data'),
                    ('has_absence_leave_data', 'Absence / leave data'),
                    ('has_employment_contract_data', 'Employment contract data'),
                    ('has_national_identifiers', 'National identifiers'),
                    ('has_payroll_corrections', 'Payroll corrections'),
                    ('has_payslip_data', 'Payslip data'),
                    ('has_cross_border_payroll_data', 'Cross-border payroll data'),
                )
            ],
            'reviewed': analyzed,
            'applicable': analyzed or any(payroll_flags),
        },
        {
            'number': 4,
            'key': 'subprocessor',
            'title': 'Subprocessor / Vendor Review',
            'risk_category': DPARiskItem.Category.SUBPROCESSOR,
            'summary': (
                'Prior approval required'
                if pack.subprocessor_prior_approval_required
                else (
                    'General authorization allowed'
                    if pack.subprocessor_general_authorization_allowed
                    else 'Subprocessor controls not confirmed'
                )
            ),
            'details': [
                ('Prior approval required', 'Yes' if pack.subprocessor_prior_approval_required else 'No'),
                ('General authorization', 'Yes' if pack.subprocessor_general_authorization_allowed else 'No'),
                (
                    'Notification period',
                    f'{pack.subprocessor_notification_period_days} days'
                    if pack.subprocessor_notification_period_days is not None
                    else 'Not specified',
                ),
                (
                    'Linked subprocessors',
                    ', '.join(sp.name for sp in pack.subprocessors.all()) or 'None linked',
                ),
            ],
            'reviewed': analyzed,
            'applicable': True,
        },
        {
            'number': 5,
            'key': 'transfer',
            'title': 'International Transfer Review',
            'risk_category': DPARiskItem.Category.TRANSFER,
            'summary': (
                'Transfers outside EEA — mechanism review required'
                if pack.transfers_outside_eea
                else 'No EEA-outbound transfers flagged'
            ),
            'details': [
                ('Transfers outside EEA', 'Yes' if pack.transfers_outside_eea else 'No'),
                ('Transfer mechanism present', 'Yes' if pack.transfer_mechanism_present else 'No'),
                ('DPO/Security escalation', 'Yes' if pack.transfer_escalation_required else 'No'),
                ('Notes', pack.transfer_notes or '—'),
            ],
            'reviewed': analyzed,
            'applicable': (not analyzed)
            or pack.transfers_outside_eea
            or bool(by_category.get(DPARiskItem.Category.TRANSFER)),
        },
        {
            'number': 6,
            'key': 'security',
            'title': 'Security Measures',
            'risk_category': DPARiskItem.Category.SECURITY,
            'summary': (
                'Specific measures described'
                if pack.security_measures_specific
                else (
                    f'{sum(1 for flag in security_flags if flag)} controls mentioned — specificity unclear'
                    if any(security_flags)
                    else 'Security measures not confirmed'
                )
            ),
            'details': [
                (label, 'Present' if getattr(pack, field) else 'Not present')
                for field, label in (
                    ('security_encryption', 'Encryption'),
                    ('security_access_control', 'Access control'),
                    ('security_mfa', 'Multi-factor authentication'),
                    ('security_logging', 'Logging'),
                    ('security_backup', 'Backup'),
                    ('security_incident_response', 'Incident response'),
                    ('security_data_segregation', 'Data segregation'),
                )
            ]
            + [
                (
                    'Specificity',
                    'Specific' if pack.security_measures_specific else 'Vague / generic',
                ),
                ('Notes', pack.security_notes or '—'),
            ],
            'reviewed': analyzed,
            'applicable': True,
        },
        {
            'number': 7,
            'key': 'breach',
            'title': 'Breach Notification',
            'risk_category': DPARiskItem.Category.BREACH_NOTIFICATION,
            'summary': (
                f'{pack.breach_notification_deadline_hours}h deadline'
                + ('' if pack.breach_notification_realistic else ' — may be unrealistic')
                if pack.breach_notification_deadline_hours is not None
                else 'Deadline not specified'
            ),
            'details': [
                (
                    'Deadline',
                    f'{pack.breach_notification_deadline_hours} hours'
                    if pack.breach_notification_deadline_hours is not None
                    else 'Not specified',
                ),
                ('Realistic', 'Yes' if pack.breach_notification_realistic else 'No'),
                ('Conflicts with MSA', 'Yes' if pack.breach_notification_conflicts_msa else 'No'),
                ('Notes', pack.breach_notification_notes or '—'),
            ],
            'reviewed': analyzed or pack.breach_notification_deadline_hours is not None,
            'applicable': True,
        },
        {
            'number': 8,
            'key': 'dsar',
            'title': 'Data Subject Request Assistance',
            'risk_category': DPARiskItem.Category.DSAR,
            'summary': (
                'Assistance required'
                + (
                    f' · {pack.dsar_assistance_deadline_days} days'
                    if pack.dsar_assistance_deadline_days is not None
                    else ''
                )
                if pack.dsar_assistance_required
                else 'Assistance not required / not confirmed'
            ),
            'details': [
                ('Assistance required', 'Yes' if pack.dsar_assistance_required else 'No'),
                (
                    'Deadline',
                    f'{pack.dsar_assistance_deadline_days} days'
                    if pack.dsar_assistance_deadline_days is not None
                    else 'Not specified',
                ),
                ('Chargeable', 'Yes' if pack.dsar_assistance_chargeable else 'No'),
                ('Business confirmation needed', 'Yes' if pack.dsar_business_confirmation_needed else 'No'),
            ],
            'reviewed': analyzed,
            'applicable': True,
        },
        {
            'number': 9,
            'key': 'audit',
            'title': 'Audit Rights',
            'risk_category': DPARiskItem.Category.AUDIT,
            'summary': (
                'On-site audit allowed'
                if pack.audit_rights_onsite_allowed
                else (
                    'Third-party reports accepted'
                    if pack.audit_third_party_reports_accepted
                    else 'Audit rights not confirmed'
                )
            ),
            'details': [
                ('On-site allowed', 'Yes' if pack.audit_rights_onsite_allowed else 'No'),
                ('Frequency limited', 'Yes' if pack.audit_rights_frequency_limited else 'No'),
                ('Third-party reports', 'Yes' if pack.audit_third_party_reports_accepted else 'No'),
                ('Costs addressed', 'Yes' if pack.audit_costs_addressed else 'No'),
                ('Conflicts with MSA', 'Yes' if pack.audit_conflicts_msa else 'No'),
                ('Notes', pack.audit_notes or '—'),
            ],
            'reviewed': analyzed,
            'applicable': True,
        },
        {
            'number': 10,
            'key': 'deletion',
            'title': 'Deletion and Return',
            'risk_category': DPARiskItem.Category.DELETION,
            'summary': (
                f'{pack.deletion_return_deadline_days}-day return / deletion window'
                if pack.deletion_return_deadline_days is not None
                else 'Deletion / return deadline not specified'
            ),
            'details': [
                (
                    'Deadline',
                    f'{pack.deletion_return_deadline_days} days'
                    if pack.deletion_return_deadline_days is not None
                    else 'Not specified',
                ),
                ('Statutory retention conflict', 'Yes' if pack.deletion_legal_retention_conflict else 'No'),
                ('Backup addressed', 'Yes' if pack.deletion_backup_addressed else 'No'),
                ('Certification required', 'Yes' if pack.deletion_certification_required else 'No'),
                ('Notes', pack.deletion_notes or '—'),
            ],
            'reviewed': analyzed or pack.deletion_return_deadline_days is not None,
            'applicable': True,
        },
        {
            'number': 11,
            'key': 'liability',
            'title': 'Liability Conflict Detection',
            'risk_category': DPARiskItem.Category.LIABILITY,
            'summary': (
                'Uncapped or MSA-cap override risk'
                if pack.liability_uncapped or pack.liability_overrides_msa_cap
                else 'No liability conflict flagged'
            ),
            'details': [
                ('Uncapped', 'Yes' if pack.liability_uncapped else 'No'),
                ('Overrides MSA cap', 'Yes' if pack.liability_overrides_msa_cap else 'No'),
                ('Separate indemnities', 'Yes' if pack.liability_separate_indemnities else 'No'),
                ('Conflicts standard position', 'Yes' if pack.liability_conflicts_standard_position else 'No'),
                ('Notes', pack.liability_notes or '—'),
            ],
            'reviewed': analyzed,
            'applicable': True,
        },
    ]

    rows = []
    for spec in specs:
        category_risks = by_category.get(spec['risk_category'], [])
        # Payroll shares PROCESSING_SCOPE with processing description — only
        # attach scope risks to the processing row to avoid duplicate banners.
        if spec['key'] == 'payroll':
            category_risks = []
        state = _category_state(category_risks, reviewed=spec['reviewed'], applicable=spec['applicable'])
        open_count = sum(1 for r in category_risks if r.status in _OPENISH_RISK_STATUSES)
        decision_summary = spec['summary']
        if state == 'risk' and open_count:
            decision_summary = f'{open_count} open risk{"s" if open_count != 1 else ""} — {spec["summary"]}'
        elif state == 'needs_input':
            decision_summary = f'Needs human input — {spec["summary"]}'
        rows.append(
            {
                **spec,
                'state': state,
                'state_label': _CATEGORY_STATE_LABELS[state],
                'state_tone': _CATEGORY_STATE_TONES[state],
                'open_risk_count': open_count,
                'decision_summary': decision_summary,
                'risks': category_risks,
            }
        )
    return rows


def _primary_action_for_pack(pack, unresolved_risks, critical_risk_count, can_edit, can_approve):
    """One contextual primary CTA for the review header."""
    next_action = _next_action_for_pack(pack, unresolved_risks, critical_risk_count)
    if next_action == 'Resolve role qualification':
        return {
            'label': 'Review findings',
            'href': '?tab=findings',
            'mode': 'link',
            'next_action': next_action,
        }
    if next_action in {'Address critical risks', 'Resolve open risks'}:
        return {
            'label': 'Open risks',
            'href': '?tab=risks',
            'mode': 'link',
            'next_action': next_action,
        }
    if next_action == 'Start review' and can_edit and not pack.last_analyzed_at:
        return {
            'label': 'Run analysis',
            'mode': 'analyze',
            'next_action': next_action,
        }
    if next_action in {'Complete approval decision', 'Resolve escalation', 'Revise after rejection'} and can_approve:
        return {
            'label': 'Record decision',
            'href': '#dpa-decision-bar',
            'mode': 'link',
            'next_action': next_action,
        }
    if next_action == 'Start review' and can_approve:
        return {
            'label': 'Start review',
            'href': '#dpa-decision-bar',
            'mode': 'link',
            'next_action': next_action,
        }
    return {
        'label': 'View findings',
        'href': '?tab=findings',
        'mode': 'link',
        'next_action': next_action,
    }


def _workspace_tabs_for_pack(pack, active_tab):
    base = reverse('contracts:dpa_review_pack_detail', kwargs={'pk': pack.pk})
    tabs = (
        ('overview', 'Overview'),
        ('findings', 'Findings'),
        ('risks', 'Risks'),
        ('documents', 'Documents'),
        ('history', 'Decision history'),
    )
    return [
        {
            'key': key,
            'label': label,
            'url': f'{base}?tab={key}',
            'active': key == active_tab,
            'panel_id': f'dpa-tab-{key}',
        }
        for key, label in tabs
    ]


class DPAReviewPackListView(TenantScopedQuerysetMixin, LoginRequiredMixin, ListView):
    """Operational DPA review queue: unresolved work, filters, and next actions."""
    model = DPAReviewPack
    template_name = 'contracts/dpa_review_pack_list.html'
    context_object_name = 'review_packs'

    def get_queryset(self):
        org = get_user_organization(self.request.user)
        if not org:
            return DPAReviewPack.objects.none()
        qs = (
            DPAReviewPack.objects.filter(organization=org)
            .select_related('contract', 'counterparty', 'reviewer')
            .prefetch_related('risk_items')
            .order_by('-updated_at')
        )
        params = self.request.GET
        selected_view = (params.get('view') or '').strip()
        if selected_view == 'my_reviews':
            qs = reviewer_privacy_packs_queryset(org, self.request.user)
        search = (params.get('q') or '').strip()
        if search:
            qs = qs.filter(
                Q(contract__title__icontains=search)
                | Q(counterparty__name__icontains=search)
                | Q(reviewer__first_name__icontains=search)
                | Q(reviewer__last_name__icontains=search)
                | Q(reviewer__username__icontains=search)
            )
        status = (params.get('status') or '').strip()
        if status in {choice.value for choice in DPAReviewPack.ApprovalStatus}:
            qs = qs.filter(approval_status=status)
        role = (params.get('role') or '').strip()
        if role in {choice.value for choice in DPAReviewPack.RoleQualification}:
            qs = qs.filter(role_qualification=role)
        owner = (params.get('owner') or '').strip()
        if owner == 'unassigned':
            qs = qs.filter(reviewer__isnull=True)
        elif owner.isdigit():
            qs = qs.filter(reviewer_id=int(owner))
        severity = (params.get('severity') or '').strip()
        if severity in {choice.value for choice in DPARiskItem.Severity}:
            open_severity = DPARiskItem.objects.filter(
                review_pack_id=OuterRef('pk'),
                severity=severity,
            ).exclude(status__in=_RESOLVED_RISK_STATUSES)
            qs = qs.filter(Exists(open_severity))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        packs = list(ctx['review_packs'])
        org = get_user_organization(self.request.user)
        # Metrics reflect the full org queue so the strip stays an operational
        # pulse even when the table is filtered.
        all_packs = list(
            DPAReviewPack.objects.filter(organization=org)
            .prefetch_related('risk_items')
            .select_related('reviewer')
        ) if org else []

        ctx['playbook_url'] = reverse('contracts:dpa_playbook_list')
        ctx['start_dpa_url'] = reverse('contracts:dpa_workflow_builder')
        ctx['upload_dpa_url'] = reverse('contracts:upload_signed_contract')
        ctx['can_manage_playbook'] = bool(org and can_manage_organization(self.request.user, org))
        ctx['total_packs'] = len(all_packs)
        ctx['needs_decision_count'] = sum(
            1 for p in all_packs
            if p.approval_status in (
                DPAReviewPack.ApprovalStatus.DRAFT,
                DPAReviewPack.ApprovalStatus.UNDER_REVIEW,
            )
        )
        # Keep the legacy key for existing callers/tests.
        ctx['pending_approval_count'] = ctx['needs_decision_count']
        ctx['escalated_count'] = sum(
            1 for p in all_packs if p.approval_status == DPAReviewPack.ApprovalStatus.ESCALATED
        )
        open_risks = [
            risk for pack in all_packs for risk in _unresolved_risks(pack)
        ]
        ctx['open_risk_count'] = len(open_risks)
        ctx['open_critical_risk_count'] = sum(
            1 for risk in open_risks if risk.severity == DPARiskItem.Severity.CRITICAL
        )

        params = self.request.GET
        selected_view = (params.get('view') or '').strip()
        ctx['search_query'] = (params.get('q') or '').strip()
        ctx['selected_status'] = (params.get('status') or '').strip()
        ctx['selected_role'] = (params.get('role') or '').strip()
        ctx['selected_severity'] = (params.get('severity') or '').strip()
        ctx['selected_owner'] = (params.get('owner') or '').strip()
        ctx['selected_view'] = selected_view
        list_url = reverse('contracts:dpa_review_pack_list')
        selected_status = ctx['selected_status']
        selected_severity = ctx['selected_severity']
        ctx['view_tabs'] = [
            {
                'key': 'all',
                'label': 'All reviews',
                'url': list_url,
                'active': not selected_status and not selected_severity and selected_view != 'my_reviews',
            },
            {
                'key': 'my_reviews',
                'label': 'My reviews',
                'url': f'{list_url}?view=my_reviews',
                'active': selected_view == 'my_reviews',
            },
            {
                'key': 'needs_decision',
                'label': 'Needs decision',
                'url': f'{list_url}?status=UNDER_REVIEW',
                'active': selected_status == 'UNDER_REVIEW',
            },
            {
                'key': 'critical',
                'label': 'Critical risks',
                'url': f'{list_url}?severity=CRITICAL',
                'active': selected_severity == 'CRITICAL',
            },
        ]
        ctx['review_status_choices'] = DPAReviewPack.ApprovalStatus.choices
        ctx['processing_role_choices'] = DPAReviewPack.RoleQualification.choices
        ctx['risk_severity_choices'] = DPARiskItem.Severity.choices
        owner_options = []
        seen_owners = set()
        for pack in all_packs:
            if pack.reviewer_id and pack.reviewer_id not in seen_owners:
                seen_owners.add(pack.reviewer_id)
                owner_options.append(pack.reviewer)
        owner_options.sort(key=lambda u: (u.get_full_name() or u.username).lower())
        ctx['owner_choices'] = owner_options

        rows = []
        for pack in packs:
            unresolved_risks = _unresolved_risks(pack)
            critical_risk_count = sum(
                1 for risk in unresolved_risks
                if risk.severity == DPARiskItem.Severity.CRITICAL
            )
            conflict_count = sum(
                1 for risk in unresolved_risks
                if getattr(risk, 'is_cross_document_conflict', False)
            )
            from contracts.services.governance_ux import privacy_blocker_for_pack
            blocker = privacy_blocker_for_pack(
                pack,
                unresolved_critical=critical_risk_count,
                conflict_count=conflict_count,
            )
            role_is_ambiguous = (
                pack.role_qualification == DPAReviewPack.RoleQualification.AMBIGUOUS
            )
            at_approval_gate = pack.approval_status in _APPROVAL_GATE_STATUSES
            risks_url = f"{reverse('contracts:dpa_review_pack_detail', kwargs={'pk': pack.pk})}?tab=risks"
            rows.append({
                'pack': pack,
                'detail_url': reverse('contracts:dpa_review_pack_detail', kwargs={'pk': pack.pk}),
                'risks_url': risks_url,
                'memo_url': reverse('contracts:dpa_review_pack_memo', kwargs={'pk': pack.pk}),
                'contract_url': reverse('contracts:contract_detail', kwargs={'pk': pack.contract_id}),
                'unresolved_risk_count': len(unresolved_risks),
                'critical_risk_count': critical_risk_count,
                'conflict_count': conflict_count,
                'is_blocked': blocker['is_blocked'],
                'blocking_issue': blocker['blocking_issue'],
                'blocker_owner': blocker['blocker_owner'],
                'priority_reason': (
                    'Cross-document conflicts blocking completion' if conflict_count
                    else f'{critical_risk_count} critical risk{"s" if critical_risk_count != 1 else ""} open'
                    if critical_risk_count else ''
                ),
                'priority_label': (
                    'Critical' if critical_risk_count or conflict_count else ''
                ),
                'priority_tone': 'danger' if critical_risk_count or conflict_count else 'neutral',
                'risk_tone': 'danger' if unresolved_risks else 'success',
                'approval_tone': _REVIEW_STATUS_TONES.get(pack.approval_status, 'neutral'),
                'review_status_label': _review_status_list_label(pack),
                'at_approval_gate': at_approval_gate,
                'role_label': _role_list_label(pack),
                'role_tone': 'attention' if role_is_ambiguous else 'neutral',
                'role_is_ambiguous': role_is_ambiguous,
                'owner_label': (
                    (pack.reviewer.get_full_name() or pack.reviewer.username)
                    if pack.reviewer_id else 'Unassigned'
                ),
                'next_action': _next_action_for_pack(
                    pack, unresolved_risks, critical_risk_count, conflict_count=conflict_count,
                ),
            })
        ctx['review_pack_rows'] = rows
        if selected_view == 'my_reviews' and not rows:
            title, copy, how = QUEUE_EMPTY_PERSONAL['privacy_mine']
            ctx['privacy_empty_state'] = {
                'title': title,
                'copy': copy,
                'how': how,
                'personal_hub': True,
            }
        return ctx


class DPAReviewPackDetailView(TenantScopedQuerysetMixin, LoginRequiredMixin, DetailView):
    model = DPAReviewPack
    template_name = 'contracts/dpa_review_pack_detail.html'
    context_object_name = 'review_pack'

    def get_queryset(self):
        org = get_user_organization(self.request.user)
        if not org:
            return DPAReviewPack.objects.none()
        return (
            DPAReviewPack.objects.filter(organization=org)
            .select_related('contract', 'counterparty', 'matter', 'reviewer')
            .prefetch_related('risk_items__notes__author', 'subprocessors', 'transfer_records', 'related_contracts', 'documents', 'approval_history__changed_by')
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        review_pack = ctx['review_pack']
        risk_items = list(review_pack.risk_items.all())
        unresolved = [r for r in risk_items if r.status not in _RESOLVED_RISK_STATUSES]
        critical_count = sum(1 for r in unresolved if r.severity == DPARiskItem.Severity.CRITICAL)
        risk_summary = _risk_summary_for_pack(risk_items)
        can_edit = can_access_contract_action(self.request.user, review_pack.contract, ContractAction.EDIT)
        can_review = _can_review_pack(self.request.user, review_pack)
        primary = _primary_action_for_pack(
            review_pack, unresolved, critical_count, can_edit=can_edit, can_approve=can_review,
        )
        active_tab = (self.request.GET.get('tab') or 'overview').strip().lower()
        allowed_tabs = {'overview', 'findings', 'risks', 'documents', 'history'}
        if active_tab not in allowed_tabs:
            active_tab = 'overview'

        review_categories = _build_review_categories(review_pack, risk_items)
        ctx['risk_items'] = risk_items
        ctx['open_risks'] = unresolved
        ctx['review_categories'] = review_categories
        ctx['key_findings'] = [
            row for row in review_categories if row['state'] in {'risk', 'needs_input'}
        ][:5]
        ctx['approval_history'] = review_pack.approval_history.all()
        ctx['can_edit'] = can_edit
        ctx['can_review'] = can_review
        ctx['can_approve'] = can_review
        ctx['risk_summary'] = risk_summary
        ctx['active_tab'] = active_tab
        ctx['workspace_tabs'] = _workspace_tabs_for_pack(review_pack, active_tab)
        ctx['review_command'] = {
            'next_action': primary['next_action'],
            'primary_action': primary,
            'show_primary_action': True,
            'owner_label': (
                review_pack.reviewer.get_full_name() or review_pack.reviewer.username
                if review_pack.reviewer_id
                else 'Unassigned'
            ),
            'status_label': _review_status_label(review_pack),
            'risk_badges': [
                badge
                for badge in (
                    {'label': f'{risk_summary["critical"]} critical', 'tone': 'danger'}
                    if risk_summary['critical']
                    else None,
                    {'label': f'{risk_summary["high"]} high', 'tone': 'attention'}
                    if risk_summary['high']
                    else None,
                    {'label': f'{risk_summary["open"]} open', 'tone': 'neutral'}
                    if risk_summary['open'] and not risk_summary['critical'] and not risk_summary['high']
                    else None,
                    {'label': 'Needs input', 'tone': 'attention'}
                    if risk_summary['needs_input']
                    else None,
                )
                if badge
            ],
        }
        org = get_user_organization(self.request.user)
        ctx['linkable_contracts'] = (
            Contract.objects.filter(organization=org)
            .exclude(pk=review_pack.contract_id)
            .exclude(pk__in=review_pack.related_contracts.values_list('pk', flat=True))
            .order_by('title')
            if org else Contract.objects.none()
        )
        ctx['linked_documents'] = list(review_pack.documents.all())
        ctx['related_contracts'] = list(review_pack.related_contracts.all())
        ctx['show_decision_bar'] = can_review and review_pack.approval_status != DPAReviewPack.ApprovalStatus.APPROVED
        return ctx


class DPAReviewMemoView(TenantScopedQuerysetMixin, LoginRequiredMixin, DetailView):
    """View the generated review memo. Generation itself is a separate,
    explicit POST action (dpa_review_generate_memo) — this page only
    displays whatever memo text is currently stored."""
    model = DPAReviewPack
    template_name = 'contracts/dpa_review_pack_memo.html'
    context_object_name = 'review_pack'

    def get_queryset(self):
        org = get_user_organization(self.request.user)
        if not org:
            return DPAReviewPack.objects.none()
        return DPAReviewPack.objects.filter(organization=org).select_related('contract')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['can_edit'] = can_access_contract_action(self.request.user, ctx['review_pack'].contract, ContractAction.EDIT)
        return ctx


class DPAPlaybookListView(LoginRequiredMixin, ListView):
    """Read-only reference: standing DPA negotiation positions. Org-specific
    overrides win over the global default (organization IS NULL) per topic."""
    model = DPAPlaybookPosition
    template_name = 'contracts/dpa_playbook_list.html'
    context_object_name = 'positions'

    def get_queryset(self):
        org = get_user_organization(self.request.user)
        qs = DPAPlaybookPosition.objects.filter(Q(organization=org) | Q(organization__isnull=True))
        by_topic = {}
        for position in qs.order_by('topic', '-organization_id'):
            by_topic.setdefault(position.topic, position)  # org-specific (non-null id, sorted first) wins
        return sorted(by_topic.values(), key=lambda p: p.topic)


def _get_owned_review_pack_or_404(request, pk, prefetch_related_contracts=False):
    org = get_user_organization(request.user)
    queryset = DPAReviewPack.objects.filter(organization=org).select_related('contract') if org else DPAReviewPack.objects.none()
    if prefetch_related_contracts:
        queryset = queryset.prefetch_related('related_contracts')
    return get_object_or_404(queryset, pk=pk)


def _parse_json_body(request):
    try:
        return json.loads(request.body or '{}')
    except ValueError:
        return {}


def _approval_risk_snapshot(review_pack):
    risk_items = list(review_pack.risk_items.all())
    counts = {}
    unresolved_statuses = {
        DPARiskItem.Status.OPEN,
        DPARiskItem.Status.IN_REVIEW,
        DPARiskItem.Status.NEEDS_BUSINESS_INPUT,
        DPARiskItem.Status.NEEDS_DPO_SECURITY_INPUT,
        DPARiskItem.Status.ESCALATED,
    }
    blocker_severities = {DPARiskItem.Severity.CRITICAL, DPARiskItem.Severity.HIGH}
    unresolved_blocker_count = 0
    unresolved_critical_blocker_count = 0
    for risk in risk_items:
        counts[risk.severity] = counts.get(risk.severity, 0) + 1
        if risk.status in unresolved_statuses and risk.severity in blocker_severities:
            unresolved_blocker_count += 1
            if risk.severity == DPARiskItem.Severity.CRITICAL:
                unresolved_critical_blocker_count += 1
    return counts, unresolved_blocker_count, unresolved_critical_blocker_count


@require_POST
def dpa_review_run_analysis(request, pk):
    """Suggestion-only re-scan of the DPA text, plus cross-document
    conflict checks against every linked related_contract (MSA/SOW).
    Persists checklist field updates and refreshes auto-detected OPEN risk
    items (anything the reviewer has already triaged — accepted, marked a
    false positive, resolved, or flagged as needing input — is left
    untouched). Never touches approval_status."""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required.'}, status=403)

    review_pack = _get_owned_review_pack_or_404(request, pk, prefetch_related_contracts=True)
    if not can_access_contract_action(request.user, review_pack.contract, ContractAction.EDIT):
        return JsonResponse({'error': 'You do not have permission to analyze this DPA.'}, status=403)

    suggestions = run_dpa_analysis(review_pack)
    review_pack.last_analyzed_at = timezone.now()
    review_pack.save()

    # Cross-document conflicts read the fields run_dpa_analysis just set on
    # review_pack, so they must run after it, in the same pass. Keep this
    # de-dupe defensive in case a future DPA-only rule reuses a rule key.
    seen_rules = {s.detection_rule for s in suggestions if s.detection_rule}
    for s in check_cross_document_conflicts(review_pack):
        if s.detection_rule and s.detection_rule in seen_rules:
            continue
        suggestions.append(s)
        if s.detection_rule:
            seen_rules.add(s.detection_rule)

    review_pack.risk_items.filter(detected_automatically=True, status=DPARiskItem.Status.OPEN).delete()
    DPARiskItem.objects.bulk_create([
        DPARiskItem(
            review_pack=review_pack, category=s.category, title=s.title, description=s.description,
            severity=s.severity, confidence=s.confidence, owners=s.owners,
            fallback_recommendation=s.fallback_recommendation, evidence_text=s.evidence_text,
            source_section=s.source_section, source_field=s.source_field,
            detection_rule=s.detection_rule, conflict_type=s.conflict_type,
            related_contract_evidence_text=s.related_contract_evidence_text,
            is_cross_document_conflict=s.is_cross_document_conflict,
            detected_automatically=True,
        )
        for s in suggestions
    ])

    log_action(
        request.user, AuditLog.Action.UPDATE, 'DPAReviewPack',
        object_id=review_pack.pk, object_repr=str(review_pack), organization=review_pack.organization,
        changes={'event': 'dpa_analysis_run', 'suggested_risk_count': len(suggestions)},
        request=request,
    )
    return JsonResponse({'ok': True, 'suggested_risk_count': len(suggestions)})


@require_POST
def dpa_review_set_approval_status(request, pk):
    """Human-only approval routing. This is the ONLY place approval_status
    can change — the analyzer never sets it, and there is no auto-approve
    path anywhere in this module. Every change is recorded both in AuditLog
    (org-wide audit trail) and DPAApprovalHistoryEntry (DPA-scoped history
    shown directly on the review pack)."""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required.'}, status=403)

    review_pack = _get_owned_review_pack_or_404(request, pk)
    if not _can_review_pack(request.user, review_pack):
        return JsonResponse({'error': 'Only the assigned reviewer or a workspace admin can set DPA review status.'}, status=403)

    payload = _parse_json_body(request)
    new_status = payload.get('status')
    comment = (payload.get('comment') or '').strip()
    valid_statuses = {choice for choice, _ in DPAReviewPack.ApprovalStatus.choices}
    if new_status not in valid_statuses:
        return JsonResponse({'error': 'Invalid approval status.'}, status=400)

    previous_status = review_pack.approval_status
    if previous_status == new_status:
        return JsonResponse({'ok': True, 'status': new_status})
    if new_status not in DPA_APPROVAL_TRANSITIONS.get(previous_status, set()):
        return JsonResponse({
            'error': f'Cannot move DPA review from {previous_status} to {new_status}.'
        }, status=400)
    if new_status in {
        DPAReviewPack.ApprovalStatus.REJECTED,
        DPAReviewPack.ApprovalStatus.ESCALATED,
    } and not comment:
        return JsonResponse({'error': 'A decision note is required.'}, status=400)
    risk_counts_by_severity, unresolved_blocker_count, unresolved_critical_blocker_count = _approval_risk_snapshot(review_pack)
    security_approval = bool(payload.get('security_approval'))

    from contracts.services.exception_dual_write import dual_write_enabled_for_org
    if (
        new_status == DPAReviewPack.ApprovalStatus.APPROVED
        and unresolved_critical_blocker_count > 0
        and dual_write_enabled_for_org(review_pack.organization)
        and not security_approval
    ):
        from contracts.middleware import log_action as _log
        from contracts.services.exception_dual_write import EVENT_SECURITY_GATE_BLOCKED
        _log(
            request.user,
            AuditLog.Action.UPDATE,
            'DPAReviewPack',
            object_id=review_pack.pk,
            object_repr=str(review_pack),
            organization=review_pack.organization,
            changes={
                'event': EVENT_SECURITY_GATE_BLOCKED,
                'source': 'DPA_APPROVE_WITH_BLOCKERS',
                'unresolved_critical_blocker_count': unresolved_critical_blocker_count,
            },
            event_type=EVENT_SECURITY_GATE_BLOCKED,
            outcome='blocked',
            request=request,
        )
        return JsonResponse({
            'error': 'Critical open blockers require explicit Security approval before DPA approve.',
        }, status=403)

    review_pack.approval_status = new_status
    if new_status == DPAReviewPack.ApprovalStatus.APPROVED:
        review_pack.approved_by = request.user
        review_pack.approved_at = timezone.now()
    else:
        review_pack.approved_by = None
        review_pack.approved_at = None
    review_pack.save()

    DPAApprovalHistoryEntry.objects.create(
        review_pack=review_pack, from_status=previous_status, to_status=new_status,
        changed_by=request.user, comment=comment,
        risk_counts_by_severity=risk_counts_by_severity,
        unresolved_blocker_count=unresolved_blocker_count,
    )
    log_action(
        request.user, AuditLog.Action.UPDATE, 'DPAReviewPack',
        object_id=review_pack.pk, object_repr=str(review_pack), organization=review_pack.organization,
        changes={
            'event': 'dpa_approval_status_changed',
            'previous_status': previous_status,
            'new_status': new_status,
            'comment': comment,
            'contract_id': review_pack.contract_id,
            'risk_counts_by_severity': risk_counts_by_severity,
            'unresolved_blocker_count': unresolved_blocker_count,
        },
        request=request,
    )
    if (
        new_status == DPAReviewPack.ApprovalStatus.APPROVED
        and unresolved_blocker_count > 0
    ):
        from contracts.services.exception_dual_write import (
            ExceptionDualWriteError,
            SOURCE_DPA_APPROVE_WITH_BLOCKERS,
            build_correlation_id,
            safe_mirror_legacy_exception,
        )
        try:
            safe_mirror_legacy_exception(
                source=SOURCE_DPA_APPROVE_WITH_BLOCKERS,
                organization=review_pack.organization,
                actor=request.user,
                owner=review_pack.reviewer or request.user,
                title=f'DPA approve with open blockers ({unresolved_blocker_count})',
                reason=comment or (
                    f'DPA review pack approved with {unresolved_blocker_count} unresolved HIGH/CRITICAL blockers.'
                ),
                scope_object_model='DPAReviewPack',
                scope_object_id=review_pack.pk,
                correlation_id=build_correlation_id(
                    source=SOURCE_DPA_APPROVE_WITH_BLOCKERS,
                    object_model='DPAReviewPack',
                    object_id=review_pack.pk,
                    suffix=f'{previous_status}->{new_status}',
                ),
                outcome='APPROVED',
                contract=review_pack.contract,
                scope_reference={
                    'unresolved_blocker_count': unresolved_blocker_count,
                    'unresolved_critical_blocker_count': unresolved_critical_blocker_count,
                    'risk_counts_by_severity': risk_counts_by_severity,
                },
                authority_basis='security' if unresolved_critical_blocker_count else 'legal',
                compensating_controls=comment or 'Open blockers remain tracked on the DPA review pack.',
                granted_privileges=['approval.defer_blocker'],
                risk_classification='CRITICAL' if unresolved_critical_blocker_count else 'HIGH',
                bypasses_critical_security_control=bool(unresolved_critical_blocker_count),
                security_approval=security_approval,
                request=request,
            )
        except ExceptionDualWriteError as exc:
            return JsonResponse({'error': str(exc)}, status=403)
    return JsonResponse({'ok': True, 'status': new_status})


@require_POST
def dpa_risk_item_create(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required.'}, status=403)
    review_pack = _get_owned_review_pack_or_404(request, pk)
    if not _can_review_pack(request.user, review_pack):
        return JsonResponse({'error': 'Only the assigned reviewer or a workspace admin can add DPA risks.'}, status=403)
    payload = _parse_json_body(request)
    title = (payload.get('title') or '').strip()
    description = (payload.get('description') or '').strip()
    category = payload.get('category') or DPARiskItem.Category.PROCESSING_SCOPE
    severity = payload.get('severity') or DPARiskItem.Severity.MEDIUM
    if not title or not description:
        return JsonResponse({'error': 'Risk title and description are required.'}, status=400)
    if category not in {value for value, _ in DPARiskItem.Category.choices}:
        return JsonResponse({'error': 'Invalid risk category.'}, status=400)
    if severity not in {value for value, _ in DPARiskItem.Severity.choices}:
        return JsonResponse({'error': 'Invalid risk severity.'}, status=400)
    risk = DPARiskItem.objects.create(
        review_pack=review_pack,
        category=category,
        title=title,
        description=description,
        severity=severity,
        confidence=DPARiskItem.Confidence.NEEDS_HUMAN_CHECK,
        owners='LEGAL,DPO_SECURITY',
        reviewer_notes=(payload.get('note') or '').strip(),
        status=DPARiskItem.Status.OPEN,
        detected_automatically=False,
    )
    log_action(
        request.user, AuditLog.Action.CREATE, 'DPARiskItem', risk.pk, str(risk),
        organization=review_pack.organization, request=request,
        changes={
            'event': 'dpa_risk_item.created',
            'contract_id': review_pack.contract_id,
            'review_pack_id': review_pack.pk,
            'severity': risk.severity,
            'status': risk.status,
        },
    )
    return JsonResponse({'ok': True, 'risk_id': risk.pk}, status=201)


@require_POST
def dpa_risk_item_set_status(request, pk):
    """Reviewer disposition: false positive, accepted risk, resolved, or
    needs input (plus the initial 'open' state). Reviewer notes are
    optional free text recorded alongside the disposition."""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required.'}, status=403)

    org = get_user_organization(request.user)
    queryset = DPARiskItem.objects.filter(review_pack__organization=org).select_related('review_pack__contract') if org else DPARiskItem.objects.none()
    risk_item = get_object_or_404(queryset, pk=pk)
    if not _can_review_pack(request.user, risk_item.review_pack):
        return JsonResponse({'error': 'You do not have permission to update this risk item.'}, status=403)

    payload = _parse_json_body(request)
    new_status = payload.get('status')
    valid_statuses = {choice for choice, _ in DPARiskItem.Status.choices}
    if new_status not in valid_statuses:
        return JsonResponse({'error': 'Invalid risk item status.'}, status=400)

    previous_status = risk_item.status
    if previous_status == new_status:
        return JsonResponse({'ok': True, 'status': new_status})

    risk_item.status = new_status
    risk_item.save(update_fields=['status', 'updated_at'])
    note_text = (payload.get('note') or payload.get('reason') or payload.get('comments') or '').strip()
    note_id = None
    if note_text:
        note = DPARiskItemNote.objects.create(
            risk_item=risk_item, author=request.user, note=note_text,
        )
        note_id = note.pk
    log_action(
        request.user, AuditLog.Action.UPDATE, 'DPARiskItem',
        object_id=risk_item.pk, object_repr=str(risk_item), organization=risk_item.review_pack.organization,
        changes={
            'event': 'dpa_risk_item_status_changed',
            'contract_id': risk_item.review_pack.contract_id,
            'previous_status': previous_status,
            'new_status': new_status,
            'note_id': note_id,
            'note': note_text[:240] if note_text else '',
        },
        request=request,
    )
    if new_status == DPARiskItem.Status.ACCEPTED_RISK:
        from contracts.services.exception_dual_write import (
            ExceptionDualWriteError,
            SOURCE_ACCEPTED_RISK,
            build_correlation_id,
            safe_mirror_legacy_exception,
        )
        is_critical = risk_item.severity == DPARiskItem.Severity.CRITICAL
        security_approval = bool(payload.get('security_approval'))
        try:
            safe_mirror_legacy_exception(
                source=SOURCE_ACCEPTED_RISK,
                organization=risk_item.review_pack.organization,
                actor=request.user,
                owner=request.user,
                title=f'Accepted risk: {risk_item.title}'[:255],
                reason=note_text or f'DPA risk item {risk_item.pk} accepted as risk.',
                scope_object_model='DPARiskItem',
                scope_object_id=risk_item.pk,
                correlation_id=build_correlation_id(
                    source=SOURCE_ACCEPTED_RISK,
                    object_model='DPARiskItem',
                    object_id=risk_item.pk,
                    suffix='accepted',
                ),
                outcome='APPROVED',
                contract=risk_item.review_pack.contract,
                scope_reference={'review_pack_id': risk_item.review_pack_id},
                authority_basis='security' if is_critical else 'policy_owner',
                compensating_controls=note_text or 'Accepted risk recorded on DPA review pack.',
                granted_privileges=['risk.accept'],
                risk_classification=risk_item.severity or 'MEDIUM',
                bypasses_critical_security_control=is_critical,
                security_approval=security_approval,
                request=request,
            )
        except ExceptionDualWriteError as exc:
            return JsonResponse({'error': str(exc)}, status=403)
    return JsonResponse({'ok': True, 'status': new_status, 'note_id': note_id})


@require_POST
def dpa_risk_item_add_note(request, pk):
    """Append a timestamped reviewer note to a risk item."""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required.'}, status=403)

    org = get_user_organization(request.user)
    queryset = DPARiskItem.objects.filter(review_pack__organization=org).select_related('review_pack__contract') if org else DPARiskItem.objects.none()
    risk_item = get_object_or_404(queryset, pk=pk)
    if not _can_review_pack(request.user, risk_item.review_pack):
        return JsonResponse({'error': 'You do not have permission to add a reviewer note.'}, status=403)

    payload = _parse_json_body(request)
    note_text = (payload.get('note') or '').strip()
    if not note_text:
        return JsonResponse({'error': 'Note is required.'}, status=400)

    note = DPARiskItemNote.objects.create(risk_item=risk_item, author=request.user, note=note_text)
    log_action(
        request.user, AuditLog.Action.UPDATE, 'DPARiskItem',
        object_id=risk_item.pk, object_repr=str(risk_item), organization=risk_item.review_pack.organization,
        changes={
            'event': 'dpa_risk_item_note_added',
            'contract_id': risk_item.review_pack.contract_id,
            'note_id': note.pk,
        },
        request=request,
    )
    return JsonResponse({'ok': True, 'note': note.note, 'created_at': note.created_at.isoformat()})


@require_POST
def dpa_review_link_related_contract(request, pk):
    """Link an MSA/SOW (or any other org contract) to this DPA review pack
    so cross-document conflict checks have something to compare against."""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required.'}, status=403)

    review_pack = _get_owned_review_pack_or_404(request, pk)
    if not can_access_contract_action(request.user, review_pack.contract, ContractAction.EDIT):
        return JsonResponse({'error': 'You do not have permission to edit this DPA review.'}, status=403)

    payload = _parse_json_body(request)
    contract_id = payload.get('contract_id')
    org = get_user_organization(request.user)
    contract = get_object_or_404(Contract.objects.filter(organization=org), pk=contract_id)
    review_pack.related_contracts.add(contract)

    log_action(
        request.user, AuditLog.Action.UPDATE, 'DPAReviewPack',
        object_id=review_pack.pk, object_repr=str(review_pack), organization=review_pack.organization,
        changes={'event': 'dpa_related_contract_linked', 'contract_id': contract.pk},
        request=request,
    )
    return JsonResponse({'ok': True})


@require_POST
def dpa_review_generate_memo(request, pk):
    """Compile the current checklist/risk-item/history state into
    review_pack.review_memo. Purely a summarization step — it does not
    change any finding, risk status, or approval status."""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required.'}, status=403)

    review_pack = _get_owned_review_pack_or_404(request, pk, prefetch_related_contracts=True)
    if not can_access_contract_action(request.user, review_pack.contract, ContractAction.EDIT):
        return JsonResponse({'error': 'You do not have permission to generate this memo.'}, status=403)

    review_pack.review_memo = generate_review_memo(review_pack)
    review_pack.review_memo_generated_at = timezone.now()
    review_pack.save(update_fields=['review_memo', 'review_memo_generated_at', 'updated_at'])

    log_action(
        request.user, AuditLog.Action.UPDATE, 'DPAReviewPack',
        object_id=review_pack.pk, object_repr=str(review_pack), organization=review_pack.organization,
        changes={'event': 'dpa_review_memo_generated'},
        request=request,
    )
    return JsonResponse({'ok': True})


def dpa_review_memo_export(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required.'}, status=403)

    review_pack = _get_owned_review_pack_or_404(request, pk)
    response = HttpResponse(review_pack.review_memo or '', content_type='text/plain; charset=utf-8')
    safe_title = ''.join(c if c.isalnum() or c in ' -_' else '' for c in review_pack.contract.title).strip().replace(' ', '_')
    response['Content-Disposition'] = f'attachment; filename="dpa-review-memo-{safe_title or review_pack.pk}.txt"'
    return response
