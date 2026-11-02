from django.urls import path
from . import views
from . import compare_views

app_name = 'myapp'

urlpatterns = [
    path('', views.index, name='index'),
    path('product/<slug:slug>/', views.detail, name='detail'),
    path('product/<slug:slug>/notify/', views.notify_when_available, name='notify_when_available'),
    path('products/tags/<slug:slug>/', views.tag, name='tag'),
    path('search/', views.search, name='search'),
    path('category/<slug:slug>/', views.category, name='category'),
    path('compare/', compare_views.comparison_page, name='comparison'),
    path('compare/add/', compare_views.add_to_comparison, name='comparison_add'),
    path('compare/remove/', compare_views.remove_from_comparison, name='comparison_remove'),
]