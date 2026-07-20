import csv
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import PasswordChangeView
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import dateformat, timezone
from django.views import View
from django.views.generic import CreateView
from django.core.mail import send_mail

from contracts.forms import BudgetExpenseForm, ChecklistItemForm, DueDiligenceRiskForm, DueDiligenceTaskForm, UserProfileForm
from contracts.models import AuditLog, BudgetExpense, ChecklistItem, Contract, DueDiligenceRisk, DueDiligenceTask, NegotiationThread, Notification, Organization, OrganizationMembership, UserProfile
from contracts.middleware import log_action
from contracts.permissions import ContractAction, can_access_contract_action, can_manage_organization
from contracts.session_security import (
    get_organization_session_audit,
    get_user_sessions,
    revoke_organization_sessions,
    revoke_session_by_key,
)
from contracts.tenancy import get_user_organization
from contracts.view_support import (
    TenantAssignCreateMixin,
    scope_budgets_for_organization as _scope_budgets_for_organization,
    scope_checklist_items_for_organization as _scope_checklist_items_for_organization,
    scope_checklists_for_organization as _scope_checklists_for_organization,
    scope_due_diligence_processes_for_organization as _scope_due_diligence_processes_for_organization,
    scope_due_diligence_tasks_for_organization as _scope_due_diligence_tasks_for_organization,
)


class ToggleChecklistItemView(LoginRequiredMixin, View):
    def post(self, request, pk):
        organization = get_user_organization(request.user)
        item = get_object_or_404(_scope_checklist_items_for_organization(organization), pk=pk)
        linked_contract = item.checklist.contract
        if linked_contract and not can_access_contract_action(request.user, linked_contract, ContractAction.EDIT):
            return HttpResponseForbidden('You do not have permission to update this contract checklist item.')
        item.is_completed = not item.is_completed
        item.completed_by = request.user if item.is_completed else None
        item.completed_at = timezone.now() if item.is_completed else None
        item.save()
        return redirect('contracts:compliance_checklist_detail', pk=item.checklist.pk)


class AddChecklistItemView(TenantAssignCreateMixin, LoginRequiredMixin, CreateView):
    model = ChecklistItem
    form_class = ChecklistItemForm
    template_name = 'contracts/checklist_item_form.html'

    def form_valid(self, form):
        checklist_pk = self.kwargs.get('checklist_pk') or self.kwargs.get('pk')
        organization = get_user_organization(self.request.user)
        checklist = get_object_or_404(_scope_checklists_for_organization(organization), pk=checklist_pk)
        if checklist.contract and not can_access_contract_action(self.request.user, checklist.contract, ContractAction.EDIT):
            return HttpResponseForbidden('You do not have permission to add items to this contract checklist.')
        form.instance.checklist = checklist
        return super().form_valid(form)

    def get_success_url(self):
        checklist_pk = self.kwargs.get('checklist_pk') or self.kwargs.get('pk')
        return reverse_lazy('contracts:compliance_checklist_detail', kwargs={'pk': checklist_pk})


class AddDueDiligenceItemView(LoginRequiredMixin, CreateView):
    model = DueDiligenceTask
    form_class = DueDiligenceTaskForm
    template_name = 'contracts/dd_task_form.html'

    def form_valid(self, form):
        organization = get_user_organization(self.request.user)
        process = get_object_or_404(_scope_due_diligence_processes_for_organization(organization), pk=self.kwargs['process_pk'])
        form.instance.process = process
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('contracts:due_diligence_detail', kwargs={'pk': self.kwargs['process_pk']})


class AddDueDiligenceRiskView(LoginRequiredMixin, CreateView):
    model = DueDiligenceRisk
    form_class = DueDiligenceRiskForm
    template_name = 'contracts/dd_risk_form.html'

    def form_valid(self, form):
        organization = get_user_organization(self.request.user)
        process = get_object_or_404(_scope_due_diligence_processes_for_organization(organization), pk=self.kwargs['process_pk'])
        form.instance.process = process
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('contracts:due_diligence_detail', kwargs={'pk': self.kwargs['process_pk']})


