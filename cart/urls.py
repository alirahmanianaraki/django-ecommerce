from django.urls import path
from . import views

app_name = 'cart'

urlpatterns = [
    path('add-to-cart/', views.add_to_cart, name='add_to_cart'),
    path('cart-overview/', views.cart_overview, name='cart_overview'),
    path('update-cart/', views.update_cart, name='update_cart'),
    path('delete-cart/', views.delete_cart, name='delete_cart'),
]