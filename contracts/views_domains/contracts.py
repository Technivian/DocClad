from datetime import date, timedelta
from decimal import Decimal
import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from contracts.forms import ContractForm, DocumentForm, UserProfileForm
from contracts.middleware import log_action
from contracts.models import (
    AuditLog,
    Budget,
    Case,
    CaseMatter,
    Client,
    Contract,
    ContractTemplate,
    Document,
    Invoice,
    LegalTask,
    Matter,
    NegotiationThread,
    Notification,
    Organization,
    OrganizationMembership,
    RiskLog,
    SignatureRequest,
    TimeEntry,
    TrustAccount,
    UserProfile,
    Workflow,
    WorkflowStep,
    CaseSignal,
    Deadline,
    DSARRequest,
    ApprovalRequest,
    DPAReviewPack,
    DPARiskItem,
    DPAPlaybookPosition,
    ApprovalRule,
    ClausePlaybook,
    OrgPolicy,
    ContractReviewFinding,
    DocumentReviewRun,
    ClauseUsageEvent,
    CounterpartyCollaborationItem,
    CounterpartyCollaborationParticipant,
)
from contracts.permissions import ContractAction, can_access_contract_action, can_manage_organization
from contracts.services.queue_rows import TERMINAL_STATUSES, assignee_map_for_contracts, latest_activity_map
from contracts.services.command_center import (
    COMPACT_LIFECYCLE_LABELS,
    build_upcoming_deadlines,
    explainable_risk_score,
    get_command_center_rail_items,
    get_command_center_saved_views,
    get_persisted_command_center_rows,
    get_recent_review_memos,
    get_workflow_type_summary,
    governed_recommendation,
    group_recommended_actions,
    rank_command_center_rows,
)
from contracts.services.contract_launch_setup import get_entry_card_sections, get_launch_setup_map
from contracts.services.intake_risk import assess_intake_risk, intake_risk_client_policy
from contracts.services.intake_routing import intake_routing_client_policy
from contracts.services.draft_cockpit import get_governance_panel
from contracts.templatetags.clmone_format import (
    contract_status_badge_tone,
    legacy_badge_class_for_tone,
    lifecycle_steps,
)
from contracts.tenancy import get_user_organization, scope_queryset_for_organization, set_organization_on_instance
from contracts.view_support import (
    TenantAssignCreateMixin,
    TenantScopedQuerysetMixin,
    apply_form_queryset_scopes,
)
from contracts.services.contract_lifecycle import (
    build_contract_audit_changes,
    get_signature_routing_blockers,
    record_contract_grounded_check,
)
from contracts.services.contract_detail_workspace import (
    build_contract_command,
    build_contract_detail_tabs,
    build_workflow_section_tabs,
    contract_operations_hub_tabs,
    build_overview_progress,
    contract_detail_tab_url,
    derive_contract_review_status,
    format_contract_audit_activity_detail,
    get_submit_readiness,
    normalize_contract_detail_tab,
    normalize_workflow_section,
)
from contracts.services.ai_policy import evaluate_prompt
from contracts.services.ai_actions import build_action_plan, execute_action_plan
from config.feature_flags import is_feature_redesign_enabled

from .contract_helpers import _build_contract_ai_response, build_contract_lifecycle_guidance
from contracts.services.contract_templates import render_merge_fields
from contracts.templatetags.clmone_format import object_type_label
from contracts.services.document_ocr import queue_document_ocr_review

User = get_user_model()


class ContractListView(TenantScopedQuerysetMixin, LoginRequiredMixin, ListView):
    """Legacy parallel list — Phase 4 retires it in favor of the repository."""

    model = Contract
    template_name = 'contracts/contract_list.html'
    context_object_name = 'contracts'
    paginate_by = 25

    def dispatch(self, request, *args, **kwargs):
        # Canonical Contracts destination is the repository workspace.
        # Auth first — never alias-redirect anonymous users past login.
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        target = reverse('contracts:repository')
        query = request.META.get('QUERY_STRING')
        if query:
            target = f'{target}?{query}'
        return redirect(target, permanent=False)

    def get_queryset(self):
        org = get_user_organization(self.request.user)
        queryset = scope_queryset_for_organization(Case.objects.select_related('client', 'matter', 'created_by'), org)
        query = self.request.GET.get('q')
        status = self.request.GET.get('status')
        contract_type = self.request.GET.get('type')
        sort = self.request.GET.get('sort', '-created_at')
        if query:
            queryset = queryset.filter(Q(title__icontains=query) | Q(counterparty__icontains=query))
        if status == 'BLOCKED':
            queryset = queryset.filter(status__in=[
                Contract.Status.EXPIRED,
                Contract.Status.TERMINATED,
                Contract.Status.CANCELLED,
            ])
        elif status == 'DRAFT':
            queryset = queryset.filter(
                status=Contract.Status.IN_PROGRESS,
                lifecycle_stage__in=[
                    Contract.LifecycleStage.INTAKE,
                    Contract.LifecycleStage.DRAFTING,
                ],
            )
        elif status == 'IN_REVIEW':
            queryset = queryset.filter(
                status=Contract.Status.IN_PROGRESS,
                lifecycle_stage__in=[
                    Contract.LifecycleStage.INTERNAL_REVIEW,
                    Contract.LifecycleStage.NEGOTIATION,
                ],
            )
        elif status == 'PENDING':
            queryset = queryset.filter(
                status=Contract.Status.IN_PROGRESS,
                lifecycle_stage=Contract.LifecycleStage.APPROVAL,
            )
        elif status == 'APPROVED':
            queryset = queryset.filter(
                status=Contract.Status.IN_PROGRESS,
                lifecycle_stage=Contract.LifecycleStage.SIGNATURE,
            )
        elif status:
            queryset = queryset.filter(status=status)
        if contract_type:
            queryset = queryset.filter(contract_type=contract_type)

        allowed_sort_fields = {
            'title', '-title', 'status', '-status', 'end_date', '-end_date',
            'created_at', '-created_at', 'updated_at', '-updated_at',
            'value', '-value', 'lifecycle_stage', '-lifecycle_stage',
            'risk_level', '-risk_level',
        }
        if sort not in allowed_sort_fields:
            sort = '-created_at'
        return queryset.order_by(sort)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        org = get_user_organization(self.request.user)
        today = date.today()
        thirty_days_from_today = today + timedelta(days=30)
        tenant_cases = scope_queryset_for_organization(Case.objects.all(), org)
        case_stats = tenant_cases.aggregate(
            total=Count('id'),
            active=Count('id', filter=Q(status=Contract.Status.ACTIVE)),
            expiring_soon=Count(
                'id',
                filter=Q(
                    status=Contract.Status.ACTIVE,
                    end_date__lte=thirty_days_from_today,
                    end_date__gte=today,
                ),
            ),
            draft=Count(
                'id',
                filter=Q(
                    status=Contract.Status.IN_PROGRESS,
                    lifecycle_stage__in=[
                        Contract.LifecycleStage.INTAKE,
                        Contract.LifecycleStage.DRAFTING,
                    ],
                ),
            ),
            legal_review=Count(
                'id',
                filter=Q(
                    status=Contract.Status.IN_PROGRESS,
                    lifecycle_stage__in=[
                        Contract.LifecycleStage.INTERNAL_REVIEW,
                        Contract.LifecycleStage.NEGOTIATION,
                    ],
                ),
            ),
            approval=Count(
                'id',
                filter=Q(
                    status=Contract.Status.IN_PROGRESS,
                    lifecycle_stage=Contract.LifecycleStage.APPROVAL,
                ),
            ),
            signature=Count(
                'id',
                filter=Q(
                    status=Contract.Status.IN_PROGRESS,
                    lifecycle_stage=Contract.LifecycleStage.SIGNATURE,
                ),
            ),
            blocked=Count(
                'id',
                filter=Q(status__in=[
                    Contract.Status.EXPIRED,
                    Contract.Status.TERMINATED,
                    Contract.Status.CANCELLED,
                ]),
            ),
            high_risk=Count('id', filter=Q(risk_level__in=['HIGH', 'CRITICAL'])),
        )
        expiring_ids_qs = tenant_cases.filter(
            status='ACTIVE',
            end_date__lte=thirty_days_from_today,
            end_date__gte=today,
        ).values_list('id', flat=True)

        context['FEATURE_REDESIGN'] = is_feature_redesign_enabled()
        context['search_query'] = self.request.GET.get('q', '')
        context['sort'] = self.request.GET.get('sort', '-created_at')
        context['current_status'] = self.request.GET.get('status', '')
        # Legacy list aliases stage-oriented filters; labels must not say "Draft"
        # as a record status (PDR-0002). Values remain stage-filter keys.
        context['status_tabs'] = [
            ('All', ''),
            ('Drafting', 'DRAFT'),
            ('Internal review', 'IN_REVIEW'),
            ('Approval', 'PENDING'),
            ('Signature', 'APPROVED'),
            ('Blocked', 'BLOCKED'),
        ]
        context['total_cases'] = case_stats['total'] or 0
        context['active_cases'] = case_stats['active'] or 0
        context['expiring_case_count'] = case_stats['expiring_soon'] or 0
        context['expiring_contract_ids'] = set(expiring_ids_qs)
        context['cases'] = context['object_list']
        context['total_contracts'] = context['total_cases']
        context['active_contracts'] = context['active_cases']
        context['expiring_soon'] = context['expiring_case_count']
        context['workspace_counts'] = {
            'draft': case_stats['draft'] or 0,
            'legal_review': case_stats['legal_review'] or 0,
            'approval': case_stats['approval'] or 0,
            'signature': case_stats['signature'] or 0,
            'blocked': case_stats['blocked'] or 0,
            'high_risk': case_stats['high_risk'] or 0,
        }

        if context['FEATURE_REDESIGN']:
            case_payload = []
            for case_record in context['object_list']:
                case_payload.append({
                    'id': case_record.id,
                    'title': case_record.title,
                    'status': case_record.status,
                    'status_display': case_record.get_status_display(),
                    'contract_type': case_record.get_contract_type_display(),
                    'start_date': case_record.start_date.strftime('%b %d, %Y') if case_record.start_date else None,
                    'end_date': case_record.end_date.strftime('%b %d, %Y') if case_record.end_date else None,
                    'value': float(case_record.value) if case_record.value else None,
                    'counterparty': case_record.counterparty or '',
                    'client': case_record.client.name if case_record.client else '',
                    'owner': case_record.created_by.get_full_name() if case_record.created_by else 'System',
                    'updated_at': case_record.updated_at.strftime('%b %d, %Y'),
                })
            context['cases_json'] = json.dumps(case_payload)
            context['contracts_json'] = context['cases_json']
        return context


