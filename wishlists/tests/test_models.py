from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from myapp.models import Product
from wishlists.models import Wishlist, WishlistItems


class WishlistModelTests(TestCase):
    def test_wishlist_str(self):
        user = User.objects.create_user(username="alice", password="StrongPass123!")
        wishlist = Wishlist.objects.create(user=user)
        self.assertEqual(str(wishlist), "alice Wishlist")

    def test_wishlist_item_str(self):
        user = User.objects.create_user(username="alice", password="StrongPass123!")
        wishlist = Wishlist.objects.create(user=user)
        product = Product.objects.create(
            title="GPU", description="GPU", price=Decimal("100.00"), stock=1
        )
        item = WishlistItems.objects.create(wishlist=wishlist, product=product)
        self.assertEqual(str(item), f"{wishlist} Product {product}")
