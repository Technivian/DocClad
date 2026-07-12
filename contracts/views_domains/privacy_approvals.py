import csv
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from contracts.forms import (
    ApprovalRequestForm,
    ApprovalRuleForm,
    DSARRequestForm,
    DataInventoryForm,
    LegalHoldForm,
    RetentionPolicyForm,
    SignatureRequestForm,
    SubprocessorForm,
    TransferRecordForm,
)
from contracts.models import (
    ApprovalRequest,
    ApprovalRule,
    AuditLog,
    Client,
    Contract,
    DSARRequest,
    DataInventoryRecord,
    Document,
    EthicalWall,
    LegalHold,
    Matter,
    OrgPolicy,
    RetentionPolicy,
    SignatureRequest,
    Subprocessor,
    TransferRecord,
    Notification,
    OrganizationMembership,
)
from contracts.middleware import log_action
from contracts.tenancy import get_user_organization, scope_queryset_for_organization
from contracts.services.esign import ESignTransitionError, send_signature_request, transition_signature_request
from contracts.services.signature_providers import SignatureProviderError
from contracts.services.signature_audit import (
    log_signature_packet_cancel,
    log_signature_packet_created,
    log_signature_packet_resend,
    log_signature_packet_retry,
)
from contracts.services.signature_workspace import build_signature_packet, build_signature_workspace
from contracts.view_support import (
    TenantAssignCreateMixin,
    TenantScopedFormMixin,
    TenantScopedQuerysetMixin,
    get_scoped_queryset_for_request,
    organization_user_queryset as _organization_user_queryset,
)
from contracts.permissions import can_manage_organization


class SignatureRequestListView(TenantScopedQuerysetMixin, LoginRequiredMixin, ListView):
    model = SignatureRequest
    template_name = 'contracts/signature_request_list.html'
    context_object_name = 'signatures'

    def get_queryset(self):
        org = self.get_organization()
        qs = scope_queryset_for_organization(SignatureRequest.objects.select_related('contract').all(), org)
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        workspace = build_signature_workspace(self.get_organization())
        status = self.request.GET.get('status')
        packet_rows = workspace['queue_rows']
        if status:
            packet_rows = [row for row in packet_rows if row.status == status]
        context['signature_workspace'] = workspace
        context['packet_rows'] = packet_rows
        context['failed_packets'] = workspace['failed_packets']
        context['signature_kpis'] = workspace['kpis']
        return context


class SignatureRequestCreateView(TenantScopedFormMixin, TenantAssignCreateMixin, LoginRequiredMixin, CreateView):
    model = SignatureRequest
    form_class = SignatureRequestForm
    template_name = 'contracts/signature_request_form.html'
    success_url = reverse_lazy('contracts:signature_request_list')
    scoped_form_fields = {'contract': Contract, 'document': Document}

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        contract = form.instance.contract
        if contract and contract.signature_requests.filter(organization=form.instance.organization).count() == 1:
            log_signature_packet_created(
                user=self.request.user,
                contract=contract,
                organization=form.instance.organization,
                request_count=1,
                request=self.request,
            )
        return response


class SignatureRequestDetailView(TenantScopedQuerysetMixin, LoginRequiredMixin, DetailView):
    model = SignatureRequest
    template_name = 'contracts/signature_request_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['available_transitions'] = self.object.available_transitions_for_actor(self.request.user)
        context['needs_follow_up'] = self.object.is_follow_up_due()
        context['follow_up_threshold_days'] = 7
        context['routing_blockers'] = self.object.routing_blockers()
        context['routing_ready'] = self.object.is_routing_ready()
        context['can_send_reminder'] = (
            self.object.created_by_id == self.request.user.id
            or can_manage_organization(self.request.user, self.object.organization)
        )
        context['packet_detail_url'] = reverse('contracts:signature_packet_detail', kwargs={'contract_pk': self.object.contract_id})
        context['packet_summary'] = build_signature_packet(self.object.organization, self.object.contract)
        return context


def _signature_reminder_recipients(signature_request):
    recipients = set()
    if signature_request.created_by_id:
        recipients.add(signature_request.created_by)
    organization = signature_request.organization
    if organization:
        for membership in OrganizationMembership.objects.filter(
            organization=organization,
            is_active=True,
            role__in=[OrganizationMembership.Role.OWNER, OrganizationMembership.Role.ADMIN],
        ).select_related('user'):
            recipients.add(membership.user)
    return recipients


