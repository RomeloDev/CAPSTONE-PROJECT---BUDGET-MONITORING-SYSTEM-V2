from django.urls import path
from .views import AdminDashboardView, ApprovedBudgetListView
from . import views

urlpatterns = [
    path('dashboard/', AdminDashboardView.as_view(), name='admin_dashboard'),
    path('approved_budget/', ApprovedBudgetListView.as_view(), name='approved_budget'),
    path('approved_budget/report/pdf/', views.export_approved_budget_report_pdf, name='export_approved_budget_report_pdf'),
    path('approved_budget/<int:pk>/details/', views.approved_budget_detail, name='approved_budget_detail'),
    path('budget_allocation/', views.BudgetAllocationListView.as_view(), name='budget_allocation'),
    path('api/get-users-by-mfo/', views.get_users_by_mfo, name='get_users_by_mfo'),
    path('budget_allocation/<int:pk>/details/', views.budget_allocation_detail, name='budget_allocation_detail'),
    path('users/', views.ClientAccountsListView.as_view(), name='client_accounts'),
    path('users/<int:pk>/details/', views.user_detail, name='user_detail'),
    path('users/<int:pk>/toggle-status/', views.toggle_user_status, name='toggle_user_status'),
    path('users/bulk-action/', views.bulk_user_action, name='bulk_user_action'),
    path('audit-trail/', views.AuditTrailListView.as_view(), name='audit_trail'),
    path('pre/', views.PRERequestListView.as_view(), name='admin_pre_list'),
    path('pre/<uuid:pk>/', views.PREDetailView.as_view(), name='admin_pre_detail'),
    path('pre/<uuid:pre_id>/action/', views.admin_handle_pre_action, name='admin_handle_pre_action'),
    path('pre/<uuid:pre_id>/verify/', views.admin_verify_and_approve_pre, name='admin_verify_and_approve_pre'),
    path('pre/<uuid:pre_id>/upload-doc/', views.admin_upload_approved_document, name='admin_upload_approved_document'), 
    path('pr-requests/', views.AdminPRListView.as_view(), name='admin_pr_list'),
    path('pr-requests/<uuid:pr_id>/', views.AdminPRDetailView.as_view(), name='admin_pr_detail'),
    path('pr-requests/<uuid:pr_id>/action/', views.handle_pr_action, name='admin_pr_action'),
    path('pr-requests/<uuid:pr_id>/verify/', views.admin_verify_and_approve_pr, name='admin_verify_and_approve_pr'),
    path('department/ad-requests/', views.DepartmentADRequestView.as_view(), name='department_ad_request'),
    path('department/ad-requests/<uuid:pk>/handle/', views.HandleADRequestView.as_view(), name='handle_activity_design_request'),
    # Add detail view path if you implement AdminADDetailView
    path('department/ad-requests/<uuid:pk>/details/', views.AdminADDetailView.as_view(), name='admin_preview_ad'),
    path('realignment/', views.AdminPREBudgetRealignmentListView.as_view(), name='admin_realignment_list'),
    path('realignment/<int:pk>/', views.AdminPREBudgetRealignmentDetailView.as_view(), name='admin_realignment_detail'),
    path('realignment/<int:pk>/action/', views.handle_admin_realignment_action, name='handle_admin_realignment_action'),
]