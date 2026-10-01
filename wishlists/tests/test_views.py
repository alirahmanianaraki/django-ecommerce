from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from myapp.models import Product
from wishlists.models import Wishlist, WishlistItems


class WishlistViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="alice", password="StrongPass123!"
        )
        cls.product = Product.objects.create(
            title="GPU", description="GPU", price=Decimal("100.00"), stock=5
        )

    def test_add_requires_authentication(self):
        response = self.client.post(
            reverse("wishlists:add_item_to_wishlist"),
            {"product_id": self.product.pk},
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])

    def test_add_requires_product_id(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("wishlists:add_item_to_wishlist"))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "Product id is required")

    def test_add_item(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("wishlists:add_item_to_wishlist"),
            {"product_id": self.product.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["added"])
        self.assertEqual(WishlistItems.objects.count(), 1)

    def test_add_existing_item_reports_already_added(self):
        self.client.force_login(self.user)
        self.client.post(
            reverse("wishlists:add_item_to_wishlist"), {"product_id": self.product.pk}
        )
        response = self.client.post(
            reverse("wishlists:add_item_to_wishlist"), {"product_id": self.product.pk}
        )
        self.assertFalse(response.json()["added"])
        self.assertEqual(response.json()["message"], "Already in the wishlist")
        self.assertEqual(WishlistItems.objects.count(), 1)

    def test_remove_requires_authentication(self):
        response = self.client.post(
            reverse("wishlists:remove_item_from_wishlist"),
            {"product_id": self.product.pk},
        )
        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.json()["removed"])

    def test_remove_item(self):
        self.client.force_login(self.user)
        self.client.post(
            reverse("wishlists:add_item_to_wishlist"), {"product_id": self.product.pk}
        )
        response = self.client.post(
            reverse("wishlists:remove_item_from_wishlist"),
            {"product_id": self.product.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["deleted"])
        self.assertEqual(WishlistItems.objects.count(), 0)

    def test_remove_missing_item_returns_false(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("wishlists:remove_item_from_wishlist"),
            {"product_id": self.product.pk},
        )
        self.assertFalse(response.json()["deleted"])

    def test_overview_requires_authentication(self):
        response = self.client.get(reverse("wishlists:wishlist_overview"))
        self.assertRedirects(response, reverse("users:register"))

    def test_overview_renders_for_authenticated_user(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("wishlists:wishlist_overview"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "wishlists/wishlist_overview.html")

    def test_overview_shows_wishlist_product(self):
        self.client.force_login(self.user)
        wishlist = Wishlist.objects.create(user=self.user)
        WishlistItems.objects.create(wishlist=wishlist, product=self.product)
        response = self.client.get(reverse("wishlists:wishlist_overview"))
        self.assertContains(response, self.product.title)
