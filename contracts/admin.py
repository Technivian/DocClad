from datetime import timedelta

from django.contrib import admin
from django.utils import timezone

from .models import (
    Organization, OrganizationMembership, OrganizationInvitation, Deadline,
    TrademarkRequest, LegalTask, RiskLog, ComplianceChecklist,
    Workflow, WorkflowTemplate, WorkflowTemplateStep, WorkflowStep, ChecklistItem,
    DueDiligenceProcess, DueDiligenceTask, DueDiligenceRisk, Budget, BudgetExpense, Contract,
    ContractTemplate, ContractType,
    Counterparty, ClauseCategory, ClauseTemplate, SignatureRequest, DataInventoryRecord,
    DSARRequest, Subprocessor, TransferRecord, RetentionPolicy, LegalHold,
    ApprovalRule, ApprovalRequest, EthicalWall, SalesforceOrganizationConnection,
    OrganizationContractFieldMap, SalesforceSyncRun, WebhookEndpoint, WebhookDelivery,
    CommandCenterSavedView, CommandCenterWorkItem, CommandCenterRailItem, ReviewMemo,
    ExceptionRequest, ExceptionDecision,
)


class ExpiringContractFilter(admin.SimpleListFilter):
    title = 'contract health'
    parameter_name = 'contract_health'

    def lookups(self, request, model_admin):
        return (
            ('expiring_30', 'Expiring in 30 days'),
            ('expired', 'Expired'),
        )

    def queryset(self, request, queryset):
        today = timezone.localdate()
        if self.value() == 'expiring_30':
            return queryset.filter(status='ACTIVE', end_date__gte=today, end_date__lte=today + timedelta(days=30))
        if self.value() == 'expired':
            return queryset.filter(end_date__lt=today)
        return queryset


class OverdueApprovalFilter(admin.SimpleListFilter):
    title = 'approval health'
    parameter_name = 'approval_health'

    def lookups(self, request, model_admin):
        return (
            ('pending', 'Pending'),
            ('overdue', 'Overdue'),
        )

    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == 'pending':
            return queryset.filter(status='PENDING')
        if self.value() == 'overdue':
            return queryset.filter(status='PENDING', due_date__lt=now)
        return queryset


class OverdueDSARFilter(admin.SimpleListFilter):
    title = 'dsar health'
    parameter_name = 'dsar_health'

    def lookups(self, request, model_admin):
        return (
            ('open', 'Open'),
            ('overdue', 'Overdue'),
        )

    def queryset(self, request, queryset):
        today = timezone.localdate()
        if self.value() == 'open':
            return queryset.exclude(status__in=['COMPLETED', 'DENIED'])
        if self.value() == 'overdue':
            return queryset.exclude(status__in=['COMPLETED', 'DENIED']).filter(due_date__lt=today)
        return queryset


class DeadlineHealthFilter(admin.SimpleListFilter):
    title = 'deadline health'
    parameter_name = 'deadline_health'

    def lookups(self, request, model_admin):
        return (
            ('open', 'Open'),
            ('overdue', 'Overdue'),
            ('completed', 'Completed'),
        )

    def queryset(self, request, queryset):
        today = timezone.localdate()
        if self.value() == 'open':
            return queryset.filter(is_completed=False)
        if self.value() == 'overdue':
            return queryset.filter(is_completed=False, due_date__lt=today)
        if self.value() == 'completed':
            return queryset.filter(is_completed=True)
        return queryset


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'slug')


@admin.register(OrganizationMembership)
class OrganizationMembershipAdmin(admin.ModelAdmin):
    list_display = ('organization', 'user', 'role', 'is_active', 'created_at')
    list_filter = ('role', 'is_active')
    search_fields = ('organization__name', 'user__username', 'user__email')


@admin.register(OrganizationInvitation)
class OrganizationInvitationAdmin(admin.ModelAdmin):
    list_display = ('organization', 'email', 'role', 'status', 'invited_by', 'expires_at', 'created_at')
    list_filter = ('role', 'status')
    search_fields = ('organization__name', 'email', 'invited_by__username')


@admin.register(SalesforceOrganizationConnection)
class SalesforceOrganizationConnectionAdmin(admin.ModelAdmin):
    list_display = (
        'organization',
        'is_active',
        'connected_by',
        'instance_url',
        'token_expires_at',
        'updated_at',
    )
    list_filter = ('is_active',)
    search_fields = ('organization__name', 'organization__slug', 'external_org_id', 'instance_url')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(OrganizationContractFieldMap)