@login_required
@require_POST
def signature_request_send_reminder(request, pk):
    org = get_user_organization(request.user)
    queryset = scope_queryset_for_organization(SignatureRequest.objects.select_related('contract', 'document', 'created_by'), org)
    signature_request = get_object_or_404(queryset, pk=pk)
    if not (signature_request.created_by_id == request.user.id or can_manage_organization(request.user, signature_request.organization)):
        return HttpResponseForbidden('You are not authorized to send reminders for this signature request.')

    if signature_request.status not in {SignatureRequest.Status.PENDING, SignatureRequest.Status.SENT, SignatureRequest.Status.VIEWED}:
        messages.info(request, 'This signature request is already closed.')
        return redirect(reverse('contracts:signature_request_detail', kwargs={'pk': signature_request.pk}))

    recipients = _signature_reminder_recipients(signature_request)
    reminder_link = reverse('contracts:signature_request_detail', kwargs={'pk': signature_request.pk})
    reminder_title = f'Signature reminder: {signature_request.contract.title} ({signature_request.signer_name})'
    created_count = 0
    for recipient in recipients:
        exists = Notification.objects.filter(
            recipient=recipient,
            notification_type=Notification.NotificationType.SYSTEM,
            title=reminder_title,
            link=reminder_link,
            created_at__date=timezone.localdate(),
        ).exists()
        if exists:
            continue
        Notification.objects.create(
            recipient=recipient,
            notification_type=Notification.NotificationType.SYSTEM,
            title=reminder_title,
            message=(
                f'{signature_request.contract.title} is waiting on signature from '
                f'{signature_request.signer_name} ({signature_request.signer_email}).'
            ),
            link=reminder_link,
        )
        created_count += 1

    log_action(
        request.user,
        AuditLog.Action.UPDATE,
        'SignatureRequest',
        object_id=signature_request.id,
        object_repr=str(signature_request),
        changes={
            'event': 'signature_request_reminder_sent',
            'notification_count': created_count,
            'organization_id': getattr(org, 'id', None),
        },
        request=request,
    )
    messages.success(request, f'Signature reminder queued for {created_count} recipient(s).')
    return redirect(reverse('contracts:signature_request_detail', kwargs={'pk': signature_request.pk}))


class SignatureRequestUpdateView(TenantScopedFormMixin, TenantScopedQuerysetMixin, LoginRequiredMixin, UpdateView):
    model = SignatureRequest
    form_class = SignatureRequestForm
    template_name = 'contracts/signature_request_form.html'
    success_url = reverse_lazy('contracts:signature_request_list')
    scoped_form_fields = {'contract': Contract, 'document': Document}

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['actor'] = self.request.user
        return kwargs


@login_required
@require_POST
def signature_request_transition(request, pk, new_status):
    org = get_user_organization(request.user)
    queryset = scope_queryset_for_organization(SignatureRequest.objects.select_related('contract', 'document', 'created_by'), org)
    signature_request = get_object_or_404(queryset, pk=pk)
    try:
        transition_signature_request(signature_request, new_status, actor=request.user)
    except ESignTransitionError as exc:
        return HttpResponseForbidden(str(exc))

    log_action(
        request.user,
        AuditLog.Action.UPDATE,
        'SignatureRequest',
        object_id=signature_request.id,
        object_repr=str(signature_request),
        changes={
            'event': 'signature_request_transition',
            'to_status': new_status,
            'organization_id': getattr(org, 'id', None),
        },
        request=request,
    )
    messages.success(request, f'Signature request marked as {signature_request.get_status_display().lower()}.')
    return redirect(reverse('contracts:signature_request_detail', kwargs={'pk': signature_request.pk}))


@login_required
@require_POST
def signature_request_send(request, pk):
    org = get_user_organization(request.user)
    queryset = scope_queryset_for_organization(
        SignatureRequest.objects.select_related('contract', 'document', 'created_by'), org
    )
    signature_request = get_object_or_404(queryset, pk=pk)
    try:
        result = send_signature_request(signature_request, actor=request.user)
    except ESignTransitionError as exc:
        return HttpResponseForbidden(str(exc))
    except SignatureProviderError as exc:
        messages.error(request, f'Could not send for signature: {exc}')
        return redirect(reverse('contracts:signature_request_detail', kwargs={'pk': signature_request.pk}))

    if result.get('sent'):
        log_action(
            request.user,
            AuditLog.Action.UPDATE,
            'SignatureRequest',
            object_id=signature_request.id,
            object_repr=str(signature_request),
            changes={
                'event': 'signature_request_sent',
                'provider': result.get('provider'),
                'external_id': result.get('external_id'),
                'organization_id': getattr(org, 'id', None),
            },
            request=request,
        )
        messages.success(request, f'Sent to {signature_request.signer_email} for signature.')
    else:
        messages.info(request, 'Signature request was already sent.')
    return redirect(reverse('contracts:signature_request_detail', kwargs={'pk': signature_request.pk}))


