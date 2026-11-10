from django.db import transaction
from django.utils import timezone
from orders.emails import send_order_confirmation_safely
from orders.models import Order
from orders.services import transition_order
from wallets.models import WalletTransaction
from wallets.services import InsufficientFunds, WalletError, debit
from .services import PaymentError, expire_checkout_session

@transaction.atomic
def pay_order_with_wallet(order_id, *, actor):
    """
    Pay a pending order from the owner's wallet.
    """
    order = Order.objects.select_for_update().get(pk=order_id)

    if order.status != Order.Status.PENDING:
        raise PaymentError('This order can no longer be paid.')

    try:
        debit(
            user=order.user, amount=order.total_amount,
            kind=WalletTransaction.Kind.PURCHASE,
            reference=f"purchase:{order.pk}", order=order,
            note=f"Payment for order #{order.pk}", created_by=actor
        )
    except InsufficientFunds:
        raise PaymentError('Your wallet balance is too low for this order.')
    except WalletError:
        raise PaymentError("We couldn't use your wallet for this order")

    # Close any Stripe payment page, or the customer could pay twice
    expire_checkout_session(order)

    order.paid_at = timezone.now()
    order.save(update_fields=['paid_at'])
    transition_order(order, Order.Status.PAID, note='Paid with wallet balance')

    pk = order.pk
    transaction.on_commit(lambda: send_order_confirmation_safely(pk))
    return order