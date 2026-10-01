from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes

from users.models import Address
from users.token import account_activation_token


class UserViewTests(TestCase):
    def setUp(self):
        self.password = "StrongPass123!"
        self.user = User.objects.create_user(
            username="alice", email="alice@example.com", password=self.password
        )

    @patch("users.views.get_current_site", return_value="example.com")
    @patch("django.contrib.auth.models.User.email_user")
    def test_register_creates_inactive_user_and_redirects(self, email_user, _site):
        response = self.client.post(
            reverse("users:register"),
            {
                "username": "newuser",
                "email": "new@example.com",
                "password1": self.password,
                "password2": self.password,
            },
        )
        self.assertRedirects(response, reverse("users:email_verification_sent"))
        new_user = User.objects.get(username="newuser")
        self.assertFalse(new_user.is_active)
        email_user.assert_called_once()

    def test_email_verification_activates_user(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        token = account_activation_token.make_token(self.user)
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))

        response = self.client.get(
            reverse("users:email_verification", kwargs={"uidb64": uid, "token": token})
        )
        self.assertRedirects(response, reverse("users:email_verification_success"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_email_verification_with_invalid_token_fails(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))

        response = self.client.get(
            reverse("users:email_verification", kwargs={"uidb64": uid, "token": "invalid"})
        )
        self.assertRedirects(response, reverse("users:email_verification_failed"))
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_login_with_valid_credentials_preserves_cart(self):
        session = self.client.session
        session["cart"] = {"123": {"price": "10.00", "qty": "2"}}
        session.save()

        response = self.client.post(
            reverse("users:login"),
            {"username": "alice", "password": self.password},
        )
        self.assertRedirects(response, reverse("myapp:index"))
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertEqual(self.client.session["cart"]["123"]["qty"], "2")

    def test_authenticated_user_visiting_login_is_redirected(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("users:login"))
        self.assertRedirects(response, reverse("myapp:index"))

    def test_logout_preserves_cart(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["cart"] = {"123": {"price": "10.00", "qty": "2"}}
        session.save()

        response = self.client.get(reverse("users:logout"))
        self.assertRedirects(response, reverse("myapp:index"))
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertEqual(self.client.session["cart"]["123"]["qty"], "2")

    def test_profile_requires_login(self):
        response = self.client.get(reverse("users:profile"))
        self.assertRedirects(
            response,
            f"{reverse('users:login')}?next={reverse('users:profile')}",
        )

    def test_profile_displays_user(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("users:profile"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/profile.html")
        self.assertEqual(response.context["user"], self.user)

    def test_add_address_creates_address_for_logged_in_user(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("users:add_address"),
            {
                "title": "Home",
                "full_name": "Alice Smith",
                "description": "123 Main Street",
                "city": "Amsterdam",
                "state": "North Holland",
                "postal_code": "1011AA",
                "country": "Netherlands",
            },
        )
        self.assertRedirects(response, reverse("users:profile"))
        address = Address.objects.get(user=self.user)
        self.assertEqual(address.city, "Amsterdam")

    @patch("users.views.get_current_site", return_value="example.com")
    @patch("django.contrib.auth.models.User.email_user")
    def test_modify_profile_with_same_email_updates_user(self, email_user, _site):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("users:modify_user_info"),
            {
                "username": "alice",
                "first_name": "Alice Updated",
                "last_name": "Smith",
                "email": "alice@example.com",
            },
        )
        self.assertRedirects(response, reverse("users:profile"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Alice Updated")
        email_user.assert_not_called()