class SignaturePacketDetailView(TenantScopedQuerysetMixin, LoginRequiredMixin, DetailView):
    model = Contract
    template_name = 'contracts/signature_packet_detail.html'
    context_object_name = 'contract'
    pk_url_kwarg = 'contract_pk'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        packet = build_signature_packet(self.get_organization(), self.object)
        context['packet'] = packet
        context.update(packet)
        return context


def _packet_queryset(request, contract_pk):
    org = get_user_organization(request.user)
    contract_queryset = scope_queryset_for_organization(Contract.objects.select_related('organization').all(), org)
    contract = get_object_or_404(contract_queryset, pk=contract_pk)
    signatures = list(
        scope_queryset_for_organization(
            SignatureRequest.objects.select_related('contract', 'created_by').all(),
            org,
        ).filter(contract=contract).order_by('order', 'created_at', 'pk')
    )
    return org, contract, signatures


def _packet_action_allowed(request, contract):
    return (
        contract.created_by_id == getattr(request.user, 'id', None)
        or can_manage_organization(request.user, contract.organization)
    )


@login_required
@require_POST
def signature_packet_resend(request, contract_pk):
    org, contract, signatures = _packet_queryset(request, contract_pk)
    if not _packet_action_allowed(request, contract):
        return HttpResponseForbidden('You are not authorized to resend this signature packet.')

    active_signatures = [item for item in signatures if item.status in {SignatureRequest.Status.PENDING, SignatureRequest.Status.SENT, SignatureRequest.Status.VIEWED}]
    if not active_signatures:
        messages.info(request, 'This packet has no active requests to resend.')
        return redirect(reverse('contracts:signature_packet_detail', kwargs={'contract_pk': contract.pk}))

    now = timezone.now()
    changed_ids = []
    for signature in active_signatures:
        if signature.status == SignatureRequest.Status.PENDING:
            signature.status = SignatureRequest.Status.SENT
        signature.sent_at = now
        signature.save(update_fields=['status', 'sent_at'])
        changed_ids.append(signature.id)

    log_signature_packet_resend(
        user=request.user,
        contract=contract,
        organization=org,
        request_ids=changed_ids,
        request_count=len(changed_ids),
        request=request,
    )
    messages.success(request, f'Resent signature packet to {len(changed_ids)} request(s).')
    return redirect(reverse('contracts:signature_packet_detail', kwargs={'contract_pk': contract.pk}))


@login_required
@require_POST
def signature_packet_cancel(request, contract_pk):
    org, contract, signatures = _packet_queryset(request, contract_pk)
    if not _packet_action_allowed(request, contract):
        return HttpResponseForbidden('You are not authorized to cancel this signature packet.')

    active_signatures = [item for item in signatures if item.status not in {SignatureRequest.Status.SIGNED, SignatureRequest.Status.DECLINED, SignatureRequest.Status.EXPIRED, SignatureRequest.Status.CANCELLED}]
    if not active_signatures:
        messages.info(request, 'This packet is already closed.')
        return redirect(reverse('contracts:signature_packet_detail', kwargs={'contract_pk': contract.pk}))

    changed_ids = []
    for signature in active_signatures:
        signature.status = SignatureRequest.Status.CANCELLED
        signature.save(update_fields=['status'])
        changed_ids.append(signature.id)

    log_signature_packet_cancel(
        user=request.user,
        contract=contract,
        organization=org,
        request_ids=changed_ids,
        request_count=len(changed_ids),
        request=request,
    )
    messages.success(request, f'Cancelled {len(changed_ids)} signature request(s).')
    return redirect(reverse('contracts:signature_packet_detail', kwargs={'contract_pk': contract.pk}))