class ContractDetailView(TenantScopedQuerysetMixin, LoginRequiredMixin, DetailView):
    model = Contract
    template_name = 'contracts/contract_detail.html'
    context_object_name = 'contract'

    def get_queryset(self):
        org = get_user_organization(self.request.user)
        return scope_queryset_for_organization(Contract.objects.all(), org)

    def _attachment_form(self, data=None, files=None):
        """Build the existing upload form with this contract fixed server-side."""
        form = DocumentForm(data, files, instance=Document(contract=self.object))
        apply_form_queryset_scopes(
            form,
            get_user_organization(self.request.user),
            {'contract': Contract, 'matter': Matter, 'client': Client},
        )
        # An attachment belongs to the contract in this URL; never trust a
        # posted relation to retarget it to another record.
        for field_name in ('contract', 'matter', 'client'):
            form.fields.pop(field_name, None)
        return form

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not can_access_contract_action(request.user, self.object, ContractAction.EDIT):
            return HttpResponseForbidden('You do not have permission to upload documents for this contract.')

        form = self._attachment_form(request.POST, request.FILES)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(
                attach_document_form=form,
                attach_document_dialog_open=True,
            ))

        from contracts.services.document_version_service import create_document_version

        staged = form.save(commit=False)
        organization = get_user_organization(request.user)
        document, _version = create_document_version(
            organization=organization,
            title=staged.title,
            document_type=staged.document_type,
            status=staged.status,
            description=staged.description,
            file=staged.file,
            contract=self.object,
            matter=staged.matter,
            client=staged.client,
            uploaded_by=request.user,
            actor=request.user,
            source='contract_attachment',
            tags=staged.tags,
            is_privileged=staged.is_privileged,
            is_confidential=staged.is_confidential,
            request=request,
            supersede_prior=False,
        )
        form.save_m2m()
        queue_document_ocr_review(document)
        log_action(
            request.user,
            'CREATE',
            'Document',
            document.id,
            str(document),
            changes={
                'event': 'document.uploaded',
                'equivalent_event': 'document.version.created',
                'version': document.version,
                'file_hash': document.file_hash,
                'source': 'contract_detail_attachment',
            },
            request=request,
        )
        messages.success(request, f'Document "{document.title}" attached to this contract.')
        return redirect(contract_detail_tab_url(self.object.pk, 'documents'))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        case_record = self.object
        ctx['case'] = case_record
        ctx['case_record'] = case_record
        ctx['documents'] = list(
            case_record.documents
            .select_related('uploaded_by', 'ocr_review')
            .prefetch_related('ai_extraction_spans__source_template', 'ai_extraction_spans__reviewed_by')
            .all()[:10]
        )
        ctx['case_documents'] = ctx['documents']
        ctx['primary_document'] = ctx['documents'][0] if ctx['documents'] else None
        ctx['deadlines'] = case_record.deadlines.filter(is_completed=False)[:5]
        ctx['case_deadlines'] = ctx['deadlines']
        ctx['negotiation_threads'] = case_record.negotiation_threads.all()[:10]
        ctx['case_negotiation_threads'] = ctx['negotiation_threads']
        ctx['related_case_matter'] = case_record.matter
        ctx['lifecycle_guidance'] = build_contract_lifecycle_guidance(case_record)

        # Record-shell convergence: owner/assignee, and the Workflow/Activity
        # tabs' embedded content. Contract has no owner field of its own —
        # reuse the exact same derivation Dashboard/Repository already use
        # (assignee_map_for_contracts), so "who owns this" agrees everywhere.
        org = get_user_organization(self.request.user)
        ctx['owner'] = case_record.owner or case_record.created_by
        approval_requests_qs = case_record.approval_requests.select_related(
            'assigned_to', 'delegated_to',
        ).order_by('sort_order', 'created_at', 'pk')
        approval_requests = list(approval_requests_qs)
        ctx['approval_requests'] = approval_requests[:10]
        ctx['approval_requests_all'] = approval_requests
        ctx['signature_requests'] = case_record.signature_requests.order_by('-created_at')[:10]
        ctx['contract_tasks'] = LegalTask.objects.filter(contract=case_record).select_related(
            'assigned_to',
        ).order_by('due_date')[:10]
        approval_ids = [approval.pk for approval in approval_requests]
        deadline_ids = list(case_record.deadlines.values_list('pk', flat=True))
        dpa_pack_ids = list(case_record.dpa_review_packs.values_list('pk', flat=True))
        activity_filter = Q(model_name='Contract', object_id=case_record.pk)
        if approval_ids:
            activity_filter |= Q(model_name='ApprovalRequest', object_id__in=approval_ids)
        if deadline_ids:
            activity_filter |= Q(model_name='Deadline', object_id__in=deadline_ids)
        if dpa_pack_ids:
            activity_filter |= Q(model_name='DPAReviewPack', object_id__in=dpa_pack_ids)
        activity_entries = list(
            AuditLog.objects.filter(
                activity_filter, organization=org,
            ).select_related('user').order_by('-timestamp')[:40]
        )
        ctx['activity_entries'] = activity_entries
        ctx['contract_risks'] = list(
            RiskLog.objects.filter(contract=case_record).select_related('assigned_to').order_by(
                'risk_level', '-updated_at',
            )[:10]
        )
        ctx['open_findings'] = [
            risk for risk in ctx['contract_risks']
            if risk.status in (RiskLog.Status.OPEN, RiskLog.Status.IN_PROGRESS)
        ]
        ctx['high_risk_findings'] = [
            risk for risk in ctx['open_findings']
            if risk.risk_level in (RiskLog.RiskLevel.HIGH, RiskLog.RiskLevel.CRITICAL)
        ]
        ctx['reviewer_choices'] = User.objects.filter(
            organization_memberships__organization=org,
            organization_memberships__is_active=True,
        ).exclude(pk=case_record.owner_id or case_record.created_by_id).distinct().order_by(
            'first_name', 'last_name', 'username',
        )
        ctx['can_edit'] = can_access_contract_action(self.request.user, case_record, ContractAction.EDIT)
        if 'attach_document_form' not in ctx:
            ctx['attach_document_form'] = self._attachment_form()
        ctx['can_comment'] = can_access_contract_action(self.request.user, case_record, ContractAction.COMMENT)
        policy = OrgPolicy.objects.filter(organization=org).first()
        ctx['ai_features_enabled'] = policy.ai_features_enabled if policy else True
        ctx['ai_provider_configured'] = bool(
            getattr(settings, 'GEMINI_AI_ENABLED', False)
            and getattr(settings, 'GEMINI_API_KEY', '')
        )
        ctx['can_use_ai'] = (
            ctx['ai_features_enabled']
            and can_access_contract_action(self.request.user, case_record, ContractAction.AI)
        )
        ctx['ai_clause_span_count'] = sum(
            len(document.ai_extraction_spans.all()) for document in ctx['documents']
        )
        document_ids = [document.pk for document in ctx['documents']]
        ctx['uploaded_ai_review'] = (
            AuditLog.objects.filter(
                organization=org,
                model_name='Document',
                object_id__in=document_ids,
                event_type='ai.uploaded_contract_review',
            ).order_by('-timestamp').first()
            if document_ids else None
        )
        check_log = AuditLog.objects.filter(
            organization=org,
            model_name='Contract',
            object_id=case_record.pk,
            event_type='contract.grounded_check_completed',
        ).order_by('-timestamp').first()
        check_is_current = bool(check_log and check_log.timestamp >= case_record.updated_at)
        ctx['grounded_check'] = {
            'last_run_at': check_log.timestamp if check_log else None,
            'is_current': check_is_current,
            'label': 'Complete' if check_is_current else 'Needs refresh',
        }
        ctx['signature_routing_blockers'] = get_signature_routing_blockers(case_record)
        ctx['can_route_for_signature'] = ctx['can_edit'] and not ctx['signature_routing_blockers']
        ctx['open_approval'] = case_record.approval_requests.filter(
            status__in=[ApprovalRequest.Status.PENDING, ApprovalRequest.Status.ESCALATED],
        ).select_related('assigned_to').order_by('-created_at').first()
        if ctx['open_approval']:
            from contracts.services.approval_workflow import actor_can_decide
            ctx['can_decide_approval'] = actor_can_decide(
                ctx['open_approval'], self.request.user, 'approve',
            )
        else:
            ctx['can_decide_approval'] = False
        ctx['dpa_review_pack'] = case_record.dpa_review_packs.order_by('-created_at').first()
        pending_approvals = [
            approval for approval in approval_requests
            if approval.status in (ApprovalRequest.Status.PENDING, ApprovalRequest.Status.ESCALATED)
        ]
        activity_feed = []

        def _actor_snapshot(user):
            if user:
                actor_name = user.get_full_name() or user.username
                actor_initial = (user.first_name or user.username or '?')[:1].upper()
            else:
                actor_name = 'System'
                actor_initial = 'S'
            return actor_name, actor_initial

        def _audit_detail(changes, event_type=None):
            return format_contract_audit_activity_detail(changes, event_type=event_type)

        for log in activity_entries:
            actor_name, actor_initial = _actor_snapshot(log.user)
            activity_feed.append({
                'kind': 'audit',
                'timestamp': log.timestamp,
                'actor_name': actor_name,
                'actor_initial': actor_initial,
                'title': f'{actor_name} {log.get_action_display().lower()} {object_type_label(log.model_name)}',
                'detail': _audit_detail(log.changes or {}, getattr(log, 'event_type', None)),
                'badge_label': 'Audit',
                'badge_class': 'badge-gray',
                'log': log,
            })

        negotiation_threads = list(case_record.negotiation_threads.select_related('created_by').order_by('-created_at')[:10])
        for note in negotiation_threads:
            actor_name, actor_initial = _actor_snapshot(note.created_by)
            activity_feed.append({
                'kind': 'note',
                'timestamp': note.created_at,
                'actor_name': actor_name,
                'actor_initial': actor_initial,
                'title': note.title,
                'detail': note.content,
                'badge_label': 'Internal note',
                'badge_class': 'badge-blue',
                'note': note,
            })
        activity_feed.sort(key=lambda item: item['timestamp'], reverse=True)
        ctx['contract_activity_feed'] = activity_feed[:12]
        ctx['recent_activity_feed'] = activity_feed[:5]
        ctx['negotiation_threads'] = negotiation_threads
        collaboration_participants = list(
            case_record.counterparty_collaboration_participants.select_related('invited_by').all()[:20]
        )
        collaboration_items = list(
            case_record.counterparty_collaboration_items.select_related(
                'participant', 'created_by', 'document'
            ).all()[:8]
        )
        ctx['counterparty_collaboration'] = {
            'participants': collaboration_participants,
            'items': collaboration_items,
            'active_count': sum(
                1 for participant in collaboration_participants
                if participant.status in (
                    CounterpartyCollaborationParticipant.Status.PENDING,
                    CounterpartyCollaborationParticipant.Status.ACTIVE,
                ) and participant.is_accessible
            ),
            'shared_document_count': case_record.documents.filter(
                share_with_counterparty=True, is_privileged=False, is_deleted=False,
            ).count(),
            'can_manage': ctx['can_edit'],
        }
        approved_count = sum(
            1 for approval in approval_requests
            if approval.status == ApprovalRequest.Status.APPROVED
        )
        approval_total_count = len(approval_requests)
        approval_create_url = f"{reverse('contracts:approval_request_create')}?contract={case_record.pk}"
        paper_source_label = case_record.get_paper_source_display() if case_record.paper_source else 'Not set'
        paper_source_complete = bool(case_record.paper_source)
        workflow_ready = bool(
            case_record.title
            and case_record.contract_type
            and case_record.counterparty
            and case_record.owner_id
            and paper_source_complete
        )
        ctx['approval_summary'] = {
            'label': (
                f'{approved_count} of {approval_total_count} approved'
                if approval_total_count
                else 'No approvers yet'
            ),
            'approved_count': approved_count,
            'total_count': approval_total_count,
            'create_url': approval_create_url,
            'has_approvers': approval_total_count > 0,
            'can_edit_chain': ctx['can_edit'] and approval_total_count > 1,
        }
        playbook_usage_qs = ClauseUsageEvent.objects.filter(
            organization=org,
            contract=case_record,
            clause__is_approved=True,
        ).select_related('clause', 'performed_by')
        playbook_usage_count = playbook_usage_qs.count()
        playbook_usage_unique_clause_count = playbook_usage_qs.values('clause_id').distinct().count()
        playbook_usage_top_clauses = [
            {
                'title': row['clause__title'],
                'count': row['total'],
            }
            for row in (
                playbook_usage_qs.values('clause_id', 'clause__title')
                .annotate(total=Count('pk'))
                .order_by('-total', 'clause__title')[:3]
            )
        ]
        ctx['playbook_usage_summary'] = {
            'has_data': playbook_usage_count > 0,
            'event_count': playbook_usage_count,
            'unique_clause_count': playbook_usage_unique_clause_count,
            'top_clauses': playbook_usage_top_clauses,
            'summary': (
                f'{playbook_usage_unique_clause_count} approved clause'
                f'{"s" if playbook_usage_unique_clause_count != 1 else ""}'
                f' used across {playbook_usage_count} recorded event'
                f'{"s" if playbook_usage_count != 1 else ""}.'
            ),
        }
        review_changes = (ctx['uploaded_ai_review'].changes if ctx['uploaded_ai_review'] else {}) or {}
        review_completed = review_changes.get('review_status') == 'completed'
        review_finding_count = int(review_changes.get('finding_count') or 0)
        has_documents = bool(ctx['documents'])
        review_label, review_badge_class = derive_contract_review_status(
            has_documents=has_documents,
            review_completed=review_completed,
            check_is_current=check_is_current,
            has_grounded_check=bool(check_log),
            has_uploaded_review=bool(ctx['uploaded_ai_review']),
        )
        submit_readiness = get_submit_readiness(
            can_edit=ctx['can_edit'],
            status=case_record.status,
            has_documents=has_documents,
            review_status=review_label,
            has_reviewer_choices=ctx['reviewer_choices'].exists(),
        )
        ctx['submit_readiness'] = submit_readiness
        ctx['can_submit_for_review'] = submit_readiness['ready']
        ctx['workflow_checklist'] = [
            {
                'label': 'Record basics',
                'status': 'Complete' if workflow_ready else 'Needs input',
                'badge_class': 'badge-green' if workflow_ready else 'badge-yellow',
                'detail': 'Title, counterparty, owner and paper source are captured.',
            },
            {
                'label': 'Contract review',
                'status': review_label,
                'badge_class': review_badge_class,
                'detail': 'Grounded evidence must match the current source document.',
            },
            {
                'label': 'Approval route',
                'status': (
                    f'{approved_count} of {approval_total_count} approved'
                    if approval_total_count
                    else 'Not started'
                ),
                'badge_class': 'badge-green' if approval_total_count and approved_count == approval_total_count else 'badge-yellow' if approval_total_count else 'badge-gray',
                'detail': 'Shows whether the contract has a recorded approval chain.',
            },
            {
                'label': 'Paper source',
                'status': paper_source_label,
                'badge_class': 'badge-green' if paper_source_complete else 'badge-gray',
                'detail': 'Used to set intake expectations and review routing.',
            },
        ]

        if ctx['high_risk_findings']:
            risk_label, risk_badge_class = 'High-risk findings open', 'badge-red'
        elif ctx['open_findings']:
            risk_label, risk_badge_class = 'Open findings', 'badge-yellow'
        else:
            if (
                case_record.status == Contract.Status.IN_PROGRESS
                and case_record.lifecycle_stage == 'DRAFTING'
                and not review_completed
            ):
                created_audit = next(
                    (
                        audit for audit in AuditLog.objects.filter(
                            model_name='Contract', object_id=case_record.pk,
                        ).order_by('-timestamp')[:20]
                        if isinstance(audit.changes, dict) and audit.changes.get('event') == 'contract_created'
                    ),
                    None,
                )
                audited_assessment = (created_audit.changes or {}).get('risk_assessment', {}) if created_audit else {}
                intake_assessment = assess_intake_risk(case_record.__dict__)
                intake_level = audited_assessment.get('level') or intake_assessment.level
                risk_label = audited_assessment.get('label') or intake_assessment.label
                if not intake_level or 'not assessed' in str(risk_label).casefold():
                    risk_badge_class = 'badge-gray'
                else:
                    risk_badge_class = {
                        Contract.RiskLevel.CRITICAL: 'badge-red',
                        Contract.RiskLevel.HIGH: 'badge-yellow',
                        Contract.RiskLevel.MEDIUM: 'badge-blue',
                        Contract.RiskLevel.LOW: 'badge-green',
                    }.get(intake_level, 'badge-gray')
            elif review_completed:
                risk_label = f'Reviewed {case_record.get_risk_level_display()} risk'
                risk_badge_class = {
                    Contract.RiskLevel.CRITICAL: 'badge-red',
                    Contract.RiskLevel.HIGH: 'badge-yellow',
                    Contract.RiskLevel.MEDIUM: 'badge-blue',
                    Contract.RiskLevel.LOW: 'badge-green',
                }.get(case_record.risk_level, 'badge-gray')
            else:
                risk_label = f'{case_record.get_risk_level_display()} risk'
                # Unreviewed record-level defaults are not completed assessments.
                if case_record.risk_level == Contract.RiskLevel.LOW:
                    risk_badge_class = 'badge-yellow'
                    if case_record.status == Contract.Status.IN_PROGRESS:
                        risk_label = 'Risk reassessment required'
                else:
                    risk_badge_class = {
                        Contract.RiskLevel.CRITICAL: 'badge-red',
                        Contract.RiskLevel.HIGH: 'badge-yellow',
                        Contract.RiskLevel.MEDIUM: 'badge-blue',
                        Contract.RiskLevel.LOW: 'badge-green',
                    }.get(case_record.risk_level, 'badge-gray')

        risk_tone = {
            'badge-red': 'danger',
            'badge-yellow': 'attention',
            'badge-blue': 'progress',
            'badge-green': 'success',
            'badge-gray': 'neutral',
        }.get(risk_badge_class, 'neutral')
        incomplete_risk = any(
            token in str(risk_label).casefold()
            for token in ('not assessed', 'incomplete', 'reassessment required')
        )
        if incomplete_risk:
            # Reserve green for completed assessments with no material risk.
            risk_tone = 'attention'
            if risk_badge_class == 'badge-green':
                risk_badge_class = 'badge-yellow'

        ctx['contract_command'] = build_contract_command(
            contract=case_record,
            has_documents=has_documents,
            review_status=review_label,
            review_badge_class=review_badge_class,
            review_finding_count=review_finding_count,
            high_risk_findings=ctx['high_risk_findings'],
            open_findings=ctx['open_findings'],
            can_decide_approval=ctx['can_decide_approval'],
            open_approval=ctx['open_approval'],
            can_submit_for_review=ctx['can_submit_for_review'],
            can_route_for_signature=ctx['can_route_for_signature'],
            can_edit=ctx['can_edit'],
            lifecycle_guidance=ctx['lifecycle_guidance'],
            pending_approvals=pending_approvals,
            approval_requests=approval_requests,
            signature_routing_blockers=ctx['signature_routing_blockers'],
            risk_label=risk_label,
            risk_badge_class=risk_badge_class,
        )
        ctx['current_blockers'] = ctx['contract_command']['current_blockers']
        ctx['later_workflow_requirements'] = ctx['contract_command']['later_workflow_requirements']
        ctx['lifecycle_command_label'] = ctx['contract_command']['lifecycle_label']
        ctx['lifecycle_command_badge_class'] = ctx['contract_command']['lifecycle_badge_class']

        raw_tab = self.request.GET.get('tab')
        active_tab = normalize_contract_detail_tab(raw_tab)
        ctx['active_tab'] = active_tab
        ctx['workspace_tabs'] = build_contract_detail_tabs(case_record.pk, active_tab)
        workflow_section = normalize_workflow_section(
            self.request.GET.get('section'),
            raw_tab=raw_tab,
        )
        ctx['workflow_section'] = workflow_section
        ctx['workflow_section_tabs'] = build_workflow_section_tabs(case_record.pk, workflow_section)
        ctx['overview_tab_url'] = contract_detail_tab_url(case_record.pk, 'overview')
        ctx['workflow_tab_url'] = contract_detail_tab_url(case_record.pk, 'workflow')
        ctx['workflow_review_url'] = f"{ctx['workflow_tab_url']}&section=review" if '?' in ctx['workflow_tab_url'] else f"{ctx['workflow_tab_url']}?section=review"
        ctx['workflow_approvals_url'] = f"{ctx['workflow_tab_url']}&section=approvals" if '?' in ctx['workflow_tab_url'] else f"{ctx['workflow_tab_url']}?section=approvals"
        ctx['contract_obligations'] = list(
            case_record.deadlines.select_related('assigned_to').order_by('due_date', 'pk')[:20]
        )
        upcoming_items = []
        if case_record.renewal_date:
            upcoming_items.append({'label': 'Renewal', 'date': case_record.renewal_date})
        if case_record.end_date:
            upcoming_items.append({'label': 'Expiry', 'date': case_record.end_date})
        for deadline in ctx['deadlines']:
            upcoming_items.append({'label': deadline.title, 'date': deadline.due_date})
        upcoming_items.sort(key=lambda item: item['date'] or date.max)
        ctx['upcoming_dates'] = upcoming_items[:5]
        ctx['next_milestone'] = upcoming_items[0] if upcoming_items else None
        ctx['obligations_workspace_url'] = (
            f"{reverse('contracts:obligations_workspace')}?contract={case_record.pk}"
        )
        ctx['overview_risk_snapshot'] = {
            'label': risk_label,
            'badge_class': risk_badge_class,
            'tone': risk_tone,
            'findings': list(ctx['open_findings'][:3]),
            'high_risk_count': len(ctx['high_risk_findings']),
            'open_count': len(ctx['open_findings']),
        }
        ctx['lifecycle_path'] = lifecycle_steps(case_record)
        ctx['overview_progress'] = build_overview_progress(
            case_record,
            lifecycle_path=ctx['lifecycle_path'],
            next_milestone=ctx['next_milestone'],
            current_blockers=ctx['current_blockers'],
            later_workflow_requirements=ctx['later_workflow_requirements'],
        )
        return ctx


