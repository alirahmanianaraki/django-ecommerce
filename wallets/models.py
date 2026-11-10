from decimal import Decimal
from django.db import models
from django.conf import settings
from django.db.models import Q

# Create your models here.
class Wallet(models.Model):
    """
    One wallet per user. 'balance' is a cache of the ledger total
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='wallet'
    )
    balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(balance__gte=0),
                name='wallet_balance_non_negative',
            ),
        ]

    def __str__(self):
        return f"Wallet of {self.user} ({self.balance})"

class WalletTransaction(models.Model):
    """
    One line of the ledger; append-only.
    """
    class Kind(models.TextChoices):
        TOPUP = 'topup', 'Top-up'
        PURCHASE = 'purchase', 'Purchase'
        REFUND = 'refund', 'Refund'
        WITHDRAWAL = 'withdrawal', 'Withdrawal'
        ADJUSTMENT = 'adjustment', 'Manual adjustment'

    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.PROTECT,
        related_name='transactions'
    )
    kind = models.CharField(max_length=20, choices=Kind.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.CharField(max_length=120, unique=True)
    order = models.ForeignKey(
        'orders.Order',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='wallet_transactions'
    )
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['wallet', '-created_at'])
        ]
        constraints = [
            models.CheckConstraint(
                condition=~Q(amount=0), name='wallet_txn_amount_not_zero'
            ),
            models.CheckConstraint(
                condition=(
                    Q(kind__in=['topup', 'refund'], amount__gt=0)
                    | Q(kind__in=['purchase', 'withdrawal'], amount__lt=0)
                    | Q(kind='adjustment')
                ),
                name='wallet_txn_sign_matches_kind'
            )
        ]

    def __str__(self):
        return f"{self.kind} {self.amount} ({self.reference})"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError('Ledger entries are immutable')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError('Ledger entries cannot be deleted')