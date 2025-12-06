from django.urls import path
from django.contrib.auth.views import LogoutView
from .views import AdminLoginView, EndUserLoginView, logout_view

urlpatterns = [
    path('login/', EndUserLoginView.as_view(), name='end_user_login'),
    path('admin/login/', AdminLoginView.as_view(), name='admin_login'),
    path('logout/', logout_view, name='logout'),
]