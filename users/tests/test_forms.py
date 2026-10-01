from django.contrib.auth.models import User
from django.test import TestCase

from users.forms import AddressForm, CreateUserForm, LoginForm, ProfileForm


class UserFormTests(TestCase):
    def test_create_user_form_has_expected_fields(self):
        self.assertEqual(
            list(CreateUserForm().fields),
            ["username", "email", "password1", "password2"],
        )

    def test_create_user_form_valid_data(self):
        form = CreateUserForm(
            data={
                "username": "alice",
                "email": "alice@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_login_form_accepts_valid_credentials(self):
        user = User.objects.create_user(username="alice", password="StrongPass123!")
        form = LoginForm(
            request=None,
            data={"username": "alice", "password": "StrongPass123!"},
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.get_user(), user)


class ProfileFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="alice", email="alice@example.com", password="StrongPass123!"
        )

    def valid_data(self, **overrides):
        data = {
            "username": "alice",
            "first_name": "Alice",
            "last_name": "Smith",
            "email": "alice@example.com",
        }
        data.update(overrides)
        return data

    def test_same_user_can_keep_username_and_email(self):
        form = ProfileForm(data=self.valid_data(), instance=self.user)
        self.assertTrue(form.is_valid(), form.errors)

    def test_duplicate_username_is_rejected(self):
        User.objects.create_user(username="bob", email="bob@example.com")
        form = ProfileForm(data=self.valid_data(username="bob"), instance=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn("Username already exists", form.errors["username"])

    def test_duplicate_email_is_rejected(self):
        User.objects.create_user(username="bob", email="bob@example.com")
        form = ProfileForm(data=self.valid_data(email="bob@example.com"), instance=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn("Email already exists", form.errors["email"])


class AddressFormTests(TestCase):
    def test_user_is_excluded_from_form(self):
        self.assertNotIn("user", AddressForm().fields)

    def test_valid_address(self):
        form = AddressForm(
            data={
                "title": "Home",
                "full_name": "Alice Smith",
                "description": "123 Main Street",
                "city": "Amsterdam",
                "state": "North Holland",
                "postal_code": "1011AA",
                "country": "Netherlands",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
