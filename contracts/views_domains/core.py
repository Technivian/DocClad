import logging
from datetime import date, timedelta

from django.utils import timezone

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from urllib.parse import urlencode

from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.views.generic import FormView, View
from django.contrib.auth import get_user_model

from contracts.forms import UserProfileForm, RegistrationForm, LoginForm


def _safe_next(request, fallback='/dashboard/') -> str:
    """Return next URL only if it is a safe same-host redirect target."""
    url = request.POST.get('next') or request.GET.get('next') or ''
    if url and url_has_allowed_host_and_scheme(url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return url
    return fallback
from contracts.models import AuditLog, BackgroundJob, Case, CaseMatter, Client, Deadline, Invoice, Notification, OrganizationMembership, OrgPolicy, RiskLog, TimeEntry, TrustAccount, UserProfile, Workflow, CaseSignal, ApprovalRequest, SignatureRequest, DSARRequest, Document
from contracts.middleware import log_action
from contracts.observability import db_health_snapshot, request_metrics_snapshot, scheduler_health_snapshot, evaluate_alert_policy
from contracts.tenancy import get_user_organization, scope_queryset_for_organization

User = get_user_model()
logger = logging.getLogger(__name__)


def get_or_create_profile(user):
    profile, created = UserProfile.objects.get_or_create(user=user)
    return profile


def index(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'landing.html')


def health_check(request):
    response_format = request.GET.get('format', '').lower()
    if response_format != 'json':
        return HttpResponse('OK', content_type='text/plain')

    scheduler = scheduler_health_snapshot()
    database = db_health_snapshot()
    request_metrics = request_metrics_snapshot()
    status = 'ok'
    status_code = 200
    if scheduler.get('status') == 'stale' or database.get('status') == 'down':
        status = 'degraded'
        status_code = 503
    elif database.get('status') == 'slow':
        status = 'degraded'

    return JsonResponse(
        {
            'status': status,
            'scheduler': scheduler,
            'database': database,
            'request_metrics': request_metrics,
        },
        status=status_code,
    )


@login_required
def operations_dashboard(request):
    org = get_user_organization(request.user)
    if not org:
        messages.error(request, 'No active organization found.')
        return redirect('settings_hub')

    recent_jobs = BackgroundJob.objects.filter(organization=org).order_by('-created_at')[:12]
    job_counts = {
        'pending': BackgroundJob.objects.filter(organization=org, status=BackgroundJob.Status.PENDING).count(),
        'running': BackgroundJob.objects.filter(organization=org, status=BackgroundJob.Status.RUNNING).count(),
        'completed': BackgroundJob.objects.filter(organization=org, status=BackgroundJob.Status.COMPLETED).count(),
        'failed': BackgroundJob.objects.filter(organization=org, status=BackgroundJob.Status.FAILED).count(),
    }
    # Scheduled-job run evidence so operators can see whether nightly/periodic
    # jobs actually ran for this tenant — and any failures — without DB access.
    from contracts.models import ScheduledJobRun
    org_runs = ScheduledJobRun.objects.filter(organization=org)
    recent_job_runs = list(org_runs.order_by('-started_at')[:12])
    failed_job_runs_24h = org_runs.filter(
        status__in=[ScheduledJobRun.Status.FAILED, ScheduledJobRun.Status.PARTIAL],
        started_at__gte=timezone.now() - timedelta(hours=24),
    ).count()
    context = {
        'organization': org,
        'scheduler': scheduler_health_snapshot(),
        'database': db_health_snapshot(),
        'request_metrics': request_metrics_snapshot(),
        'alerts': evaluate_alert_policy(),
        'job_counts': job_counts,
        'recent_jobs': recent_jobs,
        'recent_job_runs': recent_job_runs,
        'failed_job_runs_24h': failed_job_runs_24h,
        'drill_state': {
            'last_run_iso': cache.get('operations_drill.last_run_iso'),
            'last_summary': cache.get('operations_drill.last_summary'),
        },
    }
    return render(request, 'contracts/operations_dashboard.html', context)


@login_required
def switch_organization(request):
    org_id = request.POST.get('organization_id')
    membership = (
        OrganizationMembership.objects
        .filter(
            user=request.user,
            is_active=True,
            organization__is_active=True,
            organization_id=org_id,
        )
        .select_related('organization')
        .first()
    )
    if membership:
        request.session['active_organization_id'] = membership.organization_id
        log_action(
            request.user,
            AuditLog.Action.UPDATE,
            'OrganizationMembership',
            object_id=membership.id,
            object_repr=str(membership),
            changes={'event': 'switch_organization', 'organization_id': membership.organization_id},
            request=request,
        )
        messages.success(request, f'Switched to {membership.organization.name}.')
    else:
        messages.error(request, 'You do not have access to that organization.')
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))


