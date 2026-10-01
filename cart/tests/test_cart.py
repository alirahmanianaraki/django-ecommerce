from decimal import Decimal

from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory, TestCase

from cart.cart import Cart
from myapp.models import Product


class CartTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.product = Product.objects.create(
            title="GPU", description="Graphics card", price=Decimal("250.00"), stock=10
        )
        cls.product2 = Product.objects.create(
            title="RAM", description="Memory", price=Decimal("75.50"), stock=10
        )

    def setUp(self):
        self.request = RequestFactory().get("/")
        self.request.session = SessionStore()
        self.cart = Cart(self.request)

    def test_new_cart_is_initialized_in_session(self):
        self.assertEqual(self.cart.cart, {})
        self.assertIn("cart", self.request.session)

    def test_add_new_product(self):
        self.cart.add(str(self.product.pk), "2")
        self.assertEqual(self.cart.cart[str(self.product.pk)]["price"], "250.00")
        self.assertEqual(self.cart.cart[str(self.product.pk)]["qty"], "2")
        self.assertTrue(self.request.session.modified)

    def test_add_existing_product_replaces_quantity(self):
        self.cart.add(str(self.product.pk), "2")
        self.cart.add(str(self.product.pk), "5")
        self.assertEqual(self.cart.cart[str(self.product.pk)]["qty"], "5")

    def test_len_returns_total_quantity(self):
        self.cart.add(str(self.product.pk), "2")
        self.cart.add(str(self.product2.pk), "3")
        self.assertEqual(len(self.cart), 5)

    def test_iteration_returns_product_price_quantity_and_total(self):
        self.cart.add(str(self.product.pk), "2")
        item = next(iter(self.cart))
        self.assertEqual(item["product"], self.product)
        self.assertEqual(item["price"], Decimal("250.00"))
        self.assertEqual(item["qty"], Decimal("2"))
        self.assertEqual(item["total"], Decimal("500.00"))

    def test_total_price(self):
        self.cart.add(str(self.product.pk), "2")
        self.cart.add(str(self.product2.pk), "3")
        self.assertEqual(self.cart.get_total_price(), Decimal("726.50"))

    def test_update_changes_quantity(self):
        self.cart.add(str(self.product.pk), "2")
        self.cart.update(self.product.pk, "7")
        self.assertEqual(self.cart.cart[str(self.product.pk)]["qty"], "7")
        self.assertTrue(self.request.session.modified)

    def test_update_missing_product_does_nothing(self):
        self.cart.update(self.product.pk, "7")
        self.assertEqual(self.cart.cart, {})

    def test_delete_removes_product(self):
        self.cart.add(str(self.product.pk), "2")
        self.cart.delete(self.product.pk)
        self.assertNotIn(str(self.product.pk), self.cart.cart)
        self.assertTrue(self.request.session.modified)

    def test_delete_missing_product_does_nothing(self):
        self.cart.delete(self.product.pk)
        self.assertEqual(self.cart.cart, {})