class OrganizationContractFieldMapAdmin(admin.ModelAdmin):
    list_display = (
        'organization',
        'canonical_field',
        'salesforce_object',
        'salesforce_field',
        'is_required',
        'is_active',
    )
    list_filter = ('is_required', 'is_active', 'salesforce_object')
    search_fields = ('organization__name', 'canonical_field', 'salesforce_field')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(SalesforceSyncRun)
class SalesforceSyncRunAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'organization',
        'status',
        'trigger_source',
        'dry_run',
        'fetched_records',
        'created_count',
        'updated_count',
        'error_count',
        'started_at',
        'completed_at',
    )
    list_filter = ('status', 'trigger_source', 'dry_run')
    search_fields = ('organization__name', 'organization__slug', 'error_message')
    readonly_fields = ('started_at', 'completed_at')


@admin.register(WebhookEndpoint)
class WebhookEndpointAdmin(admin.ModelAdmin):
    list_display = ('organization', 'name', 'url', 'status', 'max_attempts', 'updated_at')
    list_filter = ('status',)
    search_fields = ('organization__name', 'name', 'url')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'organization',
        'endpoint',
        'event_type',
        'status',
        'attempt_count',
        'max_attempts',
        'response_status',
        'created_at',
    )
    list_filter = ('status', 'event_type')
    search_fields = ('organization__name', 'endpoint__name', 'event_type', 'error_message')
    readonly_fields = ('created_at', 'updated_at', 'dead_lettered_at', 'sent_at')


@admin.register(Deadline)
class DeadlineAdmin(admin.ModelAdmin):
    list_display = ('title', 'contract', 'matter', 'due_date', 'is_completed', 'is_overdue')
    list_filter = ('is_completed', 'deadline_type', 'priority', DeadlineHealthFilter)
    search_fields = ('title', 'description', 'contract__title', 'matter__title')
    date_hierarchy = 'due_date'

    @admin.display(boolean=True, description='Overdue')
    def is_overdue(self, obj):
        return obj.is_overdue

@admin.register(RiskLog)
class RiskLogAdmin(admin.ModelAdmin):
    list_display = ('title', 'risk_level', 'case_record', 'created_by', 'created_at')
    list_filter = ('risk_level', 'created_at')
    search_fields = ('title', 'description')

    @admin.display(description='Case')
    def case_record(self, obj):
        return obj.contract or obj.matter

class ChecklistItemInline(admin.TabularInline):
    model = ChecklistItem
    extra = 1

@admin.register(ComplianceChecklist)
class ComplianceChecklistAdmin(admin.ModelAdmin):
    list_display = ('title', 'regulation_type', 'created_at')
    list_filter = ('regulation_type',)
    search_fields = ('title', 'description')
    inlines = [ChecklistItemInline]

@admin.register(TrademarkRequest)
class TrademarkRequestAdmin(admin.ModelAdmin):
    list_display = ('mark_text', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('mark_text', 'description')

@admin.register(LegalTask)
class LegalTaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'priority', 'status', 'due_date', 'assigned_to')
    list_filter = ('priority', 'status')
    search_fields = ('title', 'description')

class DueDiligenceTaskInline(admin.TabularInline):
    model = DueDiligenceTask
    extra = 1

class DueDiligenceRiskInline(admin.TabularInline):
    model = DueDiligenceRisk
    extra = 1

@admin.register(DueDiligenceProcess)
class DueDiligenceProcessAdmin(admin.ModelAdmin):
    list_display = ('title', 'target_company', 'transaction_type', 'status', 'target_completion_date')
    list_filter = ('transaction_type', 'status', 'created_at')
    search_fields = ('title', 'target_company')
    inlines = [DueDiligenceTaskInline, DueDiligenceRiskInline]

@admin.register(DueDiligenceTask)
class DueDiligenceTaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'process', 'category', 'status', 'assigned_to', 'due_date')
    list_filter = ('category', 'status', 'process')
    search_fields = ('title', 'description')

@admin.register(DueDiligenceRisk)
class DueDiligenceRiskAdmin(admin.ModelAdmin):
    list_display = ('title', 'process', 'risk_level', 'category', 'owner')
    list_filter = ('risk_level', 'category', 'process')
    search_fields = ('title', 'description')

