import hashlib
import hmac
import json
import time
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from myapp.models import Product
from orders.models import Order, OrderItem
from payments.models import StripeWebhookEvent

SECRET = "whsec_test_secret"


def post_signed(client, event):
    """Send a webhook exactly like Stripe does: HMAC-SHA256 of '<timestamp>.<body>'."""
    payload = json.dumps(event)
    ts = int(time.time())
    sig = hmac.new(SECRET.encode(), f"{ts}.{payload}".encode(), hashlib.sha256).hexdigest()
    return client.post(
        reverse("payments:webhook"), data=payload,
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE=f"t={ts},v1={sig}",
    )


def make_event(event_type, session, event_id="evt_1"):
    return {"id": event_id, "type": event_type, "data": {"object": session}}


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET, STRIPE_CURRENCY="usd")
class StripeWebhookTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@example.com", "StrongPass123!")
        # stock 8 = 10 originally, minus the 2 reserved by this order
        self.product = Product.objects.create(
            title="GPU", description="x", price=Decimal("100.00"), stock=8)
        self.order = Order.objects.create(
            user=self.user, subtotal_amount=Decimal("200.00"),
            total_amount=Decimal("200.00"), stripe_checkout_session_id="cs_test_1")
        OrderItem.objects.create(
            order=self.order, product=self.product, quantity=2,
            unit_price=Decimal("100.00"))

    def session(self, **overrides):
        data = {
            "id": "cs_test_1", "metadata": {"order_id": str(self.order.pk)},
            "payment_status": "paid", "amount_total": 20000,
            "currency": "usd", "payment_intent": "pi_123",
        }
        data.update(overrides)
        return data

    def test_bad_signature_is_rejected(self):
        response = self.client.post(
            reverse("payments:webhook"), data="{}",
            content_type="application/json", HTTP_STRIPE_SIGNATURE="t=1,v1=bad")
        self.assertEqual(response.status_code, 400)

    def test_paid_event_marks_order_paid(self):
        response = post_signed(self.client, make_event("checkout.session.completed", self.session()))
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)
        self.assertTrue(self.order.is_paied)
        self.assertEqual(self.order.stripe_payment_intent_id, "pi_123")
        self.assertIsNotNone(self.order.paid_at)

    def test_duplicate_event_is_processed_once(self):
        event = make_event("checkout.session.completed", self.session())
        post_signed(self.client, event)
        post_signed(self.client, event)
        self.assertEqual(StripeWebhookEvent.objects.count(), 1)
        self.assertEqual(self.order.status_events.count(), 1)

    def test_amount_mismatch_does_not_mark_paid(self):
        response = post_signed(self.client, make_event(
            "checkout.session.completed", self.session(amount_total=100)))
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING)

    def test_unpaid_async_session_waits(self):
        post_signed(self.client, make_event(
            "checkout.session.completed", self.session(payment_status="unpaid")))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING)

    def test_expired_session_cancels_order_and_restores_stock(self):
        post_signed(self.client, make_event("checkout.session.expired", self.session()))
        self.order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CANCELLED)
        self.assertEqual(self.product.stock, 10)

    def test_stale_expired_session_is_ignored(self):
        post_signed(self.client, make_event(
            "checkout.session.expired", self.session(id="cs_old")))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING)


class PayViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", password="StrongPass123!")
        self.order = Order.objects.create(user=self.user, total_amount=Decimal("10.00"))

    def test_pay_redirects_to_stripe(self):
        self.client.force_login(self.user)
        url = "https://checkout.stripe.com/c/pay/cs_test_x"
        with patch("payments.views.get_or_create_checkout_url", return_value=url):
            response = self.client.post(reverse("payments:pay", args=[self.order.pk]))
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response["Location"], url)

    def test_cannot_pay_someone_elses_order(self):
        other = User.objects.create_user("bob", password="StrongPass123!")
        self.client.force_login(other)
        response = self.client.post(reverse("payments:pay", args=[self.order.pk]))
        self.assertEqual(response.status_code, 404)