class AddExpenseView(LoginRequiredMixin, CreateView):
    model = BudgetExpense
    form_class = BudgetExpenseForm
    template_name = 'contracts/expense_form.html'

    def form_valid(self, form):
        organization = get_user_organization(self.request.user)
        budget = get_object_or_404(_scope_budgets_for_organization(organization), pk=self.kwargs['budget_pk'])
        form.instance.budget = budget
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('contracts:budget_detail', kwargs={'pk': self.kwargs['budget_pk']})


@login_required
def toggle_redesign(request):
    if request.method == 'POST':
        import os
        current_value = os.environ.get('FEATURE_REDESIGN', 'false').lower()
        new_value = 'false' if current_value == 'true' else 'true'
        os.environ['FEATURE_REDESIGN'] = new_value
        from config.feature_flags import cache
        cache.clear()
        return redirect(request.META.get('HTTP_REFERER', 'dashboard'))
    return redirect('dashboard')


@login_required
def toggle_dd_item(request, pk):
    organization = get_user_organization(request.user)
    task = get_object_or_404(_scope_due_diligence_tasks_for_organization(organization), pk=pk)
    if task.status == 'COMPLETED':
        task.status = 'PENDING'
    else:
        task.status = 'COMPLETED'
    task.save()
    return redirect('contracts:due_diligence_detail', pk=task.process.pk)


def _profile_email_managed(organization):
    if not organization:
        return False
    if organization.scim_enabled:
        return True
    if organization.identity_provider == Organization.IdentityProvider.SAML:
        if organization.saml_sso_url or organization.saml_entity_id:
            return True
    return False


def _profile_permission_set_label(membership):
    if membership and membership.role in {
        OrganizationMembership.Role.OWNER,
        OrganizationMembership.Role.ADMIN,
    }:
        return 'Workspace administrator'
    return 'Standard member'


def _profile_sign_in_method(organization):
    if (
        organization
        and organization.identity_provider == Organization.IdentityProvider.SAML
        and (organization.saml_sso_url or organization.saml_entity_id)
    ):
        return 'Single sign-on (SAML)'
    return 'Email and password'


_PROFILE_SESSION_ELEVATED_THRESHOLD = 4


def _profile_can_change_password(user, organization):
    """Password change is offered for local accounts with a usable password."""
    if not user or not user.is_authenticated:
        return False
    if not user.has_usable_password():
        return False
    if _profile_email_managed(organization):
        return False
    return True


def _profile_regional_previews(profile_obj):
    """Build live date/time examples for each date-format choice."""
    now = timezone.now()
    tz_name = (getattr(profile_obj, 'timezone', None) or 'UTC').strip() or 'UTC'
    try:
        now = timezone.localtime(now, ZoneInfo(tz_name))
    except Exception:
        now = timezone.localtime(now)
    formats = {}
    for value, _label in UserProfile.DateFormat.choices:
        formats[value] = f'{dateformat.format(now, value)} {dateformat.format(now, "H:i")}'
    current_key = getattr(profile_obj, 'date_format', None) or UserProfile.DateFormat.DMY_LONG
    preview = formats.get(current_key) or formats[UserProfile.DateFormat.DMY_LONG]
    if tz_name:
        preview = f'{preview} · {tz_name}'
    return preview, formats


def _profile_security_summary(request, profile_obj, organization):
    personal_sessions = get_user_sessions(
        request.user,
        current_session_key=request.session.session_key,
    )
    recovery_count = profile_obj.mfa_recovery_code_count if profile_obj else 0
    session_count = len(personal_sessions)
    return {
        'mfa_status_label': 'MFA active' if profile_obj and profile_obj.mfa_enabled else 'MFA not enrolled',
        'enrolled_mfa_method': 'Email verification' if profile_obj and profile_obj.mfa_enabled else 'None',
        'sign_in_method': _profile_sign_in_method(organization),
        'last_sign_in': request.user.last_login,
        'recovery_method_status': (
            f'{recovery_count} recovery codes' if recovery_count else 'Not configured'
        ),
        'personal_session_count': session_count,
        'sessions_elevated': session_count >= _PROFILE_SESSION_ELEVATED_THRESHOLD,
    }


