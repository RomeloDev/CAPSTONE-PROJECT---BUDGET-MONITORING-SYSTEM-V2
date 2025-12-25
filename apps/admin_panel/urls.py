from django.urls import path
from .views import AdminDashboardView, ApprovedBudgetListView
from . import views

urlpatterns = [
    path('dashboard/', AdminDashboardView.as_view(), name='admin_dashboard'),
    path('approved_budget/', ApprovedBudgetListView.as_view(), name='approved_budget'),
    path('approved_budget/<int:pk>/details/', views.approved_budget_detail, name='approved_budget_detail'),
    path('budget_allocation/', views.BudgetAllocationListView.as_view(), name='budget_allocation'),
    path('api/get-users-by-mfo/', views.get_users_by_mfo, name='get_users_by_mfo'),
    path('budget_allocation/<int:pk>/details/', views.budget_allocation_detail, name='budget_allocation_detail'),
    path('users/', views.ClientAccountsListView.as_view(), name='client_accounts'),
    path('users/<int:pk>/details/', views.user_detail, name='user_detail'),
    path('users/<int:pk>/toggle-status/', views.toggle_user_status, name='toggle_user_status'),
    path('users/bulk-action/', views.bulk_user_action, name='bulk_user_action'),
    path('audit-trail/', views.AuditTrailListView.as_view(), name='audit_trail'),
]