from decimal import Decimal

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from cart.cart import Cart
from myapp.models import Product
from orders.models import Order, OrderItem
from orders.services import (
    InsufficientStock,
    MissingShippingAddress,
    place_order,
)
from users.models import Address


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

    def setUp(self):
        self.address = Address.objects.create(
            user=self.user,
            title="Home",
            full_name="Alice Smith",
            description="123 Main Street",
            city="Amsterdam",
            state="North Holland",
            postal_code="1011AA",
            country="Netherlands",
        )

    def make_cart(self, quantity):
        request = RequestFactory().get("/")
        request.session = self.client.session
        cart = Cart(request)
        cart.add(str(self.product.pk), str(quantity))
        return cart

    def make_empty_cart(self):
        request = RequestFactory().get("/")
        request.session = self.client.session
        cart = Cart(request)
        cart.clear()
        return cart

    def test_place_order_decrements_stock(self):
        cart = self.make_cart(3)
        place_order(user=self.user, cart=cart, address=self.address)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 7)

    def test_place_order_creates_order_and_items(self):
        cart = self.make_cart(2)
        order = place_order(user=self.user, cart=cart, address=self.address)

        self.assertEqual(order.user, self.user)
        self.assertEqual(order.total_amount, Decimal("500.00"))

        item = OrderItem.objects.get(order=order)
        self.assertEqual(item.product, self.product)
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.unit_price, Decimal("250.00"))

    def test_place_order_snapshots_shipping_address(self):
        cart = self.make_cart(1)
        order = place_order(user=self.user, cart=cart, address=self.address)

        self.assertEqual(order.shipping_title, "Home")
        self.assertEqual(order.shipping_full_name, "Alice Smith")
        self.assertEqual(order.shipping_description, "123 Main Street")
        self.assertEqual(order.shipping_city, "Amsterdam")
        self.assertEqual(order.shipping_state, "North Holland")
        self.assertEqual(order.shipping_postal_code, "1011AA")
        self.assertEqual(order.shipping_country, "Netherlands")

    def test_place_order_snapshot_survives_address_deletion(self):
        cart = self.make_cart(1)
        order = place_order(user=self.user, cart=cart, address=self.address)

        self.address.delete()
        order.refresh_from_db()

        self.assertEqual(order.shipping_city, "Amsterdam")
        self.assertEqual(order.shipping_full_name, "Alice Smith")

    def test_place_order_clears_the_cart(self):
        cart = self.make_cart(2)
        place_order(user=self.user, cart=cart, address=self.address)
        self.assertEqual(len(cart), 0)

    def test_place_order_rejects_empty_cart(self):
        empty_cart = self.make_empty_cart()

        with self.assertRaises(ValueError):
            place_order(user=self.user, cart=empty_cart, address=self.address)

        self.assertEqual(Order.objects.count(), 0)

    def test_place_order_rejects_missing_address(self):
        cart = self.make_cart(1)

        with self.assertRaises(MissingShippingAddress):
            place_order(user=self.user, cart=cart, address=None)

        self.assertEqual(Order.objects.count(), 0)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

    def test_place_order_raises_when_stock_insufficient(self):
        cart = self.make_cart(99)

        with self.assertRaises(InsufficientStock) as ctx:
            place_order(user=self.user, cart=cart, address=self.address)

        self.assertEqual(ctx.exception.available, 10)
        self.assertEqual(ctx.exception.requested, 99)

        self.assertEqual(Order.objects.count(), 0)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

    def test_place_order_is_all_or_nothing_across_items(self):
        other = Product.objects.create(
            title="RAM", description="Memory",
            price=Decimal("75.00"), stock=1,
        )
        request = RequestFactory().get("/")
        request.session = self.client.session
        cart = Cart(request)
        cart.add(str(self.product.pk), "2")
        cart.add(str(other.pk), "5")

        with self.assertRaises(InsufficientStock):
            place_order(user=self.user, cart=cart, address=self.address)

        self.product.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(self.product.stock, 10)
        self.assertEqual(other.stock, 1)
        self.assertEqual(Order.objects.count(), 0)