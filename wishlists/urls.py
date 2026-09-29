from django.urls import path
from . import views
app_name = 'wishlists'

urlpatterns = [
    path('add-item/', views.add_item_to_wishlist, name='add_item_to_wishlist'),
    path('remove-item/', views.remove_item_from_wishlist, name='remove_item_from_wishlist'),
    path('overview/', views.wishlist_overview, name='wishlist_overview'),
]