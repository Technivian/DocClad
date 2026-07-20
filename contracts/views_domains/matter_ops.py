from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models
from django.db.models import Q, Sum, Count
from django.http import HttpResponseForbidden, JsonResponse, QueryDict
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.functional import cached_property
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from contracts.forms import (
    BudgetExpenseForm,
    BudgetForm,
    ChecklistItemForm,
    ComplianceChecklistForm,
    DueDiligenceProcessForm,
    DueDiligenceRiskForm,
    DueDiligenceTaskForm,
    LegalTaskForm,
    RiskLogForm,
    TrademarkRequestForm,
)
from contracts.models import (
    AuditLog,
    Budget,
    BudgetExpense,
    ChecklistItem,
    ComplianceChecklist,
    Contract,
    DueDiligenceProcess,
    DueDiligenceRisk,
    DueDiligenceTask,
    LegalTask,
    Matter,
    RiskLog,
    TrademarkRequest,
)
from contracts.middleware import log_action
from contracts.permissions import ContractAction, can_access_contract_action
from contracts.services.legal_signals import get_legal_signal_counts_for_org, get_legal_signals_for_org
from contracts.tenancy import get_user_organization, scope_queryset_for_organization
from contracts.view_support import TenantAssignCreateMixin, TenantScopedFormMixin, TenantScopedQuerysetMixin


def _can_actor_complete_task(task, user, org):
    """Single source of truth for "can this actor complete this task" —
    used by both the Tasks queue (to decide whether to show a live Complete
    button) and the legal_task_complete endpoint (the real enforcement
    boundary), so the UI can never claim an action is available that the
    API would then refuse. Mirrors the exact rule LegalTaskUpdateView.dispatch
    already applies to editing: contract-linked tasks require contract-edit
    access; matter-linked tasks require the matter to belong to the actor's
    organization. A task with neither link has nothing further to check."""
    if task.contract_id and not can_access_contract_action(user, task.contract, ContractAction.EDIT):
        return False
    if task.matter_id and (not org or task.matter.organization_id != org.id):
        return False
    return True


