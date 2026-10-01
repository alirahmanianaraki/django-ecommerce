from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from myapp.models import Product
from orders.models import Order, OrderItem
from users.models import Address


class OrderViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="alice", email="alice@example.com", password="StrongPass123!"
        )
        cls.product = Product.objects.create(
            title="GPU", description="Graphics card", price=Decimal("250.00"), stock=10
        )

    def setUp(self):
        self.client.force_login(self.user)

    def add_cart_item(self, quantity="2"):
        session = self.client.session
        session["cart"] = {
            str(self.product.pk): {"price": str(self.product.price), "qty": quantity}
        }
        session.save()

    def test_checkout_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("orders:checkout"))
        self.assertRedirects(response, reverse("users:register"))

    def test_checkout_renders_for_authenticated_user(self):
        response = self.client.get(reverse("orders:checkout"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "orders/checkout.html")
        self.assertEqual(response.context["cart_length"], 0)

    def test_checkout_includes_first_address(self):
        Address.objects.create(
            user=self.user,
            title="Home",
            full_name="Alice Smith",
            description="123 Main Street",
            city="Amsterdam",
            state="North Holland",
            postal_code="1011AA",
            country="Netherlands",
        )
        response = self.client.get(reverse("orders:checkout"))
        self.assertEqual(response.context["address"].city, "Amsterdam")

    def test_place_order_rejects_empty_cart(self):
        response = self.client.post(reverse("orders:place_order"))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["success"], False)
        self.assertEqual(response.json()["redirect"], "index")
        self.assertEqual(Order.objects.count(), 0)

    def test_place_order_rejects_anonymous_user(self):
        self.client.logout()
        self.add_cart_item()   # inject cart into the now-anonymous session
        response = self.client.post(reverse("orders:place_order"))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["success"], False)
        self.assertEqual(response.json()["redirect"], "register")
        self.assertEqual(Order.objects.count(), 0)

    def test_place_order_creates_order_and_items(self):
        self.add_cart_item("2")
        response = self.client.post(reverse("orders:place_order"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"success": True})

        order = Order.objects.get(user=self.user)
        self.assertEqual(order.total_amount, Decimal("500.00"))
        item = OrderItem.objects.get(order=order)
        self.assertEqual(item.product, self.product)
        self.assertEqual(item.quantity, 2)
