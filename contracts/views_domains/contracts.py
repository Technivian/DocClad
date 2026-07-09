from datetime import date, timedelta
from decimal import Decimal
import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q, Sum
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from contracts.forms import ContractForm, UserProfileForm
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
)
from contracts.permissions import ContractAction, can_access_contract_action, can_manage_organization
from contracts.services.queue_rows import TERMINAL_STATUSES, assignee_map_for_contracts, latest_activity_map
from contracts.services.command_center import (
    get_command_center_rail_items,
    get_command_center_saved_views,
    get_persisted_command_center_rows,
    get_recent_review_memos,
    get_workflow_type_summary,
)
from contracts.services.contract_launch_setup import get_entry_cards, get_launch_setup_map
from contracts.services.draft_cockpit import get_governance_panel
from contracts.templatetags.docclad_format import status_badge_class
from contracts.tenancy import get_user_organization, scope_queryset_for_organization, set_organization_on_instance
from contracts.view_support import TenantAssignCreateMixin, TenantScopedQuerysetMixin
from contracts.services.contract_lifecycle import build_contract_audit_changes
from contracts.services.ai_policy import evaluate_prompt
from contracts.services.ai_actions import build_action_plan, execute_action_plan
from config.feature_flags import is_feature_redesign_enabled

from .contract_helpers import _build_contract_ai_response, build_contract_lifecycle_guidance
from contracts.services.contract_templates import render_merge_fields


class ContractListView(TenantScopedQuerysetMixin, LoginRequiredMixin, ListView):
    model = Contract
    template_name = 'contracts/contract_list.html'
    context_object_name = 'contracts'
    paginate_by = 25

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
            active=Count('id', filter=Q(status='ACTIVE')),
            expiring_soon=Count('id', filter=Q(status='ACTIVE', end_date__lte=thirty_days_from_today, end_date__gte=today)),
            draft=Count('id', filter=Q(status='DRAFT')),
            legal_review=Count('id', filter=Q(status='IN_REVIEW')),
            approval=Count('id', filter=Q(status='PENDING')),
            signature=Count('id', filter=Q(status='APPROVED')),
            blocked=Count('id', filter=Q(status__in=['EXPIRED', 'TERMINATED', 'CANCELLED'])),
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
        context['status_tabs'] = [
            ('All', ''),
            ('Draft', 'DRAFT'),
            ('Legal Review', 'IN_REVIEW'),
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

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        case_record = self.object
        ctx['case'] = case_record
        ctx['case_record'] = case_record
        ctx['documents'] = case_record.documents.select_related('uploaded_by').all()[:10]
        ctx['case_documents'] = ctx['documents']
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
        ctx['owner'] = assignee_map_for_contracts(org, [case_record.pk]).get(case_record.pk)
        ctx['approval_requests'] = case_record.approval_requests.select_related(
            'assigned_to', 'delegated_to',
        ).order_by('-created_at')[:10]
        ctx['signature_requests'] = case_record.signature_requests.order_by('-created_at')[:10]
        ctx['contract_tasks'] = LegalTask.objects.filter(contract=case_record).select_related(
            'assigned_to',
        ).order_by('due_date')[:10]
        ctx['activity_entries'] = AuditLog.objects.filter(
            organization=org, model_name='Contract', object_id=case_record.pk,
        ).select_related('user').order_by('-timestamp')[:20]
        ctx['contract_risks'] = RiskLog.objects.filter(contract=case_record).select_related('assigned_to')[:10]
        return ctx


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
        context['entry_cards'] = get_entry_cards(
            start_url_for=lambda ct: (
                reverse('contracts:dpa_workflow_builder') if ct == Contract.ContractType.DPA
                else reverse('contracts:msa_workflow_builder') if ct == Contract.ContractType.MSA
                else reverse('contracts:nda_workflow_builder') if ct == Contract.ContractType.NDA
                else f"{reverse('contracts:contract_create')}?type={ct}"
            )
        )
    return render(request, 'contracts/contract_template_picker.html', context)


class ContractCreateView(TenantAssignCreateMixin, LoginRequiredMixin, CreateView):
    model = Contract
    form_class = ContractForm
    template_name = 'contracts/contract_form.html'
    success_url = reverse_lazy('contracts:contract_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organization'] = get_user_organization(self.request.user)
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
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        selected_template = self._selected_template()
        contract_type = self.request.GET.get('type') or (selected_template.contract_type if selected_template else '')
        org = get_user_organization(self.request.user)
        ctx['selected_template'] = selected_template
        ctx['launch_setup_map'] = get_launch_setup_map()
        ctx['governance_panel'] = get_governance_panel(org, contract_type, selected_template)
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
            },
        )

    def post(self, request, *args, **kwargs):
        if 'preview_draft' in request.POST:
            form = self.get_form()
            if form.is_valid():
                return self._render_preview(form)
            return self.form_invalid(form)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        set_organization_on_instance(form.instance, get_user_organization(self.request.user))
        form.instance.created_by = self.request.user
        # New contracts always start in DRAFT; reaching ACTIVE etc. must go
        # through ContractLifecycleService transitions (prevents create-as-ACTIVE
        # bypassing the approval prerequisite).
        form.instance.status = Contract.Status.DRAFT
        # Resolve any {{merge_field}} tokens against the instance's own
        # cleaned field values — harmless no-op if the content has none,
        # so this runs whether or not a template was used to start the draft.
        form.instance.content = render_merge_fields(form.instance.content, form.instance)
        response = super().form_valid(form)
        log_action(
            self.request.user,
            'CREATE',
            'Contract',
            self.object.id,
            str(self.object),
            changes={
                'event': 'contract_created',
                'status': self.object.status,
                'lifecycle_stage': self.object.lifecycle_stage,
                'contract_type': self.object.contract_type,
            },
            request=self.request,
        )
        messages.success(self.request, f'Contract "{self.object.title}" created.')
        return response


