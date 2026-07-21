import logging
import secrets
import subprocess
import time
import traceback
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse

from .logging_context import (
    request_id_var,
    request_org_id_var,
    request_path_var,
    request_user_id_var,
)
from .models import UserProfile
from .session_security import current_session_timestamp
from .models import AuditLog
from .observability import record_request_metric
from .tenancy import get_user_organization

logger = logging.getLogger(__name__)


class DevServerCodeDriftMiddleware:
    """Fail closed when a --noreload worker outlives a git checkout/branch switch.

    Local DEBUG uses uncached template loaders, so HTML can change on disk while
    URLconf stays frozen. That produces NoReverseMatch (e.g. my_work_saved_views_api)
    after switching branches without restarting. When scripts/dev_up.sh records
    logs/devserver.boot_sha, refuse requests until the server is restarted.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self._boot_sha = None
        self._warned = False
        boot_file = Path(settings.BASE_DIR) / 'logs' / 'devserver.boot_sha'
        if boot_file.exists():
            self._boot_sha = boot_file.read_text(encoding='utf-8').strip() or None

    def __call__(self, request):
        if not settings.DEBUG or not self._boot_sha:
            return self.get_response(request)
        path = request.path or ''
        if path.startswith(('/static/', '/media/', '/__reload__/', '/csp-report/')):
            return self.get_response(request)
        try:
            current = subprocess.check_output(
                ['git', '-C', str(settings.BASE_DIR), 'rev-parse', 'HEAD'],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=1,
            ).strip()
        except (OSError, subprocess.SubprocessError):
            return self.get_response(request)
        if not current or current == self._boot_sha:
            return self.get_response(request)
        if not self._warned:
            logger.warning(
                'dev_server_code_drift boot=%s current=%s path=%s',
                self._boot_sha[:8],
                current[:8],
                path,
            )
            self._warned = True
        body = (
            '<!doctype html><html><head><meta charset="utf-8"><title>Restart required</title></head>'
            '<body style="font:14px/1.45 system-ui,sans-serif;max-width:40rem;margin:3rem auto;padding:0 1rem">'
            '<h1>Dev server is out of date</h1>'
            '<p>This worker was started on commit '
            f'<code>{self._boot_sha[:12]}</code> but the workspace is now on '
            f'<code>{current[:12]}</code>.</p>'
            '<p>With <code>--noreload</code>, URLconf stays frozen while templates '
            'reload from disk — that causes <code>NoReverseMatch</code> after a '
            'branch switch.</p>'
            '<p>Run <code>bash scripts/dev_restart.sh</code> and reload.</p>'
            '</body></html>'
        )
        return HttpResponse(body, status=503, content_type='text/html; charset=utf-8')


class PreviewExceptionMiddleware:
    """Surface verbose errors **only in DEBUG/preview**; never leak in production.

    Audit finding B4: this middleware previously returned a full Python
    traceback to any client on any unhandled 500, defeating ``DEBUG=False``.
    It now emits the verbose body only when ``settings.DEBUG`` is on (local
    dev / preview). In production it logs server-side and re-raises so Django's
    standard handler500 renders the branded, information-free 500 page.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except Exception as exc:
            logger.exception('request_failed', extra={'path': request.path, 'method': request.method})
            if settings.DEBUG:
                return HttpResponse(
                    'Preview request failed:\n\n'
                    f'{exc.__class__.__name__}: {exc}\n\n'
                    f'{traceback.format_exc()}',
                    status=500,
                    content_type='text/plain',
                )
            # Production: do not disclose internals. Let Django render handler500.
            raise


