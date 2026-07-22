from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.http import HttpResponseForbidden
from django.urls import reverse_lazy, reverse
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from contracts.forms import ConflictCheckForm, TrustAccountForm, TrustTransactionForm
from contracts.middleware import log_action
from contracts.models import Client, ConflictCheck, Matter, TrustAccount, TrustTransaction
from contracts.permissions import can_manage_organization
from contracts.view_support import TenantAssignCreateMixin, TenantScopedFormMixin, TenantScopedQuerysetMixin


class TrustAccountingPermissionMixin:
    """IOLTA trust accounting (client funds) is restricted to organization
    owners/admins, matching the bar-compliance expectation that support
    staff (e.g. paralegals) don't have standing access to trust balances or
    transactions. Requires an OrganizationContextMixin-derived get_organization()
    elsewhere in the MRO (already true everywhere this is used)."""

    def dispatch(self, request, *args, **kwargs):
        if not can_manage_organization(request.user, self.get_organization()):
            return HttpResponseForbidden('Only organization owners/admins can manage trust accounts.')
        return super().dispatch(request, *args, **kwargs)


class TrustAccountListView(TenantScopedQuerysetMixin, LoginRequiredMixin, TrustAccountingPermissionMixin, ListView):
    model = TrustAccount
    template_name = 'contracts/trust_account_list.html'
    context_object_name = 'accounts'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['total_balance'] = self.get_queryset().aggregate(total=Sum('balance'))['total'] or Decimal('0')
        return ctx


class TrustAccountDetailView(TenantScopedQuerysetMixin, LoginRequiredMixin, TrustAccountingPermissionMixin, DetailView):
    model = TrustAccount
    template_name = 'contracts/trust_account_detail.html'
    context_object_name = 'account'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['transactions'] = self.object.transactions.all()[:20]
        ctx['transaction_form'] = TrustTransactionForm()
        return ctx


class TrustAccountCreateView(TenantScopedFormMixin, TenantAssignCreateMixin, LoginRequiredMixin, TrustAccountingPermissionMixin, CreateView):
    model = TrustAccount
    form_class = TrustAccountForm
    template_name = 'contracts/trust_account_form.html'
    success_url = reverse_lazy('contracts:trust_account_list')
    scoped_form_fields = {'client': Client, 'matter': Matter}

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        log_action(self.request.user, 'CREATE', 'TrustAccount', self.object.id, str(self.object), request=self.request)
        return response


class AddTrustTransactionView(TenantAssignCreateMixin, LoginRequiredMixin, TrustAccountingPermissionMixin, CreateView):
    model = TrustTransaction
    form_class = TrustTransactionForm
    template_name = 'contracts/trust_transaction_form.html'

    def form_valid(self, form):
        form.instance.account_id = self.kwargs['account_pk']
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        log_action(self.request.user, 'CREATE', 'TrustTransaction', self.object.id, str(self.object), request=self.request)
        return response

    def get_success_url(self):
        return reverse('contracts:trust_account_detail', kwargs={'pk': self.kwargs['account_pk']})


class ConflictCheckListView(TenantScopedQuerysetMixin, LoginRequiredMixin, ListView):
    model = ConflictCheck
    template_name = 'contracts/conflict_check_list.html'
    context_object_name = 'conflict_checks'
    paginate_by = 25


class ConflictCheckCreateView(TenantScopedFormMixin, TenantAssignCreateMixin, LoginRequiredMixin, CreateView):
    model = ConflictCheck
    form_class = ConflictCheckForm
    template_name = 'contracts/conflict_check_form.html'
    success_url = reverse_lazy('contracts:conflict_check_list')
    scoped_form_fields = {'client': Client, 'matter': Matter}

    def form_valid(self, form):
        form.instance.checked_by = self.request.user
        response = super().form_valid(form)
        log_action(self.request.user, 'CREATE', 'ConflictCheck', self.object.id, str(self.object), request=self.request)
        return response


class ConflictCheckUpdateView(TenantScopedFormMixin, TenantScopedQuerysetMixin, LoginRequiredMixin, UpdateView):
    model = ConflictCheck
    form_class = ConflictCheckForm
    template_name = 'contracts/conflict_check_form.html'
    success_url = reverse_lazy('contracts:conflict_check_list')
    scoped_form_fields = {'client': Client, 'matter': Matter}

    def form_valid(self, form):
        previous_status = (
            ConflictCheck.objects.filter(pk=form.instance.pk).values_list('status', flat=True).first()
            if form.instance.pk else None
        )
        response = super().form_valid(form)
        if (
            self.object.status == ConflictCheck.Status.WAIVED
            and previous_status != ConflictCheck.Status.WAIVED
        ):
            from django.contrib import messages

            from contracts.services.exception_dual_write import (
                ExceptionDualWriteError,
                SOURCE_CONFLICT_CHECK_WAIVER,
                build_correlation_id,
                safe_mirror_legacy_exception,
            )
            organization = None
            if self.object.client_id:
                organization = getattr(self.object.client, 'organization', None)
            if organization is None:
                organization = self.get_organization()
            try:
                safe_mirror_legacy_exception(
                    source=SOURCE_CONFLICT_CHECK_WAIVER,
                    organization=organization,
                    actor=self.request.user,
                    owner=self.request.user,
                    title=f'Conflict check waived: {self.object.checked_party}'[:255],
                    reason=(self.object.notes or self.object.conflicts_found or 'ConflictCheck waived.').strip(),
                    scope_object_model='ConflictCheck',
                    scope_object_id=self.object.pk,
                    correlation_id=build_correlation_id(
                        source=SOURCE_CONFLICT_CHECK_WAIVER,
                        object_model='ConflictCheck',
                        object_id=self.object.pk,
                        suffix='waived',
                    ),
                    outcome='APPROVED',
                    scope_reference={
                        'client_id': self.object.client_id,
                        'matter_id': self.object.matter_id,
                        'previous_status': previous_status,
                    },
                    authority_basis='legal',
                    compensating_controls='Conflict waiver recorded on ConflictCheck; ethical wall policies remain in force.',
                    granted_privileges=['policy.deviation'],
                    risk_classification='HIGH',
                    request=self.request,
                )
            except ExceptionDualWriteError as exc:
                messages.error(self.request, str(exc))
        log_action(
            self.request.user, 'UPDATE', 'ConflictCheck',
            self.object.id, str(self.object), request=self.request,
        )
        return response
