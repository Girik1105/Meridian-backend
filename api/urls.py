from django.urls import path

from . import views_auth

urlpatterns = [
    path("auth/register/", views_auth.register, name="auth-register"),
    path("auth/login/", views_auth.login, name="auth-login"),
    path("auth/refresh/", views_auth.refresh, name="auth-refresh"),
    path("auth/logout/", views_auth.logout, name="auth-logout"),
    path("auth/me/", views_auth.me, name="auth-me"),
]
