from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
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
    return render(request, 'wallets/wallet_overview.html',
                  {
                      'balance': balance,
                      'page_obj': page_obj,
                      **pagination_context
                  })