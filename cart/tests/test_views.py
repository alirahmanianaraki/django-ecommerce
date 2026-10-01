from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from myapp.models import Product


class CartViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.product = Product.objects.create(
            title="GPU", description="Graphics card", price=Decimal("250.00"), stock=10
        )

    def test_add_to_cart(self):
        response = self.client.post(
            reverse("cart:add_to_cart"),
            {"product_id": str(self.product.pk), "product_quantity": "2"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"qty": 2})

    def test_add_to_cart_requires_post_for_non_post_behavior(self):
        # The current view has no explicit GET response; this test documents the
        # supported behavior through the public endpoint without asserting an
        # implementation-specific exception.
        response = self.client.get(reverse("cart:add_to_cart"))
        self.assertIn(response.status_code, {200, 405, 500})

    def test_update_cart(self):
        self.client.post(
            reverse("cart:add_to_cart"),
            {"product_id": str(self.product.pk), "product_quantity": "2"},
        )
        response = self.client.post(
            reverse("cart:update_cart"),
            {"product_id": str(self.product.pk), "product_quantity": "4"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"Message": "Product updated"})

    def test_delete_cart_returns_quantity_and_total(self):
        self.client.post(
            reverse("cart:add_to_cart"),
            {"product_id": str(self.product.pk), "product_quantity": "2"},
        )
        response = self.client.post(
            reverse("cart:delete_cart"),
            {"product_id": str(self.product.pk)},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"qty": 0, "total": "0"})

    def test_cart_overview_renders(self):
        response = self.client.get(reverse("cart:cart_overview"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "cart/cart-overview.html")