class LegalTaskKanbanView(TenantScopedQuerysetMixin, LoginRequiredMixin, ListView):
    model = LegalTask
    template_name = 'contracts/legal_task_board.html'
    context_object_name = 'legal_tasks'

    def get_queryset(self):
        org = get_user_organization(self.request.user)
        if not org:
            return LegalTask.objects.none()
        return LegalTask.objects.select_related('contract', 'matter', 'assigned_to').filter(
            Q(contract__organization=org) | Q(matter__organization=org)
        ).order_by('-updated_at', '-created_at')

    def get_context_data(self, **kwargs):
        """Tasks queue: saved-view tabs backing the shared WorkQueue table.

        `legal_tasks`/`task_signals`/`open_task_signal_count` (from
        context_object_name above) are left completely untouched — existing
        callers keep reading the plain org-scoped queryset exactly as
        before. `queue_tabs` is additive.
        """
        context = super().get_context_data(**kwargs)
        context['task_signals'] = context['legal_tasks']
        context['open_task_signal_count'] = context['legal_tasks'].filter(status='PENDING').count()
        context['queue_tabs'] = self._build_queue_tabs()
        return context

    def _build_queue_tabs(self):
        from datetime import timedelta

        from contracts.services.queue_rows import creator_map, latest_activity_map
        from contracts.templatetags.clmone_format import task_priority_badge_class, task_status_badge_class

        user = self.request.user
        org = get_user_organization(user)
        today = timezone.localdate()

        empty_tabs_spec = [
            ('assigned_to_me', 'Assigned to Me', 'No tasks assigned to you.'),
            ('created_by_me', 'Created by Me', 'No tasks created by you.'),
            ('due_soon', 'Due Soon', 'Nothing due soon.'),
            ('overdue', 'Overdue', 'No overdue tasks.'),
            ('completed', 'Completed', 'No completed tasks yet.'),
            ('all_open', 'All Open', 'No open tasks.'),
        ]
        if not org:
            return [{'key': k, 'label': label, 'rows': [], 'empty_message': msg} for k, label, msg in empty_tabs_spec]

        base_qs = LegalTask.objects.select_related(
            'contract', 'matter', 'matter__client', 'assigned_to',
        ).filter(Q(contract__organization=org) | Q(matter__organization=org))
        open_statuses = (LegalTask.Status.PENDING, LegalTask.Status.IN_PROGRESS)

        def _to_rows(qs, limit=25):
            items = list(qs.order_by('due_date', '-updated_at')[:limit])
            ids = [t.pk for t in items]
            activity_map = latest_activity_map(org, ids, model_name='LegalTask')
            rows = []
            for task in items:
                contract = task.contract
                matter = task.matter
                due = task.due_date
                overdue = bool(due and due < today and task.status in open_statuses)

                edit_url = reverse('contracts:legal_task_update', kwargs={'pk': task.pk})
                href = edit_url
                meta_parts = []
                if contract:
                    href = reverse('contracts:contract_detail', kwargs={'pk': contract.pk})
                    meta_parts.append(contract.title)
                    if contract.counterparty:
                        meta_parts.append(contract.counterparty)
                elif matter:
                    href = reverse('contracts:matter_detail', kwargs={'pk': matter.pk})
                    meta_parts.append(matter.title)
                    if matter.client_id:
                        meta_parts.append(matter.client.name)

                rows.append({
                    'id': task.pk,
                    'title': task.title,
                    'edit_url': edit_url,
                    'href': href,
                    'meta': ' · '.join(meta_parts),
                    'contract': contract,
                    'assignee': task.assigned_to,
                    'activity': activity_map.get(task.pk),
                    'due_date': due,
                    'due_overdue': overdue,
                    'status_label': task.get_status_display(),
                    'status_badge_class': task_status_badge_class(task.status),
                    'priority_label': task.get_priority_display(),
                    'priority_badge_class': task_priority_badge_class(task.priority),
                    # Gate on BOTH "is this actor eligible" and "is this task
                    # still open" — an eligible admin must not see a live
                    # Complete button on an already-completed/cancelled task,
                    # since that action can only ever fail (see the same
                    # rule applied to Approvals' can_decide).
                    'can_complete': (
                        task.status in open_statuses
                        and _can_actor_complete_task(task, user, org)
                    ),
                    'complete_url': reverse('contracts:legal_task_complete', kwargs={'pk': task.pk}),
                })
            return rows

        assigned_qs = base_qs.filter(assigned_to=user, status__in=open_statuses)
        due_soon_qs = base_qs.filter(
            status__in=open_statuses, due_date__gte=today, due_date__lte=today + timedelta(days=7),
        )
        overdue_qs = base_qs.filter(status__in=open_statuses, due_date__lt=today)
        completed_qs = base_qs.filter(status=LegalTask.Status.COMPLETED)
        all_open_qs = base_qs.filter(status__in=open_statuses)

        all_ids = list(base_qs.values_list('pk', flat=True))
        creators = creator_map(org, all_ids, model_name='LegalTask')
        created_ids = [task_id for task_id, creator in creators.items() if creator and creator.id == user.id]
        created_qs = base_qs.filter(pk__in=created_ids)

        return [
            {'key': 'assigned_to_me', 'label': 'Assigned to Me', 'rows': _to_rows(assigned_qs),
             'empty_message': 'No tasks assigned to you.'},
            {'key': 'created_by_me', 'label': 'Created by Me', 'rows': _to_rows(created_qs),
             'empty_message': 'No tasks created by you.'},
            {'key': 'due_soon', 'label': 'Due Soon', 'rows': _to_rows(due_soon_qs),
             'empty_message': 'Nothing due soon.'},
            {'key': 'overdue', 'label': 'Overdue', 'rows': _to_rows(overdue_qs),
             'empty_message': 'No overdue tasks.'},
            {'key': 'completed', 'label': 'Completed', 'rows': _to_rows(completed_qs),
             'empty_message': 'No completed tasks yet.'},
            {'key': 'all_open', 'label': 'All Open', 'rows': _to_rows(all_open_qs),
             'empty_message': 'No open tasks.'},
        ]