@login_required
def legal_front_door(request):
    """The Legal Front Door: "What legal work do you need?" — the entry
    point ahead of the contract-type picker. Every option below routes to
    an existing, already-governed CLM One destination; this view adds no
    new domain model and no new permission surface, it only assembles
    links. Shared/mode-neutral per docs/WORKSPACE_MODE_CONTAINMENT.md —
    every option applies equally to law_firm_ops and in_house_clm tenants,
    so this view does not branch on workspace_mode."""
    options = [
        {
            'key': 'create',
            'title': 'Create a contract',
            'description': 'Select a contract type. CLM One applies the right approved template, playbook, and approval route.',
            'icon': 'document',
            'href': reverse('contracts:contract_template_picker'),
        },
        {
            'key': 'review',
            'title': 'Review a contract',
            'description': 'Open an existing contract to review its terms, status, and risk position.',
            'icon': 'search',
            'href': reverse('contracts:repository'),
        },
        {
            'key': 'upload',
            'title': 'Upload signed contract',
            'description': 'Ingest an already-signed agreement into the repository for tracking and obligations.',
            'icon': 'upload',
            'href': reverse('contracts:upload_signed_contract'),
        },
        {
            'key': 'dpa_review',
            'title': 'Start DPA review',
            'description': 'Assess an existing contract for privacy risk — SCC position, subprocessors, data transfers.',
            'icon': 'shield',
            'href': reverse('contracts:dpa_review_pack_list'),
        },
        {
            'key': 'legal_question',
            'title': 'Ask a legal question',
            'description': 'Log a question for the Legal team and track it as an assigned task.',
            'icon': 'question',
            'href': reverse('contracts:legal_task_create'),
        },
        {
            'key': 'approval',
            'title': 'Request approval',
            'description': 'Send a contract or decision through the approval routing engine.',
            'icon': 'approval',
            'href': reverse('contracts:approval_request_list'),
        },
        {
            'key': 'renewal',
            'title': 'Start renewal / amendment',
            'description': 'Draft an amendment or renewal against an existing agreement.',
            'icon': 'edit',
            'href': f"{reverse('contracts:contract_create')}?type={Contract.ContractType.AMENDMENT}",
        },
    ]
    return render(request, 'legal_front_door.html', {'legal_work_options': options})


@login_required
def upload_signed_contract(request):
    """Render the existing-agreement intake form.

    The CSRF-protected multipart API creates both the draft contract record
    and its persisted source document; this view supplies tenant-scoped owner
    choices and canonical contract metadata options.
    """
    organization = get_user_organization(request.user)
    owners = User.objects.filter(
        organization_memberships__organization=organization,
        organization_memberships__is_active=True,
    ).distinct().order_by('first_name', 'last_name', 'username')
    policy_enabled = OrgPolicy.objects.filter(organization=organization).values_list(
        'ai_features_enabled', flat=True,
    ).first()
    if policy_enabled is None:
        policy_enabled = True
    provider_configured = bool(
        getattr(settings, 'GEMINI_AI_ENABLED', False)
        and getattr(settings, 'GEMINI_API_KEY', '')
    )
    ai_review_available = bool(policy_enabled and provider_configured)
    if not policy_enabled:
        ai_review_unavailable_reason = 'AI review is disabled by this workspace’s data controls.'
    elif not provider_configured:
        ai_review_unavailable_reason = 'AI review is not configured for this environment. Your agreement can still be stored and reviewed manually.'
    else:
        ai_review_unavailable_reason = ''
    return render(request, 'contracts/upload_signed_contract.html', {
        'contract_types': Contract.ContractType.choices,
        'currencies': Contract.Currency.choices,
        'owners': owners,
        'matters': Matter.objects.filter(organization=organization).order_by('title')[:100],
        'ai_review_available': ai_review_available,
        'ai_review_unavailable_reason': ai_review_unavailable_reason,
        'hide_app_footer': True,
    })


@login_required
def contract_review_workspace(request, pk):
    """Single review surface for an uploaded agreement version and its evidence."""
    organization = get_user_organization(request.user)
    contract = get_object_or_404(Contract, pk=pk, organization=organization)
    review_run = contract.document_review_runs.select_related('document').order_by('-started_at').first()
    document = review_run.document if review_run else contract.documents.order_by('-version', '-created_at').first()

    if request.method == 'POST':
        if not can_access_contract_action(request.user, contract, ContractAction.EDIT):
            return HttpResponseForbidden('You do not have permission to update this review.')
        if review_run is None:
            messages.error(request, 'Create an uploaded document review before resolving review blockers.')
            return redirect('contracts:contract_review_workspace', pk=contract.pk)
        action = (request.POST.get('action') or '').strip()
        metadata = dict(review_run.extracted_metadata or {})
        governance = dict(review_run.governance_sources or {})
        contract_fields = []
        if action == 'confirm_counterparty':
            contract.counterparty = (request.POST.get('counterparty') or '').strip()
            if not contract.counterparty:
                messages.error(request, 'Enter the confirmed counterparty to continue.')
            else:
                contract_fields.append('counterparty')
        elif action == 'confirm_contract_type':
            contract_type = (request.POST.get('contract_type') or '').strip()
            if contract_type not in Contract.ContractType.values or contract_type == Contract.ContractType.OTHER:
                messages.error(request, 'Select the confirmed contract type to continue.')
            else:
                contract.contract_type = contract_type
                contract_fields.append('contract_type')
        elif action == 'confirm_governing_law':
            contract.governing_law = (request.POST.get('governing_law') or '').strip()
            if not contract.governing_law:
                messages.error(request, 'Enter the confirmed governing law to continue.')
            else:
                metadata['governing_law_confirmed'] = True
                contract_fields.append('governing_law')
        elif action == 'confirm_value':
            raw_value = (request.POST.get('value') or '').strip()
            try:
                contract.value = Decimal(raw_value)
            except Exception:
                messages.error(request, 'Enter a valid contract value to continue.')
            else:
                metadata['value_confirmed'] = True
                contract_fields.append('value')
        elif action == 'confirm_payment_terms':
            payment_terms = (request.POST.get('payment_terms') or '').strip()
            if not payment_terms:
                messages.error(request, 'Enter the confirmed payment terms to continue.')
            else:
                metadata['payment_terms'] = payment_terms
                metadata['payment_terms_confirmed'] = True
        elif action == 'select_playbook':
            playbook = ClausePlaybook.objects.filter(
                pk=request.POST.get('playbook_id'), organization=organization, is_active=True,
            ).first()
            if playbook is None:
                messages.error(request, 'Select an active approved playbook to continue.')
            else:
                governance.update({
                    'selected_playbook_id': playbook.pk,
                    'selected_playbook_name': playbook.name,
                    'approved_playbook_matched': True,
                })
        elif action == 'retry_preview':
            governance['preview_retry_requested_at'] = timezone.now().isoformat()
            messages.info(request, 'Preview retry requested. The original file remains available to download while rendering is retried.')
        elif action == 'run_ai_review':
            state = _document_review_state(contract, document, review_run, finding_count=0)
            if state['can_run_ai_review']:
                from contracts.api.documents_ai import _run_uploaded_contract_review
                _run_uploaded_contract_review(
                    request=request, organization=organization, document=document, review_run=review_run,
                )
                messages.success(request, 'AI review was started using the confirmed contract information and review basis.')
            else:
                messages.error(request, 'Resolve the required review blockers before running AI review.')
        if contract_fields:
            contract.save(update_fields=[*contract_fields, 'updated_at'])
        if action in {'confirm_governing_law', 'confirm_value', 'confirm_payment_terms'}:
            review_run.extracted_metadata = metadata
        if action in {'select_playbook', 'retry_preview'}:
            review_run.governance_sources = governance
        if action in {
            'confirm_counterparty', 'confirm_contract_type', 'confirm_governing_law',
            'confirm_value', 'confirm_payment_terms', 'select_playbook',
        }:
            state = _document_review_state(contract, document, review_run, finding_count=0)
            if not state['classification_complete']:
                review_run.status = DocumentReviewRun.Status.CLASSIFICATION_REQUIRED
                review_run.current_step = 'Classifying'
                review_run.primary_next_action = 'Confirm the required contract information before AI review can begin.'
            elif not state['playbook_confirmed']:
                review_run.status = DocumentReviewRun.Status.PLAYBOOK_REQUIRED
                review_run.current_step = 'Matching playbook'
                review_run.primary_next_action = 'Select an approved contract playbook before AI review can begin.'
            elif not state['analysis_completed']:
                review_run.status = DocumentReviewRun.Status.AI_REVIEW_INCOMPLETE
                review_run.current_step = 'AI reviewing'
                review_run.primary_next_action = 'Run AI review using the confirmed contract information and approved playbook.'
        if action != 'run_ai_review':
            review_run.save()
        return redirect('contracts:contract_review_workspace', pk=contract.pk)
    findings = (
        ContractReviewFinding.objects.filter(review_run=review_run)
        .select_related('source_span', 'assigned_reviewer', 'source_span__source_template')
        .order_by('severity', 'created_at')
        if review_run else ContractReviewFinding.objects.none()
    )
    finding_counts = {severity: findings.filter(severity=severity).count() for severity, _ in ContractReviewFinding.Severity.choices}
    reviewers = User.objects.filter(
        organization_memberships__organization=organization,
        organization_memberships__is_active=True,
    ).distinct().order_by('first_name', 'last_name', 'username')
    spans = document.ai_extraction_spans.select_related('source_template').all() if document else []
    activity = AuditLog.objects.filter(
        Q(model_name='Contract', object_id=contract.pk)
        | Q(model_name='Document', object_id=document.pk if document else 0),
        organization=organization,
    ).order_by('-timestamp')[:20]
    review_state = _document_review_state(contract, document, review_run, finding_count=findings.count())
    workspace_tabs = build_contract_detail_tabs(contract.pk, 'workflow')
    for tab in workspace_tabs:
        if tab['key'] == 'workflow':
            tab['url'] = reverse('contracts:contract_review_workspace', kwargs={'pk': contract.pk})
            break
    return render(request, 'contracts/contract_review_workspace.html', {
        'contract': contract,
        'review_run': review_run,
        'document': document,
        'findings': findings,
        'finding_counts': finding_counts,
        'reviewers': reviewers,
        'spans': spans,
        'activity': activity,
        'review_state': review_state,
        'playbooks': ClausePlaybook.objects.filter(organization=organization, is_active=True).order_by('name'),
        'contract_types': Contract.ContractType.choices,
        'workspace_tabs': workspace_tabs,
        'active_tab': 'workflow',
        'workflow_section': 'review',
        'can_edit': can_access_contract_action(request.user, contract, ContractAction.EDIT),
        'hide_app_footer': True,
    })


def _document_review_state(contract, document, review_run, *, finding_count):
    """Derive the visible review state from evidence, never from optimistic labels."""
    metadata = (review_run.extracted_metadata if review_run else {}) or {}
    governance = (review_run.governance_sources if review_run else {}) or {}
    try:
        extracted_text = document.ocr_review.extracted_text or ''
    except Exception:
        extracted_text = ''
    extraction_complete = bool(extracted_text.strip()) or bool(
        review_run and governance.get('citation_count') is not None
    )
    preview_available = bool(document and document.file and document.file_extension in {'.pdf', '.txt', '.md', '.html'})
    counterparty_confirmed = bool((contract.counterparty or '').strip())
    type_confirmed = contract.contract_type != Contract.ContractType.OTHER
    law_confirmed = bool((contract.governing_law or '').strip() and metadata.get('governing_law_confirmed'))
    value_confirmed = contract.value is not None and bool(metadata.get('value_confirmed'))
    payment_hint = bool((metadata.get('payment_terms') or '').strip())
    payment_confirmed = bool(metadata.get('payment_terms_confirmed')) if payment_hint else True
    playbook_confirmed = bool(governance.get('approved_playbook_matched') or governance.get('selected_playbook_id'))
    analysis_completed = bool(governance.get('ai_analysis_completed'))
    blockers = []
    if not counterparty_confirmed:
        blockers.append({'key': 'counterparty', 'label': 'Counterparty', 'state': 'Needs confirmation', 'action': 'Confirm'})
    if not type_confirmed:
        blockers.append({'key': 'contract_type', 'label': 'Contract type', 'state': 'Needs confirmation', 'action': 'Confirm'})
    if not law_confirmed:
        blockers.append({'key': 'governing_law', 'label': 'Governing law', 'state': 'Not confidently extracted', 'action': 'Confirm'})
    if not value_confirmed:
        blockers.append({'key': 'value', 'label': 'Contract value', 'state': 'Not confidently extracted', 'action': 'Confirm'})
    if payment_hint and not payment_confirmed:
        blockers.append({'key': 'payment_terms', 'label': 'Payment terms', 'state': 'Not confidently extracted', 'action': 'Confirm'})
    if not playbook_confirmed:
        blockers.append({'key': 'playbook', 'label': 'Review playbook', 'state': 'Not matched', 'action': 'Select playbook'})
    if not analysis_completed:
        blockers.append({'key': 'findings', 'label': 'AI findings', 'state': 'Not yet generated', 'action': 'Run review'})
    classification_complete = (
        counterparty_confirmed and type_confirmed and law_confirmed and value_confirmed and payment_confirmed
    )
    prerequisites_complete = extraction_complete and classification_complete and playbook_confirmed
    ready = prerequisites_complete and analysis_completed
    current_status = review_run.status if review_run else DocumentReviewRun.Status.UPLOADED
    if not extraction_complete:
        status_label, status_class, status_badge_tone = 'AI review incomplete', 'badge-red', 'danger'
    elif not prerequisites_complete:
        status_label, status_class, status_badge_tone = 'Needs input', 'badge-yellow', 'attention'
    elif current_status == DocumentReviewRun.Status.AI_REVIEW_IN_PROGRESS:
        status_label, status_class, status_badge_tone = 'AI review in progress', 'badge-blue', 'progress'
    elif ready and contract.lifecycle_stage == Contract.LifecycleStage.INTERNAL_REVIEW:
        status_label, status_class, status_badge_tone = 'Human review in progress', 'badge-blue', 'progress'
    elif ready:
        status_label, status_class, status_badge_tone = 'AI review ready', 'badge-green', 'success'
    else:
        status_label, status_class, status_badge_tone = 'AI review incomplete', 'badge-red', 'danger'
    if not extraction_complete:
        current_step = 'Extracting'
    elif not classification_complete:
        current_step = 'Classifying'
    elif not playbook_confirmed:
        current_step = 'Matching playbook'
    elif not ready:
        current_step = 'AI reviewing'
    else:
        current_step = 'Review ready'
    steps = []
    labels = ('Uploaded', 'Extracting', 'Classifying', 'Matching playbook', 'AI reviewing', 'Review ready')
    current_index = labels.index(current_step)
    for index, label in enumerate(labels):
        state = 'complete' if index < current_index else ('active' if index == current_index else 'pending')
        if not extraction_complete and label == 'Extracting':
            state = 'blocked'
        elif label == 'Classifying' and extraction_complete and not classification_complete:
            state = 'blocked'
        elif label == 'Matching playbook' and extraction_complete and classification_complete and not playbook_confirmed:
            state = 'blocked'
        steps.append({'key': label.lower().replace(' ', '-'), 'label': label, 'status': state})
    return {
        'status_label': status_label,
        'status_class': status_class,
        'status_badge_tone': status_badge_tone,
        'stage_label': 'Internal review' if not ready else contract.get_lifecycle_stage_display(),
        'primary_action': 'Start human review' if ready else ('Run AI review' if prerequisites_complete else 'Resolve review blockers'),
        'message': (
            'AI review could not be completed. The document preview failed, no approved playbook was matched and required contract information needs confirmation.'
            if not ready else 'AI review is ready for a human-owned review decision.'
        ),
        'blockers': blockers,
        'steps': steps,
        'preview_available': preview_available,
        'extraction_complete': extraction_complete,
        'classification_complete': classification_complete,
        'playbook_confirmed': playbook_confirmed,
        'analysis_completed': analysis_completed,
        'findings_ready': ready,
        'can_run_ai_review': prerequisites_complete and not analysis_completed,
        'finding_count': finding_count,
    }