class ContractUpdateView(TenantScopedQuerysetMixin, LoginRequiredMixin, UpdateView):
    model = Contract
    form_class = ContractForm
    template_name = 'contracts/contract_form.html'
    success_url = reverse_lazy('contracts:contract_list')

    def get_queryset(self):
        org = get_user_organization(self.request.user)
        return scope_queryset_for_organization(Contract.objects.all(), org)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organization'] = get_user_organization(self.request.user)
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        org = get_user_organization(self.request.user)
        ctx['launch_setup_map'] = get_launch_setup_map()
        ctx['governance_panel'] = get_governance_panel(org, self.object.contract_type, None, contract=self.object)
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
                'contract': self.object,
                'form_action': reverse('contracts:contract_update', kwargs={'pk': self.object.pk}),
                'draft_sections': draft_sections,
                'draft_preview_selected_clause_count': len(draft_sections),
                'preview_mode': True,
            },
        )

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
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

    def form_valid(self, form):
        from contracts.services.contract_lifecycle import (
            ContractTransitionError,
            can_transition_contract_status,
            get_contract_lifecycle_service,
        )
        new_status = form.cleaned_data.get('status')
        original_status = getattr(self, 'original_contract', None) and self.original_contract.status
        status_changing = bool(original_status) and new_status != original_status

        # The status transition is owned by the lifecycle service, not the form.
        # Pre-validate the graph cheaply, then keep the form save status-neutral
        # and apply the transition through the service after the field edits land.
        if status_changing:
            if not can_transition_contract_status(original_status, new_status):
                form.add_error('status', f'Cannot change status from {original_status} to {new_status}.')
                return self.form_invalid(form)
            form.instance.status = original_status  # field edits save with the old status

        response = super().form_valid(form)
        changes = build_contract_audit_changes(getattr(self, 'original_contract', None), self.object)
        event = 'contract_updated'
        if changes.get('lifecycle_stage'):
            event = 'contract_lifecycle_stage_changed'
        log_action(
            self.request.user,
            'UPDATE',
            'Contract',
            self.object.id,
            str(self.object),
            changes={
                'event': event,
                'changed_fields': sorted(changes.keys()),
                'field_changes': changes,
            },
            request=self.request,
        )

        if status_changing:
            try:
                get_contract_lifecycle_service().transition(
                    self.object, new_status, self.request.user, request=self.request,
                )
            except ContractTransitionError as exc:
                form.add_error('status', str(exc))
                return self.form_invalid(form)
        return response


