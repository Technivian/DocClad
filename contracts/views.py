from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum, Count, Q, Avg, Min
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login, get_user_model
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.http import HttpResponse, HttpResponseForbidden
from django.conf import settings
from django.db import models, connection, DatabaseError
from django.utils.dateparse import parse_date
from django.utils.decorators import method_decorator
from datetime import datetime, timedelta, date
from decimal import Decimal
import csv
import logging

from .forms import (
    BudgetForm, LegalTaskForm, BudgetExpenseForm,
    ClientForm, CareConfigurationForm, DocumentForm,
    DeadlineForm, UserProfileForm,
    RegistrationForm,
    OrganizationInvitationForm,
    MunicipalityConfigurationForm, RegionalConfigurationForm,
    CaseAssessmentForm, DueDiligenceProcessForm,
)
from .models import (
    Organization, OrganizationMembership, OrganizationInvitation,
    Contract, NegotiationThread, TrademarkRequest, LegalTask, RiskLog, ComplianceChecklist, ChecklistItem,
    Workflow, WorkflowTemplate, WorkflowTemplateStep, WorkflowStep,
    DueDiligenceProcess, DueDiligenceTask, DueDiligenceRisk, Budget, BudgetExpense,
    Client, Matter, Document, TimeEntry, Invoice, TrustAccount, TrustTransaction,
    Deadline, AuditLog, Notification, UserProfile, ConflictCheck,
    Counterparty, ClauseCategory, ClauseTemplate, EthicalWall, SignatureRequest,
    DataInventoryRecord, DSARRequest, Subprocessor, TransferRecord, RetentionPolicy,
    LegalHold, ApprovalRule, ApprovalRequest, Case, CaseMatter, CaseSignal,
)
from .middleware import log_action
from .observability import db_health_snapshot, request_metrics_snapshot, scheduler_health_snapshot
from .permissions import (
    CaseAction,
    can_access_case_action,
    can_manage_organization,
    is_organization_owner,
)
from .tenancy import get_user_organization, scope_queryset_for_organization, set_organization_on_instance
from .services.starter_content import ensure_org_starter_content
from .view_support import (
    OrganizationContextMixin,
    TenantAssignCreateMixin,
    TenantScopedFormMixin,
    TenantScopedQuerysetMixin,
    apply_form_queryset_scopes as _apply_form_queryset_scopes,
    configure_workflow_form as _configure_workflow_form,
    organization_user_queryset as _organization_user_queryset,
    scope_budgets_for_organization as _scope_budgets_for_organization,
    scope_checklist_items_for_organization as _scope_checklist_items_for_organization,
    scope_checklists_for_organization as _scope_checklists_for_organization,
    scope_due_diligence_processes_for_organization as _scope_due_diligence_processes_for_organization,
    scope_due_diligence_tasks_for_organization as _scope_due_diligence_tasks_for_organization,
    scope_workflow_steps_for_organization as _scope_workflow_steps_for_organization,
    scope_workflows_for_organization as _scope_workflows_for_organization,
)
from .views_domains.privacy_approvals import (
    ApprovalRequestCreateView,
    ApprovalRequestListView,
    ApprovalRequestUpdateView,
    ApprovalRuleCreateView,
    ApprovalRuleListView,
    ApprovalRuleUpdateView,
    DSARRequestCreateView,
    DSARRequestDetailView,
    DSARRequestListView,
    DSARRequestUpdateView,
    DataInventoryCreateView,
    DataInventoryDetailView,
    DataInventoryListView,
    DataInventoryUpdateView,
    LegalHoldCreateView,
    LegalHoldDetailView,
    LegalHoldListView,
    LegalHoldUpdateView,
    RetentionPolicyCreateView,
    RetentionPolicyListView,
    RetentionPolicyUpdateView,
    SignatureRequestCreateView,
    SignatureRequestDetailView,
    SignatureRequestListView,
    SignatureRequestUpdateView,
    SignaturePacketDetailView,
    signature_request_refresh,
    signature_request_send,
    signature_request_send_reminder,
    signature_request_transition,
    signature_packet_resend,
    signature_packet_cancel,
    signature_packet_retry,
    SubprocessorCreateView,
    SubprocessorDetailView,
    SubprocessorListView,
    SubprocessorUpdateView,
    TransferRecordCreateView,
    TransferRecordListView,
    TransferRecordUpdateView,
    privacy_dashboard,
    privacy_evidence_export,
    ai_data_controls,
)
from .views_domains.organization_admin import (
    accept_organization_invite,
    deactivate_organization_member,
    organization_identity_settings,
    organization_activity,
    organization_activity_export,
    organization_team,
    revoke_member_sessions,
    reactivate_organization_member,
    reports_dashboard,
    reports_export,
    resend_organization_invite,
    retry_organization_invite,
    revoke_organization_invite,
    update_invitation_role,
    update_membership_role,
)
from .views_domains.saml import (
    saml_acs,
    saml_login,
    saml_metadata,
    saml_logout,
    saml_select,
)
from .views_domains.deadlines import (
    DeadlineCreateView,
    DeadlineListView,
    DeadlineUpdateView,
    ObligationsWorkspaceView,
    deadline_complete,
    deadline_delete,
)
from .views_domains.contracts import (
    ContractCreateView,
    ContractDetailView,
    ContractListView,
    ContractUpdateView,
    RepositoryView,
    contract_ai_assistant,
    contract_approval_decision,
    contract_approval_chain_reorder,
    contract_submit_for_review,
    contract_template_picker,
    dashboard,
    legal_front_door,
    upload_signed_contract,
    contract_review_workspace,
)
from .views_domains.dpa_workflow import (
    DPAReviewAndGenerateView,
    DPAWorkflowBuilderView,
    dpa_confirm_section,
    dpa_exception_action,
    dpa_submit_for_review,
)
from .views_domains.msa_workflow import (
    MSAWorkflowBuilderView,
    msa_confirm_section,
    msa_exception_action,
    msa_export_document,
    msa_submit_for_review,
)
from .views_domains.nda_workflow import (
    NDAWorkflowBuilderView,
    nda_confirm_section,
    nda_exception_action,
    nda_submit_for_review,
)
from .views_domains.dpa_review import (
    DPAPlaybookListView,
    DPAReviewMemoView,
    DPAReviewPackDetailView,
    DPAReviewPackListView,
    dpa_review_generate_memo,
    dpa_review_link_related_contract,
    dpa_review_memo_export,
    dpa_review_run_analysis,
    dpa_review_set_approval_status,
    dpa_risk_item_add_note,
    dpa_risk_item_create,
    dpa_risk_item_set_status,
)
from .views_domains.matter_ops import (
    ComplianceChecklistCreateView,
    ComplianceChecklistDetailView,
    ComplianceChecklistListView,
    ComplianceChecklistUpdateView,
    DueDiligenceCreateView,
    DueDiligenceDetailView,
    DueDiligenceListView,
    DueDiligenceUpdateView,
    LegalTaskCreateView,
    LegalTaskKanbanView,
    LegalTaskUpdateView,
    legal_task_complete,
    BudgetCreateView,
    BudgetDetailView,
    BudgetListView,
    BudgetUpdateView,
    RiskLogCreateView,
    RiskLogListView,
    RiskLogUpdateView,
    TrademarkRequestCreateView,
    TrademarkRequestDetailView,
    TrademarkRequestListView,
    TrademarkRequestUpdateView,
)
from .views_domains.actions import (
    AddChecklistItemView,
    AddDueDiligenceItemView,
    AddDueDiligenceRiskView,
    AddExpenseView,
    AddNegotiationNoteView,
    ToggleChecklistItemView,
    identity_telemetry_dashboard,
    organization_security_settings,
    organization_security_export,
    organization_session_audit,
    organization_session_audit_export,
    profile,
    profile_sessions,
    ProfilePasswordChangeView,
    settings_hub,
    toggle_dd_item,
    toggle_redesign,
)
from .views_domains.counterparty_collaboration import (
    counterparty_collaboration_add_comment,
    counterparty_collaboration_complete_task,
    counterparty_collaboration_create_item,
    counterparty_collaboration_document_download,
    counterparty_collaboration_invite,
    counterparty_collaboration_portal,
    counterparty_collaboration_revoke,
    counterparty_collaboration_upload_revision,
)
from .views_domains.core import (
    csp_report,
    CLMOnePasswordResetConfirmView,
    CLMOnePasswordResetView,
    health_check,
    index,
    LoginView,
    MfaRequiredMixin,
    mfa_challenge,
    mfa_challenge_resend,
    mfa_enroll,
    operations_dashboard,
    SignUpView,
    switch_organization,
)
from .views_domains.workspace_nav import (
    MyWorkView,
    TemplatesPlaybooksHubView,
)
from .views_domains.activity import (
    AuditLogListView,
    mark_all_notifications_read,
    mark_notification_read,
    notification_list,
)
from .views_domains.client_matter_document import (
    ClientCreateView,
    ClientDetailView,
    ClientListView,
    ClientUpdateView,
    DocumentCreateView,
    DocumentDeleteView,
    DocumentDetailView,
    DocumentCompareView,
    DocumentListView,
    DocumentUpdateView,
    document_download,
    DocumentOCRQueueView,
    DocumentOCRReviewUpdateView,
    MatterCreateView,
    MatterDetailView,
    MatterListView,
    MatterUpdateView,
)
from .views_domains.billing import (
    InvoiceCreateView,
    InvoiceDetailView,
    InvoiceListView,
    InvoiceUpdateView,
    TimeEntryCreateView,
    TimeEntryListView,
    TimeEntryUpdateView,
)
from .views_domains.trust_conflict import (
    AddTrustTransactionView,
    ConflictCheckCreateView,
    ConflictCheckListView,
    ConflictCheckUpdateView,
    TrustAccountCreateView,
    TrustAccountDetailView,
    TrustAccountListView,
)
from .views_domains.repository_management import (
    ClauseCategoryCreateView,
    ClauseCategoryListView,
    ClauseCategoryUpdateView,
    ClauseTemplateCreateView,
    ClauseTemplateDetailView,
    ClauseTemplateCompareView,
    ClauseTemplateListView,
    ClauseTemplateUpdateView,
    clause_playbook_create,
    CounterpartyCreateView,
    CounterpartyDetailView,
    CounterpartyListView,
    CounterpartyUpdateView,
    EthicalWallCreateView,
    EthicalWallListView,
    EthicalWallUpdateView,
    clause_variant_create,
    delete_search_preset,
    global_search,
    save_search_preset,
)
from .views_domains.workflow_management import (
    AddWorkflowStepView,
    AddWorkflowTemplateStepView,
    WorkflowCreateView,
    WorkflowDetailView,
    WorkflowListView,
    WorkflowStepCompleteView,
    WorkflowStepUpdateView,
    WorkflowTemplateCreateView,
    WorkflowTemplateDetailView,
    WorkflowTemplateListView,
    WorkflowTemplateUpdateView,
    WorkflowUpdateView,
    update_workflow_step,
    workflow_create,
    workflow_dashboard,
    workflow_detail,
    workflow_activity,
    workflow_template_create,
    workflow_template_clone_version,
    workflow_template_duplicate,
    workflow_template_archive,
    workflow_template_delete,
    workflow_template_restore_version,
    workflow_template_compare,
    workflow_template_detail,
    workflow_template_activity,
    workflow_template_list,
    workflow_template_preview,
    workflow_template_scenario_save,
    workflow_template_audit_export,
    workflow_template_publish_toggle,
    workflow_template_step_delete,
    workflow_template_step_reorder,
    workflow_template_step_update,
    workflow_approval_route_list,
    workflow_designer_history,
)
from config.feature_flags import get_feature_flag, is_feature_redesign_enabled

logger = logging.getLogger(__name__)
User = get_user_model()


# ==================== ACTION / FUNCTION-BASED VIEWS ====================
