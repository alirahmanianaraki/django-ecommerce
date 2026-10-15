from decimal import Decimal

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from myapp.models import Product
from orders.models import Order, OrderItem
from orders.services import InsufficientStock, place_order
from cart.cart import Cart


class PlaceOrderServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="alice", password="StrongPass123!"
        )
        cls.product = Product.objects.create(
            title="GPU", description="Graphics card",
            price=Decimal("250.00"), stock=10,
        )

    def make_cart(self, quantity):
        request = RequestFactory().get("/")
        request.session = self.client.session
        cart = Cart(request)
        cart.add(str(self.product.pk), str(quantity))
        return cart

    def test_place_order_decrements_stock(self):
        cart = self.make_cart(3)
        place_order(user=self.user, cart=cart)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 7)

    def test_place_order_creates_order_and_items(self):
        cart = self.make_cart(2)
        order = place_order(user=self.user, cart=cart)

        self.assertEqual(order.user, self.user)
        self.assertEqual(order.total_amount, Decimal("500.00"))

        item = OrderItem.objects.get(order=order)
        self.assertEqual(item.product, self.product)
        self.assertEqual(item.quantity, 2)

    def test_place_order_clears_the_cart(self):
        cart = self.make_cart(2)
        place_order(user=self.user, cart=cart)
        self.assertEqual(len(cart), 0)

    def test_place_order_rejects_empty_cart(self):
        cart = self.make_cart(0)   # cart.add with qty=0? Let's instead do:
        # Better: build a Cart with no items
        request = RequestFactory().get("/")
        request.session = self.client.session
        empty_cart = Cart(request)
        empty_cart.clear()

        with self.assertRaises(ValueError):
            place_order(user=self.user, cart=empty_cart)

        self.assertEqual(Order.objects.count(), 0)

    def test_place_order_raises_when_stock_insufficient(self):
        cart = self.make_cart(99)   # product only has 10

        with self.assertRaises(InsufficientStock) as ctx:
            place_order(user=self.user, cart=cart)

        self.assertEqual(ctx.exception.available, 10)
        self.assertEqual(ctx.exception.requested, 99)

        # Nothing should have been written.
        self.assertEqual(Order.objects.count(), 0)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

    def test_place_order_is_all_or_nothing_across_items(self):
        # Two products: one in stock, one not enough.
        other = Product.objects.create(
            title="RAM", description="Memory",
            price=Decimal("75.00"), stock=1,
        )
        request = RequestFactory().get("/")
        request.session = self.client.session
        cart = Cart(request)
        cart.add(str(self.product.pk), "2")   # OK
        cart.add(str(other.pk), "5")          # Not OK

        with self.assertRaises(InsufficientStock):
            place_order(user=self.user, cart=cart)

        # Neither product was decremented, no order was created.
        self.product.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(self.product.stock, 10)
        self.assertEqual(other.stock, 1)
        self.assertEqual(Order.objects.count(), 0)