def _profile_forms(profile_obj, *, email_managed=False):
    return {
        'identity_form': UserProfileForm(
            instance=profile_obj,
            email_managed=email_managed,
            section='identity',
        ),
        'regional_form': UserProfileForm(instance=profile_obj, section='regional'),
        'notifications_form': UserProfileForm(instance=profile_obj, section='notifications'),
    }


def profile(request):
    profile_obj = None
    organization = None
    membership = None
    identity_form = regional_form = notifications_form = None
    email_managed = False
    workspace_role_label = 'Member'
    permission_set_label = 'Standard member'
    membership_admin = False
    member_since = None
    mfa_required = False
    security_error = ''
    recovery_codes_preview = request.session.pop('mfa_recovery_codes_preview', None)
    show_mfa_setup = False
    security_summary = {}

    if request.user.is_authenticated:
        profile_obj, _ = UserProfile.objects.get_or_create(user=request.user)
        organization = get_user_organization(request.user)
        email_managed = _profile_email_managed(organization)
        mfa_required = bool(getattr(organization, 'require_mfa', False)) if organization else False
        membership = OrganizationMembership.objects.filter(
            organization=organization,
            user=request.user,
            is_active=True,
        ).first() if organization else None
        membership_admin = bool(organization and can_manage_organization(request.user, organization))
        member_since = membership.created_at if membership else request.user.date_joined
        workspace_role_label = membership.get_role_display() if membership else 'Member'
        permission_set_label = _profile_permission_set_label(membership)
        security_summary = _profile_security_summary(request, profile_obj, organization)
        show_mfa_setup = (
            request.GET.get('mfa') == 'setup'
            or request.session.get('mfa_setup_started')
            or bool(profile_obj.mfa_enrollment_code_hash)
        )

        if request.method == 'POST':
            action = request.POST.get('action', 'save')
            if action == 'start_mfa_setup':
                request.session['mfa_setup_started'] = True
                return redirect(f"{reverse('profile')}?mfa=setup")
            if action == 'send_mfa_code':
                request.session['mfa_setup_started'] = True
                enrollment_code = profile_obj.issue_mfa_enrollment_code()
                from contracts.services.notifications import send_mfa_code_email
                send_mfa_code_email(request.user, enrollment_code)
                messages.success(request, 'Verification code sent to your email address.')
                return redirect(f"{reverse('profile')}?mfa=setup")
            if action == 'verify_mfa':
                request.session['mfa_setup_started'] = True
                enrollment_code = (request.POST.get('mfa_enrollment_code') or '').strip()
                if not profile_obj.verify_mfa_enrollment_code(enrollment_code):
                    security_error = 'Enter the 6-digit verification code sent to your email.'
                    show_mfa_setup = True
                    forms = _profile_forms(profile_obj, email_managed=email_managed)
                    identity_form = forms['identity_form']
                    regional_form = forms['regional_form']
                    notifications_form = forms['notifications_form']
                else:
                    request.session.pop('mfa_setup_started', None)
                    request.session['mfa_verified'] = True
                    log_action(
                        request.user,
                        AuditLog.Action.UPDATE,
                        'UserProfile',
                        object_id=profile_obj.id,
                        object_repr=str(profile_obj),
                        changes={'event': 'mfa_enrolled', 'organization_id': getattr(organization, 'id', None)},
                        request=request,
                    )
                    try:
                        from contracts.services.notifications import send_mfa_enrolled_notification
                        send_mfa_enrolled_notification(request.user)
                    except Exception:
                        import logging
                        logging.getLogger(__name__).exception('mfa_enrolled_notification failed user=%s', request.user.pk)
                    messages.success(request, 'Multi-factor authentication enrolled successfully.')
                    return redirect('profile')
            elif action == 'generate_mfa_recovery_codes':
                recovery_codes = profile_obj.issue_mfa_recovery_codes()
                request.session['mfa_recovery_codes_preview'] = recovery_codes
                log_action(
                    request.user,
                    AuditLog.Action.UPDATE,
                    'UserProfile',
                    object_id=profile_obj.id,
                    object_repr=str(profile_obj),
                    changes={'event': 'mfa_recovery_codes_generated', 'count': len(recovery_codes), 'organization_id': getattr(organization, 'id', None)},
                    request=request,
                )
                try:
                    from contracts.services.notifications import send_mfa_recovery_codes_regenerated_notification
                    send_mfa_recovery_codes_regenerated_notification(request.user)
                except Exception:
                    import logging
                    logging.getLogger(__name__).exception('recovery_codes_regenerated_notification failed user=%s', request.user.pk)
                messages.success(request, 'Recovery codes generated. Save them now; they will only be shown once.')
                return redirect('profile')
            elif action in {'save_identity', 'save_regional', 'save_notifications', 'save'} or action not in {
                'start_mfa_setup', 'send_mfa_code', 'verify_mfa', 'generate_mfa_recovery_codes',
            }:
                section_messages = {
                    'save_identity': ('identity', 'Personal details saved.', 'identity'),
                    'save_regional': ('regional', 'Regional preferences saved.', 'regional'),
                    'save_notifications': ('notifications', 'Notification preferences saved.', 'notifications'),
                    'save': ('all', 'Account updated successfully.', None),
                }
                section, success_message, saved_flag = section_messages.get(
                    action,
                    ('all', 'Account updated successfully.', None),
                )
                form = UserProfileForm(
                    request.POST,
                    instance=profile_obj,
                    email_managed=email_managed,
                    section=section,
                )
                if form.is_valid():
                    profile_obj = form.save()
                    if 'bio' in request.POST:
                        profile_obj.bio = request.POST.get('bio', '')
                        profile_obj.save(update_fields=['bio', 'updated_at'])
                    messages.success(request, success_message)
                    if saved_flag:
                        return redirect(f"{reverse('profile')}?saved={saved_flag}")
                    return redirect('profile')

                if section == 'identity':
                    identity_form = form
                    other_forms = _profile_forms(profile_obj, email_managed=email_managed)
                    regional_form = other_forms['regional_form']
                    notifications_form = other_forms['notifications_form']
                elif section == 'regional':
                    regional_form = form
                    other_forms = _profile_forms(profile_obj, email_managed=email_managed)
                    identity_form = other_forms['identity_form']
                    notifications_form = other_forms['notifications_form']
                elif section == 'notifications':
                    notifications_form = form
                    other_forms = _profile_forms(profile_obj, email_managed=email_managed)
                    identity_form = other_forms['identity_form']
                    regional_form = other_forms['regional_form']
                else:
                    forms = _profile_forms(profile_obj, email_managed=email_managed)
                    identity_form = forms['identity_form']
                    regional_form = forms['regional_form']
                    notifications_form = forms['notifications_form']
        else:
            forms = _profile_forms(profile_obj, email_managed=email_managed)
            identity_form = forms['identity_form']
            regional_form = forms['regional_form']
            notifications_form = forms['notifications_form']

    regional_preview = ''
    regional_preview_formats = {}
    can_change_password = False
    if request.user.is_authenticated and profile_obj:
        regional_preview, regional_preview_formats = _profile_regional_previews(profile_obj)
        can_change_password = _profile_can_change_password(request.user, organization)

    return render(request, 'profile.html', {
        'identity_form': identity_form,
        'regional_form': regional_form,
        'notifications_form': notifications_form,
        'profile': profile_obj,
        'organization': organization if request.user.is_authenticated else None,
        'membership': membership,
        'email_managed': email_managed,
        'workspace_role_label': workspace_role_label,
        'permission_set_label': permission_set_label,
        'membership_admin': membership_admin,
        'member_since': member_since,
        'profile_sessions_url': reverse('profile_sessions'),
        'mfa_required': mfa_required,
        'security_error': security_error,
        'recovery_codes_preview': recovery_codes_preview,
        'show_mfa_setup': show_mfa_setup and not (profile_obj and profile_obj.mfa_enabled),
        'regional_preview': regional_preview,
        'regional_preview_formats': regional_preview_formats,
        'can_change_password': can_change_password,
        'hide_app_footer': True,
        **security_summary,
    })


class ProfilePasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    """Change password from Account settings when local passwords are supported."""

    template_name = 'profile_password_change.html'
    success_url = reverse_lazy('profile')
    form_class = PasswordChangeForm

    def dispatch(self, request, *args, **kwargs):
        organization = get_user_organization(request.user)
        if not _profile_can_change_password(request.user, organization):
            messages.error(request, 'Password change is not available for this account.')
            return redirect('profile')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, 'Password updated.')
        return super().form_valid(form)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for field in form.fields.values():
            css = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{css} dc-ds-control'.strip()
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['hide_app_footer'] = True
        return context


@login_required
def profile_sessions(request):
    current_session_key = request.session.session_key
    if request.method == 'POST':
        action = request.POST.get('action', 'revoke_session')
        if action == 'revoke_session':
            session_key = (request.POST.get('session_key') or '').strip()
            sessions = get_user_sessions(request.user, current_session_key=current_session_key)
            target = next((item for item in sessions if item['session_key'] == session_key), None)
            if target and target['is_current']:
                messages.error(request, 'You cannot revoke your current session.')
            elif target and revoke_session_by_key(session_key):
                log_action(
                    request.user,
                    AuditLog.Action.UPDATE,
                    'Session',
                    object_repr=session_key,
                    changes={
                        'event': 'personal_session_revoked',
                        'session_key': session_key,
                    },
                    request=request,
                )
                messages.success(request, 'Session revoked.')
            else:
                messages.error(request, 'Unable to revoke that session.')
        return redirect('profile_sessions')

    return render(request, 'profile_sessions.html', {
        'sessions': get_user_sessions(request.user, current_session_key=current_session_key),
        'hide_app_footer': True,
    })


