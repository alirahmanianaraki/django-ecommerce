from decimal import Decimal
from django.test import TestCase

from cart.cart import Cart
from myapp.models import Coupon, Product
from orders.models import Order
from orders.services import InvalidCoupon, place_order
from users.models import Address
from django.contrib.auth.models import User
from django.test import RequestFactory


class CouponServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="alice", password="StrongPass123!"
        )
        cls.product = Product.objects.create(
            title="GPU", description="x",
            price=Decimal("100.00"), stock=10,
        )
        cls.percent_coupon = Coupon.objects.create(
            code="SAVE10", discount_type="percent", value=Decimal("10"),
        )
        cls.fixed_coupon = Coupon.objects.create(
            code="TENOFF", discount_type="fixed", value=Decimal("10"),
        )

    def setUp(self):
        self.address = Address.objects.create(
            user=self.user, title="Home", full_name="Alice",
            description="1 Main", city="Ams", state="NH",
            postal_code="1011", country="NL",
        )

    def make_cart(self, qty="2"):
        request = RequestFactory().get("/")
        request.session = self.client.session
        cart = Cart(request)
        cart.add(str(self.product.pk), qty)
        return cart

    def test_percent_discount(self):
        cart = self.make_cart("2")     # subtotal = 200
        cart.apply_coupon("SAVE10", user=self.user)
        self.assertEqual(cart.get_discount_amount(), Decimal("20.00"))
        self.assertEqual(cart.get_total_after_discount(), Decimal("180.00"))

    def test_fixed_discount(self):
        cart = self.make_cart("2")
        cart.apply_coupon("TENOFF", user=self.user)
        self.assertEqual(cart.get_discount_amount(), Decimal("10.00"))

    def test_fixed_discount_never_below_zero(self):
        cart = self.make_cart("1")     # subtotal = 100
        big = Coupon.objects.create(
            code="BIG", discount_type="fixed", value=Decimal("500"),
        )
        cart.apply_coupon("BIG", user=self.user)
        self.assertEqual(cart.get_discount_amount(), Decimal("100.00"))

    def test_lowercase_code_is_accepted(self):
        cart = self.make_cart("1")
        cart.apply_coupon("save10", user=self.user)
        self.assertEqual(cart.coupon.code, "SAVE10")

    def test_min_order_amount_rejects(self):
        cheap = Coupon.objects.create(
            code="MIN50", discount_type="fixed", value=Decimal("5"),
            min_order_amount=Decimal("50"),
        )
        cart = self.make_cart("1")  # subtotal 100 → OK
        cart.apply_coupon("MIN50", user=self.user)
        # now try with an empty-ish cart scenario; drop quantity to force below min
        cart.add(str(self.product.pk), "0.5")  # subtotal 50  → still OK
        # For below-min we'd need a cheaper product; use a real one:
        small = Product.objects.create(
            title="Cable", description="x",
            price=Decimal("10"), stock=5,
        )
        new_request = RequestFactory().get("/")
        new_request.session = self.client.session
        new_cart = Cart(new_request)
        new_cart.add(str(small.pk), "1")   # subtotal 10
        with self.assertRaises(Exception):
            new_cart.apply_coupon("MIN50", user=self.user)

    def test_place_order_snapshots_discount(self):
        cart = self.make_cart("2")
        cart.apply_coupon("SAVE10", user=self.user)
        order = place_order(user=self.user, cart=cart, address=self.address)

        self.assertEqual(order.discount_amount, Decimal("20.00"))
        self.assertEqual(order.coupon_code, "SAVE10")
        self.assertEqual(order.total_amount, Decimal("180.00"))

    def test_place_order_increments_used_count(self):
        cart = self.make_cart("2")
        cart.apply_coupon("SAVE10", user=self.user)
        place_order(user=self.user, cart=cart, address=self.address)
        self.percent_coupon.refresh_from_db()
        self.assertEqual(self.percent_coupon.used_count, 1)

    def test_place_order_rejects_expired_coupon(self):
        from datetime import timedelta
        from django.utils import timezone

        # 1. Customer applies the coupon while it's still valid.
        cart = self.make_cart("2")
        cart.apply_coupon("SAVE10", user=self.user)
        self.assertEqual(cart.coupon.code, "SAVE10")   # sanity check

        # 2. Time passes. The coupon expires AFTER it was applied.
        self.percent_coupon.valid_until = timezone.now() - timedelta(days=1)
        self.percent_coupon.save()

        # 3. The customer hits "Place Order".
        #    place_order must re-check and reject.
        with self.assertRaises(InvalidCoupon):
            place_order(user=self.user, cart=cart, address=self.address)

        # Nothing was created, nothing was charged, stock unchanged.
        self.assertEqual(Order.objects.count(), 0)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)