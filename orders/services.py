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

class MissingShippingAddress(Exception):
    """Raised when a place_order call has no shipping address"""
    pass

def place_order(user, cart, address):
    """
    Create an Order for `user` from `cart`, snapshot the shipping `address`,
    decrement stock atomically, and empty the cart on success.
    """
    if address is None:
        raise MissingShippingAddress("No shipping address provided.")

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

            # Snapshot the address at the moment of ordering.
            shipping_title=address.title,
            shipping_full_name=address.full_name,
            shipping_description=address.description,
            shipping_city=address.city,
            shipping_state=address.state,
            shipping_postal_code=address.postal_code,
            shipping_country=address.country,
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
                unit_price=product.price,
            )

    cart.clear()

    return order