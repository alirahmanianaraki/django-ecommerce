from django.urls import path
from . import views

app_name = 'myapp'

urlpatterns = [
    path('', views.index, name='index'),
    path('product/<slug:slug>/', views.detail, name='detail'),
    path('product/<slug:slug>/notify/', views.notify_when_available, name='notify_when_available'),
    path('products/tags/<slug:slug>/', views.tag, name='tag'),
    path('search/', views.search, name='search'),
    path('category/<slug:slug>/', views.category, name='category')
]