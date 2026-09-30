from django.contrib import admin
from .models import Wishlist, WishlistItems
# Register your models here.
admin.site.register(WishlistItems)
admin.site.register(Wishlist)