from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'users'

urlpatterns = [
    # Login, Logout and Register
    path('register/', views.register_user, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('profile/', views.profile, name='profile'),
    path('profile/modify/', views.modify_user_info, name='modify_user_info'),
    path('profile/modify/add-address', views.add_address, name='add_address'),
    # Email Verification
    path('email-verification/<str:uidb64>/<str:token>', views.email_verification, name='email_verification'),
    path('email-verification/sent', views.email_verification_sent, name='email_verification_sent'),
    path('email-verification-success/', views.email_verification_success, name='email_verification_success'),
    path('email-verification-failed/', views.email_verification_failed, name='email_verification_failed'),
]