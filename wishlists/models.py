from django.contrib.auth.models import User
from django.db import models
from myapp.models import Product

# Create your models here.
class Wishlist(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='user_wishlist'
    )
    name = models.CharField(
        max_length=100,
        blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class WishlistItems(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='wishlist_products'
    )
    wishlist = models.ForeignKey(
        Wishlist,
        on_delete=models.CASCADE
    )