@login_required
def identity_telemetry_dashboard(request):
    organization = get_user_organization(request.user)
    if not organization:
        messages.error(request, 'No active organization found.')
        return redirect('settings_hub')

    if not can_manage_organization(request.user, organization):
        return HttpResponseForbidden('Only organization owners/admins can view identity telemetry.')

    recent_logs = (
        AuditLog.objects
        .filter(changes__organization_id=organization.id)
        .order_by('-timestamp')[:25]
    )
    telemetry_events = [
        {
            'key': 'mfa_enrolled',
            'label': 'MFA enrolled',
            'value': AuditLog.objects.filter(changes__organization_id=organization.id, changes__event='mfa_enrolled').count(),
        },
        {
            'key': 'mfa_disabled',
            'label': 'MFA disabled',
            'value': AuditLog.objects.filter(changes__organization_id=organization.id, changes__event='mfa_disabled').count(),
        },
        {
            'key': 'mfa_recovery_codes_generated',
            'label': 'Recovery codes generated',
            'value': AuditLog.objects.filter(changes__organization_id=organization.id, changes__event='mfa_recovery_codes_generated').count(),
        },
        {
            'key': 'saml_login_succeeded',
            'label': 'SAML login succeeded',
            'value': AuditLog.objects.filter(changes__organization_id=organization.id, changes__event='saml_login_succeeded').count(),
        },
        {
            'key': 'saml_login_failed',
            'label': 'SAML login failed',
            'value': AuditLog.objects.filter(changes__organization_id=organization.id, changes__event='saml_login_failed').count(),
        },
        {
            'key': 'scim_user_provisioned',
            'label': 'SCIM user provisioned',
            'value': AuditLog.objects.filter(changes__organization_id=organization.id, changes__event='scim_user_provisioned').count(),
        },
        {
            'key': 'scim_user_deprovisioned',
            'label': 'SCIM user deprovisioned',
            'value': AuditLog.objects.filter(changes__organization_id=organization.id, changes__event='scim_user_deprovisioned').count(),
        },
    ]
    recovery_code_counts = (
        UserProfile.objects
        .filter(user__organization_memberships__organization=organization, user__organization_memberships__is_active=True)
        .select_related('user')
    )
    return render(request, 'contracts/identity_telemetry_dashboard.html', {
        'organization': organization,
        'recent_logs': recent_logs,
        'telemetry_events': telemetry_events,
        'recovery_code_counts': recovery_code_counts,
    })