class SecurityHeadersMiddleware:
    """Apply baseline security headers consistently across responses."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Per-request CSP nonce. Set before get_response so templates can stamp
        # inline <script>/<style> via the csp_nonce context processor.
        request.csp_nonce = secrets.token_urlsafe(16)
        response = self.get_response(request)
        if not getattr(settings, 'SECURITY_HEADERS_ENABLED', True):
            return response

        response.setdefault('X-Content-Type-Options', 'nosniff')
        response.setdefault('Referrer-Policy', getattr(settings, 'SECURE_REFERRER_POLICY', 'same-origin'))
        response.setdefault('Permissions-Policy', getattr(settings, 'PERMISSIONS_POLICY', 'geolocation=(), microphone=(), camera=()'))
        policy = getattr(settings, 'CONTENT_SECURITY_POLICY', "default-src 'self'")
        response.setdefault('Content-Security-Policy', policy.replace('{nonce}', request.csp_nonce))
        return response


class ControlledPilotScopeMiddleware:
    """Deny direct URL access to surfaces outside the controlled pilot scope.

    Enforcement is path-based and fail-closed for excluded prefixes. When
    ``CONTROLLED_PILOT_ENABLED`` is false, only the existing billing/trust
    kill switches apply (so ``render.yaml`` flags are actually enforced).
    Does not log request bodies, credentials, or contract content.
    """

    # Exact freeform create is excluded; governed builders remain allowed.
    _PILOT_ALLOWED_NEW_PREFIXES = (
        '/contracts/new/start',
        '/contracts/new/msa',
        '/contracts/new/nda',
        '/contracts/new/dpa',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path or '/'
        decision = self._deny_reason(path, request=request)
        if decision:
            logger.info(
                'pilot_scope_denied path=%s reason=%s',
                path,
                decision,
            )
            if request.user.is_authenticated:
                try:
                    from django.contrib import messages
                    if decision == 'law_firm_module_retired':
                        messages.warning(
                            request,
                            'That module is retired for in-house CLM. Use Contracts, Approvals, Privacy Reviews, or Obligations instead.',
                        )
                    else:
                        messages.warning(
                            request,
                            'That area is outside the approved controlled-pilot scope.',
                        )
                except Exception:
                    pass
                return redirect(reverse('dashboard'))
            return redirect(reverse('login'))
        return self.get_response(request)

    def _deny_reason(self, path, request=None):
        billing_on = getattr(settings, 'BILLING_SELF_SERVE_ENABLED', True)
        trust_on = getattr(settings, 'TRUST_ACCOUNTING_ENABLED', True)
        pilot_on = getattr(settings, 'CONTROLLED_PILOT_ENABLED', False)
        ai_on = getattr(settings, 'GEMINI_AI_ENABLED', False)

        if not billing_on and path.startswith('/contracts/billing'):
            return 'billing_disabled'
        if not trust_on and path.startswith('/contracts/trust-accounts'):
            return 'trust_accounting_disabled'

        if not pilot_on:
            # Phase 4: demote half-migrated commercial modules for in-house CLM.
            # Matters stay reachable for obligation/source deep links but stay
            # out of the default nav. Clients and invoices have no in-house JTBD.
            if path.startswith(('/contracts/clients', '/contracts/invoices')):
                user = getattr(request, 'user', None) if request is not None else None
                if user is not None and getattr(user, 'is_authenticated', False):
                    org = get_user_organization(user)
                    if org and getattr(org, 'workspace_mode', None) == 'in_house_clm':
                        return 'law_firm_module_retired'
            return None

        # Law-firm / commercial modules out of pilot.
        for prefix, reason in (
            ('/contracts/clients', 'law_firm_clients'),
            ('/contracts/matters', 'law_firm_matters'),
            ('/contracts/invoices', 'law_firm_invoices'),
            ('/contracts/trust-accounts', 'trust_accounting'),
            ('/contracts/billing', 'billing'),
            ('/contracts/signatures', 'signatures_out_of_scope'),
            ('/contracts/new/upload', 'upload_review_out_of_scope'),
            ('/contracts/dpa-reviews', 'dpa_review_packs_out_of_scope'),
            ('/contracts/obligations', 'obligations_out_of_scope'),
            ('/contracts/workflows/templates', 'workflow_designer_out_of_scope'),
            ('/contracts/approval-rules', 'approval_rule_authoring_out_of_scope'),
        ):
            if path.startswith(prefix):
                return reason

        # Freeform create (/contracts/new/ or /contracts/new/?…) — not builders.
        if path.rstrip('/') == '/contracts/new' or path.startswith('/contracts/new?'):
            return 'freeform_create_out_of_scope'
        if path.startswith('/contracts/new/'):
            if not any(path.startswith(p) for p in self._PILOT_ALLOWED_NEW_PREFIXES):
                return 'freeform_create_out_of_scope'

        # Unrestricted AI entry points when kill switch is off (pilot default).
        if not ai_on:
            if '/ai-' in path or path.endswith('/ai-assistant/') or '/ai-assistant' in path:
                return 'ai_disabled'
            if '/api/' in path and any(
                token in path
                for token in ('/ai-extract', '/ai-suggest', '/ai-draft', '/ai-clauses')
            ):
                return 'ai_disabled'

        return None


class AuthRateLimitMiddleware:
    """
    Simple per-IP request throttling for auth-sensitive endpoints.

    This is intentionally lightweight and works without external dependencies.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            if not getattr(settings, 'RATELIMIT_ENABLED', True):
                return self.get_response(request)

            path = request.path
            client_ip = self._client_ip(request)
            trusted = client_ip in getattr(settings, 'RATELIMIT_TRUSTED_IPS', ())

            # Token-authenticated API/SCIM surfaces: throttle repeated auth
            # FAILURES per IP, leaving legitimate authenticated traffic alone.
            api_prefix = self._matched_api_prefix(path)
            if api_prefix and not trusted:
                return self._handle_api_request(request, api_prefix, client_ip)

            if path not in getattr(settings, 'RATELIMIT_PATHS', ('/login/', '/register/')):
                return self.get_response(request)

            if request.method not in {'POST'}:
                return self.get_response(request)

            if trusted:
                return self.get_response(request)

            limit, window = self._policy_for_path(path)
            key = self._auth_rate_limit_key(path, client_ip)
            reset_key = self._auth_rate_limit_reset_key(path, client_ip)
            now = int(time.time())
            count, reset_at = self._load_auth_counter(key, reset_key, window, now)

            if path == '/login/':
                blocked = count >= limit
                response = self.get_response(request)
                if response.status_code == 302:
                    cache.delete(key)
                    cache.delete(reset_key)
                    return response
                if blocked:
                    retry_after = max(reset_at - now, 1)
                    response = HttpResponse('Too many requests. Please try again later.', status=429)
                    response['Retry-After'] = str(retry_after)
                    return response
                if response.status_code == 200:
                    new_count = self._increment_auth_counter(key, reset_key, reset_at, now)
                    # Close the concurrent multi-worker race: if this failure pushed
                    # the shared counter past the limit, return 429 for this request.
                    if new_count > limit:
                        retry_after = max(reset_at - now, 1)
                        response = HttpResponse('Too many requests. Please try again later.', status=429)
                        response['Retry-After'] = str(retry_after)
                        return response
                return response

            if count >= limit:
                retry_after = max(reset_at - now, 1)
                response = HttpResponse('Too many requests. Please try again later.', status=429)
                response['Retry-After'] = str(retry_after)
                return response

            response = self.get_response(request)
            self._increment_auth_counter(key, reset_key, reset_at, now)
            return response
        except Exception as exc:
            logger.exception('auth_rate_limit_cache_failure', extra={'path': request.path, 'client_ip': self._client_ip(request)})
            if settings.DEBUG:
                return HttpResponse(
                    f'Auth rate limit error: {exc.__class__.__name__}: {exc}',
                    status=503,
                    content_type='text/plain',
                )
            # Production: cache backend is unavailable. Fail closed on auth
            # endpoints rather than disclose internals or silently stop
            # throttling (audit C10). Generic, information-free response.
            return HttpResponse('Service temporarily unavailable.', status=503, content_type='text/plain')

    @staticmethod
    def _auth_rate_limit_key(path, client_ip):
        return f'auth-rl:{path}:{client_ip}'

    @staticmethod
    def _auth_rate_limit_reset_key(path, client_ip):
        return f'auth-rl-reset:{path}:{client_ip}'

    @staticmethod
    def _load_auth_counter(key, reset_key, window, now):
        """Load count + window end; migrate legacy dict buckets if present."""
        raw = cache.get(key)
        if isinstance(raw, dict):
            reset_at = int(raw.get('reset_at') or (now + window))
            if now >= reset_at:
                cache.delete(key)
                cache.delete(reset_key)
                return 0, now + window
            return int(raw.get('count') or 0), reset_at

        reset_at = cache.get(reset_key)
        if reset_at is None or now >= int(reset_at):
            return 0, now + window
        return int(raw or 0), int(reset_at)

    @staticmethod
    def _increment_auth_counter(key, reset_key, reset_at, now):
        """Atomically increment the shared Redis/LocMem failure counter."""
        ttl = max(int(reset_at) - now, 1)
        cache.add(reset_key, int(reset_at), timeout=ttl)
        raw = cache.get(key)
        if isinstance(raw, dict):
            count = int(raw.get('count') or 0) + 1
            cache.set(key, count, timeout=ttl)
            return count
        if raw is None:
            cache.set(key, 1, timeout=ttl)
            return 1
        try:
            incremented = cache.incr(key)
            if incremented is None:
                raise ValueError('cache.incr returned None')
            return int(incremented)
        except (ValueError, TypeError):
            try:
                count = int(raw) + 1
            except (TypeError, ValueError):
                count = 1
            cache.set(key, count, timeout=ttl)
            return count

    @staticmethod
    def _client_ip(request):
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if forwarded:
            return forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '') or 'unknown'

    @staticmethod
    def _policy_for_path(path):
        if path == '/register/':
            return (
                int(getattr(settings, 'REGISTER_RATE_LIMIT_REQUESTS', 10)),
                int(getattr(settings, 'REGISTER_RATE_LIMIT_WINDOW_SECONDS', 300)),
            )
        return (
            int(getattr(settings, 'LOGIN_RATE_LIMIT_REQUESTS', 10)),
            int(getattr(settings, 'LOGIN_RATE_LIMIT_WINDOW_SECONDS', 300)),
        )

    @staticmethod
    def _matched_api_prefix(path):
        for prefix in getattr(settings, 'API_RATELIMIT_PREFIXES', ()):
            if path.startswith(prefix):
                return prefix
        return None

    def _handle_api_request(self, request, prefix, client_ip):
        limit = int(getattr(settings, 'API_AUTH_FAIL_LIMIT', 20))
        window = int(getattr(settings, 'API_AUTH_FAIL_WINDOW_SECONDS', 300))
        key = f'api-authfail-rl:{prefix}:{client_ip}'
        now = int(time.time())
        bucket = cache.get(key)
        if not bucket or not isinstance(bucket, dict) or now >= bucket.get('reset_at', 0):
            bucket = {'count': 0, 'reset_at': now + window}

        # Block once too many recent auth failures have accumulated.
        if bucket['count'] >= limit:
            retry_after = max(bucket['reset_at'] - now, 1)
            response = HttpResponse('Too many failed authentication attempts.', status=429)
            response['Retry-After'] = str(retry_after)
            return response

        response = self.get_response(request)

        # Count only auth failures, so authenticated clients are never throttled.
        if response.status_code in (401, 403):
            bucket['count'] += 1
            cache.set(key, bucket, timeout=max(bucket['reset_at'] - now, 1))
        return response


class AuditLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response


class OrganizationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user and getattr(user, 'is_authenticated', False):
            preferred_org_id = request.session.get('active_organization_id')
            if preferred_org_id:
                user._active_organization_id = preferred_org_id
            organization = get_user_organization(user)
            request.organization = organization
            if organization and request.session.get('active_organization_id') != organization.id:
                request.session['active_organization_id'] = organization.id
        else:
            request.organization = None
        return self.get_response(request)


class SessionSecurityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if not user or not getattr(user, 'is_authenticated', False):
            return self.get_response(request)

        mfa_redirect = self._mfa_gate_redirect(request)
        if mfa_redirect is not None:
            return mfa_redirect

        session = request.session
        profile, _ = UserProfile.objects.get_or_create(user=user)

        current_revocation_counter = profile.session_revocation_counter
        session_revocation_counter = session.get('session_revocation_counter')
        if session_revocation_counter is None:
            session['session_revocation_counter'] = current_revocation_counter
            session_revocation_counter = current_revocation_counter
        elif session_revocation_counter != current_revocation_counter:
            session.flush()
            return redirect(f"{settings.LOGIN_URL}?next={request.get_full_path()}")

        organization = getattr(request, 'organization', None) or get_user_organization(user)
        idle_timeout_minutes = int(
            getattr(organization, 'session_idle_timeout_minutes', None)
            or getattr(settings, 'SESSION_IDLE_TIMEOUT_MINUTES', 120)
        )
        now_ts = current_session_timestamp()
        # Pilot verification harness (DJANGO_E2E only): force idle expiry without waiting.
        if getattr(settings, 'DJANGO_E2E', False) and request.GET.get('e2e_force_idle') == '1':
            request.session['session_last_activity_at'] = now_ts - (idle_timeout_minutes * 60 + 5)
        last_activity = session.get('session_last_activity_at')
        if last_activity is not None:
            try:
                last_activity = int(last_activity)
            except (TypeError, ValueError):
                last_activity = None
        if last_activity is not None and now_ts - last_activity > idle_timeout_minutes * 60:
            session.flush()
            return redirect(f"{settings.LOGIN_URL}?next={request.get_full_path()}")

        session['session_last_activity_at'] = now_ts

        return self.get_response(request)

    # Phase 4F: ONLY the exact routes needed to complete or escape the MFA flow
    # are exempt — not broad /profile//settings//admin/ prefixes. Profile,
    # security/org settings, billing and the admin console are now gated.
    _MFA_EXEMPT_ROUTE_NAMES = (
        'mfa_enroll',           # first-time enrollment
        'mfa_challenge',        # per-session challenge + recovery-code use
        'mfa_challenge_resend',
        'login',                # auth
        'logout',               # escape hatch
    )
    # Infrastructure prefixes (not sensitive app routes); exempting these avoids
    # 302'ing the enrollment page's own assets.
    _MFA_EXEMPT_INFRA_PREFIXES = ('/static/', '/media/')

    @classmethod
    def _exempt_paths(cls):
        cached = cls.__dict__.get('_exempt_paths_cache')
        if cached is None:
            from django.urls import NoReverseMatch, reverse
            paths = set()
            for name in cls._MFA_EXEMPT_ROUTE_NAMES:
                try:
                    paths.add(reverse(name))
                except NoReverseMatch:
                    pass
            cls._exempt_paths_cache = paths
            cached = paths
        return cached

    @classmethod
    def _is_exempt_path(cls, path):
        if path in cls._exempt_paths():
            return True
        return any(path.startswith(prefix) for prefix in cls._MFA_EXEMPT_INFRA_PREFIXES)

    def _mfa_gate_redirect(self, request):
        """Fail-closed MFA gate applied to EVERY non-exempt authenticated view.

        Enforcement lives here (not only in MfaRequiredMixin) so a view that
        forgets the mixin cannot become an MFA bypass. Returns a redirect
        response when the user must satisfy MFA first, else None.
        """
        if self._is_exempt_path(request.path):
            return None
        from contracts.services.mfa_policy import organization_requires_mfa
        organization = getattr(request, 'organization', None) or get_user_organization(request.user)
        if not organization_requires_mfa(organization):
            return None
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        if not profile.mfa_enabled or profile.mfa_verified_at is None:
            return redirect('mfa_enroll')
        if not request.session.get('mfa_verified'):
            return redirect(f"{reverse('mfa_challenge')}?next={request.get_full_path()}")
        return None
class RequestContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started = time.perf_counter()
        request_id = request.META.get('HTTP_X_REQUEST_ID') or str(uuid4())
        request.request_id = request_id
        user = getattr(request, 'user', None)
        organization = getattr(request, 'organization', None)

        request_id_token = request_id_var.set(request_id)
        request_path_token = request_path_var.set(getattr(request, 'path', '-'))
        user_token = request_user_id_var.set(str(user.id) if getattr(user, 'is_authenticated', False) else '-')
        org_token = request_org_id_var.set(str(organization.id) if organization else '-')

        try:
            response = self.get_response(request)
            latency_ms = (time.perf_counter() - started) * 1000
            record_request_metric(request.path, response.status_code, latency_ms)

            response['X-Request-ID'] = request_id
            logger.info(
                'request_completed',
                extra={
                    'method': request.method,
                    'path': request.path,
                    'status_code': response.status_code,
                    'latency_ms': round(latency_ms, 2),
                },
            )
            return response
        finally:
            request_id_var.reset(request_id_token)
            request_path_var.reset(request_path_token)
            request_user_id_var.reset(user_token)
            request_org_id_var.reset(org_token)


def log_action(
    user, action, model_name, object_id=None, object_repr='', changes=None, request=None,
    *, organization=None, organization_id=None, event_type=None, actor_type=None,
    outcome=None, job_run_id=None,
):
    """Canonical audit entry point — appends to the per-org tamper-evident chain.

    Backward compatible: existing callers pass (user, action, model_name, ...).
    Organization is resolved from the explicit arg, then request.organization,
    then a legacy ``changes['organization_id']``. Audit failures are logged and
    swallowed so a logging fault never breaks the business action; the append
    itself runs in its own savepoint so it cannot poison the caller's
    transaction.
    """
    from contracts.services.audit import append_audit

    ip_address = None
    user_agent = ''
    request_id = ''
    if request:
        ip_address = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
        if ip_address and ',' in ip_address:
            ip_address = ip_address.split(',')[0].strip()
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        request_id = getattr(request, 'request_id', '') or ''
        if organization is None and organization_id is None:
            organization = getattr(request, 'organization', None)

    if organization is None and organization_id is None and isinstance(changes, dict):
        organization_id = changes.get('organization_id')

    from contracts.services.audit import AuditMisclassificationError
    try:
        return append_audit(
            action=action,
            model_name=model_name,
            organization=organization,
            organization_id=organization_id,
            user=user,
            object_id=object_id,
            object_repr=object_repr,
            changes=changes,
            event_type=event_type,
            actor_type=actor_type,
            outcome=outcome or AuditLog.Outcome.SUCCESS,
            request_id=request_id,
            job_run_id=job_run_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except AuditMisclassificationError:
        # Never silently downgrade a tenant event onto the system chain — fail
        # loud so the missing-organization call site is fixed.
        raise
    except Exception:
        logger.exception('audit append failed action=%s model=%s', action, model_name)
        return None
