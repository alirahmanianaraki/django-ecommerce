from django.contrib import admin
from .models import Product, ProductImage, Tag
# Register your models here.

admin.site.register(Product)
admin.site.register(ProductImage)
admin.site.register(Tag)