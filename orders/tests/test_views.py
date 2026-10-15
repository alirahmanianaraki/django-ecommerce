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

    def add_cart_item(self, quantity="2"):
        session = self.client.session
        session["cart"] = {
            str(self.product.pk): {"price": str(self.product.price), "qty": quantity}
        }
        session.save()

    # ------------------------------------------------------------------
    # Checkout page
    # ------------------------------------------------------------------

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
        response = self.client.get(reverse("orders:checkout"))
        self.assertEqual(response.context["address"].city, "Amsterdam")

    # ------------------------------------------------------------------
    # place_order view
    # ------------------------------------------------------------------

    def test_place_order_rejects_empty_cart(self):
        response = self.client.post(reverse("orders:place_order"))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["success"], False)
        self.assertEqual(response.json()["redirect"], "index")
        self.assertEqual(Order.objects.count(), 0)

    def test_place_order_rejects_anonymous_user(self):
        self.client.logout()
        self.add_cart_item()
        response = self.client.post(reverse("orders:place_order"))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["success"], False)
        self.assertEqual(response.json()["redirect"], "register")
        self.assertEqual(Order.objects.count(), 0)

    def test_place_order_rejects_missing_address(self):
        self.address.delete()
        self.add_cart_item("1")

        response = self.client.post(reverse("orders:place_order"))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["success"], False)
        self.assertEqual(response.json()["redirect"], "address")
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
        self.assertEqual(item.unit_price, Decimal("250.00"))

    def test_place_order_snapshots_shipping_address(self):
        self.add_cart_item("1")
        self.client.post(reverse("orders:place_order"))

        order = Order.objects.get(user=self.user)
        self.assertEqual(order.shipping_full_name, "Alice Smith")
        self.assertEqual(order.shipping_city, "Amsterdam")
        self.assertEqual(order.shipping_country, "Netherlands")

    def test_place_order_decrements_stock(self):
        self.add_cart_item("3")
        response = self.client.post(reverse("orders:place_order"))

        self.assertEqual(response.status_code, 200)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 7)

    def test_place_order_rejects_insufficient_stock(self):
        self.add_cart_item("999")
        response = self.client.post(reverse("orders:place_order"))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["success"], False)
        self.assertIn("Only", response.json()["error"])
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)
        self.assertEqual(Order.objects.count(), 0)

    def test_place_order_clears_cart_on_success(self):
        self.add_cart_item("2")
        self.client.post(reverse("orders:place_order"))
        self.assertEqual(self.client.session.get("cart"), {})

    # ------------------------------------------------------------------
    # Order list
    # ------------------------------------------------------------------

    def test_order_list_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("orders:order_list"))
        expected = f"{reverse('users:login')}?next={reverse('orders:order_list')}"
        self.assertRedirects(response, expected)

    def test_order_list_shows_only_own_orders(self):
        other_user = User.objects.create_user(username="bob", password="StrongPass123!")
        my_order = Order.objects.create(user=self.user, total_amount=Decimal("10.00"))
        other_order = Order.objects.create(user=other_user, total_amount=Decimal("20.00"))

        response = self.client.get(reverse("orders:order_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"#{my_order.pk}")
        self.assertNotContains(response, f"#{other_order.pk}")

    def test_order_list_empty_state(self):
        response = self.client.get(reverse("orders:order_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No orders yet")

    # ------------------------------------------------------------------
    # Order detail
    # ------------------------------------------------------------------

    def test_order_detail_requires_login(self):
        self.client.logout()
        order = Order.objects.create(user=self.user, total_amount=Decimal("10.00"))
        response = self.client.get(reverse("orders:order_detail", kwargs={"pk": order.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_order_detail_returns_404_for_other_users_order(self):
        other_user = User.objects.create_user(username="bob", password="StrongPass123!")
        other_order = Order.objects.create(user=other_user, total_amount=Decimal("20.00"))

        response = self.client.get(
            reverse("orders:order_detail", kwargs={"pk": other_order.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_order_detail_returns_404_for_missing_order(self):
        response = self.client.get(
            reverse("orders:order_detail", kwargs={"pk": 999999})
        )
        self.assertEqual(response.status_code, 404)

    def test_order_detail_renders_own_order(self):
        order = Order.objects.create(
            user=self.user,
            total_amount=Decimal("10.00"),
            shipping_full_name="Alice Smith",
            shipping_city="Amsterdam",
            shipping_state="North Holland",
            shipping_postal_code="1011AA",
            shipping_country="Netherlands",
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            quantity=2,
            unit_price=self.product.price,
        )

        response = self.client.get(reverse("orders:order_detail", kwargs={"pk": order.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"Order #{order.pk}")
        self.assertContains(response, self.product.title)
        self.assertContains(response, "Alice Smith")
        self.assertContains(response, "Amsterdam")

    def test_order_detail_shows_snapshot_price_not_current(self):
        order = Order.objects.create(user=self.user, total_amount=Decimal("100.00"))
        OrderItem.objects.create(
            order=order,
            product=self.product,
            quantity=1,
            unit_price=Decimal("100.00"),
        )

        self.product.price = Decimal("999.99")
        self.product.save()

        response = self.client.get(reverse("orders:order_detail", kwargs={"pk": order.pk}))
        self.assertContains(response, "100.00")
        self.assertNotContains(response, "999.99")