@login_required
@require_POST
def signature_packet_retry(request, contract_pk):
    org, contract, signatures = _packet_queryset(request, contract_pk)
    if not _packet_action_allowed(request, contract):
        return HttpResponseForbidden('You are not authorized to retry this signature packet.')

    failed_signatures = [item for item in signatures if item.status in {SignatureRequest.Status.DECLINED, SignatureRequest.Status.EXPIRED, SignatureRequest.Status.CANCELLED}]
    if not failed_signatures:
        messages.info(request, 'This packet does not have any failed requests to retry.')
        return redirect(reverse('contracts:signature_packet_detail', kwargs={'contract_pk': contract.pk}))

    changed_ids = []
    for signature in failed_signatures:
        signature.status = SignatureRequest.Status.PENDING
        signature.sent_at = None
        signature.viewed_at = None
        signature.signed_at = None
        signature.declined_at = None
        signature.decline_reason = ''
        signature.ip_address = None
        signature.execution_certificate_url = ''
        signature.external_id = ''
        signature.save(
            update_fields=[
                'status',
                'sent_at',
                'viewed_at',
                'signed_at',
                'declined_at',
                'decline_reason',
                'ip_address',
                'execution_certificate_url',
                'external_id',
            ]
        )
        changed_ids.append(signature.id)

    log_signature_packet_retry(
        user=request.user,
        contract=contract,
        organization=org,
        request_ids=changed_ids,
        request_count=len(changed_ids),
        request=request,
    )
    messages.success(request, f'Retried {len(changed_ids)} failed signature request(s).')
    return redirect(reverse('contracts:signature_packet_detail', kwargs={'contract_pk': contract.pk}))


class DataInventoryListView(TenantScopedQuerysetMixin, LoginRequiredMixin, ListView):
    model = DataInventoryRecord
    template_name = 'contracts/data_inventory_list.html'
    context_object_name = 'records'


class DataInventoryCreateView(TenantScopedFormMixin, TenantAssignCreateMixin, LoginRequiredMixin, CreateView):
    model = DataInventoryRecord
    form_class = DataInventoryForm
    template_name = 'contracts/data_inventory_form.html'
    success_url = reverse_lazy('contracts:data_inventory_list')
    scoped_form_fields = {'client': Client}

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class DataInventoryDetailView(TenantScopedQuerysetMixin, LoginRequiredMixin, DetailView):
    model = DataInventoryRecord
    template_name = 'contracts/data_inventory_detail.html'


class DataInventoryUpdateView(TenantScopedFormMixin, TenantScopedQuerysetMixin, LoginRequiredMixin, UpdateView):
    model = DataInventoryRecord
    form_class = DataInventoryForm
    template_name = 'contracts/data_inventory_form.html'
    success_url = reverse_lazy('contracts:data_inventory_list')
    scoped_form_fields = {'client': Client}


class DSARRequestListView(TenantScopedQuerysetMixin, LoginRequiredMixin, ListView):
    model = DSARRequest
    template_name = 'contracts/dsar_list.html'
    context_object_name = 'requests'

    def get_queryset(self):
        org = self.get_organization()
        qs = scope_queryset_for_organization(DSARRequest.objects.all(), org).order_by('-received_date')
        status = self.request.GET.get('status')
        rtype = self.request.GET.get('type')
        if status:
            qs = qs.filter(status=status)
        if rtype:
            qs = qs.filter(request_type=rtype)
        return qs


class DSARRequestCreateView(TenantScopedFormMixin, TenantAssignCreateMixin, LoginRequiredMixin, CreateView):
    model = DSARRequest
    form_class = DSARRequestForm
    template_name = 'contracts/dsar_form.html'
    success_url = reverse_lazy('contracts:dsar_list')
    scoped_form_fields = {'client': Client, 'assigned_to': _organization_user_queryset}

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class DSARRequestDetailView(TenantScopedQuerysetMixin, LoginRequiredMixin, DetailView):
    model = DSARRequest
    template_name = 'contracts/dsar_detail.html'


class DSARRequestUpdateView(TenantScopedFormMixin, TenantScopedQuerysetMixin, LoginRequiredMixin, UpdateView):
    model = DSARRequest
    form_class = DSARRequestForm
    template_name = 'contracts/dsar_form.html'
    success_url = reverse_lazy('contracts:dsar_list')
    scoped_form_fields = {'client': Client, 'assigned_to': _organization_user_queryset}


class SubprocessorListView(TenantScopedQuerysetMixin, LoginRequiredMixin, ListView):
    model = Subprocessor
    template_name = 'contracts/subprocessor_list.html'
    context_object_name = 'subprocessors'