class BudgetExpenseInline(admin.TabularInline):
    model = BudgetExpense
    extra = 1

@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ('department', 'year', 'quarter', 'allocated_amount')
    list_filter = ('year', 'quarter', 'department')
    search_fields = ('department',)
    inlines = [BudgetExpenseInline]

@admin.register(BudgetExpense)
class BudgetExpenseAdmin(admin.ModelAdmin):
    list_display = ['budget', 'description', 'amount', 'category', 'date', 'created_by']
    list_filter = ['category', 'date', 'created_at']
    search_fields = ['description', 'budget__department']
    date_hierarchy = 'date'

class WorkflowStepInline(admin.TabularInline):
    model = WorkflowStep
    extra = 1
    ordering = ['-created_at']

@admin.register(Workflow)
class WorkflowAdmin(admin.ModelAdmin):
    list_display = ['title', 'status', 'created_by', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['title', 'description']
    readonly_fields = ['created_at']

@admin.register(WorkflowTemplate)
class WorkflowTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'version', 'category', 'parent_template', 'is_active', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at',)

    _PUBLISHED_LOCKED_FIELDS = (
        'name',
        'description',
        'organization',
        'category',
        'version',
        'parent_template',
        'contract_type',
        'fallback_signer',
    )

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if obj is not None and obj.is_active:
            readonly = list(dict.fromkeys([*readonly, *self._PUBLISHED_LOCKED_FIELDS, 'is_active']))
        return readonly

    def save_model(self, request, obj, form, change):
        if change and obj.pk:
            prior = WorkflowTemplate.objects.filter(pk=obj.pk).first()
            if prior and prior.is_active:
                # Published rows are immutable in Admin. Unpublish via the product UI.
                from django.contrib import messages
                messages.error(
                    request,
                    'Published workflow templates are immutable in Admin. '
                    'Use Workflow Designer to create a new version or unpublish to draft.',
                )
                return
        super().save_model(request, obj, form, change)

@admin.register(WorkflowTemplateStep)
class WorkflowTemplateStepAdmin(admin.ModelAdmin):
    list_display = ['template', 'name', 'order']
    list_filter = ['template']
    search_fields = ['template__name', 'name']
    ordering = ['template', 'order']

@admin.register(WorkflowStep)
class WorkflowStepAdmin(admin.ModelAdmin):
    list_display = ['workflow', 'name', 'status', 'assigned_to', 'due_date']
    list_filter = ['status', 'due_date']
    search_fields = ['workflow__title', 'name']

@admin.register(ContractType)
class ContractTypeAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['code', 'name', 'description']
    ordering = ['name']
    readonly_fields = ['created_at']

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ['code', 'created_at']
        return ['created_at']

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        from contracts.services.contract_type_catalogue import audit_catalogue_mutation, valid_codes
        from django.core.exceptions import ValidationError

        if not change and obj.code not in valid_codes():
            raise ValidationError('New catalogue rows must use an approved enum code.')
        super().save_model(request, obj, form, change)
        audit_catalogue_mutation(
            actor=request.user,
            catalogue=obj,
            action='update' if change else 'create',
            changes={'code': obj.code, 'name': obj.name, 'is_active': obj.is_active},
            request=request,
        )


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'organization', 'status', 'origin_kind', 'counterparty',
        'value', 'start_date', 'end_date', 'created_at', 'is_expiring_soon',
    ]
    list_filter = ['organization', 'status', 'origin_kind', 'created_at', 'start_date', ExpiringContractFilter]
    search_fields = ['title', 'content', 'counterparty', 'source_system_id', 'provenance_correlation_id']
    ordering = ['-created_at']
    readonly_fields = [
        'origin_kind',
        'origin_channel',
        'origin_workflow',
        'origin_workflow_template',
        'origin_workflow_template_version',
        'origin_reason',
        'provenance_correlation_id',
        'provenance_locked_at',
        'source_system',
        'source_system_id',
        'created_by',
        'created_at',
        'updated_at',
    ]

    def save_model(self, request, obj, form, change):
        from contracts.services.contract_provenance import (
            EVENT_PROVENANCE_ASSIGNED,
            EVENT_RECORD_CREATED,
            OriginKind,
            apply_provenance_fields,
            provenance_snapshot,
        )
        from contracts.middleware import log_action
        from contracts.models import AuditLog

        if not change:
            apply_provenance_fields(
                obj,
                origin_kind=OriginKind.ADMIN,
                origin_channel='django_admin',
                origin_reason='Created via Django admin',
                actor=request.user,
                lock=True,
                validate=True,
            )
        super().save_model(request, obj, form, change)
        if not change:
            snap = provenance_snapshot(obj)
            log_action(
                request.user,
                AuditLog.Action.CREATE,
                'Contract',
                obj.pk,
                str(obj),
                organization=obj.organization,
                request=request,
                event_type=EVENT_RECORD_CREATED,
                changes={'event': EVENT_RECORD_CREATED, 'provenance': snap},
            )
            log_action(
                request.user,
                AuditLog.Action.CREATE,
                'Contract',
                obj.pk,
                str(obj),
                organization=obj.organization,
                request=request,
                event_type=EVENT_PROVENANCE_ASSIGNED,
                changes={'event': EVENT_PROVENANCE_ASSIGNED, 'provenance': snap},
            )

    @admin.display(boolean=True, description='Expiring <=30d')
    def is_expiring_soon(self, obj):
        return bool(
            obj.status == 'ACTIVE' and obj.end_date and timezone.localdate() <= obj.end_date <= timezone.localdate() + timedelta(days=30)
        )


