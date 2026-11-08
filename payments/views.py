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
from .handlers import HANDLERS
from .models import StripeWebhookEvent
from .services import PaymentError, get_or_create_checkout_url

logger = logging.getLogger(__name__)

@require_POST
@login_required(login_url="users:login")
def pay_for_order(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    try:
        url = get_or_create_checkout_url(order.pk)
    except PaymentError as exc:
        messages.error(request, str(exc))
        return redirect('orders:order_detail', pk=order.pk)
    return HttpResponseRedirect(url, status=303)

@login_required(login_url='users:login')
def payment_success(request):
    """
    Cosmetic page. The webhook marks orders as paid
    """
    session_id = request.GET.get('session_id', '')
    if not session_id:
        raise Http404
    order = get_object_or_404(
        Order, stripe_checkout_session_id=session_id, user=request.user
    )

    # While the webhook hasn't arrived yet, re-check a few time automatically
    try:
        attempt = max(0, min(int(request.GET.get('n', 0)), 20))
    except ValueError:
        attempt = 0
    refresh_url = None
    if order.status == Order.Status.PENDING and attempt < 10:
        refresh_url = f"{request.path}?" + urlencode(
            {"session_id": session_id, "n": attempt + 1}
        )
    return render(request, 'payments/success.html',
                  {
                      'order': order,
                      'refresh_url': refresh_url
                  })

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
        return HttpResponse(status=200) # an event we don't care about

    try:
        with transaction.atomic():
            _, created = StripeWebhookEvent.objects.get_or_create(
                event_id=event['id'], defaults={'event_type': event['type']},
            )
            if created:
                handler(event['data']['object'])
    except Exception:
        # The transaction rolled back
        logger.exception(f"Stripe webhook {event['id']} ({event['type']})")
        return HttpResponse(status=500)
    return HttpResponse(status=200)

