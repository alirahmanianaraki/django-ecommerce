from django.contrib.auth.models import User
from django.test import TestCase

from users.token import account_activation_token


class EmailVerificationTokenTests(TestCase):
    def test_token_is_valid_for_unchanged_user(self):
        user = User.objects.create_user(username="alice", password="StrongPass123!")
        token = account_activation_token.make_token(user)
        self.assertTrue(account_activation_token.check_token(user, token))

    def test_token_changes_when_active_state_changes(self):
        user = User.objects.create_user(
            username="alice", password="StrongPass123!", is_active=False
        )
        token = account_activation_token.make_token(user)   # hashed with is_active=False
        user.is_active = True
        user.save(update_fields=["is_active"])               # now is_active=True
        self.assertFalse(account_activation_token.check_token(user, token))