from django.db import transaction
from django.db.models import F

from myapp.models import Product

from .models import Order, OrderItem


class InsufficientStock(Exception):
    """Raised when a cart line asks for more units than are in stock."""

    def __init__(self, product, requested, available):
        self.product = product
        self.requested = requested
        self.available = available
        super().__init__(
            f"Only {available} of '{product.title}' in stock (you asked for {requested})."
        )


def place_order(user, cart):
    """
    Create an Order for `user` from `cart`, decrement stock atomically, and
    empty the cart on success.
    """
    items = list(cart)
    if not items:
        raise ValueError("Cannot place an order from an empty cart.")

    product_ids = sorted(item['product'].pk for item in items)

    with transaction.atomic():
        locked = (
            Product.objects
            .select_for_update()
            .filter(pk__in=product_ids)
            .order_by('pk')
        )
        products_by_pk = {p.pk: p for p in locked}

        for item in items:
            product = products_by_pk[item['product'].pk]
            requested = int(item['qty'])
            if product.stock < requested:
                raise InsufficientStock(product, requested, product.stock)

        order = Order.objects.create(
            user=user,
            total_amount=cart.get_total_price(),
        )

        for item in items:
            product = products_by_pk[item['product'].pk]
            requested = int(item['qty'])

            Product.objects.filter(pk=product.pk).update(
                stock=F('stock') - requested
            )

            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=requested,
            )

    cart.clear()

    return order