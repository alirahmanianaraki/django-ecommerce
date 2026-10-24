from django.contrib.auth.models import User
from django.db import models
from decimal import Decimal
from myapp.models import Product

# Create your models here.
class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending payment'
        PAID = 'paid', 'Paid'
        PROCESSING = 'processing', 'Processing'
        SHIPPED = 'shipped', 'Shipped'
        DELIVERED = 'delivered', 'Delivered'
        CANCELLED = 'cancelled', 'Cancelled'

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
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    status_updated_at = models.DateTimeField(null=True, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"Order #{self.pk} - {self.user}"

    ALLOWED_TRANSITIONS = {
        Status.PENDING: {Status.PAID, Status.CANCELLED},
        Status.PAID: {Status.PROCESSING, Status.CANCELLED},
        Status.PROCESSING: {Status.SHIPPED, Status.CANCELLED},
        Status.SHIPPED: {Status.DELIVERED},
        Status.DELIVERED: set(), # terminal
        Status.CANCELLED: set() # terminal
    }

    def can_transition_to(self, new_status):
        return new_status in self.ALLOWED_TRANSITIONS.get(self.status, set())

    @property
    def is_cancellable(self):
        return self.can_transition_to(self.Status.CANCELLED)

    @property
    def is_terminal(self):
        return self.status in {self.Status.DELIVERED, self.Status.CANCELLED}
    
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
    original_unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="The product's regular price at the moment of ordering, before any discount"
    )

    @property
    def total_price(self):
        return self.quantity * self.unit_price

    @property
    def discount_amount(self):
        """How much was saved on this line"""
        if not self.original_unit_price:
            return Decimal('0.00')
        per_unit = self.original_unit_price - self.unit_price
        if per_unit <= 0:
            return Decimal('0.00')
        return (per_unit * self.quantity).quantize(Decimal('0.01'))

class OrderStatusEvent(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='status_events'
    )
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20)
    changed_at = models.DateTimeField(auto_now_add=True)
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='order_status_changes'
    )
    note = models.TextField(blank=True)

    class Meta:
        ordering = ['-changed_at']
        indexes = [models.Index(fields=['order', '-changed_at'])]

    def __str__(self):
        return f"Order #{self.order_id}: {self.from_status or '-'} → {self.to_status}"
