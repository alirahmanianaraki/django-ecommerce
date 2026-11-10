from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from myapp.models import Product
from orders.models import Order, OrderItem
from payments.models import Refund
from payments.refunds import RefundError, cancel_order_and_refund, refund_order_to_wallet
from payments.tests.test_payments import SECRET, make_event, post_signed
from wallets.services import get_balance


class RefundFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('alice', 'alice@example.com', 'StrongPass123!')
        # stock 8 = 10 originally, minus the 2 reserved by the order
        self.product = Product.objects.create(
            title='GPU', description='x', price=Decimal('100.00'), stock=8)

    def make_order(self, status, paid):
        order = Order.objects.create(
            user=self.user, subtotal_amount=Decimal('200.00'),
            total_amount=Decimal('200.00'), status=status, is_paied=paid)
        OrderItem.objects.create(order=order, product=self.product,
                                 quantity=2, unit_price=Decimal('100.00'))
        return order

    def cancel(self, order, **kwargs):
        return cancel_order_and_refund(
            order.pk, actor=self.user, reason=Refund.Reason.CUSTOMER_CANCELLED,
            note='test', **kwargs)

    def test_cancelling_a_paid_order_refunds_wallet_and_restocks(self):
        order = self.make_order(Order.Status.PAID, True)
        refund = self.cancel(order)
        order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(refund.amount, Decimal('200.00'))
        self.assertEqual(get_balance(self.user), Decimal('200.00'))
        self.assertEqual(self.product.stock, 10)

    def test_cancelling_twice_never_refunds_twice(self):
        order = self.make_order(Order.Status.PAID, True)
        self.cancel(order)
        with self.assertRaises(RefundError):
            self.cancel(order)
        self.assertEqual(get_balance(self.user), Decimal('200.00'))
        self.assertEqual(order.refunds.count(), 1)

    def test_customer_cannot_cancel_an_order_being_packed(self):
        order = self.make_order(Order.Status.PROCESSING, True)
        with self.assertRaises(RefundError):
            self.cancel(order)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PROCESSING)
        self.assertEqual(get_balance(self.user), Decimal('0.00'))

    def test_staff_can_cancel_a_processing_order(self):
        order = self.make_order(Order.Status.PROCESSING, True)
        self.cancel(order, staff=True)
        self.assertEqual(get_balance(self.user), Decimal('200.00'))

    def test_cancelling_an_unpaid_order_refunds_nothing(self):
        order = self.make_order(Order.Status.PENDING, False)
        self.assertIsNone(self.cancel(order))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(get_balance(self.user), Decimal('0.00'))

    def test_partial_refunds_can_never_exceed_the_total(self):
        order = self.make_order(Order.Status.DELIVERED, True)
        refund_order_to_wallet(order.pk, amount=Decimal('150.00'), reason=Refund.Reason.ADMIN)
        with self.assertRaises(RefundError):
            refund_order_to_wallet(order.pk, amount=Decimal('60.00'), reason=Refund.Reason.ADMIN)
        refund_order_to_wallet(order.pk, amount=Decimal('50.00'), reason=Refund.Reason.ADMIN)
        self.assertEqual(get_balance(self.user), Decimal('200.00'))
        self.assertIsNone(refund_order_to_wallet(order.pk, reason=Refund.Reason.ADMIN))

    def test_unpaid_order_cannot_be_refunded(self):
        order = self.make_order(Order.Status.PENDING, False)
        with self.assertRaises(RefundError):
            refund_order_to_wallet(order.pk, reason=Refund.Reason.ADMIN)

    def test_cancel_view_refunds_to_wallet(self):
        order = self.make_order(Order.Status.PAID, True)
        self.client.force_login(self.user)
        response = self.client.post(reverse('orders:cancel_order', args=[order.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(get_balance(self.user), Decimal('200.00'))

    def test_cannot_cancel_someone_elses_order(self):
        order = self.make_order(Order.Status.PAID, True)
        self.client.force_login(User.objects.create_user('bob', password='StrongPass123!'))
        response = self.client.post(reverse('orders:cancel_order', args=[order.pk]))
        self.assertEqual(response.status_code, 404)


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET, STRIPE_CURRENCY='usd')
class LatePaymentTests(TestCase):
    def test_payment_for_a_cancelled_order_is_credited_to_wallet(self):
        user = User.objects.create_user('alice', password='StrongPass123!')
        order = Order.objects.create(
            user=user, subtotal_amount=Decimal('200.00'), total_amount=Decimal('200.00'),
            status=Order.Status.CANCELLED, stripe_checkout_session_id='cs_test_1')
        session = {
            'id': 'cs_test_1', 'metadata': {'order_id': str(order.pk)},
            'payment_status': 'paid', 'amount_total': 20000,
            'currency': 'usd', 'payment_intent': 'pi_late',
        }
        response = post_signed(self.client, make_event('checkout.session.completed', session))
        self.assertEqual(response.status_code, 200)

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)   # stays cancelled
        self.assertTrue(order.is_paied)
        self.assertEqual(get_balance(user), Decimal('200.00'))
        self.assertEqual(order.refunds.get().reason, Refund.Reason.LATE_PAYMENT)