@login_required
def settings_hub(request):
    """Compact configuration landing hub for personal, workspace, and governance settings."""
    organization = get_user_organization(request.user)
    can_manage = bool(organization and can_manage_organization(request.user, organization))
    profile_url = reverse('profile')

    def card(*, label, copy, href, icon, admin_only=False):
        return {
            'label': label,
            'copy': copy,
            'href': href,
            'icon': icon,
            'admin_only': admin_only,
            'badge_label': 'Admin only' if admin_only else '',
            'aria_label': f'{label}. {copy}',
        }

    personal = [
        card(
            label='Account settings',
            copy='Manage your personal details and account preferences.',
            href=profile_url,
            icon='users',
        ),
        card(
            label='Notifications',
            copy='Choose which alerts you receive and how they are delivered.',
            href=f'{profile_url}#notification-settings',
            icon='bell',
        ),
        card(
            label='Appearance and language',
            copy='Manage language, timezone, date formats, and display preferences.',
            href=f'{profile_url}#regional-preferences',
            icon='settings',
        ),
    ]
    workspace = [
        card(
            label='Members and roles',
            copy='Invite members and manage workspace roles and permissions.',
            href=reverse('contracts:organization_team'),
            icon='user-plus',
            admin_only=True,
        ),
        card(
            label='Contract types and intake',
            copy='Configure governed contract types, intake fields, and launch workflows.',
            href=reverse('contracts:templates_playbooks_hub'),
            icon='briefcase',
            admin_only=True,
        ),
        card(
            label='Workflow templates',
            copy='Manage reusable lifecycle blueprints for contract processes.',
            href=reverse('contracts:workflow_template_list'),
            icon='workflow',
            admin_only=True,
        ),
        card(
            label='Negotiation playbooks',
            copy='Define approved positions, fallback guidance, and escalation rules.',
            href=reverse('contracts:dpa_playbook_list'),
            icon='list',
            admin_only=True,
        ),
        card(
            label='Approval policies',
            copy='Configure value, risk, and exception-based approval routing.',
            href=reverse('contracts:approval_rule_list'),
            icon='circle-check',
            admin_only=True,
        ),
        card(
            label='Integrations',
            copy='Connect identity providers, SCIM, webhooks, and external services.',
            href=reverse('organization_identity_settings'),
            icon='cloud',
            admin_only=True,
        ),
    ]
    security = [
        card(
            label='Authentication and access',
            copy='Configure MFA, sign-in methods, and workspace access requirements.',
            href=reverse('organization_security_settings'),
            icon='lock',
            admin_only=True,
        ),
        card(
            label='Workspace sessions',
            copy='Review and revoke active user sessions across the workspace.',
            href=reverse('organization_session_audit'),
            icon='clock',
            admin_only=True,
        ),
        card(
            label='Audit log',
            copy='Inspect workspace activity, security events, and governance changes.',
            href=reverse('contracts:organization_activity'),
            icon='archive',
            admin_only=True,
        ),
    ]

    def visible(cards):
        return [item for item in cards if not item['admin_only'] or can_manage]

    settings_groups = [
        {'id': 'personal', 'title': 'Personal', 'cards': visible(personal)},
        {'id': 'workspace', 'title': 'Workspace', 'cards': visible(workspace)},
        {'id': 'security', 'title': 'Security and governance', 'cards': visible(security)},
    ]
    settings_groups = [group for group in settings_groups if group['cards']]

    return render(request, 'settings_hub.html', {
        'can_manage_settings': can_manage,
        'settings_groups': settings_groups,
    })

