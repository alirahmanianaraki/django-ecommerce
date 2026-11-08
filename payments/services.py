import logging
import time
from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.urls import reverse
from stripe import StripeClient, StripeError
from orders.models import Order

logger = logging.getLogger(__name__)

class PaymentError(Exception):
    """
    A payment problem whose message is safe to show to the customer
    """

def get_stripe_client():
    if not settings.STRIPE_SECRET_KEY:
        raise ImproperlyConfigured('STRIPE_SECRET_KEY is not set')
    return StripeClient(settings.STRIPE_SECRET_KEY)

def to_minor_units(amount):
    return int((Decimal(amount) * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))

def _build_session_params(order, client):
    currency = settings.STRIPE_CURRENCY.lower()
    site_url = settings.SITE_URL.rstrip('/')
    if not site_url:
        raise ImproperlyConfigured('SITE_URL is not set')

    items = list(order.orderitem_set.select_related('product'))
    if not items:
        raise PaymentError('This order has no items')

    line_items = []
    subtotal_cents = 0
    for item in items:
        unit_cents = to_minor_units(item.unit_price)
        subtotal_cents += unit_cents * item.quantity
        line_items.append({
            'quantity': item.quantity,
            'price_data': {
                'currency': currency,
                'unit_amount': unit_cents,
                'product_data': {'name': item.product.title},
            },
        })
    discount_cents = to_minor_units(order.discount_amount)

    # Safety net
    if subtotal_cents - discount_cents != to_minor_units(order.total_amount):
        logger.error(f"Order {order.pk} total do not add up; refusing to charge")
        raise PaymentError("We couldn't verify the order total. Please contact support")

    params = {
        'mode': 'payment',
        'line_items': line_items,
        'client_reference_id': str(order.pk),
        'metadata': {'order_id': str(order.pk)},
        'payment_intent_data': {'metadata': {'order_id': str(order.pk)}},
        'success_url': (site_url + reverse('payments:success')
                        + "?session_id={CHECKOUT_SESSION_ID}"),
        'cancel_url': site_url + reverse('orders:order_detail', 
                                         kwargs={'pk': order.pk}),
        'expires_at': int(time.time()) + settings.STRIPE_CHECKOUT_EXPIRES_MINUTES * 60,
    }
    if order.user.email:
        params['customer_email'] = order.user.email

    if discount_cents > 0:
        coupon = client.v1.coupons.create({
            'amount_off': discount_cents,
            'currency': currency,
            'duration': 'once',
            'max_redemptions': 1,
            'name': f"Coupon {order.coupon_code}"[:40],
        })
        params['discounts'] = [{'coupon': coupon.id}]

    return params

def get_or_create_checkout_url(order_id):
    """
    Return the Stripe-hosted payment page URL for a pending order.
    """
    client = get_stripe_client()
    with transaction.atomic():
        # Lock this order row so two simultaneous clicks run one after another.
        order = Order.objects.select_for_update().get(pk=order_id)

        if order.status != Order.Status.PENDING:
            raise PaymentError('This order can no longer be paid')

        if order.stripe_checkout_session_id:
            try:
                existing = client.v1.checkout.sessions.retrieve(
                    order.stripe_checkout_session_id
                )
            except StripeError:
                logger.exception(f"Could not retrieve session for order {order.pk}")
                raise PaymentError("We couldn't reach our payment provider. Please try again")

            if existing.status == 'open' and existing.url:
                return existing.url
            if existing.status == "complete":
                raise PaymentError("Your payment is being confirmed. Please check back in a minute")

        try:
            session = client.v1.checkout.sessions.create(
                _build_session_params(order, client)
            )
        except StripeError:
            logger.exception(f"Stripe session creation failed for order {order.pk}")
            raise PaymentError("We couldn't start the payment. Please try again")

        order.stripe_checkout_session_id = session.id
        order.save(update_fields=['stripe_checkout_session_id'])
        return session.url

def expire_checkout_session(order):
    """
    Close the payment page of a pending order so it can't be paid after we cancel.
    """
    session_id = order.stripe_checkout_session_id
    if not session_id:
        return

    client = get_stripe_client()
    try:
        client.v1.checkout.sessions.expire(session_id)
    except StripeError:
        try:
            status = client.v1.checkout.sessions.retrieve(session_id).status
        except StripeError:
            raise PaymentError("We couldn't reach our payment provider. Please try again.")
        if status != 'expired':
            raise PaymentError(
                "Your payment is being processed, so this order can't be cancelled right now"
            )