@login_required
def contract_template_picker(request):
    """Step 1 of contract creation: pick a contract type, then a template.

    Templates are optional per type — types with none just show a "Start
    blank" card, same as today's create form with that type preselected.

    The no-type screen shows the curated entry-card grid (get_entry_cards)
    for the six highest-traffic types; every type — including ones without
    a card — stays reachable via the full dropdown once inside the form,
    same as before this screen existed.
    """
    contract_type = request.GET.get('type')
    context = {'contract_types': Contract.ContractType.choices}
    if contract_type:
        context['selected_type'] = contract_type
        context['selected_type_label'] = dict(Contract.ContractType.choices).get(contract_type, contract_type)
        context['templates'] = ContractTemplate.objects.filter(contract_type=contract_type, is_active=True)
    else:
        # DPA, MSA, and NDA are the governed drafting reference flows — their
        # cards start dedicated workflow builders instead of the legacy
        # generic intake form. Other curated cards stay unchanged.
        def start_url_for(ct):
            if ct == Contract.ContractType.DPA:
                return reverse('contracts:dpa_workflow_builder')
            if ct == Contract.ContractType.MSA:
                return reverse('contracts:msa_workflow_builder')
            if ct == Contract.ContractType.NDA:
                return reverse('contracts:nda_workflow_builder')
            return f"{reverse('contracts:contract_create')}?type={ct}"

        org = get_user_organization(request.user)
        context['entry_sections'] = get_entry_card_sections(
            start_url_for=start_url_for,
            organization=org,
            user=request.user,
        )
        context['entry_cards'] = [
            card for section in context['entry_sections'] for card in section.cards
        ]
    return render(request, 'contracts/contract_template_picker.html', context)


class ContractCreateView(TenantAssignCreateMixin, LoginRequiredMixin, CreateView):
    model = Contract
    form_class = ContractForm
    template_name = 'contracts/contract_form.html'
    success_url = reverse_lazy('contracts:repository')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organization'] = get_user_organization(self.request.user)
        kwargs['actor'] = self.request.user
        kwargs['selected_template'] = self._selected_template()
        return kwargs

    def _selected_template(self):
        template_id = self.request.GET.get('template')
        if not template_id:
            return None
        return ContractTemplate.objects.filter(pk=template_id, is_active=True).first()

    def get_initial(self):
        initial = super().get_initial()
        template = self._selected_template()
        if template:
            initial['contract_type'] = template.contract_type
            initial['content'] = template.body
        elif self.request.GET.get('type'):
            initial['contract_type'] = self.request.GET.get('type')
        initial.setdefault('owner', self.request.user)
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        selected_template = self._selected_template()
        ctx['selected_template'] = selected_template
        ctx['launch_setup_map'] = get_launch_setup_map()
        ctx['intake_risk_policy'] = intake_risk_client_policy()
        ctx['intake_routing_policy'] = intake_routing_client_policy()
        ctx['hide_app_footer'] = True
        ctx['can_view_approval_routing'] = can_manage_organization(
            self.request.user, get_user_organization(self.request.user),
        )
        org = get_user_organization(self.request.user)
        contract_type = (
            ctx['form'].initial.get('contract_type')
            or self.request.GET.get('type')
            or Contract.ContractType.OTHER
        )
        ctx['governance_panel'] = get_governance_panel(org, contract_type, None)
        return ctx

    @staticmethod
    def _build_preview_sections(form):
        draft_sections = list(form.cleaned_data.get('draft_sections') or [])
        if draft_sections:
            preview_sections = []
            for index, section in enumerate(draft_sections):
                preview_sections.append({
                    'index': index,
                    'order': section.get('order', index + 1),
                    'include': True,
                    'title': section.get('title', ''),
                    'content': section.get('content', ''),
                    'source_label': 'Edited draft section',
                })
            return preview_sections

        clause_templates = list(form.cleaned_data.get('clause_templates') or [])
        preview_sections = []
        for index, clause_template in enumerate(clause_templates, start=1):
            section = form.build_clause_preview_section(clause_template)
            section.update({
                'index': index - 1,
                'order': index,
                'include': True,
                'template_url': reverse('contracts:clause_template_detail', kwargs={'pk': clause_template.pk}),
                'playbook_url': reverse('contracts:clause_template_detail', kwargs={'pk': clause_template.pk}) + '#playbooks' if section.get('resolved_playbook') else '',
            })
            preview_sections.append(section)
        return preview_sections

    def _render_preview(self, form):
        draft_sections = self._build_preview_sections(form)
        return render(
            self.request,
            self.template_name,
            {
                'form': form,
                'form_action': reverse('contracts:contract_create'),
                'draft_sections': draft_sections,
                'draft_preview_selected_clause_count': len(draft_sections),
                'preview_mode': True,
                'selected_template': form.selected_template_for_intake(),
                'launch_setup_map': get_launch_setup_map(),
                'intake_risk_policy': intake_risk_client_policy(),
                'intake_routing_policy': intake_routing_client_policy(),
                'hide_app_footer': True,
                'can_view_approval_routing': can_manage_organization(
                    self.request.user, get_user_organization(self.request.user),
                ),
            },
        )

    def post(self, request, *args, **kwargs):
        # BaseCreateView normally initializes ``self.object`` before building
        # a form.  The preview branch intentionally bypasses that base
        # implementation, so initialise it here as well; otherwise an invalid
        # preview submission crashes while rendering its validation errors.
        self.object = None
        if 'preview_draft' in request.POST:
            form = self.get_form()
            if form.is_valid():
                return self._render_preview(form)
            return self.form_invalid(form)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        set_organization_on_instance(form.instance, get_user_organization(self.request.user))
        form.instance.created_by = self.request.user
        parent_id = self.request.GET.get('parent') or self.request.POST.get('parent_contract_id')
        if parent_id:
            parent = (
                scope_queryset_for_organization(Contract.objects.all(), get_user_organization(self.request.user))
                .filter(pk=parent_id)
                .first()
            )
            if parent:
                form.instance.parent_contract = parent
        # New contracts always start IN_PROGRESS at DRAFTING; reaching ACTIVE
        # must go through activate_contract / lifecycle transitions.
        form.instance.status = Contract.Status.IN_PROGRESS
        form.instance.lifecycle_stage = Contract.LifecycleStage.DRAFTING
        assessment = form.intake_risk_assessment()
        route_decision = form.intake_route_decision()
        form.instance.risk_level = assessment.level or Contract.RiskLevel.LOW
        # Resolve any {{merge_field}} tokens against the instance's own
        # cleaned field values — harmless no-op if the content has none,
        # so this runs whether or not a template was used to start the draft.
        form.instance.content = render_merge_fields(form.instance.content, form.instance)
        from contracts.services.contract_provenance import (
            EVENT_PROVENANCE_ASSIGNED,
            OriginKind,
            apply_provenance_fields,
            provenance_snapshot,
        )
        apply_provenance_fields(
            form.instance,
            origin_kind=OriginKind.MANUAL,
            origin_channel='contract_create_ui',
            origin_reason='Created via contract form',
            actor=self.request.user,
            lock=True,
            validate=True,
        )
        response = super().form_valid(form)
        if self.object.dpa_attached:
            from contracts.services.dpa_activation import ensure_dpa_review_pack
            ensure_dpa_review_pack(self.object, self.request.user, request=self.request)
        snap = provenance_snapshot(self.object)
        log_action(
            self.request.user,
            'CREATE',
            'Contract',
            self.object.id,
            str(self.object),
            changes={
                'event': 'contract_created',
                'equivalent_event': 'contract.record.created',
                'status': self.object.status,
                'lifecycle_stage': self.object.lifecycle_stage,
                'contract_type': self.object.contract_type,
                'owner_id': self.object.owner_id,
                'counterparty': self.object.counterparty,
                'start_date': self.object.start_date.isoformat() if self.object.start_date else None,
                'end_date': self.object.end_date.isoformat() if self.object.end_date else None,
                'risk_assessment': assessment.as_dict(),
                'routing_decision': route_decision.as_dict(),
                'selected_template_id': (
                    form.selected_template_for_intake().pk
                    if form.selected_template_for_intake() else None
                ),
                'selected_template_name': (
                    form.selected_template_for_intake().name
                    if form.selected_template_for_intake() else None
                ),
                'selected_playbook': assessment.playbook_name,
                'playbook_applied': assessment.playbook_applied,
                'review_route': route_decision.reviewers,
                'approval_route': route_decision.approvers,
                'provenance': snap,
            },
            request=self.request,
        )
        log_action(
            self.request.user,
            'CREATE',
            'Contract',
            self.object.id,
            str(self.object),
            changes={'event': EVENT_PROVENANCE_ASSIGNED, 'provenance': snap},
            request=self.request,
            event_type=EVENT_PROVENANCE_ASSIGNED,
        )
        messages.success(self.request, f'Contract "{self.object.title}" created.')
        return response