@login_required
def organization_security_settings(request):
    organization = get_user_organization(request.user)
    if not organization:
        messages.error(request, 'No active organization found.')
        return redirect('settings_hub')

    if not can_manage_organization(request.user, organization):
        return HttpResponseForbidden('Only organization owners/admins can manage organization security settings.')

    if request.method == 'POST':
        action = request.POST.get('action', 'save')
        if action == 'save_workspace_mode':
            standard_mode = Organization.WorkspaceMode.IN_HOUSE_CLM
            if organization.workspace_mode != standard_mode:
                previous_mode = organization.workspace_mode
                organization.workspace_mode = standard_mode
                organization.save(update_fields=['workspace_mode', 'updated_at'])
                log_action(
                    request.user,
                    AuditLog.Action.UPDATE,
                    'Organization',
                    object_id=organization.id,
                    object_repr=organization.name,
                    changes={
                        'event': 'organization_workspace_mode_standardized',
                        'workspace_mode': standard_mode,
                        'previous_workspace_mode': previous_mode,
                    },
                    request=request,
                )
                messages.success(request, 'Command Center is now the standard workspace.')
            else:
                messages.info(request, 'Command Center is already the standard workspace.')
            return redirect('organization_security_settings')

        if action == 'revoke_sessions':
            affected_users = revoke_organization_sessions(organization)
            log_action(
                request.user,
                AuditLog.Action.UPDATE,
                'Organization',
                object_id=organization.id,
                object_repr=organization.name,
                changes={
                    'event': 'organization_sessions_revoked',
                    'affected_users': len(affected_users),
                },
                request=request,
            )
            messages.success(request, f'Revoked sessions for {len(affected_users)} active organization members.')
            return redirect('organization_security_settings')

        enable_mfa = request.POST.get('require_mfa') == 'on'
        session_timeout_raw = (request.POST.get('session_idle_timeout_minutes') or '').strip()
        try:
            session_timeout_minutes = int(session_timeout_raw)
        except (TypeError, ValueError):
            session_timeout_minutes = None
        if session_timeout_minutes is not None and session_timeout_minutes < 5:
            messages.error(request, 'Session idle timeout must be at least 5 minutes.')
            return redirect('organization_security_settings')

        changes = {}
        if organization.require_mfa != enable_mfa:
            organization.require_mfa = enable_mfa
            changes['require_mfa'] = enable_mfa
        if organization.session_idle_timeout_minutes != session_timeout_minutes and session_timeout_minutes is not None:
            organization.session_idle_timeout_minutes = session_timeout_minutes
            changes['session_idle_timeout_minutes'] = session_timeout_minutes

        if changes:
            organization.save(update_fields=['require_mfa', 'session_idle_timeout_minutes', 'updated_at'])
            if 'require_mfa' in changes:
                # Keep the OrgPolicy mirror in sync with the authoritative field.
                from contracts.services.mfa_policy import set_organization_mfa_required
                set_organization_mfa_required(organization, enable_mfa, user=request.user)
            log_action(
                request.user,
                AuditLog.Action.UPDATE,
                'Organization',
                object_id=organization.id,
                object_repr=organization.name,
                changes={'event': 'organization_security_policy_updated', **changes},
                request=request,
            )
            messages.success(request, 'Organization security settings updated.')
        else:
            messages.info(request, 'Organization security settings are already set to those values.')
        return redirect('organization_security_settings')

    return render(request, 'contracts/organization_security_settings.html', {
        'organization': organization,
        'member_count': OrganizationMembership.objects.filter(organization=organization, is_active=True).count(),
    })


@login_required
def organization_security_export(request):
    organization = get_user_organization(request.user)
    if not organization:
        messages.error(request, 'No active organization found.')
        return redirect('settings_hub')

    if not can_manage_organization(request.user, organization):
        return HttpResponseForbidden('Only organization owners/admins can export organization security data.')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="organization-security-{organization.slug}.csv"'

    writer = csv.writer(response)
    writer.writerow(['organization', organization.name])
    writer.writerow(['require_mfa', organization.require_mfa])
    writer.writerow(['session_idle_timeout_minutes', organization.session_idle_timeout_minutes])
    writer.writerow([])
    writer.writerow(['username', 'email', 'role', 'mfa_enabled', 'mfa_verified_at', 'session_revocation_counter'])

    for membership in OrganizationMembership.objects.filter(organization=organization, is_active=True).select_related('user'):
        profile, _ = UserProfile.objects.get_or_create(user=membership.user)
        writer.writerow([
            membership.user.username,
            membership.user.email,
            membership.role,
            profile.mfa_enabled,
            profile.mfa_verified_at.isoformat() if profile.mfa_verified_at else '',
            profile.session_revocation_counter,
        ])

    return response