class SubprocessorCreateView(TenantAssignCreateMixin, LoginRequiredMixin, CreateView):
    model = Subprocessor
    form_class = SubprocessorForm
    template_name = 'contracts/subprocessor_form.html'
    success_url = reverse_lazy('contracts:subprocessor_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class SubprocessorDetailView(TenantScopedQuerysetMixin, LoginRequiredMixin, DetailView):
    model = Subprocessor
    template_name = 'contracts/subprocessor_detail.html'


class SubprocessorUpdateView(TenantScopedQuerysetMixin, LoginRequiredMixin, UpdateView):
    model = Subprocessor
    form_class = SubprocessorForm
    template_name = 'contracts/subprocessor_form.html'
    success_url = reverse_lazy('contracts:subprocessor_list')


class TransferRecordListView(TenantScopedQuerysetMixin, LoginRequiredMixin, ListView):
    model = TransferRecord
    template_name = 'contracts/transfer_record_list.html'
    context_object_name = 'transfers'


class TransferRecordCreateView(TenantScopedFormMixin, TenantAssignCreateMixin, LoginRequiredMixin, CreateView):
    model = TransferRecord
    form_class = TransferRecordForm
    template_name = 'contracts/transfer_record_form.html'
    success_url = reverse_lazy('contracts:transfer_record_list')
    scoped_form_fields = {'subprocessor': Subprocessor, 'contract': Contract}

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class TransferRecordUpdateView(TenantScopedFormMixin, TenantScopedQuerysetMixin, LoginRequiredMixin, UpdateView):
    model = TransferRecord
    form_class = TransferRecordForm
    template_name = 'contracts/transfer_record_form.html'
    success_url = reverse_lazy('contracts:transfer_record_list')
    scoped_form_fields = {'subprocessor': Subprocessor, 'contract': Contract}


class RetentionPolicyListView(TenantScopedQuerysetMixin, LoginRequiredMixin, ListView):
    model = RetentionPolicy
    template_name = 'contracts/retention_policy_list.html'
    context_object_name = 'policies'


class RetentionPolicyCreateView(TenantAssignCreateMixin, LoginRequiredMixin, CreateView):
    model = RetentionPolicy
    form_class = RetentionPolicyForm
    template_name = 'contracts/retention_policy_form.html'
    success_url = reverse_lazy('contracts:retention_policy_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class RetentionPolicyUpdateView(TenantScopedQuerysetMixin, LoginRequiredMixin, UpdateView):
    model = RetentionPolicy
    form_class = RetentionPolicyForm
    template_name = 'contracts/retention_policy_form.html'
    success_url = reverse_lazy('contracts:retention_policy_list')


class LegalHoldListView(TenantScopedQuerysetMixin, LoginRequiredMixin, ListView):
    model = LegalHold
    template_name = 'contracts/legal_hold_list.html'
    context_object_name = 'holds'


class LegalHoldCreateView(TenantScopedFormMixin, TenantAssignCreateMixin, LoginRequiredMixin, CreateView):
    model = LegalHold
    form_class = LegalHoldForm
    template_name = 'contracts/legal_hold_form.html'
    success_url = reverse_lazy('contracts:legal_hold_list')
    scoped_form_fields = {
        'matter': Matter,
        'client': Client,
        'custodians': _organization_user_queryset,
    }

    def form_valid(self, form):
        form.instance.issued_by = self.request.user
        return super().form_valid(form)


class LegalHoldDetailView(TenantScopedQuerysetMixin, LoginRequiredMixin, DetailView):
    model = LegalHold
    template_name = 'contracts/legal_hold_detail.html'


class LegalHoldUpdateView(TenantScopedFormMixin, TenantScopedQuerysetMixin, LoginRequiredMixin, UpdateView):
    model = LegalHold
    form_class = LegalHoldForm
    template_name = 'contracts/legal_hold_form.html'
    success_url = reverse_lazy('contracts:legal_hold_list')
    scoped_form_fields = {
        'matter': Matter,
        'client': Client,
        'custodians': _organization_user_queryset,
    }


class ApprovalRuleListView(TenantScopedQuerysetMixin, LoginRequiredMixin, ListView):
    model = ApprovalRule
    template_name = 'contracts/approval_rule_list.html'
    context_object_name = 'rules'


class ApprovalRuleCreateView(TenantScopedFormMixin, TenantAssignCreateMixin, LoginRequiredMixin, CreateView):
    model = ApprovalRule
    form_class = ApprovalRuleForm
    template_name = 'contracts/approval_rule_form.html'
    success_url = reverse_lazy('contracts:approval_rule_list')
    scoped_form_fields = {'specific_approver': _organization_user_queryset}


class ApprovalRuleUpdateView(TenantScopedFormMixin, TenantScopedQuerysetMixin, LoginRequiredMixin, UpdateView):
    model = ApprovalRule
    form_class = ApprovalRuleForm
    template_name = 'contracts/approval_rule_form.html'
    success_url = reverse_lazy('contracts:approval_rule_list')
    scoped_form_fields = {'specific_approver': _organization_user_queryset}


class ApprovalRequestListView(TenantScopedQuerysetMixin, LoginRequiredMixin, ListView):
    model = ApprovalRequest
    template_name = 'contracts/approval_request_list.html'
    context_object_name = 'approvals'

    def get_queryset(self):
        org = self.get_organization()
        qs = scope_queryset_for_organization(
            ApprovalRequest.objects.select_related('contract', 'assigned_to', 'delegated_to').all(),
            org,
        ).order_by('-created_at')
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        """Approvals inbox: saved-view tabs backing the WorkQueue table.

        `approvals` (from context_object_name above) is left completely
        untouched — existing callers (incl. the cross-tenant isolation test)
        keep reading the plain org-scoped/optionally status-filtered
        queryset exactly as before. `queue_tabs` is additive.
        """
        context = super().get_context_data(**kwargs)
        context['queue_tabs'] = self._build_queue_tabs()
        return context

    def _build_queue_tabs(self):
        from django.urls import reverse

        from contracts.services.approval_workflow import actor_can_decide
        from contracts.services.queue_rows import latest_activity_map
        from contracts.templatetags.docclad_format import (
            approval_status_badge_class,
            approval_status_badge_tone,
            approval_step_label,
            money,
        )

        org = self.get_organization()
        user = self.request.user
        now = timezone.now()

        if not org:
            empty_tabs = [
                ('waiting_on_me', 'Waiting on Me', 'No approvals waiting on you.'),
                ('requested_by_me', 'Requested by Me', 'No approvals requested by you.'),
                ('all_open', 'All Open', 'No open approvals.'),
                ('approved', 'Approved', 'No approved approvals yet.'),
                ('rejected', 'Rejected', 'No rejected approvals.'),
                ('escalated_overdue', 'Escalated / Overdue', 'Nothing escalated or overdue.'),
            ]
            return [{'key': k, 'label': label, 'rows': [], 'empty_message': msg} for k, label, msg in empty_tabs]

        base_qs = scope_queryset_for_organization(
            ApprovalRequest.objects.select_related(
                'contract', 'contract__created_by', 'assigned_to', 'delegated_to',
            ),
            org,
        )

        def _to_rows(qs, limit=25):
            items = list(qs.order_by('-created_at')[:limit])
            ids = [a.pk for a in items]
            activity_map = latest_activity_map(org, ids, model_name='ApprovalRequest')
            rows = []
            for approval in items:
                contract = approval.contract
                effective_assignee = approval.delegated_to or approval.assigned_to
                due = approval.due_date
                overdue = bool(due and due < now and approval.status in ('PENDING', 'ESCALATED'))
                meta_parts = [p for p in (
                    contract.counterparty if contract and contract.counterparty else None,
                    approval_step_label(approval.approval_step),
                ) if p]
                if contract and contract.value:
                    meta_parts.append(money(contract.value, contract.currency))
                rows.append({
                    'id': approval.pk,
                    'title': contract.title if contract else f'Approval #{approval.pk}',
                    'href': reverse('contracts:contract_detail', kwargs={'pk': contract.pk}) if contract else '',
                    'meta': ' · '.join(meta_parts),
                    'contract': contract,
                    'requester': contract.created_by if contract else None,
                    'assignee': effective_assignee,
                    'activity': activity_map.get(approval.pk),
                    'due_date': due,
                    'due_overdue': overdue,
                    'status_label': approval.get_status_display(),
                    'status_badge_class': approval_status_badge_class(approval.status),
                    'status_badge_tone': approval_status_badge_tone(approval.status),
                    # actor_can_decide() checks authorization only; a decision on an
                    # already-APPROVED/REJECTED row would still be rejected by the
                    # API's own status guard (ApprovalWorkflowService._decide), but
                    # showing live-looking buttons that can only ever fail reads as a
                    # fake control. Gate the UI on the same PENDING/ESCALATED
                    # condition the API enforces, so a button only appears when the
                    # action can actually succeed.
                    'can_decide': (
                        approval.status in ('PENDING', 'ESCALATED')
                        and actor_can_decide(approval, user, 'approve')
                    ),
                    'approve_url': reverse('contracts:approval_approve_api', kwargs={'approval_id': approval.pk}),
                    'reject_url': reverse('contracts:approval_reject_api', kwargs={'approval_id': approval.pk}),
                    'edit_url': reverse('contracts:approval_request_update', kwargs={'pk': approval.pk}),
                })
            return rows

        waiting_qs = base_qs.filter(
            Q(assigned_to=user) | Q(delegated_to=user), status__in=['PENDING', 'ESCALATED'],
        )
        requested_qs = base_qs.filter(contract__created_by=user)
        all_open_qs = base_qs.filter(status__in=['PENDING', 'ESCALATED'])
        approved_qs = base_qs.filter(status='APPROVED')
        rejected_qs = base_qs.filter(status='REJECTED')
        escalated_overdue_qs = base_qs.filter(Q(status='ESCALATED') | Q(status='PENDING', due_date__lt=now))

        return [
            {'key': 'waiting_on_me', 'label': 'Waiting on Me', 'rows': _to_rows(waiting_qs),
             'empty_message': 'No approvals waiting on you.'},
            {'key': 'requested_by_me', 'label': 'Requested by Me', 'rows': _to_rows(requested_qs),
             'empty_message': 'No approvals requested by you.'},
            {'key': 'all_open', 'label': 'All Open', 'rows': _to_rows(all_open_qs),
             'empty_message': 'No open approvals.'},
            {'key': 'approved', 'label': 'Approved', 'rows': _to_rows(approved_qs),
             'empty_message': 'No approved approvals yet.'},
            {'key': 'rejected', 'label': 'Rejected', 'rows': _to_rows(rejected_qs),
             'empty_message': 'No rejected approvals.'},
            {'key': 'escalated_overdue', 'label': 'Escalated / Overdue', 'rows': _to_rows(escalated_overdue_qs),
             'empty_message': 'Nothing escalated or overdue.'},
        ]


class ApprovalRequestCreateView(TenantScopedFormMixin, TenantAssignCreateMixin, LoginRequiredMixin, CreateView):
    model = ApprovalRequest
    form_class = ApprovalRequestForm
    template_name = 'contracts/approval_request_form.html'
    success_url = reverse_lazy('contracts:approval_request_list')
    scoped_form_fields = {
        'contract': Contract,
        'assigned_to': _organization_user_queryset,
        'delegated_to': _organization_user_queryset,
    }


class ApprovalRequestUpdateView(TenantScopedFormMixin, TenantScopedQuerysetMixin, LoginRequiredMixin, UpdateView):
    model = ApprovalRequest
    form_class = ApprovalRequestForm
    template_name = 'contracts/approval_request_form.html'
    success_url = reverse_lazy('contracts:approval_request_list')
    scoped_form_fields = {
        'contract': Contract,
        'assigned_to': _organization_user_queryset,
        'delegated_to': _organization_user_queryset,
    }

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['actor'] = self.request.user
        return kwargs

    def form_valid(self, form):
        # Approve/reject/delegate decisions are routed through the approval
        # service so the HTML path enforces the exact same authorization
        # (incl. segregation of duties) as the API — blocker A5. Plain field
        # edits (comments/due_date/PENDING reset) keep the normal save path.
        from contracts.services.approval_workflow import (
            ApprovalAccessDenied,
            get_approval_workflow_service,
        )

        svc = get_approval_workflow_service()
        ar = self.object
        new_status = form.cleaned_data.get('status')
        delegated_to = form.cleaned_data.get('delegated_to')
        comments = form.cleaned_data.get('comments') or ''
        # NB: form.is_valid() has already copied POST data onto self.object, so
        # ar.status reflects the *submitted* value. Read the PERSISTED status and
        # assignee from the DB to detect what actually changed.
        persisted = (
            type(ar).objects
            .filter(pk=ar.pk)
            .values('status', 'assigned_to_id')
            .first()
            or {}
        )
        original_status = persisted.get('status')
        previous_assignee_id = persisted.get('assigned_to_id')

        decision_made = False
        try:
            if delegated_to and delegated_to.id != previous_assignee_id:
                svc.delegate(ar.pk, delegated_to, self.request.user)
                decision_made = True
            if new_status == ApprovalRequest.Status.APPROVED and original_status != ApprovalRequest.Status.APPROVED:
                svc.approve(ar.pk, self.request.user, comments)
                decision_made = True
            elif new_status == ApprovalRequest.Status.REJECTED and original_status != ApprovalRequest.Status.REJECTED:
                svc.reject(ar.pk, self.request.user, comments)
                decision_made = True
        except ApprovalAccessDenied as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)
        except ValueError as exc:
            form.add_error('status', str(exc))
            return self.form_invalid(form)

        if decision_made:
            messages.success(self.request, 'Approval updated.')
            return redirect(self.get_success_url())

        # No decision was made — persist plain field edits normally.
        if new_status == ApprovalRequest.Status.PENDING:
            form.instance.decided_at = None
            form.instance.decided_by = None
        return super().form_valid(form)


@login_required
def privacy_dashboard(request):
    data_inventory_qs = get_scoped_queryset_for_request(request, DataInventoryRecord)
    dsar_qs = get_scoped_queryset_for_request(request, DSARRequest)
    transfer_qs = get_scoped_queryset_for_request(request, TransferRecord)
    subprocessor_qs = get_scoped_queryset_for_request(request, Subprocessor)
    retention_qs = get_scoped_queryset_for_request(request, RetentionPolicy)
    legal_hold_qs = get_scoped_queryset_for_request(request, LegalHold)
    ethical_wall_qs = get_scoped_queryset_for_request(request, EthicalWall)

    data_inventory_count = data_inventory_qs.count()
    dsar_pending = dsar_qs.filter(status__in=['RECEIVED', 'VERIFIED', 'IN_PROGRESS']).count()
    dsar_overdue = dsar_qs.filter(
        status__in=['RECEIVED', 'VERIFIED', 'IN_PROGRESS'],
        due_date__lt=date.today(),
    ).count()
    subprocessor_count = subprocessor_qs.filter(is_active=True).count()
    transfer_count = transfer_qs.filter(is_active=True).count()
    retention_count = retention_qs.filter(is_active=True).count()
    legal_hold_count = legal_hold_qs.filter(status='ACTIVE').count()
    ethical_wall_count = ethical_wall_qs.filter(is_active=True).count()
    recent_dsars = dsar_qs.order_by('-received_date')[:5]
    context = {
        'data_inventory_count': data_inventory_count,
        'dsar_pending': dsar_pending,
        'dsar_overdue': dsar_overdue,
        'subprocessor_count': subprocessor_count,
        'transfer_count': transfer_count,
        'retention_count': retention_count,
        'legal_hold_count': legal_hold_count,
        'ethical_wall_count': ethical_wall_count,
        'recent_dsars': recent_dsars,
    }
    return render(request, 'contracts/privacy_dashboard.html', context)


@login_required
def privacy_evidence_export(request):
    org = get_user_organization(request.user)
    if org is None:
        return HttpResponseForbidden('No active organization found.')
    if not can_manage_organization(request.user, org):
        return HttpResponseForbidden('Only organization owners/admins can export privacy evidence.')

    data_inventory_qs = get_scoped_queryset_for_request(request, DataInventoryRecord)
    dsar_qs = get_scoped_queryset_for_request(request, DSARRequest)
    transfer_qs = get_scoped_queryset_for_request(request, TransferRecord)
    subprocessor_qs = get_scoped_queryset_for_request(request, Subprocessor)
    retention_qs = get_scoped_queryset_for_request(request, RetentionPolicy)
    legal_hold_qs = get_scoped_queryset_for_request(request, LegalHold)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="privacy-evidence-{org.slug}-{date.today().isoformat()}.csv"'
    writer = csv.writer(response)
    writer.writerow(['category', 'metric', 'value'])
    writer.writerow(['summary', 'data_inventory_count', data_inventory_qs.count()])
    writer.writerow(['summary', 'dsar_pending', dsar_qs.filter(status__in=['RECEIVED', 'VERIFIED', 'IN_PROGRESS']).count()])
    writer.writerow(['summary', 'dsar_overdue', dsar_qs.filter(status__in=['RECEIVED', 'VERIFIED', 'IN_PROGRESS'], due_date__lt=date.today()).count()])
    writer.writerow(['summary', 'subprocessor_count', subprocessor_qs.filter(is_active=True).count()])
    writer.writerow(['summary', 'transfer_count', transfer_qs.filter(is_active=True).count()])
    writer.writerow(['summary', 'retention_count', retention_qs.filter(is_active=True).count()])
    writer.writerow(['summary', 'legal_hold_count', legal_hold_qs.filter(status='ACTIVE').count()])
    for log in AuditLog.objects.filter(changes__organization_id=org.id).order_by('-timestamp')[:20]:
        writer.writerow(['audit_log', log.timestamp.isoformat(), f'{log.model_name}:{log.action}:{(log.changes or {}).get("event", "")}'])
    return response


@login_required
def ai_data_controls(request):
    org = get_user_organization(request.user)
    if org is None:
        return HttpResponseForbidden('No active organization found.')
    policy, _ = OrgPolicy.objects.get_or_create(organization=org)
    can_manage = can_manage_organization(request.user, org)
    if request.method == 'POST':
        if not can_manage:
            return HttpResponseForbidden('Only administrators can modify AI data controls.')
        policy.ai_features_enabled = request.POST.get('ai_features_enabled') == '1'
        policy.updated_by = request.user
        policy.save(update_fields=['ai_features_enabled', 'updated_by', 'updated_at'])
        messages.success(request, 'AI data controls updated.')
        return redirect('contracts:ai_data_controls')
    return render(request, 'contracts/ai_data_controls.html', {
        'policy': policy,
        'can_manage': can_manage,
    })
