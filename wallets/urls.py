from django.urls import path
from . import views

app_name = 'wallets'

urlpatterns = [
    path('', views.wallet_overview, name='overview')
]