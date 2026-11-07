import stripe
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import logging
from .models import Order
from .services import transition_order
from .emails import send_order_confirmation

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY

def _mark_order_paid(order, source):
    """
    Safely transition a PENDING order to PAID and
    send the confirmation email exactly once.
    """
    if order.status != Order.Status.PENDING:
        logger.info(
            f'Webhook {source}: order {order.pk} already {order.status} - Skipping'
        )
        return

    try:
        transition_order(
            order,
            Order.Status.PAID,
            changed_by=None,
            note=f"Payment confirmed by Stripe ({source})",
        )
        logger.info(f"Webhook {source}: order {order.pk} marked PAID")
    except Exception:
        logger.exception(
            f"Webhook {source}: failed to transition order {order.pk} to PAID"
        )
        raise

    try:
        send_order_confirmation(order, request=None)
    except Exception:
        # Email failuer must not break the payment state.
        logger.exception(
            f"Webhook {source}: confirmation email failed for {order.pk}"
        )


@csrf_exempt
@require_POST
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        logger.warning('Stripe webhook: invalid payload')
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        logger.warning('Stripe webhook: invalid signature')
        return HttpResponse(status=400)

    event_type = event['type']

    try:
        if event_type == 'payment_intent.succeeded':
            # Primary signal: The money is captured.
            intent = event['data']['object']
            order_id = (intent.metadata.order_id
                        if intent.metadata else None)
            if not order_id:
                logger.warning(
                    'payment_intent.succeeded: missing metadata.order_id '
                    f"on intent {intent.id}"
                )
                return HttpResponse(status=200)

            order = Order.objects.filter(pk=order_id).first()
            if not order:
                logger.warning(
                    f"payment_intent.succeeded: order {order_id} not found"
                )
                return HttpResponse(status=200)
            
            _mark_order_paid(order, source='payment_intent.succeeded')

        elif event_type == 'checkout.session.completed':
            # Secondary signal: checkout flow finished
            session = event['data']['object']

            if session.payment_status != 'paid':
                logger.info(
                    f"checkout.session.completed: session {session.id} not yet paid"
                    f"(status={session.payment_status}) - will wait for payment_intent.succeeded"
                )
                return HttpResponse(status=200)

            order_id = session.client_reference_id
            if not order_id and session.metadata:
                order_id = session.metadata.order_id

            if not order_id:
                logger.warning(
                    f"checkout.session.completed: no order_id on session {session.id}"
                )
                return HttpResponse(status=200)

            order = Order.objects.filter(pk=order_id).first()
            if not order:
                logger.warning(
                    f"checkout.session.completed: order {order_id} not found"
                )
                return HttpResponse(status=200)

            _mark_order_paid(order, source='checkout.session.completed')

        elif event_type in (
            "payment_intent.payment_failed",
            'checkout.session.async_payment_failed',
        ):
            logger.warning(f"Stripe {event_type} event received - payment failed")
    except Exception:
        logger.exception(f"Unhandled error processing Stripe event {event_type}")
        return HttpResponse(status=500)
    return HttpResponse(status=200)