from django.db import transaction
from django.db.models import F
from decimal import Decimal
from django.utils import timezone
from myapp.models import Product, Coupon
from .models import Order, OrderItem, OrderStatusEvent

# Exceptions
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

class InvalidCoupon(Exception):
    """Raised when the cart's coupon cannot be used at checkout"""
    pass

class InvalidStatusTransition(Exception):
    """Riased when an order cannot legally move to the requested status"""
    pass

class TrackingNumberRequired(Exception):
    """Raised when shipping an order without a tracking number"""
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

        coupon = cart.coupon
        subtotal = cart.get_subtotal()
        discount_amount = Decimal('0.00')
        coupon_code = ''

        if coupon is not None:
            # Lock the coupon row for this transaction
            try:
                locked_coupon = (
                    Coupon.objects.select_for_update().get(pk=coupon.pk)
                )
            except Coupon.DoesNotExist:
                raise InvalidCoupon('This coupon no longer exists')

            if not locked_coupon.is_currently_valid:
                raise InvalidCoupon('This coupon no longer exists')

            subtotal = cart.get_subtotal()
            if subtotal < locked_coupon.min_order_amount:
                raise InvalidCoupon(
                    f'This coupon require a minimum order of'
                    f"{locked_coupon.min_order_amount}"
                )

            if locked_coupon.one_per_user:
                if Order.objects.filter(
                    user=user, coupon_code=locked_coupon.code
                ).exists():
                    raise InvalidCoupon('You have already used this coupon')

            discount_amount = locked_coupon.calculate_discount(subtotal)
            coupon_code = locked_coupon.code

            # Atomically increment usage
            Coupon.objects.filter(pk=locked_coupon.pk).update(
                used_count=F('used_count') + 1
            )

        total_amount = (subtotal - discount_amount).quantize(
            Decimal('0.01')
        )

        order = Order.objects.create(
            user=user,
            subtotal_amount=subtotal,
            total_amount=total_amount,
            coupon_code=coupon_code,
            discount_amount=discount_amount,

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
            paid_price = product.get_effective_price()
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=requested,
                unit_price=paid_price,
                original_unit_price=product.price,
            )

    cart.clear()
    return order

def transition_order(order, new_status, changed_by=None, note='', tracking_number=''):
    """
    Move 'order' to 'new_status', recording the change as an OrderStatusEvent.
    """
    if new_status == order.status:
        return None

    if not order.can_transition_to(new_status):
        raise InvalidStatusTransition(
            f"Cannot move order #{order.pk} from '{order.status}' to '{new_status}'"
        )

    if new_status == Order.Status.SHIPPED and not tracking_number.strip():
        raise TrackingNumberRequired(
            'A tracking numbmer is required to mark an order as shipped'
        )

    old_status = order.status

    with transaction.atomic():
        # 1. Persist the status change on the order row
        order.status = new_status
        order.status_updated_at = timezone.now()
        update_fields = ['status', 'status_updated_at']

        if new_status == Order.Status.PAID:
            order.is_paied = True
            update_fields.append('is_paied')

        if new_status == Order.Status.SHIPPED and tracking_number:
            order.tracking_number = tracking_number.strip()
            update_fields.append('tracking_number')

        order.save(update_fields=update_fields)

        # 2. Restore stock if we're cancelling a not yet shipped order
        if new_status == Order.Status.CANCELLED:
            # Reload items to be safe
            for item in order.orderitem_set.all():
                Product.objects.filter(pk=item.product_id).update(
                    stock=F('stock') + item.quantity
                )

        # 3. Append the audit event.
        event = OrderStatusEvent.objects.create(
            order=order,
            from_status=old_status,
            to_status=new_status,
            changed_by=changed_by if (changed_by and changed_by.is_authenticated) else None,
            note=note.strip()
        )

    # Send a status-update email
    try:
        from .emails import send_status_update_email
        send_status_update_email(order, old_status, new_status)
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            f"Status update email failed for order #{order.pk}"
        )

    return event