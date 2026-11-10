import logging
from decimal import Decimal, InvalidOperation
from django.db import transaction
from .models import Wallet, WalletTransaction

logger = logging.getLogger(__name__)

CENT = Decimal('0.01')

class WalletError(Exception):
    """Something is wrong with a wallet operation"""

class InsufficientFunds(WalletError):
    """The wallet doesn't hold enough money"""

def to_money(value):
    """Turn input into a Decimal with exactly 2 places, or raise WalletError"""
    if isinstance(value, float):
        raise WalletError("Amounts must be Decimal or string, never float")
    try:
        amount = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        raise WalletError('Invalid amount')
    if not amount.is_finite() or amount != amount.quantize(CENT):
        raise WalletError('Amounts must have at most 2 decimal places')
    return amount.quantize(CENT)

def get_or_create_wallet(user):
    wallet, _ = Wallet.objects.get_or_create(user=user)
    return wallet

def get_balance(user):
    """Read-only helper for display"""
    balance = Wallet.objects.filter(user=user).values_list('balance', flat=True).first()
    return balance if balance is not None else Decimal('0.00')

def apply_transaction(*, user, kind, amount, reference, order=None, note='', created_by=None):
    """
    Add one ledger row and update the balance, atomically.
    """
    amount = to_money(amount)
    if amount == 0:
        raise WalletError('Amount cannot be zero')

    with transaction.atomic():
        get_or_create_wallet(user)
        # Lock this wallet row.
        wallet = Wallet.objects.select_for_update().get(user=user)
        existing = WalletTransaction.objects.filter(reference=reference).first()
        if existing is not None:
            if (existing.wallet_id != wallet.pk or existing.amount != amount
                or existing.kind != kind):
                raise WalletError(f"Reference {reference!r} was already used for a different operation")
            return existing, False

        new_balance = wallet.balance + amount
        if new_balance < 0:
            raise InsufficientFunds('Insufficient wallet balance.')

        txn = WalletTransaction.objects.create(
            wallet=wallet, kind=kind, amount=amount, balance_after=new_balance,
            reference=reference, order=order, note=note[:255], created_by=created_by,
        )
        wallet.balance = new_balance
        wallet.save(update_fields=['balance', 'updated_at'])
        return txn, True

def credit(*, user, amount, kind, reference, order=None, note='', created_by=None):
    amount = to_money(amount)
    if amount <= 0:
        raise WalletError('A credit must be positive.')
    return apply_transaction(user=user, kind=kind, amount=amount, reference=reference,
                             order=order, note=note, created_by=created_by)

def debit(*, user, amount, kind, reference, order=None, note='', created_by=None):
    amount = to_money(amount)
    if amount <= 0:
        raise WalletError('A debit must be positive (we apply the minus sign).')
    return apply_transaction(user=user, kind=kind, amount=-amount, reference=reference,
                             order=order, note=note, created_by=created_by)