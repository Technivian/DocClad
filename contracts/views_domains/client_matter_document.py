from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Case, Count, IntegerField, Q, Sum, When
from django.http import Http404, HttpResponseForbidden, HttpResponseRedirect
from django.urls import reverse, reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from contracts.forms import ClientForm, DocumentForm, DocumentOCRReviewForm, MatterForm
from contracts.middleware import log_action
from contracts.models import (
    ApprovalRequest,
    AuditLog,
    Client,
    Contract,
    Document,
    DocumentOCRReview,
    DPARiskItem,
    Matter,
    RiskLog,
)
from contracts.permissions import ContractAction, can_access_contract_action
from contracts.tenancy import get_user_organization, scope_queryset_for_organization, set_organization_on_instance
from contracts.view_support import (
    TenantAssignCreateMixin,
    TenantScopedFormMixin,
    TenantScopedQuerysetMixin,
    organization_user_queryset,
)
from contracts.services.document_versions import compare_document_versions
from contracts.services.document_ocr import queue_document_ocr_review


class ClientListView(TenantScopedQuerysetMixin, LoginRequiredMixin, ListView):
    model = Client
    template_name = 'contracts/client_list.html'
    context_object_name = 'clients'
    paginate_by = 25

    def get_queryset(self):
        org = get_user_organization(self.request.user)
        qs = scope_queryset_for_organization(Client.objects.all(), org)
        q = self.request.GET.get('q')
        status = self.request.GET.get('status')
        client_type = self.request.GET.get('type')
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(email__icontains=q) | Q(industry__icontains=q))
        if status:
            qs = qs.filter(status=status)
        if client_type:
            qs = qs.filter(client_type=client_type)
        return qs.order_by('-created_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        org = get_user_organization(self.request.user)
        tenant_clients = scope_queryset_for_organization(Client.objects.all(), org)
        client_stats = tenant_clients.aggregate(
            total=Count('id'),
            active=Count('id', filter=Q(status='ACTIVE')),
        )
        ctx['total_clients'] = client_stats['total']
        ctx['active_clients'] = client_stats['active']
        ctx['search_query'] = self.request.GET.get('q', '')
        return ctx


class ClientDetailView(TenantScopedQuerysetMixin, LoginRequiredMixin, DetailView):
    model = Client
    template_name = 'contracts/client_detail.html'
    context_object_name = 'client'

    def get_queryset(self):
        org = get_user_organization(self.request.user)
        return scope_queryset_for_organization(Client.objects.all(), org)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['matters'] = self.object.matters.all()[:10]
        ctx['contracts'] = self.object.contracts.all()[:10]
        ctx['invoices'] = self.object.invoices.all()[:10]
        ctx['documents'] = self.object.documents.all()[:10]
        return ctx


class ClientCreateView(TenantScopedFormMixin, TenantAssignCreateMixin, LoginRequiredMixin, CreateView):
    model = Client
    form_class = ClientForm
    template_name = 'contracts/client_form.html'
    success_url = reverse_lazy('contracts:client_list')
    scoped_form_fields = {
        'responsible_attorney': organization_user_queryset,
        'originating_attorney': organization_user_queryset,
    }

    def form_valid(self, form):
        set_organization_on_instance(form.instance, get_user_organization(self.request.user))
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        log_action(self.request.user, 'CREATE', 'Client', self.object.id, str(self.object), request=self.request)
        messages.success(self.request, f'Client "{self.object.name}" created successfully.')
        return response


class ClientUpdateView(TenantScopedFormMixin, TenantScopedQuerysetMixin, LoginRequiredMixin, UpdateView):
    model = Client
    form_class = ClientForm
    template_name = 'contracts/client_form.html'
    success_url = reverse_lazy('contracts:client_list')
    scoped_form_fields = {
        'responsible_attorney': organization_user_queryset,
        'originating_attorney': organization_user_queryset,
    }

    def get_queryset(self):
        org = get_user_organization(self.request.user)
        return scope_queryset_for_organization(Client.objects.all(), org)

    def form_valid(self, form):
        response = super().form_valid(form)
        log_action(self.request.user, 'UPDATE', 'Client', self.object.id, str(self.object), request=self.request)
        messages.success(self.request, f'Client "{self.object.name}" updated successfully.')
        return response


class MatterListView(TenantScopedQuerysetMixin, LoginRequiredMixin, ListView):
    model = Matter
    template_name = 'contracts/matter_list.html'
    context_object_name = 'matters'
    paginate_by = 25

    def get_queryset(self):
        org = self.get_organization()
        qs = scope_queryset_for_organization(Matter.objects.select_related('client', 'responsible_attorney'), org)
        q = self.request.GET.get('q')
        status = self.request.GET.get('status')
        practice_area = self.request.GET.get('practice_area')
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(matter_number__icontains=q) | Q(client__name__icontains=q))
        if status:
            qs = qs.filter(status=status)
        if practice_area:
            qs = qs.filter(practice_area=practice_area)
        return qs.order_by('-created_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        org = self.get_organization()
        tenant_matters = scope_queryset_for_organization(Matter.objects.all(), org)
        matter_stats = tenant_matters.aggregate(
            total=Count('id'),
            active=Count('id', filter=Q(status='ACTIVE')),
        )
        ctx['total_matters'] = matter_stats['total']
        ctx['active_matters'] = matter_stats['active']
        ctx['search_query'] = self.request.GET.get('q', '')
        return ctx


class MatterDetailView(TenantScopedQuerysetMixin, LoginRequiredMixin, DetailView):
    model = Matter
    template_name = 'contracts/matter_detail.html'
    context_object_name = 'matter'

    def get_queryset(self):
        org = self.get_organization()
        return scope_queryset_for_organization(Matter.objects.all(), org)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        matter = self.object
        org = self.get_organization()
        workspace_mode = getattr(org, 'workspace_mode', 'law_firm_ops') if org else 'law_firm_ops'
        is_in_house_clm = workspace_mode == 'in_house_clm'
        ctx['is_in_house_clm'] = is_in_house_clm

        ctx['contracts'] = matter.contracts.all().order_by('-updated_at')
        ctx['documents'] = matter.documents.filter(is_deleted=False).order_by('-created_at')[:10]
        ctx['time_entries'] = matter.time_entries.all()[:10]
        ctx['tasks'] = matter.tasks.all()[:10]
        ctx['deadlines'] = matter.deadlines.filter(is_completed=False).order_by('due_date')[:10]
        ctx['risks'] = matter.risks.all()[:10]

        if not is_in_house_clm:
            return ctx

        # ── Matter Workspace Spine (Phase 3) — in_house_clm only ────────
        # Every figure below reads PERSISTED rows already attached to this
        # matter (Contract/DPAReviewPack/DPARiskItem/RiskLog/Deadline/
        # ApprovalRequest). Nothing here triggers DPA analysis, obligation
        # extraction, or any AI call — that only happens from the DPA
        # Review Pack's explicit "Run Analysis" action, unchanged here.
        # All querysets below are reached through `matter`, which is
        # already tenant-scoped by get_queryset(), so every row is
        # implicitly organization-scoped through its FK chain to matter.
        severity_rank = Case(
            When(severity='CRITICAL', then=0),
            When(severity='HIGH', then=1),
            When(severity='MEDIUM', then=2),
            When(severity='LOW', then=3),
            default=4, output_field=IntegerField(),
        )
        risk_level_rank = Case(
            When(risk_level='CRITICAL', then=0),
            When(risk_level='HIGH', then=1),
            When(risk_level='MEDIUM', then=2),
            When(risk_level='LOW', then=3),
            default=4, output_field=IntegerField(),
        )

        clm_contracts = list(
            matter.contracts.all()
            .prefetch_related('approval_requests', 'dpa_review_packs')
            .order_by('-updated_at')
        )
        for contract in clm_contracts:
            contract.clm_pending_approval_count = sum(
                1 for a in contract.approval_requests.all() if a.status == ApprovalRequest.Status.PENDING
            )
            contract.clm_dpa_pack = next(iter(contract.dpa_review_packs.all()), None)
        ctx['clm_contracts'] = clm_contracts

        dpa_packs = list(
            matter.dpa_review_packs
            .select_related('contract', 'counterparty')
            .prefetch_related('risk_items')
            .order_by('-updated_at')
        )
        for pack in dpa_packs:
            items = list(pack.risk_items.all())
            pack.clm_high_risk_count = sum(
                1 for i in items
                if i.severity in ('HIGH', 'CRITICAL') and i.status not in ('RESOLVED', 'FALSE_POSITIVE')
            )
            pack.clm_conflict_count = sum(
                1 for i in items
                if i.is_cross_document_conflict and i.status not in ('RESOLVED', 'FALSE_POSITIVE')
            )
        ctx['clm_dpa_packs'] = dpa_packs
        ctx['clm_memos'] = sorted(
            (pack for pack in dpa_packs if pack.review_memo_generated_at),
            key=lambda pack: pack.review_memo_generated_at, reverse=True,
        )

        risk_log_items = list(
            matter.risks
            .exclude(status=RiskLog.Status.RESOLVED)
            .select_related('assigned_to')
            .annotate(severity_rank=risk_level_rank)
            .order_by('severity_rank', '-created_at')
        )
        dpa_risk_items = list(
            DPARiskItem.objects
            .filter(review_pack__matter=matter)
            .exclude(status__in=['RESOLVED', 'FALSE_POSITIVE'])
            .select_related('review_pack', 'review_pack__contract')
            .annotate(severity_rank=severity_rank)
            .order_by('severity_rank', '-created_at')
        )
        _severity_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
        combined_risks = [
            {
                'source': 'Contract Risk',
                'title': r.title or (r.description[:80] if r.description else 'Risk'),
                'severity': r.risk_level,
                'severity_display': r.get_risk_level_display(),
                'owner': r.assigned_to,
                'status_display': r.get_status_display(),
                'detail_url': reverse('contracts:risk_log_update', kwargs={'pk': r.pk}),
            }
            for r in risk_log_items
        ] + [
            {
                'source': 'DPA Risk',
                'title': i.title,
                'severity': i.severity,
                'severity_display': i.get_severity_display(),
                'owner': None,
                'status_display': i.get_status_display(),
                'detail_url': reverse('contracts:dpa_review_pack_detail', kwargs={'pk': i.review_pack_id}),
            }
            for i in dpa_risk_items
        ]
        combined_risks.sort(key=lambda entry: _severity_order.get(entry['severity'], 4))
        ctx['clm_risks'] = combined_risks
        ctx['clm_open_risk_count'] = len(combined_risks)

        clm_approvals = list(
            ApprovalRequest.objects
            .filter(contract__matter=matter)
            .exclude(status__in=[ApprovalRequest.Status.APPROVED, ApprovalRequest.Status.REJECTED])
            .select_related('contract', 'assigned_to')
            .order_by('due_date')
        )
        ctx['clm_approvals'] = clm_approvals[:10]
        ctx['clm_open_approval_count'] = len(clm_approvals)

        ctx['clm_upcoming_deadline_count'] = matter.deadlines.filter(is_completed=False).count()

        return ctx


class MatterCreateView(TenantScopedFormMixin, TenantAssignCreateMixin, LoginRequiredMixin, CreateView):
    model = Matter
    form_class = MatterForm
    template_name = 'contracts/matter_form.html'
    scoped_form_fields = {
        'client': Client,
        'responsible_attorney': organization_user_queryset,
        'originating_attorney': organization_user_queryset,
    }

    def get_success_url(self):
        return reverse('contracts:matter_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        set_organization_on_instance(form.instance, get_user_organization(self.request.user))
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        log_action(self.request.user, 'CREATE', 'Matter', self.object.id, str(self.object), request=self.request)
        messages.success(self.request, f'Matter "{self.object.title}" created.')
        return response


class MatterUpdateView(TenantScopedFormMixin, TenantScopedQuerysetMixin, LoginRequiredMixin, UpdateView):
    model = Matter
    form_class = MatterForm
    template_name = 'contracts/matter_form.html'
    scoped_form_fields = {
        'client': Client,
        'responsible_attorney': organization_user_queryset,
        'originating_attorney': organization_user_queryset,
    }

    def get_success_url(self):
        return reverse('contracts:matter_detail', kwargs={'pk': self.object.pk})

    def get_queryset(self):
        org = self.get_organization()
        return scope_queryset_for_organization(Matter.objects.all(), org)

    def form_valid(self, form):
        response = super().form_valid(form)
        log_action(self.request.user, 'UPDATE', 'Matter', self.object.id, str(self.object), request=self.request)
        messages.success(self.request, f'Matter "{self.object.title}" updated.')
        return response


class DocumentListView(TenantScopedQuerysetMixin, LoginRequiredMixin, ListView):
    model = Document
    template_name = 'contracts/document_list.html'
    context_object_name = 'documents'
    paginate_by = 25

    def get_queryset(self):
        org = self.get_organization()
        qs = scope_queryset_for_organization(
            Document.objects.select_related('contract', 'matter', 'client', 'uploaded_by'),
            org,
        ).filter(is_deleted=False)  # soft-deleted documents are hidden from listings
        q = self.request.GET.get('q')
        doc_type = self.request.GET.get('type')
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(tags__icontains=q))
        if doc_type:
            qs = qs.filter(document_type=doc_type)
        return qs.order_by('-created_at')


class DocumentDetailView(TenantScopedQuerysetMixin, LoginRequiredMixin, DetailView):
    model = Document
    template_name = 'contracts/document_detail.html'
    context_object_name = 'document'

    def get_queryset(self):
        org = self.get_organization()
        return scope_queryset_for_organization(Document.objects.all(), org).filter(is_deleted=False)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ancestor_chain = []
        current_document = self.object
        while current_document.parent_document_id:
            current_document = current_document.parent_document
            ancestor_chain.append(current_document)
        ctx['version_chain'] = list(reversed(ancestor_chain))
        ctx['versions'] = Document.objects.filter(parent_document=self.object).order_by('-version')
        return ctx


class DocumentCompareView(TenantScopedQuerysetMixin, LoginRequiredMixin, DetailView):
    model = Document
    template_name = 'contracts/document_compare.html'
    context_object_name = 'document'

    def get_queryset(self):
        org = self.get_organization()
        return scope_queryset_for_organization(Document.objects.all(), org).filter(is_deleted=False)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        other_document = get_object_or_404(
            scope_queryset_for_organization(Document.objects.all(), self.get_organization()),
            pk=self.kwargs['other_pk'],
        )
        context['other_document'] = other_document
        context['comparison'] = compare_document_versions(self.object, other_document)
        return context


class DocumentCreateView(TenantScopedFormMixin, TenantAssignCreateMixin, LoginRequiredMixin, CreateView):
    model = Document
    form_class = DocumentForm
    template_name = 'contracts/document_form.html'
    success_url = reverse_lazy('contracts:document_list')
    scoped_form_fields = {'contract': Contract, 'matter': Matter, 'client': Client}

    def form_valid(self, form):
        set_organization_on_instance(form.instance, get_user_organization(self.request.user))
        if form.instance.contract and not can_access_contract_action(self.request.user, form.instance.contract, ContractAction.EDIT):
            return HttpResponseForbidden('You do not have permission to upload documents for this contract.')
        from contracts.services.document_version_service import create_document_version

        staged = form.save(commit=False)
        organization = get_user_organization(self.request.user)
        document, _version = create_document_version(
            organization=organization,
            title=staged.title,
            document_type=staged.document_type,
            status=staged.status,
            description=staged.description,
            file=staged.file,
            contract=staged.contract,
            matter=staged.matter,
            client=staged.client,
            uploaded_by=self.request.user,
            actor=self.request.user,
            source='manual_upload',
            tags=staged.tags,
            is_privileged=staged.is_privileged,
            is_confidential=staged.is_confidential,
            share_with_counterparty=staged.share_with_counterparty,
            request=self.request,
            supersede_prior=False,
        )
        self.object = document
        queue_document_ocr_review(self.object)
        messages.success(self.request, f'Document "{self.object.title}" uploaded.')
        return redirect(self.get_success_url())


class DocumentUpdateView(TenantScopedFormMixin, TenantScopedQuerysetMixin, LoginRequiredMixin, UpdateView):
    model = Document
    form_class = DocumentForm
    template_name = 'contracts/document_form.html'
    success_url = reverse_lazy('contracts:document_list')
    scoped_form_fields = {'contract': Contract, 'matter': Matter, 'client': Client}

    def get_queryset(self):
        org = self.get_organization()
        return scope_queryset_for_organization(Document.objects.all(), org)

    def dispatch(self, request, *args, **kwargs):
        document = self.get_object()
        self.original_document = document
        if document.contract and not can_access_contract_action(request.user, document.contract, ContractAction.EDIT):
            return HttpResponseForbidden('You do not have permission to edit documents for this contract.')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        original_document = getattr(self, 'original_document', None) or self.get_object()
        staged_document = form.save(commit=False)
        from contracts.services.document_version_service import create_document_version

        document, _version = create_document_version(
            organization=original_document.organization,
            title=staged_document.title,
            document_type=staged_document.document_type,
            status=staged_document.status,
            description=staged_document.description,
            file=staged_document.file,
            contract=staged_document.contract,
            matter=staged_document.matter,
            client=staged_document.client,
            uploaded_by=self.request.user,
            actor=self.request.user,
            source='document_edit',
            derived_from_document=original_document,
            parent_document=original_document,
            tags=staged_document.tags,
            is_privileged=staged_document.is_privileged,
            is_confidential=staged_document.is_confidential,
            request=self.request,
            supersede_prior=True,
        )
        self.object = document
        queue_document_ocr_review(self.object)
        messages.success(self.request, f'Document "{self.object.title}" updated as version {self.object.version}.')
        return redirect('contracts:document_detail', pk=self.object.pk)


class DocumentDeleteView(TenantScopedQuerysetMixin, LoginRequiredMixin, DeleteView):
    model = Document
    template_name = 'contracts/document_confirm_delete.html'
    success_url = reverse_lazy('contracts:document_list')

    def get_queryset(self):
        org = get_user_organization(self.request.user)
        return scope_queryset_for_organization(Document.objects.all(), org)

    def form_valid(self, form):
        # Authorization + retention + soft-delete + chained audit all live in the
        # canonical deletion service (Phase 4E). The DeleteView is tenant-scoped
        # via get_queryset, so this can only target the user's own org.
        from contracts.services.document_deletion import (
            DocumentDeletionError,
            soft_delete_document,
        )
        document = self.get_object()
        doc_title = document.title
        try:
            soft_delete_document(self.request.user, document, request=self.request)
        except DocumentDeletionError as exc:
            messages.error(self.request, str(exc))
            return redirect('contracts:document_detail', pk=document.pk)
        messages.success(self.request, f'Document "{doc_title}" deleted.')
        return HttpResponseRedirect(self.get_success_url())


@login_required
def document_download(request, pk):
    """Authenticated, tenant-safe, audited document download (A6).

    CLM One authorizes here and then redirects to a short-lived signed URL
    (private object storage) rather than exposing object URLs directly. Enforces
    tenant access, document permission, and (soft-)deletion state, and records a
    download/blocked audit event without storing the URL or file contents.
    """
    org = get_user_organization(request.user)
    if org is None:
        raise Http404

    # Cross-tenant attempts: detect a foreign document to audit the block, but
    # never reveal it (still 404). The blocked event is filed on the ACTOR's org.
    scoped = scope_queryset_for_organization(Document.objects.all(), org)
    document = scoped.filter(pk=pk).first()
    if document is None:
        if Document.objects.filter(pk=pk).exists():
            log_action(
                request.user, AuditLog.Action.VIEW, 'Document',
                object_id=None, object_repr='cross-tenant document access blocked',
                organization=org, event_type='document.access_blocked', outcome='blocked',
                changes={'event': 'document.access_blocked', 'attempted_document_id': pk},
                request=request,
            )
        raise Http404

    # Document permission: VIEW on the linked contract where present.
    if document.contract_id and not can_access_contract_action(
        request.user, document.contract, ContractAction.VIEW
    ):
        return HttpResponseForbidden('You do not have permission to access this document.')

    # Deletion/retention state (soft-delete added in 4E; defensive until then).
    if getattr(document, 'is_deleted', False):
        raise Http404

    if not document.file:
        raise Http404

    log_action(
        request.user, AuditLog.Action.VIEW, 'Document',
        object_id=document.pk, object_repr=document.title[:300],
        organization=org, event_type='document.downloaded',
        changes={'event': 'document.downloaded', 'document_id': document.pk,
                 'contract_id': document.contract_id},
        request=request,
    )
    # Redirect to the storage URL: a signed, expiring URL under S3; the dev
    # media handler under filesystem. We never persist the URL.
    try:
        return redirect(document.file.url)
    except Exception:
        # Object missing/unavailable — fail safe without leaking backend detail.
        raise Http404


class DocumentOCRQueueView(TenantScopedQuerysetMixin, LoginRequiredMixin, ListView):
    model = DocumentOCRReview
    template_name = 'contracts/document_ocr_queue.html'
    context_object_name = 'reviews'
    paginate_by = 25

    def get_queryset(self):
        org = self.get_organization()
        qs = scope_queryset_for_organization(
            DocumentOCRReview.objects.select_related('document', 'reviewed_by'),
            org,
        )
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs.order_by('-created_at')


class DocumentOCRReviewUpdateView(TenantScopedQuerysetMixin, LoginRequiredMixin, UpdateView):
    model = DocumentOCRReview
    form_class = DocumentOCRReviewForm
    template_name = 'contracts/document_ocr_review.html'

    def get_queryset(self):
        org = self.get_organization()
        return scope_queryset_for_organization(
            DocumentOCRReview.objects.select_related('document', 'reviewed_by'),
            org,
        )

    def form_valid(self, form):
        review = form.save(commit=False)
        review.organization = self.get_organization()
        review.reviewed_by = self.request.user
        review.reviewed_at = timezone.now()
        if review.status == DocumentOCRReview.Status.VERIFIED:
            review.mark_verified(self.request.user)
        elif review.status == DocumentOCRReview.Status.REJECTED:
            review.mark_rejected(self.request.user)
        review.save()
        messages.success(self.request, f'OCR review for "{review.document.title}" updated.')
        return redirect('contracts:document_ocr_queue')
