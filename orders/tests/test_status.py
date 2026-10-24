from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from orders.models import Order, OrderItem, OrderStatusEvent
from orders.services import (
    InvalidStatusTransition,
    TrackingNumberRequired,
    transition_order,
)


class OrderStatusTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="alice", password="StrongPass123!"
        )
        self.order = Order.objects.create(
            user=self.user,
            total_amount=Decimal("100.00"),
            subtotal_amount=Decimal("100.00"),
            status=Order.Status.PENDING,
        )

    def test_pending_to_paid(self):
        transition_order(self.order, Order.Status.PAID, changed_by=self.user)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)
        self.assertTrue(self.order.is_paied)
        self.assertEqual(self.order.status_events.count(), 1)
        ev = self.order.status_events.first()
        self.assertEqual(ev.from_status, 'pending')
        self.assertEqual(ev.to_status, 'paid')

    def test_illegal_transition_raises(self):
        with self.assertRaises(InvalidStatusTransition):
            transition_order(self.order, Order.Status.DELIVERED)

    def test_same_status_is_noop(self):
        event = transition_order(self.order, Order.Status.PENDING)
        self.assertIsNone(event)
        self.assertEqual(self.order.status_events.count(), 0)

    def test_shipped_requires_tracking_number(self):
        transition_order(self.order, Order.Status.PAID)
        transition_order(self.order, Order.Status.PROCESSING)
        with self.assertRaises(TrackingNumberRequired):
            transition_order(self.order, Order.Status.SHIPPED)

    def test_shipped_with_tracking_number_records_it(self):
        transition_order(self.order, Order.Status.PAID)
        transition_order(self.order, Order.Status.PROCESSING)
        transition_order(
            self.order, Order.Status.SHIPPED, tracking_number="1Z999AA1"
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.SHIPPED)
        self.assertEqual(self.order.tracking_number, "1Z999AA1")

    def test_terminal_status_cannot_transition(self):
        transition_order(self.order, Order.Status.PAID)
        transition_order(self.order, Order.Status.PROCESSING)
        transition_order(
            self.order, Order.Status.SHIPPED, tracking_number="1Z"
        )
        transition_order(self.order, Order.Status.DELIVERED)
        with self.assertRaises(InvalidStatusTransition):
            transition_order(self.order, Order.Status.CANCELLED)

    def test_cancel_restores_stock(self):
        from myapp.models import Product

        product = Product.objects.create(
            title="GPU", description="x", price=Decimal("50.00"), stock=8
        )
        OrderItem.objects.create(
            order=self.order, product=product, quantity=2, unit_price=Decimal("50.00")
        )
        transition_order(self.order, Order.Status.CANCELLED)
        product.refresh_from_db()
        self.assertEqual(product.stock, 10)