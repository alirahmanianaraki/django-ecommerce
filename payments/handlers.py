import logging
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from orders.emails import send_order_confirmation
from orders.models import Order
from orders.services import transition_order
from .services import to_minor_units

logger = logging.getLogger(__name__)

def _get_locked_order(session):
    """
    Find the order a Stripe session belongs to, and lock its row
    """
    order_id = (session.get('metadata') or {}).get('order_id')
    if not order_id or not str(order_id).isdigit():
        logger.error(f"Stripe session {session.get('id')} has no order_id metadata")
        return None
    order = Order.objects.select_for_update().filter(pk=int(order_id)).first()
    if order is None:
        logger.error(f"Stripe session {session.get('id')} points to missing order {order_id}")
    return order

def _send_confirmation(order_pk):
    try:
        order = Order.objects.select_related('user').get(pk=order_pk)
        send_order_confirmation(order)
    except Exception:
        logger.exception(f"Order confirmation email failed for order {order_pk}")

def handle_payment_succeeded(session):
    order = _get_locked_order(session)
    if order is None:
        return

    if session.get('payment_status') != 'paid':
        logger.info(f"Session {session.get('id')} completed but not paid yet; waiting")
        return

    if order.status != Order.Status.PENDING:
        if order.status == Order.Status.CANCELLED:
            logger.error(
                f"MONEY RECEIVED FOR CANCELLED ORDER {order.pk} (session {session.get('id')}, payment_intent {session.get("payment_intent")}). A REFUND IS NEEDED."
            )
        return

    expected = to_minor_units(order.total_amount)
    currency = (session.get("currency") or "").lower()
    if session.get('amount_total') != expected or currency != settings.STRIPE_CURRENCY.lower():
        logger.error(
            f"AMOUNT MISMATCH on order {order.pk}: Stripe says {session.get("amount_total")} {currency}, we expected {expected} {settings.STRIPE_CURRENCY}."
        )
        return

    order.stripe_checkout_session_id = session['id']
    order.stripe_payment_intent_id = session.get('payment_intent') or ""
    order.paid_at = timezone.now()
    order.save(update_fields=[
        'stripe_checkout_session_id', 'stripe_payment_intent_id', 'paid_at'
    ])
    transition_order(order, Order.Status.PAID, note='Payment received via Stripe')

    pk = order.pk
    transaction.on_commit(lambda: _send_confirmation(pk))

def _cancel_if_current(session, note):
    order = _get_locked_order(session)
    if order is None or order.status != Order.Status.PENDING:
        return
    if order.stripe_checkout_session_id != session.get('id'):
        logger.info(f"Ignoring stale session {session.get('id')} for order {order.pk}")
        return
    transition_order(order, Order.Status.CANCELLED, note=note)

def handle_payment_failed(session):
    _cancel_if_current(session, 'Delayed payment failed')

def handle_session_expired(session):
    _cancel_if_current(session, "Payment not completed in time (checkout expired)")

HANDLERS = {
    "checkout.session.completed": handle_payment_succeeded,
    "checkout.session.async_payment_succeeded": handle_payment_succeeded,
    "checkout.session.async_payment_failed": handle_payment_failed,
    "checkout.session.expired": handle_session_expired,
}