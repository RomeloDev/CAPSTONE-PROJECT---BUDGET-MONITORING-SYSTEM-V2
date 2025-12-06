from django.urls import path
from .views import AdminDashboardView, ApprovedBudgetListView
from . import views

urlpatterns = [
    path('dashboard/', AdminDashboardView.as_view(), name='admin_dashboard'),
    path('approved_budget/', ApprovedBudgetListView.as_view(), name='approved_budget'),
    path('approved_budget/<int:pk>/details/', views.approved_budget_detail, name='approved_budget_detail'),
]