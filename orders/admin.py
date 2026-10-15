from django.contrib import admin
from .models import Order, OrderItem
# Register your models here.

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['user', 'total_amount', 'is_paied', 'created_at']
    list_filter = ['is_paied']
    search_fields = ['user', 'is_paied']

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['order', 'product', 'quantity', 'unit_price']
    list_filter = ['product']
    search_fields = ['order', 'product']