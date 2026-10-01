from django.contrib.auth.models import User
from django.test import TestCase

from users.models import Address


class AddressModelTests(TestCase):
    def test_str(self):
        user = User.objects.create_user(username="alice", password="StrongPass123!")
        address = Address.objects.create(
            user=user,
            title="Home",
            full_name="Alice Smith",
            description="123 Main Street",
            city="Amsterdam",
            state="North Holland",
            postal_code="1011AA",
            country="Netherlands",
        )
        self.assertEqual(str(address), "User: alice | Under name: Alice Smith | Title: Home")
