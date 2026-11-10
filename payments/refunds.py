import logging
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from orders.models import Order
from orders.services import transition_order
from wallets.models import WalletTransaction
from wallets.services import WalletError, credit, to_money
from .models import Refund
from .services import expire_checkout_session

logger = logging.getLogger(__name__)

class RefundError(Exception):
    """
    A refund/cancel problem whose message is safe to show to the user
    """

@transaction.atomic
def refund_order_to_wallet(order_id, *, reason, amount=None, note='', created_by=None):
    """
    Credit an order's price to the customer's wallet.
    """
    # Lock order
    order = Order.objects.select_for_update().get(pk=order_id)
    if not order.is_paied:
        raise RefundError('This order was never paid, there is nothing to refund.')

    already = order.refunds.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    remaining = order.total_amount - already

    if amount is None:
        if remaining <= 0:
            return None
        amount = remaining
    else:
        try:
            amount = to_money(amount)
        except WalletError as exc:
            raise RefundError(str(exc))
        if amount <= 0:
            raise RefundError('The refund amount must be greater than zero')
        if amount > remaining:
            raise RefundError(f"At most {remaining} can still be refunded on this order.")

    sequence = order.refunds.count() + 1
    txn, _ = credit(
        user=order.user, amount=amount, kind=WalletTransaction.Kind.REFUND,
        reference=f"refund:{order.pk}:{sequence}", order=order,
        note=note or f"Refund for order #{order.pk}", created_by=created_by,
    )
    return Refund.objects.create(
        order=order, amount=amount, destination=Refund.Destination.WALLET,
        reason=reason, note=note[:255], wallet_transaction=txn, created_by=created_by
    )

@transaction.atomic
def cancel_order_and_refund(order_id, *, actor, reason, note, staff=False):
    """
    Cancel an order and, if it was paid, return the money to the wallet.
    """
    order = Order.objects.select_for_update().get(pk=order_id)
    allowed = order.is_cancellable if staff else order.is_customer_cancellable 
    if not allowed:
        raise RefundError(
            'This order can no longer be cancelled online. Please contact support.'
            if not staff else
            f"Order #{order.pk} cannot be cancelled from status '{order.status}'."
    )

    refund = None
    if order.status == Order.Status.PENDING:
        expire_checkout_session(order)
    else:
        refund = refund_order_to_wallet(order.pk, reason=reason, note=note, created_by=actor)

    transition_order(order, Order.Status.CANCELLED, changed_by=actor, note=note)
    return refund
