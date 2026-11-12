from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from stripe import StripeError

from payments.models import TopUp
from payments.tests.test_payments import SECRET, make_event, post_signed
from payments.topups import TopUpError, parse_topup_amount, start_topup
from wallets.models import WalletTransaction
from wallets.services import credit, get_balance

LIMITS = dict(
    WALLET_TOPUP_MIN_AMOUNT=Decimal('5.00'),
    WALLET_TOPUP_MAX_AMOUNT=Decimal('500.00'),
    WALLET_MAX_BALANCE=Decimal('2000.00'),
    WALLET_TOPUP_MAX_ATTEMPTS_PER_HOUR=10,
    STRIPE_CURRENCY='usd',
    SITE_URL='http://127.0.0.1:8000',
)


@override_settings(**LIMITS)
class ParseAmountTests(TestCase):
    def test_valid_amounts(self):
        self.assertEqual(parse_topup_amount('25'), Decimal('25.00'))
        self.assertEqual(parse_topup_amount(' 25.50 '), Decimal('25.50'))

    def test_invalid_amounts_are_rejected(self):
        for bad in ['', 'abc', '1.234', '-5', 'NaN', '4.99', '500.01']:
            with self.subTest(bad=bad), self.assertRaises(TopUpError):
                parse_topup_amount(bad)


def fake_client(session_id='cs_test_t1'):
    client = MagicMock()
    client.v1.checkout.sessions.create.return_value = SimpleNamespace(
        id=session_id, url=f'https://checkout.stripe.com/c/pay/{session_id}')
    return client


@override_settings(**LIMITS)
class StartTopUpTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('alice', 'alice@example.com', 'StrongPass123!')

    def test_creates_topup_and_returns_stripe_url(self):
        client = fake_client()
        with patch('payments.topups.get_stripe_client', return_value=client):
            url = start_topup(self.user, '25.00')
        self.assertEqual(url, 'https://checkout.stripe.com/c/pay/cs_test_t1')
        topup = TopUp.objects.get()
        self.assertEqual(topup.amount, Decimal('25.00'))
        self.assertEqual(topup.status, TopUp.Status.PENDING)
        self.assertEqual(topup.stripe_checkout_session_id, 'cs_test_t1')
        params = client.v1.checkout.sessions.create.call_args.args[0]
        self.assertEqual(params['line_items'][0]['price_data']['unit_amount'], 2500)
        self.assertEqual(params['metadata'], {'type': 'wallet_topup', 'topup_id': str(topup.pk)})

    def test_stripe_failure_marks_topup_failed(self):
        client = MagicMock()
        client.v1.checkout.sessions.create.side_effect = StripeError('boom')
        with patch('payments.topups.get_stripe_client', return_value=client):
            with self.assertRaises(TopUpError):
                start_topup(self.user, '25.00')
        self.assertEqual(TopUp.objects.get().status, TopUp.Status.FAILED)

    def test_wallet_balance_cap(self):
        credit(user=self.user, amount=Decimal('1990.00'),
               kind=WalletTransaction.Kind.ADJUSTMENT, reference='fund')
        with self.assertRaises(TopUpError):
            start_topup(self.user, '20.00')
        self.assertEqual(TopUp.objects.count(), 0)

    @override_settings(WALLET_TOPUP_MAX_ATTEMPTS_PER_HOUR=2)
    def test_attempt_rate_limit(self):
        for _ in range(2):
            TopUp.objects.create(user=self.user, amount=Decimal('10.00'), currency='usd')
        with self.assertRaises(TopUpError):
            start_topup(self.user, '10.00')

    def test_view_rejects_bad_amount_without_calling_stripe(self):
        self.client.force_login(self.user)
        with patch('payments.topups.get_stripe_client') as get_client:
            response = self.client.post(reverse('payments:topup'), {'amount': '1'})
        self.assertRedirects(response, reverse('wallets:overview'))
        get_client.assert_not_called()

    def test_view_redirects_to_stripe(self):
        self.client.force_login(self.user)
        url = 'https://checkout.stripe.com/c/pay/cs_test_x'
        with patch('payments.views.start_topup', return_value=url):
            response = self.client.post(reverse('payments:topup'), {'amount': '25'})
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response['Location'], url)


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET, STRIPE_CURRENCY='usd')
class TopUpWebhookTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('alice', 'alice@example.com', 'StrongPass123!')
        self.topup = TopUp.objects.create(
            user=self.user, amount=Decimal('25.00'), currency='usd',
            stripe_checkout_session_id='cs_test_t1')

    def session(self, **overrides):
        data = {
            'id': 'cs_test_t1',
            'metadata': {'type': 'wallet_topup', 'topup_id': str(self.topup.pk)},
            'payment_status': 'paid', 'amount_total': 2500,
            'currency': 'usd', 'payment_intent': 'pi_t1',
        }
        data.update(overrides)
        return data

    def send(self, event_type='checkout.session.completed', event_id='evt_1', **overrides):
        return post_signed(self.client, make_event(event_type, self.session(**overrides), event_id))

    def test_paid_event_credits_the_wallet(self):
        self.assertEqual(self.send().status_code, 200)
        self.topup.refresh_from_db()
        self.assertEqual(self.topup.status, TopUp.Status.COMPLETED)
        self.assertEqual(get_balance(self.user), Decimal('25.00'))
        txn = WalletTransaction.objects.get()
        self.assertEqual(txn.reference, 'topup:cs_test_t1')
        self.assertEqual(txn.kind, WalletTransaction.Kind.TOPUP)
        self.assertEqual(self.topup.wallet_transaction, txn)

    def test_the_same_event_twice_credits_once(self):
        self.send(event_id='evt_1')
        self.send(event_id='evt_1')
        self.assertEqual(get_balance(self.user), Decimal('25.00'))

    def test_two_different_events_for_one_payment_credit_once(self):
        self.send('checkout.session.completed', 'evt_1')
        self.send('checkout.session.async_payment_succeeded', 'evt_2')
        self.assertEqual(get_balance(self.user), Decimal('25.00'))
        self.assertEqual(WalletTransaction.objects.count(), 1)

    def test_amount_mismatch_credits_nothing(self):
        self.send(amount_total=100)
        self.topup.refresh_from_db()
        self.assertEqual(self.topup.status, TopUp.Status.PENDING)
        self.assertEqual(get_balance(self.user), Decimal('0.00'))

    def test_unpaid_session_waits(self):
        self.send(payment_status='unpaid')
        self.assertEqual(get_balance(self.user), Decimal('0.00'))

    def test_wrong_session_is_ignored(self):
        self.send(id='cs_other')
        self.assertEqual(get_balance(self.user), Decimal('0.00'))

    def test_expired_marks_expired(self):
        self.send('checkout.session.expired')
        self.topup.refresh_from_db()
        self.assertEqual(self.topup.status, TopUp.Status.EXPIRED)

    def test_failed_marks_failed(self):
        self.send('checkout.session.async_payment_failed')
        self.topup.refresh_from_db()
        self.assertEqual(self.topup.status, TopUp.Status.FAILED)

    def test_money_received_after_expiry_is_still_credited(self):
        self.topup.status = TopUp.Status.EXPIRED
        self.topup.save()
        self.send()
        self.assertEqual(get_balance(self.user), Decimal('25.00'))