from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from .models import Wishlist, WishlistItems
from myapp.models import Product

class WishlistService():
    def __init__(self, user, request):
        self.user = user
        self.wishlist, _ = Wishlist.objects.get_or_create(user=self.user)

    def add(self, product_id):
        product = get_object_or_404(Product, pk=product_id)
        item, created = WishlistItems.objects.get_or_create(product=product, wishlist=self.wishlist)
        return created

    def remove(self, product_id):
        deleted, _ =  WishlistItems.objects.filter(product_id=product_id, wishlist=self.wishlist).delete()
        return deleted > 0

    def clear(self):
        deleted, _ = self.wishlist.wishlistitems_set.all().delete()
        return deleted

