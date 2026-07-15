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
from django.db.models import Q
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


class DPAReviewPackListView(TenantScopedQuerysetMixin, LoginRequiredMixin, ListView):
    """DPA dashboard: role qualification, processing scope, transfer/
    subprocessor risk, security, breach notification, audit, deletion,
    liability conflicts, and approval status — one row per DPA review pack."""
    model = DPAReviewPack
    template_name = 'contracts/dpa_review_pack_list.html'
    context_object_name = 'review_packs'

    def get_queryset(self):
        org = get_user_organization(self.request.user)
        if not org:
            return DPAReviewPack.objects.none()
        return (
            DPAReviewPack.objects.filter(organization=org)
            .select_related('contract', 'counterparty', 'reviewer')
            .prefetch_related('risk_items')
            .order_by('-updated_at')
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        packs = ctx['review_packs']
        ctx['playbook_url'] = reverse('contracts:dpa_playbook_list')
        ctx['total_packs'] = len(packs)
        ctx['pending_approval_count'] = sum(1 for p in packs if p.approval_status in (DPAReviewPack.ApprovalStatus.DRAFT, DPAReviewPack.ApprovalStatus.UNDER_REVIEW))
        ctx['escalated_count'] = sum(1 for p in packs if p.approval_status == DPAReviewPack.ApprovalStatus.ESCALATED)
        ctx['open_critical_risk_count'] = sum(
            1 for p in packs for r in p.risk_items.all()
            if r.status == DPARiskItem.Status.OPEN and r.severity == DPARiskItem.Severity.CRITICAL
        )

        # The list is a compact scan surface, so it needs presentation-ready
        # counts and semantic tones without teaching the template about model
        # enums. The underlying queryset remains available as `review_packs`
        # for compatibility with existing callers and tests.
        approval_tones = {
            DPAReviewPack.ApprovalStatus.DRAFT: 'neutral',
            DPAReviewPack.ApprovalStatus.UNDER_REVIEW: 'progress',
            DPAReviewPack.ApprovalStatus.ESCALATED: 'danger',
            DPAReviewPack.ApprovalStatus.APPROVED: 'success',
            DPAReviewPack.ApprovalStatus.REJECTED: 'danger',
        }
        resolved_risk_statuses = {
            DPARiskItem.Status.RESOLVED,
            DPARiskItem.Status.ACCEPTED_RISK,
            DPARiskItem.Status.FALSE_POSITIVE,
        }
        rows = []
        for pack in packs:
            unresolved_risks = [
                risk for risk in pack.risk_items.all()
                if risk.status not in resolved_risk_statuses
            ]
            critical_risk_count = sum(
                1 for risk in unresolved_risks
                if risk.severity == DPARiskItem.Severity.CRITICAL
            )
            rows.append({
                'pack': pack,
                'unresolved_risk_count': len(unresolved_risks),
                'critical_risk_count': critical_risk_count,
                # An unresolved risk is an active intervention, regardless of
                # severity. Amber is reserved for incomplete/unmeasured setup.
                'risk_tone': 'danger' if unresolved_risks else 'success',
                'approval_tone': approval_tones.get(pack.approval_status, 'neutral'),
            })
        ctx['review_pack_rows'] = rows
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
        ctx['risk_items'] = review_pack.risk_items.all()
        ctx['approval_history'] = review_pack.approval_history.all()
        ctx['can_edit'] = can_access_contract_action(self.request.user, review_pack.contract, ContractAction.EDIT)
        ctx['can_review'] = _can_review_pack(self.request.user, review_pack)
        ctx['can_approve'] = ctx['can_review']
        org = get_user_organization(self.request.user)
        ctx['linkable_contracts'] = (
            Contract.objects.filter(organization=org)
            .exclude(pk=review_pack.contract_id)
            .exclude(pk__in=review_pack.related_contracts.values_list('pk', flat=True))
            .order_by('title')
            if org else Contract.objects.none()
        )
        ctx['payroll_data_fields'] = [
            (label, getattr(review_pack, field_name)) for field_name, label in (
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
        ]
        ctx['security_fields'] = [
            (label, getattr(review_pack, field_name)) for field_name, label in (
                ('security_encryption', 'Encryption'),
                ('security_access_control', 'Access control'),
                ('security_mfa', 'Multi-factor authentication'),
                ('security_logging', 'Logging'),
                ('security_backup', 'Backup'),
                ('security_incident_response', 'Incident response'),
                ('security_data_segregation', 'Data segregation'),
            )
        ]
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
    for risk in risk_items:
        counts[risk.severity] = counts.get(risk.severity, 0) + 1
        if risk.status in unresolved_statuses and risk.severity in blocker_severities:
            unresolved_blocker_count += 1
    return counts, unresolved_blocker_count


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
    risk_counts_by_severity, unresolved_blocker_count = _approval_risk_snapshot(review_pack)

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
    log_action(
        request.user, AuditLog.Action.UPDATE, 'DPARiskItem',
        object_id=risk_item.pk, object_repr=str(risk_item), organization=risk_item.review_pack.organization,
        changes={
            'event': 'dpa_risk_item_status_changed',
            'contract_id': risk_item.review_pack.contract_id,
            'previous_status': previous_status,
            'new_status': new_status,
        },
        request=request,
    )
    return JsonResponse({'ok': True, 'status': new_status})


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
