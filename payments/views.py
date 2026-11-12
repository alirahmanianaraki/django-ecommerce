import json
import logging
import stripe
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from orders.models import Order
from wallets.services import get_balance
from .free_orders import pay_free_order
from .handlers import HANDLERS
from .models import StripeWebhookEvent, TopUp
from .services import PaymentError, get_or_create_checkout_url
from .topups import TopUpError, start_topup
from .wallet_payment import pay_order_with_wallet

logger = logging.getLogger(__name__)

def _refresh_url(request, session_id, still_waiting):
    """
    URL for the 'check again in 3 seconds' loop (max 10 attempts), or None.
    """
    if not still_waiting:
        return None
    try:
        attempt = max(0, min(int(request.GET.get('n', 0)), 20))
    except ValueError:
        attempt = 0
    if attempt >= 10:
        return None
    return f"{request.path}?" + urlencode({'session_id': session_id, 'n': attempt + 1})

def _confirm_free_order(request, order):
    try:
        pay_free_order(order.pk, actor=request.user)
    except PaymentError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"Order #{order.pk} is confirmed. No payment was needed.")
    return redirect('orders:order_detail', pk=order.pk)

@require_POST
@login_required(login_url='users:login')
def pay_for_order(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    if order.total_amount == 0:
        return _confirm_free_order(request, order)
    try:
        url = get_or_create_checkout_url(order.pk)
    except PaymentError as exc:
        messages.error(request, str(exc))
        return redirect('orders:order_detail', pk=order.pk)
    return HttpResponseRedirect(url, status=303)

@require_POST
@login_required(login_url='users:login')
def pay_with_wallet(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    if order.total_amount == 0:
        return _confirm_free_order(request, order)
    try:
        pay_order_with_wallet(order.pk, actor=request.user)
    except PaymentError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"Order #{order.pk} is paid. Thank you!")
    return redirect('orders:order_detail', pk=order.pk)

@login_required(login_url='users:login')
def payment_success(request):
    """
    Cosmetic page.
    """
    session_id = request.GET.get('session_id', '')
    if not session_id:
        raise Http404
    order = get_object_or_404(
        Order, stripe_checkout_session_id=session_id, user=request.user
    )
    waiting = order.status == Order.Status.PENDING
    return render(request, 'payments/success.html',
                  {
                      'order': order,
                      'refresh_url': _refresh_url(request, session_id, waiting),
                  })

# ------------------------------------- top-ups
@require_POST
@login_required(login_url='users:login')
def start_topup_view(request):
    try:
        url = start_topup(request.user, request.POST.get('amount', ''))
    except TopUpError as exc:
        messages.error(request, str(exc))
        return redirect('wallets:overview')
    return HttpResponseRedirect(url, status=303)

@login_required(login_url='users:login')
def topup_success(request):
    """
    Cosmetic page.
    """
    session_id = request.GET.get('session_id', '')
    if not session_id:
        raise Http404
    topup = get_object_or_404(
        TopUp, stripe_checkout_session_id=session_id, user=request.user
    )
    waiting = topup.status == TopUp.Status.PENDING
    return render(request, 'payments/topup_success.html',
                  {
                      'topup': topup,
                      'balance': get_balance(request.user),
                      'refresh_url': _refresh_url(request, session_id, waiting),
                  })

# ------------------------------------- Webhook
@csrf_exempt
@require_POST
def stripe_webhook(request):
    if not settings.STRIPE_WEBHOOK_SECRET:
        logger.error('STRIPE_WEBHOOK_SECRET is not configured')
        return HttpResponse(status=500)

    payload = request.body
    signature = request.headers.get('Stripe-Signature', '')

    try:
        stripe.Webhook.construct_event(payload, signature, settings.STRIPE_WEBHOOK_SECRET)
    except ValueError:
        return HttpResponse(status=400)
    except stripe.SignatureVerificationError:
        logger.warning('Stripe webhook with invalid signature')
        return HttpResponse(status=400)

    event = json.loads(payload)
    handler = HANDLERS.get(event['type'])
    if handler is None:
        return HttpResponse(status=200)

    try:
        with transaction.atomic():
            _, created = StripeWebhookEvent.objects.get_or_create(
                event_id=event['id'], defaults={'event_type': event['type']},
            )
            if created:
                handler(event['data']['object'])
    except Exception:
        logger.exception(f"Stripe webhook {event['id']} ({event['type']} failed)")
        return HttpResponse(status=500)
    return HttpResponse(status=200)