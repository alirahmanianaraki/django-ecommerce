from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('webhook/', views.stripe_webhook, name='webhook'),
    path('orders/<int:pk>/pay/', views.pay_for_order, name='pay'),
    path('success/', views.payment_success, name='success'),
    path('orders/<int:pk>/pay-with-wallet/', views.pay_with_wallet, name='pay_with_wallet'),
]