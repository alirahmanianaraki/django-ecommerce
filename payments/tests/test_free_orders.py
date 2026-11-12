from decimal import Decimal

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from unittest.mock import patch

from cart.cart import Cart
from myapp.models import Coupon, Product
from orders.models import Order
from orders.services import place_order
from payments.free_orders import pay_free_order
from payments.models import Refund
from payments.refunds import cancel_order_and_refund
from payments.services import PaymentError, get_or_create_checkout_url
from users.models import Address
from wallets.services import get_balance


class FreeOrderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('alice', 'alice@example.com', 'StrongPass123!')

    def make_order(self, total, status=Order.Status.PENDING):
        return Order.objects.create(
            user=self.user, subtotal_amount=Decimal('100.00'),
            total_amount=Decimal(total), status=status)

    def test_hundred_percent_coupon_end_to_end(self):
        product = Product.objects.create(
            title='GPU', description='x', price=Decimal('100.00'), stock=5)
        Coupon.objects.create(code='FREE100', discount_type='percent', value=Decimal('100'))
        address = Address.objects.create(
            user=self.user, title='Home', full_name='Alice', description='1 Main',
            city='Ams', state='NH', postal_code='1011', country='NL')
        request = RequestFactory().get('/')
        request.session = self.client.session
        cart = Cart(request)
        cart.add(str(product.pk), '1')
        cart.apply_coupon('FREE100', user=self.user)

        order = place_order(user=self.user, cart=cart, address=address)
        self.assertEqual(order.total_amount, Decimal('0.00'))

        pay_free_order(order.pk, actor=self.user)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertTrue(order.is_paied)
        self.assertIsNotNone(order.paid_at)

    def test_refuses_an_order_that_still_has_an_amount(self):
        order = self.make_order('10.00')
        with self.assertRaises(PaymentError):
            pay_free_order(order.pk, actor=self.user)

    def test_cannot_be_confirmed_twice(self):
        order = self.make_order('0.00')
        pay_free_order(order.pk, actor=self.user)
        with self.assertRaises(PaymentError):
            pay_free_order(order.pk, actor=self.user)

    def test_pay_view_confirms_without_touching_stripe(self):
        order = self.make_order('0.00')
        self.client.force_login(self.user)
        with patch('payments.views.get_or_create_checkout_url') as stripe_call:
            response = self.client.post(reverse('payments:pay', args=[order.pk]))
        self.assertRedirects(response, reverse('orders:order_detail', args=[order.pk]))
        stripe_call.assert_not_called()
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)

    def test_wallet_view_confirms_free_order_too(self):
        order = self.make_order('0.00')
        self.client.force_login(self.user)
        self.client.post(reverse('payments:pay_with_wallet', args=[order.pk]))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(get_balance(self.user), Decimal('0.00'))

    def test_cancelling_a_free_order_refunds_nothing(self):
        order = self.make_order('0.00')
        pay_free_order(order.pk, actor=self.user)
        refund = cancel_order_and_refund(
            order.pk, actor=self.user, reason=Refund.Reason.CUSTOMER_CANCELLED, note='changed my mind')
        self.assertIsNone(refund)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)

    @override_settings(STRIPE_SECRET_KEY='sk_test_dummy', STRIPE_MIN_CHARGE_AMOUNT=Decimal('0.50'))
    def test_card_payment_below_stripe_minimum_is_refused(self):
        order = self.make_order('0.30')
        with self.assertRaises(PaymentError):
            get_or_create_checkout_url(order.pk)