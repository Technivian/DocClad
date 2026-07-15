"""Subscription / billing views — plan dashboard, Stripe checkout, portal, webhook."""

from __future__ import annotations

import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from contracts.models import BillingPlan, OrgBillingSubscription
from contracts.services.billing import get_billing_service
from contracts.services.stripe_service import get_stripe_service
from contracts.tenancy import get_user_organization

logger = logging.getLogger(__name__)

_TIER_PRICE_ATTR = {
    'STARTER': 'STRIPE_PRICE_STARTER',
    'PROFESSIONAL': 'STRIPE_PRICE_PROFESSIONAL',
}


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@login_required
def billing_dashboard(request):
    org = get_user_organization(request.user)
    usage = get_billing_service().get_current_usage(org)
    plans = list(BillingPlan.objects.filter(is_active=True).order_by('price_monthly'))
    try:
        sub = OrgBillingSubscription.objects.select_related('plan').get(organization=org)
    except OrgBillingSubscription.DoesNotExist:
        sub = None

    return render(request, 'contracts/billing_dashboard.html', {
        'usage': usage,
        'plans': plans,
        'current_sub': sub,
        'stripe_enabled': settings.STRIPE_ENABLED,
        'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY,
    })


# ---------------------------------------------------------------------------
# Checkout (start Stripe Checkout Session → redirect to Stripe)
# ---------------------------------------------------------------------------


@login_required
@require_POST
def billing_checkout(request, tier: str):
    tier = tier.upper()

    if tier == 'ENTERPRISE':
        messages.info(request, 'For Enterprise pricing, please contact sales@clmone.com.')
        return redirect('contracts:billing_dashboard')

    price_attr = _TIER_PRICE_ATTR.get(tier)
    price_id = getattr(settings, price_attr, '') if price_attr else ''
    if not price_id:
        messages.error(request, f'{tier.title()} plan is not yet configured. Contact support.')
        return redirect('contracts:billing_dashboard')

    if not settings.STRIPE_ENABLED:
        messages.error(request, 'Payment processing is not configured.')
        return redirect('contracts:billing_dashboard')

    org = get_user_organization(request.user)
    free_plan = BillingPlan.objects.filter(name='FREE').first()
    sub, _ = OrgBillingSubscription.objects.get_or_create(
        organization=org,
        defaults={'plan': free_plan},
    )

    svc = get_stripe_service()

    success_url = (
        request.build_absolute_uri(reverse('contracts:billing_success'))
        + '?session_id={CHECKOUT_SESSION_ID}'
    )
    cancel_url = request.build_absolute_uri(reverse('contracts:billing_dashboard'))

    try:
        session = svc.create_checkout_session(org, sub, price_id, success_url, cancel_url)
    except Exception as exc:
        logger.exception('billing_checkout: Stripe error for org %s', org.pk)
        messages.error(request, f'Could not start checkout: {exc}')
        return redirect('contracts:billing_dashboard')

    return redirect(session.url, permanent=False)


# ---------------------------------------------------------------------------
# Customer portal (upgrade, downgrade, cancel, update payment method)
# ---------------------------------------------------------------------------


@login_required
@require_POST
def billing_portal(request):
    org = get_user_organization(request.user)
    try:
        sub = OrgBillingSubscription.objects.get(organization=org)
    except OrgBillingSubscription.DoesNotExist:
        messages.error(request, 'No active subscription found.')
        return redirect('contracts:billing_dashboard')

    if not sub.stripe_customer_id:
        messages.error(request, 'No payment method on file. Start a subscription first.')
        return redirect('contracts:billing_dashboard')

    svc = get_stripe_service()
    return_url = request.build_absolute_uri(reverse('contracts:billing_dashboard'))

    try:
        portal_session = svc.create_portal_session(org, sub, return_url)
    except Exception as exc:
        logger.exception('billing_portal: Stripe error for org %s', org.pk)
        messages.error(request, f'Could not open billing portal: {exc}')
        return redirect('contracts:billing_dashboard')

    return redirect(portal_session.url, permanent=False)


# ---------------------------------------------------------------------------
# Success / cancel landing pages
# ---------------------------------------------------------------------------


@login_required
def billing_success(request):
    return render(request, 'contracts/billing_success.html')


# ---------------------------------------------------------------------------
# Stripe webhook (no CSRF, Stripe signature verified instead)
# ---------------------------------------------------------------------------


@csrf_exempt
@require_POST
def stripe_webhook(request):
    if not settings.STRIPE_WEBHOOK_SECRET:
        return HttpResponse('Webhook not configured', status=400)

    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')

    svc = get_stripe_service()

    try:
        event = svc.construct_event(payload, sig_header)
    except ValueError as exc:
        logger.warning('stripe_webhook: invalid payload: %s', exc)
        return HttpResponse('Invalid payload', status=400)
    except Exception as exc:
        logger.warning('stripe_webhook: signature verification failed: %s', exc)
        return HttpResponse('Signature verification failed', status=400)

    try:
        svc.handle_webhook_event(event)
    except Exception:
        logger.exception('stripe_webhook: error handling event %s', event.type)
        return HttpResponse('Handler error', status=500)

    return HttpResponse('OK', status=200)