@login_required
def organization_session_audit(request):
    organization = get_user_organization(request.user)
    if not organization:
        messages.error(request, 'No active organization found.')
        return redirect('settings_hub')

    if not can_manage_organization(request.user, organization):
        return HttpResponseForbidden('Only organization owners/admins can view session audit data.')

    if request.method == 'POST':
        action = request.POST.get('action', 'revoke_session')
        if action == 'revoke_session':
            session_key = (request.POST.get('session_key') or '').strip()
            if session_key and revoke_session_by_key(session_key):
                log_action(
                    request.user,
                    AuditLog.Action.UPDATE,
                    'Session',
                    object_repr=session_key,
                    changes={
                        'organization_id': organization.id,
                        'event': 'organization_session_revoked',
                        'session_key': session_key,
                    },
                    request=request,
                )
                messages.success(request, 'Session revoked.')
            else:
                messages.error(request, 'Unable to revoke that session.')
            return redirect('organization_session_audit')

    return render(request, 'contracts/organization_session_audit.html', {
        'organization': organization,
        'sessions': get_organization_session_audit(organization),
    })


@login_required
def organization_session_audit_export(request):
    organization = get_user_organization(request.user)
    if not organization:
        messages.error(request, 'No active organization found.')
        return redirect('settings_hub')

    if not can_manage_organization(request.user, organization):
        return HttpResponseForbidden('Only organization owners/admins can export session audit data.')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="organization-sessions-{organization.slug}.csv"'
    writer = csv.writer(response)
    writer.writerow(['organization', organization.name])
    writer.writerow(['session_key', 'username', 'email', 'role', 'last_activity_at', 'expire_date', 'is_expired'])
    for session_info in get_organization_session_audit(organization):
        writer.writerow([
            session_info['session_key'],
            session_info['username'],
            session_info['email'],
            session_info['role'],
            session_info['last_activity_at'] or '',
            session_info['expire_date'].isoformat() if session_info['expire_date'] else '',
            session_info['is_expired'],
        ])
    return response


class AddNegotiationNoteView(TenantAssignCreateMixin, LoginRequiredMixin, CreateView):
    model = NegotiationThread
    fields = ['title', 'content']
    template_name = 'contracts/negotiation_note_form.html'

    def form_valid(self, form):
        organization = get_user_organization(self.request.user)
        contract = get_object_or_404(
            Contract.objects.filter(organization=organization),
            id=self.kwargs['pk'],
        )
        if not can_access_contract_action(self.request.user, contract, ContractAction.COMMENT):
            return HttpResponseForbidden('You do not have permission to comment on this contract.')
        form.instance.contract = contract
        form.instance.created_by = self.request.user
        response = super().form_valid(form)

        mentioned_users = []
        if form.instance.content:
            import re

            mention_candidates = {m.lower() for m in re.findall(r'@([A-Za-z0-9_.-]{3,150})', form.instance.content)}
            if mention_candidates and contract.organization:
                memberships = (
                    OrganizationMembership.objects
                    .filter(organization=contract.organization, is_active=True)
                    .select_related('user')
                )
                seen_user_ids = set()
                for membership in memberships:
                    username = (membership.user.username or '').lower()
                    if username in mention_candidates and membership.user_id != self.request.user.id and membership.user_id not in seen_user_ids:
                        mentioned_users.append(membership.user)
                        seen_user_ids.add(membership.user_id)

        for user in mentioned_users:
            Notification.objects.create(
                recipient=user,
                notification_type=Notification.NotificationType.CONTRACT,
                title=f'Mentioned in contract note: {contract.title}',
                message=(
                    f'{self.request.user.get_full_name() or self.request.user.username} '
                    f'mentioned you in note "{form.instance.title}".'
                ),
                link=reverse('contracts:contract_detail', kwargs={'pk': contract.id}),
            )

        log_action(
            self.request.user,
            AuditLog.Action.CREATE,
            'NegotiationThread',
            object_id=self.object.id,
            object_repr=str(self.object),
            changes={
                'organization_id': contract.organization_id,
                'event': 'negotiation_note_created',
                'mentions_count': len(mentioned_users),
            },
            request=self.request,
        )
        return response

    def get_success_url(self):
        return reverse_lazy('contracts:contract_detail', kwargs={'pk': self.kwargs['pk']})
