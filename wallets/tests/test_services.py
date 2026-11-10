from decimal import Decimal

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase

from wallets.models import Wallet, WalletTransaction
from wallets.services import (
    InsufficientFunds, WalletError, credit, debit, get_balance,
)

Kind = WalletTransaction.Kind


class WalletServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('alice', password='StrongPass123!')

    def test_credit_updates_balance_and_ledger(self):
        txn, created = credit(user=self.user, amount=Decimal('10.00'),
                              kind=Kind.TOPUP, reference='t1')
        self.assertTrue(created)
        self.assertEqual(get_balance(self.user), Decimal('10.00'))
        self.assertEqual(txn.balance_after, Decimal('10.00'))

    def test_same_reference_is_applied_only_once(self):
        credit(user=self.user, amount=Decimal('10.00'), kind=Kind.TOPUP, reference='t1')
        _, created = credit(user=self.user, amount=Decimal('10.00'), kind=Kind.TOPUP, reference='t1')
        self.assertFalse(created)
        self.assertEqual(get_balance(self.user), Decimal('10.00'))
        self.assertEqual(WalletTransaction.objects.count(), 1)

    def test_reusing_a_reference_for_a_different_amount_is_rejected(self):
        credit(user=self.user, amount=Decimal('10.00'), kind=Kind.TOPUP, reference='t1')
        with self.assertRaises(WalletError):
            credit(user=self.user, amount=Decimal('99.00'), kind=Kind.TOPUP, reference='t1')

    def test_cannot_overdraw(self):
        credit(user=self.user, amount=Decimal('5.00'), kind=Kind.TOPUP, reference='t1')
        with self.assertRaises(InsufficientFunds):
            debit(user=self.user, amount=Decimal('10.00'), kind=Kind.PURCHASE, reference='p1')
        self.assertEqual(get_balance(self.user), Decimal('5.00'))
        self.assertEqual(WalletTransaction.objects.count(), 1)

    def test_floats_and_three_decimals_are_rejected(self):
        with self.assertRaises(WalletError):
            credit(user=self.user, amount=0.1, kind=Kind.TOPUP, reference='f1')
        with self.assertRaises(WalletError):
            credit(user=self.user, amount=Decimal('1.001'), kind=Kind.TOPUP, reference='f2')

    def test_balance_always_equals_ledger_sum(self):
        credit(user=self.user, amount=Decimal('50.00'), kind=Kind.TOPUP, reference='a')
        debit(user=self.user, amount=Decimal('12.34'), kind=Kind.PURCHASE, reference='b')
        credit(user=self.user, amount=Decimal('2.00'), kind=Kind.REFUND, reference='c')
        total = sum(t.amount for t in WalletTransaction.objects.all())
        self.assertEqual(Wallet.objects.get(user=self.user).balance, total)
        self.assertEqual(total, Decimal('39.66'))

    def test_database_refuses_a_negative_balance(self):
        wallet = Wallet.objects.create(user=self.user)
        wallet.balance = Decimal('-1.00')
        with self.assertRaises(IntegrityError), transaction.atomic():
            wallet.save()

    def test_ledger_rows_cannot_be_edited(self):
        txn, _ = credit(user=self.user, amount=Decimal('5.00'), kind=Kind.TOPUP, reference='t1')
        txn.note = 'tampered'
        with self.assertRaises(RuntimeError):
            txn.save()