class ProfileView(LoginRequiredMixin, View):
    def get(self, request):
        profile = get_or_create_profile(request.user)
        form = UserProfileForm(instance=profile, initial={
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'email': request.user.email,
        })
        return render(request, 'profile.html', {'form': form, 'profile': profile})

    def post(self, request):
        profile = get_or_create_profile(request.user)
        form = UserProfileForm(request.POST, instance=profile)
        if form.is_valid():
            profile = form.save()
            request.user.first_name = form.cleaned_data.get('first_name', '')
            request.user.last_name = form.cleaned_data.get('last_name', '')
            request.user.email = form.cleaned_data.get('email', '')
            request.user.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('profile')
        return render(request, 'profile.html', {'form': form, 'profile': profile})


@method_decorator(ensure_csrf_cookie, name='dispatch')
class SignUpView(FormView):
    form_class = RegistrationForm
    success_url = reverse_lazy('dashboard')
    template_name = 'registration/register.html'

    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except Exception as exc:
            logger.exception('signup_view_failed')
            if settings.DEBUG:
                return HttpResponse(f'Signup failed: {exc.__class__.__name__}: {exc}', status=500, content_type='text/plain')
            raise  # production: render branded handler500, no internals leaked

    def form_valid(self, form):
        self.object = form.save()
        UserProfile.objects.get_or_create(user=self.object)

        login(
            self.request,
            self.object,
            backend='django.contrib.auth.backends.ModelBackend',
        )
        return super().form_valid(form)


@method_decorator(ensure_csrf_cookie, name='dispatch')
class LoginView(FormView):
    form_class = LoginForm
    success_url = reverse_lazy('dashboard')
    template_name = 'registration/login.html'

    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except Exception as exc:
            logger.exception('login_view_failed')
            if settings.DEBUG:
                return HttpResponse(f'Login failed: {exc.__class__.__name__}: {exc}', status=500, content_type='text/plain')
            raise  # production: render branded handler500, no internals leaked

    def form_valid(self, form):
        user = form.cleaned_data['user']
        login(
            self.request,
            user,
            backend='django.contrib.auth.backends.ModelBackend',
        )
        if not form.cleaned_data.get('remember'):
            self.request.session.set_expiry(0)

        # MFA enforcement (fail-closed): authoritative source is
        # Organization.require_mfa via the mfa_policy service. We deliberately do
        # NOT wrap this in a broad try/except — a failure here must block login,
        # never silently bypass MFA. See contracts/services/mfa_policy.py.
        from contracts.tenancy import get_user_organization
        from contracts.services.mfa_policy import organization_requires_mfa
        org = get_user_organization(user)
        if organization_requires_mfa(org):
            profile, _ = UserProfile.objects.get_or_create(user=user)
            # A fresh challenge is required this session.
            self.request.session['mfa_verified'] = False
            if not profile.mfa_enabled:
                return redirect('mfa_enroll')
            code = profile.issue_mfa_enrollment_code()
            _send_mfa_email(user, code)
            return redirect('mfa_challenge')

        next_url = _safe_next(self.request)
        if next_url != '/dashboard/':
            return redirect(next_url)
        return super().form_valid(form)


