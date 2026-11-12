from django.db import models
from django.conf import settings
# Create your models here.
class StripeWebhookEvent(models.Model):
    event_id = models.CharField(max_length=255, unique=True)
    event_type = models.CharField(max_length=100)
    received_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.event_type} ({self.event_id})"

class Refund(models.Model):
    """One refund of an order."""
    class Destination(models.TextChoices):
        WALLET = 'wallet', 'Customer wallet'

    class Reason(models.TextChoices):
        CUSTOMER_CANCELLED = 'customer_cancelled', 'Cancelled by customer'
        ADMIN = 'admin', 'Issued by staff'
        LATE_PAYMENT = 'late_payment', 'Payment arrived after cancellation'

    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.PROTECT,
        related_name='refunds'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    destination = models.CharField(
        max_length=20,
        choices=Destination.choices,
        default=Destination.WALLET
    )
    reason = models.CharField(
        max_length=30,
        choices=Reason.choices
    )
    note = models.CharField(max_length=255, blank=True)
    wallet_transaction = models.OneToOneField(
        'wallets.WalletTransaction',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='refund'
    )
    created_by = models.ForeignKey(
        'auth.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name='refund_amount_positive'),
        ]

    def __str__(self):
        return f"Refund {self.amount} for order #{self.order_id}"

class TopUp(models.Model):
    """
    One attempt to add money to a wallet through stripe
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'Awaiting payment'
        COMPLETED = 'completed', 'Completed'
        EXPIRED = 'expired', 'Expired'
        FAILED = 'failed', 'Failed'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='wallet_topups'
    )
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2
        )
    currency = models.CharField(max_length=3)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    stripe_checkout_session_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        unique=True
    )
    stripe_payment_intent_id = models.CharField(
        max_length=255,
        blank=True
    )
    wallet_transaction = models.OneToOneField(
        'wallets.WalletTransaction',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='topup'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', '-created_at'])]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0),
                                   name='topup_amount_positive')
        ]

    def __str__(self):
        return f"Top-up {self.amount} for {self.user} ({self.status})"