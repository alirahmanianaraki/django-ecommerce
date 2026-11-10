from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from orders.models import Order
from payments.services import PaymentError
from payments.wallet_payment import pay_order_with_wallet
from wallets.models import WalletTransaction
from wallets.services import credit, get_balance


class WalletPaymentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('alice', 'alice@example.com', 'StrongPass123!')
        self.order = Order.objects.create(
            user=self.user, subtotal_amount=Decimal('50.00'), total_amount=Decimal('50.00'))

    def fund(self, amount):
        credit(user=self.user, amount=Decimal(amount), kind=WalletTransaction.Kind.ADJUSTMENT,
               reference='fund-1', note='test funds')

    def test_paying_with_wallet_marks_order_paid_and_debits(self):
        self.fund('80.00')
        pay_order_with_wallet(self.order.pk, actor=self.user)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)
        self.assertTrue(self.order.is_paied)
        self.assertEqual(get_balance(self.user), Decimal('30.00'))

    def test_insufficient_balance_changes_nothing(self):
        self.fund('10.00')
        with self.assertRaises(PaymentError):
            pay_order_with_wallet(self.order.pk, actor=self.user)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING)
        self.assertEqual(get_balance(self.user), Decimal('10.00'))

    def test_an_order_cannot_be_paid_twice(self):
        self.fund('200.00')
        pay_order_with_wallet(self.order.pk, actor=self.user)
        with self.assertRaises(PaymentError):
            pay_order_with_wallet(self.order.pk, actor=self.user)
        self.assertEqual(get_balance(self.user), Decimal('150.00'))

    def test_pay_view_redirects_back_to_the_order(self):
        self.fund('80.00')
        self.client.force_login(self.user)
        response = self.client.post(reverse('payments:pay_with_wallet', args=[self.order.pk]))
        self.assertRedirects(response, reverse('orders:order_detail', args=[self.order.pk]))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)