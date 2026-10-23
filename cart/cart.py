from myapp.models import Product
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal

class Cart():
    def __init__(self, request):
        self.session = request.session
        cart = request.session.get('cart')
        if 'cart' not in request.session:
            cart = self.session['cart'] = {}
        self.cart = cart

    def _get_coupon(self):
        """
        Read the coupon code from the session
        and fetch the coupon
        """
        code = self.session.get('coupon_code')
        if not code:
            return None
        # Local import
        from myapp.models import Coupon
        try:
            return Coupon.objects.get(code=code)
        except Coupon.DoesNotExist:
            # Code was deleted from the DB while in the cart - clean up
            self.session.pop('coupon_code', None)
            self.session.modified = True
            return None

    @property
    def coupon(self):
        """
        The currently attached Coupon instance (or None)
        """
        if not hasattr(self, '_coupon_cache'):
            self._coupon_cache = self._get_coupon()
        return self._coupon_cache

    def get_subtotal(self):
        """Raw sum of cart lines, Before any discount"""
        return self.get_total_price()

    def get_discount_amount(self):
        """Dollar amount the coupon knocks off the subtotal"""
        coupon = self.coupon
        if not coupon:
            return Decimal('0.00')
        return coupon.calculate_discount(self.get_subtotal())

    def get_total_after_discount(self):
        """Final total the customer pays (before shipping)"""
        return (self.get_subtotal() - self.get_discount_amount()).quantize(Decimal('0.01'))

    def _validate_coupon_for_cart(self, coupon, user):
        """
        Raise validationError if the coupon can't be used on the current cart
        """
        if not coupon.is_currently_valid:
            if not coupon.is_active:
                raise ValidationError('This coupon is no longer active')
            now = timezone.now()
            if coupon.valid_from and now < coupon.valid_from:
                raise ValidationError('This coupon is not valid yet')
            if coupon.valid_until and now > coupon.valid_until:
                raise ValidationError('This coupon has expired')
            if coupon.max_uses is not None and coupon.used_count >= coupon.max_uses:
                raise ValidationError('This coupon has reached its usage limit')

        subtotal = self.get_subtotal()
        if subtotal < coupon.min_order_amount:
            raise ValidationError(
                f"This coupon requires a minimum order of {coupon.min_order_amount}"
            )

        if coupon.one_per_user:
            if user is None or not getattr(user, 'is_authenticated', False):
                raise ValidationError(
                    'You must be logged in to use this coupon'
                )
            # Local import
            from orders.models import Order
            already_used = Order.objects.filter(
                user=user,
                coupon_code=coupon.code,
            ).exists()
            if already_used:
                raise ValidationError('You have already used this coupon')

    def apply_coupon(self, code, user):
        """
        Validate 'code' against the current cart and user, then store
        it in the session.
        """
        # Local import
        from myapp.models import Coupon
        code = (code or '').strip().upper()
        if not code:
            raise ValidationError('Please enter a coupon code')
        try:
            coupon = Coupon.objects.get(code=code)
        except Coupon.DoesNotExist:
            raise ValidationError('Invalid coupon code')

        self._validate_coupon_for_cart(coupon, user)
        self.session['coupon_code'] = coupon.code
        self.session.modified = True
        # Invalidate the cache so next access re-fetches
        self._coupon_cache = coupon
        return coupon

    def remove_coupon(self):
        """
        Detach the coupon from the cart
        """
        if 'coupon_code' in self.session:
            self.session.pop('coupon_code')
            self.session.modified = True
        self._coupon_cache = None

    def __len__(self):
        return sum(int(item['qty']) for item in self.cart.values())

    def __iter__(self):
        product_ids = self.cart.keys()
        products = Product.objects.filter(id__in=product_ids)
        # Shallow copy of the top-level mapping
        cart = self.cart.copy()
        # Deep-copy each entry so we never mutate the session dict
        cart = {k: dict(v) for k, v in cart.items()}

        for product in products:
            cart[str(product.id)]['product'] = product

        for item in cart.keys():
            entry = cart[item]
            product = entry['product']
            original_price = Decimal(entry['price'])
            qty = Decimal(entry['qty'])
            current_unit_price = product.get_effective_price()
            entry['original_price'] = original_price
            entry['price'] = current_unit_price
            entry['has_discount'] = product.has_discount
            entry['discount_per_unit'] = (original_price - current_unit_price) \
                if product.has_discount else Decimal('0.00')
            entry['qty'] = qty
            entry['total'] = (current_unit_price * qty).quantize(Decimal('0.01'))
            yield entry

    def get_total_price(self):
        """
        Live subtotal: sum of (effective price * qty) for every line
        """
        return sum(
            (item['total'] for item in self),
            Decimal('0.00'),
        )

    def add(self, product_id, product_quantity):
        product = Product.objects.get(pk=product_id)
        if product_id in self.cart:
            self.cart[product_id]['qty'] = product_quantity
        else:
            self.cart[product_id] = {
                'price': str(product.price),
                'qty': product_quantity
            }
        print(f'Cart pID {product_id}')
        self.session.modified = True

    def update(self, product_id, product_quantity):
        product_id = str(product_id)
        if product_id in self.cart:
            self.cart[product_id]['qty'] = product_quantity
            self.session.modified = True

    def delete(self, product_id):
        product_id = str(product_id)
        if product_id in self.cart:
            del self.cart[product_id]
            self.session.modified = True

    def clear(self):
        """Empty the cart and mark the session as modified"""
        self.session['cart'] = {}
        self.session.pop('coupon_code', None)
        self.cart = self.session['cart']
        self.session.modified = True
        