class LegalTaskCreateView(TenantScopedFormMixin, TenantAssignCreateMixin, LoginRequiredMixin, CreateView):
    model = LegalTask
    form_class = LegalTaskForm
    template_name = 'contracts/legal_task_form.html'
    success_url = reverse_lazy('contracts:legal_task_kanban')
    scoped_form_fields = {'contract': Contract, 'matter': Matter}

    def form_valid(self, form):
        org = get_user_organization(self.request.user)
        if form.instance.contract and not can_access_contract_action(self.request.user, form.instance.contract, ContractAction.EDIT):
            return HttpResponseForbidden('You do not have permission to create tasks for this contract.')
        if form.instance.matter and org and form.instance.matter.organization_id != org.id:
            return HttpResponseForbidden('You do not have permission to create tasks for this matter.')
        response = super().form_valid(form)
        # LegalTask has no created_by field of its own — this CREATE entry is
        # the only signal the Tasks queue's "Created by Me" tab can use to
        # attribute a task to its creator (see queue_rows.creator_map).
        task = self.object
        task_org = task.contract.organization if task.contract_id else (task.matter.organization if task.matter_id else org)
        log_action(
            self.request.user, AuditLog.Action.CREATE, 'LegalTask',
            object_id=task.pk, object_repr=str(task), organization=task_org,
            changes={'event': 'legal_task_created'},
            request=self.request,
        )
        return response


class LegalTaskUpdateView(TenantScopedFormMixin, TenantScopedQuerysetMixin, LoginRequiredMixin, UpdateView):
    model = LegalTask
    form_class = LegalTaskForm
    template_name = 'contracts/legal_task_form.html'
    success_url = reverse_lazy('contracts:legal_task_kanban')
    scoped_form_fields = {'contract': Contract, 'matter': Matter}

    def get_queryset(self):
        org = get_user_organization(self.request.user)
        if not org:
            return LegalTask.objects.none()
        return LegalTask.objects.filter(Q(contract__organization=org) | Q(matter__organization=org))

    def dispatch(self, request, *args, **kwargs):
        task = self.get_object()
        org = get_user_organization(request.user)
        if not _can_actor_complete_task(task, request.user, org):
            return HttpResponseForbidden('You do not have permission to edit tasks for this contract or matter.')
        return super().dispatch(request, *args, **kwargs)


@login_required
@require_POST
def legal_task_complete(request, pk):
    """Mark a task complete from the Tasks queue.

    Reuses the exact same authorization LegalTaskUpdateView already enforces
    (contract-edit access, or matching matter organization) — this action
    does not introduce a new permission model, just a faster path to a
    status change the edit form already allows implicitly via the object
    queryset scoping. Cross-tenant tasks 404 (excluded by the queryset,
    mirroring the approval API's cross-tenant behaviour); same-tenant but
    unauthorized is 403; an already-decided task is a safe 400, never a
    silent no-op.
    """
    org = get_user_organization(request.user)
    if not org:
        return JsonResponse({'error': 'No active organization found.'}, status=403)

    queryset = LegalTask.objects.select_related('contract', 'matter').filter(
        Q(contract__organization=org) | Q(matter__organization=org)
    )
    task = get_object_or_404(queryset, pk=pk)

    if not _can_actor_complete_task(task, request.user, org):
        return JsonResponse({'error': 'You do not have permission to complete this task.'}, status=403)

    if task.status not in (LegalTask.Status.PENDING, LegalTask.Status.IN_PROGRESS):
        return JsonResponse(
            {'error': f'Cannot complete a task with status {task.get_status_display()}.'}, status=400,
        )

    task.status = LegalTask.Status.COMPLETED
    task.save(update_fields=['status', 'updated_at'])

    task_org = task.contract.organization if task.contract_id else (task.matter.organization if task.matter_id else org)
    log_action(
        request.user, AuditLog.Action.UPDATE, 'LegalTask',
        object_id=task.pk, object_repr=str(task), organization=task_org,
        changes={'event': 'legal_task_completed'},
        request=request,
    )
    return JsonResponse({'ok': True})