class OrganizationScopedAdmin(admin.ModelAdmin):
    list_filter = ['organization']


@admin.register(Counterparty)
class CounterpartyAdmin(OrganizationScopedAdmin):
    list_display = ['name', 'organization', 'entity_type', 'jurisdiction', 'is_active']
    search_fields = ['name', 'jurisdiction']


@admin.register(ClauseCategory)
class ClauseCategoryAdmin(OrganizationScopedAdmin):
    list_display = ['name', 'organization', 'order']
    search_fields = ['name', 'description']


@admin.register(ClauseTemplate)
class ClauseTemplateAdmin(OrganizationScopedAdmin):
    list_display = ['title', 'organization', 'category', 'jurisdiction_scope', 'is_approved']
    search_fields = ['title', 'content', 'tags']


@admin.register(ContractTemplate)
class ContractTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'contract_type', 'is_active', 'created_at']
    list_filter = ['contract_type', 'is_active']
    search_fields = ['name', 'description', 'body']


@admin.register(SignatureRequest)
class SignatureRequestAdmin(OrganizationScopedAdmin):
    list_display = ['signer_email', 'organization', 'case_record', 'status', 'created_at']
    search_fields = ['signer_name', 'signer_email', 'contract__title']

    @admin.display(description='Case')
    def case_record(self, obj):
        return obj.contract


@admin.register(DataInventoryRecord)
class DataInventoryRecordAdmin(OrganizationScopedAdmin):
    list_display = ['title', 'organization', 'client', 'lawful_basis', 'updated_at']
    search_fields = ['title', 'client__name']


@admin.register(DSARRequest)
class DSARRequestAdmin(OrganizationScopedAdmin):
    list_display = ['reference_number', 'organization', 'request_type', 'status', 'due_date', 'is_overdue']
    list_filter = ['organization', 'status', 'request_type', OverdueDSARFilter]
    search_fields = ['reference_number', 'requester_name', 'requester_email']

    @admin.display(boolean=True, description='Overdue')
    def is_overdue(self, obj):
        return obj.is_overdue


@admin.register(Subprocessor)
class SubprocessorAdmin(OrganizationScopedAdmin):
    list_display = ['name', 'organization', 'service_type', 'country', 'risk_level']
    search_fields = ['name', 'service_type', 'country']


@admin.register(TransferRecord)
class TransferRecordAdmin(OrganizationScopedAdmin):
    list_display = ['title', 'organization', 'source_country', 'destination_country', 'transfer_mechanism']
    search_fields = ['title', 'source_country', 'destination_country']


@admin.register(RetentionPolicy)
class RetentionPolicyAdmin(OrganizationScopedAdmin):
    list_display = ['title', 'organization', 'category', 'retention_period_days', 'is_active']
    search_fields = ['title', 'category']


@admin.register(LegalHold)
class LegalHoldAdmin(OrganizationScopedAdmin):
    list_display = ['title', 'organization', 'status', 'case_matter', 'client', 'hold_start_date']
    search_fields = ['title', 'description']

    @admin.display(description='Case matter')
    def case_matter(self, obj):
        return obj.matter


