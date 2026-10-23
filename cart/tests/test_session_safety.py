# cart/tests/test_session_safety.py
import json
from decimal import Decimal

from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory, TestCase

from cart.cart import Cart
from myapp.models import Coupon, Product


class SessionSafetyTests(TestCase):
    def test_iterating_cart_does_not_mutate_session(self):
        product = Product.objects.create(
            title="GPU", description="x",
            price=Decimal("500.00"),
            discount_price=Decimal("400.00"),
            stock=10,
        )
        request = RequestFactory().get("/")
        request.session = SessionStore()
        cart = Cart(request)
        cart.add(str(product.pk), "2")

        # Force iteration, then JSON-encode the session.
        list(cart)
        # If __iter__ polluted the session, this raises TypeError.
        json.dumps(request.session['cart'])