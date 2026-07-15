from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
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
    model. Compliance status (Met/Overdue/Breach Risk/Pending Action) is
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
        obligations = list(
            Deadline.objects
            .for_organization(org)
            .select_related('matter', 'contract', 'assigned_to')
            .order_by('due_date')
        )

        counts = {'MET': 0, 'OVERDUE': 0, 'BREACH_RISK': 0, 'PENDING': 0}
        for obligation in obligations:
            obligation.compliance_status = obligation_compliance_status(obligation)
            obligation.source = obligation.contract or obligation.matter
            counts[obligation.compliance_status] += 1

        context['obligations'] = obligations
        context['obligations_met_count'] = counts['MET']
        context['obligations_overdue_count'] = counts['OVERDUE']
        context['obligations_breach_risk_count'] = counts['BREACH_RISK']
        context['obligations_pending_count'] = counts['PENDING']
        return context


class DeadlineCreateView(TenantScopedFormMixin, TenantAssignCreateMixin, LoginRequiredMixin, CreateView):
    model = Deadline
    form_class = DeadlineForm
    template_name = 'contracts/deadline_form.html'
    success_url = reverse_lazy('contracts:deadline_list')
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
    success_url = reverse_lazy('contracts:deadline_list')
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
