# Top-up Logic

import logging
import time
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from stripe import StripeError

from wallets.models import WalletTransaction
from wallets.services import WalletError, credit, get_balance, to_money
from .models import TopUp
from .services import get_stripe_client, to_minor_units

logger = logging.getLogger(__name__)

class TopUpError(Exception):
    """
    A top-up problem whoe message is is safe to show to the customer
    """

def parse_topup_amount(raw):
    """
    Turn what the customer typed into a validated Decimal, or raise TopUpError.
    """
    try:
        amount = to_money((raw or '').strip())
    except WalletError:
        raise TopUpError('Please enter an amount')

    minimum = settings.WALLET_TOPUP_MIN_AMOUNT
    maximum = settings.WALLET_TOPUP_MAX_AMOUNT

    if amount < minimum:
        raise TopUpError(f"The minimum top-up is ${minimum}")
    if amount > maximum:
        raise TopUpError(f"The maximum top-up is ${maximum}")
    return amount

def start_topup(user, raw_amount):
    """
    Returns the Stripe URL to send the customer to.
    """
    amount = parse_topup_amount(raw_amount)

    # Soft checks.
    if get_balance(user) + amount > settings.WALLET_MAX_BALANCE:
        raise TopUpError(f"A wallet can hold at most ${settings.WALLET_MAX_BALANCE}.")
    since = timezone.now() - timedelta(hours=1)
    attempts = TopUp.objects.filter(user=user, created_at__gte=since).count()
    if attempts >= settings.WALLET_TOPUP_MAX_ATTEMPTS_PER_HOUR:
        raise TopUpError("Too many top-up attempts. Please try again later.")

    currency = settings.STRIPE_CURRENCY.lower()
    site_url = settings.SITE_URL.rstrip('/')
    if not site_url:
        raise ImproperlyConfigured('SITE_URL is not set')
    client = get_stripe_client()

    topup = TopUp.objects.create(user=user, amount=amount, currency=currency)

    params = {
        'mode': 'payment',
        'line_items': [{
            'quantity': 1,
            'price_data': {
                'currency': currency,
                'unit_amount': to_minor_units(amount),
                'product_data': {'name': 'Wallet top-up'},
            },
        }],
        'client_reference_id': f"topup-{topup.pk}",
        'metadata': {'type': 'wallet_topup', 'topup_id': str(topup.pk)},
        'payment_intent_data':{
            'metadata': {'type': 'wallet_topup', 'topup_id': str(topup.pk)},
        },
        'success_url': (site_url + reverse('payments:topup_success')
                        + '?session_id={CHECKOUT_SESSION_ID}'),
        'cancel_url': site_url + reverse('wallets:overview'),
        'expires_at': int(time.time()) + settings.STRIPE_CHECKOUT_EXPIRES_MINUTES * 60,
    }
    if user.email:
        params['customer_email'] = user.email

    try:
        session = client.v1.checkout.sessions.create(params)
    except StripeError:
        logger.exception(f"Stripe session creation failed for top-up {topup.pk}")
        topup.status = TopUp.Status.FAILED
        topup.save(update_fields=['status'])
        raise TopUpError('we could not start the payment. Please try again.')

    topup.stripe_checkout_session_id = session.id
    topup.save(update_fields=['stripe_checkout_session_id'])
    return session.url

# -------------------------------------------- Webhook handlers


def _get_locked_topup(session):
    """
    Find the TopUp a Stripe session belongs to, and lock its row.
    """
    topup_id = (session.get('metadata') or {}).get('topup_id')
    if not topup_id or not str(topup_id).isdigit():
        logger.error(f"Stripe session {session.get('id')} has no topup_id metadata")
        return None
    topup = TopUp.objects.select_for_update().filter(pk=int(topup_id)).first()
    if topup is None:
        logger.error(f"Stripe session {session.get('id')} points to missing top-up {topup_id}")
    return topup

@transaction.atomic
def complete_topup(session):
    """
    Money arrived: credit the wallet, exactly once
    """
    topup = _get_locked_topup(session)
    if topup is None:
        return

    if session.get('payment_status') != 'paid':
        # Delayed methods: wait for the 'async_payment_succeeded' event
        logger.info(f"Top-up session {session.get('id')} not paid yet; waiting")
        return

    # Duplicate
    if topup.status == TopUp.Status.COMPLETED:
        return

    session_id = session.get('id')
    if topup.stripe_checkout_session_id != session_id:
        logger.error(f"Top-up {topup.pk}: unexpected session {session_id}. Manual review needed")
        return

    expected = to_minor_units(topup.amount)
    currency = (session.get('currency') or '').lower()
    if session.get('amount_total') != expected or currency != topup.currency:
        logger.error(
            f"AMOUNT MISMATCH on top-up {topup.pk}: Stripe says "
            f"{session.get('amount_total')} {currency}, we expected {expected} {topup.currency}."
        )
        return 

    txn, _ = credit(
        user=topup.user, amount=topup.amount, kind=WalletTransaction.Kind.TOPUP,
        reference=f"topup:{session_id}", note='Wallet top-up'
    )
    topup.status = TopUp.Status.COMPLETED
    topup.completed_at = timezone.now()
    topup.stripe_payment_intent_id = session.get('payment_intent') or ''
    topup.wallet_transaction = txn
    topup.save(update_fields=[
        'status', 'completed_at', 'stripe_payment_intent_id', 'wallet_transaction',
    ])

def _close_if_current(session, new_status):
    topup = _get_locked_topup(session)
    if topup is None or topup.status != TopUp.Status.PENDING:
        return
    if topup.stripe_checkout_session_id != session.get('id'):
        return
    topup.status = new_status
    topup.save(update_fields=['status'])

@transaction.atomic
def expire_topup(session):
    _close_if_current(session, TopUp.Status.EXPIRED)

@transaction.atomic
def fail_topup(session):
    _close_if_current(session, TopUp.Status.FAILED)