class TrademarkRequestListView(TenantScopedQuerysetMixin, LoginRequiredMixin, ListView):
    model = TrademarkRequest
    template_name = 'contracts/trademark_request_list.html'
    context_object_name = 'trademark_requests'

    def get_queryset(self):
        org = get_user_organization(self.request.user)
        if org:
            qs = TrademarkRequest.objects.select_related('client', 'matter').filter(Q(client__organization=org) | Q(matter__organization=org))
        else:
            qs = TrademarkRequest.objects.none()
        search_query = (self.request.GET.get('q') or '').strip()
        status = (self.request.GET.get('status') or '').strip()
        if search_query:
            qs = qs.filter(Q(mark_text__icontains=search_query) | Q(description__icontains=search_query) | Q(client__name__icontains=search_query) | Q(matter__title__icontains=search_query))
        if status:
            qs = qs.filter(status=status)
        return qs.order_by('-updated_at', '-created_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        org = get_user_organization(self.request.user)
        if org:
            tenant_requests = TrademarkRequest.objects.filter(Q(client__organization=org) | Q(matter__organization=org))
        else:
            tenant_requests = TrademarkRequest.objects.none()
        ctx['search_query'] = (self.request.GET.get('q') or '').strip()
        ctx['selected_status'] = (self.request.GET.get('status') or '').strip()
        ctx['status_choices'] = TrademarkRequest.Status.choices
        ctx['total_requests'] = tenant_requests.count()
        ctx['pending_requests'] = tenant_requests.filter(status=TrademarkRequest.Status.PENDING).count()
        ctx['approved_requests'] = tenant_requests.filter(status=TrademarkRequest.Status.APPROVED).count()
        ctx['request_tabs'] = [('All Requests', ''), ('Pending', TrademarkRequest.Status.PENDING), ('Approved', TrademarkRequest.Status.APPROVED)]
        return ctx


class TrademarkRequestDetailView(TenantScopedQuerysetMixin, LoginRequiredMixin, DetailView):
    model = TrademarkRequest
    template_name = 'contracts/trademark_request_detail.html'
    context_object_name = 'trademark_request'

    def get_queryset(self):
        org = get_user_organization(self.request.user)
        if not org:
            return TrademarkRequest.objects.none()
        return TrademarkRequest.objects.filter(Q(client__organization=org) | Q(matter__organization=org))


class TrademarkRequestCreateView(TenantAssignCreateMixin, LoginRequiredMixin, CreateView):
    model = TrademarkRequest
    form_class = TrademarkRequestForm
    template_name = 'contracts/trademark_request_form.html'
    success_url = reverse_lazy('contracts:trademark_request_list')


class TrademarkRequestUpdateView(TenantScopedQuerysetMixin, LoginRequiredMixin, UpdateView):
    model = TrademarkRequest
    form_class = TrademarkRequestForm
    template_name = 'contracts/trademark_request_form.html'
    success_url = reverse_lazy('contracts:trademark_request_list')

    def get_queryset(self):
        org = get_user_organization(self.request.user)
        if not org:
            return TrademarkRequest.objects.none()
        return TrademarkRequest.objects.filter(Q(client__organization=org) | Q(matter__organization=org))


class RiskLogListView(TenantScopedQuerysetMixin, LoginRequiredMixin, ListView):
    """Risk Review.

    law_firm_ops keeps the original Risk Register (RiskLog-only, unchanged
    below). in_house_clm renders the Phase 4 Legal Intelligence Hub instead —
    the same route/URL names, gated by workspace_mode so law_firm_ops
    behavior and queries are untouched (`is_in_house_clm` short-circuits the
    RiskLog queryset/context building entirely rather than computing it and
    discarding it).
    """
    model = RiskLog
    context_object_name = 'risk_logs'

    @cached_property
    def organization(self):
        return get_user_organization(self.request.user)

    @cached_property
    def is_in_house_clm(self):
        mode = getattr(self.organization, 'workspace_mode', 'law_firm_ops') if self.organization else 'law_firm_ops'
        return mode == 'in_house_clm'

    def get_template_names(self):
        if self.is_in_house_clm:
            return ['contracts/legal_intelligence_hub.html']
        return ['contracts/risk_log_list.html']

    def get_queryset(self):
        if self.is_in_house_clm:
            return RiskLog.objects.none()
        org = self.organization
        if org:
            qs = RiskLog.objects.select_related('contract', 'matter', 'created_by').filter(Q(contract__organization=org) | Q(matter__organization=org))
        else:
            qs = RiskLog.objects.none()
        search_query = (self.request.GET.get('q') or '').strip()
        risk_level = (self.request.GET.get('risk_level') or '').strip()
        if search_query:
            qs = qs.filter(Q(title__icontains=search_query) | Q(description__icontains=search_query) | Q(contract__title__icontains=search_query) | Q(matter__title__icontains=search_query))
        if risk_level:
            qs = qs.filter(risk_level=risk_level)
        risk_order = models.Case(
            models.When(risk_level=RiskLog.RiskLevel.CRITICAL, then=models.Value(0)),
            models.When(risk_level=RiskLog.RiskLevel.HIGH, then=models.Value(1)),
            models.When(risk_level=RiskLog.RiskLevel.MEDIUM, then=models.Value(2)),
            default=models.Value(3),
            output_field=models.IntegerField(),
        )
        return qs.annotate(risk_sort=risk_order).order_by('risk_sort', '-created_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['is_in_house_clm'] = self.is_in_house_clm
        if self.is_in_house_clm:
            signal_type = (self.request.GET.get('type') or 'all').strip()
            search_query = (self.request.GET.get('q') or '').strip()
            selected_severity = (self.request.GET.get('severity') or '').strip()
            filters = {}
            if signal_type and signal_type != 'all':
                filters['type'] = signal_type
            if search_query:
                filters['q'] = search_query
            if selected_severity:
                filters['severity'] = selected_severity
            counts = get_legal_signal_counts_for_org(self.organization)
            signals = get_legal_signals_for_org(
                self.organization,
                user=self.request.user,
                filters=filters or None,
            )
            hub_url = reverse('contracts:risk_log_list')
            tab_defs = [
                ('all', 'All', counts['total_count']),
                ('conflicts', 'Conflicts', counts['conflict_count']),
                ('dpa_risk', 'DPA Risks', counts['by_type']['dpa_risk']),
                ('contract_risk', 'Contract Risks', counts['by_type']['contract_risk']),
                ('approval', 'Approvals', counts['by_type']['approval']),
                ('deadline', 'Deadlines', counts['by_type']['deadline']),
            ]
            view_tabs = []
            for key, label, tab_count in tab_defs:
                params = QueryDict(mutable=True)
                if key != 'all':
                    params['type'] = key
                if search_query:
                    params['q'] = search_query
                if selected_severity:
                    params['severity'] = selected_severity
                query = params.urlencode()
                view_tabs.append({
                    'key': key,
                    'label': f'{label} ({tab_count})',
                    'url': f'{hub_url}?{query}' if query else hub_url,
                    'active': signal_type == key,
                })
            clear_params = QueryDict(mutable=True)
            if signal_type and signal_type != 'all':
                clear_params['type'] = signal_type
            clear_query = clear_params.urlencode()
            ctx['legal_signals'] = signals
            ctx['legal_signal_counts'] = counts
            ctx['selected_signal_type'] = signal_type
            ctx['search_query'] = search_query
            ctx['selected_severity'] = selected_severity
            ctx['filters_active'] = bool(search_query or selected_severity)
            ctx['hub_clear_url'] = f'{hub_url}?{clear_query}' if clear_query else hub_url
            ctx['view_tabs'] = view_tabs
            # Legacy tuple form kept for older assertions that scan tab names.
            ctx['signal_tabs'] = [
                (label, key, tab_count) for key, label, tab_count in tab_defs
            ]
            return ctx

        org = self.organization
        if org:
            tenant_risks = RiskLog.objects.filter(Q(contract__organization=org) | Q(matter__organization=org))
        else:
            tenant_risks = RiskLog.objects.none()
        ctx['search_query'] = (self.request.GET.get('q') or '').strip()
        ctx['selected_risk_level'] = (self.request.GET.get('risk_level') or '').strip()
        ctx['total_risks'] = tenant_risks.count()
        ctx['high_risk_count'] = tenant_risks.filter(risk_level=RiskLog.RiskLevel.HIGH).count()
        ctx['critical_risk_count'] = tenant_risks.filter(risk_level=RiskLog.RiskLevel.CRITICAL).count()
        ctx['risk_tabs'] = [('All Risks', ''), ('High Risk', RiskLog.RiskLevel.HIGH), ('Critical Risk', RiskLog.RiskLevel.CRITICAL)]
        # Governance KPI strip (Risk Register convergence block): real,
        # existing fields only — status and risk_level are the only severity/
        # progress signals RiskLog actually carries. High severity bundles
        # HIGH+CRITICAL since the strip has one severity slot, not two.
        ctx['open_risk_count'] = tenant_risks.filter(status=RiskLog.Status.OPEN).count()
        ctx['in_progress_risk_count'] = tenant_risks.filter(status=RiskLog.Status.IN_PROGRESS).count()
        ctx['resolved_risk_count'] = tenant_risks.filter(status=RiskLog.Status.RESOLVED).count()
        ctx['high_severity_count'] = tenant_risks.filter(
            risk_level__in=[RiskLog.RiskLevel.HIGH, RiskLog.RiskLevel.CRITICAL]
        ).count()
        return ctx


class RiskLogCreateView(TenantAssignCreateMixin, LoginRequiredMixin, CreateView):
    model = RiskLog
    form_class = RiskLogForm
    template_name = 'contracts/risk_log_form.html'
    success_url = reverse_lazy('contracts:risk_log_list')

    def form_valid(self, form):
        if form.instance.contract and not can_access_contract_action(self.request.user, form.instance.contract, ContractAction.EDIT):
            return HttpResponseForbidden('You do not have permission to create risk logs for this contract.')
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class RiskLogUpdateView(TenantScopedQuerysetMixin, LoginRequiredMixin, UpdateView):
    model = RiskLog
    form_class = RiskLogForm
    template_name = 'contracts/risk_log_form.html'
    success_url = reverse_lazy('contracts:risk_log_list')

    def get_queryset(self):
        org = get_user_organization(self.request.user)
        if not org:
            return RiskLog.objects.none()
        return RiskLog.objects.filter(Q(contract__organization=org) | Q(matter__organization=org))

    def dispatch(self, request, *args, **kwargs):
        risk_log = self.get_object()
        if risk_log.contract and not can_access_contract_action(request.user, risk_log.contract, ContractAction.EDIT):
            return HttpResponseForbidden('You do not have permission to edit risk logs for this contract.')
        return super().dispatch(request, *args, **kwargs)


class ComplianceChecklistListView(TenantScopedQuerysetMixin, LoginRequiredMixin, ListView):
    model = ComplianceChecklist
    template_name = 'contracts/compliance_checklist_list.html'
    context_object_name = 'compliance_checklists'


class ComplianceChecklistDetailView(TenantScopedQuerysetMixin, LoginRequiredMixin, DetailView):
    model = ComplianceChecklist
    template_name = 'contracts/compliance_checklist_detail.html'
    context_object_name = 'compliance_checklist'


class ComplianceChecklistCreateView(TenantAssignCreateMixin, LoginRequiredMixin, CreateView):
    model = ComplianceChecklist
    form_class = ComplianceChecklistForm
    template_name = 'contracts/compliance_checklist_form.html'
    success_url = reverse_lazy('contracts:compliance_checklist_list')

    def form_valid(self, form):
        if form.instance.contract and not can_access_contract_action(self.request.user, form.instance.contract, ContractAction.EDIT):
            return HttpResponseForbidden('You do not have permission to create checklists for this contract.')
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class ComplianceChecklistUpdateView(TenantScopedQuerysetMixin, LoginRequiredMixin, UpdateView):
    model = ComplianceChecklist
    form_class = ComplianceChecklistForm
    template_name = 'contracts/compliance_checklist_form.html'
    success_url = reverse_lazy('contracts:compliance_checklist_list')

    def dispatch(self, request, *args, **kwargs):
        checklist = self.get_object()
        if checklist.contract and not can_access_contract_action(request.user, checklist.contract, ContractAction.EDIT):
            return HttpResponseForbidden('You do not have permission to edit this contract checklist.')
        return super().dispatch(request, *args, **kwargs)


class DueDiligenceListView(TenantScopedQuerysetMixin, LoginRequiredMixin, ListView):
    model = DueDiligenceProcess
    template_name = 'contracts/due_diligence_list.html'
    context_object_name = 'processes'


class DueDiligenceCreateView(TenantAssignCreateMixin, LoginRequiredMixin, CreateView):
    model = DueDiligenceProcess
    form_class = DueDiligenceProcessForm
    template_name = 'contracts/due_diligence_form.html'
    success_url = reverse_lazy('contracts:due_diligence_list')


class DueDiligenceDetailView(TenantScopedQuerysetMixin, LoginRequiredMixin, DetailView):
    model = DueDiligenceProcess
    template_name = 'contracts/due_diligence_detail.html'
    context_object_name = 'process'


class DueDiligenceUpdateView(TenantScopedQuerysetMixin, LoginRequiredMixin, UpdateView):
    model = DueDiligenceProcess
    form_class = DueDiligenceProcessForm
    template_name = 'contracts/due_diligence_form.html'
    success_url = reverse_lazy('contracts:due_diligence_list')


# Departmental capacity budgets are firm-operations data (allocations, spend,
# department/quarter), not client funds — deliberately open to any active org
# member (MEMBER/ADMIN/OWNER), same policy as Invoice and the reports
# dashboard. This is a policy decision, not an oversight: contrast with
# TrustAccount (contracts/views_domains/trust_conflict.py), which holds client
# funds and is restricted to OWNER/ADMIN for bar-compliance reasons that don't
# apply here. Tenant scoping (TenantScopedQuerysetMixin / TenantAssignCreateMixin)
# still applies — see tests/test_budget_access_policy.py.
class BudgetListView(TenantScopedQuerysetMixin, LoginRequiredMixin, ListView):
    model = Budget
    template_name = 'contracts/budget_list.html'
    context_object_name = 'budgets'

    def get_queryset(self):
        org = get_user_organization(self.request.user)
        queryset = scope_queryset_for_organization(Budget.objects.all(), org)
        search_query = (self.request.GET.get('q') or '').strip()
        year = (self.request.GET.get('year') or '').strip()
        if search_query:
            queryset = queryset.filter(Q(department__icontains=search_query) | Q(description__icontains=search_query))
        if year and year.isdigit():
            queryset = queryset.filter(year=int(year))
        return queryset.order_by('-year', 'quarter', 'department')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        org = get_user_organization(self.request.user)
        tenant_budgets = scope_queryset_for_organization(Budget.objects.all(), org)
        current_year = timezone.localdate().year
        ctx['search_query'] = (self.request.GET.get('q') or '').strip()
        ctx['selected_year'] = (self.request.GET.get('year') or '').strip()
        ctx['current_year'] = current_year
        budget_stats = tenant_budgets.aggregate(total=Count('id'), current_year=Count('id', filter=Q(year=current_year)), total_allocated=Sum('allocated_amount'))
        ctx['total_budgets'] = budget_stats['total']
        ctx['current_year_budgets'] = budget_stats['current_year']
        ctx['total_allocated'] = budget_stats['total_allocated'] or Decimal('0')
        ctx['budget_tabs'] = [('All Budgets', ''), (str(current_year), str(current_year))]
        return ctx


# Same policy as BudgetListView above: any active org member may create a
# department budget.
class BudgetCreateView(TenantAssignCreateMixin, LoginRequiredMixin, CreateView):
    model = Budget
    form_class = BudgetForm
    template_name = 'contracts/budget_form.html'
    success_url = reverse_lazy('contracts:budget_list')


# Same policy as BudgetListView above: any active org member may view a
# department budget's detail.
class BudgetDetailView(TenantScopedQuerysetMixin, LoginRequiredMixin, DetailView):
    model = Budget
    template_name = 'contracts/budget_detail.html'
    context_object_name = 'budget'


# Same policy as BudgetListView above: any active org member may edit a
# department budget.
class BudgetUpdateView(TenantScopedQuerysetMixin, LoginRequiredMixin, UpdateView):
    model = Budget
    form_class = BudgetForm
    template_name = 'contracts/budget_form.html'
    success_url = reverse_lazy('contracts:budget_list')