class ContractUpdateView(TenantScopedQuerysetMixin, LoginRequiredMixin, UpdateView):
    model = Contract
    form_class = ContractForm
    template_name = 'contracts/contract_form.html'
    success_url = reverse_lazy('contracts:repository')

    def get_queryset(self):
        org = get_user_organization(self.request.user)
        return scope_queryset_for_organization(Contract.objects.all(), org)

    def _revision_unlocked(self):
        contract = getattr(self, 'object', None) or getattr(self, 'original_contract', None)
        if not contract:
            return False
        from contracts.services.contract_edit_governance import revision_session_key
        return bool(self.request.session.get(revision_session_key(contract.pk)))

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organization'] = get_user_organization(self.request.user)
        kwargs['actor'] = self.request.user
        kwargs['revision_unlocked'] = self._revision_unlocked()
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        org = get_user_organization(self.request.user)
        from contracts.services.contract_edit_governance import build_edit_governance_context
        revision_unlocked = self._revision_unlocked()
        edit_gov = build_edit_governance_context(self.object, revision_unlocked=revision_unlocked)
        ctx['launch_setup_map'] = get_launch_setup_map()
        ctx['intake_risk_policy'] = intake_risk_client_policy()
        ctx['intake_routing_policy'] = intake_routing_client_policy()
        ctx['governance_panel'] = get_governance_panel(org, self.object.contract_type, None, contract=self.object)
        ctx['hide_app_footer'] = True
        ctx['edit_governance'] = edit_gov
        ctx['is_edit_mode'] = True
        ctx['can_view_approval_routing'] = can_manage_organization(self.request.user, org)
        ctx['amendment_create_url'] = (
            reverse('contracts:contract_create')
            + f'?type=AMENDMENT&parent={self.object.pk}'
        )
        return ctx

    @staticmethod
    def _build_preview_sections(form):
        draft_sections = list(form.cleaned_data.get('draft_sections') or [])
        if draft_sections:
            preview_sections = []
            for index, section in enumerate(draft_sections):
                preview_sections.append({
                    'index': index,
                    'order': section.get('order', index + 1),
                    'include': True,
                    'title': section.get('title', ''),
                    'content': section.get('content', ''),
                    'source_label': 'Edited draft section',
                })
            return preview_sections

        clause_templates = list(form.cleaned_data.get('clause_templates') or [])
        preview_sections = []
        for index, clause_template in enumerate(clause_templates, start=1):
            section = form.build_clause_preview_section(clause_template)
            section.update({
                'index': index - 1,
                'order': index,
                'include': True,
                'template_url': reverse('contracts:clause_template_detail', kwargs={'pk': clause_template.pk}),
                'playbook_url': reverse('contracts:clause_template_detail', kwargs={'pk': clause_template.pk}) + '#playbooks' if section.get('resolved_playbook') else '',
            })
            preview_sections.append(section)
        return preview_sections

    def _render_preview(self, form):
        draft_sections = self._build_preview_sections(form)
        context = self.get_context_data(form=form)
        context.update({
            'form': form,
            'contract': self.object,
            'form_action': reverse('contracts:contract_update', kwargs={'pk': self.object.pk}),
            'draft_sections': draft_sections,
            'draft_preview_selected_clause_count': len(draft_sections),
            'preview_mode': True,
            'hide_app_footer': True,
        })
        return render(self.request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.original_contract = self.object
        from contracts.services.contract_edit_governance import revision_session_key
        from contracts.services.contract_versions import get_version_service

        if 'create_new_version' in request.POST:
            version = get_version_service().create_version(
                self.object,
                changed_by=request.user,
                change_summary='Baseline snapshot before governed revision',
            )
            request.session[revision_session_key(self.object.pk)] = True
            log_action(
                request.user,
                'UPDATE',
                'Contract',
                self.object.id,
                str(self.object),
                changes={
                    'event': 'contract_version_created_for_edit',
                    'version_number': version.version_number,
                },
                request=request,
            )
            messages.success(
                request,
                f'Version v{version.version_number} saved. Governed fields are unlocked for this revision.',
            )
            return redirect(reverse('contracts:contract_update', kwargs={'pk': self.object.pk}))

        if 'preview_draft' in request.POST:
            form = self.get_form()
            if form.is_valid():
                return self._render_preview(form)
            return self.form_invalid(form)
        return super().post(request, *args, **kwargs)

    def dispatch(self, request, *args, **kwargs):
        contract = self.get_object()
        self.original_contract = contract
        if not can_access_contract_action(request.user, contract, ContractAction.EDIT):
            return HttpResponseForbidden('You do not have permission to edit this contract.')
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('contracts:contract_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        from contracts.services.contract_edit_governance import (
            GOVERNED_CHANGE_WARNING,
            assess_edit_risk,
            contract_is_governance_locked,
            governed_fields_changed,
            restore_governed_fields,
            revision_session_key,
        )

        original = getattr(self, 'original_contract', None) or self.object
        revision_unlocked = self._revision_unlocked()
        changed_governed = governed_fields_changed(form.cleaned_data, original)

        if getattr(form, 'governed_fields_readonly', False):
            restore_governed_fields(form.instance, original)
            changed_governed = []

        if changed_governed and not revision_unlocked and contract_is_governance_locked(original):
            # Defence in depth if a forged POST bypasses disabled widgets.
            restore_governed_fields(form.instance, original)
            form.add_error(
                None,
                'Governed terms cannot overwrite the approved record. Create a new version or amendment first.',
            )
            return self.form_invalid(form)

        risk_assessment = None
        if changed_governed:
            risk_assessment = assess_edit_risk(form.cleaned_data)
            if risk_assessment.level:
                form.instance.risk_level = risk_assessment.level

        # Preserve operational status/stage — never accept free-form POSTs for them.
        form.instance.status = original.status
        form.instance.lifecycle_stage = original.lifecycle_stage

        response = super().form_valid(form)
        changes = build_contract_audit_changes(original, self.object)
        event = 'contract_updated'
        if changes.get('lifecycle_stage'):
            event = 'contract_lifecycle_stage_changed'
        audit_changes = {
            'event': event,
            'changed_fields': sorted(changes.keys()),
            'field_changes': changes,
        }
        if changed_governed:
            audit_changes['governed_fields_changed'] = changed_governed
            audit_changes['risk_assessment'] = risk_assessment.as_dict() if risk_assessment else None
            audit_changes['revision_unlocked'] = revision_unlocked
        log_action(
            self.request.user,
            'UPDATE',
            'Contract',
            self.object.id,
            str(self.object),
            changes=audit_changes,
            request=self.request,
        )

        if changed_governed:
            messages.warning(self.request, GOVERNED_CHANGE_WARNING)
            self.request.session.pop(revision_session_key(self.object.pk), None)
        else:
            messages.success(self.request, f'Contract "{self.object.title}" updated.')

        if self.object.dpa_attached:
            from contracts.services.dpa_activation import ensure_dpa_review_pack
            ensure_dpa_review_pack(self.object, self.request.user, request=self.request)
        return response


@login_required
@require_POST
def contract_submit_for_review(request, pk):
    organization = get_user_organization(request.user)
    contract = get_object_or_404(
        scope_queryset_for_organization(Contract.objects.select_related('owner', 'created_by'), organization),
        pk=pk,
    )
    reviewer = get_object_or_404(
        User.objects.filter(
            organization_memberships__organization=organization,
            organization_memberships__is_active=True,
        ).distinct(),
        pk=request.POST.get('reviewer_id'),
    )
    from contracts.services.approval_workflow import ApprovalAccessDenied, get_approval_workflow_service
    try:
        get_approval_workflow_service().submit_for_review(
            contract,
            request.user,
            reviewer,
            comment=(request.POST.get('comment') or '').strip(),
            request=request,
        )
    except (ApprovalAccessDenied, ValueError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f'Contract submitted to {reviewer.get_full_name() or reviewer.username}.')
    from contracts.services.contract_detail_workspace import contract_detail_tab_url
    return redirect(contract_detail_tab_url(contract.pk, 'approvals'))


@login_required
@require_POST
def contract_approval_decision(request, pk, approval_id, decision):
    organization = get_user_organization(request.user)
    contract = get_object_or_404(
        scope_queryset_for_organization(Contract.objects.all(), organization), pk=pk,
    )
    approval = get_object_or_404(
        ApprovalRequest.objects.filter(organization=organization, contract=contract), pk=approval_id,
    )
    from contracts.services.approval_workflow import ApprovalAccessDenied, get_approval_workflow_service
    actions = {
        'approve': get_approval_workflow_service().approve,
        'reject': get_approval_workflow_service().reject,
        'request-changes': get_approval_workflow_service().request_changes,
    }
    action = actions.get(decision)
    if action is None:
        return HttpResponseForbidden('Invalid approval decision.')
    try:
        action(approval.pk, request.user, comments=(request.POST.get('comment') or '').strip())
    except (ApprovalAccessDenied, ValueError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f'Approval decision recorded: {decision.replace("-", " ")}.')
    return redirect('contracts:contract_detail', pk=contract.pk)


@login_required
@require_POST
def contract_approval_chain_reorder(request, pk, approval_id):
    organization = get_user_organization(request.user)
    contract = get_object_or_404(
        scope_queryset_for_organization(Contract.objects.all(), organization), pk=pk,
    )
    if not can_access_contract_action(request.user, contract, ContractAction.EDIT):
        return HttpResponseForbidden('You do not have permission to edit this contract.')

    approval = get_object_or_404(
        ApprovalRequest.objects.filter(organization=organization, contract=contract), pk=approval_id,
    )
    direction = (request.POST.get('direction') or '').strip().lower()
    if direction not in {'up', 'down'}:
        return HttpResponseForbidden('Invalid approval chain move.')

    approvals = list(
        ApprovalRequest.objects.filter(organization=organization, contract=contract)
        .order_by('sort_order', 'created_at', 'pk')
    )
    current_index = next((index for index, item in enumerate(approvals) if item.pk == approval.pk), None)
    if current_index is None:
        messages.error(request, 'That approver is no longer on this contract.')
        return redirect('contracts:contract_detail', pk=contract.pk)

    next_index = current_index - 1 if direction == 'up' else current_index + 1
    if next_index < 0 or next_index >= len(approvals):
        messages.info(request, 'That approver is already at the edge of the chain.')
        return redirect('contracts:contract_detail', pk=contract.pk)

    approvals[current_index], approvals[next_index] = approvals[next_index], approvals[current_index]
    with transaction.atomic():
        for position, item in enumerate(approvals, start=1):
            new_sort_order = position * 10
            if item.sort_order != new_sort_order:
                item.sort_order = new_sort_order
                item.save(update_fields=['sort_order'])

    log_action(
        request.user,
        AuditLog.Action.UPDATE,
        'ApprovalRequest',
        approval.pk,
        str(approval),
        changes={
            'event': 'contract.approval_chain_reordered',
            'contract_id': contract.pk,
            'direction': direction,
            'new_sort_order': approval.sort_order,
        },
        request=request,
    )
    messages.success(request, 'Approval chain updated.')
    return redirect('contracts:contract_detail', pk=contract.pk)


class RepositoryView(TenantScopedQuerysetMixin, LoginRequiredMixin, ListView):
    model = Contract
    template_name = 'contracts/repository.html'
    context_object_name = 'contracts'

    def get_queryset(self):
        org = get_user_organization(self.request.user)
        return scope_queryset_for_organization(Contract.objects.select_related('created_by', 'owner'), org).order_by('-updated_at', '-created_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        org = get_user_organization(self.request.user)
        tenant_contracts = scope_queryset_for_organization(Contract.objects.all(), org)
        expiry_cutoff = timezone.localdate() + timedelta(days=30)
        contract_stats = tenant_contracts.aggregate(
            total=Count('id'),
            awaiting_action=Count(
                'id',
                filter=Q(
                    status=Contract.Status.IN_PROGRESS,
                    lifecycle_stage__in=[
                        Contract.LifecycleStage.INTERNAL_REVIEW,
                        Contract.LifecycleStage.NEGOTIATION,
                        Contract.LifecycleStage.APPROVAL,
                    ],
                ),
            ),
            active=Count('id', filter=Q(status=Contract.Status.ACTIVE)),
            draft=Count(
                'id',
                filter=Q(
                    status=Contract.Status.IN_PROGRESS,
                    lifecycle_stage__in=[
                        Contract.LifecycleStage.INTAKE,
                        Contract.LifecycleStage.DRAFTING,
                    ],
                ),
            ),
            expiring=Count(
                'id',
                filter=Q(
                    status=Contract.Status.ACTIVE,
                    end_date__gte=timezone.localdate(),
                    end_date__lte=expiry_cutoff,
                ),
            ),
        )
        ctx['total_contracts'] = contract_stats['total']
        ctx['awaiting_action_contracts'] = contract_stats['awaiting_action']
        ctx['active_contracts'] = contract_stats['active']
        ctx['draft_contracts'] = contract_stats['draft']
        ctx['expiring_contracts'] = contract_stats['expiring']
        # Compatibility context keys retained for downstream integrations/tests;
        # templates use the contract-oriented names above.
        ctx['total_documents'] = ctx['total_contracts']
        ctx['active_documents'] = ctx['active_contracts']
        ctx['draft_documents'] = ctx['draft_contracts']
        ctx['expiring_documents'] = ctx['expiring_contracts']
        ctx['contract_types'] = Contract.ContractType.choices
        ctx['risk_levels'] = Contract.RiskLevel.choices
        ctx['approval_states'] = ApprovalRequest.Status.choices
        ctx['repository_owners'] = (
            User.objects.filter(
                organization_memberships__organization=org,
                organization_memberships__is_active=True,
            )
            .distinct()
            .order_by('first_name', 'last_name', 'username')
        )
        ctx['repository_counterparties'] = list(
            tenant_contracts.exclude(counterparty='')
            .order_by('counterparty')
            .values_list('counterparty', flat=True)
            .distinct()
        )
        ctx['hub_tabs'] = contract_operations_hub_tabs(active='repository')
        return ctx


@login_required
@require_POST
def contract_ai_assistant(request, pk):
    organization = get_user_organization(request.user)
    contract = get_object_or_404(scope_queryset_for_organization(Contract.objects.all(), organization), id=pk)
    if not can_access_contract_action(request.user, contract, ContractAction.COMMENT):
        return HttpResponseForbidden('You do not have access to this contract organization.')

    prompt = ''
    execute_actions = False
    approval_confirmed = False
    content_type = (request.content_type or '').lower()
    if 'application/json' in content_type:
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
            prompt = (payload.get('prompt') or '').strip()
            execute_actions = bool(payload.get('execute_actions'))
            approval_confirmed = bool(payload.get('approval_confirmed'))
        except (ValueError, UnicodeDecodeError):
            prompt = ''
    else:
        prompt = (request.POST.get('prompt') or '').strip()
        execute_actions = str(request.POST.get('execute_actions', '')).strip().lower() in {'1', 'true', 'yes', 'on'}
        approval_confirmed = str(request.POST.get('approval_confirmed', '')).strip().lower() in {'1', 'true', 'yes', 'on'}

    if not prompt:
        prompt = 'Give me a risk and renewal summary for this contract.'

    prompt_policy = evaluate_prompt(prompt)
    if not prompt_policy.get('allowed'):
        log_action(
            request.user,
            AuditLog.Action.EXPORT,
            'ContractAI',
            object_id=contract.id,
            object_repr=contract.title,
            changes={
                'organization_id': contract.organization_id,
                'event': 'contract_ai_assistant_blocked',
                'prompt_length': len(prompt),
                'policy_reason': prompt_policy.get('reason'),
            },
            request=request,
        )
        return JsonResponse(
            {
                'ok': False,
                'error': 'Prompt rejected by AI policy.',
                'policy': {
                    'allowed': False,
                    'reason': prompt_policy.get('reason'),
                },
            },
            status=400,
        )

    normalized_prompt = prompt_policy.get('normalized_prompt') or prompt
    ai_response = _build_contract_ai_response(contract, normalized_prompt)
    action_plan = build_action_plan(contract, normalized_prompt)
    action_plan_payload = [
        {
            'action_type': action.action_type,
            'description': action.description,
            'payload': action.payload,
            'requires_approval': action.requires_approval,
        }
        for action in action_plan
    ]
    action_execution = None

    if execute_actions and action_plan_payload:
        if not can_manage_organization(request.user, organization):
            return HttpResponseForbidden('Only organization owners/admins can execute AI actions.')
        if not approval_confirmed:
            return JsonResponse(
                {
                    'ok': False,
                    'error': 'AI action execution requires explicit approval confirmation.',
                    'action_execution': {
                        'status': 'approval_required',
                        'required': True,
                        'action_plan': action_plan_payload,
                    },
                },
                status=409,
            )
        action_execution = execute_action_plan(
            organization=organization,
            contract=contract,
            actor=request.user,
            plan=action_plan,
        )

    log_action(
        request.user,
        AuditLog.Action.EXPORT,
        'ContractAI',
        object_id=contract.id,
        object_repr=contract.title,
        changes={
            'organization_id': contract.organization_id,
            'event': 'contract_ai_assistant_invoked',
            'prompt_length': len(prompt),
            'mode': ai_response.get('mode'),
            'policy_reason': prompt_policy.get('reason'),
            'execute_actions': execute_actions,
            'action_plan_count': len(action_plan_payload),
            'action_trace_id': action_execution.get('trace_id') if action_execution else '',
            'rollback_plan': action_execution.get('rollback_plan') if action_execution else [],
        },
        request=request,
    )
    record_contract_grounded_check(contract, request.user, request=request, trigger='manual')
    return JsonResponse(
        {
            'ok': True,
            'response': ai_response,
            'action_plan': action_plan_payload,
            'action_execution': action_execution,
        }
    )


@login_required
def dashboard(request):
    if not request.user.is_authenticated:
        return redirect(f"{settings.LOGIN_URL}?next={request.get_full_path()}")

    today = date.today()
    seven_days = today + timedelta(days=7)
    thirty_days = today + timedelta(days=30)
    org = get_user_organization(request.user)

    case_qs = scope_queryset_for_organization(Case.objects.all(), org)
    clients_qs = scope_queryset_for_organization(Client.objects.all(), org)
    case_matter_qs = scope_queryset_for_organization(CaseMatter.objects.all(), org)
    workflows_qs = scope_queryset_for_organization(Workflow.objects.all(), org)
    invoices_qs = scope_queryset_for_organization(Invoice.objects.all(), org)
    documents_qs = scope_queryset_for_organization(Document.objects.all(), org)
    approvals_qs = scope_queryset_for_organization(ApprovalRequest.objects.all(), org)
    signatures_qs = scope_queryset_for_organization(SignatureRequest.objects.all(), org)
    dsars_qs = scope_queryset_for_organization(DSARRequest.objects.all(), org)
    time_entries_qs = scope_queryset_for_organization(TimeEntry.objects.all(), org)
    trust_accounts_qs = scope_queryset_for_organization(TrustAccount.objects.all(), org)
    legal_tasks_qs = CaseSignal.objects.for_organization(org) if org else CaseSignal.objects.none()
    risks_qs = RiskLog.objects.for_organization(org) if org else RiskLog.objects.none()
    deadlines_qs = Deadline.objects.for_organization(org)

    case_stats = case_qs.aggregate(
        total=Count('id'),
        active=Count('id', filter=Q(status=Contract.Status.ACTIVE)),
        draft=Count(
            'id',
            filter=Q(
                status=Contract.Status.IN_PROGRESS,
                lifecycle_stage__in=[
                    Contract.LifecycleStage.INTAKE,
                    Contract.LifecycleStage.DRAFTING,
                ],
            ),
        ),
        pending=Count(
            'id',
            filter=Q(
                status=Contract.Status.IN_PROGRESS,
                lifecycle_stage__in=[
                    Contract.LifecycleStage.INTERNAL_REVIEW,
                    Contract.LifecycleStage.NEGOTIATION,
                    Contract.LifecycleStage.APPROVAL,
                ],
            ),
        ),
        expiring_soon=Count('id', filter=Q(status=Contract.Status.ACTIVE, end_date__lte=thirty_days, end_date__gte=today)),
        high_risk_active=Count('id', filter=Q(status=Contract.Status.ACTIVE, risk_level__in=['HIGH', 'CRITICAL'])),
        missing_dpa=Count('id', filter=Q(status=Contract.Status.ACTIVE, dpa_attached=False)),
        missing_governing_law=Count('id', filter=Q(status=Contract.Status.ACTIVE, governing_law='')),
    )
    client_stats = clients_qs.aggregate(total=Count('id'))
    case_matter_stats = case_matter_qs.aggregate(total=Count('id'), active=Count('id', filter=Q(status='ACTIVE')))
    task_signal_stats = legal_tasks_qs.aggregate(pending=Count('id', filter=Q(status='PENDING')))
    workflow_stats = workflows_qs.aggregate(active=Count('id', filter=Q(status='ACTIVE')))
    risk_stats = risks_qs.aggregate(high_critical=Count('id', filter=Q(risk_level__in=['HIGH', 'CRITICAL'])))
    deadline_stats = deadlines_qs.aggregate(
        overdue=Count('id', filter=Q(is_completed=False, due_date__lt=today)),
        upcoming=Count('id', filter=Q(is_completed=False, due_date__gte=today, due_date__lte=seven_days)),
    )
    invoice_stats = invoices_qs.aggregate(
        outstanding=Sum('total_amount', filter=Q(status__in=['SENT', 'OVERDUE'])) or Decimal('0'),
        overdue=Sum('total_amount', filter=Q(status='OVERDUE')) or Decimal('0'),
        paid_this_month=Sum('total_amount', filter=Q(status='PAID', updated_at__month=today.month, updated_at__year=today.year)) or Decimal('0'),
    )
    approval_stats = approvals_qs.aggregate(pending=Count('id', filter=Q(status='PENDING')))
    signature_stats = signatures_qs.aggregate(pending=Count('id', filter=Q(status='PENDING')))
    dsar_stats = dsars_qs.aggregate(open=Count('id', filter=Q(status__in=['RECEIVED', 'IN_PROGRESS'])))
    unread_notifications = Notification.objects.filter(recipient=request.user, is_read=False).count() if request.user.is_authenticated else 0

    recent_cases = list(case_qs.select_related('client', 'created_by').order_by('-created_at')[:6])
    upcoming_deadlines = list(deadlines_qs.select_related('contract', 'matter', 'assigned_to').filter(is_completed=False, due_date__gte=today).order_by('due_date')[:6])
    upcoming_tasks = list(legal_tasks_qs.select_related('contract', 'matter', 'assigned_to').filter(status='PENDING', due_date__gte=today).order_by('due_date')[:5])
    recent_audit = list(AuditLog.objects.select_related('user').filter(organization_id=org.id).order_by('-timestamp')[:8]) if org else []
    top_risks = list(
        risks_qs.select_related('contract', 'matter')
        .filter(risk_level__in=['HIGH', 'CRITICAL'], status__in=['OPEN', 'IN_PROGRESS'])
        .order_by('-risk_level', '-created_at')[:5]
    )

    case_status_data = []
    status_mapping = [
        (Contract.Status.ACTIVE, 'Active'),
        (Contract.Status.IN_PROGRESS, 'In progress'),
        (Contract.Status.EXPIRED, 'Expired'),
        (Contract.Status.TERMINATED, 'Terminated'),
        (Contract.Status.CANCELLED, 'Cancelled'),
        (Contract.Status.ARCHIVED, 'Archived'),
    ]
    status_counts = case_qs.values('status').annotate(count=Count('id'))
    status_counts_dict = {item['status']: item['count'] for item in status_counts}
    for status_code, status_label in status_mapping:
        cnt = status_counts_dict.get(status_code, 0)
        if cnt > 0:
            case_status_data.append({'label': status_label, 'count': cnt})

    billable_hours = time_entries_qs.filter(date__month=today.month, date__year=today.year).aggregate(total=Sum('hours'))['total'] or Decimal('0')
    trust_balance = trust_accounts_qs.aggregate(total=Sum('balance'))['total'] or Decimal('0')
    total_documents = documents_qs.count()

    expiring_contracts = list(case_qs.select_related('client').filter(
        status='ACTIVE', end_date__lte=thirty_days, end_date__gte=today
    ).order_by('end_date')[:5])

    # ── Workflow queue tabs (Dashboard/work-queue conversion) ───────────
    # Every tab renders through the same WorkQueueTable component, so each
    # row — whether it started life as a Contract or a LegalTask/Deadline/
    # ApprovalRequest/WorkflowStep/SignatureRequest — is normalized to one
    # shape: title, href, contract (for StageDots; may be None), assignee
    # (for AssigneeChip; may be None), activity (for ActivityLine; may be
    # None), due_date, status_label, status_badge_class.
    #
    # assignee/activity resolution lives in contracts.services.queue_rows,
    # shared with the Repository table so the same contract never shows a
    # different assignee or "latest activity" depending on which screen
    # you're looking at.
    def _assignee_map_for_contracts(contract_ids):
        return assignee_map_for_contracts(org, contract_ids)

    def _latest_activity_map(contract_ids):
        return latest_activity_map(org, contract_ids)

    def _role_for_user(user):
        profile = getattr(user, 'profile', None) if user else None
        return profile.get_role_display() if profile else ''

    # Contract.lifecycle_stage -> the verb for the row-level action button.
    # Deliberately a small, fixed vocabulary (not a routing engine) — every
    # action still lands on the contract detail page, where the real
    # review/approve/send workflow lives.
    _QUEUE_ACTION_LABELS = {
        'DRAFTING': 'Edit',
        'INTERNAL_REVIEW': 'Review',
        'NEGOTIATION': 'Review',
        'APPROVAL': 'Approve',
        'SIGNATURE': 'Send',
        'EXECUTED': 'View',
        'OBLIGATION_TRACKING': 'Track',
        'RENEWAL': 'Track',
    }

    def _build_contract_queue(queryset, due_field='end_date', limit=10):
        contracts = list(queryset[:limit])
        ids = [c.pk for c in contracts]
        assignee_map = _assignee_map_for_contracts(ids)
        activity_map = _latest_activity_map(ids)
        rows = []
        for contract in contracts:
            due = getattr(contract, due_field, None)
            assignee = assignee_map.get(contract.pk)
            rows.append({
                'title': contract.title,
                'href': reverse('contracts:contract_detail', kwargs={'pk': contract.pk}),
                'edit_href': reverse('contracts:contract_update', kwargs={'pk': contract.pk}),
                'meta': contract.client.name if contract.client_id else None,
                'contract': contract,
                'assignee': assignee,
                'owner_role': _role_for_user(assignee),
                'activity': activity_map.get(contract.pk),
                'due_date': due,
                'due_overdue': bool(due and due < today and contract.status not in TERMINAL_STATUSES),
                'due_today': bool(due and due == today),
                'status_label': contract.get_status_display(),
                'status_badge_class': legacy_badge_class_for_tone(
                    contract_status_badge_tone(contract.status)
                ),
                'action_label': _QUEUE_ACTION_LABELS.get(contract.lifecycle_stage, 'View'),
                'next_action': _QUEUE_ACTION_LABELS.get(contract.lifecycle_stage, 'Open'),
                'current_stage': COMPACT_LIFECYCLE_LABELS.get(
                    contract.lifecycle_stage,
                    contract.get_lifecycle_stage_display(),
                ),
                # Fallback-path filter flags: the persisted CommandCenterWorkItem
                # path (command_center_work_item_to_row) sets these from richer
                # workflow/flags data; this queryset-built path only has Contract
                # fields to work with, so these are best-effort equivalents, not
                # exact parity — kept so no saved-view tab silently hides every
                # row when there are no persisted work items yet (previously
                # these keys were absent entirely, and every tab but "All"
                # rendered empty).
                'filter_all': True,
                'filter_blocked': (
                    contract.status == Contract.Status.IN_PROGRESS
                    and contract.lifecycle_stage in (
                        Contract.LifecycleStage.INTERNAL_REVIEW,
                        Contract.LifecycleStage.NEGOTIATION,
                        Contract.LifecycleStage.APPROVAL,
                    )
                ),
                'filter_dpa': contract.contract_type == 'DPA',
                'filter_high_risk': contract.risk_level in ('HIGH', 'CRITICAL'),
                'filter_renewals': bool(due),
                'filter_waiting': (
                    contract.status == Contract.Status.IN_PROGRESS
                    and contract.lifecycle_stage in (
                        Contract.LifecycleStage.INTERNAL_REVIEW,
                        Contract.LifecycleStage.NEGOTIATION,
                        Contract.LifecycleStage.APPROVAL,
                    )
                ),
            })
        return rows

    queue_in_progress = _build_contract_queue(
        case_qs.select_related('client').filter(
            Q(status=Contract.Status.IN_PROGRESS) | Q(status=Contract.Status.ACTIVE)
        ).order_by('-updated_at')
    )
    queue_needs_review = _build_contract_queue(
        case_qs.select_related('client').filter(
            status=Contract.Status.IN_PROGRESS,
            lifecycle_stage__in=[
                Contract.LifecycleStage.INTERNAL_REVIEW,
                Contract.LifecycleStage.NEGOTIATION,
                Contract.LifecycleStage.APPROVAL,
            ],
        ).order_by('-created_at')
    )
    queue_renewals = _build_contract_queue(
        case_qs.select_related('client').filter(
            status=Contract.Status.ACTIVE,
            end_date__lte=thirty_days,
            end_date__gte=today,
        ).order_by('end_date'),
        due_field='end_date',
    )
    for row in queue_renewals:
        row['due_overdue'] = False  # a renewal window is upcoming attention, not a missed deadline
    queue_completed = _build_contract_queue(
        case_qs.select_related('client').filter(
            status=Contract.Status.ACTIVE,
            lifecycle_stage__in=[
                Contract.LifecycleStage.EXECUTED,
                Contract.LifecycleStage.OBLIGATION_TRACKING,
            ],
        ).order_by('-updated_at')
    )

    queue_tabs = [
        {'key': 'in_progress', 'label': 'In Progress', 'rows': queue_in_progress, 'empty_message': 'No contracts currently in progress.'},
        {'key': 'needs_review', 'label': 'Needs Review', 'rows': queue_needs_review, 'empty_message': 'Nothing awaiting review.'},
        {'key': 'renewals', 'label': 'Renewals', 'rows': queue_renewals, 'empty_message': 'No renewals due in the next 30 days.'},
        {'key': 'completed', 'label': 'Completed', 'rows': queue_completed, 'empty_message': 'No completed contracts yet.'},
    ]
    dashboard_has_data = bool(total_documents) or any(tab['rows'] for tab in queue_tabs) or (case_stats['total'] or 0) > 0

    risk_level_counts = case_qs.aggregate(
        high=Count('id', filter=Q(risk_level__in=['HIGH', 'CRITICAL'])),
        medium=Count('id', filter=Q(risk_level='MEDIUM')),
        low=Count('id', filter=Q(risk_level='LOW')),
    )

    # Lifecycle Status Overview — buckets every contract into one of 7
    # stages. EXPIRED/TERMINATED status overrides lifecycle_stage (a contract
    # can be EXECUTED but have gone EXPIRED); everything else buckets off
    # lifecycle_stage via the same simplified vocabulary as the queue table's
    # Stage chip (RENEWAL/ARCHIVED fold into Active — this overview tracks
    # the 7 headline stages, not the full 9-stage detail).
    # Bucket labels use workflow-stage language (Drafting), never record-status "Draft".
    _LIFECYCLE_BUCKET_ORDER = ['Intake', 'Drafting', 'Internal review', 'Approval', 'Signature', 'Active', 'Expired', 'Terminated']
    _LIFECYCLE_BUCKET_COLORS = {
        'Intake': '#4A5568',
        'Drafting': '#0B1330',
        'Internal review': '#0A7264',
        'Approval': '#3F569B',
        'Signature': '#6D4E8E',
        'Active': '#17A76B',
        'Expired': '#D99A2B',
        'Terminated': '#AAB2C2',
    }
    _STAGE_TO_BUCKET = {
        'INTAKE': 'Intake',
        'DRAFTING': 'Drafting',
        'INTERNAL_REVIEW': 'Internal review',
        'NEGOTIATION': 'Internal review',
        'APPROVAL': 'Approval',
        'SIGNATURE': 'Signature',
        'EXECUTED': 'Active',
        'OBLIGATION_TRACKING': 'Active',
        'RENEWAL': 'Active',
    }
    lifecycle_buckets = {label: 0 for label in _LIFECYCLE_BUCKET_ORDER}
    for row in case_qs.values('status', 'lifecycle_stage').annotate(count=Count('id')):
        if row['status'] == 'EXPIRED':
            bucket = 'Expired'
        elif row['status'] == 'TERMINATED':
            bucket = 'Terminated'
        elif row['status'] == 'ARCHIVED':
            bucket = 'Active'  # archived records fold into Active for the overview chart
        else:
            bucket = _STAGE_TO_BUCKET.get(row['lifecycle_stage'], 'Drafting')
        lifecycle_buckets[bucket] += row['count']
    lifecycle_chart = [
        {'label': label, 'count': lifecycle_buckets[label], 'color': _LIFECYCLE_BUCKET_COLORS[label]}
        for label in _LIFECYCLE_BUCKET_ORDER
        if lifecycle_buckets[label] > 0
    ]

    # ── Command Center (Phase 2 of the Product Coherence Redesign) ──────
    # The Command Center is the standard dashboard for every organization,
    # regardless of workspace_mode. Every figure below reads PERSISTED rows
    # (DPARiskItem, RiskLog, ApprovalRequest, Deadline,
    # DPAReviewPack.review_memo*) — nothing here re-runs DPA analysis or
    # cross-document conflict detection at render time; that only happens
    # when a user explicitly re-runs the review (dpa_review_run_analysis),
    # unchanged by this work.
    clm_conflict_count = 0
    clm_top_conflicts = []
    clm_needs_review_count = 0
    clm_my_approvals_count = 0
    clm_pending_approvals_count = 0
    clm_renewals_count = 0
    clm_high_severity_count = 0
    clm_approval_overdue_count = 0
    clm_deadline_overdue_count = 0
    clm_policy_exception_count = 0
    clm_recent_memos = []
    clm_recent_matters = []
    command_center_saved_views = get_command_center_saved_views(org)
    persisted_command_center_rows = get_persisted_command_center_rows(org, current_user=request.user, today=today)

    if org:
        # Aliased on import — this module already has `Case` bound to
        # contracts.models.Case; a same-named local import would shadow it
        # for the whole function (UnboundLocalError on the case_qs line
        # above, since Python scopes a name as local the moment any
        # assignment to it appears anywhere in the function body).
        from django.db.models import Case as DBCase
        from django.db.models import IntegerField, When

        severity_rank = DBCase(
            When(severity='CRITICAL', then=0),
            When(severity='HIGH', then=1),
            When(severity='MEDIUM', then=2),
            When(severity='LOW', then=3),
            default=4, output_field=IntegerField(),
        )
        conflict_qs = (
            DPARiskItem.objects
            .filter(review_pack__organization=org, is_cross_document_conflict=True)
            .exclude(status__in=['RESOLVED', 'FALSE_POSITIVE'])
        )
        clm_conflict_count = conflict_qs.count()
        clm_top_conflicts = list(
            conflict_qs.select_related('review_pack', 'review_pack__contract')
            .annotate(severity_rank=severity_rank)
            .order_by('severity_rank', '-created_at')[:5]
        )

        clm_needs_review_count = case_qs.filter(
            status=Contract.Status.IN_PROGRESS,
            lifecycle_stage__in=[
                Contract.LifecycleStage.INTERNAL_REVIEW,
                Contract.LifecycleStage.NEGOTIATION,
                Contract.LifecycleStage.APPROVAL,
            ],
        ).count()

        clm_my_approvals_count = approvals_qs.filter(status='PENDING', assigned_to=request.user).count()
        clm_pending_approvals_count = approvals_qs.filter(status='PENDING').count()
        clm_approval_overdue_count = approvals_qs.filter(
            status='PENDING', due_date__lt=timezone.now(),
        ).count()

        clm_deadlines_30d_count = deadlines_qs.filter(
            is_completed=False, due_date__gte=today, due_date__lte=thirty_days,
        ).count()
        clm_renewals_count = clm_deadlines_30d_count + (case_stats['expiring_soon'] or 0)
        clm_deadline_overdue_count = deadlines_qs.filter(is_completed=False, due_date__lt=today).count()

        clm_high_risk_log_count = risks_qs.filter(risk_level__in=['HIGH', 'CRITICAL']).exclude(status='RESOLVED').count()
        clm_high_dpa_risk_count = (
            DPARiskItem.objects
            .filter(review_pack__organization=org, severity__in=['HIGH', 'CRITICAL'])
            .exclude(status__in=['RESOLVED', 'FALSE_POSITIVE'])
            .count()
        )
        clm_high_severity_count = clm_high_risk_log_count + clm_high_dpa_risk_count
        clm_policy_exception_count = DPARiskItem.objects.filter(
            review_pack__organization=org,
            status=DPARiskItem.Status.ACCEPTED_RISK,
        ).count()

        dpa_pack_recent_memos = list(
            DPAReviewPack.objects
            .filter(organization=org, review_memo_generated_at__isnull=False)
            .select_related('contract', 'counterparty')
            .order_by('-review_memo_generated_at')[:5]
        )
        clm_recent_memos = get_recent_review_memos(org, fallback_packs=dpa_pack_recent_memos)

        clm_recent_matters = list(
            Matter.objects.filter(organization=org)
            .select_related('client')
            .order_by('-updated_at')[:5]
        )

    from django.shortcuts import render

    # Built from the exact same four counts the metric cards below render
    # (clm_conflict_count / clm_needs_review_count / clm_my_approvals_count /
    # clm_renewals_count) so the banner can never disagree with the cards —
    # it previously mixed in org-wide approval_stats/deadline_stats figures
    # that don't back any visible card, which could show "no open items"
    # while a card still read nonzero.
    attention_parts = []
    if clm_conflict_count:
        n = clm_conflict_count
        attention_parts.append(f"{n} DPA/MSA conflict{'s' if n != 1 else ''}")
    if clm_needs_review_count:
        n = clm_needs_review_count
        attention_parts.append(f"{n} contract{'s' if n != 1 else ''} needing legal review")
    if clm_pending_approvals_count:
        n = clm_pending_approvals_count
        attention_parts.append(f"{n} open approval{'s' if n != 1 else ''} across the organization")
    if clm_renewals_count:
        n = clm_renewals_count
        attention_parts.append(f"{n} renewal{'s' if n != 1 else ''}/deadline{'s' if n != 1 else ''} due soon")
    attention_total = (clm_conflict_count or 0) + (clm_needs_review_count or 0) + (clm_pending_approvals_count or 0) + (clm_renewals_count or 0)
    if len(attention_parts) <= 1:
        attention_summary = attention_parts[0] if attention_parts else ''
    elif len(attention_parts) == 2:
        attention_summary = f"{attention_parts[0]} and {attention_parts[1]}"
    else:
        attention_summary = f"{', '.join(attention_parts[:-1])}, and {attention_parts[-1]}"

    priority_queue_rows = persisted_command_center_rows or queue_in_progress
    for row in priority_queue_rows:
        row.setdefault('contract_type', getattr(row.get('contract'), 'contract_type', '') if row.get('contract') else '')
        row.setdefault('item_type', 'Contract')
        row.setdefault('work_type', 'Legal review')
        row.setdefault('current_stage', row.get('stage', 'Review'))
        row.setdefault('risk_level', getattr(row.get('contract'), 'risk_level', '') if row.get('contract') else '')
        row.setdefault('risk_label', getattr(row.get('contract'), 'get_risk_level_display', lambda: 'Review required')() if row.get('contract') else 'Review required')
        row.setdefault('risk_personality', 'Operational review')
        row.setdefault('highest_risk_signal', row.get('risk_label', 'Review required'))
        row.setdefault('blocking_issue', row.get('meta') or 'Open operational review item.')
        row.setdefault('next_action', row.get('action_label', 'Open'))
        row.setdefault('approval_route', '')
        row.setdefault('counterparty', getattr(row.get('contract'), 'counterparty', '') if row.get('contract') else '')
        row.setdefault('workspace_href', row.get('href'))
        row.setdefault('is_workflow', False)
        row.setdefault('owner_label', row.get('assignee').get_full_name() or row.get('assignee').username if row.get('assignee') else 'Unassigned')
        row.setdefault('due_label', 'No due date' if not row.get('due_date') else row['due_date'].strftime('%d %b %Y'))
        row.setdefault('due_note', 'No SLA' if not row.get('due_date') else 'Scheduled')
        row.setdefault('priority', 0)
        row.setdefault('source_type', 'CONTRACT')
        recommendation = governed_recommendation(row)
        row['attention_explanation'] = recommendation['explanation']
        row['recommendation_title'] = recommendation['title']
        row['recommendation'] = recommendation['action']
        if row.get('due_overdue'):
            row['recommendation_reason'] = 'Overdue'
        elif row.get('status_label') == 'Blocked':
            row['recommendation_reason'] = 'Blocking workflow'
        elif row.get('due_date') and (row['due_date'] - today).days <= 3:
            row['recommendation_reason'] = 'Due within 3 days'
        elif row.get('owner_label') == 'Unassigned':
            row['recommendation_reason'] = 'Owner required'
        else:
            row['recommendation_reason'] = row.get('risk_label') or 'Action required'

    priority_queue_rows = rank_command_center_rows(priority_queue_rows, today=today)
    # Open Governed Actions must represent real workflow issues only — no
    # onboarding-checklist substitution when the workspace has none. An
    # empty workspace renders the panel's real "No open governed actions"
    # empty state instead.
    clm_recommended_actions = group_recommended_actions(priority_queue_rows, today=today, limit=5)

    # Secondary-filter option lists for the Filters popover — derived from
    # what's actually present in the queue, so no filter ever shows an
    # option with zero matching rows.
    def _distinct_options(field):
        seen = {}
        for row in priority_queue_rows:
            value = (row.get(field) or '').strip()
            if value and value not in seen:
                seen[value] = value
        return sorted(seen.values())

    priority_filter_options = {
        'risk_levels': [rl for rl in ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW') if rl in {row.get('risk_level') for row in priority_queue_rows}],
        'stages': _distinct_options('current_stage'),
        'contract_types': _distinct_options('contract_type'),
        'owners': sorted({row.get('owner_label') for row in priority_queue_rows if row.get('owner_label')}),
    }
    workflow_type_summary = get_workflow_type_summary(persisted_command_center_rows)
    command_center_rail_items = get_command_center_rail_items(org, {
        'approvals': clm_my_approvals_count,
        'deadlines': clm_renewals_count,
        'dpa_conflicts': clm_conflict_count,
        'review_memos': len(clm_recent_memos),
    })
    command_center_last_updated = timezone.localtime()

    # Sparse-workspace command-center context.  These values describe real
    # operating readiness and the selected legal finding; they are deliberately
    # separate from the portfolio analytics projection used by larger reports.
    workspace_is_sparse = (case_stats['active'] or 0) < 5
    operational_needs_review = max(
        clm_needs_review_count or 0,
        clm_conflict_count or 0,
        sum(1 for row in priority_queue_rows if row.get('risk_level') in ('MEDIUM', 'HIGH', 'CRITICAL')),
    )
    renewal_dates_recorded = case_qs.filter(
        Q(end_date__isnull=False)
        | Q(renewal_date__isnull=False)
        | Q(termination_notice_date__isnull=False)
    ).exists() or deadlines_qs.filter(deadline_type=Deadline.DeadlineType.RENEWAL).exists()
    owner_assigned = any(row.get('owner_label') and row.get('owner_label') != 'Unassigned' for row in priority_queue_rows)
    governing_law_recorded = case_qs.exclude(governing_law='').filter(governing_law__isnull=False).exists()
    approval_path_configured = ApprovalRule.objects.filter(organization=org).exists() if org else False
    playbook_attached = DPAPlaybookPosition.objects.filter(Q(organization=org) | Q(organization__isnull=True)).exists() if org else False
    deadline_tracking_configured = deadlines_qs.exists() or renewal_dates_recorded
    dpa_monitoring_configured = DPAReviewPack.objects.filter(organization=org).exists() if org else False
    reviewer_setup_required = (
        OrganizationMembership.objects.filter(organization=org, is_active=True).count() < 2
        if org else True
    )
    clm_setup_required_count = sum((
        not approval_path_configured,
        not deadline_tracking_configured,
        not dpa_monitoring_configured,
        reviewer_setup_required,
    ))

    priority_feature = priority_queue_rows[0] if priority_queue_rows else None
    priority_feature_reason = ''
    priority_feature_score = 0
    priority_feature_band = 'No active risk'
    priority_feature_history_label = 'No prior snapshot'
    priority_feature_contributors = []
    priority_feature_additional_contributors = []
    priority_feature_status = 'Review required'
    if priority_feature:
        if priority_feature.get('due_overdue'):
            priority_feature_reason = 'Selected because the next action is overdue'
        elif priority_feature.get('risk_level') == 'CRITICAL':
            priority_feature_reason = 'Selected as the highest-risk open matter'
        elif priority_feature.get('status_label') == 'Blocked':
            priority_feature_reason = 'Selected because its workflow is blocked'
        elif priority_feature.get('risk_level') == 'HIGH':
            priority_feature_reason = 'Selected as a high-risk open matter'
        elif priority_feature.get('due_date') and (priority_feature['due_date'] - today).days <= 3:
            priority_feature_reason = 'Selected because action is due within 3 days'
        else:
            priority_feature_reason = 'Selected as the highest-priority open work item'

        feature_contract = priority_feature.get('contract')
        feature_deviation_count = 0
        feature_approval_count = 0
        feature_conflict_count = 0
        if feature_contract:
            feature_deviation_count = (
                risks_qs.filter(
                    contract=feature_contract,
                    risk_level__in=['HIGH', 'CRITICAL'],
                ).exclude(status='RESOLVED').count()
                + DPARiskItem.objects.filter(
                    review_pack__organization=org,
                    review_pack__contract=feature_contract,
                    severity__in=['HIGH', 'CRITICAL'],
                ).exclude(status__in=['RESOLVED', 'FALSE_POSITIVE']).count()
            )
            feature_pending_approvals = approvals_qs.filter(
                contract=feature_contract, status='PENDING',
            )
            feature_approval_count = feature_pending_approvals.count()
            feature_conflict_count = DPARiskItem.objects.filter(
                review_pack__organization=org,
                review_pack__contract=feature_contract,
                is_cross_document_conflict=True,
            ).exclude(status__in=['RESOLVED', 'FALSE_POSITIVE']).count()
            pending_approval_steps = list(
                feature_pending_approvals.values_list('approval_step', flat=True)
            )
        else:
            pending_approval_steps = []
        if (
            feature_deviation_count == 0
            and priority_feature.get('risk_level') in ('HIGH', 'CRITICAL')
            and priority_feature.get('highest_risk_signal')
            and priority_feature.get('highest_risk_signal').lower() != 'no legal risk detected'
        ):
            # The normalized workflow item is itself a persisted risk signal,
            # even if no duplicate RiskLog row was created for it.
            feature_deviation_count = 1
        score_data = explainable_risk_score(
            priority_feature.get('risk_level'),
            {
                'high_risk_deviations': feature_deviation_count,
                'pending_approvals': feature_approval_count,
                'dpa_conflicts': feature_conflict_count,
                'unresolved_blockers': int(priority_feature.get('status_label') == 'Blocked'),
                'expired_exceptions': 0,
                'missing_approval_authority': int(not approval_path_configured),
            },
            history=priority_feature.get('score_history'),
        )
        priority_feature_score = score_data['score']
        priority_feature_band = score_data['band']
        priority_feature_history_label = score_data['history_label']
        priority_feature_contributors = [
            {'value': feature_deviation_count, 'label': 'high-risk findings'},
            {'value': feature_approval_count, 'label': 'pending approvals'},
            {'value': feature_conflict_count, 'label': 'cross-document conflicts'},
        ]
        priority_feature_additional_contributors = [item for item in [
            {'value': score_data['contributors']['unresolved_blockers'], 'label': 'unresolved blockers'},
            {'value': score_data['contributors']['expired_exceptions'], 'label': 'expired exceptions'},
            {'value': score_data['contributors']['missing_approval_authority'], 'label': 'missing approval authority'},
        ] if item['value']]
        current_stage = (priority_feature.get('current_stage') or '').strip()
        if priority_feature.get('status_label') == 'Blocked':
            priority_feature_status = 'Exception'
        elif any('finance' in step.lower() for step in pending_approval_steps):
            priority_feature_status = 'Finance review required'
        elif feature_approval_count:
            priority_feature_status = 'Awaiting approval'
        elif current_stage.lower() == 'draft':
            priority_feature_status = 'Review required'
        elif current_stage:
            priority_feature_status = current_stage

    # Compact, real-data readiness indicators for the Command Center health
    # panel.  These are derived from the same organization-scoped querysets
    # and queue rows already used by the dashboard; no additional data model
    # or projection is introduced by the presentation refresh.
    queue_owner_total = len(priority_queue_rows)
    queue_owner_count = sum(
        1 for row in priority_queue_rows
        if row.get('owner_label') and row.get('owner_label') != 'Unassigned'
    )
    dated_contract_count = case_qs.filter(
        Q(end_date__isnull=False)
        | Q(renewal_date__isnull=False)
        | Q(termination_notice_date__isnull=False)
    ).distinct().count()
    contract_count = case_stats['total'] or 0

    def _percent(complete, total):
        return round((complete / total) * 100) if total else 0

    contracts_with_owner_percent = _percent(queue_owner_count, queue_owner_total)
    renewal_dates_percent = _percent(dated_contract_count, contract_count)
    playbook_coverage_percent = 100 if playbook_attached else 0
    approval_path_percent = 100 if approval_path_configured else 0
    governing_law_percent = 100 if governing_law_recorded else 0
    workspace_health_percent = round(sum((
        contracts_with_owner_percent,
        renewal_dates_percent,
        playbook_coverage_percent,
        approval_path_percent,
        governing_law_percent,
    )) / 5)
    # Portfolio health is a measurement of actual contract records. Workspace
    # configuration remains useful elsewhere on the Command Center, but must
    # never be presented as a portfolio score before a contract exists.
    portfolio_health_available = contract_count > 0
    portfolio_deadline_count = clm_renewals_count + clm_deadline_overdue_count
    if portfolio_health_available:
        portfolio_health_factors = [
            {
                'label': 'High-risk findings',
                'count': clm_high_severity_count,
                'weight': 12,
                'penalty': min(clm_high_severity_count * 12, 42),
            },
            {
                'label': 'Pending approvals',
                'count': clm_pending_approvals_count,
                'weight': 5,
                'penalty': min(clm_pending_approvals_count * 5, 20),
            },
            {
                'label': 'Upcoming or overdue deadlines',
                'count': portfolio_deadline_count,
                'weight': 4,
                'penalty': min(portfolio_deadline_count * 4, 16),
            },
            {
                'label': 'Policy exceptions',
                'count': clm_policy_exception_count,
                'weight': 6,
                'penalty': min(clm_policy_exception_count * 6, 12),
            },
            {
                'label': 'Cross-document conflicts',
                'count': clm_conflict_count,
                'weight': 9,
                'penalty': min(clm_conflict_count * 9, 18),
            },
        ]
        portfolio_health_penalty = sum(factor['penalty'] for factor in portfolio_health_factors)
        portfolio_health_score = max(0, 100 - portfolio_health_penalty)
    else:
        portfolio_health_score = None
        portfolio_health_factors = []
    if not portfolio_health_available:
        portfolio_health_band = ''
        portfolio_health_summary = (
            'Add your first contract to begin monitoring approvals, risks, '
            'deadlines, obligations and policy exceptions.'
        )
    elif portfolio_health_score >= 85:
        portfolio_health_band = 'Healthy'
        portfolio_health_summary = 'Portfolio controls are healthy. Keep monitoring the items below so routine work stays on track.'
    elif portfolio_health_score >= 65:
        portfolio_health_band = 'Needs attention'
        portfolio_health_summary = 'Most portfolio controls are in place, but the highlighted actions need follow-through to protect the current posture.'
    else:
        portfolio_health_band = 'At risk'
        portfolio_health_summary = 'Multiple portfolio signals require attention. Start with the priority contract, then clear the remaining governed actions.'
    audit_event_count = AuditLog.objects.filter(organization=org).count() if org else 0
    audit_ready_count = AuditLog.objects.filter(organization=org).exclude(entry_hash='').count() if org else 0
    audit_readiness_percent = _percent(audit_ready_count, audit_event_count)
    governed_workflow_count = sum(1 for row in priority_queue_rows if row.get('is_workflow'))
    clm_governance_signals = [
        {
            'label': 'Playbook compliance',
            'value': f'{playbook_coverage_percent}%' if governed_workflow_count else 'Not measured',
            'detail': 'No governed contracts yet' if not governed_workflow_count else 'Measured across governed workflows',
            'tone': 'good' if governed_workflow_count and playbook_coverage_percent else 'warn',
            'href': reverse('contracts:dpa_playbook_list'),
        },
        {
            'label': 'Approval authority',
            'value': 'Configured' if approval_path_configured else 'Missing',
            'detail': 'Review approval rules' if approval_path_configured else 'Configure approval authority',
            'tone': 'good' if approval_path_configured else 'warn',
            'href': reverse('contracts:approval_rule_list'),
            'emphasis': not approval_path_configured,
        },
        {
            'label': 'Audit infrastructure',
            'value': f'{audit_readiness_percent}%' if audit_event_count and governed_workflow_count else 'Ready',
            'detail': 'Hash-backed events enabled',
            'tone': 'good' if audit_event_count and audit_readiness_percent == 100 else 'warn',
            'href': reverse('contracts:audit_log_list'),
        },
        {
            'label': 'Policy exceptions',
            'value': f'{clm_policy_exception_count} open' if clm_policy_exception_count else 'None open',
            'detail': 'Open exceptions' if clm_policy_exception_count else 'No policy exceptions',
            'tone': 'warn' if clm_policy_exception_count else 'good',
            'href': reverse('contracts:dpa_review_pack_list'),
        },
    ]

    selected_conflict = clm_top_conflicts[0] if clm_top_conflicts else None
    selected_playbook_position = None
    if org:
        selected_playbook_position = (
            DPAPlaybookPosition.objects
            .filter(Q(organization=org) | Q(organization__isnull=True), topic=DPAPlaybookPosition.Topic.LIABILITY)
            .order_by('-organization_id')
            .first()
        )

    def _format_currency_eur(value):
        if not value:
            return '—'
        if value >= Decimal('1000000'):
            return f"EUR {value / Decimal('1000000'):.1f}M"
        if value >= Decimal('1000'):
            return f"EUR {value / Decimal('1000'):.0f}K"
        return f"EUR {value:.0f}"

    workflow_rows = [row for row in priority_queue_rows if row.get('is_workflow')]
    blocked_rows = [row for row in priority_queue_rows if row.get('status_label') == 'Blocked']
    contract_exposure_total = sum(
        (row['contract'].value or Decimal('0'))
        for row in workflow_rows
        if row.get('contract') and row['contract'].value
    )
    # Legal Pulse — a compact, clickable metric strip (not KPI cards). Each
    # entry either has a real value+href, or an `empty_headline`/`empty_detail`
    # pair so a zero never renders as a bare, meaningless "0". Exposure shows
    # its own empty copy (not a dash) when no contract carries a value.
    clm_action_cards = [
        {
            'title': 'Urgent actions',
            'value': attention_total,
            'supporting_text': 'Blocking, critical, or overdue work',
            'href': reverse('contracts:repository'),
            'tone': 'rose' if attention_total else 'teal',
            'empty_headline': None if attention_total else 'All caught up',
            'empty_detail': 'No governed workflows need attention right now.',
        },
        {
            'title': 'Needs Legal Review',
            'value': clm_needs_review_count,
            'supporting_text': 'Contracts awaiting legal action',
            'href': reverse('contracts:repository'),
            'tone': 'teal',
            'empty_headline': None if clm_needs_review_count else 'Nothing awaiting review',
            'empty_detail': 'No contracts are waiting on legal review.',
        },
        {
            'title': 'Blocked',
            'value': len(blocked_rows),
            'supporting_text': 'Awaiting business owner',
            'href': reverse('contracts:approval_request_list'),
            'tone': 'amber' if blocked_rows else 'teal',
            'empty_headline': None if blocked_rows else 'No blocked contracts',
            'empty_detail': 'All active workflows are moving.',
        },
        {
            'title': 'Notice / Renewal Risk',
            'value': clm_renewals_count,
            'supporting_text': 'Deadlines in the next 30 days',
            'href': reverse('contracts:obligations_workspace'),
            'tone': 'amber' if clm_renewals_count else 'teal',
            'empty_headline': None if clm_renewals_count else 'No renewals due',
            'empty_detail': 'No renewal or notice dates in the next 30 days.',
        },
    ]
    clm_action_cards.append({
        'title': 'Exposure Review',
        'value': _format_currency_eur(contract_exposure_total) if contract_exposure_total else None,
        'supporting_text': 'Commercial exposure under review',
        'href': reverse('contracts:repository'),
        'tone': 'neutral',
        'empty_headline': None if contract_exposure_total else 'No exposure data',
        'empty_detail': 'Add contract values to track commercial exposure.',
    })

    lifecycle_counts = {
        'Drafting': 0,
        'Internal review': 0,
        'Privacy review': 0,
        'Approval': 0,
        'Signature': 0,
        'Renewal': 0,
        'Active': case_stats['active'] or 0,
    }
    for row in workflow_rows:
        stage_text = (row.get('current_stage') or row.get('stage') or '').lower()
        if 'privacy' in stage_text or 'dpo' in stage_text or row.get('contract_type') == 'DPA':
            lifecycle_counts['Privacy review'] += 1
        elif 'approval' in stage_text:
            lifecycle_counts['Approval'] += 1
        elif 'signature' in stage_text:
            lifecycle_counts['Signature'] += 1
        elif 'renewal' in stage_text:
            lifecycle_counts['Renewal'] += 1
        elif 'draft' in stage_text or 'intake' in stage_text or 'ai draft' in stage_text:
            lifecycle_counts['Drafting'] += 1
        elif stage_text:
            lifecycle_counts['Internal review'] += 1
    clm_lifecycle_overview = [
        {
            'label': label,
            'count': lifecycle_counts[label],
            'tone': (
                'navy' if label == 'Drafting'
                else 'teal' if label in ('Internal review', 'Privacy review', 'Active')
                else 'amber' if label in ('Approval', 'Renewal')
                else 'gray'
            ),
        }
        for label in ('Drafting', 'Internal review', 'Privacy review', 'Approval', 'Signature', 'Renewal', 'Active')
    ]

    blocker_map = {}
    blocker_order = [
        ('Business owner response overdue', 'Business owner response overdue', 'Attention'),
        ('DPA fallback language missing', 'DPA fallback language missing', 'Critical'),
        ('Liability position unresolved', 'Liability position unresolved', 'Attention'),
        ('Signature package incomplete', 'Signature package incomplete', 'Attention'),
    ]
    for row in priority_queue_rows:
        issue = (row.get('blocking_issue') or '').lower()
        if not issue or issue.startswith('no legal risk detected'):
            continue
        if 'owner' in issue or 'business' in issue:
            key = 'Business owner response overdue'
        elif 'scc' in issue or ('fallback' in issue and row.get('contract_type') == 'DPA'):
            key = 'DPA fallback language missing'
        elif 'liability' in issue or 'fallback clause' in issue:
            key = 'Liability position unresolved'
        elif 'signature' in issue:
            key = 'Signature package incomplete'
        else:
            key = row.get('blocking_issue')
        blocker = blocker_map.setdefault(key, {
            'label': key,
            'count': 0,
            'severity': 'Attention',
            'href': row.get('workspace_href') or row.get('href'),
        })
        blocker['count'] += 1
    clm_top_blockers = []
    for key, label, severity in blocker_order:
        blocker = blocker_map.pop(key, None)
        if blocker:
            blocker['label'] = label
            blocker['severity'] = severity
            clm_top_blockers.append(blocker)
    clm_top_blockers.extend(
        sorted(blocker_map.values(), key=lambda item: (-item['count'], item['label']))[: max(0, 4 - len(clm_top_blockers))]
    )

    overdue_count = sum(1 for row in priority_queue_rows if row.get('due_overdue'))
    due_soon_count = sum(
        1
        for row in priority_queue_rows
        if row.get('due_date') and not row.get('due_overdue') and (row['due_date'] - today).days <= 3
    )
    on_track_count = sum(
        1
        for row in priority_queue_rows
        if row.get('due_date') and not row.get('due_overdue') and (row['due_date'] - today).days > 3
    )
    no_sla_count = sum(1 for row in priority_queue_rows if not row.get('due_date'))
    clm_queue_health = [
        {'label': 'Overdue', 'count': overdue_count, 'tone': 'rose'},
        {'label': 'Due soon', 'count': due_soon_count, 'tone': 'amber'},
        {'label': 'On track', 'count': on_track_count, 'tone': 'teal'},
        {'label': 'No SLA', 'count': no_sla_count, 'tone': 'gray'},
    ]

    deadline_candidates = [
        {
            'title': deadline.title,
            'counterparty': getattr(deadline.contract, 'counterparty', '') or 'No counterparty',
            'due_date': deadline.due_date,
            'href': reverse('contracts:deadline_update', kwargs={'pk': deadline.pk}),
        }
        for deadline in deadlines_qs.select_related('contract').filter(is_completed=False).order_by('due_date', 'pk')[:6]
    ]
    deadline_candidates.extend(
        {
            'title': approval.contract.title,
            'counterparty': approval.contract.counterparty or 'No counterparty',
            'due_date': approval.due_date.date(),
            'href': reverse('contracts:approval_request_update', kwargs={'pk': approval.pk}),
        }
        for approval in approvals_qs.select_related('contract').filter(
            status='PENDING', due_date__isnull=False,
        ).order_by('due_date', 'pk')[:6]
    )
    deadline_candidates.extend(
        {
            'title': row.get('title'),
            'counterparty': row.get('counterparty') or 'No counterparty',
            'due_date': row.get('due_date'),
            'href': row.get('workspace_href') or row.get('href'),
        }
        for row in priority_queue_rows
        if row.get('due_date') or row.get('is_workflow')
    )
    clm_upcoming_obligations = build_upcoming_deadlines(deadline_candidates, today=today, limit=3)

    clm_missing_dpa_count = sum(
        1
        for row in priority_queue_rows
        if 'missing dpa' in (row.get('highest_risk_signal') or '').lower()
        or 'linked dpa' in (row.get('highest_risk_signal') or '').lower()
    )
    clm_missing_governing_law_count = case_qs.filter(
        Q(governing_law__isnull=True) | Q(governing_law__exact='')
    ).count()
    clm_high_attention_records = [
        {'label': 'High-risk contracts', 'count': sum(1 for row in priority_queue_rows if row.get('risk_level') in ('HIGH', 'CRITICAL'))},
        {'label': 'Contracts missing DPA', 'count': clm_missing_dpa_count},
        {'label': 'Contracts missing governing law', 'count': clm_missing_governing_law_count},
    ]

    clm_recent_review_items = []
    for memo in clm_recent_memos[:4]:
        if hasattr(memo, 'memo_type'):
            title = memo.title
            timestamp = memo.generated_at
            href = reverse('contracts:dpa_review_pack_list')
            source = f"{memo.get_memo_type_display()} · generated from DPAReviewPack findings"
        else:
            title = f"{memo.contract.title if memo.contract_id else 'Review memo'} opened"
            timestamp = memo.review_memo_generated_at
            href = reverse('contracts:dpa_review_pack_detail', kwargs={'pk': memo.pk})
            source = 'DPA Review Pack · rules-based analysis'
        clm_recent_review_items.append({
            'title': title,
            'timestamp': timestamp,
            'href': href,
            'source': source,
            'recommended_action': 'Review before signature' if 'DPA' in source else 'Open memo for details',
        })

    clm_repository_shortcuts = [
        {'label': 'Templates Library', 'href': reverse('contracts:templates_list')},
        {'label': 'Workflow Templates', 'href': reverse('contracts:workflow_template_list')},
        {'label': 'Clause Library', 'href': reverse('contracts:clause_template_list')},
        {'label': 'Counterparties', 'href': reverse('contracts:counterparty_list')},
    ]

    return render(request, 'dashboard.html', {
        'attention_total': attention_total,
        'attention_summary': attention_summary,
        'priority_queue_rows': priority_queue_rows,
        'priority_feature': priority_feature,
        'priority_feature_reason': priority_feature_reason,
        'priority_feature_score': priority_feature_score,
        'priority_feature_band': priority_feature_band,
        'priority_feature_history_label': priority_feature_history_label,
        'priority_feature_contributors': priority_feature_contributors,
        'priority_feature_additional_contributors': priority_feature_additional_contributors,
        'priority_feature_status': priority_feature_status,
        'clm_recommended_actions': clm_recommended_actions,
        'priority_filter_options': priority_filter_options,
        'workflow_type_summary': workflow_type_summary,
        'persisted_command_center_rows': persisted_command_center_rows,
        'command_center_saved_views': command_center_saved_views,
        'command_center_rail_items': command_center_rail_items,
        'risk_level_counts': risk_level_counts,
        'case_stats': case_stats,
        'client_stats': client_stats,
        'case_matter_stats': case_matter_stats,
        'task_signal_stats': task_signal_stats,
        'workflow_stats': workflow_stats,
        'risk_stats': risk_stats,
        'deadline_stats': deadline_stats,
        'invoice_stats': invoice_stats,
        'approval_stats': approval_stats,
        'signature_stats': signature_stats,
        'dsar_stats': dsar_stats,
        'unread_notifications': unread_notifications,
        'today': today,
        'recent_cases': recent_cases,
        'upcoming_deadlines': upcoming_deadlines,
        'upcoming_tasks': upcoming_tasks,
        'recent_audit': recent_audit,
        'top_risks': top_risks,
        'queue_tabs': queue_tabs,
        'dashboard_has_data': dashboard_has_data,
        'case_status_data': case_status_data,
        'billable_hours': billable_hours,
        'trust_balance': trust_balance,
        'total_documents': total_documents,
        'total_cases': case_stats['total'] or 0,
        'active_cases': case_stats['active'] or 0,
        'expiring_case_count': case_stats['expiring_soon'] or 0,
        'total_contracts': case_stats['total'] or 0,
        'active_contracts': case_stats['active'] or 0,
        'expiring_soon': case_stats['expiring_soon'] or 0,
        'expiring_contracts': expiring_contracts,
        'lifecycle_chart': lifecycle_chart,
        'lifecycle_total': case_stats['total'] or 0,
        'clm_conflict_count': clm_conflict_count,
        'clm_top_conflicts': clm_top_conflicts,
        'clm_needs_review_count': clm_needs_review_count,
        'clm_my_approvals_count': clm_my_approvals_count,
        'clm_pending_approvals_count': clm_pending_approvals_count,
        'clm_renewals_count': clm_renewals_count,
        'clm_high_severity_count': clm_high_severity_count,
        'clm_approval_overdue_count': clm_approval_overdue_count,
        'clm_deadline_overdue_count': clm_deadline_overdue_count,
        'clm_policy_exception_count': clm_policy_exception_count,
        'clm_governance_signals': clm_governance_signals,
        'clm_recent_memos': clm_recent_memos,
        'clm_recent_matters': clm_recent_matters,
        'clm_action_cards': clm_action_cards,
        'clm_lifecycle_overview': clm_lifecycle_overview,
        'clm_top_blockers': clm_top_blockers,
        'clm_queue_health': clm_queue_health,
        'clm_upcoming_obligations': clm_upcoming_obligations,
        'clm_high_attention_records': clm_high_attention_records,
        'clm_recent_review_items': clm_recent_review_items,
        'clm_repository_shortcuts': clm_repository_shortcuts,
        'command_center_last_updated': command_center_last_updated,
        'workspace_is_sparse': workspace_is_sparse,
        'operational_needs_review': operational_needs_review,
        'blocked_work_count': len(blocked_rows),
        'renewal_dates_recorded': renewal_dates_recorded,
        'owner_assigned': owner_assigned,
        'governing_law_recorded': governing_law_recorded,
        'approval_path_configured': approval_path_configured,
        'playbook_attached': playbook_attached,
        'deadline_tracking_configured': deadline_tracking_configured,
        'dpa_monitoring_configured': dpa_monitoring_configured,
        'reviewer_setup_required': reviewer_setup_required,
        'clm_setup_required_count': clm_setup_required_count,
        'workspace_health_percent': workspace_health_percent,
        'portfolio_health_available': portfolio_health_available,
        'portfolio_health_score': portfolio_health_score,
        'portfolio_health_factors': portfolio_health_factors,
        'portfolio_health_band': portfolio_health_band,
        'portfolio_health_summary': portfolio_health_summary,
        'portfolio_deadline_count': portfolio_deadline_count,
        'contracts_with_owner_percent': contracts_with_owner_percent,
        'renewal_dates_percent': renewal_dates_percent,
        'playbook_coverage_percent': playbook_coverage_percent,
        'approval_path_percent': approval_path_percent,
        'selected_conflict': selected_conflict,
        'selected_playbook_position': selected_playbook_position,
    })
