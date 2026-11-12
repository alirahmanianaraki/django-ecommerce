from decimal import Decimal
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from myapp.pagination import paginate
from .models import Wallet, WalletTransaction

@login_required(login_url='users:login')
def wallet_overview(request):
    wallet = Wallet.objects.filter(user=request.user).first()
    balance = wallet.balance if wallet else Decimal('0.00')
    transactions = (WalletTransaction.objects
                    .filter(wallet__user=request.user)
                    .select_related('order'))
    page_obj, pagination_context = paginate(request, transactions)

    minimum = settings.WALLET_TOPUP_MIN_AMOUNT
    maximum = settings.WALLET_TOPUP_MAX_AMOUNT
    presets = [Decimal(p) for p in ('10', '25', '50', '100') if minimum <= Decimal(p) <= maximum]
    pending_topups = request.user.wallet_topups.filter(
        status='pending', created_at__gte=timezone.now() - timedelta(days=2),
    )
    return render(request, 'wallets/wallet_overview.html',
                  {
                      'balance': balance,
                      'page_obj': page_obj,
                      'topup_min': minimum,
                      'topup_max': maximum,
                      'presets': presets,
                      'pending_topups': pending_topups,
                      **pagination_context
                  })