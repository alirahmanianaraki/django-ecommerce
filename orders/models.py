from django.contrib.auth.models import User
from django.db import models
from myapp.models import Product

# Create your models here.
class Order(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    is_paied = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    shipping_title = models.CharField(max_length=100, blank=True)
    shipping_full_name = models.CharField(max_length=100, blank=True)
    shipping_description = models.TextField(blank=True)
    shipping_city = models.CharField(max_length=150, blank=True)
    shipping_state = models.CharField(max_length=150, blank=True)
    shipping_postal_code = models.CharField(max_length=50, blank=True)
    shipping_country = models.CharField(max_length=150, blank=True)
    coupon_code = models.CharField(max_length=50, blank=True)
    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )
    subtotal_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    def __str__(self):
        return f"Order #{self.pk} - {self.user}"

class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
    )

    @property
    def total_price(self):
        return self.quantity * self.unit_price
