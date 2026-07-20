from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, ListView, TemplateView, UpdateView

from contracts.forms import DeadlineForm
from contracts.middleware import log_action
from contracts.models import Contract, Deadline, Matter
from contracts.permissions import ContractAction, can_access_contract_action
from contracts.templatetags.clmone_format import obligation_compliance_status
from contracts.tenancy import get_user_organization
from contracts.view_support import (
    TenantAssignCreateMixin,
    TenantScopedFormMixin,
    TenantScopedQuerysetMixin,
    organization_user_queryset,
)

_OBLIGATION_VIEW_TABS = (
    ('all', 'All'),
    ('mine', 'My obligations'),
    ('due_soon', 'Due soon'),
    ('overdue', 'Overdue'),
    ('completed', 'Completed'),
)

_OBLIGATION_STATUS_FILTERS = (
    ('PENDING', 'Pending'),
    ('DUE_SOON', 'Due soon'),
    ('AT_RISK', 'At risk'),
    ('OVERDUE', 'Overdue'),
    ('COMPLETED', 'Completed'),
)

_OBLIGATION_DUE_PERIOD_FILTERS = (
    ('overdue', 'Overdue'),
    ('7', 'Next 7 days'),
    ('30', 'Next 30 days'),
    ('90', 'Next 90 days'),
)

_TYPE_NEXT_ACTIONS = {
    Deadline.DeadlineType.SLA: 'Review service report',
    Deadline.DeadlineType.PAYMENT: 'Confirm payment schedule',
    Deadline.DeadlineType.RENEWAL: 'Review renewal notice',
    Deadline.DeadlineType.NDA_EXPIRY: 'Review NDA expiry',
    Deadline.DeadlineType.REGULATORY: 'Confirm regulatory filing',
    Deadline.DeadlineType.FILING: 'Confirm filing package',
    Deadline.DeadlineType.CONTRACT: 'Review contract obligation',
    Deadline.DeadlineType.COURT: 'Confirm court deadline',
    Deadline.DeadlineType.SOL: 'Review limitation period',
    Deadline.DeadlineType.INTERNAL: 'Complete internal follow-up',
    Deadline.DeadlineType.CLIENT: 'Confirm with client',
    Deadline.DeadlineType.OTHER: 'Review obligation',
}


def _next_action_for_obligation(obligation):
    """Surface the highest-priority follow-up for the obligations queue."""
    if obligation.is_completed:
        return 'View record'
    if obligation.is_overdue:
        return 'Mark completed'
    return _TYPE_NEXT_ACTIONS.get(obligation.deadline_type, 'Review obligation')


def _matches_due_period(obligation, due_period, today):
    if not due_period or obligation.is_completed:
        return False if due_period else True
    if due_period == 'overdue':
        return obligation.is_overdue
    if due_period.isdigit():
        days = int(due_period)
        return (not obligation.is_overdue) and obligation.due_date <= today + timedelta(days=days)
    return True


