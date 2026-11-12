from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('webhook/', views.stripe_webhook, name='webhook'),
    path('orders/<int:pk>/pay/', views.pay_for_order, name='pay'),
    path('orders/<int:pk>/pay-with-wallet/', views.pay_with_wallet, name='pay_with_wallet'),
    path('success/', views.payment_success, name='success'),
    path('topup/', views.start_topup_view, name='topup'),
    path('topup/success/', views.topup_success, name='topup_success'),
]