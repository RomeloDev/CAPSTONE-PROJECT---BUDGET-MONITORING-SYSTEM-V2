from django.urls import path
from .views import EndUserDashboardView

urlpatterns = [
    path('dashboard/', EndUserDashboardView.as_view(), name='user_dashboard')
]
