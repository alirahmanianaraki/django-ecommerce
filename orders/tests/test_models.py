from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from myapp.models import Product
from orders.models import Order, OrderItem


class OrderModelTests(TestCase):
    def test_order_defaults_to_unpaid(self):
        user = User.objects.create_user(username="alice", password="StrongPass123!")
        order = Order.objects.create(user=user, total_amount=Decimal("100.00"))
        self.assertFalse(order.is_paied)
        self.assertIsNotNone(order.created_at)

    def test_order_str(self):
        user = User.objects.create_user(username="alice", password="StrongPass123!")
        order = Order.objects.create(user=user, total_amount=Decimal("100.00"))
        self.assertEqual(str(order), f"Order #{order.pk} - alice")

    def test_order_item_total_price_uses_unit_price(self):
        user = User.objects.create_user(username="alice", password="StrongPass123!")
        product = Product.objects.create(
            title="GPU", description="GPU", price=Decimal("125.50"), stock=5
        )
        order = Order.objects.create(user=user, total_amount=Decimal("251.00"))
        item = OrderItem.objects.create(
            order=order,
            product=product,
            quantity=2,
            unit_price=Decimal("125.50"),
        )
        self.assertEqual(item.total_price, Decimal("251.00"))

    def test_order_item_total_price_ignores_current_product_price(self):
        """Once a price is snapshotted, later changes to Product.price don't affect it."""
        user = User.objects.create_user(username="alice", password="StrongPass123!")
        product = Product.objects.create(
            title="GPU", description="GPU", price=Decimal("125.50"), stock=5
        )
        order = Order.objects.create(user=user, total_amount=Decimal("251.00"))
        item = OrderItem.objects.create(
            order=order,
            product=product,
            quantity=2,
            unit_price=Decimal("125.50"),
        )

        product.price = Decimal("999.99")
        product.save()

        item.refresh_from_db()
        self.assertEqual(item.unit_price, Decimal("125.50"))
        self.assertEqual(item.total_price, Decimal("251.00"))

    def test_order_shipping_snapshot_defaults_to_blank(self):
        user = User.objects.create_user(username="alice", password="StrongPass123!")
        order = Order.objects.create(user=user, total_amount=Decimal("100.00"))
        self.assertEqual(order.shipping_title, "")
        self.assertEqual(order.shipping_full_name, "")
        self.assertEqual(order.shipping_city, "")