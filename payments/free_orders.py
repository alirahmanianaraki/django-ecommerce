from django.db import transaction
from django.utils import timezone

from orders.emails import send_order_confirmation_safely
from orders.models import Order
from orders.services import transition_order
from .services import PaymentError, expire_checkout_session

@transaction.atomic
def pay_free_order(order_id, *, actor):
    """
    Confirm an order whose total is exactly zero (e.g. a 100% coupon).
    """
    order = Order.objects.select_for_update().get(pk=order_id)

    if order.status != Order.Status.PENDING:
        raise PaymentError('This order can no longer be paid')
    if order.total_amount != 0:
        raise PaymentError('This order still has an amount to pay')

    expire_checkout_session(order)

    order.paid_at = timezone.now()
    order.save(update_fields=['paid_at'])
    transition_order(order, Order.Status.PAID, changed_by=actor,
                     note='No payment needed (order total is zero)')
    pk = order.pk
    transaction.on_commit(lambda: send_order_confirmation_safely(pk))
    return order