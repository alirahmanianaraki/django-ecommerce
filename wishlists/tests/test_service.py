from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from myapp.models import Product
from wishlists.models import Wishlist, WishlistItems
from wishlists.wishlist import WishlistService


class WishlistServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="StrongPass123!")
        self.product = Product.objects.create(
            title="GPU", description="GPU", price=Decimal("100.00"), stock=5
        )
        self.service = WishlistService(user=self.user, request=None)

    def test_initializes_one_wishlist_for_user(self):
        self.assertEqual(Wishlist.objects.filter(user=self.user).count(), 1)
        self.assertEqual(self.service.wishlist.user, self.user)

    def test_add_creates_item(self):
        created = self.service.add(self.product.pk)
        self.assertTrue(created)
        self.assertTrue(
            WishlistItems.objects.filter(
                wishlist=self.service.wishlist, product=self.product
            ).exists()
        )

    def test_add_existing_item_returns_false(self):
        self.assertTrue(self.service.add(self.product.pk))
        self.assertFalse(self.service.add(self.product.pk))
        self.assertEqual(WishlistItems.objects.count(), 1)

    def test_remove_existing_item_returns_true(self):
        self.service.add(self.product.pk)
        self.assertTrue(self.service.remove(self.product.pk))
        self.assertEqual(WishlistItems.objects.count(), 0)

    def test_remove_missing_item_returns_false(self):
        self.assertFalse(self.service.remove(self.product.pk))

    def test_clear_removes_all_items(self):
        product2 = Product.objects.create(
            title="RAM", description="Memory", price=Decimal("50.00"), stock=3
        )
        self.service.add(self.product.pk)
        self.service.add(product2.pk)
        deleted = self.service.clear()
        self.assertEqual(deleted, 2)
        self.assertEqual(WishlistItems.objects.count(), 0)
