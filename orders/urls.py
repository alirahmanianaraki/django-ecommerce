from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    path('checkout/', views.checkout, name='checkout'),
    path('place-order/', views.place_order_view, name='place_order'),
    path('order-success/', views.order_success, name='order_success'),
    path('order-failed/', views.order_failed, name='order_failed'),
    path('my-orders/', views.order_list, name='order_list'),
    path('my-orders/<int:pk>/', views.order_detail, name='order_detail'),
]