if settings.DEBUG:
    SignUpView = method_decorator(csrf_exempt, name='dispatch')(SignUpView)


import json


@csrf_exempt
def csp_report(request):
    if request.method != 'POST':
        return HttpResponse(status=405)
    try:
        report = json.loads(request.body.decode('utf-8', errors='replace'))
        try:
            import sentry_sdk
            violation = (report.get('csp-report') or report).get('violated-directive', 'unknown')
            with sentry_sdk.new_scope() as scope:
                scope.set_context('csp_report', report)
                sentry_sdk.capture_message(f'CSP Violation: {violation}', level='warning')
        except Exception:
            logger.warning('CSP violation (Sentry unavailable): %s', report)
    except Exception:
        pass
    return HttpResponse(status=204)


# ---------------------------------------------------------------------------
# MFA support
# ---------------------------------------------------------------------------

def _send_mfa_email(user, code: str) -> None:
    try:
        send_mail(
            subject='Your DocClad verification code',
            message=(
                f'Your verification code is: {code}\n\n'
                'This code expires in 10 minutes. Do not share it with anyone.'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )
    except Exception:
        logger.exception('mfa_email_failed user=%s', user.pk)


class MfaRequiredMixin:
    """Block access if the org requires MFA and this session hasn't verified it."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            # Fail-closed: authoritative MFA check, no broad exception swallow.
            from contracts.tenancy import get_user_organization
            from contracts.services.mfa_policy import organization_requires_mfa
            org = get_user_organization(request.user)
            if organization_requires_mfa(org) and not request.session.get('mfa_verified'):
                from django.urls import reverse
                redirect_url = reverse('mfa_challenge') + '?' + urlencode({'next': request.path})
                return redirect(redirect_url)
        return super().dispatch(request, *args, **kwargs)


@login_required
def mfa_challenge(request):
    """Enter the emailed OTP to set the mfa_verified session flag."""
    next_url = _safe_next(request)
    error = None

    if request.method == 'POST':
        code = request.POST.get('code', '').strip()
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        # Accept either the emailed OTP or a one-time recovery code. The recovery
        # code is the explicit operator escape hatch if email delivery is broken,
        # so a configuration defect cannot permanently lock everyone out.
        if profile.check_mfa_code(code) or profile.verify_mfa_recovery_code(code):
            request.session['mfa_verified'] = True
            return redirect(next_url)
        error = 'Invalid or expired code. Request a new one below.'

    return render(request, 'contracts/mfa_challenge.html', {
        'next': next_url,
        'error': error,
    })


@login_required
def mfa_challenge_resend(request):
    """Re-issue the OTP and redirect back to the challenge page."""
    if request.method == 'POST':
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        code = profile.issue_mfa_enrollment_code()
        _send_mfa_email(request.user, code)
        messages.success(request, 'A new verification code has been sent to your email.')
    next_url = _safe_next(request)
    return redirect(reverse('mfa_challenge') + '?' + urlencode({'next': next_url}))


@login_required
def mfa_enroll(request):
    """First-time MFA enrollment: issue code, verify, activate MFA for user."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    error = None

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'send':
            code = profile.issue_mfa_enrollment_code()
            _send_mfa_email(request.user, code)
            messages.success(request, 'Verification code sent to your email.')
            return redirect('mfa_enroll')

        code = request.POST.get('code', '').strip()
        if profile.verify_mfa_enrollment_code(code):
            request.session['mfa_verified'] = True
            messages.success(request, 'MFA enabled. Your account is now protected.')
            return redirect('dashboard')
        error = 'Invalid or expired code. Please try again.'

    return render(request, 'contracts/mfa_enroll.html', {
        'profile': profile,
        'error': error,
    })