@admin.register(ApprovalRule)
class ApprovalRuleAdmin(OrganizationScopedAdmin):
    list_display = ['name', 'organization', 'trigger_type', 'approval_step', 'approver_role', 'is_active']
    search_fields = ['name', 'trigger_value']


@admin.register(ApprovalRequest)
class ApprovalRequestAdmin(OrganizationScopedAdmin):
    list_display = ['case_record', 'organization', 'approval_step', 'status', 'assigned_to', 'created_at', 'due_date', 'is_overdue']
    list_filter = ['organization', 'status', 'approval_step', OverdueApprovalFilter]
    search_fields = ['contract__title', 'approval_step', 'comments']

    @admin.display(description='Case')
    def case_record(self, obj):
        return obj.contract

    @admin.display(boolean=True, description='Overdue')
    def is_overdue(self, obj):
        return bool(obj.status == 'PENDING' and obj.due_date and obj.due_date < timezone.now())


@admin.register(ExceptionRequest)
class ExceptionRequestAdmin(OrganizationScopedAdmin):
    list_display = [
        'title', 'organization', 'category', 'status', 'owner',
        'risk_classification', 'starts_at', 'expires_at', 'is_permanent',
    ]
    list_filter = ['organization', 'status', 'category', 'risk_classification']
    search_fields = ['title', 'reason', 'legacy_source']
    readonly_fields = ['created_at', 'updated_at', 'closed_at']


@admin.register(ExceptionDecision)
class ExceptionDecisionAdmin(OrganizationScopedAdmin):
    list_display = [
        'exception_request', 'organization', 'outcome', 'decided_by',
        'security_approval', 'decided_at',
    ]
    list_filter = ['organization', 'outcome', 'security_approval']
    search_fields = ['comments', 'authority_basis']
    readonly_fields = [
        'exception_request', 'organization', 'outcome', 'decided_by',
        'authority_basis', 'authority_holder_id', 'security_approval',
        'comments', 'compensating_controls_at_decision',
        'granted_privileges_at_decision', 'starts_at', 'expires_at',
        'is_permanent_approved', 'decided_at', 'created_at',
    ]


@admin.register(CommandCenterSavedView)
class CommandCenterSavedViewAdmin(OrganizationScopedAdmin):
    list_display = ['name', 'organization', 'key', 'is_default', 'sort_order', 'updated_at']
    list_filter = ['organization', 'is_default']
    search_fields = ['name', 'key', 'description']


@admin.register(CommandCenterWorkItem)
class CommandCenterWorkItemAdmin(OrganizationScopedAdmin):
    list_display = ['title', 'organization', 'source_type', 'status', 'risk_level', 'priority', 'owner', 'due_at', 'updated_at']
    list_filter = ['organization', 'source_type', 'status', 'risk_level', 'priority']
    search_fields = ['title', 'subtitle', 'item_type', 'stage']


@admin.register(CommandCenterRailItem)
class CommandCenterRailItemAdmin(OrganizationScopedAdmin):
    list_display = ['title', 'organization', 'kind', 'count', 'severity', 'is_active', 'sort_order', 'updated_at']
    list_filter = ['organization', 'kind', 'severity', 'is_active']
    search_fields = ['title', 'summary']


@admin.register(ReviewMemo)
class ReviewMemoAdmin(OrganizationScopedAdmin):
    list_display = ['title', 'organization', 'memo_type', 'contract', 'dpa_review_pack', 'generated_at']
    list_filter = ['organization', 'memo_type']
    search_fields = ['title', 'body', 'source']


@admin.register(EthicalWall)
class EthicalWallAdmin(OrganizationScopedAdmin):
    list_display = ['name', 'organization', 'case_matter', 'client', 'is_active']
    search_fields = ['name', 'description']

    @admin.display(description='Case matter')
    def case_matter(self, obj):
        return obj.matter


from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Read-only: audit evidence is append-only and must not be edited or
    deleted through the admin. No add/change/delete permissions are granted."""

    list_display = ('timestamp', 'organization', 'actor_type', 'user', 'action',
                    'event_type', 'outcome', 'model_name', 'object_id', 'seq')
    list_filter = ('action', 'actor_type', 'outcome', 'event_type')
    search_fields = ('event_type', 'model_name', 'object_repr', 'request_id')
    date_hierarchy = 'timestamp'
    ordering = ('-timestamp',)

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
