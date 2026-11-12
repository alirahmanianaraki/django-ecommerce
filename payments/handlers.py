import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from orders.emails import send_order_confirmation_safely
from orders.models import Order
from orders.services import transition_order
from .models import Refund
from .refunds import refund_order_to_wallet
from .services import to_minor_units
from . import topups

logger = logging.getLogger(__name__)


def _get_locked_order(session):
    """Find the order a Stripe session belongs to, and lock its row."""
    order_id = (session.get('metadata') or {}).get('order_id')
    if not order_id or not str(order_id).isdigit():
        logger.error(f"Stripe session {session.get('id')} has no order_id metadata")
        return None
    order = Order.objects.select_for_update().filter(pk=int(order_id)).first()
    if order is None:
        logger.error(f"Stripe session {session.get('id')} points to missing order {order_id}")
    return order


def handle_payment_succeeded(session):
    order = _get_locked_order(session)
    if order is None:
        return

    if session.get('payment_status') != 'paid':
        logger.info(f"Session {session.get('id')} completed but not paid yet; waiting")
        return

    if order.status not in (Order.Status.PENDING, Order.Status.CANCELLED):
        return  # already PAID or later: this event was handled before

    expected = to_minor_units(order.total_amount)
    currency = (session.get('currency') or '').lower()
    if session.get('amount_total') != expected or currency != settings.STRIPE_CURRENCY.lower():
        logger.error(
            f"AMOUNT MISMATCH on order {order.pk}: Stripe says "
            f"{session.get('amount_total')} {currency}, "
            f"we expected {expected} {settings.STRIPE_CURRENCY}."
        )
        return

    order.stripe_checkout_session_id = session['id']
    order.stripe_payment_intent_id = session.get('payment_intent') or ''
    order.paid_at = timezone.now()

    if order.status == Order.Status.CANCELLED:
        # The customer paid after we cancelled. Keep the order cancelled and
        # hand the money back as wallet credit.
        if order.is_paied:
            logger.error(
                f"DUPLICATE PAYMENT on already-paid order {order.pk} "
                f"(session {session['id']}). Manual review needed."
            )
            return
        order.is_paied = True
        order.save(update_fields=[
            'stripe_checkout_session_id', 'stripe_payment_intent_id', 'paid_at', 'is_paied',
        ])
        refund_order_to_wallet(
            order.pk, reason=Refund.Reason.LATE_PAYMENT,
            note=f"Payment received after order #{order.pk} was cancelled",
        )
        logger.warning(f"Late payment on cancelled order {order.pk} credited to wallet")
        return

    order.save(update_fields=[
        'stripe_checkout_session_id', 'stripe_payment_intent_id', 'paid_at',
    ])
    transition_order(order, Order.Status.PAID, note='Payment received via Stripe')

    pk = order.pk
    transaction.on_commit(lambda: send_order_confirmation_safely(pk))


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
    _cancel_if_current(session, 'Payment not completed in time (checkout expired)')


def _is_topup(session):
    return (session.get('metadata') or {}).get('type') == 'wallet_topup'

def _on_payment_succeeded(session):
    if _is_topup(session):
        topups.complete_topup(session)
    else:
        handle_payment_succeeded(session)

def _on_payment_failed(session):
    if _is_topup(session):
        topups.fail_topup(session)
    else:
        handle_payment_failed(session)

def _on_session_expired(session):
    if _is_topup(session):
        topups.expire_topup(session)
    else:
        handle_session_expired(session)

HANDLERS = {
    "checkout.session.completed": _on_payment_succeeded,
    "checkout.session.async_payment_succeeded": _on_payment_succeeded,
    "checkout.session.async_payment_failed": _on_payment_failed,
    "checkout.session.expired": _on_session_expired,
}