class DeadlineListView(LoginRequiredMixin, ListView):
    model = Deadline
    template_name = 'contracts/deadline_list.html'
    context_object_name = 'deadlines'
    paginate_by = 25

    def get_organization(self):
        if not hasattr(self.request, '_cached_organization'):
            self.request._cached_organization = get_user_organization(self.request.user)
        return self.request._cached_organization

    def get_queryset(self):
        org = self.get_organization()
        queryset = Deadline.objects.select_related('matter', 'contract', 'assigned_to').for_organization(org)
        show = self.request.GET.get('show', 'upcoming')
        if show == 'overdue':
            queryset = queryset.filter(is_completed=False, due_date__lt=date.today())
        elif show == 'completed':
            queryset = queryset.filter(is_completed=True)
        elif show != 'all':
            queryset = queryset.filter(is_completed=False, due_date__gte=date.today())
        return queryset.order_by('due_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        org = self.get_organization()
        org_deadlines = Deadline.objects.for_organization(org)
        context['overdue_count'] = org_deadlines.filter(is_completed=False, due_date__lt=date.today()).count()
        context['upcoming_count'] = org_deadlines.filter(is_completed=False, due_date__gte=date.today()).count()
        context['show'] = self.request.GET.get('show', 'upcoming')
        return context


class ObligationsWorkspaceView(LoginRequiredMixin, TemplateView):
    """Phase 4: the in_house_clm "Obligations" workspace.

    Reuses the existing Deadline entity — there is no separate Obligation
    model. Operational status (Completed/Overdue/At risk/Due soon/Pending) is
    derived per-row via obligation_compliance_status, never stored, so it
    can't drift from the deadline's actual due_date/is_completed state.

    Deliberately uses Deadline.objects.for_organization(org) rather than the
    generic scope_queryset_for_organization helper: Deadline rows reach an
    organization through *either* contract or matter (both nullable FKs), an
    OR relationship the generic single-path resolver isn't built to express.
    for_organization() already encodes that OR correctly (see
    DeadlineQuerySet above) and is the same method DeadlineListView uses.
    """
    template_name = 'contracts/obligations_workspace.html'

    def get_organization(self):
        if not hasattr(self.request, '_cached_organization'):
            self.request._cached_organization = get_user_organization(self.request.user)
        return self.request._cached_organization

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        org = self.get_organization()
        today = date.today()
        params = self.request.GET

        all_obligations = list(
            Deadline.objects
            .for_organization(org)
            .select_related('matter', 'contract', 'assigned_to')
            .order_by('due_date')
        )

        counts = {
            'COMPLETED': 0,
            'OVERDUE': 0,
            'AT_RISK': 0,
            'DUE_SOON': 0,
            'PENDING': 0,
        }
        due_within_30_count = 0
        for obligation in all_obligations:
            obligation.compliance_status = obligation_compliance_status(obligation)
            obligation.source = obligation.contract or obligation.matter
            obligation.next_action = _next_action_for_obligation(obligation)
            counts[obligation.compliance_status] = counts.get(obligation.compliance_status, 0) + 1
            if (
                not obligation.is_completed
                and not obligation.is_overdue
                and obligation.due_date <= today + timedelta(days=30)
            ):
                due_within_30_count += 1

        selected_view = (params.get('view') or 'all').strip()
        if selected_view not in {key for key, _ in _OBLIGATION_VIEW_TABS}:
            selected_view = 'all'
        search_query = (params.get('q') or '').strip()
        selected_status = (params.get('status') or '').strip()
        selected_owner = (params.get('owner') or '').strip()
        selected_contract = (params.get('contract') or '').strip()
        selected_type = (params.get('type') or '').strip()
        selected_due = (params.get('due') or '').strip()

        filtered = all_obligations
        if selected_view == 'mine':
            filtered = [o for o in filtered if o.assigned_to_id == self.request.user.id]
        elif selected_view == 'due_soon':
            filtered = [
                o for o in filtered
                if not o.is_completed and not o.is_overdue and o.due_date <= today + timedelta(days=30)
            ]
        elif selected_view == 'overdue':
            filtered = [o for o in filtered if o.compliance_status == 'OVERDUE']
        elif selected_view == 'completed':
            filtered = [o for o in filtered if o.compliance_status == 'COMPLETED']

        if search_query:
            needle = search_query.casefold()
            filtered = [
                o for o in filtered
                if needle in (o.title or '').casefold()
                or needle in (o.contract.title if o.contract_id else '').casefold()
                or needle in (o.matter.title if o.matter_id else '').casefold()
                or (
                    o.assigned_to_id
                    and needle in (
                        (o.assigned_to.get_full_name() or o.assigned_to.username or '')
                    ).casefold()
                )
            ]

        if selected_status in {key for key, _ in _OBLIGATION_STATUS_FILTERS}:
            filtered = [o for o in filtered if o.compliance_status == selected_status]

        if selected_owner == 'unassigned':
            filtered = [o for o in filtered if not o.assigned_to_id]
        elif selected_owner.isdigit():
            owner_id = int(selected_owner)
            filtered = [o for o in filtered if o.assigned_to_id == owner_id]

        if selected_contract.isdigit():
            contract_id = int(selected_contract)
            filtered = [o for o in filtered if o.contract_id == contract_id]

        if selected_type in {choice.value for choice in Deadline.DeadlineType}:
            filtered = [o for o in filtered if o.deadline_type == selected_type]

        if selected_due in {key for key, _ in _OBLIGATION_DUE_PERIOD_FILTERS}:
            filtered = [o for o in filtered if _matches_due_period(o, selected_due, today)]

        owner_options = []
        seen_owners = set()
        contract_options = []
        seen_contracts = set()
        for obligation in all_obligations:
            if obligation.assigned_to_id and obligation.assigned_to_id not in seen_owners:
                seen_owners.add(obligation.assigned_to_id)
                owner_options.append(obligation.assigned_to)
            if obligation.contract_id and obligation.contract_id not in seen_contracts:
                seen_contracts.add(obligation.contract_id)
                contract_options.append(obligation.contract)
        owner_options.sort(key=lambda u: (u.get_full_name() or u.username).lower())
        contract_options.sort(key=lambda c: (c.title or '').lower())

        view_tabs = []
        for key, label in _OBLIGATION_VIEW_TABS:
            tab_params = params.copy()
            if key == 'all':
                tab_params.pop('view', None)
            else:
                tab_params['view'] = key
            view_tabs.append({
                'key': key,
                'label': label,
                'url': f"{reverse('contracts:obligations_workspace')}?{tab_params.urlencode()}" if tab_params else reverse('contracts:obligations_workspace'),
                'active': selected_view == key,
            })

        context['obligations'] = filtered
        context['obligations_completed_count'] = counts['COMPLETED']
        context['obligations_met_count'] = counts['COMPLETED']  # legacy alias
        context['obligations_overdue_count'] = counts['OVERDUE']
        context['obligations_at_risk_count'] = counts['AT_RISK']
        context['obligations_breach_risk_count'] = counts['AT_RISK']  # legacy alias
        context['obligations_due_soon_count'] = counts['DUE_SOON']
        context['obligations_pending_count'] = counts['PENDING']
        context['obligations_due_within_30_count'] = due_within_30_count
        context['view_tabs'] = view_tabs
        context['selected_view'] = selected_view
        context['search_query'] = search_query
        context['selected_status'] = selected_status
        context['selected_owner'] = selected_owner
        context['selected_contract'] = selected_contract
        context['selected_type'] = selected_type
        context['selected_due'] = selected_due
        context['status_filter_choices'] = _OBLIGATION_STATUS_FILTERS
        context['due_period_choices'] = _OBLIGATION_DUE_PERIOD_FILTERS
        context['type_filter_choices'] = Deadline.DeadlineType.choices
        context['owner_choices'] = owner_options
        context['contract_choices'] = contract_options
        context['filters_active'] = bool(
            search_query or selected_status or selected_owner
            or selected_contract or selected_type or selected_due
        )
        return context


class DeadlineCreateView(TenantScopedFormMixin, TenantAssignCreateMixin, LoginRequiredMixin, CreateView):
    model = Deadline
    form_class = DeadlineForm
    template_name = 'contracts/deadline_form.html'
    success_url = reverse_lazy('contracts:obligations_workspace')
    scoped_form_fields = {
        'matter': Matter,
        'contract': Contract,
        'assigned_to': organization_user_queryset,
    }

    def get_initial(self):
        initial = super().get_initial()
        contract_id = self.request.GET.get('contract')
        if contract_id:
            contract = Contract.objects.filter(
                organization=self.get_organization(), pk=contract_id,
            ).first()
            if contract:
                initial['contract'] = contract
        return initial

    def form_valid(self, form):
        if form.instance.contract and not can_access_contract_action(self.request.user, form.instance.contract, ContractAction.EDIT):
            return HttpResponseForbidden('You do not have permission to create deadlines for this contract.')
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        log_action(
            self.request.user, 'CREATE', 'Deadline', self.object.id, str(self.object), request=self.request,
            changes={
                'event': 'deadline.created',
                'contract_id': self.object.contract_id,
                'due_date': self.object.due_date.isoformat(),
                'assigned_to_id': self.object.assigned_to_id,
            },
        )
        return response


class DeadlineUpdateView(TenantScopedFormMixin, TenantScopedQuerysetMixin, LoginRequiredMixin, UpdateView):
    model = Deadline
    form_class = DeadlineForm
    template_name = 'contracts/deadline_form.html'
    success_url = reverse_lazy('contracts:obligations_workspace')
    scoped_form_fields = {
        'matter': Matter,
        'contract': Contract,
        'assigned_to': organization_user_queryset,
    }

    def get_queryset(self):
        org = self.get_organization()
        if not org:
            return Deadline.objects.none()
        return Deadline.objects.for_organization(org)

    def dispatch(self, request, *args, **kwargs):
        deadline = self.get_object()
        self.original_values = {
            field: getattr(deadline, field)
            for field in ('title', 'description', 'deadline_type', 'priority', 'due_date', 'due_time', 'reminder_days', 'contract_id', 'matter_id', 'assigned_to_id')
        }
        if deadline.contract and not can_access_contract_action(request.user, deadline.contract, ContractAction.EDIT):
            return HttpResponseForbidden('You do not have permission to edit this contract deadline.')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        if form.instance.contract and not can_access_contract_action(
            self.request.user, form.instance.contract, ContractAction.EDIT,
        ):
            return HttpResponseForbidden('You do not have permission to attach this deadline to that contract.')
        response = super().form_valid(form)
        changes = {}
        for field_name, before in self.original_values.items():
            after = getattr(self.object, field_name)
            if before != after:
                changes[field_name] = {
                    'before': before.isoformat() if hasattr(before, 'isoformat') else before,
                    'after': after.isoformat() if hasattr(after, 'isoformat') else after,
                }
        log_action(
            self.request.user, 'UPDATE', 'Deadline', self.object.id, str(self.object),
            request=self.request,
            changes={
                'event': 'deadline.updated',
                'contract_id': self.object.contract_id,
                'field_changes': changes,
            },
        )
        return response


@login_required
@require_POST
def deadline_complete(request, pk):
    if not hasattr(request, '_cached_organization'):
        request._cached_organization = get_user_organization(request.user)
    organization = request._cached_organization

    deadline_queryset = Deadline.objects.for_organization(organization)
    deadline = get_object_or_404(deadline_queryset, pk=pk)
    if deadline.contract and not can_access_contract_action(request.user, deadline.contract, ContractAction.EDIT):
        return HttpResponseForbidden('You do not have permission to complete this contract deadline.')
    if deadline.is_completed:
        messages.info(request, f'Deadline "{deadline.title}" was already complete.')
        return redirect('contracts:deadline_list')
    deadline.is_completed = True
    deadline.completed_at = timezone.now()
    deadline.completed_by = request.user
    deadline.save()
    log_action(
        request.user, 'UPDATE', 'Deadline', deadline.id, str(deadline), request=request,
        changes={
            'event': 'deadline.completed',
            'contract_id': deadline.contract_id,
            'previous_state': 'OPEN',
            'new_state': 'COMPLETED',
        },
    )
    messages.success(request, f'Deadline "{deadline.title}" marked as complete.')
    return redirect('contracts:deadline_list')


@login_required
@require_POST
def deadline_delete(request, pk):
    organization = get_user_organization(request.user)
    deadline = get_object_or_404(Deadline.objects.for_organization(organization), pk=pk)
    if deadline.contract and not can_access_contract_action(request.user, deadline.contract, ContractAction.EDIT):
        return HttpResponseForbidden('You do not have permission to delete this contract deadline.')
    snapshot = {
        'event': 'deadline.deleted',
        'contract_id': deadline.contract_id,
        'title': deadline.title,
        'due_date': deadline.due_date.isoformat(),
        'was_completed': deadline.is_completed,
    }
    object_id = deadline.pk
    object_repr = str(deadline)
    deadline.delete()
    log_action(
        request.user, 'DELETE', 'Deadline', object_id, object_repr,
        request=request, changes=snapshot,
    )
    messages.success(request, f'Deadline "{snapshot["title"]}" deleted.')
    return redirect('contracts:deadline_list')