class RepositoryView(TenantScopedQuerysetMixin, LoginRequiredMixin, ListView):
    model = Contract
    template_name = 'contracts/repository.html'
    context_object_name = 'contracts'

    def get_queryset(self):
        org = get_user_organization(self.request.user)
        return scope_queryset_for_organization(Contract.objects.select_related('created_by'), org).order_by('-updated_at', '-created_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        org = get_user_organization(self.request.user)
        tenant_contracts = scope_queryset_for_organization(Contract.objects.all(), org)
        expiry_cutoff = timezone.localdate() + timedelta(days=30)
        doc_stats = tenant_contracts.aggregate(
            total=Count('id'),
            active=Count('id', filter=Q(status=Contract.Status.ACTIVE)),
            draft=Count('id', filter=Q(status=Contract.Status.DRAFT)),
            expiring=Count('id', filter=Q(end_date__isnull=False, end_date__lte=expiry_cutoff)),
        )
        ctx['total_documents'] = doc_stats['total']
        ctx['active_documents'] = doc_stats['active']
        ctx['draft_documents'] = doc_stats['draft']
        ctx['expiring_documents'] = doc_stats['expiring']
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

    def _normalize_sort_date(value):
        if value is None:
            return date.max
        if hasattr(value, 'date'):
            try:
                return value.date()
            except TypeError:
                return value
        return value

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
        active=Count('id', filter=Q(status='ACTIVE')),
        draft=Count('id', filter=Q(status='DRAFT')),
        pending=Count('id', filter=Q(status='PENDING')),
        expiring_soon=Count('id', filter=Q(status='ACTIVE', end_date__lte=thirty_days, end_date__gte=today)),
        high_risk_active=Count('id', filter=Q(status='ACTIVE', risk_level__in=['HIGH', 'CRITICAL'])),
        missing_dpa=Count('id', filter=Q(status='ACTIVE', dpa_attached=False)),
        missing_governing_law=Count('id', filter=Q(status='ACTIVE', governing_law='')),
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

    # ── "Waiting on Me" queue rows — heterogeneous items assigned to the
    # current user, normalized (via _finalize_waiting_on_me below) to the
    # same row shape as the contract-based queues so one WorkQueueTable
    # component can render every tab.
    waiting_on_me_raw = []
    if org:
        my_legal_tasks = list(
            CaseSignal.objects.for_organization(org)
            .select_related('contract', 'matter', 'assigned_to')
            .filter(assigned_to=request.user, status__in=['PENDING', 'IN_PROGRESS'])
            .order_by('due_date', 'created_at')[:4]
        )
        for task in my_legal_tasks:
            waiting_on_me_raw.append({
                'title': task.title,
                'meta': f'Legal task · {task.get_status_display()}',
                'href': reverse('contracts:legal_task_update', kwargs={'pk': task.pk}),
                'contract': task.contract,
                'assignee': request.user,
                'due_date': task.due_date,
                'status_label': 'In progress' if task.status == 'IN_PROGRESS' else 'Pending',
                'status_badge_class': 'badge-blue',
                'sort_key': (_normalize_sort_date(task.due_date), 10, task.pk),
            })

        for deadline in list(
            Deadline.objects.for_organization(org)
            .select_related('contract', 'matter', 'assigned_to')
            .filter(assigned_to=request.user, is_completed=False)
            .order_by('due_date')[:4]
        ):
            waiting_on_me_raw.append({
                'title': deadline.title,
                'meta': f"Deadline · {deadline.contract.title if deadline.contract else deadline.matter.title if deadline.matter else 'Unlinked'}",
                'href': reverse('contracts:deadline_update', kwargs={'pk': deadline.pk}),
                'contract': deadline.contract,
                'assignee': request.user,
                'due_date': deadline.due_date,
                'status_label': 'Overdue' if deadline.due_date and deadline.due_date < today else 'Upcoming',
                'status_badge_class': 'badge-red' if deadline.due_date and deadline.due_date < today else 'badge-yellow',
                'sort_key': (_normalize_sort_date(deadline.due_date), 20, deadline.pk),
            })

        for approval in list(
            approvals_qs.select_related('contract', 'assigned_to')
            .filter(assigned_to=request.user, status='PENDING')
            .order_by('due_date', 'created_at')[:4]
        ):
            waiting_on_me_raw.append({
                'title': approval.contract.title,
                'meta': f"Approval · {approval.approval_step}",
                'href': reverse('contracts:approval_request_update', kwargs={'pk': approval.pk}),
                'contract': approval.contract,
                'assignee': request.user,
                'due_date': approval.due_date.date() if approval.due_date else None,
                'status_label': approval.get_status_display(),
                'status_badge_class': 'badge-yellow',
                'sort_key': (_normalize_sort_date(approval.due_date), 30, approval.pk),
            })

        for dsar in list(
            dsars_qs.select_related('client', 'assigned_to')
            .filter(assigned_to=request.user, status__in=['RECEIVED', 'VERIFIED', 'IN_PROGRESS'])
            .order_by('due_date', 'received_date')[:4]
        ):
            client_name = dsar.client.name if dsar.client else 'Unlinked'
            waiting_on_me_raw.append({
                'title': dsar.requester_name,
                'meta': f"Data subject request · {client_name}",
                'href': reverse('contracts:dsar_update', kwargs={'pk': dsar.pk}),
                'contract': None,
                'assignee': request.user,
                'due_date': dsar.due_date,
                'status_label': dsar.get_status_display(),
                'status_badge_class': 'badge-purple',
                'sort_key': (_normalize_sort_date(dsar.due_date or dsar.received_date), 40, dsar.pk),
            })

        for step in list(
            WorkflowStep.objects.select_related('workflow', 'assigned_to')
            .filter(workflow__organization=org, assigned_to=request.user, status='PENDING')
            .order_by('order', 'pk')[:4]
        ):
            waiting_on_me_raw.append({
                'title': step.name,
                'meta': f"Workflow · {step.workflow.title}",
                'href': reverse('contracts:workflow_step_update', kwargs={'pk': step.pk}),
                'contract': step.workflow.contract,
                'assignee': request.user,
                'due_date': step.due_date.date() if step.due_date else None,
                'status_label': 'Waiting on you',
                'status_badge_class': 'badge-yellow',
                'sort_key': (_normalize_sort_date(step.due_date), 50, step.order, step.pk),
            })

        for signature in list(
            signatures_qs.select_related('contract')
                .filter(signer_email__iexact=request.user.email, status__in=['PENDING', 'SENT', 'VIEWED'])
                .order_by('order', 'created_at')[:4]
        ):
            waiting_on_me_raw.append({
                'title': signature.contract.title,
                'meta': f"Signature · {signature.signer_name} · {signature.get_status_display()}",
                'href': reverse('contracts:signature_request_detail', kwargs={'pk': signature.pk}),
                'contract': signature.contract,
                'assignee': request.user,
                'due_date': None,
                'status_label': signature.get_status_display(),
                'status_badge_class': 'badge-blue',
                'sort_key': (_normalize_sort_date(signature.created_at), 60, signature.order, signature.pk),
            })

    waiting_on_me_raw = sorted(waiting_on_me_raw, key=lambda item: item['sort_key'])[:10]

    case_status_data = []
    status_mapping = [('ACTIVE', 'Active'), ('DRAFT', 'Draft'), ('PENDING', 'In Review'), ('EXPIRED', 'Expired'), ('TERMINATED', 'Terminated')]
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
        'ARCHIVED': 'View',
    }

    def _build_contract_queue(queryset, due_field='end_date', limit=10):
        contracts = list(queryset[:limit])
        ids = [c.pk for c in contracts]
        assignee_map = _assignee_map_for_contracts(ids)
        activity_map = _latest_activity_map(ids)
        rows = []
        for contract in contracts:
            due = getattr(contract, due_field, None)
            rows.append({
                'title': contract.title,
                'href': reverse('contracts:contract_detail', kwargs={'pk': contract.pk}),
                'edit_href': reverse('contracts:contract_update', kwargs={'pk': contract.pk}),
                'meta': contract.client.name if contract.client_id else None,
                'contract': contract,
                'assignee': assignee_map.get(contract.pk),
                'owner_role': _role_for_user(assignee_map.get(contract.pk)),
                'activity': activity_map.get(contract.pk),
                'due_date': due,
                'due_overdue': bool(due and due < today and contract.status not in TERMINAL_STATUSES),
                'due_today': bool(due and due == today),
                'status_label': contract.get_status_display(),
                'status_badge_class': status_badge_class(contract.status),
                'action_label': _QUEUE_ACTION_LABELS.get(contract.lifecycle_stage, 'View'),
            })
        return rows

    def _finalize_waiting_on_me(raw_rows):
        contract_ids = [r['contract'].pk for r in raw_rows if r['contract']]
        activity_map = _latest_activity_map(contract_ids)
        rows = []
        for r in raw_rows:
            rows.append({
                'title': r['title'],
                'href': r['href'],
                'edit_href': r['href'],
                'meta': r['meta'],
                'contract': r['contract'],
                'assignee': r['assignee'],
                'owner_role': _role_for_user(r['assignee']),
                'activity': activity_map.get(r['contract'].pk) if r['contract'] else None,
                'due_date': r['due_date'],
                'due_overdue': bool(r['due_date'] and r['due_date'] < today),
                'due_today': bool(r['due_date'] and r['due_date'] == today),
                'status_label': r['status_label'],
                'status_badge_class': r['status_badge_class'],
                'action_label': _QUEUE_ACTION_LABELS.get(r['contract'].lifecycle_stage, 'View') if r['contract'] else 'Open',
            })
        return rows

    queue_in_progress = _build_contract_queue(
        case_qs.select_related('client').filter(status__in=['PENDING', 'IN_REVIEW', 'APPROVED', 'ACTIVE']).order_by('-updated_at')
    )
    queue_needs_review = _build_contract_queue(
        case_qs.select_related('client').filter(status__in=['PENDING', 'IN_REVIEW']).order_by('-created_at')
    )
    queue_renewals = _build_contract_queue(
        case_qs.select_related('client').filter(status='ACTIVE', end_date__lte=thirty_days, end_date__gte=today).order_by('end_date'),
        due_field='end_date',
    )
    for row in queue_renewals:
        row['due_overdue'] = False  # a renewal window is upcoming attention, not a missed deadline
    queue_completed = _build_contract_queue(
        case_qs.select_related('client').filter(status='COMPLETED').order_by('-updated_at')
    )
    queue_waiting_on_me = _finalize_waiting_on_me(waiting_on_me_raw)

    queue_tabs = [
        {'key': 'in_progress', 'label': 'In Progress', 'rows': queue_in_progress, 'empty_message': 'No contracts currently in progress.'},
        {'key': 'waiting_on_me', 'label': 'Waiting on Me', 'rows': queue_waiting_on_me, 'empty_message': 'Nothing is waiting on you right now.'},
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
    _LIFECYCLE_BUCKET_ORDER = ['Draft', 'Legal Review', 'Approval', 'Signature', 'Active', 'Expired', 'Terminated']
    _LIFECYCLE_BUCKET_COLORS = {
        'Draft': '#0B1330',
        'Legal Review': '#0A7264',
        'Approval': '#3F569B',
        'Signature': '#6D4E8E',
        'Active': '#17A76B',
        'Expired': '#C96A3E',
        'Terminated': '#AAB2C2',
    }
    _STAGE_TO_BUCKET = {
        'DRAFTING': 'Draft',
        'INTERNAL_REVIEW': 'Legal Review',
        'NEGOTIATION': 'Legal Review',
        'APPROVAL': 'Approval',
        'SIGNATURE': 'Signature',
        'EXECUTED': 'Active',
        'OBLIGATION_TRACKING': 'Active',
        'RENEWAL': 'Active',
        'ARCHIVED': 'Active',
    }
    lifecycle_buckets = {label: 0 for label in _LIFECYCLE_BUCKET_ORDER}
    for row in case_qs.values('status', 'lifecycle_stage').annotate(count=Count('id')):
        if row['status'] == 'EXPIRED':
            bucket = 'Expired'
        elif row['status'] == 'TERMINATED':
            bucket = 'Terminated'
        else:
            bucket = _STAGE_TO_BUCKET.get(row['lifecycle_stage'], 'Draft')
        lifecycle_buckets[bucket] += row['count']
    lifecycle_chart = [
        {'label': label, 'count': lifecycle_buckets[label], 'color': _LIFECYCLE_BUCKET_COLORS[label]}
        for label in _LIFECYCLE_BUCKET_ORDER
        if lifecycle_buckets[label] > 0
    ]

    # ── Command Center (Phase 2 of the Product Coherence Redesign) ──────
    # in_house_clm-only data. Deliberately gated so law_firm_ops tenants pay
    # zero extra queries and see the dashboard exactly as before. Every
    # figure below reads PERSISTED rows (DPARiskItem, RiskLog, ApprovalRequest,
    # Deadline, DPAReviewPack.review_memo*) — nothing here re-runs DPA
    # analysis or cross-document conflict detection at render time; that
    # only happens when a user explicitly re-runs the review
    # (dpa_review_run_analysis), unchanged by this work.
    workspace_mode = getattr(org, 'workspace_mode', 'law_firm_ops') if org else 'law_firm_ops'
    is_in_house_clm = workspace_mode == 'in_house_clm'

    clm_conflict_count = 0
    clm_top_conflicts = []
    clm_needs_review_count = 0
    clm_my_approvals_count = 0
    clm_renewals_count = 0
    clm_high_severity_count = 0
    clm_recent_memos = []
    clm_recent_matters = []
    command_center_saved_views = get_command_center_saved_views(org)
    persisted_command_center_rows = get_persisted_command_center_rows(org, current_user=request.user, today=today)

    if is_in_house_clm and org:
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

        clm_needs_review_count = case_qs.filter(status__in=['PENDING', 'IN_REVIEW']).count()

        clm_my_approvals_count = approvals_qs.filter(status='PENDING', assigned_to=request.user).count()

        clm_deadlines_30d_count = deadlines_qs.filter(
            is_completed=False, due_date__gte=today, due_date__lte=thirty_days,
        ).count()
        clm_renewals_count = clm_deadlines_30d_count + (case_stats['expiring_soon'] or 0)

        clm_high_risk_log_count = risks_qs.filter(risk_level__in=['HIGH', 'CRITICAL']).exclude(status='RESOLVED').count()
        clm_high_dpa_risk_count = (
            DPARiskItem.objects
            .filter(review_pack__organization=org, severity__in=['HIGH', 'CRITICAL'])
            .exclude(status__in=['RESOLVED', 'FALSE_POSITIVE'])
            .count()
        )
        clm_high_severity_count = clm_high_risk_log_count + clm_high_dpa_risk_count

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
    if clm_my_approvals_count:
        n = clm_my_approvals_count
        attention_parts.append(f"{n} approval{'s' if n != 1 else ''} in your queue")
    if clm_renewals_count:
        n = clm_renewals_count
        attention_parts.append(f"{n} renewal{'s' if n != 1 else ''}/deadline{'s' if n != 1 else ''} due soon")
    attention_total = (clm_conflict_count or 0) + (clm_needs_review_count or 0) + (clm_my_approvals_count or 0) + (clm_renewals_count or 0)
    if len(attention_parts) <= 1:
        attention_summary = attention_parts[0] if attention_parts else ''
    elif len(attention_parts) == 2:
        attention_summary = f"{attention_parts[0]} and {attention_parts[1]}"
    else:
        attention_summary = f"{', '.join(attention_parts[:-1])}, and {attention_parts[-1]}"

    priority_queue_rows = persisted_command_center_rows or queue_in_progress
    workflow_type_summary = get_workflow_type_summary(persisted_command_center_rows)
    command_center_rail_items = get_command_center_rail_items(org, {
        'approvals': clm_my_approvals_count,
        'deadlines': clm_renewals_count,
        'dpa_conflicts': clm_conflict_count,
        'review_memos': len(clm_recent_memos),
    })

    return render(request, 'dashboard.html', {
        'attention_total': attention_total,
        'attention_summary': attention_summary,
        'priority_queue_rows': priority_queue_rows,
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
        'is_in_house_clm': is_in_house_clm,
        'clm_conflict_count': clm_conflict_count,
        'clm_top_conflicts': clm_top_conflicts,
        'clm_needs_review_count': clm_needs_review_count,
        'clm_my_approvals_count': clm_my_approvals_count,
        'clm_renewals_count': clm_renewals_count,
        'clm_high_severity_count': clm_high_severity_count,
        'clm_recent_memos': clm_recent_memos,
        'clm_recent_matters': clm_recent_matters,
    })
