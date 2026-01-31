from django.urls import path
from django.contrib.auth.views import LogoutView
from .views import AdminLoginView, EndUserLoginView, logout_view, CustomPasswordResetCompleteView, CustomPasswordResetConfirmView, CustomPasswordResetDoneView, CustomPasswordResetView

urlpatterns = [
    path('', EndUserLoginView.as_view(), name='end_user_login'),
    path('admin/', AdminLoginView.as_view(), name='admin_login'),
    path('logout/', logout_view, name='logout'),
    
    # Password Reset Flow (Using Custom Views)
    path('password_reset/', CustomPasswordResetView.as_view(), name='password_reset'),
    path('password_reset/done/', CustomPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', CustomPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', CustomPasswordResetCompleteView.as_view(), name='password_reset_complete'),
]